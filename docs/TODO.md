# What is left to do

> **Status: the list itself, maintained by hand.** Each item points at the doc
> that holds its detail; those docs are the authority on *how*, this file is the
> authority on *what is open and in what order*. Numbers here that can go stale
> are generated elsewhere — see `docs/TESTS.md` for adoption and
> `idc/tests/idstd_expect.txt` for the port list.

Ordered by what unblocks the most. Everything here is open as of 2026-08-23.

## ~~1. A single line of build progress in `idc/bin/idc`~~ — done

`idc/bin/idc` rewrites one line in place through `bootstrap`, `compile`, `verify`
and `link`, then collapses to a summary:

```
  built build/hello (16744 bytes, 51 source files)
```

On failure the line is **cleared** rather than written over, so a diagnostic
never lands on top of half a progress bar.

The constraint named below turned out to be the whole design: progress goes to
stderr and only when stderr is a terminal, so a log, a pipe or a test capture
sees **zero extra bytes**. `IDC_NO_PROGRESS=1` turns it off on a terminal too.
Verified: `idc/bin/idc` writes 0 bytes to a redirected stderr on success, and its
error text is still byte-identical to `idc/idc.py`'s.

## 2. Test cases that can set global state

The chosen form is a named setup and named checks,
`given SETUP (args):(expected) then CHECK:(literal)`, with `(import g)` allowed
as an argument once a setup has exported `g`. It has landed (`docs/TESTS.md`,
"Module state"), and no build in `idc/tests/run.sh` that merges `idstd` goes
through `idc/idc.py` any more, so `idstd` can hold cases written with it. What
remains is writing them: the two-case minimum is on by default, and every
build that merges `idstd` passes the deprecated `--allow-untested` until they
exist — 59 of its functions lack them, among them all 13 of `sys/err`, the trig
half of `core/math`, and every flat-store writer. `c2id` still builds itself with `idc/idc.py` and `idstd`
merged, so a `given` in `idstd` breaks that build (`docs/TESTS.md`, the status
block). See `docs/TESTS.md`, "What the case format cannot express".

## 3. Move `check_assigned_once` into the self-hosted compiler

It is a semantic check on the AST — "this export is assigned once and never
changed, so it is a constant" — and every other rule of the language lives in
`idc/compiler/parse/mid/`. This one is in `idc/idc.py` because that is where it was
written, which is precisely the drift the line ceiling exists to catch, and it
did catch it: the ceiling had to be raised by 96 lines to land it. Moving it
drops the ceiling by 96 again.

It also cannot be turned on by default until item 4 below lands. `--strict-const`
runs it today; with the flag, `idstd`'s `fx_sintab` is the first thing it names.

## ~~4. `conf.id` constants are parsed but not emitted~~ — done

A constant declared in a project's `conf.id` is now a program global:

```sh
$ cat proj/conf.id
int max_depth = 7;
$ cat proj/main.id
main(int argc, string[] argv) { print((import max_depth)); } return int 0;
$ idc/bin/idc proj && ./build/proj
7
```

All four parts landed as designed. The driver injects `#const` ahead of the
source and the declaration after it is *ordinary* source, so `parse_decl` reads
it and nothing re-implements declaration parsing for a marker payload
(`front/parse/decl/top/marker/const/`). The constant is registered through
`add_export2`, so it reserves its name program-wide and a later `export` of the
same name is the existing duplicate error. Its owner is `"conf.id"` — a string
no identifier can spell, so no function can claim to own a constant — and
`init_reach` seeds the reachable set with it, which is how "an export whose
declaring function is never called" stops being asked about something that has
no declaring function. `back/tgt/c/emit/prog/head/const/` emits it at file scope with
its initialiser attached (`int max_depth = 7;  /* constant from conf.id */`).

**`idc/idc.py` does not implement this, and will not.** The bootstrap rule
(`docs/HACKING.md`) is that stage 0 needs a construct only once the compiler's
own source uses it. It now does: a function that only returns a constant is an
error (`docs/SPEC.md` §7.2), so `compiler/parse/conf.id` declares `idx_n` and
`builtin_src`, and stage 0 is the bootstrap C regenerated from that source. So
byte-parity is not the gate here; `idc/tests/self_host_build.sh` checks the three
behaviours above against `idc/bin/idc` alone, and idc.py can no longer build
the parser stage.

Still open, and unblocked by this: migrate `idstd`'s `fx_sintab` across, delete
`fx_trig_init`, and turn `--strict-const` on by default. That also needs item 3.

## 5. `--tests` in the self-hosted compiler

Both halves are self-hosted, and the two-case minimum is the default: every
build of `idc/bin/idc` counts cases, and every written case runs, each in a
process of its own, with a failing case failing the build (`docs/TESTS.md`,
"How it runs"). What remains is deleting `--allow-untested`, the deprecated
opt-out every build in these repositories still passes. That waits on the
cases themselves (item 2; `idc/tests/run.sh` fails once adoption has no
function short of two cases while the flag exists). Freestanding builds are no
longer in the way: their cases run on the build host against the same source,
and a function that reaches an `asm` body with no host row, a native, or a
`--runtime` helper is exempt with a note (`docs/TESTS.md`, "A freestanding
build runs its cases on the build host"). The kernel and the runtime still pass
`--allow-untested` until their testable functions have cases.

## 6. Port `engine`, `moonbuggy` and `solitaire` onto `idstd`

The three remaining `broken` lines in `idc/tests/idstd_expect.txt`. Each defines a
name or a body `idstd` already has. The compiler's own two stages were the
first four and are done.

## 7. The rest of the demos become their own repositories

`flappy`, `nativeapp` and `webdemo` are done (`../id_flappy`,
`../id_nativeapp`, `../id_webdemo`). The applications still in `demos/` —
the graphics programs and the terminal engine with its two games — belong
outside too. What stays is the small teaching set the suite uses as language
fixtures: `hello`, `calc`, `control`, `adventure`, `wordcount`, `average`,
`fsdemo`, `idview`, `idc_in_id_calc`.

This one is not free: `idc/tests/backends.sh` drives `gfxdemo` and `gl3d`, and
`idc/tests/self_host_build.sh` sweeps `demos/*/`. Moving a demo out means deciding
what replaces it as a fixture.

## 8. Work the `idc/idc.py` lint budget down

`idc/tools/lint_idcpy.py` holds `idc/idc.py` to a lightweight form of the rules the
compiler enforces: 32 statements per function (`id` allows 3 actions per
block), nesting depth 4 (`id` allows 2), and no two functions with the same
logic up to renaming (`id`'s rule exactly, and it already passes).

**19 functions exceed the statement limit and 7 the nesting limit.** They are
named in `BUDGET`/`DEPTH_BUDGET`, so a new violation fails while the old ones
stand, and an entry that stops being true also fails — a stale budget is how a
ratchet quietly stops ratcheting.

Almost all of them are the same four functions written three times:
`gen_expr`, `gen_binop`, `gen_call` and `gen_stmt`, once per target, the
largest at 128 statements. That is the duplication `docs/BACKENDS.md` exists to
remove, so the budget falls as item 9 progresses rather than through separate
cleanup.

The one rule deliberately not checked is 3 functions per file: `idc/idc.py` is one
file with 160, and applying it means splitting the file, which is item 9.

## ~~9a. `--target llvm` in `idc/bin/idc`~~ — done

`idc/bin/idc PATH --target llvm` compiles through an SSA IR of `id`'s own and an
optimiser over it, passes all 62 conformance cases, compiles the compiler, and
reproduces itself exactly. `idc/tests/conform.sh`'s `llvm` target is now this one
rather than `idc/idc.py`'s. See [`docs/LLVM.md`](LLVM.md).

## ~~9b-0. Check in the bootstrap C~~ — done

`idc/bootstrap/idlex.c` and `idc/bootstrap/idparse.c` are the C `idc/compiler/lex` and
`idc/compiler/parse` emit about themselves. `idc/bin/idc` compiles them with `cc` to
get stage 0, then rebuilds both stages from the working tree through it, so
`idc/idc.py` is no longer executed by the driver at all —
`idc/tests/self_host_build.sh` proves it by running a cold-cache build against a
root whose `idc/idc.py` is a directory.

This is the item that unblocks every *additive* language feature (`break`, a
record, `clear`, a binary literal): the frozen thing that could not be taught a
new construct is now a snapshot, moved forward by `idc/tools/regen_bootstrap.sh` in
the same commit that teaches it. `idc/bootstrap/README.md` states the two-commit
rule. `docs/RELIANCES.md` §1 is the argument for why this went first.

## 9b. `--target wasm` in `idc/bin/idc`, then delete `idc/idc.py`

The last target `idc/bin/idc` does not have. The WASM back end is ~1428 lines of
`idc/idc.py`.

**What the port is, precisely.** `idc/idc.py`'s `WasmBackend` (`idc/idc.py:3316-4610`)
is a third AST walk, and it gets structured control flow for free because it
reads `if`/`while` directly: an `IfStmt` is `(if (then) (else))` and a
`WhileStmt` is `(block $b (loop $c (br_if $b (i32.eqz cond)) ... (br $c)))`.
Lowering to `idc/compiler/parse/back/ir/` instead loses that and has to rebuild it,
which is the one genuinely new algorithm here — but the CFG the front end
produces is not merely reducible, it is *structured*, because `if` and `while`
are the only control flow the language has. So a stackifier (LLVM's approach,
which assumes reducibility) is enough and a full relooper is not. What the IR
does not have and the stackifier needs: an RPO numbering and back-edge
detection. It has predecessors (`back/ir/opt/cfg/pred/`) and reads successors live off
a terminator's `iblk`; it has no dominator tree, and deliberately so
(`back/ir/opt/mem/init/init.id` explains why mem2reg does not need one).

The other half is not new: `runtime.wat` is 578 lines of hand-written WAT in
`wasm_runtime_funcs()` (`idc/idc.py:3414`) with no libc, importing
`wasi_snapshot_preview1` directly, and it moves across as data.

The shape is settled by the LLVM work: lower to the same IR
(`idc/compiler/parse/back/ir/`) and print WAT from it, rather than writing a third
AST walk. Almost everything that was hard the first time -- the CFG, phis,
argument evaluation order, the boxing contract -- is already in the IR and
target-independent. What is genuinely new is that WASM has structured control
flow rather than a CFG, so the printer has to rebuild `block`/`loop`/`br_if`
from the branches, which is a real algorithm (relooper, or the simpler
stackifier LLVM's own back end uses) and not a spelling.

After that, and after items 5 (running a test case) and the decision to stop
differential-testing against a second implementation, `git rm idc/idc.py` breaks
nothing. The bootstrap half of that sentence is already true.

## 9c. Make the freestanding target trap

`docs/KERNEL.md` lists three promises of `docs/SPEC.md` the kernel cannot keep,
and all three are the same missing thing: a trap has nowhere to go. The IDT and
the panic path now exist, so this is smaller than it was -- what is left is
routing `id`'s own traps (division by zero, an out-of-range index, a store past
the arena) into it, which means the freestanding runtime calling `kpanic`
rather than letting the CPU fault.

## 9d. The eight things docs/FRICTION.md says are worth fixing

Written up with the code that hit each one. Two of them are a few lines and
close the entries that produce *wrong answers* rather than awkward code:

* **A floor** in `idstd`. `fx_abs`, `fx_min`, `fx_max`, `fx_clamp` and
  `fx_sign` exist; nothing floors, and division truncates toward zero. Every
  program touching a negative coordinate writes it again or is quietly wrong.
* **A `print` that writes to stderr.** A parser that meets a corrupt archive
  currently writes "corrupt archive" onto the same stream as the data.

The other six are real work: a record type, a `break`, a way to return a
failure, an array literal that takes its type from its context, a decision on
evaluation order (`docs/SPEC.md` S11), and a `string` that knows its own length
-- which is the 767x one.

## 10. String building is quadratic

A 60 000-character literal costs 1.77 GB and 1.4 s; 4× the input is ~14× the
memory. The lexer accumulates tokens and the emitter builds each line of C
with `+`, and both want `poke8` + `str_of_mem`. `docs/GAPS.md` §3.

Measured, so it is not folklore — but it is **not** what makes the suite slow.
The suite is 83 s; that was mismeasured as ~25 minutes once, under heavy
parallel load, and the mistake is recorded here so it is not repeated.

## 11. The suite is 83 s, over the 60 s budget

Mitigated rather than fixed: `idc/tests/run.sh` runs by section (`--list`,
`--from`, `--resume`) and every section is 6–36 s. A real fix would make the
whole thing fit, and `conform.sh` at 36 s is where the time is.

## ~~12. Link a native backend only when its symbols are reachable (idstd C7)~~ — done

The direction this repo is pointed: `idc/backends/` stops being a thing a
program names, and becomes implementation detail inside `idstd` — a program
calls a high-level `id` function and the library decomposes it differently per
platform. C7 was the mechanism that needed first, and it exists
([`BACKENDS.md`](BACKENDS.md), "A backend is linked only when a native of it is
reached"):

* `idparse --natives` lists the natives reachable from `main` and, separately,
  from the test cases, each with the call that reaches it and the file that
  declares it. The emitted program is unchanged.
* `idc/bin/idc` compiles and links only the attached backends whose directory
  declares one of those natives — for the program and for the harness
  separately. An attached backend nothing reaches costs no compile and no link
  flag, so a standard library can name every backend.
* A reached native nothing attached implements for the build's platform is a
  diagnostic at the reaching call, naming the native and the triple.

The plan this item was written with had two premises that had gone stale by
the time it was built: the `extern int` block no longer exists (natives are
declared in `id` and every call is resolved), and `backend.json`'s `abi` is
still read by nothing — the `native` declarations are the contract instead.

**The backends moved into `idstd`** (2026-09-13). `fs` is `sys/io/fs`, `gfx`
and `gl` are `sys/win/gfx` and `sys/win/gl`, each with its C and its
`backend.id`; `idc/backends/` is gone, and no project names a backend.
`idc/bin/idc` attaches any directory holding a `backend.id` in a collected tree,
so the library's `conf.id` imports nothing. `--backend DIR` is now the override:
a directory with a `backend.id` of the same `name` and its sources replaces how
that backend is linked for one build. A reached native the platform cannot
link is checked before the refusal to run another triple's cases, which the
library's cases otherwise always hit first. See
[`BACKENDS.md`](BACKENDS.md), "Where the backends live".

Still open:

* The `idstd` functions over the natives are not written: the six groups that
  call graphics natives (`loop`, `draw_scene`/`submit_tris`, `cell_compose`,
  `draw_one_target`, `render_proj`) still live in the projects that carry
  them. Every program's test harness runs the library's cases, so a case that
  reaches a native links that backend into every build's harness; those
  functions need cases that reach no native, or the harness has to take only
  the cases of what the program reaches.
* `idc/idc.py` cannot build against the library at all (it cannot parse a
  `given` case, and it counts a `backend.id` toward the 3-entries rule).
* The LLVM target links no backend: a program reaching a native builds with
  `--target llvm` only as far as the link.

## 13. An interpreted mode, so iterating in `id` costs what it costs in Python

A goal set 2026-09-13: choosing `id` must not mean giving up edit-run speed.
Today every run is lex, parse, check, emit C, run every test case, and a C
compile and link — seconds for a small program, and much longer for a large
one. The user wants the same iterability as Python, so that there is no
tradeoff between the rules `id` enforces and how fast a change can be tried.

What that means concretely, to be designed rather than assumed:

* `idc run PATH [ARGS]` executes a program without producing a binary, with
  every compile-time rule still enforced — an interpreter that skipped the
  checks would be a second, laxer language.
* Test cases run in the same mode, so the default build's case run gets cheaper
  too.
* The interpreter is a target of the self-hosted compiler, not a separate
  implementation: `docs/BACKENDS.md` (the type registry, and "it also gives an
  interpreted mode") and `docs/DISPATCH.md` (a function reference as an index
  into a vector of bodies) already describe where it plugs in.
* Native backends and `asm` need an answer — calling the C backend from the
  interpreter, or refusing by name, as `docs/ASM.md` already notes for an
  interpreted target.

Measure first: where the seconds go today for a small project and for
`idc/compiler/parse`, so the design targets the real cost.

## 14. Move `idem`'s game seam onto function values

`idem/engine/` calls six functions each game defines — `g_init`, `g_stage`,
`g_step`, `g_draw`, `g_ref`, `g_act` — so every program that links the engine
without being a game (the unit tests, the editor) imports `idem/stub/`: six
no-ops that each touch a counter, because six identical no-ops would be one
function under the duplicate-logic rule. Function values
([`SPEC.md`](SPEC.md) §1.1) are the replacement the design chose: the engine
takes the seam as values — exports its setup stores, read with
`(import NAME)` where a frame calls them — and a game hands its functions in,
so `stub/` and the name collision it exists to avoid both go away. Not done
yet; what it has to settle:

* each seam function's current signature becomes a function type, fixed in
  the engine;
* every place the engine calls a `g_*` name reads the export into a local
  first, since a call is only through a parameter, local or export by name;
* the values must be stored before the first frame, and nothing checks that
  an export of a function type was stored before it is called;
* `IDEM_COMPILER=idc.py` cannot build it: `idc/idc.py` has no function values.
