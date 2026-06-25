# idc-in-id, stages 2b + 3: an id parser and C emitter, written in id

Parses `id` source into an AST and **emits C** from it — the front and middle of
`idc`, written in `id` itself. Fed by the stage-1 lexer through a pipe; the AST
is built entirely in parallel lists (no structs). Pass `ast` to dump the parsed
structure instead of emitting C.

```sh
./idc.py demos/idc_in_id      -o idlex
./idc.py demos/idc_in_id_parse -o idparse

# emit C, then compile and run it -- the whole front+middle is written in id:
printf 'square(int n) { int r = n * n; } return int r;\nmain() { int a = square(6); } return int a;\n' \
  | ./idlex | ./idparse > out.c
cc out.c -o out && ./out; echo $?      # 36

# or inspect the AST:
printf 'add(int x, int y) {\n  int sum = x + y;\n} return int sum;\n' | ./idlex | ./idparse ast
# (func add (params (param int x) (param int y)) int (body (decl int sum (+ x y))) (return sum))
```

## What it handles

- **Functions:** `name(params) { body } return TYPE expr;` (and `return void;`),
  with typed parameters and `T[]` types.
- **Statements:** declarations (`[export] type name = expr;`), assignments
  (`name = expr;`), `if`/`else`, `while`, and expression statements (calls).
- **Expressions:** integer/string literals, variables, function calls with
  arguments, parentheses, and binary operators across three precedence levels —
  relational/equality (`== != < > <= >=`, and a bare `=` meaning equality),
  additive (`+ -`), multiplicative (`* / %`). Left-associative.

The `classify` and `countdown` shapes from the other demos parse exactly.

## How it is built (the ABI)

Same techniques as the calculator, scaled up:

- **Shared state in exported lists**, reached via `import`: the token store
  (`tkind`/`ttext`) and the AST store. Parse routines take no state parameters;
  only the cursor `pos` (a one-element `int[]` cell) is threaded by reference.
- **Nodes are seven parallel lists** — `nkind`, two int fields, two string
  fields, and **two child-list fields** (`nl1`/`nl2` are `int[][]`) so a node can
  hold variable-arity children: a function's params and body, an `if`'s two
  branches, a call's arguments.
- **Recursive descent** with the now-familiar split: every loop body that folds
  operators or collects list items is its own small function, to respect the
  3-action-per-block and 2-deep-nesting limits.

## C emission (stage 3, the `gen*.id` files)

The emitter walks the AST and prints C, mirroring `idc.py`: id functions become
`id_NAME`; locals are **hoisted** to the top of their C function (id is
function-scoped, so a var declared inside a branch and used after it must be
declared at function scope) and their initializers become assignments; forward
declarations precede definitions; a C `main()` wraps id's `main`. id's bare `=`
equality becomes C `==`. Verified end to end: emitted C is compiled by `cc` and
run (`square(6)` exits 36, `sumto(5)` exits 15).

## Parity with idc.py

The emitter is **differentially tested** against `idc.py`: for a supported
program, `idlex | idparse` produces byte-identical C to `idc.py --emit-c`. Run
`tools/parity.sh <file-or-dir>` to check any program. A type pass (built on id's
one-type-per-name rule, so a single global symbol table suffices) drives the
type-dependent emission to match idc.py exactly:

- `print(int)` → `id_print(id_str_of_int(x))`; string `+` → `id_concat(...)`
  with operands coerced; string `==`/`!=`/`=` → `(strcmp(a, b) OP 0)`
- `(import name)` reads the exported global; exported vars become C globals in an
  `/* exported variables */` block (not hoisted locals)
- list types (`T[]`) map to `IdList*`; `main(int, string[])` gets the argv-
  marshalling wrapper

Whole demos at parity today: **`demos/calc`** and **`demos/adventure`** (and the
export/import roundtrip) emit byte-identical C under both compilers; checked in
the test suite.

## Out of scope (next gaps)

Not yet parsed/emitted: array indexing (`a[i]`) and index-assignment, array
literals, unary minus, the list builtins (`push`/`len` on lists), and float
literals (the lexer emits `0.8` as `0 . 8`, so floats need lexer work first).
These block `hello_world` and `demos/control`. The parser no longer hangs on
them — it terminates with (incorrect) output. Closing these, then feeding the
compiler its own source, is the path to full self-hosting.
