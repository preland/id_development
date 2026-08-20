#!/usr/bin/env bash
# Negative tests for idc: every .id file under tests/invalid/ must fail to
# compile, AND its error must contain the string on its `// EXPECT:` line --
# under BOTH compilers.
#
# Both, because for a long time only idc.py was checked here, and bin/idc --
# the primary compiler -- was quietly failing 15 of these cases: it rejected
# them, but by handing the generated C to `cc` and reporting the C compiler's
# complaint under the heading "this is a bug in the self-hosted compiler".
# The program was wrong, the message blamed the compiler, and nothing in the
# suite noticed because nothing here ran bin/idc. A diagnostic that only one
# of two compilers produces is a diagnostic the primary one may not have.
#
# Add a case by dropping a new .id file in tests/invalid/ with an EXPECT line.
#
# Run from anywhere: tests/invalid.sh
set -u
# Hermetic: these checks assert on exact diagnostics, exact emitted C, or the
# compiler's own bootstrap, none of which may change because a standard library
# happens to exist beside this repository. stdlib.sh covers that path instead.
export IDC_NO_STD=1

cd "$(dirname "$0")"
IDC=../idc.py
BIN_IDC=../bin/idc
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
pass=0 fail=0

# check_one COMPILER LABEL FILE EXPECT -- must exit nonzero and print EXPECT
check_one() {
    local cc="$1" label="$2" f="$3" expect="$4" out rc
    out=$("$cc" "$f" -o "$TMP/out" 2>&1)
    rc=$?
    if [ "$rc" -eq 0 ]; then
        echo "FAIL: $label (compiled successfully; expected error '$expect')"
        fail=$((fail+1)); return
    fi
    if printf '%s' "$out" | grep -qF "$expect"; then
        echo "PASS: $label"
        pass=$((pass+1))
    else
        echo "FAIL: $label (expected '$expect')"
        echo "      got: $(printf '%s' "$out" | head -1)"
        fail=$((fail+1))
    fi
}

for f in invalid/*.id; do
    name=$(basename "$f" .id)
    expect=$(sed -n 's@^// EXPECT: @@p' "$f" | head -1)
    if [ -z "$expect" ]; then
        echo "FAIL: $name (no '// EXPECT:' line in $f)"; fail=$((fail+1)); continue
    fi
    check_one "$IDC"     "$name [idc.py]"  "$f" "$expect"
    check_one "$BIN_IDC" "$name [bin/idc]" "$f" "$expect"
done

echo
echo "$pass passed, $fail failed"
[ "$fail" -eq 0 ]
