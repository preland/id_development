# word/ vocabulary

`word/` is one compilation unit, so a variable or parameter name has one type across the whole tree (docs/PROJECT.md section 5, pitfall 6) and function names are program-wide. Struct field names are scoped to their struct and do not count.

This file records what `word/core/doc` (B1) already uses. Reuse the same name for the same type, and pick another name where your type needs one that is taken.

## Names taken, by type

| type | names |
| --- | --- |
| `Doc` | `d` |
| `Body` | `b` |
| `Fmt` | `f` |
| `Para` | `p`, `np` |
| `Para[]` | `pl` |
| `Text` | `t`, `u`, `nt` |
| `Tab` | `tb`, `chars`, `tc`, `tp` |
| `Pos` | `pa`, `pb` (not `p`: that is a `Para`) |
| `Run` | `ru`, `rv`, `nr`, `cur`, `head` |
| `Run[]` | `rs`, `tr`, `src`, `dst` |
| `Style`, `Sty`, `ListDef`, `Page`, `Ext`, `Lay`, `Model` | `st`, `sy`, `ld`, `pg`, `x`, `ly`, `mo` |
| `int[]` | `cps`, `runs`, `row`, `rows`, `rg`, `sx`, `sp`, `wr`, `acc`, `ins`, `fm`, `vs`, `ws`, `none`, `sls`, `fc`, `fp`, `fl`, `lines`, `pen`, `rel`, `size`, `margin`, `hf`, `levels` |
| `string` | `name`, `text`, `font` |
| `int` | every other short name used as a loop counter, offset or result: `i j k n m w h id at off lo hi cp cprop pprop field value key val bits on mode kind which code lk res got sn ia iz begin same` |

## Where the seams of docs/WORD.md collide with that

* 4.2 `Fmt f` and 4.4 `face_for(Face f, Fmt fmt, ...)`: `f` is a `Fmt` here, so a `Face` needs another name.
* 4.2 `Tab t` is `tb` here, because `t` is a `Text`.
* 4.3 and 4.4 `Pos p` collides with `Para p`: use `ps` or another name for a `Pos`.
* 4.4 `View v`, 4.8 `Ribbon r`, `App a`, 4.3 `Sel s`, and `Pos from`, `Pos hit`, `Pos out`: B1 has none of `v r a s from hit out` as a variable name.

## Prefixes

`doc_ para_ pos_ tab_ fmt_ style_ text_ body_ page_ ext_ paras_ run_ rs_ runs_ cps_ tab_ flag_` belong to the model; `op_ rng_ rand_ flat_ model_ script_ dump_` belong to its checks and the seeded script.

## Ribbon (B7a, `ui/ribbon/model`)

Its constants in conf.id sit between the `B7a begin/end` markers. Its tab ids are `rib_tab_file rib_tab_home rib_tab_insert rib_tab_layout rib_tab_view rib_tab_qat`, not `tab_*`, because `tab_` is the model's function prefix (`tab_home` is a function there).

Where the ribbon needed a name the model already holds for another type it took an `r` prefixed one:

| name | type | instead of |
| --- | --- | --- |
| `rrow` | `int` (a row of the `rb_*` tables) | `row`, an `int[]` in the model |
| `rhead` | `string` (a tooltip head) | `head`, a `Run` |
| `rpa`, `rpb` | `int[]` (id lists) | `pa`, `pb`, a `Pos` |
| `rp` | `int` (a rect offset) | `p`, a `Para` |
| `rst` | `int[]` (a group step) | `st`, a `Style` |
| `rcur` | `int[]` (a cursor per row) | `cur`, a `Run` |
| `rx` | `int` | `x`, an `Ext` |

## Edit core (B2, `core/edit`)

Its constants in conf.id sit between the `B2 begin/end` markers (`ed_k_*` operation kinds, `ed_u_*` move units, `ed_f_*` find flags, `ed_s_*` sel_state fields, `ed_g_margin`, and the test tables `ed_t_*`). Function prefixes: `ed_` for commands and their helpers, `op_ ap_` for the primitives, `hist_ txn_ typing_` for history, `sel_ pos_ para_ cp_ cps_` for selection and the word rule, `find_ rep_ smp_ fmt_ clip_ frag_` for the rest, and `fx_` for test fixtures (they live in the tree, under `core/edit/use/test`).

The seam of docs/WORD.md 4.3 names a `Ctl` `c`, a `Sel` `s`, a `Pos` `p` and `from`, `hit`, which collide with the model's and the ribbon's names. What B2 used instead:

| name | type | instead of |
| --- | --- | --- |
| `ctl` | `Ctl` | `c` |
| `sel`, `nsel`, `orig`, `tmp` | `Sel` | `s`, and `from` |
| `ps`, `pq`, `pa`, `pb` | `Pos` | `p`, and `res` for a result (the model's `res` is an `int`) |
| `spot` | `Pos` (where find_next writes) | `hit` (an `int` in the ribbon) and `found` (an `int` in the model) |
| `from` | `Pos` (where find_next starts) | |
| `eo`, `inv` | `Op` | `op` (the model has functions `op_*`) |
| `invs`, `ops` | `Op[]` | |
| `tx`, `rt` | `Txn` | `nt` (a `Text`) |
| `take`, `give`, `undo`, `redo`, `stack` | `Txn[]` | `from`, `to` |
| `hs`, `frag` | `Hist`, `Frag` | `fr` (an `int[]` in the ribbon) |
| `again` | `int` (redo or undo) | `redo` (a `Txn[]`) |
| `loc`, `dat`, `old`, `snap`, `kp`, `acc`, `cells`, `ofs`, `fix` | `int[]` | `at`, `data`, `out`, `ls`, `st` |
| `act` | a function value | `f` (a `Fmt`) |
| `pieces`, `flds` | `string[]` | `lines`, `parts`, `f` |
| `argt`, `plain` | `string` | `rest` (an `int[]`) |
| `actual`, `want`, `dump0..dump3`, `fresh` | test fixtures | `got`, `have`, `before` |
| `lcp`, `rcp` | `int` | `a`, `b` (a `Body`) |
| `on`, `val`, `got`, `cont`, `nrun`, `isflag`, `back`, `step`, `hp` | `int` | `st` (a `Style`), `nr` (a `Run`) |
## One-paragraph layout (B3a, `core/lay/para`)

Prefixes: `face_` (the face cache and its resolvers), `lay_para lay_label lay_label_x lay_number` (the public calls), `lp_` (internals of the paragraph pass), `lp_t_` (test fixtures and their exports: `lp_t_d lp_t_f lp_t_v lp_t_h9 lp_t_h16 lp_t_h32 lp_t_cb lp_t_cs lp_t_cd lp_t_cz`). Its constants in conf.id sit between the `B3a begin/end` markers: `word_lay_* word_cp_* word_al_* word_ln_*`.

`core/lay/type/` holds the structs `Face`, `Pages` and `View` of docs/WORD.md 4.4; `gui_face`, `gui_face_file` and `gui_cp_adv` are idstd's (package A3b), and the ascent and descent of a face are `gui_font_ascent` and `gui_font_descent`, since a face is a font handle.

| name | type | instead of |
| --- | --- | --- |
| `fa` | `Face` | `f`, a `Fmt` |
| `v` | `View` | |
| `fh` | `int` (a font handle) | `f` |
| `fi` | `int` (an index into `ext.fonts`) | `font`, a `string` |
| `fs` | `int` (bold and italic bits) | `st`, a `Style` |
| `lid`, `lvl` | `int` (list id, list level) | `ls` and `lv`, a `ListDef[]` and an `int[]` |
| `lf` | `int` (a list format) | `fmt` |
| `xp` | `int` (a pen x) | `x`, an `Ext` |
| `res` | `int` | `d`, a `Doc` |
| `got`, `tot`, `ns`, `cnt`, `rem` | `int` | `a`, `s`, `c`, `r` |
| `rb`, `ri`, `re` | `int` (run start, run index, run end) | `rs`, a `Run[]` |
| `lbl` | `int[]` (a label's code points) | `cl`, an `int` (the class of a code point, B2) |
| `pgs`, `keys`, `hnd`, `starts`, `tops` | `Pages`, `int[]` | `pg`, a `Page`; `key`, an `int` |

## What `lay_para` leaves in `Lay`, for B3b and B6

* `lines`: six ints per line, `word_ln_*`: `[lo, hi, y, asc, desc, width]`. `y` is the top of the line from the top of the paragraph, so the first line's `y` is the space before. `asc` already contains the extra leading of a line spacing above 100 percent, so the baseline is `y + asc` and the line is `asc + desc` tall. `width` is the used width without the trailing spaces, and the text area's width for a justified line that is not the last.
* `pen`: `len(cps) + 1` entries, x in lu from the left edge of the text area, indents, alignment and justification included. The extra last entry is the x after the last code point, so a caret at the end of the paragraph has an x even when the paragraph ends in spaces. The entry `pen[hi]` of a line that is not the last is the start of the next line, not the end of this one; the end of the visible text of a line is `pen[lo] + width`.
* `h`: space before, every line, space after.
* A list item's label is not in `pen`: `lay_label` fills a list the caller owns, drawn in the face of the paragraph's first run at `lay_label_x`.
## ODT content reader (B4a, `io/odt/read/content`)

Prefixes: `odt_` is the seam of docs/WORD.md 4.6 (`odt_load`, `odt_load_bytes`, `odt_error`), `orc_` is everything else the reader owns, `orc_t_` is its test fixtures, and `cli_` is `word --text` (`ui/app/cli`). Its constants sit in conf.id between the `B4a begin/end` markers.

One export is new: `odt_why`, a string that `odt_load` and `odt_load_bytes` set (to "" when they start) and that `odt_error` puts in brackets after its message for the codes that carry a detail (1 path, 2 zip reason, 3 XML fault with its byte offset, 5 mimetype found). A code alone could not carry the byte offset 4.6 asks for.

What the reader keeps in `ext.parts` (docs/WORD.md 3.1.6), all of it as it is in the file:

| part name | kind | what it is |
| --- | --- | --- |
| the element name (`table:table`, `draw:frame`) | 0 | an opaque element. A block (a `kind == 1` paragraph) or an object inside a paragraph holds the code point `word_o_marker + index`; the paragraph of a block reads that marker and then a label (`[Table]`) |
| `text:sequence-decls`, `text:variable-decls`, `text:user-field-decls`, `text:dde-connection-decls`, `text:tracked-changes` | 0 | declarations that open `office:text`; no marker points at them, and the writer puts them back first |
| `auto:NAME` | 0 | the automatic style (`style:style`, `text:list-style`, ...) of content.xml that an opaque element names, kept once, for `office:automatic-styles` |
| the zip entry name (`Pictures/a.png`, `settings.xml`, `Configurations2/`) | 1 | an entry the model does not read itself |

`word_o_marker` is the code point of B5a's marker too; it is declared once in conf.id, in the B4a section.

Names this reader had to avoid because the model holds them for another type: `cs` (an `int` in the model, so the `Cs` is `cst`), `ls` (a `ListDef[]`; the link targets are `hrefs`), `lk` (an `int`; `lkeys`), `ws` (`isws`), `last` (`lastrun`), `key` (`skey`), `sty` (`sid`), `parts` and `lines` (`pieces`, `texts`), `src` (`bytes`), `out` (`ended`).

| name | type |
| --- | --- |
| `cx` | `Cx` (the read: `rd`, `d`, `cs`) |
| `rd` | `XmlR` |
| `cst` | `Cs` (`pstyles`, `lstyles`, `slots`) |
| `nm`, `pnm`, `lnm` | `Names` |
| `ev`, `at`, `k`, `kind`, `lvl`, `lev`, `rw`, `pp`, `idx`, `base`, `shut` | `int` |
| `sname`, `skey`, `href` | `string` |
| `hrefs`, `knames`, `pieces`, `texts` | `string[]` |
| `z`, `pt` | `Zip`, `Part` |
## ODT styles reader (B4b, `io/odt/read/styles`)

Functions are `ost_*` (the reader and the lookup B4a calls) and `ndump_*` (the normalised dump, docs/WORD.md 4.9a); test fixtures are `ost_t_*`. Every variable and parameter starts with `os_` and carries its type in the next letter, so none of them can collide with another package's names: `os_i*` an int (`os_ik`, `os_ibit`), `os_s*` a string (`os_sv`, `os_sname`), `os_l*` an `int[]` or `string[]` list (`os_lcrow`, `os_lface`), `os_w*` a `word[]`, `os_x*` a word, and by type `os_r` an `XmlR`, `os_b` a `StyBag`, `os_pg` a `PgTab`, `os_k` an `OdtSty`, `os_d` a `Doc`, `os_f` a `Fmt`, `os_p` a `Para`, `os_ru` a `Run`, `os_page` a `Page`. The one name shared with the model is `i`, an int loop counter.

Structs: `StyBag` (the styles of a document before they are in the model), `PgTab` (page layouts and master pages), `OdtSty` (what the content reader asks). Constants in `conf.id` between the `B4b` markers: `ost_bad ost_units ost_unum ost_uden ost_cattr ost_pattr ost_pct_base ost_s_* ost_cdef ost_pdef ost_pgdef ost_gattr ost_e_styles ost_e_content`.
## ODT content writer (B5a, `io/odt/write/content`)

Functions: `oc_*` (internal) and `odt_content_bytes`, `odt_content_check` (the seam). Fixtures: `oc_t_*`. Every variable and parameter is prefixed `oc_`, so none can collide with another package's names:

| type | names |
| --- | --- |
| `XmlW` | `oc_w` (export `oc_fw` in the fixtures) |
| `Doc` | `oc_d` (export `oc_xd`) |
| `Text`, `Ext`, `Para`, `Run`, `Tab` | `oc_tx`, `oc_ex`, `oc_pa`, `oc_ru`, `oc_tb` |
| `int[]` | `oc_cps`, `oc_ls` (list state `[open levels, list definition]`), `oc_pm`, `oc_cm` (rows in use), `oc_rw`, `oc_lvl`, `oc_bs` |
| `string` | `oc_nm`, `oc_an`, `oc_el`, `oc_s`, `oc_cv`, `oc_why` |

Automatic styles are named `WP<row>`, `WT<row>`, `WL<list>` (not LibreOffice's `P1`, `T1`, `L1`) so they never collide with the verbatim automatic styles a preserved block brings along (a table's `Table1.A1`, a frame's `P1` and `gr1`).
## ODT package writer (B5b, `io/odt/write/package`)

Functions are `odp_` (parts and archive), `odw_` (save entry points and codes 100 to 199) and the `odp_t_`/`odw_t_` test fixtures; its constants in conf.id sit between the `B5b begin/end` markers. Every variable and parameter of the package starts with `pk`, so that it cannot meet a model name of another type. The ones the other packages are most likely to meet: `pkw` is an `XmlW`, `pkz` a `ZipW`, `pkd` a `Doc`, `pkx` an `Ext`, `pkpg` a `Page`, `pksy` a `Style`, `pkpt` a `Part`, `pkby` an `int[]` of bytes, `pknames` a `string[]`.

## The merge of wave 2

Variable names that two packages gave two types were renamed in the one that had fewer uses: B3a's label list `cl` is `lbl` (B2's `cl` is the class of a code point); B2's `Doc fresh` is `nd` and its `int pv` is `pcl` (B4a's `fresh` is an `int` and its `pv` an `int[]`); B4a's `int v` is `val`, its `Part[] ps` is `pts` and its `int from` is `off` (B3a's `v` is a `View`, B2's `ps` a `Pos` and `from` a `Pos`). `style_bits` (B1) folds the layers into one int, `fold`, the flags decided so far in its low 8 bits and the bits that are decided from bit 8 up, with the locals `seen`, `add`, `nxt` and `kept`.

Error codes of `odt_error`: 1 to 6 are B4a's, 50 and 51 are B4b's (`ost_error`, with the byte of the fault as the detail), 100 to 102 are B5b's (`odw_error`).

## The viewer (V1, `ui/view`, `core/lay/page`)

`core/lay/page` is the seed of B3b's pagination: `lay_view` (a View), `lay_all` (every paragraph laid out in the text area's width), `lay_paginate` (fills `Pages`: `starts` holds a page's paragraph and line, two cells a page, and one more pair that ends the last page; `tops` holds each paragraph's top in the continuous document, pages one sheet and `word_lay_gap` apart), `lay_page_count`, `lay_sheet` and `lay_area` (the sheet and the text area, axis 0 width and 1 height, in lu), `lay_margin`, `lay_is_obj` and `lay_obj_h` (an opaque block, or a picture on a line of its own, is one box of `word_lay_obj` lu), `lay_line_h`. Its variables start with `lg` (`lgd` a `Doc`, `lgv` a `View`, `lgpa` a `Para`, `lgs` the `int[]` walk of `lay_place`, `lgz` a `string`, the rest `int`); its fixtures are `lg_t_*`.

`ui/view` is the viewer. Every variable and parameter starts with `vw` and the kind of the value: `vwi_` an `int`, `vwl_` an `int[]` (`vwl_g` the geometry of a page, `vwl_q` the look of a run, `vwl_st` the viewer's state, `vwl_r` a rectangle), `vws_` a `string`; the structs are `vwv` (`View`), `vwd` (`Doc`), `vwp` (`Para`), `vwrb` (`Ribbon`), `vwbt` (`GuiButton`), `vwb` (`GuiScroll`), `vwpt` (`Part`), `vwr` (`Run`). Functions are `vw_*`, fixtures `vw_t_*`. Its constants in conf.id sit between the `V1` markers (`vw_idml` is the chrome's idml, `vw_c_*` colours, `vw_g_*`, `vw_q_*` and `vw_s_*` the cells of the geometry, look and state lists). The exports are `vw_t` `vw_s` `vw_rc` (the chrome's tape and rectangles), `vw_dims_now`, `vw_ui` (the faces of its own text), `vw_v` (the `View`), `vw_msg` (the one-entry list that holds the message that took a document's place), `vw_st` (the state), `vw_sb` (the scrollbar), `vw_rb` and `vw_bt` (the ribbon preview and its buttons).
