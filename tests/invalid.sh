#!/usr/bin/env bash
# Negative tests for idc: every .id file under tests/invalid/ must fail to
# compile, AND its error must contain the string on its `// EXPECT:` line.
# Add a case by dropping a new .id file in tests/invalid/ with an EXPECT line.
#
# Run from anywhere: tests/invalid.sh
set -u
cd "$(dirname "$0")"
IDC=../idc.py
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
pass=0 fail=0

for f in invalid/*.id; do
    name=$(basename "$f" .id)
    expect=$(sed -n 's@^// EXPECT: @@p' "$f" | head -1)
    if [ -z "$expect" ]; then
        echo "FAIL: $name (no '// EXPECT:' line in $f)"; fail=$((fail+1)); continue
    fi

    out=$($IDC "$f" -o "$TMP/out" 2>&1)
    rc=$?

    if [ "$rc" -eq 0 ]; then
        echo "FAIL: $name (compiled successfully; expected error '$expect')"
        fail=$((fail+1)); continue
    fi
    if printf '%s' "$out" | grep -qF "$expect"; then
        echo "PASS: $name"
        pass=$((pass+1))
    else
        echo "FAIL: $name (expected '$expect')"
        echo "      got: $(printf '%s' "$out" | head -1)"
        fail=$((fail+1))
    fi
done

echo
echo "$pass passed, $fail failed"
[ "$fail" -eq 0 ]
