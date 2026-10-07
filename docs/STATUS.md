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
| `bench` | 100 | 219 | 450 | 0 | 0 |
| `c2id` | 716 | 1817 | 3405 | 203 | 0 |
| `demos` | 341 | 761 | 1588 | 0 | 0 |
| `editor` | 155 | 397 | 833 | 0 | 0 |
| `iconcheck` | 5 | 10 | 25 | 0 | 0 |
| `idem` | 1473 | 3600 | 7374 | 0 | 0 |
| `idtheme` | 17 | 44 | 107 | 0 | 0 |
| `kernel` | 103 | 249 | 398 | 0 | 52 |
| `themecheck` | 21 | 59 | 147 | 0 | 0 |
| `trials` | 383 | 920 | 2766 | 0 | 0 |
| `uicheck` | 7 | 19 | 40 | 0 | 0 |
| `word` | 614 | 1467 | 3989 | 0 | 0 |
| `wordcheck` | 74 | 188 | 538 | 0 | 0 |
| `idc/compiler` | 1274 | 3421 | 7330 | 0 | 0 |
| `idc/driver` | 7 | 18 | 36 | 0 | 0 |
| `idc/runtime` | 48 | 89 | 3 | 1 | 87 |
| `idc/tools` | 586 | 1477 | 3688 | 3 | 0 |
| `idstd/core/data` | 46 | 119 | 293 | 0 | 0 |
| `idstd/core/fmt` | 148 | 369 | 1346 | 0 | 0 |
| `idstd/core/math` | 21 | 54 | 137 | 0 | 0 |
| `idstd/core/text` | 85 | 213 | 641 | 0 | 0 |
| `idstd/host/dev` | 131 | 263 | 552 | 1 | 0 |
| `idstd/host/io` | 205 | 377 | 1074 | 0 | 0 |
| `idstd/host/num` | 21 | 19 | 93 | 0 | 0 |
| `idstd/host/os` | 113 | 168 | 420 | 0 | 0 |
| `idstd/kit/app` | 11 | 30 | 76 | 0 | 0 |
| `idstd/kit/media` | 206 | 528 | 1724 | 0 | 0 |
| `idstd/kit/ui` | 336 | 842 | 2631 | 0 | 0 |
| **all** | 7247 | 17737 | 41704 | 208 | 139 |
| of which idstd | 1323 | 2982 | 8987 | 1 | 0 |

*short of two* counts the functions with fewer than two test cases that the compiler does not exempt: a freestanding function that reaches an `asm` body is exempt, and `kernel` and `idc/runtime` are asked of the compiler with the flags `idc/tools/kbuild` builds them with. Functions are found by their headers (`idc/tools/lib/fnhead`) and their cases by `mutscore lint`, not by the compiler's own parse. `idc/tests` is not counted: it holds the inputs of the compiler's own tests, some of which break the rules on purpose. `statusgen --untested [TREE]` lists the functions that are short.

## Cases per function

| tree | 0 cases | 1 | 2 | 3-4 | 5+ |
|---|---:|---:|---:|---:|---:|
| `bench` | 0 | 0 | 208 | 11 | 0 |
| `c2id` | 203 | 0 | 1492 | 110 | 12 |
| `demos` | 0 | 0 | 712 | 45 | 4 |
| `editor` | 0 | 0 | 374 | 20 | 3 |
| `iconcheck` | 0 | 0 | 6 | 4 | 0 |
| `idem` | 0 | 0 | 3483 | 104 | 13 |
| `idtheme` | 0 | 0 | 35 | 6 | 3 |
| `kernel` | 52 | 0 | 195 | 1 | 1 |
| `themecheck` | 0 | 0 | 44 | 11 | 4 |
| `trials` | 0 | 0 | 491 | 317 | 112 |
| `uicheck` | 0 | 0 | 17 | 2 | 0 |
| `word` | 0 | 0 | 932 | 425 | 110 |
| `wordcheck` | 0 | 0 | 94 | 78 | 16 |
| `idc/compiler` | 0 | 0 | 3103 | 287 | 31 |
| `idc/driver` | 0 | 0 | 18 | 0 | 0 |
| `idc/runtime` | 88 | 0 | 0 | 1 | 0 |
| `idc/tools` | 3 | 0 | 1074 | 314 | 86 |
| `idstd/core/data` | 0 | 0 | 93 | 20 | 6 |
| `idstd/core/fmt` | 0 | 0 | 151 | 142 | 76 |
| `idstd/core/math` | 0 | 0 | 34 | 18 | 2 |
| `idstd/core/text` | 0 | 0 | 136 | 43 | 34 |
| `idstd/host/dev` | 1 | 0 | 243 | 17 | 2 |
| `idstd/host/io` | 0 | 0 | 238 | 97 | 42 |
| `idstd/host/num` | 0 | 0 | 4 | 5 | 10 |
| `idstd/host/os` | 0 | 0 | 113 | 47 | 8 |
| `idstd/kit/app` | 0 | 0 | 23 | 5 | 2 |
| `idstd/kit/media` | 0 | 0 | 272 | 166 | 90 |
| `idstd/kit/ui` | 0 | 0 | 483 | 238 | 121 |
| **all** | 347 | 0 | 14068 | 2534 | 788 |
| of which idstd | 1 | 0 | 1790 | 798 | 393 |

A distribution, not a mean: a mean of two is met by one function with many cases beside others with none.

## Shape

| tree | filler dirs | max depth | median depth | silent | echo | bare |
|---|---:|---:|---:|---:|---:|---:|
| `bench` | 0 | 5 | 3 | 4 | 15 | 0 |
| `c2id` | 15 | 11 | 6 | 553 | 509 | 3 |
| `demos` | 2 | 9 | 4 | 47 | 37 | 47 |
| `editor` | 5 | 8 | 5 | 2 | 18 | 41 |
| `iconcheck` | 0 | 1 | 1 | 0 | 0 | 0 |
| `idem` | 26 | 15 | 7 | 11 | 119 | 217 |
| `idtheme` | 0 | 4 | 2 | 0 | 1 | 0 |
| `kernel` | 5 | 8 | 5 | 36 | 5 | 0 |
| `themecheck` | 1 | 4 | 3 | 0 | 6 | 0 |
| `trials` | 4 | 8 | 5 | 3 | 97 | 0 |
| `uicheck` | 0 | 2 | 1 | 3 | 2 | 0 |
| `word` | 16 | 11 | 6 | 1 | 80 | 0 |
| `wordcheck` | 4 | 9 | 5 | 1 | 27 | 0 |
| `idc/compiler` | 67 | 14 | 8 | 130 | 102 | 48 |
| `idc/driver` | 1 | 2 | 1 | 11 | 0 | 0 |
| `idc/runtime` | 5 | 5 | 3 | 0 | 0 | 0 |
| `idc/tools` | 22 | 7 | 4 | 22 | 137 | 3 |
| `idstd/core/data` | 0 | 2 | 1 | 0 | 2 | 0 |
| `idstd/core/fmt` | 0 | 3 | 1 | 0 | 2 | 0 |
| `idstd/core/math` | 0 | 1 | 1 | 0 | 3 | 0 |
| `idstd/core/text` | 0 | 2 | 1 | 0 | 1 | 0 |
| `idstd/host/dev` | 0 | 3 | 3 | 0 | 3 | 0 |
| `idstd/host/io` | 0 | 4 | 2 | 0 | 3 | 0 |
| `idstd/host/num` | 0 | 0 | 0 | 0 | 0 | 0 |
| `idstd/host/os` | 0 | 2 | 1 | 0 | 0 | 0 |
| `idstd/kit/app` | 0 | 2 | 2 | 0 | 0 | 0 |
| `idstd/kit/media` | 0 | 3 | 3 | 0 | 3 | 0 |
| `idstd/kit/ui` | 0 | 3 | 2 | 0 | 3 | 0 |
| **all** | 173 | 15 | 5 | 824 | 1175 | 359 |
| of which idstd | 0 | 4 | 2 | 0 | 20 | 0 |

*filler dirs* are directories named more, rest, tail, cont or partN. *depth* is the number of directories between a tree's root and a source file; *median* is the lower median. *silent*, *echo* and *bare* are the cases `mutscore lint` finds that prove nothing (docs/TESTS.md, "Mutation score").

## Test sections

`idc/tests/run.sh --list` shows the sections and their indices: `core`, `core_self`, `core_rest`, `invalid`, `diagnostics`, `diagnostics_docs` (3 parts), `runtime_invalid`, `self_host_build`, `backends_fs`, `backends_ipc`, `backends_link`, `backends_demos`, `backends_display`, `backends_galaxy`, `backends_galaxy_run`, `stdlib`, `wasm`, `wasm_js`, `wasm_js_std`, `lib`, `lib_csv`, `opt`, `conform` (3 parts), `tests_feature` (5 parts), `fix`, `idstd_real`, `kernel`, `editor`, `mutscore`, `statusgen`, `tmpguard` (22 parts)

## Benchmarks

### Wall time, ratio to gcc-O2 (lower is faster)
| bench | gcc-O2 | gcc-O3n | clang-O2 | rust-O3 | rust-O3n | id-c | id-llvm |
|---|---|---|---|---|---|---|---|
| nbody | 1.00 | 0.95 | 1.02 | 0.61 | 0.55 | 3.00 | FAIL |
| spectral | 1.00 | 1.22 | 1.45 | 1.31 | 1.11 | 2.89 | 5.32 |
| fannkuch | 1.00 | 1.06 | 1.02 | 0.80 | 0.75 | 2.97 | 4.75 |
| mandel | 1.00 | 1.00 | 0.95 | 0.99 | 0.97 | 1.05 | 1.09 |
| btrees | 1.00 | 1.03 | 1.29 | 0.79 | 0.71 | 16.84 | 17.11 |
| fasta | 1.00 | 0.98 | 0.91 | 0.96 | 0.94 | 1.57 | 2.23 |
| knuc | 1.00 | 1.04 | 1.12 | 1.78 | 1.81 | 5.12 | 6.63 |
| sortb | 1.00 | 1.05 | 0.76 | 1.00 | 1.04 | 1.58 | 3.01 |
| strbuild | 1.00 | 1.50 | 1.54 | 1.02 | 1.08 | 8.98 | 9.98 |
| expr | 1.00 | 0.82 | 0.76 | 0.79 | 0.79 | 2.44 | 3.62 |
| csv | 1.00 | 1.00 | 1.09 | 2.03 | 2.03 | 14.43 | 20.66 |
| json | 1.00 | 1.11 | 1.14 | 0.89 | 0.92 | 1.46 | 1.76 |

From `bench/results/results.md`, which the benchmark program `bench/run` writes (docs/PERFORMANCE.md).

## Mutation score

No mutscore results. Run `mutscore run ROOT --out bench/results/mutscore` until it says `0 left`; `mutscore report bench/results/mutscore --tsv` then prints the score this page reads (docs/TESTS.md, "Mutation score").

## Untested functions

`statusgen --untested [TREE]` prints each function with fewer than two cases as `PATH:LINE NAME (N cases)`; the list is not copied here because it changes with every function written.
