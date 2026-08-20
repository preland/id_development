# Making the self-hosted compiler backend-agnostic

`idc.py` emits C, LLVM IR and WAT from three near-duplicate code generators —
`gen_expr`, `gen_binop`, `gen_call` and `gen_stmt` each exist three times. That
is why adding one operator to the language meant five edits, and why the LLVM
and WASM targets were left behind when `word` and the flat store arrived.

The self-hosted compiler should not repeat that. This document is the shape it
should grow into, and the order to get there.

## Why this is urgent: it is the plan for deleting `idc.py`

`idc.py` is being retired as fast as the work can be done. It is stage 0 of a
bootstrap and nothing more, and every line it keeps is a line the language does
not own. What still holds it here, measured:

| what | lines of `idc.py` (of 5285) | what removes it |
|---|---|---|
| LLVM target | ~851 | steps 1–5 below |
| WASM target | ~1428 | steps 1–5 below |
| everything else (lex/parse/check/C emit) | ~3000 | already duplicated in `id`; needed only to bootstrap `idlex`/`idparse` on a cold cache |

**43% of `idc.py` exists only to serve two targets `bin/idc` does not have.**
That is the whole of the retirement problem: this document is how it gets
solved.

The last ~3000 lines go a different way. They are not ported — they are already
written in `id`, and `tools/parity.sh` proves it byte for byte. What keeps them
alive is that a fresh checkout has no `idlex`/`idparse` and must build them from
something. **A checked-in bootstrap C artifact retires that job**: commit the
generated C for both stages, build it with `cc`, and stage 0 becomes a
compiler, not a Python program. Regenerating it is then a normal commit, and
parity is what says the commit is honest.

Done means: `bin/idc` covers every target, the bootstrap C is checked in, and
`git rm idc.py` breaks nothing. Anything that grows `idc.py` moves away from
that and needs a reason.

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

## Where this stands

Done:

* **All thirteen of `idc.py`'s rules are enforced by the self-hosted
  compiler**, in `mid/`, reading only the AST and the symbol tables — no check
  looks at emitted text, so none of them will need rewriting for a second
  target.
* **The registry exists** (`mid/types/registry/`): `tyname` / `tykind` / `tywidth`
  / `tysigned`, one row per scalar type, list types derived. It is the sole
  source of type facts for every check, and now for the widening rule too,
  which previously lived in two halves in two subtrees.
* **`idc.py` no longer compiles anything** — `bin/idc` has no fallback, and
  `idc.py`'s only remaining job is bootstrapping `idlex`/`idparse` on a cold
  cache.
* **`front/` and `mid/` no longer emit C.** Six `emit_*` functions that print
  the export and extern blocks lived in `mid/` and were called from `back/`;
  they are now `back/emit/prog/head/decl/`. What stayed in `mid/` is
  `note_extern` — whether a name resolves is a property of the program, and
  only the C those names turn into is codegen. `front/` was already clean.
* **Emission has one boundary.** Every line of generated code goes through
  `emit_line` (`back/out/sink/`) instead of 33 scattered `print`
  calls. Diagnostics deliberately still use `print`: they are `mid/`'s, they
  go out whether or not anything is emitted, and a buffered emitter would
  reorder them behind the code they complain about. The boundary is a
  pass-through today and exists because the next target cannot be one — a
  WASM module needs its type and function sections written before the bodies
  that determine them.
* **The language has a written specification and a cross-target gate**
  ([`docs/SPEC.md`](SPEC.md), `tests/conform.sh`). This is the prerequisite
  the plan below did not have: `tools/parity.sh` compares emitted *text*,
  which is only a question while both compilers emit C, so it cannot say
  anything about a second target. The first conformance run found nine
  divergences between the three existing targets, three of them wrong
  answers rather than missing features.

Two deviations from the sketch below, both earned by contact with the code:

* `tykind` separates `int` from `float` rather than lumping them as `num`. A
  single `num` bucket cannot answer *is_integral*, which is what
  `& | ^ << >> && || ! ~` need, and `is_numeric` is then just "int or float".
* **Widening cannot be a width comparison.** `word` and `float` are both 8
  wide. It needs kind *and* width — rank is width doubled plus one for float.

Still to do, in order:

1. **A per-target spelling column.** `c_type` → `c_scalar` → `cs2` → `cs3` →
   `cs4` is now a chain that names each type explicitly rather than falling
   through to a default, so it is no longer a correctness hazard — but adding
   a type still means editing it. It should become a `tyc` column that the C
   target owns, which is also the first thing a second target would need.
2. **`box` / `unbox` / `to_str`** onto that column. `to_str` is in `mid/`
   today but spells C helper names, so it belongs in `back/tgt/c/`.
3. Then the directory move and the dispatch layer described below.

`tywidth` and `tysigned` have exactly one consumer today (the widening rule)
and are otherwise honest dead weight until step 1 lands.

## Order of work

1. **Semantic checks into `mid/`.** Done. They are backend-agnostic by
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

## Native backends are already target-agnostic

Two different things are called a backend in this repo: a **compiler target**
(the code generator this document is about) and a **native backend** (a
directory under `backends/` that supplies functions at link time — `gfx`, `gl`,
`fs`). A second compiler target must not drag the second kind along with it.

It does not have to. A native backend's `backend.json` declares itself twice:

```json
{ "abi":     [ { "name": "fs_open", "params": ["string","string"], "returns": "int" } ],
  "targets": { "c": { "header": "fs.h", "platforms": { "linux": { "sources": ["fs_posix.c"] } } } } }
```

`abi` is in `id`'s types and is what the backend *promises* — the same however
the program is compiled, and the only machine-readable form of the contract (a
Python or LLVM target cannot parse `fs.h` to learn it). `targets` is what a
given code generator needs in order to *deliver* it: sources and link flags for
C, a module to import for the Python target of step 4, whatever LLVM wants.

So step 4 adds a `"py"` key to three manifests and a reader for it. It does not
touch `demos/fsdemo`, `demos/gfxdemo`, or any other `.id` file — which is the
test of whether the seam is in the right place. `gfx` and `gl` predate the
`targets` layer and carry a bare `platforms` table, read as the C target's;
they gain the layer when a second target needs them to.

## The rule that keeps this honest

Every step keeps `tools/parity.sh` at MATCH for the C target. Byte-identical
output against a known-good compiler is the only cheap evidence available that
a refactor changed nothing, and it stops being available the moment the C
emitter is restructured without it.
