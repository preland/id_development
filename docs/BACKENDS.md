# Making the self-hosted compiler backend-agnostic

> **Status: a plan, partly executed.** The split below is the target shape,
> not the current one. "Where this stands" says which steps have landed; the
> retirement section is the reason the rest is urgent.

`idc.py`, the original compiler (since deleted), emitted C, LLVM IR and WAT from three near-duplicate code generators —
`gen_expr`, `gen_binop`, `gen_call` and `gen_stmt` each exist three times. That
is why adding one operator to the language meant five edits, and why the LLVM
and WASM targets were left behind when `word` and the flat store arrived.

The self-hosted compiler should not repeat that. This document is the shape it
should grow into, and the order to get there.

## idc.py is deleted

`idc.py` was frozen, then removed. `idc/bin/idc` bootstraps from the checked-in
C in `idc/bootstrap/`, and the frozen-hash case that guarded the file is gone
from `idc/tests/run.sh`. `--target wasm` is implemented by `idc/bin/idc`
itself: it recompiles the C target's C for wasm32-wasi and links a WASI
reactor (`idc/tests/wasm.sh`, `idc/tests/conform.sh`'s wasm lane). It is not
a WAT generator in `back/tgt/`, so the codegen-per-target split below still
has exactly one real target (C) plus the LLVM one.

## The split

```
front/   lex, parse                     → AST
mid/     semantic checks, types         → annotated AST + tables
back/
  core/  the AST walk                   → calls the target interface
  tgt/
    c/     C target
    int/   interpreter       (future, docs/INTERPRETER.md)
    ll/    LLVM IR target     (future)
```

`front/` and `mid/` must not contain the word "C" anywhere. They already
almost don't: the type pass is about `id`'s types, and the semantic checks are
about `id`'s rules. Both are language properties, not codegen concerns.

`back/core/` walks the AST once and asks the *target* how to spell each thing.
Only `back/tgt/*/` knows about C, or an interpreter, or IR.

## How a target is selected

`id` now has function values (`func(T) return R`, `docs/SPEC.md` §1.1), so a
target could be a table of them. The compiler was written before they existed
and uses a dispatch chain on a target name, resolved at runtime; the sketch
below shows that shape.

```
tgt_type(string t) {
  string s = c_type(t);
  if(target() == "ll") {
    s = ll_type(t);
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

When this was written the answer to "how wide is an `int`" was spread across many files as
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
* **`idc.py` is deleted, and nothing bootstraps from it** —
  `idc/bin/idc` has no fallback and does not execute it. Stage 0 is
  `idc/bootstrap/*.c`, and `--target wasm` is implemented by `idc/bin/idc`.
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
  the plan below did not have: comparing emitted *text* against `idc.py`,
  which the tree used to do, is only a question while both compilers emit C,
  so it cannot say anything about a second target. The first conformance run
  found nine
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
4. **A second target.** An interpreter written in `id`, not LLVM and not a
   Python target (the project writes no new Python): an interpreter exercises
   the interface the way a dynamic target would (no manual boxing, a runtime of
   its own), so it will expose everything C-shaped still leaking through, and
   it is the interpreted mode the project wants anyway. Which interpreter, and
   how it is built, is the open fork in `docs/INTERPRETER.md`.
5. **LLVM IR**, once the interface has survived a second target.

## Native backends are already target-agnostic

Two different things are called a backend in this repo: a **compiler target**
(the code generator this document is about) and a **native backend** (a
directory with a `backend.id` that supplies functions at link time — `idstd`'s
`host/io/fs`, `host/os/proc/be`, `host/io/net/sock`, `host/dev/win/gfx` and
`host/dev/win/gl`). A second compiler target must not drag the second kind along
with it.

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
of the contract (an interpreter or LLVM target cannot parse `fs.h` to learn it); the
C target emits each as a prototype and the LLVM target as a typed `declare`.
`backend.id` is what a
given code generator needs in order to *deliver* it: sources and link flags for
C, whatever an interpreter target of step 4 needs, whatever LLVM wants.

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
| `string[] TARGET_PLATFORM_pkg = [...];` | pkg-config packages (C target): their `--cflags` are added to `_cflags` and their `--libs` to `_link`, at build time, and the resolved flags are in the cache keys. A package or `pkg-config` that is missing stops the build, naming the package and the fix |

Platform keys are the ones the triple maps to (`linux`, `darwin`, `none`, or
the triple's last field). The C target is `c`. **The LLVM target is not
served yet** (it declares natives and links no backend); it would read the same
shape under `llvm_`: `llvm_linux_sources` compiled with `clang -target TRIPLE`
and `llvm_linux_cflags`, and `llvm_linux_link` handed to the `clang` that links
the module.

**The wasm target reads `wasm_`**, with the platform key `wasi`, and one field
that has no C counterpart: `string[] wasm_wasi_sources` (with `_cflags` and
`_link`) is compiled with the WASI clang and linked, for natives that are plain
libc over WASI (standard input and output); `string wasm_js = "FILE.mjs";`
names a JavaScript module that answers every other native of the backend, which
the wasm module imports as `env.id_NAME`. A backend that declares neither is
not served: a native of it that the module keeps is refused at the call that
reaches it. How the module is loaded and what the JS module receives are in
`docs/INTEROP.md`, "id and JavaScript".

**It is never compiled.** A `conf.id` constant is an exported global: its name
is reserved program-wide and it is emitted in every build. Declared that way, a
backend's facts would cost every program that attaches it — including, once a
standard library names every backend, hello-world — and two backends could not
both say `c_linux_sources`. So `backend.id` is skipped by source collection and
by the layout checks exactly as `conf.id` is, and `idc/bin/idc`
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
not `id`. It stops before C because `--fingerprints` never reaches emission for
any conf.id, list-typed fields included -- not because a list constant cannot
reach C, which it now can (`docs/PROJECT.md` §5).

So step 4 adds `py_...` declarations to three backends and a reader for them.
It does not touch `demos/fsdemo`, `demos/gfxdemo`, or any other compiled `.id`
file — which is the test of whether the seam is in the right place.

### A backend is linked only when a native of it is reached

Attaching a backend — being in the build, however its directory got there —
merges its declarations and nothing else. What is compiled and linked is
decided by reachability, the same computation that decides what is emitted:

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

### What a backend's own `id` code may call: `core/`, itself and natives

A backend's `id` code may call builtins, `core/`, its own directory, and the
natives of any backend (a native is a leaf C call, so the layering of the `id`
code above it still holds). It may not call another backend's `id` functions, nor
anything in `host/` or `kit/`.

A backend directory may hold `id` code beside its natives (`fs_mkdir_p` over
`fs_mkdir`, `fs_read_bytes` over `fs_read`), and that code has cases. When a
program names a backend on its own (`--backend DIR`, or a `conf.id` import),
`idc/bin/idc` builds and tests the backend as a library of its own
(`run_backend_prechecks`), cached by content. That build includes idstd's
`core/` and no other tier, because `core/` is freestanding and always present,
the foundation everything stands on, so a backend leans on it instead of
duplicating it. The other backends of the checkout are present only as their
native declarations, with their `backend.id` and C beside them so a case that
calls one links: a copy of each is made in a scratch directory
(`tier_native_shims`), holding the `native` lines of its `id` files and none of
its `id` functions.

* The backend's functions and its cases may call any `core/` function
  (`list_fill`, `path_join`, `str_ends`, `order_strings`, and so on). Only the
  `core/` functions reached are parsed, as in any build.
* Any backend's natives may be called, in the backend's code and in its cases.
* Calling something in `host/` or `kit/`, or another backend's `id` function, is
  refused, because backends sit below those tiers. The diagnostic is `no such function` followed by a line
  naming where the function lives and the two ways out: move it into `core/`
  if it needs no host service, or move the calling code out of the backend into
  the `host/` or `kit/` library that wraps it. A backend's cases may not
  `given` a fixture from above `core/` either.
* The checkout is the nearest ancestor of the backend with `core/`, `host/` and
  a `conf.id`. A backend outside any idstd checkout keeps what it had: the whole
  standard library when the build has one, else nothing (`--no-std`).
* The pre-check's cache key includes the contents of `core/` and idstd's
  `conf.id` (the constants `core/` reads), so a change to a `core/` function a
  backend calls re-runs the backend's cases.
* A program that is `--no-std` and imports a backend directly merges the
  backend's `id` files as source, so it must import idstd's `core/` too
  (`import "…/idstd/core"` in its `conf.id`) when the backend calls it.

The rule is also checked statically, without a program naming the backend:
`idstd/run.sh layer` reads the call graph `idc idstd --calls` makes of the whole
library and, for every directory holding a `backend.id` under `host/` or `kit/`,
requires each callee of a function defined there to be a builtin, a function
under that same directory (the backend's own natives included), a function
under `core/`, or a native declared anywhere (the callee's line starts with
`native `). Anything else is reported as
`file:line: fn calls X, which lives in host/... -- move X into core/, or move fn
out of the backend` (`file:line` is where `fn` is defined). The tool is
`idstd/.tests/tool/layer`; `idstd/run.sh layerfalsify` runs it over a miniature
idstd (`.tests/assets/layer`) and requires a call from its backend into `host/`,
one into `kit/`, and one into another backend's `id` function to turn it red,
and a call to another backend's native to stay green.

A test fixture is exempt from the static check. A fixture is a function whose
name follows `given` or `then` in some case line of the library (run.sh reads
those names from the lines that start with `given ` or `(`; the call graph has no
edge for a case line), and whose every incoming call edge in the graph comes from
another such name, so no real code calls it. `idstd_wl_fixture_link`, which makes a
scratch directory with `fs_mktemp`, is one. A function that does the same call
but is also called from real code, or never named in a case, is still flagged
(`layerfalsify`). The pre-check above has no such exemption: it cannot scope a
function to the cases that name it, so a backend with a fixture that calls
another backend's `id` function is refused when a program names that backend on
its own, as it would be for any other such call (`wl`'s `idstd_wl_fixture_link` calls `fs_mktemp`, so naming `wl` alone is refused).

The pre-check runs the C target whatever `--target` the program asks for; the
backend's `id` code is the same for the C, LLVM and wasm targets, so the
answer is shared.

### Where the backends live, and how a platform chooses

**In the standard library, inside the modules that wrap them**: `host/io/fs`,
`host/os/proc/be`, `host/io/net/sock`, `host/dev/win/gfx`, `host/dev/win/gl`. A program calls a library function (or, until the
functions over them exist, the native) and never names a backend.

**Attachment is by `backend.id`, not by manifest.** `idc/bin/idc`'s
`collect_ids` records every directory holding a `backend.id` in any tree it
collects — the library, a `conf.id` import, the project, a `--backend`
directory. The alternative was a self-relative `import "host/io/fs"` in the
library's own `conf.id`. That is a second copy of the layout to keep in step
with the tree, and every imported root is a compilation unit of its own, so
each backend directory would have become a unit apart from the library that
wraps it. Discovery costs one `find` pattern, and a backend nothing reaches
still costs nothing: hello-world's cc commands are the three they were.

**A native has one declaration; the platform chooses its sources.** One
`idstd` function that needs a different implementation per platform calls one
native, and that native's `backend.id` lists sources per platform key —
`c_linux_sources`, `c_darwin_sources` — which may sit in per-platform
subdirectories. The driver picks by the triple. The other design, `native`
declarations selected by triple the way `asm` overloads are, was rejected:
`asm` matches a triple exactly with no wildcard, so every architecture of every
platform would repeat the declaration — the contract — for C that does not
change; it needs a new construct in the compiler and a bootstrap regeneration;
and it moves the unsupported-platform diagnostic into the compiler, in `asm`'s
words. Selecting sources gives the same determinism with none of that: the
source a reader sees names one function with one signature, and `backend.id`
says, per platform, what implements it.

**`--triple` moves the platform; `--backend` overrides one backend.** A
`--backend DIR` whose `backend.id` declares the `name` of an attached backend,
and which holds its sources but no declarations, replaces how that backend is
linked for that build — another windowing system on the same platform, or a
port in progress. Two for one backend is refused. A `--backend` directory that
declares natives of its own is attached like any tree.

**The platform question is asked first.** A reached native the platform cannot
link stops the build at its call before the refusal to run another triple's
test cases on this machine, because the library always has cases and that
refusal would otherwise be all a cross build ever says. The check reads
`backend.id` files and compiles nothing. `--emit-c` and the LLVM target do not
ask it; neither links a backend.

What still treats a backend differently from other source: the emitters give
a native a prototype and no body; its parameters register no names; its
fingerprint includes its name; it needs no test cases; its `backend.id` is
read by `bin/idc` rather than compiled, and its C is compiled into `*.gen.o`
beside the source; the LLVM target declares natives but links no backend; a
project with no `main` links none.

## Optimisation levels (`-O`)

id's functions are small -- the three-action limit makes every program a deep
chain of calls -- so what a build does about calls decides most of a program's
speed and size. `-O LEVEL` (or `-O0` ... `-O3`, `-Os`) chooses, on every target:

| level | C target | `--target llvm` | `--target wasm` | what it is for |
| --- | --- | --- | --- | --- |
| `0` | `-O0` per unit | IR passes off, `clang -O0` | `clang -O0` | quickest build; every id function is a call |
| `1` | `-O1` per unit | IR passes on, `clang -O1` | `clang -O1` | edit-and-run: no whole-program step, so an edit rebuilds one unit |
| `2` (default) | `-O2 -ftree-vectorize` plus `-flto` | IR passes on, `clang -O2 -flto` | `clang -O2 -flto`, `wasm-ld --lto-O2` | small functions inlined across the whole program |
| `3` | `-O3 -flto` and a larger inline budget | `clang -O3 -flto` | `-O3 -flto`, `--lto-O3` | fastest code, larger binary |
| `s` | `-Os -flto` | `clang -Os -flto` | `-Os -flto` | smallest binary; slower than `2` |

**Why LTO is how inlining is done.** The C target splits the program into units
so that an edit recompiles a few hundred lines (`unit_split` in `bin/idc`), and a
function defined in one unit is only a prototype in the others, so no `-O` level
can inline it into a caller in another unit; `bin/idc` does not mark program
functions `static` either, because a unit that is not the whole program cannot
know that nothing else calls them. With `-flto` the units are still compiled and
cached one by one (as slim bitcode), and gcc's link step sees the whole program
and tells the linker that only `main` is referenced from outside, which lets it
inline across units, drop the out-of-line copies and specialise what is left. The
price is that every relink compiles the whole program once more (`IDC_TIMES=1`
prints what the units and the link cost); that is why `-O1` exists. A program
with no `main` (a relocatable `.o`) and `--lib` are never linked with LTO, since
they export their functions, and `--target llvm` hands the module and the C
runtime to one `clang -flto`, which is what lets an id function inline the
runtime's accessors (`id_list_get`, ...); a toolchain that cannot link that way
is retried without it.

**A backend's natives inline too.** When a C-target program links with gcc LTO,
`backend_build` compiles each backend's C with `-std=gnu17 -flto
-ffat-lto-objects -fwrapv`, so a native such as `flt_sqrt` is inlined into its
caller rather than called. The language standard has to match the units' or gcc
will not inline across them, and the objects are fat because the test harness
links the same object at `-O0` without LTO. The flags are part of the object's
cache key. `--lib`, `--target llvm`, `--target wasm` and a clang `cc` keep the
plain `-O2` object.

**The runtime's accessors are `static inline` on every path.** `bin/idc` marks
the prelude's `static` functions `static inline` once, on the C every later path
(units, the whole-file fallback, `--emit-c`, `--lib`, `--target wasm`) starts from;
before that only the unit path did, so the same program ran at different speeds
depending on how it was built. A trap is still a call to code that prints its
message and exits, whatever is inlined around it; `tests/opt.sh` checks the
message and status at every level.

**The test harness is always `-O0`**, and so is the build of a case: what a
case checks is the program's meaning, which `-O` must not change, and a harness
compiled with LTO would cost far more than it saves.

`-O` also sets the IR pass level of `--target llvm` (0 off, anything else on;
`s` is 1). Today the IR pipeline has no inlining pass of its own -- see
`docs/LLVM.md`, whose table lists passes (`gvn`, `inline`, `licm`) that
`back/ir/opt/run/pipe/run.id` does not contain, so `-O2` and `-O1` are the same
IR.

## The rule that keeps this honest

Every step keeps `idc/tools/parity.sh` at MATCH for the C target. Byte-identical
output against a known-good compiler is the only cheap evidence available that
a refactor changed nothing, and it stops being available the moment the C
emitter is restructured without it.

## The Wayland client (`idstd/host/dev/win/wl`)

`gfx_open` and the rest of the `gfx_*` window calls choose their window system
when a program runs. Under a Wayland session they speak the Wayland protocol to
the compositor directly; otherwise they use the platform's own (`host/dev/win/gfx`:
X11 on Linux, Cocoa on macOS). A program is built once and takes no change.

**How the choice is made.** `gfx_open` tries Wayland when `WAYLAND_DISPLAY` is
set and `IDSTD_GFX` is neither `x11` nor `none`, and a window of positive size is asked for.
If Wayland opens, every later `gfx_*` call goes to it; if there is no
compositor, or it lacks `wl_compositor`, `wl_shm` or `xdg_wm_base`, or it never
answers, nothing is left open and `gfx_open` opens the platform window instead.
The state is one integer kept in C (`wl_mode`), so a call made before any window
exists (`gfx_width` in a program's setup) answers as the platform backend does.

**Headless graphics.** `IDSTD_GFX=none` makes `gfx_open` (Wayland and
platform both) and `glwin_open` return 0 at once, the same code as "no display
available", and opens no connection to either server. `x11` skips Wayland;
empty or unset chooses automatically. `idc/bin/idc` sets `none` for every test
case (docs/TESTS.md, "Cases never open a window"); a case that needs a window
sets `IDSTD_GFX` back with `env_put`. `idc/tools/headless.sh` sets `x11`, so a
program run on its private Xvfb cannot pick the live Wayland session.

**Why the names moved.** `id` has one function per name, and a native is a
function, so the choice cannot sit behind the same native. The platform
backend's natives are now `gfx_sys_open`, `gfx_sys_present` and so on (their C
keeps its `id_gfx_*` spelling; `gfx.h` renames the symbols), and `gfx_open`,
`gfx_present`... are `id` functions in `host/dev/win/seam` that call one or
the other, with the policy of which display to use (`idstd_gfx_want`, and
`net.id` and `session.id`: the socket path, `idstd_wl_connect` and opening a window, which read the environment). The
sixteen wrappers are the whole seam of calls; `gfx_sync`, `gfx_show` and
`gfx_clip_get` are unchanged because they only call it.

**What is `id` and what is C.** The wire protocol and the client are `id`:
`host/dev/win/wl/wire` writes and reads messages by signature (a message is built and
decoded from the tables `idc/tools/wlgen` generates from the protocol XML), and
`host/dev/win/wl/runtime` and `host/dev/win/wl/event` are the registry, the window, buffers, scale, pointer and
keyboard. The generated block at the end of `idstd/conf.id` holds interface
names, each request's and event's signature and flat index, and the enum
entries, for `wayland.xml`, `xdg-shell`, `viewporter`, `fractional-scale-v1` and
`cursor-shape-v1` (the XML is in `idc/tools/wlgen`; `idstd/run.sh wl`
regenerates the block and fails when it differs). The C (`wl_linux.c`, 23
natives) is only what `id` cannot name: a Unix socket that carries
file descriptors, shared memory both sides map, and the keyboard layout.
xkbcommon is not linked: the C declares the few functions it uses and loads
`libxkbcommon.so.0` with `dlopen` when the first keymap arrives
(`ID_XKBCOMMON_LIB` names another library), as `host/dev/audio` loads PipeWire.
When it cannot be loaded the keymap is ignored and a built-in US layout answers
(same key ids, characters and modifiers for a US keyboard), so nothing needs
the library at build time and a program still works; only another layout is not
followed.
Handles are `(kind << 24) | (generation << 8) | slot`, the convention
`trials/sqlq` and `docs/INTEROP.md` describe.

**Tradeoff against a C backend over libwayland-client.** libwayland would be
about 600 lines of C, would not need the generator and would be the more
battle-tested path. It was not taken because the goal is as much `id` as
possible with `idstd` as the foundation, and because the compositor fixture that
tests the client (`idstd/.tests/wl`) needs the same codec on the server side:
with the protocol in `id` the client and its test peer share one implementation
of the wire format, and the whole thing runs headless with no compositor. The
cost is real: about 150 small functions under the three-action, three-per-file
and two-case rules, and a second keyboard path (the built-in US layout) to keep in step with xkbcommon's answers.

**Not done.** The clipboard (`gfx_clip_*` answer 0 under Wayland: the
data-device protocol needs pipes and server-created objects), key
`gfx_poll` codes for non-ASCII text, IME, touch and tablets, subsurfaces,
popups. A resize reaches the program as an event and a changed
`gfx_width/height`; there is no way to refuse one. macOS: `wl_none.c` answers -1
to everything, so Wayland is never chosen there (not compiled or run).
