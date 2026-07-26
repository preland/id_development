# Making the self-hosted compiler backend-agnostic

`idc.py` emits C, LLVM IR and WAT from three near-duplicate code generators —
`gen_expr`, `gen_binop`, `gen_call` and `gen_stmt` each exist three times. That
is why adding one operator to the language meant five edits, and why the LLVM
and WASM targets were left behind when `word` and the flat store arrived.

The self-hosted compiler should not repeat that. This document is the shape it
should grow into, and the order to get there.

## The split

```
front/   lex, parse                     → AST
mid/     semantic checks, types         → annotated AST + tables
back/
  core/  the AST walk                   → calls the target interface
  tgt/
    c/     C target
    py/    Python target      (future)
    ll/    LLVM IR target     (future)
```

`front/` and `mid/` must not contain the word "C" anywhere. They already
almost don't: the type pass is about `id`'s types, and the semantic checks are
about `id`'s rules. Both are language properties, not codegen concerns.

`back/core/` walks the AST once and asks the *target* how to spell each thing.
Only `back/tgt/*/` knows about C, or Python, or IR.

## How a target is selected

`id` has no function pointers, so a target cannot be a table of closures. The
idiomatic answer is the same one the rest of the compiler already uses: a
dispatch chain on a target name, resolved at runtime.

```
tgt_type(string t) {
  string s = c_type(t);
  if(target() == "py") {
    s = py_type(t);
  }
} return string s;
```

One binary, target chosen by a flag. Adding a target means adding one
directory and one link in each dispatch chain — never touching `front/` or
`mid/`.

The alternative — one binary per target, selected by which directory is
compiled in — is simpler still, but it makes cross-target differential testing
(the thing that has caught almost every bug in this compiler) awkward. Prefer
runtime dispatch.

## The target interface

The complete set of questions `back/core/` needs to ask. A target is exactly
this list of functions; nothing else in the compiler should know about a
target at all.

| function | question |
| --- | --- |
| `tgt_prelude()` | the runtime preamble emitted once |
| `tgt_type(t)` | how is `id` type `t` spelled |
| `tgt_box(code, t)` / `tgt_unbox(code, t)` | how does a value enter/leave a uniform list cell |
| `tgt_binop(op, t, l, r)` | how is a binary operation spelled |
| `tgt_unop(op, t, v)` | ditto unary |
| `tgt_call(name, args)` | how is a call spelled |
| `tgt_builtin(name, args, t)` | how is a builtin spelled |
| `tgt_func_open(name, ...)` / `tgt_func_close(...)` | function framing |
| `tgt_stmt_*` | assignment, branch, loop framing |
| `tgt_entry()` | the program entry point |
| `tgt_asm(lines, t)` | inline assembly (see `ASM.md`) |

## Types as data, not as if-chains

Today the answer to "how wide is an `int`" is spread across 26 files as
`if(t == "int")` chains — `c_type`, `box`, `unbox`, `to_str`, the type pass,
the literal typer. Adding a type means finding all of them.

Instead, one registry, populated at startup, in the same parallel-list style
the AST uses:

```
tyname[i]    "int"    "float"  "string"  "void"  "word"
tykind[i]    "num"    "num"    "ref"     "unit"  "num"
tywidth[i]   4        8        8         0       8
tysigned[i]  1        0        0         0       1
```

and one column per target for its spelling. Then `c_type(t)` is a lookup, the
widening rule is a comparison of `tywidth`, and adding a type is a row.

This is what "make types a standard library" means in practice: the registry
is `id` source, in `mid/`, that any program could in principle extend — not
knowledge compiled into the emitter. It also removes the silent-default bug
this codebase already had twice (`cs3` and `unbox3` both fell through to a
wrong answer for an unknown type rather than reporting one).

## Order of work

1. **Semantic checks into `mid/`.** In progress. They are backend-agnostic by
   construction and must stay that way — no check may look at emitted text.
2. **The type registry.** Replace the if-chains with lookups, one target
   column at a time. Purely mechanical, and each step is verifiable by
   `tools/parity.sh` staying at MATCH.
3. **Rename `back/` to `back/tgt/c/` and add the dispatch layer**, with C as
   the only target. No behaviour change; parity proves it.
4. **A second target.** Python first, not LLVM: it is the one that most
   exercises the interface (no static types, no manual boxing, a real runtime
   of its own), so it will expose everything C-shaped still leaking through.
   It also gives an interpreted mode, which is useful on its own.
5. **LLVM IR**, once the interface has survived a second target.

## The rule that keeps this honest

Every step keeps `tools/parity.sh` at MATCH for the C target. Byte-identical
output against a known-good compiler is the only cheap evidence available that
a refactor changed nothing, and it stops being available the moment the C
emitter is restructured without it.
