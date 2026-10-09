# Status

> **Status: generated.** Written by `statusgen --write` from the working tree, never by hand. A number that changes belongs here and nowhere else: other documents point to this page or to the command that prints the number.

Regenerate it from the checkout root, with `IDSTD_HOME` set when the standard library is not beside the checkout:

```
idc/bin/idc idc/tools/statusgen -o statusgen
./statusgen --write
```

`idc/tests/run.sh statusgen` fails when this page is not what `statusgen` prints now, so a merge that changes a count also regenerates the page.

## Trees

| tree | files | functions | cases | short of two | exempt |
|---|---:|---:|---:|---:|---:|
| `bench` | 98 | 216 | 448 | 0 | 0 |
| `c2id` | 1068 | 2618 | 5211 | 306 | 0 |
| `demos` | 336 | 718 | 1539 | 0 | 0 |
| `editor` | 152 | 383 | 815 | 0 | 0 |
| `iconcheck` | 5 | 10 | 25 | 0 | 0 |
| `idem` | 1473 | 3600 | 7374 | 0 | 0 |
| `idtheme` | 18 | 45 | 109 | 0 | 0 |
| `kernel` | 103 | 238 | 392 | 0 | 51 |
| `themecheck` | 22 | 60 | 151 | 0 | 0 |
| `trials` | 383 | 901 | 2754 | 0 | 0 |
| `uicheck` | 7 | 19 | 40 | 0 | 0 |
| `videos` | 272 | 575 | 1485 | 0 | 0 |
| `word` | 613 | 1457 | 3976 | 0 | 0 |
| `wordcheck` | 74 | 186 | 538 | 0 | 0 |
| `idc/compiler` | 1399 | 3609 | 8084 | 0 | 0 |
| `idc/driver` | 7 | 18 | 36 | 0 | 0 |
| `idc/runtime` | 49 | 91 | 3 | 1 | 89 |
| `idc/tools` | 584 | 1433 | 3678 | 3 | 0 |
| `idstd/core/data` | 49 | 118 | 296 | 0 | 0 |
| `idstd/core/fmt` | 148 | 358 | 1336 | 0 | 0 |
| `idstd/core/math` | 20 | 52 | 135 | 0 | 0 |
| `idstd/core/text` | 88 | 215 | 734 | 0 | 0 |
| `idstd/host/dev` | 134 | 267 | 573 | 0 | 0 |
| `idstd/host/io` | 202 | 348 | 1018 | 0 | 0 |
| `idstd/host/num` | 21 | 19 | 99 | 0 | 0 |
| `idstd/host/os` | 113 | 163 | 412 | 0 | 0 |
| `idstd/kit/app` | 11 | 30 | 76 | 0 | 0 |
| `idstd/kit/media` | 208 | 527 | 1735 | 0 | 0 |
| `idstd/kit/ui` | 336 | 829 | 2612 | 0 | 0 |
| **all** | 7993 | 19103 | 45684 | 310 | 140 |
| of which idstd | 1330 | 2926 | 9026 | 0 | 0 |

*short of two* counts the functions with fewer than two test cases that the compiler does not exempt: a freestanding function that reaches an `asm` body is exempt, and `kernel` and `idc/runtime` are asked of the compiler with the flags `idc/tools/kbuild` builds them with. Functions are found by their headers (`idc/tools/lib/fnhead`) and their cases by `mutscore lint`, not by the compiler's own parse. `idc/tests` is not counted: it holds the inputs of the compiler's own tests, some of which break the rules on purpose. `statusgen --untested [TREE]` lists the functions that are short.

## Cases per function

| tree | 0 cases | 1 | 2 | 3-4 | 5+ |
|---|---:|---:|---:|---:|---:|
| `bench` | 0 | 0 | 203 | 13 | 0 |
| `c2id` | 306 | 0 | 1963 | 312 | 37 |
| `demos` | 0 | 0 | 657 | 53 | 8 |
| `editor` | 0 | 0 | 358 | 21 | 4 |
| `iconcheck` | 0 | 0 | 6 | 4 | 0 |
| `idem` | 0 | 0 | 3483 | 104 | 13 |
| `idtheme` | 0 | 0 | 36 | 6 | 3 |
| `kernel` | 51 | 0 | 180 | 4 | 3 |
| `themecheck` | 0 | 0 | 44 | 12 | 4 |
| `trials` | 0 | 0 | 465 | 320 | 116 |
| `uicheck` | 0 | 0 | 17 | 2 | 0 |
| `videos` | 0 | 0 | 379 | 167 | 29 |
| `word` | 0 | 0 | 920 | 426 | 111 |
| `wordcheck` | 0 | 0 | 90 | 80 | 16 |
| `idc/compiler` | 0 | 0 | 3098 | 440 | 71 |
| `idc/driver` | 0 | 0 | 18 | 0 | 0 |
| `idc/runtime` | 90 | 0 | 0 | 1 | 0 |
| `idc/tools` | 3 | 0 | 1018 | 320 | 92 |
| `idstd/core/data` | 0 | 0 | 88 | 24 | 6 |
| `idstd/core/fmt` | 0 | 0 | 139 | 141 | 78 |
| `idstd/core/math` | 0 | 0 | 32 | 17 | 3 |
| `idstd/core/text` | 0 | 0 | 122 | 32 | 61 |
| `idstd/host/dev` | 0 | 0 | 243 | 21 | 3 |
| `idstd/host/io` | 0 | 0 | 217 | 86 | 45 |
| `idstd/host/num` | 0 | 0 | 1 | 8 | 10 |
| `idstd/host/os` | 0 | 0 | 107 | 48 | 8 |
| `idstd/kit/app` | 0 | 0 | 23 | 5 | 2 |
| `idstd/kit/media` | 0 | 0 | 269 | 166 | 92 |
| `idstd/kit/ui` | 0 | 0 | 467 | 241 | 121 |
| **all** | 450 | 0 | 14643 | 3074 | 936 |
| of which idstd | 0 | 0 | 1708 | 789 | 429 |

A distribution, not a mean: a mean of two is met by one function with many cases beside others with none.

## Shape

| tree | filler dirs | max depth | median depth | silent | echo | bare |
|---|---:|---:|---:|---:|---:|---:|
| `bench` | 0 | 5 | 3 | 4 | 15 | 0 |
| `c2id` | 15 | 11 | 5 | 99 | 97 | 3 |
| `demos` | 2 | 9 | 4 | 47 | 31 | 47 |
| `editor` | 5 | 8 | 5 | 2 | 16 | 41 |
| `iconcheck` | 0 | 1 | 1 | 0 | 0 | 0 |
| `idem` | 26 | 15 | 7 | 11 | 119 | 217 |
| `idtheme` | 0 | 4 | 2 | 0 | 1 | 0 |
| `kernel` | 5 | 8 | 5 | 36 | 3 | 0 |
| `themecheck` | 1 | 4 | 3 | 0 | 6 | 0 |
| `trials` | 4 | 8 | 5 | 3 | 90 | 0 |
| `uicheck` | 0 | 2 | 1 | 3 | 1 | 0 |
| `videos` | 0 | 2 | 1 | 0 | 75 | 0 |
| `word` | 16 | 11 | 6 | 1 | 79 | 0 |
| `wordcheck` | 4 | 9 | 5 | 1 | 27 | 0 |
| `idc/compiler` | 67 | 14 | 8 | 125 | 95 | 48 |
| `idc/driver` | 1 | 2 | 1 | 11 | 0 | 0 |
| `idc/runtime` | 5 | 5 | 3 | 0 | 0 | 0 |
| `idc/tools` | 22 | 7 | 4 | 20 | 133 | 3 |
| `idstd/core/data` | 0 | 2 | 1 | 0 | 4 | 0 |
| `idstd/core/fmt` | 0 | 3 | 1 | 0 | 2 | 0 |
| `idstd/core/math` | 0 | 1 | 1 | 0 | 3 | 0 |
| `idstd/core/text` | 0 | 2 | 1 | 0 | 1 | 0 |
| `idstd/host/dev` | 0 | 3 | 3 | 0 | 4 | 0 |
| `idstd/host/io` | 0 | 4 | 2 | 0 | 3 | 0 |
| `idstd/host/num` | 0 | 0 | 0 | 0 | 0 | 0 |
| `idstd/host/os` | 0 | 2 | 1 | 0 | 0 | 0 |
| `idstd/kit/app` | 0 | 2 | 2 | 0 | 0 | 0 |
| `idstd/kit/media` | 0 | 3 | 3 | 0 | 2 | 0 |
| `idstd/kit/ui` | 0 | 3 | 2 | 0 | 3 | 0 |
| **all** | 173 | 15 | 5 | 363 | 810 | 359 |
| of which idstd | 0 | 4 | 2 | 0 | 22 | 0 |

*filler dirs* are directories named more, rest, tail, cont or partN. *depth* is the number of directories between a tree's root and a source file; *median* is the lower median. *silent*, *echo* and *bare* are the cases `mutscore lint` finds that prove nothing (docs/TESTS.md, "Mutation score").

## Test sections

`idc/tests/run.sh --list` shows the sections and their indices: `core`, `core_self`, `core_rest`, `invalid`, `diagnostics`, `diagnostics_docs` (3 parts), `runtime_invalid`, `self_host_build`, `backends_fs`, `backends_ipc`, `backends_link`, `backends_link_lib`, `backends_link_att`, `backends_link_pkg`, `backends_link_gfx`, `backends_demos`, `backends_display`, `backends_galaxy`, `backends_galaxy_run`, `stdlib`, `wasm`, `wasm_js`, `wasm_js_std`, `lib`, `lib_csv`, `opt`, `conform` (3 parts), `tests_feature` (5 parts), `fix`, `idstd_real`, `kernel`, `editor`, `mutscore`, `statusgen`, `tmpguard` (22 parts)

## Benchmarks

### Wall time, ratio to gcc-O2 (lower is faster)
| bench | gcc-O2 | gcc-O3n | clang-O2 | rust-O3 | rust-O3n | id-c | id-llvm |
|---|---|---|---|---|---|---|---|
| nbody | 1.00 | 0.94 | 0.88 | 0.66 | 0.61 | 1.03 | 2.71 |
| spectral | 1.00 | 1.00 | 1.23 | 1.46 | 1.41 | 1.00 | 1.29 |
| fannkuch | 1.00 | 1.10 | 1.04 | 0.80 | 0.79 | 1.09 | 2.10 |
| mandel | 1.00 | 1.00 | 0.98 | 0.98 | 0.98 | 0.99 | 0.81 |
| btrees | 1.00 | 1.00 | 1.13 | 0.75 | 0.75 | 3.13 | 3.71 |
| fasta | 1.00 | 0.98 | 0.85 | 0.88 | 0.85 | 1.04 | 1.13 |
| knuc | 1.00 | 1.00 | 1.04 | 1.32 | 1.31 | 3.95 | 4.34 |
| sortb | 1.00 | 1.00 | 0.80 | 1.00 | 1.03 | 1.34 | 1.89 |
| strbuild | 1.00 | 1.00 | 1.00 | 0.75 | 0.77 | 3.14 | 3.68 |
| expr | 1.00 | 0.82 | 0.77 | 0.82 | 0.82 | 1.00 | 1.45 |
| csv | 1.00 | 1.00 | 1.10 | 2.14 | 2.14 | 6.10 | 6.38 |
| json | 1.00 | 0.96 | 0.96 | 0.81 | 0.81 | FAIL | FAIL |

From `bench/results/results.md`, which the benchmark program `bench/run` writes (docs/PERFORMANCE.md).

## Mutation score

No mutscore results. Run `mutscore run ROOT --out bench/results/mutscore` until it says `0 left`; `mutscore report bench/results/mutscore --tsv` then prints the score this page reads (docs/TESTS.md, "Mutation score").

## Untested functions

`statusgen --untested [TREE]` prints each function with fewer than two cases as `PATH:LINE NAME (N cases)`; the list is not copied here because it changes with every function written.
