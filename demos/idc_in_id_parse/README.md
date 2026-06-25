# idc-in-id, stage 2b: a function & statement parser written in id

Parses `id` source into an AST and prints the program's structure as a nested
S-expression. Like the calculator, it is fed by the stage-1 lexer through a pipe
and builds its AST entirely in parallel lists (no structs).

```sh
./idc.py demos/idc_in_id      -o idlex
./idc.py demos/idc_in_id_parse -o idparse
printf 'add(int x, int y) {\n  int sum = x + y;\n} return int sum;\n' | ./idlex | ./idparse
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

## Out of scope (next productions)

These id features are not parsed here and are the natural next additions:
array indexing (`a[i]`) and index-assignment, array literals (`[a, b]`),
`import` expressions, unary minus, and float literals (the stage-1 lexer emits a
float `0.8` as `0 . 8`, so float support needs lexer work first). Stage 3 — C
emission from this AST — is the remaining step toward a self-hosting `idc`.
