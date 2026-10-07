# How far `id` is from C and Rust, and why

> **Status: measurement method and structure.** Every number lives in a
> generated file under `bench/results/`; this document states what is measured,
> how, and what the numbers are attributed to. A figure that varies by machine or
> by day is never written here.

## 1. The suite (`bench/`)

```
bench/ref/c/      one C program per benchmark, plus gen.c (the input generator)
bench/ref/rust/   the same programs in Rust, std only
bench/id/NAME/    the same programs in id, one project tree each
bench/run/        the harness, an id program with the same rules and cases as any other
bench/results/    generated output of the harness
```

Each benchmark solves one task and prints the same bytes in all three languages.
The harness compares every toolchain's stdout against the normalising toolchain's
(`cmp`), and a mismatch is reported as `FAIL`, not as a time.

| name | kind | task |
| --- | --- | --- |
| nbody | kernel, float | 5-body symplectic integration, energy printed as scaled integers |
| spectral | kernel, float | spectral norm, 10 power iterations |
| fannkuch | kernel, int | fannkuch-redux checksum and max flips |
| mandel | kernel, float | mandelbrot, escape-iteration totals (no bitmap: a string cannot hold NUL) |
| btrees | kernel, allocation | binary-trees |
| fasta | kernel, output | fasta generator, LCG, 60-column lines |
| knuc | kernel, hash map | k-nucleotide counts for k = 1, 2 and five fixed k-mers |
| sortb | realistic | bottom-up merge sort of an LCG integer list |
| strbuild | realistic | build a comma-joined string of decimal tokens, split it, parse each |
| expr | realistic | recursive-descent evaluation of a file of arithmetic expressions |
| csv | realistic | group-by aggregate over a CSV file with a hash map |
| json | realistic | parse a JSON document into a tree, then traverse it |

Sizes are in `bench/run/conf.id` (`br_args`, `br_gen`). They are chosen so the C
build runs about half a second or more; where that was not possible without
making the id build exhaust memory or the 60 s limit, the results file shows the
actual C time. Two deliberate deviations from the brief: the JSON document is
larger than 20 MB (the C parser takes well under half a second on 20 MB), and
binary-trees stops at a depth the leaking id build can hold in RAM.

"Idiomatic" means the representation each language reaches for first: C uses
malloc, structs and hand-rolled hash tables; Rust uses `Vec`, `Box`, `HashMap`;
id uses lists, structs of lists, idstd's `hmap_`, `str_split`, `str_join` and
`str_slice`, and a flat tape for JSON. The comparison is therefore of
programs, not of one algorithm on three runtimes; where the representations
differ in a way that explains a result, the attribution says so.

## 2. Toolchains

`bench/run/conf.id` holds one command template per toolchain. All of them
come from nix or the nix profile; the harness records the exact versions into the
results file (`meta.txt`, printed at the top).

| label | command |
| --- | --- |
| gcc-O2 | `gcc -O2 -ffp-contract=off` (the normalising toolchain) |
| gcc-O3n | `gcc -O3 -march=native -ffp-contract=off` |
| clang-O2 | `clang -O2 -ffp-contract=off` |
| rust-O3 | `rustc -C opt-level=3` (nixpkgs#rustc) |
| rust-O3n | `rustc -C opt-level=3 -C target-cpu=native` |
| id-c | `idc/bin/idc DIR -o OUT`: idc emits C and runs `cc -std=c11 -O2` per unit, see section 5 |
| id-llvm | `idc/bin/idc DIR -o OUT --target llvm`: idc emits IR, `clang -O2 -flto` over the module, the C runtime and the backends |

`-ffp-contract=off` keeps fused multiply-add out of the C builds so the float
benchmarks print identical digits; Rust never fuses. `--target wasm` is not
measured: it needs a wasm32-wasi sysroot that is not in this environment.

## 3. Methodology

* **One benchmark at a time**, pinned with `taskset -c CORE` (default core 11,
  argument 3 of the harness). The harness never runs two measured processes
  concurrently.
* **Repetitions**: argument 2 (default 5). Every cell is the median; the spread
  table is (max - min) / median.
* **Wall time and peak RSS** come from GNU `time -f '%e %M %U %S'` around the
  benchmark process only. `%e` has 10 ms resolution; the harness does not
  measure with its own clock because its child-polling loop quantises at 20 ms.
* **Binary size** is `fs_size` of the output; **compile time** is the wall time
  of the build command with the harness's caches hot (idc: lists and units
  cached, cases cached). A cold idc build is much longer because it also checks
  and compiles idstd; that is measured separately below.
* **Contention.** The harness records the load average and the five busiest
  processes when it starts (`meta.txt`). A run made on a loaded machine is
  labelled preliminary in whatever quotes it; the harness does not decide.
* **Resumable.** Rows are appended to `WORK/results.tsv`; a unit already
  present is skipped. Argument 4 is a time budget in seconds (0 = unlimited) after
  which the harness stops with status 3 and prints nothing; rerun to resume.

### Controls for the attribution experiments

The lesson of `hot-leaf-benchmarking` applies: assume the first control differs
from the treatment in more than the variable under test, and verify it.

* A variant is the C that idc emitted, changed by one `sed` expression.
* Every variant's output is compared by hash with the unmodified build's.
* Variants are timed alternating round-robin on one pinned core, and the
  reported ratio is the median of per-round pairs, with its min and max.
* The baseline of a ladder is built the way the variants are (single translation
  unit, `gcc -std=c11 -O2`), not the way idc builds, because idc's own build splits
  the program (section 5); the idc build is one rung of the ladder.

## 4. Running it

From the repository root, with `IDSTD_HOME` set:

```
idc/bin/idc bench/run -o /tmp/benchrun
/tmp/benchrun WORKDIR 5 CORE 0 > WORKDIR/results.md
```

`CORE` should be a core nothing else uses. Arguments are `WORKDIR [REPS [CORE
[BUDGET_S [FILTER]]]]`; FILTER keeps only benchmarks whose name contains it. The
full suite takes tens of minutes, so start it with `run_in_background`; to keep to
the 60 s per-command rule, pass a budget (default 50) and repeat the command.

## 5. Cost centres

Each is a property of the C that idc emits (`idc --keep-c`) or of the runtime
prelude in `idc/compiler/parse/back/tgt/c/runtime/`. They are ranked by the share
of the gap they explain in the benchmarks where they matter; the measured shares
are in `bench/results/attribution.md` (ladders and profiles), and that file also
says how far to trust them.

Items 1, 3 (the allocator half), 7 and 10 have since been addressed; each says
how. The ranking is the one the ladders measured before those changes.

1. **Program functions are not `static`.** *Addressed: `-O2`, the default, links
   with LTO (docs/BACKENDS.md, "Optimisation levels").* Every function idc emits has external
   linkage, so gcc -O2 keeps a callable copy and inlines only where that shrinks
   the code. The three-action rule makes most functions small and called from one
   place; a `static` function called once is always inlined. In the numeric
   kernels, compiling the same C with `-fwhole-program` is the single largest step
   toward C (a call per pair of bodies in nbody, a call per element in
   spectral-norm and fannkuch disappear).
2. **Which build you get.** idc's default build (unit mode, cache on) rewrites the
   prelude accessors to `static inline`; the path with the cache off, `IDC_UNITS=0`,
   or a hand compile of `--keep-c` output does not, and gcc then declines to inline
   `id_list_get`/`id_list_set` because of their cold inline error paths. The same
   program is several times slower. The unit split itself costs nothing
   measurable: a single translation unit with the same `inline` keywords runs at
   the speed of the split build.
3. **Allocation.** *Allocator addressed 2026-10-06: a list is one block from a
   headerless size-class pool (docs/MEMORY.md, section 1); unfreed structs and
   strings remain.* Before that, a list was two `malloc`s (header and cells), a struct is a list,
   a struct holding a list is four; every block also carries a 16-byte intrusive
   arena header. In allocation-heavy programs libc malloc and free are the
   majority of user time, and the unfreed memory (structs, strings) makes the
   kernel's page-fault time a large share of the wall time.
4. **Strings.** Each `str_slice`, `str_split` field or `to_int` / int-to-string
   conversion goes through the flat store, a byte copy, an allocation, a NUL scan
   (`memchr`) and, for numbers, `strtoll` or `snprintf`. Hashing a key is a
   byte-at-a-time id loop, comparing keys is `strcmp`, and every key is a fresh
   string.
5. **List accessors.** Every `xs[i]` is a null check, a bounds check and, for a
   write, a constant-lock check, then a 64-bit cell; an `int[]` is 8 bytes per
   element. Removing the checks is worth a modest fraction on numeric loops once
   inlining is fixed. *Partly addressed: the C target emits a `while (j < n ...)`
   loop twice, behind one guard that proves every access in range for the whole
   loop, and the checked loop as the fallback, so a loop that would trap still
   traps at the same iteration with the same message
   (`compiler/parse/back/tgt/c/emit/prog/code/body/fast/`). The guard covers
   `xs[j]` and `xs[j + k]`, and an index that is a sum of literals, names the
   body leaves alone, counters of the condition (`xs[j * w + c]`), a second
   counter stepped once per iteration (`dst[k]` in a merge), and a local set
   once from those at the top of the body (`int q = j * 7; xs[q + 3]`); the
   guard compares the index's largest value with the length in 64 bits.
   Accesses in a function the loop calls, and limits other than a variable, a
   literal or `len(xs)` (nbody's `len(b) / stride`), are not covered. The LLVM
   target does the same at the IR (`compiler/parse/back/ir/build/stmt/flow/loop/`):
   it asks that analysis which loops and accesses qualify, reads its guard back
   into IR (`guard/`), and lowers the loop twice, the covered accesses calling the
   runtime's unchecked `id_list_cell` / `id_list_cell_set` in the guarded copy;
   a freestanding build and `-O0` keep the checked loop. wasm is the C target's C.*
6. **Conf constants are mutable globals** (non-const, non-static): reloaded after
   any call and never folded into index arithmetic. A small effect.
7. **Native calls are opaque** (sqrt): an external call gcc must assume writes any
   memory. Small next to item 1; an intrinsic also removes the call. *Addressed:
   under LTO a backend's C is compiled for LTO too, so a native inlines, and
   idstd's `flt_` library (host/num) gives sqrt and the rest of libm. The LLVM
   target does the same with clang: a program's backends are compiled with
   `-flto -ffat-lto-objects`, and the link raises the LTO inliner's threshold to
   400 so the runtime's `id_list_set` and friends inline as gcc's do.*
8. **Overflow checks** in allocation size computations, the exit-time arena walk,
   and the arena list maintenance: each measured at a few percent or less.
9. **Float boxing** (`id_box_f` / `id_unbox_f`) compiles to plain `movsd` loads and
   stores; it costs nothing once the accessor is inlined.
10. **Signed overflow** was undefined in the emitted C. *Addressed: every C
    compile passes `-fwrapv` (SPEC.md §2.1).*

The LLVM target (`--target llvm`) once failed to assemble IR for nbody (a
negative float literal inside a list literal was emitted as `double -`); it now
builds and matches the C reference. Its ratio is in the results file.

## 6. Roadmap, by expected gain per effort

Ordered by the ladders. Items 1-6 are compiler or runtime work with no change to
the language.

1. **Mark every non-exported program function `static`** (or emit one translation
   unit and use `-fwhole-program` or LTO) in the final binary, keeping the split
   for the case harness only. Largest gain for numeric code, almost no effort.
2. **Make the two build paths emit the same inlining keywords**, so the binary does
   not depend on whether the cache is on.
3. **Cheaper allocation**: one block for a list header plus its first cells; drop
   the arena list for blocks that are freed deterministically; skip the exit-time
   walk; a bump pool for strings.
4. **Cheaper strings**: write numbers directly into a sized string, skip the NUL
   scan for sources known to be NUL-free, a `str_slice` that does one allocation,
   a cached hash in the table.
5. **Free structs** (and the lists in their fields) by the existing escape
   analysis. Removes the multi-gigabyte RSS of tree-shaped programs and the
   page-fault share of their time.
6. **Hoist accessor checks** out of loops over a list that is not reassigned
   (null and lock check once per loop), drop the bounds check where the loop bound
   is `len(xs)`, emit conf scalars as `static const`, and make sqrt and the other
   libm functions intrinsics instead of natives.
7. **Typed storage**: `int[]` as 32-bit cells and `float[]` as unboxed 64-bit, so
   the cache footprint matches C. Compiler work, but see the forks below.

Language-level forks, for the user:

* **Value-type structs** (inline fields instead of a heap list of cells): changes
  the reference semantics of SPEC.md section 1.2, but is what lets a tree node be
  one allocation.
* **Typed lists**: if `int[]` becomes 32-bit cells, anything that reads a list as
  64-bit cells (peek over a list, the native ABI `IdList`) changes.
* **A float intrinsic set** in the language (sqrt, floor, abs) rather than natives.
* **Mutable byte buffers or a string builder type**, so `s = s + x`, `str_slice`
  loops and poke8-plus-`str_of_mem` stop being the way to build text.
* **Range-proved index elision**: no syntax change needed, but a rule such as "a
  loop bounded by `len(xs)` over an unreassigned list" would make it provable.

## 7. Files

`bench/results/results.md` is the harness output of the last run;
`bench/results/attribution.md` is the attribution ladder with the exact commands
that produced it.
