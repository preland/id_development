# What is left to do

> **Status: the list itself, maintained by hand.** Each item points at the doc
> that holds its detail; those docs are the authority on *how*, this file is the
> authority on *what is open and in what order*. Numbers here that can go stale
> are generated elsewhere — see `docs/TESTS.md` for adoption and
> `tests/idstd_expect.txt` for the port list.

Ordered by what unblocks the most. Everything here is open as of 2026-08-19.

## 1. A single line of build progress in `bin/idc`

Today `bin/idc` prints nothing while it works and, on failure, whatever the
stages wrote to stderr. For a project of any size that is a silent pause
followed by a wall.

It should show **one line**, rewritten in place, in the spirit of `npm`:
what it is doing now and how far along it is — bootstrap, collect, lex, parse,
check, emit, `cc` — and on success collapse to a single summary line. On
failure it should stop the line and print the errors **concisely**: the
diagnostics themselves, grouped, without the C compiler's own noise unless
that is genuinely the fault.

Constraints worth stating before anyone builds it:

- The line goes to **stderr**, never stdout: `bin/idc PATH --emit-c -` and the
  `idlex | idparse` pipeline both put real output on stdout, and a progress
  animation in the middle of emitted C would be a bug.
- It must **disable itself when stderr is not a terminal**, or every CI log
  and every `2>` capture in `tests/` fills with carriage returns.
- `tests/invalid.sh` compares diagnostics **byte for byte against `idc.py`**.
  Progress output must not reach that comparison, and the error format must
  not change, or the whole negative suite fails. This is the real constraint:
  the pretty part is easy, keeping the diagnostics identical is the work.

## 2. Test cases that can set global state

`docs/TESTS.md` specifies `[globals](args):(expected)`. Until it exists,
`--require-tests` cannot be turned on for any directory containing a function
that reads module state — which is all 13 of `sys/err`, the trig half of
`core/math`, and every flat-store writer. Adoption is stuck at ~3% because of
it. See `docs/TESTS.md`, "What the case format cannot express".

## 3. `--tests` in the self-hosted compiler

`bin/idc --require-tests` counts cases; only `idc.py` *runs* them, because
running one needs a generated entry point. Until both halves are self-hosted,
the rule is enforced by the compiler being retired.

## 4. Port `engine`, `moonbuggy` and `solitaire` onto `idstd`

The three remaining `broken` lines in `tests/idstd_expect.txt`. Each defines a
name or a body `idstd` already has. The compiler's own two stages were the
first four and are done.

## 5. The rest of the demos become their own repositories

`flappy`, `nativeapp` and `webdemo` are done (`../id_flappy`,
`../id_nativeapp`, `../id_webdemo`). The applications still in `demos/` —
the graphics programs and the terminal engine with its two games — belong
outside too. What stays is the small teaching set the suite uses as language
fixtures: `hello`, `calc`, `control`, `adventure`, `wordcount`, `average`,
`fsdemo`, `idview`, `idc_in_id_calc`.

This one is not free: `tests/backends.sh` drives `gfxdemo` and `gl3d`, and
`tests/self_host_build.sh` sweeps `demos/*/`. Moving a demo out means deciding
what replaces it as a fixture.

## 6. `--target llvm|wasm` in `bin/idc`, then delete `idc.py`

43% of `idc.py` is the two targets `bin/idc` does not have; the rest is
bootstrap that a checked-in bootstrap C artifact retires. `docs/BACKENDS.md`
is the plan and `tests/run.sh` holds a line ceiling so the file cannot grow
while the work is pending.

## 7. String building is quadratic

A 60 000-character literal costs 1.77 GB and 1.4 s; 4× the input is ~14× the
memory. The lexer accumulates tokens and the emitter builds each line of C
with `+`, and both want `poke8` + `str_of_mem`. `docs/GAPS.md` §3.

Measured, so it is not folklore — but it is **not** what makes the suite slow.
The suite is 83 s; that was mismeasured as ~25 minutes once, under heavy
parallel load, and the mistake is recorded here so it is not repeated.

## 8. The suite is 83 s, over the 60 s budget

Mitigated rather than fixed: `tests/run.sh` runs by section (`--list`,
`--from`, `--resume`) and every section is 6–36 s. A real fix would make the
whole thing fit, and `conform.sh` at 36 s is where the time is.
