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
| `Run` | `ru`, `other_run`, `nr`, `cur`, `head` |
| `Run[]` | `rs`, `tr`, `src`, `dst` |
| `Style`, `Sty`, `ListDef`, `Page`, `Ext`, `Lay`, `Model` | `st`, `style_set`, `list_definition`, `pg`, `x`, `paragraph_layout`, `mo` |
| `int[]` | `cps`, `runs`, `row`, `rows`, `random_generator_seed`, `sx`, `span_bounds`, `written_count`, `acc`, `ins`, `style_row_identifiers`, `vs`, `link_fill_values`, `none`, `slot_list`, `flat_characters`, `flat_character_rows`, `flat_links`, `lines`, `pen`, `rel`, `size`, `margin`, `hf`, `levels` |
| `string` | `name`, `text`, `font` |
| `int` | every other short name used as a loop counter, offset or result: `i j k n m w h id at off lo hi cp cprop pprop field value key val bits on mode kind which code lk res got sn ia iz begin same` |

## Where the seams of docs/QUILL.md collide with that

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

The seam of docs/QUILL.md 4.3 names a `Ctl` `c`, a `Sel` `s`, a `Pos` `p` and `from`, `hit`, which collide with the model's and the ribbon's names. What B2 used instead:

| name | type | instead of |
| --- | --- | --- |
| `ctl` | `Ctl` | `c` |
| `sel`, `selection_clone`, `selection_original`, `tmp` | `Sel` | `s`, and `from` |
| `current_position`, `position_result`, `pa`, `pb` | `Pos` | `p`, and `res` for a result (the model's `res` is an `int`) |
| `spot` | `Pos` (where find_next writes) | `hit` (an `int` in the ribbon) and `found` (an `int` in the model) |
| `from` | `Pos` (where find_next starts) | |
| `edit_operation`, `inverse` | `Op` | `op` (the model has functions `op_*`) |
| `inverses`, `ops` | `Op[]` | |
| `transaction`, `redo_transaction` | `Txn` | `nt` (a `Text`) |
| `take`, `give`, `undo`, `redo`, `stack` | `Txn[]` | `from`, `to` |
| `history_record`, `frag` | `Hist`, `Frag` | `fr` (an `int[]` in the ribbon) |
| `again` | `int` (redo or undo) | `redo` (a `Txn[]`) |
| `location`, `dat`, `old`, `snap`, `keep_properties`, `acc`, `cells`, `match_offsets`, `fix` | `int[]` | `at`, `data`, `out`, `ls`, `st` |
| `act` | a function value | `f` (a `Fmt`) |
| `pieces`, `fields` | `string[]` | `lines`, `parts`, `f` |
| `argument_text`, `plain` | `string` | `rest` (an `int[]`) |
| `actual`, `want`, `dump0..dump3`, `fresh` | test fixtures | `got`, `have`, `before` |
| `left_code_point`, `right_code_point` | `int` | `a`, `b` (a `Body`) |
| `on`, `val`, `got`, `cont`, `nrun`, `is_flag_field`, `back`, `step`, `hp` | `int` | `st` (a `Style`), `nr` (a `Run`) |
## One-paragraph layout (B3a, `core/lay/para`)

Prefixes: `face_` (the face cache and its resolvers), `lay_para lay_label lay_label_x lay_number` (the public calls), `lp_` (internals of the paragraph pass), `lp_t_` (test fixtures and their exports: `lp_t_d lp_t_f lp_t_v lp_t_h9 lp_t_h16 lp_t_h32 lp_t_cb lp_t_cs lp_t_cd lp_t_cz`). Its constants in conf.id sit between the `B3a begin/end` markers: `quill_layout_* quill_code_point_* quill_alignment_* quill_line_*`.

`core/lay/type/` holds the structs `Face`, `Pages` and `View` of docs/QUILL.md 4.4; `gui_face`, `gui_face_file` and `gui_cp_adv` are idstd's (package A3b), and the ascent and descent of a face are `gui_font_ascent` and `gui_font_descent`, since a face is a font handle.

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
| `lbl` | `int[]` (a label's code points) | `character_class`, an `int` (the class of a code point, B2) |
| `pgs`, `keys`, `hnd`, `starts`, `tops` | `Pages`, `int[]` | `pg`, a `Page`; `key`, an `int` |

## What `lay_para` leaves in `Lay`, for B3b and B6

* `lines`: six ints per line, `quill_line_*`: `[lo, hi, y, asc, desc, width]`. `y` is the top of the line from the top of the paragraph, so the first line's `y` is the space before. `asc` already contains the extra leading of a line spacing above 100 percent, so the baseline is `y + asc` and the line is `asc + desc` tall. `width` is the used width without the trailing spaces, and the text area's width for a justified line that is not the last.
* `pen`: `len(cps) + 1` entries, x in lu from the left edge of the text area, indents, alignment and justification included. The extra last entry is the x after the last code point, so a caret at the end of the paragraph has an x even when the paragraph ends in spaces. The entry `pen[hi]` of a line that is not the last is the start of the next line, not the end of this one; the end of the visible text of a line is `pen[lo] + width`.
* `h`: space before, every line, space after.
* A list item's label is not in `pen`: `lay_label` fills a list the caller owns, drawn in the face of the paragraph's first run at `lay_label_x`.
## ODT content reader (B4a, `io/odt/read/content`)

Prefixes: `odt_` is the seam of docs/QUILL.md 4.6 (`odt_load`, `odt_load_bytes`, `odt_error`), `orc_` is everything else the reader owns, `orc_t_` is its test fixtures, and `cli_` is `word --text` (`ui/app/cli`). Its constants sit in conf.id between the `B4a begin/end` markers.

One export is new: `odt_why`, a string that `odt_load` and `odt_load_bytes` set (to "" when they start) and that `odt_error` puts in brackets after its message for the codes that carry a detail (1 path, 2 zip reason, 3 XML fault with its byte offset, 5 mimetype found). A code alone could not carry the byte offset 4.6 asks for.

What the reader keeps in `ext.parts` (docs/QUILL.md 3.1.6), all of it as it is in the file:

| part name | kind | what it is |
| --- | --- | --- |
| the element name (`table:table`, `draw:frame`) | 0 | an opaque element. A block (a `kind == 1` paragraph) or an object inside a paragraph holds the code point `quill_object_marker + index`; the paragraph of a block reads that marker and then a label (`[Table]`) |
| `text:sequence-decls`, `text:variable-decls`, `text:user-field-decls`, `text:dde-connection-decls`, `text:tracked-changes` | 0 | declarations that open `office:text`; no marker points at them, and the writer puts them back first |
| `auto:NAME` | 0 | the automatic style (`style:style`, `text:list-style`, ...) of content.xml that an opaque element names, kept once, for `office:automatic-styles` |
| the zip entry name (`Pictures/a.png`, `settings.xml`, `Configurations2/`) | 1 | an entry the model does not read itself |

`quill_object_marker` is the code point of B5a's marker too; it is declared once in conf.id, in the B4a section.

Names this reader had to avoid because the model holds them for another type: `cs` (an `int` in the model, so the `Cs` is `cst`), `ls` (a `ListDef[]`; the link targets are `hrefs`), `lk` (an `int`; `lkeys`), `ws` (`isws`), `last` (`lastrun`), `key` (`skey`), `sty` (`sid`), `parts` and `lines` (`pieces`, `texts`), `src` (`bytes`), `out` (`ended`).

| name | type |
| --- | --- |
| `cx` | `Odt_Read_Context` (the read: `odt_read_xml_reader`, `d`, `cs`) |
| `odt_read_xml_reader` | `XmlR` |
| `cst` | `Odt_Read_State` (`pstyles`, `odt_read_automatic_styles`, `slots`) |
| `nm`, `pnm`, `lnm` | `Names` |
| `ev`, `at`, `k`, `kind`, `lvl`, `lev`, `rw`, `pp`, `idx`, `base`, `shut` | `int` |
| `sname`, `skey`, `href` | `string` |
| `hrefs`, `knames`, `pieces`, `texts` | `string[]` |
| `z`, `pt` | `Zip`, `Part` |
## ODT styles reader (B4b, `io/odt/read/styles`)

Functions are `ost_*` (the reader and the lookup B4a calls) and `ndump_*` (the normalised dump, docs/QUILL.md 4.9a); test fixtures are `ost_t_*`. Every variable and parameter starts with `os_` and carries its type in the next letter, so none of them can collide with another package's names: `os_i*` an int (`os_ik`, `os_ibit`), `os_s*` a string (`os_sv`, `os_sname`), `os_l*` an `int[]` or `string[]` list (`os_lcrow`, `os_lface`), `os_w*` a `word[]`, `os_x*` a word, and by type `os_r` an `XmlR`, `os_b` a `StyBag`, `os_pg` a `PgTab`, `os_k` an `OdtSty`, `os_d` a `Doc`, `os_f` a `Fmt`, `os_p` a `Para`, `os_ru` a `Run`, `os_page` a `Page`. The one name shared with the model is `i`, an int loop counter.

Structs: `StyBag` (the styles of a document before they are in the model), `PgTab` (page layouts and master pages), `OdtSty` (what the content reader asks). Constants in `conf.id` between the `B4b` markers: `ost_bad ost_units ost_unum ost_uden ost_cattr ost_pattr ost_pct_base ost_s_* ost_cdef ost_pdef ost_pgdef ost_gattr ost_e_styles ost_e_content`.
## ODT content writer (B5a, `io/odt/write/content`)

Functions: `oc_*` (internal) and `odt_content_bytes`, `odt_content_check` (the seam). Fixtures: `oc_t_*`. Every variable and parameter is prefixed `oc_`, so none can collide with another package's names:

| type | names |
| --- | --- |
| `XmlW` | `oc_w` (export `odt_write_test_writer_output` in the fixtures) |
| `Doc` | `oc_d` (export `odt_write_test_document_made`) |
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

`core/lay/page` is the seed of B3b's pagination: `lay_view` (a View), `lay_all` (every paragraph laid out in the text area's width), `lay_paginate` (fills `Pages`: `starts` holds a page's paragraph and line, two cells a page, and one more pair that ends the last page; `tops` holds each paragraph's top in the continuous document, pages one sheet and `quill_layout_sheet_gap` apart), `lay_page_count`, `lay_sheet` and `lay_area` (the sheet and the text area, axis 0 width and 1 height, in lu), `lay_margin`, `lay_is_obj` and `lay_obj_h` (an opaque block, or a picture on a line of its own, is one box of `quill_layout_object_height` lu), `lay_line_h`. Its variables start with `lg` (`lgd` a `Doc`, `lgv` a `View`, `lgpa` a `Para`, `lgs` the `int[]` walk of `lay_place`, `lgz` a `string`, the rest `int`); its fixtures are `lg_t_*`.

`ui/view` is the viewer. Every variable and parameter starts with `vw` and the kind of the value: `vwi_` an `int`, `vwl_` an `int[]` (`vwl_g` the geometry of a page, `vwl_q` the look of a run, `vwl_st` the viewer's state, `vwl_r` a rectangle), `vws_` a `string`; the structs are `vwv` (`View`), `vwd` (`Doc`), `vwp` (`Para`), `vwrb` (`Ribbon`), `vwbt` (`GuiButton`), `vwb` (`GuiScroll`), `vwpt` (`Part`), `vwr` (`Run`). Functions are `vw_*`, fixtures `vw_t_*`. Its constants in conf.id sit between the `V1` markers (`vw_idml` is the chrome's idml, `vw_c_*` colours, `vw_g_*`, `vw_q_*` and `vw_s_*` the cells of the geometry, look and state lists). The exports are `vw_t` `vw_s` `vw_rc` (the chrome's tape and rectangles), `vw_dims_now`, `vw_v` (the `View`), `vw_msg` (the one-entry list that holds the message that took a document's place), `vw_st` (the state), `vw_sb` (the scrollbar), `vw_rb` (the ribbon of the Home tab, which `ui/ribbon` paints and handles; the preview and its `vw_bt` buttons are gone). The faces of the viewer's own text are the ribbon's: `rbd_ui_set` sets them once and `rbd_ui_f` reads them (the viewer had a copy, `vw_ui`, which is gone). Each frame `vw_rib_look` gives the ribbon what the canvas noted the selection looks like (`vw_lk`, below), and `vw_cmd` gives every command of the ribbon that is not the zoom to `cv_rib`.

## Pagination, hit testing and the caret (B3b, `core/lay/page/flow/run/pages/more`)

`more/inc` is the incremental pagination (`lay_relayout`, `lay_walk`, and the helpers it names: `lay_resume`, `lay_stable`, `lay_tail`, `lay_tops` ...), `more/hit` the geometry of a line and the caret (`lay_page_of`, `lay_origin`, `lay_line_y`, `lay_caret`, `lay_off_at` ...), `more/use` the hit test, the line and page moves (`lay_hit`, `lay_move_line`, `lay_page_move`), the layout hook (`lay_hook`, `lay_hook_install`, which exports `lay_hv`, the view the hook reads) and the selection rectangles (`lay_sel_rects`). Seam notes in docs/QUILL.md 4.4 apply; `lay_paginate` answers the number of paragraphs it walked.

Variables of `inc` start with `lw`, of the rest with `lh`: `lwv`/`lhv` a `View`, `lhpa` a `Para`, `lhq` a position in, `lho` a position out, `lhsa` and `lhsb` the two ends of a selection, `lhs` a `Sel`, `lhdc` a `Doc`, `lwo` the old `starts` (an `int[]`), `lws` the walk, `lwr`, `lhr` and `lhw` small `int[]` results, `lhc` the `int[]` a caret or rectangles are written to, `lhwd` an `int` width, the rest `int`. Fixtures are `lg_t_*` (`lg_t_paged`, `lg_t_text`, `lg_t_rows`, `lg_t_edit`, `lg_t_round`, `lg_t_one`, `lg_t_out`, `lg_t_outs`, `lg_t_pag`) with variables `lg` and `lgpo` (a `Pos`), `lgcl` (an `int[]`), `lgtx` and `lgtl` (a `string` and a `string[]`).

A layout case names `lay_paginate` through `lg_t_pag`, because `given` takes only functions that return nothing.

## The canvas (B6, `ui/view/run/in/ev/keys/edit`, `ui/view/draw/flow/item/sel`)

The viewer is an editor now. Functions are `cv_*` (commands, mouse, repaint bands, caret and selection painting) and fixtures `cv_t_*`; the constants in conf.id sit between the `B6` markers (`cv_c_*` colours, `cv_e_*` the cells of `vw_ed`, `cv_g_*` and `cv_a_*` the cells that cull and band add to a geometry and an area list, `cv_k_*` the movement key tables, `cv_f_*` the formatting commands). Every variable and parameter starts with `cv` and the kind of the value: `cvi_` an `int`, `cvl_` an `int[]` (`cvl_o` a caret `[page, x, y, height]` or the rectangles of a selection, `cvl_g` a page's geometry, `cvl_r` an area list or a stale range, `cvl_e` the edit state, `cvl_st` the viewer's state, `cvl_tp` the kept tops), `cvs_` a `string`; the structs are `cvv` (`View`), `cvc` (`Ctl`), `cvsl` (`Sel`), `cvp` and `cvq` (`Pos`).

Where it lives: `done/` is what a command leaves behind (`state/` the controller, the clock and what is kept, `mark/` the bands of the surface a command asks to repaint and the stale paragraphs, `run/` begin and end of a command, how far what moved reaches, ensure-visible and the frame tick), `key/` is the keyboard (`nav.id` movement, `cmd.id` the ribbon table's commands the canvas can do without an argument, `go/` the key and text events; `go/rib/` the commands the ribbon gives with an argument and what the selection looks like for it: `cmd.id` `cv_rib` and `cv_arg`, `set/char.id` `set/para.id` `set/page.id` the character, paragraph, style and page changes, `sync.id` `cv_look`). The layout hook of the line and page moves is B3b's `lay_hook_install`, which `cv_ed_new` installs once; the page unit of `ed_move` moves a sheet, but the Page Up and Page Down keys no longer use it: they move a screenful (B8, `wa_page`). `mouse/` is hit testing, press, drag and the drag that scrolls (`drag/`), and `sel/` under `draw/flow/item` paints the selection and the caret and repaints a band (`paint/`, `part.id`), with the fixtures in `sel/fix`.

Exports: `vw_ctl` (the controller), `vw_ed` (the edit state list: drag, last pointer, when the caret last became solid, its blink half, a frozen clock for cases, the band to repaint), `vw_tp` (the paragraph tops and the end of the last paragraph before the last command), `vw_lk` (what the selection looks like, for the ribbon: the state of each flag command of `cv_f_cmd`, 1 for the alignment the paragraphs have, the font, the size and a last cell that says it changed; `cv_look` writes it at the end of every command, `vw_rib_look` reads it once a frame) and `vw_v`, which `cv_ed_new` now exports (it was `vw_open`'s).

The canvas lays out and paginates with B3b's real functions (`lay_relayout`, `lay_caret`, `lay_hit`, `lay_move_line`, `lay_sel_rects`), whose conventions it relies on: coordinates in lu from the top left of the page's sheet, a goal x in lu from the left of the sheet, `lay_sel_rects` empties its list first and answers how many rectangles it wrote, and `lay_relayout` lays out the paragraphs that `para_stale` marked (height -1) and paginates from the first of them, stopping at the first page that starts where it did, so the tops after it are kept. B6 first wrote them thin in `run/in/load/stub`; that directory is gone.

## Ribbon painting and events (B7b, `ui/ribbon/draw`, `ui/ribbon/event`)

Functions are `rbd_*` (painting and the ribbon's constants), `rbe_*` (events, placing, menus), the seam calls `rib_*` of docs/QUILL.md 4.8 and the fixtures `rbd_t_*`. Every variable and parameter starts with `rb` and the kind of the value: `rbi_` an `int`, `rbl_` an `int[]`, `rbs_` a `string`, `rbt_` a `string[]`; the structs are `rib` and `rbr`/`rbq`/`rbn` (`Ribbon`), `rbg` (`GuiToggle`), `rbm` (`GuiMenu`), `rby` (`GuiGallery`), `rbp` (`GuiTip`). Its constants in conf.id sit between the `B7b` markers: `rbd_qat_px rbd_tab_px rbd_body_px rbd_band_px rbd_tab_pad rbd_arrow_px`, the colours `rbd_c_*`, the control looks `rbd_k_shape rbd_k_menu`, the state-list cells `rbd_s_*` (list `rbd_s0` at the start), the menu tables `rbd_pcmd rbd_plo rbd_pn rbd_plab rbd_parg` (the colour buttons and the font family have none: the colour grid answers the colour and the combo boxes the text), `rbd_cb_cmd` (the commands that are combo boxes), `rbd_paper rbd_margins rbd_styles rbd_style_f rbd_col0 rbd_col_cmd rbd_fld_cmd rbd_fld_txt rbd_tabs`. The names of A5c's widgets: `rbk` a `GuiColors` and `rbc` a `GuiCombo` (the lists of them `rbl_gk` and `rbl_b`).

The ribbon is one per process, as the viewer is. Its widgets and state are exports made by `rib_init`: `rbd_s` (state list), `rbd_col` (the colours the highlight and font colour buttons remember), `rbd_tr` (tab rectangles), `rbd_ws` and `rbd_qs` (a `GuiToggle` for each control of the open tab and of the quick-access strip), `rbd_q` (the quick-access `Ribbon`), `rbd_menu`, `rbd_gal` and `rbd_cg` (zero or one open menu, gallery or colour grid), `rbd_pl rbd_pa rbd_an rbd_nm` (the labels, the answers, the anchor and the last choice's name; a colour grid's choice is written there too, as the one answer), `rbd_cb` (the two combo boxes, the font family and the font size, made at the first `rib_fit`), `rbd_cx` (the control each stands at in the open tab, -1 when it is not there), `rbd_fo` (the one that has the keyboard, -1 for none), `rbd_fm` (the installed families, looked up when the family box is first used), `rbd_tip` (the one `GuiTip`), `rbd_ui` (the faces, `rbd_ui_set`, which the viewer uses too). Fixtures export `rbd_t_r` (the ribbon `rbd_t_up` made) and `rbd_t_kk`.

What the seam calls do:

| call | what it does |
| --- | --- |
| `ribbon_faces_set(r, b, i)` | the font handles of the ribbon's own text; call first |
| `ribbon_fit_start_ribbon() -> Ribbon` | starts the ribbon, answers the Home tab's |
| `rib_fit(rib, x, y, w, h)` | places quick-access strip, tabs and body in the band (`rbd_band_px` tall) and rebuilds the widgets; closes any menu |
| `rib_event(rib, kind, ev) -> bits` | 1 paint again, 2 a command was given (`ribbon_command_given`, `rib_arg`, `rib_name`), 4 a press closed a menu and is owed to what is under, 8 the ribbon took the event |
| `rib_open(rib)`, `rib_tick(rib)` | a menu, gallery or colour grid is open or a combo box has the keyboard (then every event goes to `rib_event` first, and the viewer paints the whole picture, not a band, so the page does not paint over it); once a frame, 1 when a tooltip came on show or went |
| `rib_text(rib, cmd, text)` | the text of the font family or font size combo box, as what the selection has now (the one being typed in is left alone) |
| `rib_put(rib, cmd, val)` | the state of a command (0 off, 1 on, 2 mixed, 3 disabled) in the open tab and the quick-access strip |
| `rib_show(rib, tab)` | opens tab 1 to 4 (the File tab opens a menu on a press, it is not a body) |
| `rib_draw(rib)` | everything, last, over the page |

Arguments of `rib_arg`: half-points for a font size, 0xRRGGBB or -1 (automatic) for a colour, percent for a line spacing, twips for an indent or a space, the position in the installed families for a font family (`rib_name` has the family as it was typed or picked, and the position is -1 for a family that is not installed), the position in `rbd_styles` for a style, the index into `rbd_margins`, `rbd_paper` or the orientation (0 portrait, 1 landscape); a split button's body gives the colour or 0.

The colour buttons open A5c's colour grid (`gui_colors_*`), which answers the colour itself with the name `#rrggbb`, or with the label of its bar for automatic and no colour (-1). The font family and size are A5c's combo boxes (`gui_combo_*`): a press on one gives it the keyboard, Enter or a choice commits (the size as half-points, by `ost_size`), Esc puts the text back, and a press elsewhere commits what was typed and is owed to what is under (bit 4). While a menu, a gallery or a colour grid is open it has every press, so a combo box under it is not pressed through it.

## The app shell (B8, `ui/app`)

The shell holds the document, the window and the files. Seam names (docs/QUILL.md 4.8 and 4.9): `app_new`, `app_frame`, `app_open`, `app_save`, `app_title`, `cmd_run`, `cmd_run_arg`, `cmd_state`; the structs `App`, `Ui` and `Shell` are in `core/type`, one to a file. Everything else is `wa_` (the shell; fixtures `wa_t_`) or `cli_` (the command line; fixtures `cli_t_`). Variables start with `wa` and the kind of the value: `wai_` an `int`, `wal_` an `int[]`, `was_` a `string`, `wat_` a `string[]`; the structs are `waa` (`App`), `wau` (`Ui`), `wash` (`Shell`), `wav` (`View`), `wad` (`Doc`), `wap` (`Pos`), `wadg` (`GuiDialog`), `wafl` (`GuiFiles`), `wahome` and `waqat` (the Home tab's and the quick-access strip's `Ribbon`). Its constants in conf.id sit between the `B8` markers (`wa_*`).

The App is the export `wa_app`, kept by `app_boot` (`app_new` is `app_boot` in the machine's own sans-serif at `wa_w` by `wa_h`; the cases boot it in a smaller surface with the font file's faces, `wa_t_app`). The canvas still reads its own exports (`vw_v`, `vw_ctl`, `vw_st`, `vw_rb`), so a new or opened document goes through `wa_swap`, which makes them again (`cv_ed_new`) and puts them in the App. `Shell.cam` is the viewer's state list `vw_st`; `Shell.dirty` is kept by `wa_dirty` after every event (`wa_note`).

* **Dirty.** B2 counts every primitive operation, edits, undo and redo alike (`ed_touch`, cell 1 of the export `ed_typing`, made by `ctl_new`); a save or an open notes the count (`wa_clean`, cell `wa_s_mark` of `wa_st`), and a document is dirty when the count is not the noted one. An undo back to what was saved is still dirty. The title is the file's name, `*` when dirty, then ` - Word` (`app_title`); the window gets it when it changed (`wa_ti`).
* **State.** `wa_st`: the count at the last save, the action waiting for the unsaved-changes dialog (`wa_a_*`), the dialog open (`wa_d_*`, named by `wa_d_names`) and whether the app should close. `wa_ps` holds what the ribbon was last told for the commands of `wa_put_cmd`, so that the picture is made again only when that changed.
* **Events.** `app_frame` (fit, `wa_events`, caret and tooltip ticks, `wa_paint`) takes events one at a time through `app_on`: a dialog first (`wa_dlg_event`), else `wa_route`: the ribbon (`wa_rib`, which runs its command with `cmd_run_arg`), the window closing (`wa_ask`), then the page area (`wa_input`: keys by `wa_key`, text, the wheel, the mouse). A key goes to `cmd_run` when the shortcut table (`key_cmd`) names a command in `wa_own_cmd` that can be done now (`wa_gate`: Tab is a list command only in a list), else to `wa_plain`: Page Up and Page Down move a screenful less `wa_overlap` pixels (`wa_page`: the page area scrolls, the caret stays at the same place on the screen, and at the end of the document it goes to the start or the end), any other key to `vw_key`. Esc quits nothing. Print has no command (docs/QUILL.md 1.1, F8 is later), so Ctrl+P is not in the key table.
* **Commands.** `cmd_run_arg` does nothing while a dialog is open. File commands: `wa_file`. Zoom: `wa_zoom` (`wa_fit` is fit width). Lists: `wa_list` (bullets and numbering toggle the built-in list 1 or 2, the menu's second entry removes it; `wa_shift` moves levels with `wa_step`). Heading shortcuts: `wa_head`. Find and Replace do nothing until B10's bar. Every other command is the canvas's (`cv_rib`). `cmd_state` answers 0 off, 1 on, 2 mixed, 3 disabled (`wa_flag`, `wa_gate`).
* **Dialogs.** `wa_open` makes a modal dialog of A5c's `gui_dialog_*` (kept as `wa_dg`); `wa_confirm` (Save, Don't Save, Cancel), `wa_oops` (a reason from `odt_error`) and `wa_picker` (the file list of `gui_files_*` in the room the dialog leaves, kept as `wa_fl`; Open starts in the document's folder or `$HOME`, Save As has the path typed in its path box). `wa_ask` asks first when the document is dirty and then does the action that waited (`wa_go`: new, the Open picker, quit); `wa_choose`, `wa_took` and `wa_keep` carry a choice out. The overlay stack is not used: the program's own loop gives the dialog every event.
* **Files.** `app_open` reads into a fresh document and replaces the open one only when it read; `app_save` writes `PATH.part` and renames it over `PATH` only when whole (docs/QUILL.md F3), noting the path and that nothing is unsaved.

### The command line (`ui/app/cli`)

`cli_main` is `main`: `--text`, `--dump`, `--roundtrip`, `--pages` (`cli/doc`, `cli/round.id`), `--render IN OUT.ppm [--page N] [--zoom Z]` (`cli/run/render`: the page as the window paints it without the desk or the caret, as a binary PPM) and `--script FILE [IN.odt [OUT.odt]]` (`cli/run/script`), and a file name or nothing opens the window. Any other line prints the usage and answers 2.

A script is one line per event, the first character the verb. Upper case verbs are `ed_play`'s (T types, E Enter, B W D F delete, U R undo and redo, C X V P clipboard, M move, A S select, G O L Y Z K formatting, H replace all), done as one command of the canvas. Lower case verbs are the shell's: `n` new, `o PATH` open (the Open picker with no path), `s PATH` save (the document's file, or the Save As picker, with no path), `q` ask the window to close, `p PATH` choose a file in the open picker, `u N` press button N of the open dialog, `k KEY:MODS` a key, `c CMD:ARG` a command of the ribbon's table, `m KIND:X:Y:BUTTON` a mouse event, `x TEXT` text typed as text events; and `d` prints the normalised dump (docs/QUILL.md 4.9a), `t` the title, `g` the name of the dialog that is open (none, unsaved, open, save, message). `q` prints `close` or the dialog that opened. Anything else is skipped. The script runs in an application with no window.

The viewer's own loop is folded in here: `vw_main`, `vw_loop`, `vw_title`, `vw_on`, `vw_events`, `vw_tick`, `vw_cmd` and `vw_rib_event` are gone (`app_main`, `wa_loop`, `app_title`, `app_on`, `wa_events`, `app_frame`, `cmd_run_arg` and `wa_rib` took their places), `vw_key` answers nothing (it used to answer 1 for Esc), and `vw_default` is gone because `word` with no file opens a blank document. `vw_boot` and `vw_open` stay for the viewer's own cases; the message card they show is not reached by the app, which tells a file that cannot be read in a dialog (`vw_msg_new` makes the export `vw_msg` for both).
