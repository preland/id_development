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
| `blocks` | 269 | 622 | 1836 | 0 | 0 |
| `c2id` | 1068 | 2618 | 5211 | 306 | 0 |
| `callgraph` | 50 | 105 | 239 | 0 | 0 |
| `demos` | 336 | 718 | 1539 | 0 | 0 |
| `editor` | 152 | 383 | 815 | 0 | 0 |
| `gym` | 299 | 616 | 2385 | 0 | 0 |
| `iconcheck` | 5 | 10 | 25 | 0 | 0 |
| `idem` | 1473 | 3598 | 7371 | 0 | 0 |
| `idmcp` | 62 | 140 | 550 | 0 | 0 |
| `idtheme` | 18 | 45 | 109 | 0 | 0 |
| `kernel` | 103 | 238 | 392 | 0 | 51 |
| `launcher` | 83 | 187 | 626 | 0 | 0 |
| `quill` | 613 | 1455 | 3972 | 0 | 0 |
| `quillcheck` | 74 | 186 | 538 | 0 | 0 |
| `themecheck` | 22 | 60 | 151 | 0 | 0 |
| `trials` | 383 | 901 | 2754 | 0 | 0 |
| `uicheck` | 7 | 19 | 40 | 0 | 0 |
| `videos` | 272 | 571 | 1475 | 0 | 0 |
| `idc/compiler` | 1471 | 3784 | 8588 | 1 | 0 |
| `idc/driver` | 7 | 18 | 36 | 0 | 0 |
| `idc/runtime` | 49 | 91 | 3 | 1 | 89 |
| `idc/tools` | 630 | 1544 | 4023 | 3 | 0 |
| `idstd/core/data` | 64 | 155 | 423 | 0 | 0 |
| `idstd/core/fmt` | 149 | 360 | 1350 | 0 | 0 |
| `idstd/core/learn` | 12 | 27 | 175 | 0 | 0 |
| `idstd/core/math` | 20 | 52 | 135 | 0 | 0 |
| `idstd/core/text` | 90 | 217 | 749 | 0 | 0 |
| `idstd/host/dev` | 134 | 267 | 573 | 0 | 0 |
| `idstd/host/io` | 207 | 354 | 1033 | 0 | 0 |
| `idstd/host/num` | 21 | 19 | 99 | 0 | 0 |
| `idstd/host/os` | 113 | 164 | 417 | 0 | 0 |
| `idstd/kit/app` | 11 | 30 | 76 | 0 | 0 |
| `idstd/kit/media` | 221 | 559 | 1874 | 0 | 0 |
| `idstd/kit/ui` | 383 | 938 | 2895 | 0 | 0 |
| **all** | 8969 | 21267 | 52925 | 311 | 140 |
| of which idstd | 1425 | 3142 | 9799 | 0 | 0 |

*short of two* counts the functions with fewer than two test cases that the compiler does not exempt: a freestanding function that reaches an `asm` body is exempt, and `kernel` and `idc/runtime` are asked of the compiler with the flags `idc/tools/kbuild` builds them with. Functions are found by their headers (`idc/tools/lib/fnhead`) and their cases by `mutscore lint`, not by the compiler's own parse. `idc/tests` is not counted: it holds the inputs of the compiler's own tests, some of which break the rules on purpose. `statusgen --untested [TREE]` lists the functions that are short.

## Cases per function

| tree | 0 cases | 1 | 2 | 3-4 | 5+ |
|---|---:|---:|---:|---:|---:|
| `bench` | 0 | 0 | 203 | 13 | 0 |
| `blocks` | 0 | 0 | 336 | 219 | 67 |
| `c2id` | 306 | 0 | 1963 | 312 | 37 |
| `callgraph` | 0 | 0 | 90 | 11 | 4 |
| `demos` | 0 | 0 | 657 | 53 | 8 |
| `editor` | 0 | 0 | 358 | 21 | 4 |
| `gym` | 0 | 0 | 203 | 254 | 159 |
| `iconcheck` | 0 | 0 | 6 | 4 | 0 |
| `idem` | 0 | 0 | 3480 | 105 | 13 |
| `idmcp` | 0 | 0 | 43 | 60 | 37 |
| `idtheme` | 0 | 0 | 36 | 6 | 3 |
| `kernel` | 51 | 0 | 180 | 4 | 3 |
| `launcher` | 0 | 0 | 85 | 62 | 40 |
| `quill` | 0 | 0 | 918 | 426 | 111 |
| `quillcheck` | 0 | 0 | 90 | 80 | 16 |
| `themecheck` | 0 | 0 | 44 | 12 | 4 |
| `trials` | 0 | 0 | 465 | 320 | 116 |
| `uicheck` | 0 | 0 | 17 | 2 | 0 |
| `videos` | 0 | 0 | 377 | 165 | 29 |
| `idc/compiler` | 0 | 1 | 3197 | 496 | 90 |
| `idc/driver` | 0 | 0 | 18 | 0 | 0 |
| `idc/runtime` | 90 | 0 | 0 | 1 | 0 |
| `idc/tools` | 3 | 0 | 1064 | 373 | 104 |
| `idstd/core/data` | 0 | 0 | 105 | 37 | 13 |
| `idstd/core/fmt` | 0 | 0 | 139 | 142 | 79 |
| `idstd/core/learn` | 0 | 0 | 1 | 8 | 18 |
| `idstd/core/math` | 0 | 0 | 32 | 17 | 3 |
| `idstd/core/text` | 0 | 0 | 122 | 32 | 63 |
| `idstd/host/dev` | 0 | 0 | 243 | 21 | 3 |
| `idstd/host/io` | 0 | 0 | 222 | 86 | 46 |
| `idstd/host/num` | 0 | 0 | 1 | 8 | 10 |
| `idstd/host/os` | 0 | 0 | 106 | 50 | 8 |
| `idstd/kit/app` | 0 | 0 | 23 | 5 | 2 |
| `idstd/kit/media` | 0 | 0 | 282 | 174 | 103 |
| `idstd/kit/ui` | 0 | 0 | 540 | 271 | 127 |
| **all** | 450 | 1 | 15646 | 3850 | 1320 |
| of which idstd | 0 | 0 | 1816 | 851 | 475 |

A distribution, not a mean: a mean of two is met by one function with many cases beside others with none.

## Shape

| tree | filler dirs | max depth | median depth | silent | echo | bare |
|---|---:|---:|---:|---:|---:|---:|
| `bench` | 0 | 5 | 3 | 4 | 15 | 0 |
| `blocks` | 0 | 2 | 1 | 0 | 6 | 0 |
| `c2id` | 15 | 11 | 5 | 99 | 97 | 3 |
| `callgraph` | 0 | 1 | 1 | 0 | 0 | 0 |
| `demos` | 2 | 9 | 4 | 47 | 31 | 47 |
| `editor` | 5 | 8 | 5 | 2 | 16 | 41 |
| `gym` | 0 | 2 | 1 | 0 | 44 | 0 |
| `iconcheck` | 0 | 1 | 1 | 0 | 0 | 0 |
| `idem` | 26 | 15 | 7 | 11 | 119 | 217 |
| `idmcp` | 0 | 2 | 1 | 2 | 15 | 0 |
| `idtheme` | 0 | 4 | 2 | 0 | 1 | 0 |
| `kernel` | 5 | 8 | 5 | 36 | 3 | 0 |
| `launcher` | 0 | 1 | 1 | 0 | 39 | 0 |
| `quill` | 16 | 11 | 6 | 1 | 79 | 0 |
| `quillcheck` | 4 | 9 | 5 | 1 | 27 | 0 |
| `themecheck` | 1 | 4 | 3 | 0 | 6 | 0 |
| `trials` | 4 | 8 | 5 | 3 | 90 | 0 |
| `uicheck` | 0 | 2 | 1 | 3 | 1 | 0 |
| `videos` | 0 | 2 | 1 | 0 | 75 | 0 |
| `idc/compiler` | 67 | 14 | 8 | 131 | 104 | 48 |
| `idc/driver` | 1 | 2 | 1 | 11 | 0 | 0 |
| `idc/runtime` | 5 | 5 | 3 | 0 | 0 | 0 |
| `idc/tools` | 22 | 7 | 4 | 20 | 148 | 3 |
| `idstd/core/data` | 0 | 2 | 1 | 0 | 4 | 0 |
| `idstd/core/fmt` | 0 | 3 | 1 | 0 | 5 | 0 |
| `idstd/core/learn` | 0 | 0 | 0 | 0 | 1 | 0 |
| `idstd/core/math` | 0 | 1 | 1 | 0 | 3 | 0 |
| `idstd/core/text` | 0 | 2 | 1 | 0 | 1 | 0 |
| `idstd/host/dev` | 0 | 3 | 3 | 0 | 4 | 0 |
| `idstd/host/io` | 0 | 4 | 2 | 0 | 3 | 0 |
| `idstd/host/num` | 0 | 0 | 0 | 0 | 0 | 0 |
| `idstd/host/os` | 0 | 2 | 1 | 0 | 0 | 0 |
| `idstd/kit/app` | 0 | 2 | 2 | 0 | 0 | 0 |
| `idstd/kit/media` | 0 | 3 | 3 | 0 | 2 | 0 |
| `idstd/kit/ui` | 0 | 3 | 2 | 0 | 3 | 0 |
| **all** | 173 | 15 | 5 | 371 | 942 | 359 |
| of which idstd | 0 | 4 | 2 | 0 | 26 | 0 |

*filler dirs* are directories named more, rest, tail, cont or partN. *depth* is the number of directories between a tree's root and a source file; *median* is the lower median. *silent*, *echo* and *bare* are the cases `mutscore lint` finds that prove nothing (docs/TESTS.md, "Mutation score").

## Test sections

`idc/tests/run.sh --list` shows the sections and their indices: `core`, `core_parse`, `core_guard`, `core_self`, `core_rest`, `invalid_1of4`, `invalid_2of4`, `invalid_3of4`, `invalid_4of4`, `diagnostics`, `diagnostics_docs` (3 parts), `runtime_invalid`, `self_host_build_demos`, `self_host_build_link`, `self_host_build_project` (3 parts), `self_host_build_stage0`, `self_host_build_boot_cold`, `self_host_build_expr`, `backends_fs`, `backends_fs_list`, `backends_ipc`, `backends_link`, `backends_link_lib`, `backends_link_att`, `backends_link_pkg`, `backends_link_gfx`, `backends_demos`, `backends_display`, `backends_galaxy`, `backends_galaxy_run`, `stdlib_import`, `stdlib_dce`, `stdlib_precheck`, `wasm`, `wasm_js`, `wasm_js_std`, `lib`, `lib_csv`, `opt`, `conform_eprint`, `conform_float`, `conform_flow`, `conform_fn`, `conform_free`, `conform_int`, `conform_list_1of2`, `conform_list_2of2`, `conform_order`, `conform_store`, `conform_str`, `conform_struct`, `conform_trap`, `conform_closure`, `conform_const`, `tests_feature` (5 parts), `fix`, `idstd_real` (3 parts), `kernel_build`, `kernel_boot`, `kernel_kfree`, `editor`, `mutscore`, `statusgen`, `tmpguard` (22 parts)

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
