#!/usr/bin/env bash
# The kernel boots, and says so.
#
# This is the test that makes "no C runtime" a claim rather than an intention:
# the image contains the kernel, the runtime, a boot stub and a linker script,
# and nothing that came from C source. If the runtime written in `id` is wrong
# about strings or arithmetic, there is no libc underneath to be right instead.
#
# Run from anywhere: tests/kernel.sh   (needs clang, ld.lld and qemu)
set -u
cd "$(dirname "$0")"
ROOT=..
pass=0 fail=0
ok()  { pass=$((pass+1)); echo "PASS: $1"; }
bad() { fail=$((fail+1)); echo "FAIL: $1"; }

for tool in clang ld.lld qemu-system-x86_64; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "SKIP: kernel tests (need $tool on PATH -- run via 'tools/devshell.sh tests/kernel.sh')"
        exit 0
    fi
done

TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
ELF="$TMP/kernel.elf"

if ! "$ROOT/tools/kbuild.sh" "$ELF" >"$TMP/build.log" 2>&1; then
    bad "the kernel builds ($(grep -v 'warning:\|cc-wrapper\|un-wrapped' "$TMP/build.log" | head -1))"
    echo; echo "$pass passed, $fail failed"; exit 1
fi
ok "the kernel builds"

# Nothing in the image may have come from a C compiler. The runtime's own
# object is the whole runtime, so a libc symbol here would mean something was
# linked that this repository did not compile from `id`.
if command -v llvm-nm >/dev/null 2>&1; then
    if llvm-nm --undefined-only "$ELF" 2>/dev/null | grep -q .; then
        bad "the kernel has no undefined symbols ($(llvm-nm --undefined-only "$ELF" | head -3 | tr '\n' ' '))"
    else
        ok "the kernel has no undefined symbols"
    fi
fi

got=$(timeout 30 qemu-system-x86_64 -kernel "$ELF" -serial stdio -display none -no-reboot 2>/dev/null)
want=$(cat kernel_expect.txt)
if [ "$got" = "$want" ]; then
    ok "the kernel boots and prints what it should"
else
    bad "the kernel boots and prints what it should"
    diff <(printf '%s\n' "$want") <(printf '%s\n' "$got") | head -20
fi

# -- the runtime written in `id`, against the runtime written in C ----------
# Everything the kernel demonstrates after its two boot lines is ordinary `id`
# that says nothing about where it runs. So the same source builds hosted, on
# the C runtime, and the two must agree -- which is the only check that says
# the `id`-written runtime is *right* rather than merely present. A wrong
# `str_of_int` produces a kernel that boots and lies.
HOST="$TMP/host"
mkdir -p "$HOST"
cp -r "$ROOT/kernel/prog/show" "$HOST/show"
cat > "$HOST/main.id" <<'IDEOF'
main(int argc, string[] argv) {
  show_all();
} return int 0;
IDEOF
if "$ROOT/bin/idc" "$HOST" --no-std -o "$TMP/host.bin" >"$TMP/host.log" 2>&1; then
    host_out=$("$TMP/host.bin" 2>&1)
    kern_out=$(printf '%s\n' "$got" | tail -n +3)
    if [ "$host_out" = "$kern_out" ]; then
        ok "the id-written runtime agrees with the C runtime, line for line"
    else
        bad "the id-written runtime agrees with the C runtime, line for line"
        diff <(printf '%s\n' "$host_out") <(printf '%s\n' "$kern_out") | head -20
    fi
else
    bad "the kernel's demonstrations build hosted ($(head -1 "$TMP/host.log"))"
fi

echo
echo "$pass passed, $fail failed"
[ "$fail" -eq 0 ]
