# idc-in-id, stage 2: an expression parser written in id

A recursive-descent arithmetic parser, evaluator, and S-expression printer —
all written in the `id` language — fed by the stage-1 lexer through a pipe.

```sh
./idc.py demos/idc_in_id    -o idlex
./idc.py demos/idc_in_id_calc -o idcalc
echo "2 * (3 + 4) - 10 % 3" | ./idlex | ./idcalc
# (- (* 2 (+ 3 4)) (% 10 3))
# = 13
```

The lexer turns the input into a `<kind> <value>` token stream; `idcalc` loads
that into a token store, parses it into an AST, then prints and evaluates it.

## How it works (the ABI)

This is the payoff of the growable-list feature. There are no structs: the AST
is **parallel lists** indexed by an integer node id.

- **Shared state is exported lists**, reached with `import`. The token store
  (`tkind`, `ttext`) and AST store (`nkind`, `na`, `nb`, `ns`) are mutated
  through their imported references, so parse routines take no state parameters.
- **The cursor is a one-element `int[]` cell** passed by reference, so
  `advance` can do `pos[0] = pos[0] + 1` and callers see it move.
- **A node is `(nkind, na, nb, ns)`**; `newnode` appends one cell to each list
  and returns the new id. Kinds: 1 = INT, 2 = BINOP, 3 = UNOP. See `ABI.md`.
- **The parser is precedence climbing** (`expr → add → mul → unary → primary`).
  Because a loop body may only do 3 actions, each left-associative fold step is
  its own function (`fold_add`, `fold_mul`).

The evaluator (`eval_expr`) and printer (`print_ast`) are independent consumers
of the AST accessors — they were built in parallel against `ABI.md`.

## Scope

Integer arithmetic only: `+ - * / %`, unary `-`, and parentheses. No variables,
comparisons, or error recovery yet — those are natural next productions to add
on the same ABI. This stage exists to prove the parser pipeline (token store →
cursor threading → AST in parallel lists → tree walks) works in `id`.
