# What is left to do

> **Status: the list itself, maintained by hand.** Each item points at the doc
> that holds its detail; those docs are the authority on *how*, this file is the
> authority on *what is open and in what order*. Numbers here that can go stale
> are generated elsewhere — see `docs/TESTS.md` for adoption and
> `tests/idstd_expect.txt` for the port list.

Ordered by what unblocks the most. Everything here is open as of 2026-08-23.

## ~~1. A single line of build progress in `bin/idc`~~ — done

`bin/idc` rewrites one line in place through `bootstrap`, `compile`, `verify`
and `link`, then collapses to a summary:

```
  built build/hello (16744 bytes, 51 source files)
```

On failure the line is **cleared** rather than written over, so a diagnostic
never lands on top of half a progress bar.

The constraint named below turned out to be the whole design: progress goes to
stderr and only when stderr is a terminal, so a log, a pipe or a test capture
sees **zero extra bytes**. `IDC_NO_PROGRESS=1` turns it off on a terminal too.
Verified: `bin/idc` writes 0 bytes to a redirected stderr on success, and its
error text is still byte-identical to `idc.py`'s.

## 2. Test cases that can set global state

`docs/TESTS.md` specifies `[globals](args):(expected)`. Until it exists,
`--require-tests` cannot be turned on for any directory containing a function
that reads module state — which is all 13 of `sys/err`, the trig half of
`core/math`, and every flat-store writer. Adoption is stuck at ~3% because of
it. See `docs/TESTS.md`, "What the case format cannot express".

## 3. Move `check_assigned_once` into the self-hosted compiler

It is a semantic check on the AST — "this export is assigned once and never
changed, so it is a constant" — and every other rule of the language lives in
`compiler/parse/mid/`. This one is in `idc.py` because that is where it was
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
$ bin/idc proj && ./build/proj
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
no declaring function. `back/emit/prog/head/const/` emits it at file scope with
its initialiser attached (`int max_depth = 7;  /* constant from conf.id */`).

**`idc.py` does not implement this, and will not.** The bootstrap rule
(`docs/HACKING.md`) is that stage 0 needs a construct only once the compiler's
own source uses it, and the compiler's own `conf.id` declares no constants. So
byte-parity is not the gate here; `tests/self_host_build.sh` checks the three
behaviours above against `bin/idc` alone.

Still open, and unblocked by this: migrate `idstd`'s `fx_sintab` across, delete
`fx_trig_init`, and turn `--strict-const` on by default. That also needs item 3.

## 5. `--tests` in the self-hosted compiler

`bin/idc --require-tests` counts cases; only `idc.py` *runs* them, because
running one needs a generated entry point. Until both halves are self-hosted,
the rule is enforced by the compiler being retired.

## 6. Port `engine`, `moonbuggy` and `solitaire` onto `idstd`

The three remaining `broken` lines in `tests/idstd_expect.txt`. Each defines a
name or a body `idstd` already has. The compiler's own two stages were the
first four and are done.

## 7. The rest of the demos become their own repositories

`flappy`, `nativeapp` and `webdemo` are done (`../id_flappy`,
`../id_nativeapp`, `../id_webdemo`). The applications still in `demos/` —
the graphics programs and the terminal engine with its two games — belong
outside too. What stays is the small teaching set the suite uses as language
fixtures: `hello`, `calc`, `control`, `adventure`, `wordcount`, `average`,
`fsdemo`, `idview`, `idc_in_id_calc`.

This one is not free: `tests/backends.sh` drives `gfxdemo` and `gl3d`, and
`tests/self_host_build.sh` sweeps `demos/*/`. Moving a demo out means deciding
what replaces it as a fixture.

## 8. Work the `idc.py` lint budget down

`tools/lint_idcpy.py` holds `idc.py` to a lightweight form of the rules the
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

The one rule deliberately not checked is 3 functions per file: `idc.py` is one
file with 160, and applying it means splitting the file, which is item 9.

## ~~9a. `--target llvm` in `bin/idc`~~ — done

`bin/idc PATH --target llvm` compiles through an SSA IR of `id`'s own and an
optimiser over it, passes all 62 conformance cases, compiles the compiler, and
reproduces itself exactly. `tests/conform.sh`'s `llvm` target is now this one
rather than `idc.py`'s. See [`docs/LLVM.md`](LLVM.md).

## 9b. `--target wasm` in `bin/idc`, then delete `idc.py`

The last target `bin/idc` does not have, and now the only thing besides the
bootstrap holding `idc.py` here. The WASM back end is ~1428 lines of it.

The shape is settled by the LLVM work: lower to the same IR
(`compiler/parse/back/ir/`) and print WAT from it, rather than writing a third
AST walk. Almost everything that was hard the first time -- the CFG, phis,
argument evaluation order, the boxing contract -- is already in the IR and
target-independent. What is genuinely new is that WASM has structured control
flow rather than a CFG, so the printer has to rebuild `block`/`loop`/`br_if`
from the branches, which is a real algorithm (relooper, or the simpler
stackifier LLVM's own back end uses) and not a spelling.

After that, `docs/BACKENDS.md`'s checked-in bootstrap C artifact retires the
last job, and `git rm idc.py` breaks nothing.

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

Mitigated rather than fixed: `tests/run.sh` runs by section (`--list`,
`--from`, `--resume`) and every section is 6–36 s. A real fix would make the
whole thing fit, and `conform.sh` at 36 s is where the time is.
