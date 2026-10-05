# An interpreted mode for `id`

> **Status: a scoping document, with milestone M1 built** (section 7). Option
> B was chosen; sections 1-6 are the scoping text as it was written and are not
> updated, so where they say "nothing is implemented" section 7 is the
> exception. Sections marked **Recommendation** are a recommendation; sections
> marked **Design fork** are the user's to decide and are deliberately left
> open. The latency numbers in section 2 are a dated snapshot with the
> commands that reproduce them; do not copy them elsewhere, re-measure.

The goal, set 2026-09-13: choosing `id` must never cost edit-run speed. Python
is the yardstick. Today `id` is the slow half of that comparison, and section 2
shows where the time goes, which is not where one would guess.

Existing documents that already promise an interpreter, and what they say:

- `docs/TESTS.md` ("Enforcement, and the migration"): "When the interpreter
  target lands, the harness stops being a subprocess and becomes an evaluation
  inside the compiler; the syntax and the diagnostics do not change."
- `docs/BACKENDS.md` "Order of work", step 4: the second target was **Python**.
  That drifted from the decision for no new Python and an interpreter written
  in `id`; BACKENDS.md step 4 now says an `id` interpreter and points here for
  the fork, so it follows whatever this document resolves to.
- `docs/DISPATCH.md` opened "Nothing here is implemented ... `id` has no function
  pointers". `docs/SPEC.md` section 1.1 specifies `func(T) return R` values;
  DISPATCH.md now says so and keeps `select` as an open proposal on top of them.

---

## 1. Use cases and requirements

| # | use | requirement | why it is hard today |
| --- | --- | --- | --- |
| U1 | `./tool.id args` with a `#!` line | one file, run directly, argv and stdin reach `main`, `main`'s return is the exit status | the lexer treats `#word` as an injected marker (`scan_hashop`); a leading `#!` is not specified anywhere |
| U2 | edit-run of a small program | under ~200 ms from save to first output, cold process, no daemon | see section 2: 0.43 s cold, 0.13 s warm without idstd, 0.44 s warm with it |
| U3 | a project tree (the `trials/` programs: 85 files, a `conf.id`, imports) | same as U2, scaling with the edit, not with the tree | a warm build of `trials/kv` measured 2.1 s |
| U4 | REPL | evaluate a line, keep state, keep the compiler's rules meaningful | see section 5 |
| U5 | tests | "cases run before output" keeps its meaning and stops costing a C compile | the harness is a separate C build per program (section 2) |

Requirements that follow, independent of architecture:

- R1. **Parity.** Same stdout, stderr, exit code and trap text as the compiled
  program (`idc/tests/conform.sh` is already the cross-target gate; "the C
  target is the reference", `docs/SPEC.md`). An interpreter that disagrees is
  a bug in the interpreter.
- R2. **No C compiler on the hot path.** The measured floor for `cc` alone on a
  20 KB emitted C file is 0.15 s (section 2), so a budget of 200 ms with one
  `cc` is not achievable; with two (program and harness) it is impossible.
- R3. **Written in `id`.** The interpreter and its driver. `idc/bin/idc` is
  2910 lines of shell; the project direction (memory: `no-shell-in-repo`) is
  pure `id`, so a new shell wrapper is not an option, and the interpreter's
  driver must not call `sha256sum` per file (finding below).
- R4. **The same rules apply to the interpreter's own source**: 3 functions per
  file, 3 entries per directory, the action limit, two cases per function.
- R5. **Memory safety and limits**: the `docs/SPEC.md` section 8 trap table with
  its exact text; the 4 GiB address-space and 30 s per-case limits of
  `docs/TESTS.md`.

---

## 2. Today's latency (baseline to beat)

Program: `scratch/hello/hello.id`, 3 functions, 6 cases, prints one line
(written to satisfy every rule; both the nested-call rule and the 3-action
rule rejected my first draft, which is a finding in itself). Emitted C is 20.8
KB / 514 lines. Machine: 12 cores, NixOS, `cc` = gcc 15.2 wrapper. Date:
2026-09-30. Stage times come from `bash -x` with `PS4='+T${EPOCHREALTIME} '`,
so each includes some tracing overhead; wall totals come from `time`.

"Cold" is `IDC_NO_CACHE=1` (the compiler binaries are cached, everything
program-specific is not). "Warm" is the second run of an unchanged program.
A from-scratch cold start that also rebuilds `idlex`/`idparse` from
`bootstrap/*.c` was **not measured** (it is one `cc` of 741 KB of C; it could
exceed the 60 s limit).

### 2.1 `--no-std` (a program that needs no idstd)

| stage | cold | warm |
| --- | ---: | ---: |
| layout check (`idlayout`) | about 13 ms | about 13 ms |
| lex (`idlex`) | 4 ms | cached |
| parse + check + emit (`idparse --harness`) | 3 ms | cached |
| harness build (`cc -O0` + link) | 205 ms | cached object |
| run the cases | about 4 ms | skipped (case cache) |
| `cc -fsyntax-only` on the emitted C | 31 ms | 32 ms |
| final `cc` + link | 158 ms | cached object |
| **wall total** | **0.43-0.45 s** | **0.13 s** |

### 2.2 default build (idstd attached)

| stage | cold | warm |
| --- | ---: | ---: |
| lex program + idstd (364 files) | 111 ms | per-unit cache |
| parse program + idstd | 376 ms | per-unit cache |
| standard library's own precheck (recursive `idc` of idstd: its harness, its cases) | 3357 ms | cached |
| program harness build | 292 ms | cached |
| run the cases | 181 ms | cached |
| `cc -fsyntax-only` | 30 ms | about 30 ms |
| final `cc` | 154 ms | cached |
| **cache-key computation in shell** | (inside the above) | **about 240 ms: 246 `sha256sum` forks** |
| **wall total** | **4.6 s** | **0.44 s** |

Appending a comment line to `hello.id` and rebuilding took 0.84 s once, then
0.43 s: a source edit defeats every program-specific cache.

### 2.3 a real project

`trials/kv` (85 `.id` files, 2,332 lines, 112 KB), copied to scratch:
first build 4.5 s; warm, **nothing changed**, 2.1-2.2 s (three runs); with
`IDC_NO_CACHE=1`, 7.5 s. In the warm run the harness binary came from the
object cache yet **the harness ran for about 1.1 s every time**, so the case
results are not being reused for it. I did not establish why (guess: the case
cache is keyed so that kv's cases re-run whenever a native backend is linked;
confirm by reading `case_cache_global` in `idc/bin/idc` around line 2092).
Also seen: `cache_prune ... 50` caps the case cache at 50 entries, so a
session that builds more than 50 programs evicts its own results.

### 2.4 the C compiler alone, on the emitted C

| command | time |
| --- | ---: |
| `cc -O0 -fsyntax-only` | 27 ms |
| `cc -O0 -c` | 56 ms |
| `cc -O0` (compile and link, default linker) | 156 ms |
| `cc -O0 -fuse-ld=lld` | 80 ms |
| `clang -O0 -fuse-ld=lld` | 61 ms |
| `clang -O0 -c` | 42 ms |

### 2.5 What this says

1. **Front end is not the problem.** Lex plus parse of a small program is 7 ms.
   Even cold with all of idstd it is under half a second, and the per-unit
   cache already removes that.
2. **`cc` is about 93% of a cold small build** (harness link 205 ms, syntax
   check 31 ms, final link 158 ms of 0.43 s), and **the default linker is two
   thirds of each `cc`**. Swapping in `lld` is measured (2.4) to halve a
   `cc -O0`. That is a cheap improvement to the *existing* path, independent of
   any interpreter, and is a separate change from this scoping work.
3. **The warm build is dominated by shell**, not compilation: about 240 of
   about 440 ms is 246 `sha256sum` forks in `bin/idc`. No amount of
   interpreter work fixes that; an `id`-written driver (R3) does.
4. **The first-edit cost is structural.** Any design that runs the harness
   through `cc` cannot get under about 0.25 s cold, because the harness is a
   second C compile plus link of a program that is changing.

The interpreter therefore has to beat roughly **0.43 s (cold, no std)** and
**0.44 s (warm, std)**, and the 200 ms target is reachable only if neither a C
compile nor a shell hash loop is on the path.

---

## 3. Architecture options

All four keep `id`'s semantics in one place only if they consume the output of
the existing front and middle end (`compiler/parse/front`, `mid`: tokens,
node store, type and rule checks). They differ in what they consume after
that.

Common issues first.

**Natives.** idstd calls C through `native` declarations (`docs/BACKENDS.md`,
"Native backends"): 68 declarations across 7 C files of about 1,600 lines in
this checkout (fs, env, proc, sock, gfx, gl and so on). An interpreter written
in `id` is itself compiled, so it can link the natives it was built with:

- *Linked-in host.* The interpreter binary attaches every idstd backend (as any
  `id` program can), and a call to a native is an interpreter dispatch chain
  from name to a call with the right arity and types. Simple, fast, and
  parity-exact because it is the same C. Limit: a *user's own* `backend.id`
  with C sources cannot be present in a prebuilt interpreter. That project
  needs a rebuilt host (a compile, which is the thing being avoided) or
  falls back to compiled mode. **Design fork F6.**
- *`dlopen` of prebuilt objects.* Would admit user natives without rebuilding
  the interpreter, but needs a `dl_open`/`dl_call` native pair with an
  argument-marshalling layer for `int`, `word`, `float`, `string`, lists. The
  marshalling is new C, and a generic call needs libffi-like assembly or a
  finite set of shapes. Not needed for milestone 1.

**Dispatch without function pointers.** An interpreter loop is a dispatch on
an opcode or node kind. `SPEC.md` section 1.1 now has function values, so a
table of handlers is expressible; whether it compiles to something faster than
an `if` chain is **not measured**. A chain of about 40 compares per
instruction is the worst case; ordering by frequency or a binary split bounds
it at about 6. This decides the interpreter's speed class and is the first
thing the milestone measures.

**Limits and traps.** A compiled program traps by printing the section 8
message and exiting. An interpreter can do better, because a trap is a value
it can propagate, which is what "the harness becomes an evaluation inside the
compiler" needs: a trapping case must fail that case, not kill the compiler.
The 4 GiB limit carries over unchanged at process level (`ccrun` applies
`ulimit -v`). The 30 s per-case limit cannot be wall-clock inside one process
without a timer native; a **fuel counter** (instructions executed) is
deterministic, reproducible and needs no native, at the price of a constant
that is not seconds. **Design fork F7.**

**Determinism.** `SPEC.md` section 7 fixes left-to-right evaluation; a
sequential interpreter satisfies that by construction, and it is checked by
running `idc/tests/conform/` through it. Float printing, `-nan` versus `nan`
(section 10, unspecified) and `argv[0]` are the known divergence points.

### Option A. Tree-walking interpreter over the node store

- **Reuses:** lex, parse, all of `mid` (checks and types). Nothing from `back/`.
- **How it works:** evaluate `node[n]` by kind with a dispatch chain, locals in
  a frame of the flat store, calls recursing into the interpreter.
- **Pros:** the smallest first step; diagnostics can point at source lines
  (nodes carry lines); no lowering bugs to inherit; REPL is natural (evaluate
  a fresh node).
- **Cons:** it is a **third semantic walk** of the AST (C emitter, IR builder,
  now this), exactly the duplication `docs/BACKENDS.md` was written to end.
  Every language addition (the recent `chain`, `func` values, list constants)
  must be implemented a third time. Speed: one dispatch per node with
  parallel-list reads per field; slowest of the four at run time.
- **Parity risk:** highest, because the lowering rules the conform gate already
  holds the other two targets to are re-derived by hand.
- **Natives:** linked-in host or dlopen, as above.
- **Phases:** (A1) expressions and locals on ints and strings; (A2) control
  flow, calls, lists, traps with exact text; (A3) builtins and the flat store;
  (A4) `chain`, `func` values, exports and `import`; (A5) natives; (A6) the
  case syntax (`given`, `then`, `stdin`, `timeout`, `traps`, `calls`,
  `prints`).

### Option B. Interpret the existing IR

- **Reuses:** everything in A, plus `back/ir/build` (AST to alloca-form IR),
  and optionally `back/ir/opt`. `docs/LLVM.md` records this lowering as
  passing 62 of 62 conformance cases (at that writing; re-query) and as a
  self-hosting fixpoint. The IR is already flat parallel lists (`iop`, `ity`,
  `ia`, `ib`, `istr`, `ilist`, `iblk`), about 35 opcodes.
- **How it works:** either walk the IR columns directly (no separate bytecode
  encoding), or encode to a denser instruction stream as a later phase.
  `-O0` alloca form maps to a frame of slots and is "obviously correct" by
  design (`docs/LLVM.md`, "Lowering is deliberately dumb"); `-O1` adds phis,
  which an interpreter must execute as moves on block entry. Start at `-O0`.
- **Pros:** semantics live in **one** lowering, shared with the LLVM target and
  checked by the conform gate; the evaluator is a small, regular switch over
  opcodes; builtins are already `call` to named runtime helpers, so the
  interpreter implements the same finite builtin list the LLVM runtime does;
  the IR is a better base for a faster encoding later.
- **Cons:** diagnostics lose source positions unless the IR keeps the node
  (`fnnode` exists per function, per instruction it is not recorded; runtime
  trap messages need no line, compile errors come from `mid` anyway);
  a REPL needs incremental lowering, which `ir_func` per function supports but
  nobody has exercised. **Gaps I did not verify:** whether the IR lowers
  every construct the C target does (`docs/LLVM.md` says `asm` is not;
  function-value calls have IR fixtures under `back/ir/core/fixture/ops/calls`
  but I did not run them; `docs/LLVM.md` says native backends are C-target
  only, which would be stale or would bind here).
- **Natives:** the IR `call` to a declared native is the dispatch point.
- **Phases:** (B0) read-only IR loader that dumps and round-trips what
  `--emit-llvm` prints, to prove the IR is consumable in-process; (B1) `int`,
  `string`, control flow, calls, `print`; (B2) lists, floats, `word`, the flat
  store, all five trap texts; (B3) function values, exports and `import`;
  (B4) natives; (B5) in-process cases; (B6) a denser encoding and dispatch
  tuning, only if measurement asks for it.

### Option C. A faster C path (tcc-style)

- **Reuses:** all of the current pipeline, unchanged, including the harness.
- **How it works:** keep emitting C, but stop paying for `gcc`: use `lld` (2.4:
  156 to 80 ms), skip the `-fsyntax-only` pass (30 ms) when the compile
  itself reports the same errors, compile the harness and the program in one
  translation unit, and cache object files per function unit.
  A literal `tcc` is not installed here and would be a new C dependency in a
  project leaving C tooling; a `tcc`-speed compiler written in `id` over the
  IR is a native code generator (x86-64 and aarch64 encoders), a far larger
  job than an interpreter.
- **Pros:** zero parity risk; it is the compiled program, so runtime speed is
  native; `lld` alone is a few lines of driver change.
- **Cons:** has a hard floor of about 60-80 ms for one compile-and-link, and
  more like 120-160 ms for harness plus program, so U2 is met only for very
  small programs, never for U3. Does not give a REPL. Does not remove the
  shell hashing (R3). `cc` stays a dependency.
- **Phases:** (C1) `lld` in the `cc` invocation; (C2) drop the syntax-only
  pass; (C3) one translation unit for harness and program; (C4) per-unit
  object cache beyond what `.idc-cache/obj` does now.
- **Verdict:** worth doing *as part of* whichever option wins, because compiled
  mode is the production path and its edit-run time matters too. It is not an
  interpreter.

### Option D. WebAssembly with an embedded runtime

- **Reuses:** `idc/bin/idc --target wasm`, which recompiles the C target's C for
  wasm32-wasi. (An earlier draft said this existed only in the deleted `idc.py`;
  that was true when written and is not now.)
- **How it works:** compile to WAT/wasm, run under a host engine. Hosts on
  this machine: `node` (startup about 70 ms by itself) and `wasmtime`, neither
  written in `id`.
- **Pros:** sandboxing and memory traps come from the engine; the store is
  linear memory, already its natural home (`SPEC.md` S6).
- **Cons:** the interpreter would not be written in `id` (violates R3),
  depends on a non-`id` engine, needs a port of the wasm target out of Python
  first, native backends are unreachable (they are C), and engine startup
  already consumes a third of the 200 ms budget. Writing the wasm *engine* in
  `id` is option B with a different instruction set and more work.
- **Verdict:** not recommended for this goal; it is the right answer to a
  different question (running `id` in a browser, as `id_webdemo` does).

### 3.1 Comparison

| | A tree-walk | B IR interpreter | C faster `cc` | D wasm |
| --- | --- | --- | --- | --- |
| new semantic walk of the AST | yes (third) | no | no | no |
| parity machinery reused | none | lowering + conform | everything | wasm target (Python) |
| meets U2 (under 200 ms) | yes, expected | yes, expected | only tiny programs | no (host startup) |
| removes C compile from cases | yes | yes | no | no |
| REPL | natural | needs incremental lowering | no | no |
| written in `id` | yes | yes | driver only | no |
| run-time speed | slowest | middle, improvable | native | near native |
| risk | parity drift | IR coverage gaps | low | high |

"Expected" means reasoned from section 2 (front end 7 ms, no C compile), not
measured; milestone M1 below turns it into a measurement.

---

## 4. Language rules in interpreted mode

The compiler's rules exist for reasons that an interpreter changes. None of
the following is decided here.

Mechanical fact first: rules enforced by `mid` (action limit, nesting, name
types, uniqueness, exports, nested-call ban) are properties of the source, not
of the target. **An interpreter that consumes `mid`'s output cannot skip them
without a flag**, and the cost of running them is already small (section 2.5,
1). So the question for each rule is whether interpreted mode *should* waive
it, not whether it can.

### F1. Two cases per function, and "cases run before output"

- **Keep, run in-process (the plan of record in `docs/TESTS.md`).** Cases run
  before `main`, cached by function-plus-callees content so an edit re-runs
  only what it touched. Preserves "there is no way to get output from a
  program whose cases fail". Cost: every script carries two cases per helper
  and per `main`; a ten-line script becomes thirty.
- **Keep for libraries and projects, waive for a single-file script.** A script
  that is one file with a `#!` line runs without cases, or with cases run only
  on request. Cost: two rules, and a script that grows into a project changes
  behaviour when it gains a directory.
- **Make cases lazy: run on `--test`, not on run.** Fastest edit-run. Cost: the
  guarantee that motivated `docs/TESTS.md` ("a regression is a compile
  error") becomes opt-in, which is the thing that document argues against.

### F2. The 3-entries-per-directory layout

A script is one file, so the layout rule has nothing to say about U1. It
applies to U3 (a project tree), where it runs `idlayout` in about 13 ms. Forks:
apply it to interpreted trees unchanged (one language, no surprises); or waive
it in a scratch mode (faster to sketch, but a tree that runs interpreted and
fails `idc` later is a trap, and the error then arrives far from the edit).

### F3. Three functions per file, the action limit, the nested-call ban

These shape every line of a script: `print(greet(square(4)))` is rejected, and
a `main` with a fourth statement needs a `chain`. Both hit my first draft of
the measurement program. For a Python-style script this is the largest
ergonomic cost, larger than the two-case rule. Forks: keep (scripts look like
`id`, everything is portable to compiled mode); waive in script mode only
(comfortable scripts, but code does not move between modes without a rewrite,
so "interpreted" becomes a second dialect, which is what `SPEC.md` exists to
prevent); or make the limits advisory in interpreted mode and enforced at
`idc` time (one dialect, deferred errors).

### F4. Function-logic uniqueness

Applied across a whole unit, it is cheap to keep for a script and irrelevant
to U1. In a REPL it forbids defining a second function with the same logic,
which is hostile to experimentation; see section 5.

### F5. One type per name

Kept by default because it is what lets `mid` type-check without scopes. See
section 5 for how it bites a REPL.

### F6. User `backend.id` natives in interpreted mode

Fall back to compiled mode; rebuild the interpreter host with the backend
linked (a compile, so slow but only for that project); or `dlopen` (section
3). Unresolved at the level of "do we promise it".

### F7. The 30 s case limit as fuel or as wall-clock

Fuel is deterministic and needs no timer native; wall-clock matches
`docs/TESTS.md` literally. A `timeout N` clause in a case would mean
"N seconds" in one and "N times some instruction count" in the other.

### F8. Shebang syntax

Accept `#!` on line 1 only, in the lexer, as a comment (then `#word` markers
injected by the driver are not confused with it, since it is a different
character after `#`). Or a header convention that is not a comment. Only the
first is a one-line lexer change; confirm by reading `scan_hashop` in
`compiler/lex/chars/dispatch/more/number_or_op.id`.

---

## 5. REPL semantics

Feasibility: **plausible on option B, natural on A, absent on C and D.** The
difficulty is not evaluation but that `id` has no top-level statements: all
code lives in functions with two cases each, and all state lives in `export`s
initialised by the function that declares them.

**What a session is.** One growing compilation unit. That is the only
reading consistent with "a name has one type across a tree" (`docs/PROJECT.md`
pitfall 6), and it is the same rule that makes a script's `int r` in one helper
constrain `string r` in another.

**Consequences, each a fork for the user:**

1. **A name has one type for the session.** Typing `x` as an `int`, then
   `string x`, is an error in a file and is an error here. In a file that is
   found at build; in a REPL one mistyped line poisons the name until the
   session ends. Options: keep the rule (correct, unforgiving); add a
   `:forget NAME` that removes the name and everything typed against it
   (forgiving, requires reverse dependencies the node store does not keep
   today); or start each session from a clean unit per top-level entry and
   accept that nothing persists (defeats a REPL).
2. **An expression line.** `1 + 2` is not a function, and `print(len(xs))` is
   a rejected nested call. The session must wrap input into a synthetic
   function `_repl_N` that lowers and evaluates. Does a synthetic function owe
   two cases? Presumably not (waived for `_repl_*`), but then the rule has an
   exception whose boundary is a naming convention.
3. **State is an export, and an export is a statement.** `docs/PROJECT.md`
   pitfall 4: an export "does not exist until that function has run". So a
   REPL variable is an export declared by a function the session writes, and
   its first read before that function ran is an error ("read of an
   uninitialised export", `SPEC.md` section 8). My reading of "single
   ownership" is that each export has one declaring function, which is the
   only place that initialises it; I did not find this worded as a rule in
   `SPEC.md` or `PROJECT.md`, so **this is unverified**: if it means something
   stronger (for example that only the declarer may write it), a REPL
   variable can be mutated only by re-running its declaring function. Options:
   model `x = 5` as redefining the declaring function (clean, but re-runs its
   side effects); or allow the session to hold a mutable top-level binding
   that has no `id` equivalent (convenient, but a REPL-only construct that
   cannot be pasted into a file).
4. **Redefinition.** Redefining `f` in a session must either re-check every
   function that calls `f` (correct, needs reverse call edges) or be refused
   when the signature changes. The duplicate-logic rule turns redefinition
   into an accident: redefining `f` to equal `g` is an error in a file and
   must be here. Options: enforce (consistent), or exempt the session (a
   REPL that accepts what a build rejects).
5. **Cases.** Every session function technically owes two. Options: waive in
   the REPL and require them at `:save` (the file a session writes out must
   build); or demand them inline (hostile to a REPL).
6. **Memory.** The flat store and lists are per process; a long session
   grows the arena until exit, same as any `id` program (`SPEC.md` section 6:
   freeing is decided but not built). Not a REPL-specific problem, but REPLs
   are long-lived.

**Recommendation for the REPL.** Defer it. It depends on decisions F1, F3 and
the five above, none of which affect a script, and scripts (U1) and edit-run
(U2) are the stated goal. Build the evaluator so an entry point accepts "lower
one more function into the existing unit" (option B already has `ir_func` per
function), and decide the REPL's semantics after the script mode has users.

---

## 6. Recommended path

**Recommendation** (not a decision; F1-F8 are the user's):

1. **Option B, interpret the IR at `-O0`, written in `id`**, as a separate
   binary (working name `idrun`) with its own `id`-written driver. Reasons:
   it adds no third semantic walk (option A's cost), it inherits the parity
   gate that already exists, it needs no `cc` and no shell, it is the only
   option that reaches U2 and U3 and leaves U4 open, and what it needs from
   the language (function values for dispatch) has landed.
2. **Independently and first, do option C1 and C2** (`lld`, drop the extra
   syntax pass) in `idc`, because compiled mode stays the production path,
   the gain is measured (section 2.4), and it is unrelated to the interpreter
   work. One concern per change, so it is its own change.
3. **Replace the shell cache-key loop with `id`** as part of the driver work in
   (1), since it is 240 of the 440 ms warm build (section 2.5).
4. **Drop BACKENDS.md step 4 (Python)** in favour of this plan, and fix the
   DISPATCH.md drift, once the user has decided.

### Milestone M1 (small and measurable)

Build `idrun`, which runs **one single-file program with no natives and no
idstd, cases skipped**, by: parse, `mid`, lower to IR at `-O0`, interpret.
Deliberately out of scope: cases, idstd, natives, projects, REPL, `#!`.

Acceptance, all measurable:

- **A.** On `scratch/hello/hello.id`, `idrun hello.id a` prints `hi 16` and
  exits 16, byte-identical to the compiled `h1`.
- **B.** The conform cases from `idc/tests/conform/` that need no native
  backend and no `asm`, run through `idrun`, match the C target's stdout,
  stderr and exit code. Report `passed/total`, and list each excluded case
  with its reason. (The suite's size is to be queried at the time, not
  recorded.)
- **C.** Wall time of `idrun hello.id`, cold process, three runs, median,
  against the 0.43 s and 0.13 s of section 2.1. The target for M1 is
  **under 50 ms**; the stretch goal is the U2 figure of 200 ms for a program
  of the `trials/kv` size without idstd.
- **D.** A dispatch microbenchmark: a loop of 10 million integer additions
  through the IR interpreter, reported next to the same loop compiled. This
  settles the `if`-chain versus handler-table question of section 3 with
  data before the interpreter's shape is fixed.

Then: M2 natives and idstd (linked-in host); M3 in-process cases and the
case cache, which is where F1 must be settled; M4 project trees and the
front-end image (a serialised prechecked idstd, so a run pays nothing for a
library it has already checked, as `run_std_precheck` does today); M5
`#!` scripts; M6 the REPL decisions.

### Unverified in this document

- Every "expected to be fast" claim: nothing was prototyped. The only numbers
  are in section 2, and those measure today's pipeline.
- That the IR lowers everything the C target does (section 3, option B).
- The reading of "single ownership" of exports (section 5, item 3).
- Why a warm `trials/kv` build re-runs its harness (section 2.3).
- A from-scratch compiler bootstrap time.
- That `#!` on line 1 is a one-line lexer change (F8).

### Reproducing section 2

```sh
export IDSTD_HOME=<WS>/../idstd
cd <WS>
time idc/bin/idc hello.id -o hello                    # warm
time IDC_NO_CACHE=1 idc/bin/idc hello.id --no-std -o hello   # cold, no std
PS4='+T${EPOCHREALTIME} ' bash -x idc/bin/idc hello.id -o hello 2> trace.txt
```

Stage boundaries are the `lex_rc=`, `parse_rc=`, `hbuild_rc=`, `hrc=`,
`syntax_rc=` and `cc_rc=` lines in the trace; the hash loop is the run of
`sha256sum` lines between the front-end and harness steps.

---

## 7. Milestone 1: `idrun`

`idc/tools/idrun` is a project tree in `id`, built with `idc/bin/idc
idc/tools/idrun -o OUT`. Every rule applies to its own source: layout, three
functions per file, uniqueness, two cases per function, cases run before the
binary is produced. `idrun [--allow-untested] [--ll] PATH [ARGS...]` runs a
`.id` file or a project directory without a C compiler.

**How it is put together.**

- The front end is the compiler's own `idlex` and `idparse`, run by a shell
  line `idrun` assembles (`idparse --target llvm --opt 0`). `idrun` finds them
  in `$IDC_CACHE_DIR`, or in `../.idc-cache` beside its own directory.
- The IR crosses as the LLVM text `idparse` already prints, not as a new
  dump: no compiler change, so no bootstrap regeneration. The consequence is
  that the loader depends on that printer's spelling, which
  `idc/tests/conform/` pins.
- The loader (`load/`) lowers that text once into a table of five-cell
  instructions (`conf.id` documents the format). The executor (`exec/`) runs
  it: a frame is a window of a value stack, a call pushes three cells on a
  call stack, and dispatch is a chain of tests in frequency order. The runtime
  helpers the IR calls (lists, strings, traps) are implemented on the host's
  own operators, so a trap has the host's own text and exit status.
- **`idrun` never touches the flat store.** Source text is read as byte cells,
  words are built with `chr`, and the sources are assembled by the shell, so
  the program being run sees `alloc`, `store_size` and the out-of-range trap
  exactly as a compiled one does. idstd's `str_slice`, `str_split` and
  `fs_mktemp` allocate in the store and are not used for that reason.

**Not supported yet** (each is reported before anything runs, not run wrongly):

- natives, and so idstd and every program that calls it (`idrun` reports the
  first undefined callee by name): milestone 2;
- the -O1 form of the IR (`phi`, `select`, `getelementptr`), `asm`, unsigned
  integer comparison predicates (`ult`, `ule`, ...), `fptosi` to a 64-bit type
  (it truncates to 32 bits), and `conf.id` `import` lines;
- running the program's cases: they are required (`--require-tests`) but not
  executed, so "cases run before output" holds only for the compiled path.
  The harness `idparse` emits is C; milestone 3 is where it becomes IR.

**Known differences from a compiled run.** A trap raised by `idrun` itself
(writing a constant list, using an uninitialised export's list) goes to stderr
through `eprint`, which flushes stdout first; the compiled runtime does not,
so the two streams can interleave differently when both go to one pipe. A
function value's address is its function id, and a float in a list is an index
into a side table, not its bit pattern; neither is observable from `id`.
Recursion depth is limited by memory, not by the host stack.

**As a script runner (added after M1; measured in `docs/INTEROP.md`, "id instead
of Python").** A first line starting `#!` is skipped by the
lexer itself (docs/SPEC.md section 9), so `idrun`'s shell line is a plain `cat` and
`idc script.id` accepts the same file; `#!/usr/bin/env idrun` works, and `idrun`
found by bare name looks itself up on `$PATH` to find `.idc-cache` (or use
`$IDC_CACHE_DIR`). F8 is closed. The memory-freeing emitter added
`id_list_free` and `id_list_free_deep` to the IR; before they were treated as
no-ops `idrun` refused every program ("called but not defined"). Arguments,
standard input and the exit status reach `main` as for a compiled program.
