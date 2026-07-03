#!/usr/bin/env bash
# Self-hosted-driver tests: bin/idc (the id-written lexer+parser driven by a
# bash driver -- see bin/idc) must build several demos to binaries whose
# RUNTIME OUTPUT matches the idc.py-built binary exactly, and its --emit-c
# output must be byte-identical to idc.py's for programs the self-hosted
# compiler fully supports.
#
# Note: bin/idc transparently falls back to idc.py for input the self-hosted
# stages can't yet handle (e.g. demos/hello, which has a float literal --
# see README.md "Self-hosting"), printing a note on stderr when it does. This
# suite checks END-TO-END CORRECTNESS of bin/idc as the build command, not
# whether the self-hosted path specifically (rather than its fallback)
# produced any particular binary -- tools/parity.sh and tests/run.sh's
# "codegen parity" section already cover self-hosted/idc.py byte-parity
# directly.
#
# Run from anywhere: tests/self_host_build.sh
set -u
cd "$(dirname "$0")"
IDC=../idc.py
BIN_IDC=../bin/idc
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
pass=0 fail=0

ok()  { pass=$((pass+1)); echo "PASS: $1"; }
bad() { fail=$((fail+1)); echo "FAIL: $1"; }

# build_pair NAME PROG -- builds PROG with both compilers into $TMP/NAME_py
# and $TMP/NAME_self; returns nonzero (and records a FAIL) if either fails.
build_pair() {
    local name="$1" prog="$2"
    if ! $IDC "$prog" -o "$TMP/${name}_py" >/dev/null 2>"$TMP/${name}.pyerr"; then
        bad "$name: idc.py build (see $(cat "$TMP/${name}.pyerr" | head -1))"
        return 1
    fi
    if ! $BIN_IDC "$prog" -o "$TMP/${name}_self" >/dev/null 2>"$TMP/${name}.selferr"; then
        bad "$name: bin/idc build (see $(cat "$TMP/${name}.selferr" | head -1))"
        return 1
    fi
    ok "$name: idc.py and bin/idc both build"
}

# check_output NAME [ARGS...] -- runs both binaries with the same args/stdin
# behavior and compares stdout+stderr.
check_output() {
    local name="$1"; shift
    local out_py out_self
    out_py=$("$TMP/${name}_py" "$@" 2>&1)
    out_self=$("$TMP/${name}_self" "$@" 2>&1)
    if [ "$out_py" = "$out_self" ]; then
        ok "$name: bin/idc binary output matches idc.py binary"
    else
        bad "$name: output mismatch (idc.py='$out_py' bin/idc='$out_self')"
    fi
}

build_pair hello ../demos/hello && check_output hello hi
build_pair calc ../demos/calc && check_output calc
build_pair control ../demos/control/flow.id && check_output control

if build_pair adventure ../demos/adventure; then
    for choices in "1 1 1" "2 2 2" "2 1 2"; do
        out_py=$(printf '%s\n' $choices | "$TMP/adventure_py" | grep -o 'ENDING [0-9]')
        out_self=$(printf '%s\n' $choices | "$TMP/adventure_self" | grep -o 'ENDING [0-9]')
        if [ "$out_py" = "$out_self" ]; then
            ok "adventure ($choices): bin/idc matches idc.py"
        else
            bad "adventure ($choices): mismatch (idc.py='$out_py' bin/idc='$out_self')"
        fi
    done
fi

# --emit-c byte parity through the driver (a couple of programs the
# self-hosted compiler fully supports today -- see tools/parity.sh)
for prog in ../demos/calc ../demos/control/flow.id ../demos/adventure; do
    $IDC "$prog" --emit-c "$TMP/ec_py.c" >/dev/null 2>&1
    $BIN_IDC "$prog" --emit-c "$TMP/ec_self.c" >/dev/null 2>&1
    if diff "$TMP/ec_py.c" "$TMP/ec_self.c" >/dev/null; then
        ok "emit-c byte parity via bin/idc ($prog)"
    else
        bad "emit-c byte parity via bin/idc ($prog)"
    fi
done

# a no-main project (a library) must build to a .o with bin/idc too
if $BIN_IDC ../demos/engine -o "$TMP/engine_self.o" >/dev/null 2>&1 \
   && [ -f "$TMP/engine_self.o" ]; then
    ok "engine (no main -> .o) builds via bin/idc"
else
    bad "engine (no main -> .o) builds via bin/idc"
fi

# bootstrap caching: a second invocation must not rebuild idlex/idparse
cache_before=$(stat -c %Y ../.idc-cache/idlex 2>/dev/null || stat -f %m ../.idc-cache/idlex 2>/dev/null)
$BIN_IDC ../demos/calc -o "$TMP/calc_self2" >/dev/null 2>"$TMP/cache.err"
cache_after=$(stat -c %Y ../.idc-cache/idlex 2>/dev/null || stat -f %m ../.idc-cache/idlex 2>/dev/null)
if [ "$cache_before" = "$cache_after" ] && ! grep -q "bootstrapping" "$TMP/cache.err"; then
    ok "bin/idc caches idlex/idparse across runs (no rebuild)"
else
    bad "bin/idc caches idlex/idparse across runs (no rebuild)"
fi

echo
echo "$pass passed, $fail failed"
[ "$fail" -eq 0 ]
