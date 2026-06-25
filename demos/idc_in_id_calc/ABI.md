# Calculator AST — ABI for the evaluator and printer

The parser (already built) turns a token stream into an AST stored in parallel
lists. The **evaluator** and **printer** are independent consumers of that AST:
each takes a node id and walks the tree using only the accessor functions below.
Neither touches the lists directly, and they do not call each other.

## Node model

A node is identified by an integer id. Its fields are read with these accessors
(already implemented, in `ast2.id` / `ast3.id`):

| accessor | returns | meaning |
|----------|---------|---------|
| `node_kind(int id)` | `int` | the node kind code (below) |
| `node_a(int id)`    | `int` | first int field |
| `node_b(int id)`    | `int` | second int field |
| `node_s(int id)`    | `string` | string field |

Kinds:

| kind | name | fields used |
|------|------|-------------|
| 1 | INT literal | `node_a` = the integer value |
| 2 | BINOP | `node_s` = operator, `node_a` = left child id, `node_b` = right child id |
| 3 | UNOP  | `node_s` = operator, `node_a` = operand child id |

Operators that appear: BINOP `node_s` is one of `+ - * / %`; UNOP `node_s` is
`-` (negation). Children of BINOP/UNOP are themselves node ids — recurse.

## What to implement

- **Evaluator** (`eval_expr(int id)` → `int`): the integer value of the subtree.
  INT → its value; UNOP `-` → negate the operand; BINOP → apply the operator to
  the evaluated children. Integer arithmetic (`/` is integer division, `%`
  remainder).
- **Printer** (`print_ast(int id)` → `string`): an S-expression. INT → its
  digits (e.g. `"" + node_a(id)`); UNOP → `(- X)`; BINOP → `(op L R)` with a
  space between parts, where L and R are the printed children. Example:
  `2 + 3 * 4` prints as `(+ 2 (* 3 4))`.

## id language rules you MUST follow (or it won't compile)

- **Every block** (function body, and each `if`/`else`/`while` body) does **at
  most 3 actions**. Each statement is one action; an `if` is one and each `else`
  another; a `while` is one. The `return` clause (after the closing brace) is
  free and may call a function. Recursion is fine.
- **Blocks nest at most 2 deep.** Deep dispatch → split into more functions.
- **At most 3 functions per file.** Add files as needed.
- **A name keeps one type** program-wide and may recur across functions (so `id`
  as an `int` everywhere is fine). One variable per name within a function.
- Function shape: `name(type p, ...) { body } return TYPE expr;` (or
  `return void;`). A bare `=` inside an expression means `==`.
- Build long results with `+` string concatenation; an int operand mixed with a
  string is converted (`"= " + 7`).

Dispatch on kind with a chain of helper functions (one decision each), e.g.
`eval_expr` checks `node_kind(id) == 1` then delegates — mirror the parser's
`parse_*` / `fold_*` split. Compile and test with:

```
./idc.py demos/idc_in_id -o /tmp/idlex
./idc.py demos/idc_in_id_calc -o /tmp/idcalc
echo "2 + 3 * 4" | /tmp/idlex | /tmp/idcalc
```
