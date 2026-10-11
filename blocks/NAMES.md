# Names in `blocks`

id keeps one namespace for functions and one type per variable name across the
whole program, idstd included (E0303, E0402). So everything here is spelled with
a prefix no idstd name uses (checked against `idstd/NAMES.md`: no `bk*` prefix
is in it).

| prefix | what | directory |
| --- | --- | --- |
| `bkk_` | constants (`conf.id`) | `conf.id` |
| `bk_` | every parameter and local; the compiler is the registry: a clash is E0303 at the second declaration | everywhere |
| `bkl_` | the tokenizer | `lex/` |
| `bkm_` | the model: tables of sprites, variables, functions, cases and diagnostics, and the loader | `model/` |
| `bkc_` | the rule checker | `rules/` |
| `bkg_` | the code generator: type checking and compiling to instructions | `gen/` |
| `bkv_` | the virtual machine, scheduler, `show` and `dump` | `vm/` |
| `bkr_` | running a program and its test cases (generated `.blk` text) | `run/` |
| `bkx_` | the command line | `cli/` |
| `exporter_` | the export to id (`blocks export`): the tree of files, each function's id text, the variables' setters and getters, the runtime texts. Its constants are `constant_export_*`, `constant_template_*` and `constant_runtime_*`; its parameters and locals are `exporter_text_*` (string), `exporter_number_*` (int), `exporter_texts_*` (string[]) | `export/` |
| `bke_` | the block editor: the document as lines, its layout, the palette, the session and its reducer, the painting, the window loop, the script replay | `edit/doc`, `edit/lay`, `edit/pal`, `edit/ses`, `edit/paint`, `edit/win`, `edit/script` |

Exported tables (declared by an init function, read as `(import NAME)`):
`bkm_*` by `bkm_init` (the list is in `model/tables.id`), `bkg_cd bkg_ft bkg_kf
bkg_ks bkg_sn bkg_sl bkg_sy bkg_brk bkg_st` by `bkg_init`, `bkv_vl bkv_gl bkv_ls
bkv_sp bkv_th bkv_cs bkv_sx bkv_out bkv_rg bkv_rv` by `bkv_boot`.

The read-backs (`bkm_dgs`, `bkg_codes`, `bkg_syms`, `bkg_breaks`, `bkv_ths`,
`bkv_outs`, `bkv_regs`) exist only so that cases of functions that reach a table
through a callee have something to name in `then`.

Local names carry one type each program-wide. The habits: `bk_i bk_j bk_k bk_n
bk_c bk_e bk_d bk_a bk_b bk_x bk_p bk_q` are ints (`bk_f` a function row, `bk_t` a
thread or a temporary slot, `bk_fp` a frame pointer); `bk_fv bk_fa bk_fb` are
floats; `bk_ts bk_as bk_ps bk_ms bk_env bk_nn bk_c1` are `string[]`; `bk_vl bk_gl
bk_kf bk_sxl bk_sx` are `float[]`; `bk_th bk_cstk bk_ft bk_tp bk_cnt` are `int[]`;
`bk_pl` is `float[][]`; `bk_pool` is `string[]`; `bk_line bk_tok bk_text bk_nm
bk_sig bk_tyn bk_kw bk_out` are strings. When a new name would break one of
these, the compiler says so at the declaration.

## The editor (`edit/`)

Its functions are `bke_` (the command line's `bkx_`), its constants `bkk_` like the
rest. Its parameters and locals carry their type in the name, so that a name never has
two types: `bei_` an int, `bes_` a string, `bel_` an int list, `bet_` a string
list, `bem_` a list of int lists, `bes_s` a list of string lists (`bes_s`, `bem_s`
and `bem_lo` are a session's text lists, int lists and layout), after the letter
`k` or the word that says what it holds (`bei_k`, `bei_ind`, `bes_line`). The command
line's own names are `bk_` like the other commands'.

A session is three bundles: `bes_s` (conf.id `bkk_z_`: document, violations, the text
being typed, the palette's blocks, the texts of the layout's boxes, sprite names, what
they said, the file's path), `bem_s` (`bkk_y_`: the state, the line of each violation,
whether each palette block is a reporter, the stage as five numbers a sprite) and
`bem_lo` (the layout, `bkk_l_`). The state is `bkk_s_` cells after the graph kit's
`graph_view_state_` ones. `bke_event(bes_s, bem_s, bem_lo, kind, a, b, c, d)` is pure and answers
`bkk_e_` bits; `bke_step` also does what the bits ask.

Exported names are the test fixtures' and exist only in cases: `bke_t_doc`, `bke_t_lo`,
`bke_t_tx`, `bke_t_cur` (`bke_t_open`), `bke_t_sdoc`, `bke_t_slo`, `bke_t_stx`
(`bke_t_laid`), `bke_t_st` (`bke_t_blank`), `bke_t_bes`, `bke_t_bem`, `bke_t_blo`
(`bke_t_session`).
