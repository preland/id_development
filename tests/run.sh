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

# --- growable lists: empty literal, push across a call (reference semantics),
#     len, index get/set, and to_int. seed() fills [0,1,4,9] through a list
#     passed by reference; done() overwrites xs[0] via index-assign + to_int.
cat > "$TMP/listrun.id" <<'EOF'
seed(int[] xs) {
  int i = 0;
  while(i < 4) {
    push(xs, i * i);
    i = i + 1;
  }
} return void;

done(int[] xs) {
  xs[0] = to_int("99");
  print("len=" + len(xs) + " xs[0]=" + xs[0] + " xs[3]=" + xs[3]);
} return void;

main() {
  int[] xs = [];
  seed(xs);
  done(xs);
} return int 0;
EOF
$IDC "$TMP/listrun.id" -o "$TMP/listrun" 2>/dev/null || bad "list runtime compiles"
expect_output "lists push/get/set/to_int" "len=4 xs[0]=99 xs[3]=9" "$("$TMP/listrun")"

# --- idc-in-id: the lexer (written in id) tokenizes id source from stdin
$IDC ../demos/idc_in_id -o "$TMP/idlex" 2>/dev/null || bad "idc-in-id lexer compiles"
expect_output "id-lexer keyword"    "kw while"   "$(printf 'while' | "$TMP/idlex" | head -1)"
expect_output "id-lexer two-char op" "op =="     "$(printf 'x == 2' | "$TMP/idlex" | sed -n 2p)"
expect_output "id-lexer string lit" 'str "hi"'   "$(printf '"hi"'   | "$TMP/idlex" | head -1)"
expect_output "id-lexer comment skip + eof" "eof" "$(printf '// just a comment\n' | "$TMP/idlex" | head -1)"

# --- idc-in-id stage 2: the calculator (parser + evaluator + printer written
#     in id), fed by the stage-1 lexer through a pipe
$IDC ../demos/idc_in_id_calc -o "$TMP/idcalc" 2>/dev/null || bad "idc-in-id calc compiles"
expect_output "calc parse+print" "(+ 2 (* 3 4))" \
    "$(echo '2 + 3 * 4' | "$TMP/idlex" | "$TMP/idcalc" | head -1)"
expect_output "calc evaluate" "= 14" \
    "$(echo '2 + 3 * 4' | "$TMP/idlex" | "$TMP/idcalc" | tail -1)"
expect_output "calc precedence/parens/unary/%" "= 13" \
    "$(echo '2 * (3 + 4) - 10 % 3' | "$TMP/idlex" | "$TMP/idcalc" | tail -1)"

# --- idc-in-id stage 2b/3: the function/statement parser + C emitter (written
#     in id), fed by the lexer. `idparse ast` prints the AST as an S-expression;
#     `idparse` (no arg) emits C.
$IDC ../demos/idc_in_id_parse -o "$TMP/idparse" 2>/dev/null || bad "idc-in-id parser compiles"
cat > "$TMP/p_fn.id" <<'EOF'
add(int x, int y) {
  int sum = x + y;
} return int sum;
EOF
expect_output "parser: function/params/decl" \
    "(func add (params (param int x) (param int y)) int (body (decl int sum (+ x y))) (return sum))" \
    "$("$TMP/idlex" < "$TMP/p_fn.id" | "$TMP/idparse" ast)"
cat > "$TMP/p_ctrl.id" <<'EOF'
countdown(int n) {
  while (n > 0) {
    print(n);
    n = n - 1;
  }
} return void;
EOF
expect_output "parser: while/call/void" \
    "(func countdown (params (param int n)) void (body (while (> n 0) (body (expr (call print n)) (assign n (- n 1))))) (return void))" \
    "$("$TMP/idlex" < "$TMP/p_ctrl.id" | "$TMP/idparse" ast)"
cat > "$TMP/p_if.id" <<'EOF'
chk(int x) {
  int r = 0;
  if (x = 0) {
    r = 1;
  }
} return int r;
EOF
expect_output "parser: if/else + bare-= equality" \
    "(func chk (params (param int x)) int (body (decl int r 0) (if (= x 0) (then (assign r 1)) (else))) (return r))" \
    "$("$TMP/idlex" < "$TMP/p_if.id" | "$TMP/idparse" ast)"

# --- stage 3 end to end: id source -> (id lexer) -> (id parser+codegen) -> C,
#     then compiled by cc and run. The whole front+middle is written in id.
cat > "$TMP/g_sq.id" <<'EOF'
square(int n) {
  int r = n * n;
} return int r;

main() {
  int a = square(6);
} return int a;
EOF
"$TMP/idlex" < "$TMP/g_sq.id" | "$TMP/idparse" > "$TMP/g_sq.c"
cc -std=c11 "$TMP/g_sq.c" -o "$TMP/g_sq" 2>/dev/null || bad "emitted C (square) compiles"
"$TMP/g_sq"; expect_output "codegen: square(6) exit code" "36" "$?"
cat > "$TMP/g_sum.id" <<'EOF'
sumto(int n) {
  int s = 0;
  while (n > 0) {
    s = s + n;
    n = n - 1;
  }
} return int s;

main() {
  int t = sumto(5);
} return int t;
EOF
"$TMP/idlex" < "$TMP/g_sum.id" | "$TMP/idparse" > "$TMP/g_sum.c"
cc -std=c11 "$TMP/g_sum.c" -o "$TMP/g_sum" 2>/dev/null || bad "emitted C (sumto) compiles"
"$TMP/g_sum"; expect_output "codegen: sumto(5) exit code" "15" "$?"

# parity: for the supported (scalar) subset, the id-written compiler emits
# byte-identical C to idc.py itself
"$IDC" "$TMP/g_sum.id" --emit-c "$TMP/parity_py.c" >/dev/null 2>&1
"$TMP/idlex" < "$TMP/g_sum.id" | "$TMP/idparse" > "$TMP/parity_id.c"
if diff "$TMP/parity_py.c" "$TMP/parity_id.c" >/dev/null; then
    ok "codegen parity with idc.py (scalar)"
else
    bad "codegen parity with idc.py (scalar)"
fi
# parity with the type pass: print(int) wraps id_str_of_int, string `+` becomes
# id_concat -- exactly as idc.py
cat > "$TMP/g_str.id" <<'EOF'
show(int n) {
  print("n = " + n);
} return void;

main() {
  show(7);
} return int 0;
EOF
"$IDC" "$TMP/g_str.id" --emit-c "$TMP/pstr_py.c" >/dev/null 2>&1
"$TMP/idlex" < "$TMP/g_str.id" | "$TMP/idparse" > "$TMP/pstr_id.c"
if diff "$TMP/pstr_py.c" "$TMP/pstr_id.c" >/dev/null; then
    ok "codegen parity with idc.py (print + string concat)"
else
    bad "codegen parity with idc.py (print + string concat)"
fi
# parity on a real multi-file demo: export/import, string[] params, concat,
# nested if/else, cross-file calls
"$IDC" ../demos/calc/app.id ../demos/calc/math.id --emit-c "$TMP/calc_py.c" >/dev/null 2>&1
cat ../demos/calc/app.id ../demos/calc/math.id | "$TMP/idlex" | "$TMP/idparse" > "$TMP/calc_id.c"
if diff "$TMP/calc_py.c" "$TMP/calc_id.c" >/dev/null; then
    ok "codegen parity with idc.py (demos/calc)"
else
    bad "codegen parity with idc.py (demos/calc)"
fi

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
