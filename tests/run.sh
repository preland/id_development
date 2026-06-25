#!/usr/bin/env bash
# Regression tests for idc. Run from anywhere: tests/run.sh
set -u
cd "$(dirname "$0")"
IDC=../idc.py
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
pass=0 fail=0

ok()   { pass=$((pass+1)); echo "PASS: $1"; }
bad()  { fail=$((fail+1)); echo "FAIL: $1"; }

expect_output() { # name, expected, actual
    if [ "$2" = "$3" ]; then ok "$1"; else bad "$1 (expected '$2', got '$3')"; fi
}
expect_error() { # name, file, pattern
    if $IDC "$2" -o "$TMP/x" 2>&1 | grep -q "$3"; then ok "$1"; else bad "$1"; fi
}

# --- hello_world end to end (needs examples/otherfn.id for testfn's link dep)
$IDC ../hello_world.id ../examples/otherfn.id -o "$TMP/hello" 2>/dev/null \
    || bad "hello_world compiles"
expect_output "usage message"  "usage: $TMP/hello <message>" "$("$TMP/hello")"
expect_output "hello with arg" "hello world: hi"             "$("$TMP/hello" hi)"

# --- demos/ projects compile and run as documented
$IDC ../demos/calc -o "$TMP/calc" 2>/dev/null \
    || bad "calc demo compiles"
expect_output "calc demo output" "total = 42 (positive)" "$("$TMP/calc")"
"$TMP/calc" >/dev/null; expect_output "calc demo exit code" "42" "$?"

$IDC ../demos/control/flow.id -o "$TMP/flow" 2>/dev/null \
    || bad "control demo compiles"
expect_output "control demo output" "7 is a big odd / medium" "$("$TMP/flow")"

# --- adventure demo: input() builtin + cross-file branching to 8 endings.
#     Feed a choice sequence on stdin and check which ending it reaches.
$IDC ../demos/adventure -o "$TMP/adv" 2>/dev/null \
    || bad "adventure demo compiles"
expect_output "adventure path 1,1,1" "ENDING 1" \
    "$(printf '1\n1\n1\n' | "$TMP/adv" | grep -o 'ENDING [0-9]')"
expect_output "adventure path 2,2,2" "ENDING 8" \
    "$(printf '2\n2\n2\n' | "$TMP/adv" | grep -o 'ENDING [0-9]')"
expect_output "adventure path 2,1,2" "ENDING 6" \
    "$(printf '2\n1\n2\n' | "$TMP/adv" | grep -o 'ENDING [0-9]')"
expect_output "adventure invalid choice" ">> You freeze with indecision and your torch gutters out. THE END." \
    "$(printf 'x\n' | "$TMP/adv" | grep '>>')"

# --- while loop + string builtins (len/charat/chr)
cat > "$TMP/scan.id" <<'EOF'
main() {
  string s = "aZ9";
  int i = 0;
  while(i < len(s)) {
    print(i + ":" + charat(s, i) + ":" + chr(charat(s, i)));
    i = i + 1;
  }
} return int 0;
EOF
$IDC "$TMP/scan.id" -o "$TMP/scan" 2>/dev/null || bad "while/len/charat/chr compiles"
expect_output "string builtins walk" "0:97:a 1:90:Z 2:57:9" "$("$TMP/scan" | tr '\n' ' ' | sed 's/ $//')"

# --- idc-in-id: the lexer (written in id) tokenizes id source from stdin
$IDC ../demos/idc_in_id -o "$TMP/idlex" 2>/dev/null || bad "idc-in-id lexer compiles"
expect_output "id-lexer keyword"    "kw while"   "$(printf 'while' | "$TMP/idlex" | head -1)"
expect_output "id-lexer two-char op" "op =="     "$(printf 'x == 2' | "$TMP/idlex" | sed -n 2p)"
expect_output "id-lexer string lit" 'str "hi"'   "$(printf '"hi"'   | "$TMP/idlex" | head -1)"
expect_output "id-lexer comment skip + eof" "eof" "$(printf '// just a comment\n' | "$TMP/idlex" | head -1)"

# --- export/import roundtrip at runtime
cat > "$TMP/roundtrip.id" <<'EOF'
main() {
  export int code = 7;
  string msg = describe();
  print(msg);
} return int code;

describe() {
  string s = "";
  if((import code) = 7) {
    s = "lucky " + (import code);
  } else {
    s = "boring";
  }
} return string s;
EOF
$IDC "$TMP/roundtrip.id" -o "$TMP/roundtrip" 2>/dev/null || bad "roundtrip compiles"
expect_output "export/import roundtrip" "lucky 7" "$("$TMP/roundtrip")"
"$TMP/roundtrip" >/dev/null; expect_output "exit code from exported var" "7" "$?"

# --- rule violations must be compile errors
cat > "$TMP/toomany.id" <<'EOF'
main() {
  int a = 1;
  int b = 2;
  int c = 3;
  int d = 4;
} return int 0;
EOF
expect_error "action limit enforced" "$TMP/toomany.id" "performs 4 actions"

cat > "$TMP/fourfns.id" <<'EOF'
f1() {} return void;
f2() {} return void;
f3() {} return void;
f4() {} return void;
EOF
expect_error "3 functions per file" "$TMP/fourfns.id" "too many functions"

# a name may repeat across functions when its type is consistent...
cat > "$TMP/reuse.id" <<'EOF'
inc(int i) { int r = i + 1; } return int r;
dec(int i) { int r = i - 1; } return int r;
main() { int r = inc(10) + dec(10); print("r=" + r); } return int 0;
EOF
$IDC "$TMP/reuse.id" -o "$TMP/reuse" 2>/dev/null || bad "name reuse (same type) compiles"
expect_output "name reuse same type" "r=20" "$("$TMP/reuse")"

# ...but the same name with two different types is an error
cat > "$TMP/typeconflict.id" <<'EOF'
main() { int count = 1; } return int 0;
other() { string count = "hi"; } return void;
EOF
expect_error "name keeps one type" "$TMP/typeconflict.id" "must keep one type"

cat > "$TMP/noimport.id" <<'EOF'
main() { int x = 1; } return int 0;
other() { int y = x; } return void;
EOF
expect_error "cross-function use needs import" "$TMP/noimport.id" "not exported"

cat > "$TMP/badimport.id" <<'EOF'
main() { int x = 1; } return int 0;
other() { int y = (import x); } return void;
EOF
expect_error "import requires export" "$TMP/badimport.id" "is not exported"

echo
echo "$pass passed, $fail failed"

# --- negative tests: every file in tests/invalid/ must be rejected with the
#     error named on its `// EXPECT:` line.
echo
echo "--- negative tests (tests/invalid/) ---"
./invalid.sh
neg=$?

[ "$fail" -eq 0 ] && [ "$neg" -eq 0 ]
