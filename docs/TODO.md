# What is left to do

> **Status: the list itself, maintained by hand.** Each item points at the doc
> that holds its detail; those docs are the authority on *how*, this file is the
> authority on *what is open and in what order*. Numbers here that can go stale
> are generated elsewhere — see `docs/TESTS.md` for adoption and
> `tests/idstd_expect.txt` for the port list.

Ordered by what unblocks the most. Everything here is open as of 2026-08-19.

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

## 4. `conf.id` constants are parsed but not emitted

`conf.id` accepts `int name = value;` after its imports and rejects an import
that follows one. Nothing yet turns those lines into program globals, so a
constant declared there does not exist at run time, and `--strict-const` names
constants it has nowhere to put.

**The design, and the obstacle, both established.** A constant must reach
`idparse`, which does the checking and the emission, and `id` cannot read a
file — so it travels in the source stream as a marker, exactly as `#file N|PATH`
already does. Four parts:

1. `bin/idc` and `idc.py` read the constants from `conf.id` and inject
   `#const int name = value;` ahead of the source, next to where they already
   inject `#file`.
2. The **lexer must learn a second marker**, and today it cannot: `scan_hash`
   slices unconditionally past `"#file "`, six characters, so `#const int
   max_depth = 3;` lexes as `file  int max_depth = 3;`. Verified. It has to
   dispatch on the marker word instead.
3. `mid/` registers the name as an export with no declaring function — which
   is the entire point, since a constant needs no init call — so
   `check_dead_exports` must not ask which function declares it.
4. `back/` emits it at file scope with a static initialiser
   (`long long id_max_depth = 3;`) rather than as an assignment inside a
   function.

Then migrate `idstd`'s `fx_sintab` across, delete `fx_trig_init`, and turn
`--strict-const` on by default.

Byte-parity is the gate throughout: both compilers must inject the same
markers in the same order and emit the same C.

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

## 9. `--target llvm|wasm` in `bin/idc`, then delete `idc.py`

43% of `idc.py` is the two targets `bin/idc` does not have; the rest is
bootstrap that a checked-in bootstrap C artifact retires. `docs/BACKENDS.md`
is the plan and `tests/run.sh` holds a line ceiling so the file cannot grow
while the work is pending.

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
