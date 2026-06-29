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
- `||`/`&&` (above equality), unary `-`/`!`, array indexing `a[i]` and
  index-assignment `a[i] = v`, array literals (`[]`, `[a, b]`), and the list
  builtins — `push` → `id_list_push` and `len` → `id_list_len`/`id_len` — all
  emit with the same boxing/unboxing casts idc.py uses for the uniform cells

Whole demos at parity today: **`demos/calc`** and **`demos/adventure`** (and the
export/import roundtrip) emit byte-identical C under both compilers; checked in
the test suite.

## Self-hosting

The compiler now **compiles itself**. `idlex | idparse` emits byte-identical C
to `idc.py` for its own source — both the stage-1 lexer (`demos/idc_in_id`) and
this parser/codegen (`demos/idc_in_id_parse`):

```sh
tools/parity.sh demos/idc_in_id        # MATCH
tools/parity.sh demos/idc_in_id_parse  # MATCH
```

And the result is a **fixpoint**: compile the compiler with `idc.py`, then use
that binary to recompile the compiler's source, and the C it produces is
identical to its own — so the self-compiled compiler reproduces itself exactly.
The test suite checks both the parity and the fixpoint.

The lexer change that unblocked this was backslash-escape handling in string
literals (so a `\"` no longer ends a string early); the runtime prelude that
`idparse` prints is one such string. Float literals remain the one unimplemented
piece of the language (the lexer still splits `0.8` into `0 . 8`), but the
compiler's own source uses no floats, so self-hosting does not need them.
