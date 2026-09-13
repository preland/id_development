# Making the self-hosted compiler backend-agnostic

> **Status: a plan, partly executed.** The split below is the target shape,
> not the current one. "Where this stands" says which steps have landed; the
> retirement section is the reason the rest is urgent.

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

**43% of `idc.py` exists only to serve two targets `idc/bin/idc` does not have.**
That is the whole of the retirement problem: this document is how it gets
solved.

The last ~3000 lines went a different way. They were not ported — they are
already written in `id`, and `idc/tools/parity.sh` proves it byte for byte. What
kept them alive is that a fresh checkout has no `idlex`/`idparse` and must
build them from something. **A checked-in bootstrap C artifact retires that
job**, and it is checked in: `idc/bootstrap/idlex.c` and `idc/bootstrap/idparse.c`,
built with `cc`, so stage 0 is a compiler and not a Python program.
Regenerating it is a normal commit (`idc/tools/regen_bootstrap.sh`), and
`idc/tests/self_host_build.sh` is what says the commit is honest — it re-emits both
files and fails if they are not what the tree emits.

Done means: `idc/bin/idc` covers every target, the bootstrap C is checked in, and
`git rm idc/idc.py` breaks nothing. The middle clause is done. Anything that grows
`idc.py` moves away from the rest and needs a reason.

**That last sentence is a gate, not a hope.** `idc/tests/run.sh` holds a line
ceiling for `idc.py` and fails if it is exceeded. The ceiling only ever
ratchets down: port something out, lower it in the same commit. It exists
because "language features are not built here" was a sentence in the README
for a while before the gate was, and `idc.py` gained 1711 lines during that
time. Prose does not hold a line; a failing test does.

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
* **`idc.py` no longer compiles anything, and no longer bootstraps** —
  `idc/bin/idc` has no fallback and does not execute it. Stage 0 is
  `idc/bootstrap/*.c`; what `idc.py` still has is `--target wasm`, running a test
  case, and being the other side of the differential suites.
* **`front/` and `mid/` no longer emit C.** Six `emit_*` functions that print
  the export and extern blocks lived in `mid/` and were called from `back/`;
  they are now `back/tgt/c/emit/prog/head/decl/`. The extern block has since
  gone altogether: a backend's functions are `native` declarations in its own
  source, so an unresolved call is always an error. `front/` was already clean.
* **Emission has one boundary.** Every line of generated code goes through
  `emit_line` (`back/drive/sink/`) instead of 33 scattered `print`
  calls. Diagnostics deliberately still use `print`: they are `mid/`'s, they
  go out whether or not anything is emitted, and a buffered emitter would
  reorder them behind the code they complain about. The boundary is a
  pass-through today and exists because the next target cannot be one — a
  WASM module needs its type and function sections written before the bodies
  that determine them.
* **The language has a written specification and a cross-target gate**
  ([`docs/SPEC.md`](SPEC.md), `idc/tests/conform.sh`). This is the prerequisite
  the plan below did not have: `idc/tools/parity.sh` compares emitted *text*,
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
   `idc/tools/parity.sh` staying at MATCH.
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
directory under `idc/backends/` that supplies functions at link time — `gfx`, `gl`,
`fs`). A second compiler target must not drag the second kind along with it.

It does not have to. A native backend declares itself twice, both times in
`id` — once as what it provides, and once in its `backend.id` as how to link it:

```
native fs_open(string path, string mode) return int;
```

```
string name = "fs";
string c_header = "fs.h";
string[] c_linux_sources = ["fs_posix.c"];
string[] c_linux_cflags = [];
string[] c_linux_link = [];
```

The `native` declarations are what the backend *promises*, in `id`'s own types.
They are ordinary source: the backend's directory is merged into the build like
any dependency, so every call into it is resolved and checked like any call —
there is no unresolved-call mode and no `extern int` guess — and the same
however the program is compiled. They are also the only machine-readable form
of the contract (a Python or LLVM target cannot parse `fs.h` to learn it); the
C target emits each as a prototype and the LLVM target as a typed `declare`.
`backend.id` is what a
given code generator needs in order to *deliver* it: sources and link flags for
C, a module to import for the Python target of step 4, whatever LLVM wants.

### `backend.id`

Every line is a constant declaration with a literal value, in one of three
shapes, and the target of a name is the text before its first underscore:

| declaration | means |
|---|---|
| `string name = "gfx";` | the backend's name, used in diagnostics (`backend` if absent) |
| `string TARGET_FIELD = "...";` | one fact about a target as a whole, e.g. `c_header` |
| `string[] TARGET_PLATFORM_sources = [...];` | the sources to compile for that target on that platform key; declaring it is what declares the platform |
| `string[] TARGET_PLATFORM_cflags = [...];` | flags for compiling those sources (empty if absent) |
| `string[] TARGET_PLATFORM_link = [...];` | flags for the final link (empty if absent) |

Platform keys are the ones the triple maps to (`linux`, `darwin`, `none`, or
the triple's last field). The C target is `c`. **The LLVM target is not
served yet** (it declares natives and links no backend); it would read the same
shape under `llvm_`: `llvm_linux_sources` compiled with `clang -target TRIPLE`
and `llvm_linux_cflags`, and `llvm_linux_link` handed to the `clang` that links
the module.

**It is never compiled.** A `conf.id` constant is an exported global: its name
is reserved program-wide and it is emitted in every build. Declared that way, a
backend's facts would cost every program that attaches it — including, once a
standard library names every backend, hello-world — and two backends could not
both say `c_linux_sources`. So `backend.id` is skipped by source collection and
by the 3-entries rule exactly as `conf.id` is, and `idc/bin/idc`
(`backend_decls`) reads it, one backend at a time, only when a native of that
backend is reached. The names need no backend prefix, because no two backends'
files are ever read into one namespace.

It is read by the shell rather than emitted by `idparse` because `idparse`
only sees what is in the source stream, and putting it there would make the
facts constants again. The grammar is small enough to check completely: a
`string` or a `string[]` of string literals without escapes. Any other line —
another type, a list where a string belongs, a `_cflags` with no `_sources`, a
name declared twice — stops the build at its line:

```
idc: backends/toy/backend.id:3: invalid backend declarations: 'c_linux_sources' is a string[], not a string
```

`tests/backends.sh` parses and type-checks each backend's `backend.id` as a
project's `conf.id` with the compiler itself (`--fingerprints`, which stops
before C), so the shell reader cannot drift into accepting something that is
not `id`. It stops before C because a list constant in a `conf.id` does not
yet emit C that `cc` accepts — an emitter gap, separate from this file.

So step 4 adds `py_...` declarations to three backends and a reader for them.
It does not touch `demos/fsdemo`, `demos/gfxdemo`, or any other compiled `.id`
file — which is the test of whether the seam is in the right place.

### A backend is linked only when a native of it is reached

Attaching a backend — a `conf.id` import, `--backend`, or the standard
library's own `conf.id` — merges its declarations and nothing else. What is
compiled and linked is decided by reachability, the same computation that
decides what is emitted:

* `idparse --natives` appends a list to its output, after the program and
  behind `/* ---- natives ---- */`, one row per native per kind:
  `KIND|NAME|CALLFILE:LINE|DECLFILE`. `program` rows are the natives called by
  a function the program keeps (every function, with no `main` or
  `--freestanding`); `harness` rows are the natives the test cases reach. The
  program part of the stream is byte for byte what it is without the flag
  (`compiler/parse/back/drive/sink/natives/`). A call's line is recorded as it
  is parsed (`cnode`/`cline`), because only statements carry one in `nline`.
* `idc/bin/idc` (`backends_for`) maps each row's declaring file to the attached
  backend whose directory holds it, and compiles and links only those backends
  — for the harness from the `harness` rows, for the program from the
  `program` rows. An attached backend nothing reaches costs no compile, no
  object and no link flag.
* **What provides a native is where it is declared**, not a list of names in
  `backend.id` (a second copy of the declarations, typed in nothing, read by
  nothing) and not the object's symbols (which exist only after the compile
  this avoids). A name is declared once per build, and the declaration is the
  one every call was checked against.
* A reached native that nothing attached can link is reported at the call that
  reaches it, never by the linker:

```
main.id:2: error: native 'gl_width', reached from main by this call, is implemented
  by backend 'gl', which has no support for platform 'darwin' (building for
  'aarch64-apple-darwin'); it is implemented for: linux
twin.id:5: error: native 'twin_a', reached from main by this call, has no
  implementation for platform 'linux' (building for 'x86_64-unknown-linux-gnu'):
  it is declared in twin.id, which is not in an attached backend
```

What still treats a backend differently from other source: the emitters give
a native a prototype and no body; its parameters register no names; its
fingerprint includes its name; it needs no test cases; its `backend.id` is
read by `bin/idc` rather than compiled, and its C is compiled into `*.gen.o`
beside the source; the LLVM target declares natives but links no backend; a
project with no `main` links none; and `idc/idc.py`, which reads the
`backend.json` that `backend.id` replaced, links no backend at all.

## The rule that keeps this honest

Every step keeps `idc/tools/parity.sh` at MATCH for the C target. Byte-identical
output against a known-good compiler is the only cheap evidence available that
a refactor changed nothing, and it stops being available the moment the C
emitter is restructured without it.
