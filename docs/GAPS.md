# What still stands between `idc/bin/idc` and being the only compiler

> **Status, 2026-07-30.** Tiers A, B, D and E are **done**, and Tier C is done
> apart from two cosmetic items (C5, C6). Every fix is locked by a test. §3
> records the performance numbers, §4 what each tier turned into. What remains
> is `--target llvm|wasm`, audio (D6, which needs specifying before building),
> and the string-building rewrite in §3.
>
> The issue list is kept as written, with each fixed item marked, because the
> report it came from is the reason any of it was found.


`../idem/docs` (ARCHITECTURE.md, NAMES.md, and `research/id-language.md`,
`research/id-patterns.md`, `research/gfx-backends.md`) is a field report from
building a real program — a game engine — against this repo. It lists the walls
that project hit. This document is that list, re-verified against the tree as it
stands today, plus the order to knock the walls down.

Every "verified" line below was re-run on this checkout, not copied from the
report. Where the report is now **stale**, it is marked so: the compiler moved
between the report being written and now.

`../id_nativeapp` appears below as evidence from when it lived here. It became
its own repository in `c1d6d62`, and no test in this tree has covered it since,
so it is left in the historical rows and taken out of the coverage claims in
§4 -- a program this suite cannot build is not a program this suite proves.

---

## 0. The premise

`idc/bin/idc` is the primary compiler. `idc/idc.py` is the reference implementation and
the bootstrap: it builds `idlex`/`idparse` once on a cold cache, and that is
meant to be its only remaining job.

It is not, today. `idc/idc.py` is still load-bearing for three things a real program
needs — native backends, most type diagnostics, and build speed — and the report
found all three, independently, as blockers. That is the shape of the work.

**Parity is intact and should stay the gate.** Verified now:

```
idc/bin/idc   idc/compiler/parse --emit-c a.c
idc/idc.py    idc/compiler/parse --emit-c b.c
cmp a.c b.c        →  byte-identical
idc/tests/run.sh       →  74 + 38 + 7 + 15 pass, 0 fail
```

Nothing below may break that.

---

## 1. Issues found

### Tier A — `idc/bin/idc` cannot yet replace `idc/idc.py`

| # | issue | verified how |
| --- | --- | --- |
| **A1** | **No `extern` declarations for link-time-resolved calls, so no program with a native backend builds.** `idc/idc.py` collects unresolved call names and emits `extern int id_<name>();` (idc/idc.py:1195); `idparse` emits nothing, and `idc/bin/idc`'s `cc -fsyntax-only` gate then rejects its own output as an "internal error". | `idc/bin/idc demos/gfxdemo --backend idc/backends/gfx` → `implicit declaration of function 'id_gfx_present'` ×4, then `idc: internal error: the self-hosted compiler emitted C that does not compile`. Same for `../id_nativeapp/id`, `demos/gl3d`. |
| **A2** | **No call-site checking: arity, argument type, return type.** The symbol table (`mid/names/symbols/build/add.id`) stores function name → *return type only*. There are no parameter types anywhere in `mid/`, so `chk_call` can only check `push`. | `h(int a)` called as `h(1,2)` → raw `too many arguments to function 'id_h'` + "internal error". `k(int a)` called as `k("s")` → raw `-Wint-conversion`. `} return int s;` on a `string` → raw `-Wint-conversion`. |
| **A3** | **No "no such function" check.** A typo'd builtin reaches `cc`. The machinery exists — `is_unknown_fn` in `mid/names/symbols/check/access/report/more/callvar/call_var.id` — but it is only wired to the *"'x' is a variable, not a function"* case. | `print(to_flot("1"))` → raw `implicit declaration of function 'id_to_flot'; did you mean 'id_to_int'?` + "internal error". `idc/idc.py` gives the real message with the full builtin list. |
| **A4** | **Duplicate function name is not checked**; it surfaces as C `redefinition`, or — when the two bodies happen to match — as a *misleading* uniqueness error that names the function as a duplicate of itself at its own line. | Two `f(int)` with different bodies → `error: redefinition of 'id_f'` + "internal error". Two with identical bodies → `error: function 'f' has the same signature and logic as 'f' (defined at …:5)` pointing at line 5 for both. |
| **A5** | **Duplicate `export` of one name (R10) is not checked at all — the program compiles silently.** The second `export` re-initialises the same C global. There is also **no test case** for this rule in `idc/tests/invalid/`, in either compiler. | Two functions each `export int e = …` → `idc/bin/idc` exit 0. `idc/idc.py` → `error: 'e' is already an exported global (exported by 'main')`. |
| **A6** | **33× slower than `idc/idc.py`, and superlinear.** The checks scan the global parallel name tables (`find_str((import fnames), …)`) once per node. | Front-end only, `idc/compiler/parse` (213 files / 4798 lines): `idc/bin/idc` **4.66 s** vs `idc/idc.py` **0.139 s**. Synthetic scaling 100 → 400 files: 371 ms → 1811 ms (4.9× for 4× input). Extrapolates to minutes on a 20 kLOC program, with no incremental build. |

**Consequence of A1–A4 together:** of the 38 canonical invalid programs in
`idc/tests/invalid/`, `idc/bin/idc` rejects all 38 (good) but gives the **wrong message
for 15** (bad) — it prints gcc's opinion of generated code and then blames
itself. Re-verified today, exact list:

```
bad_arg_count  bad_arg_type  bitwise_float  charat_bad_index  duplicate_function
input_arity  len_non_string  mem_of_str_wrong_type  modulo_float  negate_string
not_on_string  peek_wrong_arity  push_non_list  return_type_mismatch  to_int_non_string
```

This is the single most damaging item, because `idc/bin/idc` does not merely fail —
it asserts *"this is a bug in the self-hosted compiler; please report it"* about
the user's own type error. `idc/tests/invalid.sh` does not catch it because it runs
`idc/idc.py` only.

### Tier A — what the report listed that is now **fixed** (stale in `../idem/docs`)

| claim in the report | status now |
| --- | --- |
| "the self-hosted lexer still mis-lexes float literals (`0.8` → `0` `.` `8`); treat `float` as unavailable" (`id-patterns.md` §0) | **FIXED.** `float a = 1.5; print(a * 2.0 + 0.25)` builds and runs under `idc/bin/idc`. |
| "no type errors at all — dumps raw `cc` output" (`id-language.md` §0) | **Partly fixed.** Declaration/assignment types, `push` element type, index type, comparison, `void[]`, empty-list literal, condition types are all checked in `id` now, with `file:line: error:` text identical to `idc/idc.py`'s. The gap is now specifically *call sites and unary/builtin operands* (A2, A3). |
| "no structural rules" | **FIXED.** Action limit, nesting, 3-functions-per-file, name-type consistency, export access, logic uniqueness, and syntax errors all live in `mid/` and report every violation rather than stopping at the first. |
| "`idc/bin/idc` transparently falls back to `idc/idc.py`" (README, and the report quoting it) | **Removed** (commit `edb5baf`). The README still describes the fallback and the float gap — see B5. |

### Tier B — driver (`idc/bin/idc`) disagrees with `idc/idc.py`

| # | issue | verified how |
| --- | --- | --- |
| **B1** | **Hidden directories count toward the 3-entries rule.** `idc/bin/idc:127-137` walks `find … -type d` and counts every subdirectory; `idc/idc.py` skips dotted ones. A project with 3 real entries plus a `.git` is rejected by one compiler and accepted by the other. | 3 entries + `.git/` → `idc/bin/idc`: `has 4 (.id files and subdirectories)`. `idc/idc.py`: builds. |
| **B2** | **An absolute path in `conf.id` is rejected, with a false message.** `idc/bin/idc:162` builds `"$PATH_ARG/$dep"` unconditionally, so an absolute dep becomes a nonsense path and is reported as *"is not a directory"* — about a path that is a directory. | `import "/abs/path/lib"` → `idc/bin/idc: import "/abs/…/lib" is not a directory`; `idc/idc.py` builds and runs it. |
| **B3** | `--target llvm` / `--target wasm` are `idc/idc.py`-only. `idc/bin/idc` exits 2 with a pointer to `idc/idc.py`. Honest, but it means `idc/idc.py` cannot be retired. Note `docs/BACKENDS.md` already specifies the multi-target shape for the self-hosted back end. | `idc/bin/idc x.id --target llvm` → exit 2. |
| **B4** | **`--triple` is not plumbed through**, although `idparse` implements it (`back/drive/run/output_mode.id`, `arg_triple`). So a multi-platform `asm` program cannot be cross-targeted through the driver. | `idc/bin/idc` rejects any unknown option at `idc/bin/idc:65`. |
| **B5** | **idc/README.md is stale on exactly the points a new user reads first** — it documents the removed `idc/idc.py` fallback (lines 52-67, 233-238) and states float literals are unsupported. Both are wrong now. The report's §0 recommendation ("build with `idc/idc.py`") was derived from it. | `grep -n "falls back" idc/README.md` → line 61. |

### Tier C — language / runtime hazards (both compilers)

These are not `idc/bin/idc` bugs; they are `id`'s, and the report's own §"Silent
wrong code" list. Ordered by how much silent damage each does.

| # | issue | verified how |
| --- | --- | --- |
| **C1** ✅ | **`(import xs)[i] = v;` compiles to a discarded comparison and does nothing.** Index-assignment is only recognised when the target starts with a plain identifier, so this — the most natural way to write through a global — is silently dead code. Same for `f()[i] = v`. The whole `lset` idiom exists to work around it. | `bump() { (import st)[0] = 7; }` then reading `(import st)[0]` → prints `0`, no diagnostic, exit 0. |
| **C2** ✅ | **`int` division by zero is a SIGFPE core dump with no message.** `word` division by zero is a clean `id: division by zero`. The two paths disagree because `/` and `%` on `word` route through `id_sdiv`/`id_smod` and on `int` are raw C. | `10 / z` with `z == 0` → `Floating point exception (core dumped)`, exit 136. |
| **C3** ✅ | **Reading an exported global before its declaring function has run segfaults**, with nothing at compile time. Because init chains are capped at 3 actions per block, dropping one link in a chain is easy and silent — and `demos/fpsmaze` has done exactly that (E3). | `print(len((import tbl)))` before `mk()` runs → `Segmentation fault (core dumped)`, exit 139. |
| **C4** ✅ | **`/* */` is not a comment** and produces a cascade of nonsense diagnostics rather than one saying so. | `/* hello */` → `error: undefined variable '/'`, `error: undefined variable 'hello'`, `error: undefined variable '/'`. |
| **C5** | Exported names become **unprefixed C globals**, so `export int time` / `stdout` / `index` collide with libc and fail in generated code. | report `id-language.md` §11; mechanism confirmed in `idc/idc.py` codegen. |
| **C6** | `if(some_string)` compiles and tests the pointer — always true. | report §2; `id` truthiness accepts any non-`void`. |
| **C7** | String `+` in a loop is quadratic in **time and retained memory** (the arena is only freed at exit): 1920 chars × 1000 frames = 667 ms / 1.8 GB, versus 1 ms / 5.8 MB through `poke8` + `str_of_mem`. Every text-producing program has to know this. | report §3; `demos/idview` records offsets instead of substrings for this reason. |

### Tier D — the native backend seam

From `research/gfx-backends.md`, built and run against real X. These bound what
any graphics program can do, and the engine design in `../idem` is shaped around
them.

| # | issue | note |
| --- | --- | --- |
| **D1** ✅ | **No key-release events, and no arrow keys, F-keys, or bare modifiers.** Both backends handle only `KeyPress` and take `XLookupString`'s first byte. So "is this key held?" is unanswerable; games bind WASD and synthesise hold from X auto-repeat. | ~10 lines per backend: `XLookupKeysym` into a code range above 255, plus `KeyReleaseMask`. |
| **D2** ✅ | **No mouse, in either backend.** Not unreported — never requested: the `XSelectInput` masks contain no `ButtonPress` or `PointerMotion`. | |
| **D3** ✅ | **`idc/backends/gfx` cannot resize or scale.** No `StructureNotifyMask`, so `ConfigureNotify` never arrives; `XPutImage` blits 1:1; there is no `gfx_width()`/`gfx_height()`. Under a tiling WM the image sits in the top-left corner with black margins. `idc/backends/gl` already does all of this correctly. | |
| **D4** ✅ | **The two backends cannot coexist in one binary** — both define `id_gfx_open`/`poll`/`close`. Renaming GL's three window symbols fixes it (verified in the report, two recipes). | |
| **D5** ✅ | **`idc/backends/gl` has no `glReadPixels`**, so there is no headless verification path for GPU output — the software path has PPM dumps, the GL path has nothing. | |
| **D6** | **No audio backend anywhere in the repo.** Would be a new `backend.json` (`id_snd_open`, `id_snd_queue(int[])`). | |

### Tier E — bugs the report found *in this repo's demos*

Each is live in the tree today; each is also the canonical example a reader
copies from.

| # | issue | verified how |
| --- | --- | --- |
| **E1** ✅ | **`demos/gfxdemo` ignores `gfx_open`'s return value and hangs forever with no display.** `main.id:12` assigns `int ok` and never uses it; `loop()` calls `spin(1, 0)` with a hard-coded live flag. With no X server `gfx_poll` returns `-1` forever. | `main.id:12`, `loop/loop.id`. Report measured `DISPLAY= GFX_MAX_FRAMES=5 timeout 5 ./gfxdemo` → rc 124. |
| **E2** ✅ | **`demos/gfxdemo/loop/anim/grid.id:2` states the runtime "drops any out-of-range store, so no per-pixel bounds check is needed". That is false** — an out-of-range list store is a fatal abort. Its box merely happens to stay in bounds. Anyone who trusts that comment writes a rasteriser that dies on the first off-screen pixel. | `grid.id:2`; `idc/tests/runtime_invalid/` has `store_oob` proving the abort. |
| **E3** ✅ | **`demos/fpsmaze/game/sim/gfx/scene/init.id` defines `scene_init()`, which exports four lists, and nothing calls it** — a live instance of C3. Every `(import wall_verts)` site reads `NULL`. | `grep -rn scene_init demos/fpsmaze` returns only the definition. |

---

### Tier A and B — all fixed

| # | what was done | the test that keeps it done |
| --- | --- | --- |
| **A1** | `idparse` gained a call-resolution pass and an `--extern-ok` flag; under it an unresolved call is collected and emitted as `extern int id_<name>();` in idc/idc.py's block, in idc/idc.py's position and order. `idc/bin/idc` passes the flag exactly when a backend is attached (`--backend` or an `conf.id` dependency). `demos/gfxdemo`, `demos/gl3d`, `demos/gl3dgame`, `demos/fpsmaze` and `../id_nativeapp/id` now build with `idc/bin/idc`, byte-identical to `idc/idc.py`. | `idc/tests/self_host_build.sh`: backend emit-c byte parity for `demos/gfxdemo`, asserting the extern block is present |
| **A2** | The symbol table carries a node id per function (`fnodes`), so a call site can reach the callee's parameter list. Call arity, argument types and the return-clause type are checked in `id`, with idc/idc.py's wording. The builtins got the same treatment — arity and per-position argument types for all thirty, driven by three descriptions rather than thirty hand-written branches. | `idc/tests/invalid.sh`, now run against **both** compilers |
| **A3** | An unresolved call with no backend is `no such function 'X'; available builtins: …`. The builtin list is one literal, split at startup, and answers both "is this a builtin" and "what are they all", so the two cannot disagree. | `idc/tests/invalid/no_such_function.id` (new) |
| **A4** | Duplicate function names are checked before the logic-uniqueness scan, so `duplicate_function` reports `already defined at FILE:LINE` instead of naming a function as a duplicate of itself. | `idc/tests/invalid/duplicate_function.id` |
| **A5** | Duplicate `export` of one name is rejected. | `idc/tests/invalid/duplicate_export.id` (new — neither compiler had a case) |
| **A6** | See §3. | timings recorded below |
| **B1** | Hidden directories are pruned from the project walk, matching `idc/idc.py`: not counted toward the 3-entry limit, and nothing under them is compiled. | `idc/tests/self_host_build.sh` |
| **B2** | An absolute path in `conf.id` resolves; a genuinely missing dependency says "no such directory" rather than "is not a directory". | `idc/tests/self_host_build.sh` |
| **B4** | `--triple` reaches `idparse`, so `asm` overloads can be selected through the command users actually run. | `idc/tests/self_host_build.sh` |
| **B5** | README rewritten: no fallback, no float gap, and one honest statement of what `idc/idc.py` alone still does. | — |

**The count that mattered:** of the 38 canonical invalid programs, `idc/bin/idc`
gave the wrong message for 15. It now gives the expected message for all 40
(two cases were added), and so does `idc/idc.py` — `idc/tests/invalid.sh` runs both and
requires both, which is the change that keeps this from happening again.

## 2. The plan

Ordered so that each phase ends with `idc/bin/idc` strictly more capable and the
parity gate still green. Phases 1-3 are the ones that matter; 4-7 are cleanup
and can be reordered freely.

### Phase 1 — make `idc/bin/idc` build everything `idc/idc.py` builds  *(unblocks A1, A3)*

The extern gap and the unknown-function gap are **one mechanism**, exactly as in
`idc/idc.py`: a call whose name resolves to nothing is an error when no backend is
attached, and an `extern` plus a warning when one is.

1. **Teach the symbol table parameter types.** Add `fparams` (an `int[][]` of
   node ids, or a `string[]` of comma-joined type spellings) alongside
   `fnames`/`frets` in `front/tree/init/init_sym.id`, filled by
   `add_func` in `mid/names/symbols/build/add.id`. Everything in Phase 2 depends on
   this, so it comes first.
2. **Add a call-resolution pass** in `mid/`: for every `call` node, resolve the
   name against `fnames`, `builtin_type`, and the asm symbols. Unresolved →
   `no such function 'X'; did you mean the builtin 'Y'? available builtins: …`,
   reusing `is_unknown_fn` and the existing "did you mean" wording so the text
   matches `idc/idc.py` byte for byte.
3. **Add `--extern-ok` to `idparse`.** `arg_triple`'s neighbour in
   `back/drive/run/` already parses argv, so this is a second flag.
   Under it, an unresolved call is a *warning*, its name is collected, and the
   emitter prints the `/* functions not defined in any input file … */` block
   with `extern int id_<name>();` for each — matching `idc/idc.py:1190-1196`
   including the comment text, since parity is byte-level.
4. **`idc/bin/idc` passes `--extern-ok`** whenever `ALL_BACKENDS` is non-empty
   (`idc/bin/idc:292`), i.e. exactly when `--backend` or an `conf.id` backend
   dependency is in play.

**Validation:** `idc/bin/idc demos/gfxdemo --backend idc/backends/gfx` builds and runs;
same for `../id_nativeapp/id`, `demos/gl3d`, `demos/gl3dgame` (via
`idc/tools/devshell.sh`). `idc/bin/idc x.id` with a typo'd builtin gives `idc/idc.py`'s
message. `idc/tools/parity.sh` still MATCH on every demo. Add
`idc/tests/self_host_build.sh` cases for a backend build and for the typo message.

### Phase 2 — close the 15 wrong diagnostics  *(A2, A4, A5)*

With `fparams` in place these are all assertions in the existing `tc_*` walk.

1. **Call sites**: arity (`bad_arg_count`), argument types (`bad_arg_type`),
   return-expression type (`return_type_mismatch`).
2. **Builtin arity and operand types**: `input_arity`, `peek_wrong_arity`,
   `len_non_string`, `to_int_non_string`, `charat_bad_index`,
   `mem_of_str_wrong_type`, `push_non_list`.
3. **Unary and binary operands**: `negate_string`, `not_on_string`,
   `bitwise_float`, `modulo_float`.
4. **Duplicate function name** — a distinct check that runs *before* the
   uniqueness rule, so `duplicate_function` reports `already defined at …` and
   the misleading self-referencing uniqueness message goes away.
5. **Duplicate export (R10)** — one scan of the export table.

**Validation — this is the important half.** `idc/tests/invalid.sh` currently runs
`idc/idc.py` only, which is exactly why 15 broken messages went unnoticed. Change it
to run **both** compilers over all 38 cases and require the `// EXPECT:`
substring from each. Then add the two missing cases the suite has never had:
`duplicate_export.id` and `no_such_function.id`. After this phase the
`idc/bin/idc`-vs-expected count must be 40/40, and `compiler_bug()` must be
unreachable for any well-formed user error.

### Phase 3 — performance  *(A6)*

The cost is `find_str` doing a linear scan of a global `string[]` for every name
occurrence, inside walks that are themselves over every node — quadratic in
program size.

1. Add a bucketed index: a cheap string hash into `int[][]` buckets of row
   indices, built once after `build_syms`, queried by `find_str`'s callers.
   `id` has `&`, `<<`, `%` and `int[][]`, so this is ordinary code — no language
   change needed.
2. Apply it to the four hot tables: `fnames`, `vnames`, `dvname`, and the export
   table.
3. Re-measure at 100 / 200 / 400 / 800 files and on `idc/compiler/parse`.

**Target:** linear scaling, and `idc/compiler/parse` front-end under 1 s
(from 4.66 s). Getting inside 3× of `idc/idc.py` makes `idc/bin/idc` a comfortable
default; the current 33× does not. Record the numbers in the README so a
regression is a number, not a feeling.

### Phase 4 — driver parity  *(B1, B2, B4, B5)*

Small, independent, all in `idc/bin/idc` and `idc/README.md`.

1. Skip hidden directories in the 3-entry walk (`idc/bin/idc:127-137`), matching
   `idc/idc.py`.
2. Resolve `conf.id` deps as absolute-if-absolute, relative-otherwise; and
   when a dep really is missing, say *"no such directory"*, not
   *"is not a directory"*.
3. Accept `--triple T` and forward it to `idparse`.
4. **Rewrite README §"Self-hosting" and §"`idc/bin/idc`: the self-hosted driver"**
   to describe what is true now: no fallback, floats supported, and a single
   honest table of what `idc/idc.py` alone still does (which by then is
   `--target llvm|wasm` — see `docs/BACKENDS.md` for that work).

### Phase 5 — close the silent-wrong-code holes  *(C1-C4)*

Every one of these is a compile-time diagnostic that does not exist yet. They
are ordered by damage, and the first is worth more than the rest combined.

1. **Reject `(import xs)[i] = v;` and `f()[i] = v;`** — a statement whose whole
   expression is a comparison against an index target is never intentional.
   Error: *"an imported list cannot be index-assigned directly; pass it to a
   helper that takes the list as a parameter (`lset(xs, i, v)`)"*. This turns
   the language's worst trap into a message that names the fix.
2. **Guard `int` division by zero** the way `word` already is — route `int` `/`
   and `%` through a checked helper, or at minimum reject a literal `0` divisor
   at compile time. A core dump with no message is the worst failure mode in the
   runtime.
3. **Diagnose `/* */`** with one message ("block comments are not supported; use
   `//`") instead of a cascade of "undefined variable '/'".
4. **Warn when an exporting function is unreachable from `main`** — this is C3's
   only compile-time symptom, and it would have caught E3.
5. Warn on `if(<string>)` (C6), and on an exported name that collides with a
   known libc global (C5).

Each needs a `idc/tests/invalid/` case and, for the runtime ones, a
`idc/tests/runtime_invalid/` case.

### Phase 6 — the backend seam  *(D1-D5)*

Do this only when something needs it; `../idem` needs D1 and D3 for a playable
game, and D5 to verify GPU output in CI. The report costs each at ~10 lines of
C.

1. `D1` arrows + key-release: `XLookupKeysym` into codes above 255, add
   `KeyReleaseMask`, emit release as a negated code. Both backends.
2. `D3` gfx resize: `StructureNotifyMask`, reallocate `g_px`/`XImage` on
   `ConfigureNotify`, export `gfx_width()`/`gfx_height()` so `id` can re-init
   its framebuffer.
3. `D4` rename `idc/backends/gl`'s three window entry points to `glwin_*` so both
   backends link into one binary. (Do **not** use
   `-Wl,--allow-multiple-definition` — it links and then silently binds one
   subsystem to the other's uninitialised window.)
4. `D5` add `gl_read_pixels(int[] fb)`.
5. `D2` mouse and `D6` audio are new surface area; specify them before building.

### Phase 7 — fix the demos  *(E1-E3)* — **done**

Cheap, and they are what people copy.

1. **E1 was six demos, not one.** `gfxdemo`, `fpsmaze`, `gl3d`, `gl3dgame`,
   `flyover` and `galaxy` all assigned `int ok = gfx_open(...)` and then
   started the frame loop with a hard-coded `1`; every one of them ran until
   killed under `DISPLAY=`. All six now thread `ok` into the loop's live flag
   and exit 0.
2. **E2**: `pset` in `demos/gfxdemo` now clips, and both comments claiming the
   runtime drops out-of-range stores are gone. Verified the fix is
   load-bearing: with the clip removed and the box drawn past the edge, the
   program aborts with `id: index 64000 out of bounds (len 64000)`.
3. **E3**: `game_init()` now reaches `scene_init()` through a new `init_world()`
   link. Before, `gl_draw_tris` was being handed NULL and returning 0 without
   complaint -- fpsmaze rendered its maze with no walls and no targets, and
   nothing anywhere said so.

---

### Tiers C and D — what they turned into

| # | what was done | the test |
| --- | --- | --- |
| **C1** | A statement whose whole expression is an equality is rejected. `=` and `==` are one operator by the time either parser is done, so both spellings are caught -- which is the right net anyway: `x == 2;` as a statement is as pointless as the assignment it is usually a typo for. An index target gets told to use `lset`. | `idc/tests/invalid/discarded_comparison.id` |
| **C2** | `int` `/` and `%` go through checked helpers, exactly as `word` already did. gcc folds the check away whenever the divisor is a nonzero constant, and `-7/2` is still `-3`. | `idc/tests/runtime_invalid/int_div_zero.id`, `int_mod_zero.id` |
| **C3** | A **reachable** `(import x)` whose exporting function is unreachable from `main` is rejected. Reported at the read, not at the dead function: a file that declares an export and never wires it up is unfinished or illustrative -- `demos/hello` is deliberately the latter -- while a reachable read of an uninitialised global is neither. Verified against the bug it was designed for: with `demos/fpsmaze`'s fix reverted, both compilers catch it. | `idc/tests/invalid/dead_export.id` |
| **C4** | Both lexers recognise `/*` and say "block comments are not supported; use // for a line comment". The `id` lexer consumes the comment and emits one token, so one comment is one diagnostic instead of a page of complaints about the words inside it. | `idc/tests/invalid/block_comment.id` |
| **+** | Bonus, found on the way: an operator where an expression belongs used to be turned into a *variable named after the punctuation* and reported by a later pass as `undefined variable '/'`. Both compilers now say `unexpected token '/'`. | `idc/tests/invalid/unexpected_operator.id` |
| **+** | Bonus, found by the input probe: `idc/idc.py` types a link-time call `int`, the self-hosted compiler left it unknown -- so `"" + gfx_width()` emitted a raw int where a `char*` belonged. A real parity divergence, only reachable once backends built at all. | the backend parity checks |
| **D1** | Arrow keys, F1–F12, Home/End/PgUp/PgDn/Insert/Delete and bare modifiers now reach `id`, as codes 256–511; **key release** arrives as the same code plus `GFX_RELEASED`. Codes 0–255 are unchanged, so nothing written against the old contract moved. Auto-repeat is filtered, so "is this key held" is answerable for the first time. Both backends. | verified by injecting real X events: five press/release pairs, all correct |
| **D2** | Pointer state: `gfx_mouse_x/y/buttons` (`glwin_mouse_*` on the GL side). State rather than events, because a click is an edge and `id` sees an edge by comparing frames. | verified with a real click at a known position |
| **D3** | `idc/backends/gfx` follows `ConfigureNotify`, reallocates the surface, and exposes `gfx_width()`/`gfx_height()`. `id` had **no way** to learn the real window size before. | verified: a window resized from 320×200 to 922×2020 and `id` saw it |
| **D4** | The GL backend's window entry points are `glwin_open/poll/close`. They used to be `gfx_*` -- the same symbols the software backend exports -- so the two could not be linked together at all. | `idc/tests/backends.sh` links both into one binary and drives two windows |
| **D5** | `gl_read_pixels(fb)` reads the rendered frame back as `0xRRGGBB`, top row first -- the same layout `gfx_present` consumes, so one PPM dumper serves both paths. Reads `GL_BACK` before the swap: reading `GL_FRONT` after it looks more natural and returns black under a compositor. | `idc/tests/backends.sh` renders a known colour and reads it back from `id` |
| **E1** | Six demos, not one: `gfxdemo`, `fpsmaze`, `gl3d`, `gl3dgame`, `flyover`, `galaxy` all ignored `gfx_open`'s result and ran until killed under `DISPLAY=`. | `idc/tests/backends.sh` runs each with no display |

Still open in Tier C, both cosmetic: **C5** (an exported name colliding with a
libc global, which fails as a C error about generated code) and **C6**
(`if(some_string)` testing a pointer that is always true).

**A note on `idc/idc.py`.** Four of these -- C1, C2, C3, C4 -- are new diagnostics,
and C2 changes the runtime. Every one was made in *both* compilers, because a
check only the reference has is a check the primary compiler's users do not
get, and that is the exact hole `idc/tests/invalid.sh` was changed to close. The
runtime lives in `idc/idc.py` as one string that both compilers emit verbatim
(`idc/tools/gen_runtime_id.py` regenerates the `id`-side copy), so parity proves
they agree rather than requiring them to be kept in step by hand.

## 3. Performance: what was actually slow

A6 said "33× slower than `idc/idc.py`, and superlinear". Both halves were true, and
neither had the cause the guess assumed. Measured, `--emit-c`, best of three:

| | before | after |
| --- | --- | --- |
| `idc/compiler/parse` (213 files, 4798 lines) | 4661 ms | **664 ms** |
| balanced tree, 100 files | 352 ms | **63 ms** |
| balanced tree, 800 files | — | **215 ms** (`idc/idc.py`: 98 ms) |
| ratio to `idc/idc.py` on the self-host build | 33× | **5.1×** |
| ratio to `idc/idc.py` at 800 files | — | **2.2×** |

Four things, found by profiling rather than by reading:

1. **`id_charat` called `strlen` on every character access** — so walking a
   string was O(n²), and walking a string with `charat` is how every `id`
   program reads text (there is no `substr` and no file I/O). Lexing 128 KB
   took 378 ms; with the length of the last string remembered it takes 12 ms.
   This is a **runtime** fix, in `idc/idc.py`'s `RUNTIME` with the `id`-side copy
   regenerated by `idc/tools/gen_runtime_id.py`, so both compilers emit it and
   parity proves they agree. **Every `id` program that reads text gets this**,
   not just the compiler. The memo is keyed on the pointer, which is sound
   because `id` strings are immutable and nothing is freed before exit —
   except `id_realloc`, which clears it.
2. **The driver ran four processes per directory** to check the 3-entry rule —
   800 forks and 4.4 s on a 200-directory tree, more than twice the compiler.
   It is now one `find` and one `awk`.
3. **`emit_sources` forked a `cat` per file.** One `awk` instead.
4. **`find_str` was a full scan with no early exit** (`id` has no `break`, so
   even a hit walks the whole list). `lookup_var` alone made 568 000 of them —
   867 million comparisons, 64% of the run. `vnames`, `fnames` and the
   declaration registry are now hash-indexed; that inner loop dropped from 867
   M iterations to 4.8 M.

What is left is string building: 3.2 M `id_concat` calls and a 337 MB peak
while compiling this compiler, because `id` strings are immutable, every
intermediate is retained until exit, and the emitter builds each line of C with
`+`. The language's own research notes say never to do this in a loop — the fix
is `poke8` + `str_of_mem`, and it is a rewrite of both the lexer's token
accumulation and the emitter's line building, with byte-parity as the gate.
That is the next real performance step, and it is its own piece of work.

## 4. What "done" looks like

`idc/bin/idc` is the only compiler a user ever runs when all of these hold:

- ✅ Every program in `demos/` and the `idc/backends/`-using trees builds
  with `idc/bin/idc`, including native backends.
- ✅ All 40 cases in `idc/tests/invalid/` produce their expected message under
  **both** compilers, and `compiler_bug()` fires only for a genuine compiler
  bug.
- ✅ `idc/bin/idc` is within ~3× of `idc/idc.py` at realistic project shapes (2.2× at
  800 files) and scales near-linearly. It is 5.1× on the self-host build, which
  is the densest program in the tree; closing that is the string-building work
  in §3.
- ✅ `idc/tools/parity.sh` is MATCH — checked on every demo and both graphics
  backends.
- ✅ Every diagnostic either compiler gives, both give. `idc/tests/invalid.sh` and
  `idc/tests/runtime_invalid.sh` both run both.
- ⬜ `idc/idc.py`'s only remaining job is `--target llvm|wasm`. Bootstrapping is
  unavoidable and stays. `docs/BACKENDS.md` describes how the targets move
  across.
