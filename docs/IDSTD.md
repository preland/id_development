# `idstd` — the `id` standard library: handoff brief

**Status: mostly a specification to build against.** `idstd` is being written in
its own repository beside this one; §3–§7 describe what it should contain and
are not yet a description of code. The compiler side is further along — §2 has
the current state, and three of its nine items are done.

This document is the brief for the agent building `idstd`, plus the list of
changes `id_development` needs so that a standard library is *usable at all*.

Two things are true today and they pull against each other:

- `id` has 30 builtins and no module system. Every non-trivial program
  re-implements `min`, `max`, `abs`, substring, split, a PRNG, a sin table, a
  framebuffer and a bitmap font. `../idem` (a game engine in `id`) has written
  all of them once, well, with the measurements to justify each choice.
- Every function and *every variable name* in an `id` program is global, one type
  per name, and no two function bodies may match up to renaming. A library that
  is linked into every program by default therefore reserves names and logic
  program-wide, for every program, forever.

The whole design problem is the second bullet. §1 is the evidence; §2 is the
compiler work that follows from it; §3–§7 are the library itself.

---

## 0. Scope, as requested

- `idstd` is a **separate repository**, a sibling of `id_development` and `idem`.
- It is **imported by default** — no `conf.id` line, no flag. A program that
  writes `print(fx_max(a, b))` compiles.
- It defines **types** (in the sense `id` allows: conventions, records-as-lists,
  and the fixed-point scales that give integers meaning) and **standard
  functions**.
- **General-purpose graphics belongs in it**: framebuffer, 2D primitives, bitmap
  text, matrices, a software 3D rasteriser, window and input.

---

## 1. Six facts about the compiler, verified on this checkout

Each was tested directly against `bin/idc`, not inferred. The commands are worth
re-running, because every one of them is a constraint on the library.

**§1.1, §1.3 and §1.4 are now fixed** (C4, C2 and C3) and are kept as written,
because the measurements in them are the reason the fixes exist and the numbers
to compare against. §1.2, §1.5 and §1.6 still stand exactly as described.

### 1.1 An imported directory shares one namespace with the program — including locals

A stdlib parameter named `a` makes `a` an `int` in *every user program*:

```
lib/std.id:1: error: variable 'a' is declared int here but string elsewhere;
              a name must keep one type across the whole program
```

The error is reported *in the library*, pointing at innocent code, for a
declaration the user wrote. This is the single most serious obstacle to an
always-on stdlib and it needs a compiler answer (§2.4).

**Fixed by C4:** the rule now applies within a compilation unit — the user's
tree, or one imported tree — and not across them.

### 1.2 The duplicate-logic rule crosses the import boundary

A user writing the obvious `biggest(int p, int q)` collides with `std_max`:

```
lib/std.id:1: error: function 'std_max' has the same signature and logic as
              'biggest' (defined at app/main.id:1); functions must be unique
```

Arguably correct — "there is already one, call it" — but the diagnostic names
the library file first and never says *standard library*. See §2.5.

### 1.3 There is no dead-code elimination

Every function in an imported directory reaches the emitted C whether or not
anything calls it. Measured, hello-world plus a synthetic stdlib of trivial
functions:

| stdlib size | `bin/idc` wall time | binary |
| --- | --- | --- |
| none | 0.18 s | 16 KB |
| 243 functions | 0.36 s | 33 KB |
| 729 functions | 0.75 s | 75 KB |

A realistic `idstd` is 500–700 functions of *real* bodies, so every `id` program
would pay roughly +0.6 s and +60 KB minimum. `idc.py` already computes the
reachable-function set (`idc.py:1278`) for the unreachable-export check, so this
is a small change with a large payoff. See §2.2.

### 1.4 Imports are not transitive — for source directories *or* backends

```
app/conf.id  ->  import "../mid"
mid/conf.id  ->  import "../base"
mid/m.id:2: error: no such function 'bx_one'
```

and the same for a native backend named in an imported directory's manifest.
Consequences: `idstd` cannot be layered into sub-libraries that import each
other, and **`idstd`'s graphics half cannot attach `backends/gfx` on its own** —
today every user program would have to name the backend itself, which defeats
"imported by default". See §2.3.

### 1.5 An export is uninitialised until its declaring function runs, and the compiler enforces it

```
lib/std.id:6: error: 'std_tab' is exported by 'std_tab_init', which nothing
              calls -- an export is initialised when its declaring function
              runs, so this reads an uninitialised global. Call 'std_tab_init'
              from main's setup chain
```

So every stateful `idstd` module (sin table, PRNG, arena, framebuffer, font,
input state) forces a call into every user's `main`, or the program does not
compile. "Imported by default" has to mean initialised by default. See §2.6.

### 1.6 The 3-entries-per-directory rule applies to imported trees

```
lib:1: error: a project directory may contain at most 3 files and directories
       combined, but this one has 4
```

`idstd`'s own tree must obey the rule of 3 at every level including its root
(`README.md` and `conf.id` are not counted). A 600-function library is ~200
files and a tree about 5 levels deep. Plan the layout before writing code (§7).

### 1.7 Two more facts worth carrying, from `../idem/docs`

- **Exported variables become raw C globals with no prefix**, so `export int
  time` collides with libc at link time. Every `idstd` export must carry its
  module prefix — no exceptions.
- **`id` function names get an `id_` prefix**, so they collide with the runtime's
  own helpers: `concat`, `str_of_int`, `list_*`, `mem_alloc`, `arena_*`, `at`,
  `trap`, `peek_n`, `poke_n`, and friends. `idstd` must avoid all of them.

---

## 2. Prerequisite work in `id_development`

> **Status, 2026-08-04.** **C1, C2 and C3 are done and green** — the standard
> library is imported by default, imports are transitive, and dead code is not
> emitted. The suite is 242 passing, 0 failing (231 pre-existing + 16 new in
> `tests/stdlib.sh`, which replaced a count of 11 as DCE tests were added), with
> byte-parity between the two compilers intact on the compiler's own source.
>
> The measured result is the one that mattered: a 729-function library where the
> program calls one function costs **+0.007 s and +40 bytes**, against +0.57 s
> and +58 KB before elimination. The stdlib tax is gone.
>
> **C8 is partly done**, on a defect `idstd` found by hitting it: a function
> named after a runtime helper (`str_of_int`, `concat`, `print`, ...) is a C
> redefinition, and neither compiler checked for it. `cc` reported "conflicting
> types for 'id_str_of_int'", `idc.py` passed through a bare "C compilation
> failed", and **`bin/idc` reported a user's own name clash as "this is a bug in
> the self-hosted compiler; please report it"** — inviting a bug report about
> their own typo. Both compilers now reject it by name. The reserved list is
> generated from `RUNTIME` by `tools/gen_runtime_id.py` so it cannot drift, and
> `tests/stdlib.sh` asserts that it hasn't.
>
> **C4 is done.** The one-type-per-name rule is now per compilation unit — the
> program's own tree, and each imported tree — so a library's `string s` no
> longer makes `int s` an error in a user's function. The measurement that
> forced it: writing the obvious `str_cmp(string a, string b)` against `idstd`
> produced **28 errors, 25 of them inside `core/math/fx/`**, pointing at code
> that had not changed, and the message naming the cause was the 26th. The
> unit travels from `bin/idc` to the self-hosted compiler in the `#file`
> marker, which now reads `#file N|PATH`; the rule is unchanged *within* a
> unit, and `tests/stdlib.sh` holds both halves of that.
>
> **Still outstanding: C5, C6, C7, the rest of C8, C9.** C7 is now the *only* thing keeping graphics out
> of the default library — with DCE landed, an unused framebuffer costs nothing,
> but an unused X11 dependency still costs every program a link line.
>
> **C9 is now measured continuously rather than in prose.** Every project's
> standing against the real library is a line in
> [`tests/idstd_expect.txt`](../tests/idstd_expect.txt), checked by
> `tests/idstd_real.sh` on every run, and a change in either direction fails —
> a new collision, and a port that lands without the ledger being updated. The
> re-measurement below used to live here and go stale; it is now the file.
>
> As of 2026-08-19 that ledger reads: 9 projects build either way or need the
> library, 6 need `--backend` and are untested against it, and **6 are broken
> by it** — `engine`, `moonbuggy`, `solitaire`, and the two
> compiler stages `idc_in_id{,_parse}`. (`idview` was on this list and is no
> longer. `nativeapp` has since moved to its own repository, `../id_nativeapp`.)
>
> The compiler stages are the interesting pair. `bin/idc` bootstraps them with
> `--no-std`, so the build is not broken — but `bin/idc compiler/parse`
> is how the README says to build them, and that fails. Whether the compiler
> should depend on the library it ships, or be permanently a `--no-std`
> project, is an open decision and the reason those two lines exist.
>
> Everything else in `tests/run.sh` sets `IDC_NO_STD=1` and is hermetic, and
> `tests/stdlib.sh` covers the library path against a fixture library in
> `tests/fixtures/idstd`. That is deliberate, and it is also exactly why
> `idstd_real.sh` had to exist: a hermetic suite cannot see the library.
>
> Two things were learned by getting them wrong, both now locked by tests:
>
> - **Dead code must still be checked.** A good deal of `idc.py`'s checking
>   happens inside `gen_function`, so generating only the reachable functions
>   silently stopped enforcing the export/import access rules on the rest —
>   `tests/invalid`'s `import_without_export` and `unexported_access` both began
>   compiling clean, while `bin/idc` still rejected them. Everything is now
>   checked and generated; only emission is filtered.
> - **The two compilers disagreed about source order.** `idc.py` globally sorts
>   every source file; `bin/idc` concatenated per-root sorted lists. That agreed
>   only as long as no project had a source dependency — and the stdlib is a
>   source dependency of every build, with absolute paths sorting before the
>   project's relative ones. It would have broken byte-parity on every program
>   at once. `bin/idc` now does one global `LC_ALL=C sort -u`.

This is a workstream in *this* repo, and most of it should land before `idstd`
grows past a prototype. Ordered by how much the library depends on it.

Each change is built in the **self-hosted stages** (`compiler/lex`,
`compiler/parse`), and `tools/parity.sh` / `tests/run.sh` must still
pass byte-identical output.

> This paragraph used to read "every change must be made in **both**
> `idc.py` and the self-hosted stages", and that sentence turned out to be
> the single most load-bearing cause of new work landing in `idc.py` first:
> it names `idc.py` before the compiler, and it frames the self-hosted side
> as cost. It is also not true. `idc.py` is stage 0 of the bootstrap, so it
> needs a construct only once *this tree's own source* uses it. What must
> genuinely agree in both is **diagnostics**, which `tests/invalid.sh`
> enforces by running every case through both compilers. See
> [`HACKING.md`](HACKING.md).

### C1 — Implicit import of `idstd` (the headline feature) — **DONE**

- Resolve the library by, in order: `$IDSTD_HOME`, a sibling `../idstd`
  directory, a path baked into `bin/idc`. Fail with a diagnostic that says which
  paths were tried, not "no such function".
- `--no-std` must exist and must be honest, because three things need it:
  1. **`idstd` itself** cannot import itself.
  2. **The bootstrap stages.** `compiler/lex` and `compiler/parse`
     define their own `lset`, their own helpers, and their own local vocabulary.
     Implicitly importing `idstd` into them will produce duplicate-logic and
     name-type errors and change their emitted C — which breaks self-hosting and
     byte-parity. `bin/idc` must build them with `--no-std`.
  3. `tests/invalid/`, whose diagnostics must not shift because a library
     appeared in the program.
- Decide and document whether a *single-file* build (`bin/idc prog.id`) gets the
  stdlib. Recommendation: **yes** — that is the tutorial path and the one that
  most needs `fx_max` to exist.

### C2 — Dead-code elimination (§1.3) — **DONE**

Emit only functions reachable from `main` (plus their exports). `idc.py:1278`
already builds the set. Without this, `idstd` is a tax on every program.

Note the interaction with §1.5: with DCE, an unused stateful module's `*_init`
also disappears, and the unreachable-export error becomes moot for anything the
program does not use.

### C3 — Transitive imports (§1.4) — **DONE**

An imported directory's own `conf.id` must be honoured, with cycle detection
and de-duplication by resolved path. This is what lets `idstd/gfx` declare its
dependency on `backends/gfx` instead of every user program doing it.

### C4 — Stop the library from reserving the user's local names (§1.1) — **DONE**

Option (a), per-unit name-type checking, was taken. A unit is one source root:
the program's own tree, and each imported dependency tree. `bin/idc` numbers
the roots and puts the number in the `#file N|PATH` marker (the lexer is
unchanged — the marker's text was always taken verbatim); the self-hosted
compiler stamps every AST node with its unit, and both the one-type check and
the variable-type table are keyed by unit and name. `idc.py` knows which root
each file came from directly and keys `var_types` the same way. Exported names
are untouched: an export is one global for the whole program, reserved
program-wide, and is still found from every unit.

The options as they were weighed:

| option | cost |
| --- | --- |
| **(a) Per-unit name-type checking** — the one-type-per-name rule applies within a compilation unit (user tree, each imported tree) rather than across them | a compiler change; the rule stays exactly as strong *within* the code a person is writing, which is where it was earning its keep |
| (b) `idstd` publishes a reserved vocabulary and users work around it | free, and it makes `string n` a compile error in someone else's program for the rest of time |
| (c) `idstd` prefixes every parameter and local (`fx_a`, `fx_b`) | free, unbearable to read, and does not scale past a few modules |

**Recommendation: (a).** The rule exists so that `obj` cannot mean two things in
one program a person is reading; a library's internals are not that program.
If (a) is rejected, fall back to (b) and write the vocabulary into `idstd`'s
`NAMES.md` before the first function is written.

### C5 — Duplicate-logic diagnostics that know what the standard library is (§1.2) — outstanding

Keep the check — "we already have one, call it" is the right answer — but:

- name the standard library as such, and lead with the *user's* file, not the
  library's;
- suggest the call: `error: this is fx_max from the standard library; call it
  instead`;
- consider marking library internals as not participating in the user-facing
  check. `id` has no public/private distinction today; a manifest listing the
  library's public surface would be enough, and is useful documentation anyway.

### C6 — Automatic initialisation of stdlib state (§1.5) — outstanding

A user's `main` must not have to call `idstd_init()`. Either:

- the generated C `main` wrapper (`idc.py:1841`) calls a fixed `idstd` init chain
  before `id_main`, for the modules actually reachable; or
- `idstd` is built with no exported state at all, which is not achievable for a
  sin table, a framebuffer or a font.

Take the first. The init chain's order must be explicit and documented, exactly
as `idem_boot` does it.

### C7 — Link a native backend only when its symbols are reachable — outstanding

Otherwise every `id` program links X11 and OpenGL because `idstd` contains a
framebuffer. With C2 in place the reachable-symbol set is already known; the
driver should skip a backend none of whose functions survive. Without this,
graphics cannot be in the default-imported library and §0's last bullet fails.

### C8 — Versioning and diagnostics hygiene — outstanding

- `bin/idc --version` should report the `idstd` it resolved.
- A stdlib frame in a diagnostic should be visually distinguishable from user
  code, because most compile errors a beginner hits will now name a library file.

### C9 — Re-measure `tests/run.sh` and the demos — outstanding

Every demo in this repo defines helpers that `idstd` will also define
(`demos/engine`'s `lset`, the games' `rng_*`, `fpsmaze`'s sin table). They will
all fail to compile the day `idstd` is implicit. Either port them onto `idstd`
(good — it is the library's first real test) or build them `--no-std` (fast, and
leaves the duplication in place). Budget for this; it is not a footnote.

---

## 3. What goes in `idstd`

Prefix-per-module, as in `../idem/docs/NAMES.md`. "Source" is where a
ready-to-lift implementation already exists.

### 3.1 `core/math` — `fx_`, `rnd_`

The floor of everything. `id` has no `abs`, `min`, `max`, `sqrt`, trig or
`rand()`.

| function | source |
| --- | --- |
| `fx_abs`, `fx_min`, `fx_max` | `idem/engine/core/math/fx/base.id` |
| `fx_clamp`, `fx_sign`, `fx_lerp` | `idem/engine/core/math/fx/lim.id` |
| `fx_mul(a,b,sc)`, `fx_div(a,b,sc)` — scaled multiply/divide with `word` intermediates | `idem/engine/core/math/fx/wide/mul/mul.id` |
| `fx_sqrt`, `fx_sqbit`, `fx_sqstep`, `fx_sqtake`, `fx_sqloop` — bit-by-bit integer root | `idem/engine/core/math/fx/wide/` |
| `fx_hyp`, `fx_hyp3`, `fx_hypfix`, `fx_wroot` — 2D/3D magnitude with wide accumulation | `idem/engine/core/math/fx/wide/` |
| `fx_sin`, `fx_cos`, `fx_sin_q`, `fx_sin_lin`, `fx_norm_deg`, `fx_tab`, `fx_trig_init` — 91-entry quarter-wave table, millidegrees in, ×1000 out | `idem/engine/core/math/trig/` |
| `rnd_init`, `rnd_next`, `rnd_range` — Park-Miller via Schrage | `idem/engine/core/math/rnd.id` |

**To write new:** `fx_atan2` (millidegrees — nothing in either repo has it, and
every aiming, orbit and polar conversion needs it), `fx_hypot` for the `int`
case, `fx_pow`, and a float-side mirror if §8's decision goes that way.

Carry `idem`'s recorded traps into the doc comments: `fx_sqrt` is silently wrong
above 2^31; a per-mille vector already carries its scale; an unconditional
neighbour read needs a clamped index.

### 3.2 `core/data` — `lst_`, and the four bare helpers

| function | source |
| --- | --- |
| `lset`, `lget`, `sset`, `lset2`, `wset` — writing through a list you do not own | `idem/engine/core/util/lst/` |
| `lst_fill`, `lst_set_all` | `idem/engine/core/util/lst/grow.id` |
| `lst_pick(at, i, hit)` — first-match fold, because there is no `break` | `idem/engine/core/util/lst/w/pick.id` |

`lset` is not a convenience: `(import xs)[i] = v` is rejected by the compiler and
the diagnostic *already names `lset` as the fix*. Once `idstd` exists, that
diagnostic should name `idstd`'s `lset` specifically — a small C5 follow-on.

**To write new:** `lst_copy`, `lst_swap`, `lst_reverse`, `lst_find`,
`lst_index_of`, `lst_last`, `lst_sort` (int; and a string sort once `str_cmp`
exists), `lst_min`/`lst_max`, `lst_sum`, plus `buf_zero`/`buf_copy`/`buf_cmp`
over the flat store (`alloc`/`peek8`/`poke8`).

### 3.3 `core/text` — `str_`, `chr_`, `fmt_`

The largest genuinely-missing area. `../idem/docs/research/id-language.md` §10
lists what the language ships (`len`, `charat`, `chr`, `to_int`, `+`, `==`,
`str_of_mem`, `mem_of_str`) and what every program hand-rolls:

> `substr`, `split`, `join`, `index_of`, `starts_with`, `trim`, `to_upper`,
> string ordering, `to_float`, int→string other than via `"" + n`.

| function | source |
| --- | --- |
| `str_slice(s, i, n)` — substring via the flat store, one allocation | `idem/engine/core/util/str.id` |
| `str_blit(s, i, n, ad)` | same |
| `str_eqat(s, i, txt)` — match without materialising a substring | same |

**To write new:** `str_find`, `str_starts`, `str_ends`, `str_split → string[]`,
`str_join`, `str_trim`, `str_upper`/`str_lower`, `str_cmp` (there is no `<` on
strings, so sorting is impossible without it), `str_repeat`, `str_pad`,
`str_hash`, `str_to_float`; `chr_is_digit`,
`chr_is_alpha`, `chr_is_space`, `chr_upper`, `chr_lower`; `fmt_int`, `fmt_hex`,
`fmt_pad`.

**`str_of_int` and `str_of_word` cannot exist**, and this section used to ask
for them. §1.7 is the binding constraint: the runtime prelude already defines
`id_str_of_int`, so an `id` function of that name is a C redefinition. The
compiler now says so directly (see C8) instead of letting `cc` report it as
nobody's fault. Use `fmt_int` and friends. `fx_hypot` is out for the same class
of reason: it would have the same body and signature as `fx_hyp`, which is a
duplicate-logic error.

**Two performance rules must be enforced by the implementations, not just
documented** — both measured in `idem`:

- `s = s + chr(c)` in a loop is quadratic in time *and retained memory*
  (1000 frames of text: 667 ms, 1.8 GB). Every builder here goes through
  `alloc`/`poke8`/`str_of_mem` (the same work: 1 ms, 5.8 MB).
- `len(s)` is a `strlen` every time and is not memoised; `charat` memoises the
  last string's length. So every loop is `while (charat(s, i) >= 0)`, never
  `while (i < len(s))` — and alternating `charat` between two strings defeats the
  memo, which is why `str_eqat` is fine per line and wrong per token.

### 3.4 `sys/err` — `err_`

`id` has no stderr, no exceptions and no early return, so errors are
*accumulated*: report, count, continue, and let the caller gate on
`err_count() == 0`. That pattern is general, not engine-specific.

`err_init`, `err_report`, `err_count`, `err_clear`, `err_say`, `err_mute`,
`err_keep*`, `err_drop*` — `idem/engine/core/util/err/`.

`err_mute` matters more than it looks: a program whose output *is* data (a PPM on
stdout, a generated file) cannot print a diagnostic without corrupting it.

### 3.5 `sys/io` — `file_`, `term_`

**Files** wrap `id_development/backends/fs` (`fs_open`, `fs_read`, `fs_write`,
`fs_close`, `fs_size`, `fs_exists`, `fs_remove`, `fs_error`, plus `fs_run`).
Bytes cross that seam as an `int[]`, which is what makes binary files possible —
a `string` is NUL-terminated. To write new: `file_read_all` (chunked into the
flat store; `idem/engine/game/load/asset/io/` is the worked example, 64 KB
staging), `file_write_all`, `file_lines`, `file_slurp_text`.

**Terminal**, from `id_development/demos/engine`: `term_setup`/`term_done`, raw
mode, SGR colour, the character-cell screen model, `draw_text`, `draw_box`,
`draw_hline`/`draw_vline`, dirty-cell rendering, `finish_frame`.

⚠️ **`demos/engine` cannot be lifted as-is.** Its functions are named `clear()`,
`render()`, `drain()`, `fixup()`, `set_cell()`, `lset()` — bare, unprefixed
names, which is exactly the collision class an always-on library must not create.
Every one needs a `term_` prefix, and `lset` must become the shared one from
§3.2 rather than a second copy (which would be a duplicate-logic error).

### 3.6 `sys/win` — `sys_`, `inp_`

The window and input seam over `backends/gfx`, from `idem/engine/core/sys/`:

- `sys_open`, `sys_sync`, `sys_present`, `sys_fit`, `sys_alive`, `sys_quit`
- `sys_stage`, `sys_sx`/`sy`/`sw`/`sh`, `sys_vp_init` — the aspect-preserved,
  centred mapping from a declared logical size into the real window
- `sys_now`, `sys_pace`, `sys_wait` — frame pacing
- `inp_init`, `inp_drain`, `inp_down`, `inp_hit`, `inp_up`, `inp_mx`, `inp_my`,
  `inp_mdown`, `inp_mhit`

Two contracts to carry across verbatim, both learned painfully:

- **`sys_sync` and `sys_present` are two calls.** Resizing may only happen before
  anything is drawn; merging them shears the frame.
- **`inp_sample` is the single legal reader of the mouse-button mask, once per
  frame**, because the two wheel bits are a latch that reading clears.

### 3.7 `gfx/px` — `sf_`, `ppm_`

The framebuffer. From `idem/engine/gfx/px/`: `sf_alloc`, `sf_init`, `sf_open`,
`sf_grow`, `sf_clear`, `sf_idx`, `sf_pset`, `sf_pget`, `sf_span`, `sf_span_row`,
`sf_rect`, `sf_clip`, `sf_unclip`, `sf_cl_init`; `ppm_dump` and friends.

Two rules that are the whole reason this is worth lifting rather than rewriting:

- **Clipping lives in exactly one place.** `sf_pset` tests bounds; every span
  routine clips once at the ends and then writes untested. An out-of-range list
  store **aborts the process** — it is not silently dropped, whatever
  `demos/gfxdemo`'s comment says.
- **A span is a flat `while` loop assigning into a list *parameter*** — 4.3–5.0
  Gpx/s, against 0.5 Gpx/s for per-pixel `sf_pset`. A 10× difference, and it is
  what makes software rendering viable.

`ppm_dump` is disproportionately valuable: it is how graphics gets tested with no
display (§9).

### 3.8 `gfx/d2` — `d2_`, `txt_`

From `idem/engine/gfx/d2/`:

- colour: `d2_rgb`, `d2_cr`/`cg`/`cb`, `d2_shade`, `d2_blend`
- shapes: `d2_hline`, `d2_vline`, `d2_line` (Bresenham), `d2_frame`,
  `d2_circle`, `d2_disc`, `d2_clear`
- sprites: the sprite table (`d2_spr_add`/`push`/`find`/`at`/`px`/`w`/`h`/`nf`),
  `d2_blit`, `d2_blit_scaled`, `d2_blit_flip`
- text: `txt_draw`, `txt_draw_sc`, `txt_draw_at`, `txt_glyph`, `txt_width`,
  `txt_number`, `txt_cell`, `txt_cellh`, `txt_align`, `txt_ui`

**The bitmap font is one of the highest-value things in the whole brief.** `idem`
carries the IBM VGA 8×16 face generated into `id` source by `tools/mkfont.py`
from `test_assets/vga8x16.psf`, plus `psf_load` to replace it at runtime with any
PC Screen Font. Text on a framebuffer, for free, in every `id` program.
`../idem/docs/research/id-patterns.md` §6 documents the whole thing, and
`NAMES.md` §6 records the trap: **the cell is not square**, `txt_cell()` is the
*width* only, and conflating it with the row count drew every second glyph.

Note `../idem/docs/ARCHITECTURE.md` §13 records the editor's row pitch still
assuming an 8-pixel glyph — check the constants on the way across rather than
copying the bug.

### 3.9 `gfx/d3` — `m4_`, `d3_`

From `idem/engine/gfx/d3/`:

- `m4_new`, `m4_ident`, `m4_mul`, `m4_translate`, `m4_scale`, `m4_rot_x/y/z`,
  `m4_perspective`, `m4_apply`, `m4_pt` — 16-entry row-major `int[]`, entries
  ×1000, `word` intermediates narrowed once
- `d3_` camera and view matrix, near-plane clip, viewport, backface test,
  z-buffer, z-buffered triangle spans, Gouraud spans

This is a complete software 3D pipeline that has rendered a 233 552-triangle
Blender scene at 37.6 ms/frame. It belongs in a standard library far more than in
one engine.

Carry `idem`'s two performance findings: **compute nothing before you know it
will be drawn** (backface test before the Lambert term — 4× on a real scene), and
the exact plane test and the rasteriser's projected winding disagree on ~29 of
256 000 pixels at coplanar depth ties, which is a documented tie, not a bug.

---

## 4. The fixed-point convention is part of the library

`id` has no cast and no `float` in the parts of `idem` that matter, so integers
carry meaning only by convention. Publishing that convention is as much a part of
`idstd` as the functions are — it is the closest thing the language has to
*types*, which is the other half of what was asked for.

Take `../idem/docs/ARCHITECTURE.md` §4 as written:

| quantity | scale |
| --- | --- |
| screen position, 2D | whole pixels |
| 2D sub-pixel motion | centipixels (×100) |
| world position, 3D | millunits (×1000) |
| angle | millidegrees (×1000) |
| trig result | ×1000 |
| matrix entry | ×1000 |
| scale factor | per-mille (1000 = unscaled) |
| colour | packed `0xRRGGBB` |
| time | milliseconds |

Plus the rule that goes with it: **multiply before dividing, always**, and a
function's name says which scale it speaks. Overflow is the real hazard — `int`
is 32-bit and wraps silently, so anything reaching 10⁶ accumulates in a `word`
and narrows once, inside the helper, so no caller repeats it.

Alongside this, `idstd` should publish the **record-as-list** convention
(`../idem/docs/research/id-patterns.md` §3, idioms 4–6): parallel lists indexed
by an integer id for many-of-a-kind, one fixed-slot list with named zero-action
accessors for one-of-a-kind, and slot numbers spoken *only* through named
functions. `id` has no structs; this is what a struct is here.

---

## 5. Constants: the `base() + n` rule is mandatory

A zero-action function returning a bare `int` literal has the same *logic* as
every other zero-action function returning that literal, program-wide. `idem`'s
first whole-engine build failed exactly this way — `ast_k_repeat()` and
`inp_hold()` both returned `120`, in modules whose authors had never met.

An always-imported library makes this dramatically worse: **every bare integer
constant `idstd` defines makes that literal unavailable to every user program.**
So every family of constants is `<prefix>_base() + n`, with one base function per
family holding the unique bare literal, and the base table is registered in
`idstd`'s `NAMES.md`. Reserve `idstd`'s base values in a block far from anything
a user program would pick (`idem` uses 400, 3100, 3900, 4000, 5200, 6000, 6400 —
do not collide with those either, since `idem` will import `idstd`).

---

## 6. Explicitly *not* in `idstd` (v1)

Recorded so the boundary is a decision rather than an oversight.

| excluded | why |
| --- | --- |
| `ent_`, `scn_`, `scr_`, `run_`, `sim_`, `ui_` | a game engine's model, not a standard library's. They stay in `idem`. |
| `lex_`, `par_`, `ast_` | these are *idml*'s lexer and parser, not general ones. A general tokeniser toolkit is a fair v2 idea; a specific language's parser is not. |
| `png_`, `jpg_`, `inf_`, `zst_`, `bl_`, `psf_` | image, DEFLATE, zstd, `.blend` and font decoders — ~600 functions of genuinely general code, and far too much to link into hello-world before DCE (§2.2) exists. **Strong v2 candidates**, probably as a separate opt-in `idfmt`. `psf_load` is the exception worth reconsidering for v1: it is small and the font table is already there. |
| `pack_`, `imp_`, `ed_` | tools, not library. |
| anything needing a filesystem *walk* | `id` cannot see directories; that is why `bin/idc` and `tools/idem` are shell drivers. A stdlib cannot fix it. |
| audio | there is no audio backend anywhere in either repo. Do not stub it. |

---

## 7. Tree layout

The rule of 3 binds at every level *including the repository root*, and it binds
on imported trees (§1.6). `README.md` and `conf.id` do not count. Sketch:

```
idstd/
  README.md
  NAMES.md              the registry -- a build dependency, not documentation
  conf.id             backends/fs, backends/gfx   (needs C3)
  core/
    math/   fx/  trig/  rnd/
    data/   lst/  buf/
    text/   str/  chr/  fmt/
  sys/
    err/
    io/     file/  term/
    win/    sys/   inp/
  gfx/
    px/     surf/  clip/  ppm/
    d2/     shape/ spr/   text/
    d3/     m4/    tri/   view/
```

Nine leaves, each of which becomes its own 3-deep tree — `idem`'s `engine/gfx/d3`
alone is ~90 functions across ~30 files. Expect ~200 files at 600 functions.
Lay the skeleton out *first*: `idem` records that parallel workstreams repeatedly
broke each other's builds because the 3-entry rule was violated mid-restructure
in an imported tree, and every program in the world will now be importing this one.

---

## 8. Decisions to make before writing code

These change the shape of the library and should be settled, not discovered.

1. **`float`, or fixed point only?** `float` works end to end in both compilers,
   and `idem` chose integers deliberately (bit-identical simulation, integer
   framebuffer, integer z-key). A *standard library* has a wider audience than a
   game engine. Recommendation: fixed-point `fx_` is the primary surface as
   `idem` wrote it, plus a thin `flt_` module (`flt_sqrt`, `flt_sin`, …) so that
   scientific and scripting uses are not locked out. Both, clearly labelled.
2. **Does `idstd` include graphics by default, or is `gfx` opt-in?** §0 says
   graphics is in. That is only affordable with C2 and C7 (DCE plus
   link-on-demand); without them, every hello-world links X11 and OpenGL. If
   those slip, ship `core` + `sys` as the implicit library and make `gfx` an
   explicit import for one release.
3. **Public surface, or all of it?** Related to C5. A published list of public
   functions lets internals be exempted from the user-facing duplicate-logic
   check and gives the library a documented API. Recommendation: yes, from day
   one, in `NAMES.md`.
4. **Versioning and compatibility.** Once names are reserved program-wide,
   *removing* an `idstd` function is a breaking change and *adding* one can break
   an existing program (a new stdlib function that duplicates a user's helper).
   Decide the policy now.
5. **Who owns `idem`'s copies?** `idem` should import `idstd` and delete its
   `engine/core` and most of `engine/gfx` once the library exists. That migration
   is the library's best acceptance test and should be planned as part of it.

---

## 9. Verification

`idem`'s testing approach transfers directly and should be adopted, not
reinvented (`../idem/docs/ARCHITECTURE.md` §10):

- **Every graphics path is verified off-screen.** `ppm_dump` writes the
  framebuffer to stdout; a golden file is a checksum. A display is a way to
  *look* at the library, never a way to test it.
- **Assert numbers computed independently.** `idem`'s 3D suite checks the view
  matrix against hand-derived vectors and the clipper against a row-summed screen
  area, because "it looked right" is not available.
- **A matching output hash is not evidence of correctness** — it is evidence
  about one input. `idem` shipped a zstd decoder that hashed correctly on two
  fixtures while decoding wrongly, because an over-long copy was clipped at
  exactly the right byte. Test properties, not just goldens.
- Run the whole suite through **both** compilers (`idc.py` and `bin/idc`); it is
  the cheapest parity check available, and `idstd` is now in every program's
  build so a parity break is a break everywhere.
- Add a **cost regression**: hello-world's build time and binary size, asserted.
  That number is the one that tells you whether C2 is still working.

---

## 10. Suggested order of work

1. `id_development`: **C2** (DCE) — it is independently useful and it unblocks
   everything about cost.
2. `id_development`: **C3** (transitive imports), **C7** (link on demand).
3. `idstd`: skeleton tree + `NAMES.md` + `core/math` + `core/data`, built as an
   ordinary explicit import. Port one demo onto it.
4. `id_development`: **C4** (the name-reservation decision) — settle it before
   the library is large enough that reversing it is expensive.
5. `idstd`: `core/text` (the largest new-code area), `sys/err`.
6. `id_development`: **C1** (implicit import) + **C6** (auto-init) + **C5**
   (diagnostics), then **C9** (fix the demos).
7. `idstd`: `gfx/*` and `sys/win`, lifted from `idem`.
8. `idem`: delete its `engine/core` and import `idstd` instead — the acceptance
   test.

---

## Appendix — where to read before starting

| document | what it gives you |
| --- | --- |
| `../idem/docs/research/id-language.md` | the verified language reference: types, operators, the 30 builtins, all 13 rules with their exact diagnostics, and §11's list of what silently produces wrong code |
| `../idem/docs/research/id-patterns.md` | how real `id` code is actually written: dispatch chains under the 3-action limit, the state idioms, the fixed-point tricks, the parser template, the frame loop |
| `../idem/docs/NAMES.md` | the registry `idstd`'s own must be modelled on, including §6's traps |
| `../idem/docs/ARCHITECTURE.md` | §3 (rasteriser), §4 (fixed point), §5 (data model), §10 (verification), §13 (known gaps — read before copying anything) |
| `id_development/README.md` | the language rules as the compiler states them |
| `id_development/docs/GAPS.md` | what `bin/idc` still cannot do |
| `id_development/backends/fs/README.md` | the worked example of a backend manifest |
