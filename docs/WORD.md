# A word processor in `id`: the editor, grown into a Word replacement

> **Status: plan.** Nothing in this file is built. It was written from the code
> and docs as they are (`editor/`, `docs/EDITOR.md`, `docs/UI.md`, `docs/SPEC.md`
> 1.2, `docs/STRUCTS.md`, idstd's `NAMES.md` and `README.md`), not from memory;
> where a number or an API is a guess it says so and says what would confirm it.
> Nothing was built or run to write it, so every cost is an estimate.

Goal: a document editor with the ribbon at the top and `.odt` as its native
format, close to Word's basic functionality, built only from `id`, idstd (with
its GUI toolkit, `docs/UI.md`) and the editor's own ODT code. LibreOffice
(`soffice`) is a **test oracle only**.

## 0. Reading guide

| section | answers |
| --- | --- |
| 1 | what Word does that we will do, and when (core v1 / v2 / later) |
| 2 | what exists today, with paths, per feature |
| 3 | the architecture, and where each piece lives |
| 4 | the seams: structs and signatures parallel agents build against |
| 5 | phases and work packages, with directories, dependencies, acceptance tests |
| 6 | risks and language limits |
| 7 | decisions that need the user |

Tiers: **core v1** is the credible daily driver for plain documents (letters,
essays, notes, reports without tables or pictures); **v2** is the first release
after it; **later** is deliberately not scheduled.

Two rules that shape everything below, stated once:

* A struct has one to three fields, lives alone in a file, and is a reference
  (`docs/SPEC.md` 1.2). A struct is **never freed** (SPEC 1.2 "Memory"): do not
  allocate one per line, per glyph, per frame or per keystroke. Per-pass data
  is a list that is emptied and refilled.
* Strings are never freed on any target (`docs/MEMORY.md` 2a). Document text is
  therefore an `int[]` of code points that is edited in place, and no string is
  built per frame.

---

## 1. Feature inventory

Ids (`F1`, `E3`, ...) are used by section 2.

### 1.1 File

| id | feature | tier | notes |
| --- | --- | --- | --- |
| F1 | New (blank document, Normal style, A4/Letter by locale default) | core v1 | replaces the current document after the unsaved-changes prompt |
| F2 | Open `.odt` from a path or an in-app file picker | core v1 | the picker is built from toolkit widgets over `fs_list` |
| F3 | Save, Save As, `Ctrl+S`, dirty marker in the title | core v1 | write to a temp name, then `fs_rename` over the target |
| F4 | Unsaved-changes prompt (Save / Don't save / Cancel) on New, Open, Close | core v1 | a modal dialog |
| F5 | Preserve what we cannot edit (tables, images, fields, unknown XML) through a round trip | core v1 | opaque blocks, section 3.1.6 |
| F6 | Recent files | v2 | a text file under `$XDG_STATE_HOME`; shown in the File menu |
| F7 | Export PDF | v2 | needs a PDF writer with an embedded TrueType font |
| F8 | Print | later | needs a spooler path; PDF export plus `lp` is the likely route |
| F9 | Open `.docx`, `.rtf`, `.txt` | later | `.txt` import is a day's work and could come early; `.docx` is out of the brief |
| F10 | Autosave and crash recovery | later | |
| F11 | Document properties (title, author) | v2 | `meta.xml` is written in v1 with fixed values |

### 1.2 Editing

| id | feature | tier | notes |
| --- | --- | --- | --- |
| E1 | Typing, Enter splits a paragraph, Backspace/Delete, merging paragraphs | core v1 | typing takes the character properties of the text before the caret |
| E2 | Caret movement: arrows, Ctrl+arrows (word), Home/End (line), Ctrl+Home/End, PgUp/PgDn, Up/Down keeping the column | core v1 | |
| E3 | Selection by mouse (click, drag, double = word, triple = paragraph, Shift+click) and keyboard (Shift+movement, `Ctrl+A`), across paragraphs and pages | core v1 | |
| E4 | Clipboard: system plain text out and in; rich (formatted) copy/paste inside the app | core v1 | rich is an in-process fragment, validated against the plain text on the system clipboard |
| E5 | Undo and redo, unlimited depth, typing coalesced by word | core v1 | |
| E6 | Find (`Ctrl+F`, next/previous, highlight all, match case) | core v1 | a find bar, not a pane |
| E7 | Replace, Replace All | core v1 | same bar, second text box |
| E8 | Word count (status bar), characters, paragraphs | core v1 | recomputed on change, not per frame |
| E9 | Drag and drop of selected text | later | |
| E10 | Autocorrect, smart quotes, auto-list (`1.` or `*` then space) | v2 | |
| E11 | Spelling and grammar | later | needs a dictionary and an affix engine; out of scope for the foreseeable plan |
| E12 | Go to page/heading, navigation pane | later | |
| E13 | Insert/overtype toggle, input methods (IME) preedit | later | committed IME text already arrives as TEXT events (`gfx.h`) |

### 1.3 Character formatting

| id | feature | tier | notes |
| --- | --- | --- | --- |
| C1 | Bold, italic, underline (single), strikethrough, with `Ctrl+B/I/U` | core v1 | **real** bold and italic faces when the system has them, synthetic otherwise |
| C2 | Font family (combobox of installed families) and size (combobox plus grow/shrink) | core v1 | families from fontconfig discovery; sizes in half-points |
| C3 | Font colour, highlight colour (colour grid) | core v1 | |
| C4 | Superscript, subscript | core v1 | |
| C5 | Clear formatting | core v1 | resets direct properties on the selection |
| C6 | Change case, small caps, all caps | v2 | |
| C7 | Underline styles (double, dotted, wavy), text effects, character spacing | later | |
| C8 | Format Painter | v2 | |
| C9 | Font fallback for missing glyphs (symbols, CJK, emoji) | v2 | the font layer draws the face's missing-glyph box today (UI.md 7b) |

### 1.3a Paragraph formatting

| id | feature | tier | notes |
| --- | --- | --- | --- |
| P1 | Alignment: left, centre, right, justify (`Ctrl+L/E/R/J`) | core v1 | |
| P2 | Indents: left, right, first-line; increase/decrease indent | core v1 | set from ribbon steppers; a ruler comes in v2 |
| P3 | Line spacing (single, 1.15, 1.5, 2.0) and spacing before/after | core v1 | |
| P4 | Bullets and numbering, three levels, Tab/Shift+Tab to change level | core v1 | decimal, lower/upper alpha, roman, bullet |
| P5 | Styles: Normal, Title, Subtitle, Heading 1-3, List Paragraph, Quote; apply from a gallery; Enter after a heading starts Normal | core v1 | named styles with parents, as in ODT |
| P6 | Page break (`Ctrl+Enter`), keep with next, page-break-before | core v1 (break) / v2 (keeps) | |
| P7 | Widow/orphan control | v2 | |
| P8 | Tab stops (left, centre, right, decimal), leaders | v2 | default tabs every 36 pt in v1 |
| P9 | Borders, shading, paragraph frames | later | |
| P10 | Modify a style, create a style, style inspector | v2 | v1 can apply but not edit styles |
| P11 | Multilevel lists tied to headings, list restart/continue | later | |

### 1.4 Page

| id | feature | tier | notes |
| --- | --- | --- | --- |
| G1 | Page size (Letter, A4, A5, Legal) and orientation | core v1 | dropdowns with presets |
| G2 | Margins (Normal, Narrow, Moderate, Wide presets) | core v1 | custom margins need a dialog: v2 |
| G3 | Headers and footers, page numbers (`Page X of Y` fields) | v2 | see decision 7.3; the model reserves the fields in v1 and the writer preserves existing ones as opaque |
| G4 | Different first page, odd/even | later | |
| G5 | Columns, sections, section breaks | later | |
| G6 | Page borders, watermark, page colour | later | |
| G7 | Page Setup dialog (custom size/margins, gutter) | v2 | |

### 1.5 Insert

| id | feature | tier | notes |
| --- | --- | --- | --- |
| I1 | Page break | core v1 | same command as P6 |
| I2 | Hyperlinks: display (blue, underlined), preserve, `Ctrl+click` opens | core v1 (display, preserve) | the link is a property of a run |
| I3 | Insert/edit hyperlink dialog | v2 | |
| I4 | Tables: insert, edit cells, add/remove rows and columns, borders | v2 | v1 shows an existing table as an opaque block |
| I5 | Images: display, insert from file, resize | v2 | v1 shows an existing image as an opaque placeholder and preserves the bytes. PNG first; JPEG later |
| I6 | Symbols dialog | v2 | a grid of code points from the current face |
| I7 | Shapes, charts, SmartArt, text boxes, equations | later | |
| I8 | Footnotes/endnotes, comments, bookmarks, cross-references, TOC, fields | later | |

### 1.6 View

| id | feature | tier | notes |
| --- | --- | --- | --- |
| V1 | Print layout: pages as white sheets on grey, with shadow | core v1 | the only view |
| V2 | Scrolling: wheel, scrollbar, PgUp/PgDn, caret-follows | core v1 | |
| V3 | Zoom: slider and `-`/`+`/100% in the status bar, `Ctrl+wheel`, fit width | core v1 | layout does not change with zoom (3.4) |
| V4 | Status bar: `Page X of Y`, word count, zoom | core v1 | |
| V5 | Rulers (horizontal, with indent markers) | v2 | |
| V6 | Gridlines, navigation pane, multi-page view, read mode, dark mode | later | |

### 1.7 The ribbon

| id | feature | tier | notes |
| --- | --- | --- | --- |
| R1 | Tab strip: File, Home, Insert, Layout, View; Home is the default | core v1 | File opens a dropdown menu in v1 and a backstage page in v2 |
| R2 | Groups with a caption under them: Clipboard, Font, Paragraph, Styles, Editing (Home); Pages, Links (Insert); Page Setup, Paragraph (Layout); Zoom, Show (View) | core v1 | |
| R3 | Controls: icon button, toggle (pressed state follows the selection), split button, dropdown, combobox, gallery, colour picker | core v1 | state shows tri-state ("mixed") for a mixed selection |
| R4 | Tooltips: name, shortcut, one line | core v1 | after a 500 ms hover |
| R5 | Keyboard shortcuts for everything common (table in 3.7) | core v1 | |
| R6 | Quick-access toolbar: Save, Undo, Redo | core v1 | a strip above the tabs |
| R7 | Only working controls are shown; no greyed placeholders for v2 features | core v1 | decision, not an omission |
| R8 | Insert tab content: Page Break, Hyperlink (v2), Table (v2), Picture (v2), Symbol (v2) | core v1 (tab with Page Break only) | |
| R9 | Collapse/pin the ribbon, adapt to narrow windows (groups collapse to a menu) | v2 | v1 sets a minimum window width instead |
| R10 | Alt key tips, customisable ribbon, contextual tabs (Table Design) | later | |

---

## 2. Current state

Read from the code on this branch (`language-integrity`). "Editor" is
`/home/preland/git/id_development/editor`; "idstd" is
`/home/preland/git/idstd`.

### 2.1 The editor as it is

* **One compilation unit with global state.** `editor/NAMES.md` makes the whole
  tree one unit with a shared vocabulary. State is `export int[]` / `string[]`
  globals: `odt_txts` (one string per run), `odt_plo`/`odt_phi` (paragraph to run
  range), `odt_keys`, `odt_fonts`, `odt_nums`, `odt_flags` (style table as
  parallel lists), `lay_g`/`lay_x`/`lay_y`/`lay_px`/`lay_st` (one row per glyph),
  `ed_cur` (caret). There are about 427 functions
  (`grep -rhoE '^[a-z_0-9]+\(' editor --include=*.id`). None of it uses a struct.
* **Document model** (`editor/lib/doc/odt/`): runs and paragraphs only. Styles
  are `style:style` rows with a font name, a size in points, a bold flag and an
  italic flag (`odt/walk/sty/prop.id`, `odt/get/style.id`). No parent styles, no
  paragraph properties, no colour, no list, no page layout, no named versus
  automatic distinction. Elements handled: `text:p`, `text:h`, `style:style`,
  `style:text-properties`, `text:s`, `text:tab` (`odt/walk/elem/dispatch.id`);
  everything else's text falls into the open run. Spans work through a style
  stack (`odt/walk/elem/stk/`, whose comments mention nested `text:span`); the
  dispatch file read for this plan does not show the span handling itself.
* **XML** (`lib/doc/xml/`): a pull parser, global state (`xml_st`, `xml_buf`),
  namespace prefixes not resolved (`text:p` as written), `pt` sizes only. There
  is no writer.
* **ZIP** (`lib/zip/`): central-directory reader, method 0 and 8, DEFLATE through
  idstd's `inf_inflate` (`lib/zip/arc/read/infl.id`; idstd NAMES 1.15). State in
  `zip_h`, `zip_off`, `zip_csz`... **No CRC-32 check, no writer, no compressor.**
  `editor/NAMES.md` still lists `inf_` under `lib/zip/` although it moved to idstd
  (a doc drift, listed in 2.5).
* **Font** (`lib/font/`): an adapter over idstd's `ttf_` that keeps exactly one
  face (`tt_load` replaces the previous one). Bold and italic are faked
  (glyph drawn twice a pixel apart; shear of a fifth of the height,
  `docs/EDITOR.md` "Layout and drawing"). Kerning unused.
* **Layout** (`app/view/lay/`): one glyph row per code point in global lists;
  pen in 64ths of a pixel; breaks **at the overflowing glyph**, not at a space
  (`lay/put/more/wrap.id`, which says so itself); line lead from the font's
  line metric; no indents, alignment, spacing, justification or tabs; no
  pagination (`docs/EDITOR.md` "No scrolling. The window shows one page").
  The layout runs over the whole document each time (`lay_doc(w)`).
* **Rendering** (`app/view/draw/`): rasterises per glyph into the framebuffer
  `ed_fb`, presents through `gfx_*`; also writes a PPM (`--ppm`), which is how
  the render suite tests it.
* **Caret and input** (`app/view/txt/edit/`, `app/run/key/`): the caret is one
  code-point index over all runs (`ed_cur`); a keystroke inserts into
  `odt_txts[run]` by building a new string (`txt/edit/doc/mut/ins.id`); keys come
  from `gfx_poll` (`run/key/dispatch.id`: printable ASCII, Backspace, Delete,
  arrows). **No selection, no mouse, no undo, no paragraph split,
  an empty paragraph cannot hold the caret.**
* **Tests**: `idc/tests/editor.sh`, `editor_zip.sh`, `editor_doc.sh`,
  `editor_render.sh`: shell scripts, and the zip suite compares against Python's
  `zlib`/`zipfile`. Both are what the project has since decided to retire
  (memory: no shell, no Python in the repo). Every function also carries inline
  cases.

### 2.2 The toolkit (`idstd/gfx/kit/gui/`) as it is

| piece | state | where |
| --- | --- | --- |
| idml parse, tape, bind, layout | works: exact-fill tiling, `hug`, anchors, overlays, `?@ref` gates | `core/doc`, `core/flow` |
| idml features parsed but not acted on | `fit`/`fill` (need text measure), `pad`, `gap`, `overflow`, `Repeat`, `Table`, `define` expansion, `Modal` backdrop | `docs/UI.md` section 10 |
| idml has no pixel unit | all sizes are basis points of the parent; `gui_bind` can feed `@ref` basis points, so a fixed-pixel band is `px * 10000 / window_h` recomputed on resize | `docs/UI.md` 3.3, 5 |
| fonts | system discovery via fontconfig rules, `.ttf` only, **Regular style only**; anti-aliased draw, kerning, 64ths pen, per (face, size) glyph cache with 4 sub-pixel slots; text-**string** API only (`gui_text_width(f, s)`, `gui_text_draw`, `gui_text_x`, `gui_text_hit`) | `font/`; NAMES 1.21 |
| text box model | `GuiTb` struct: text as a UTF-8 **string**, byte caret/anchor, word classes (`utf8_class`), undo history of whole-text snapshots, clipboard action protocol | `tb/edit`; NAMES 1.19a |
| text box widget | one line, focus, mouse selection, scroll, caret blink, I-beam cursor | `tb/box`; NAMES 1.19b |
| **widgets other than the text box** | **none**: no button, toggle, checkbox, dropdown, popup, scrollbar, tooltip, dialog, colour grid, icon (UI.md section 6 is a table of intentions) | |
| paint | text box paints with `d2_l_rect` and `gui_text_draw` directly (immediate); no retained draw list (UI.md Fork 3 open) | `tb/box/view/paint` |
| clip | `gui_text_clip` clips glyph pixels only; `sf_l_pset` clips to the surface only; no rectangle-clip stack | `font/seam/clip.id`; UI.md section 8 |

The toolkit is therefore a layout engine, a text engine and **one** widget. The
ribbon needs about a dozen more.

### 2.3 idstd as it is (what the plan reuses or must add)

| need | exists | missing |
| --- | --- | --- |
| window, events, clipboard | `gfx_open/present/sync/show/event/mods/cursor/clip_set/clip_get` (`sys/win/gfx`); events: key, TEXT, mouse down/up/move, resize, quit, wheel; mods 1 shift 2 ctrl 4 alt 8 super | window **title** after open; F-keys as `gfx_event` keys (README "Not covered"); macOS shim is uncompiled |
| surface | `sf_l_*`, `d2_l_rect`, `ppm_l_dump` | clip rectangle, alpha rectangle, line/polygon, blit with scaling |
| fonts | `ttf_*` (outlines, exact-area coverage at 1-512 px, kerning, composites), `gui_font_*` | style (bold/italic) discovery and selection; code-point API; family list; open by file path for deterministic tests; synthetic bold/italic |
| inflate | `inf_inflate`, `gz_decompress` (`core/data/seq/byte/pack/inflate`, NAMES 1.15) | **deflate compressor**, CRC-32 |
| zip | none (the editor's reader is in `editor/lib/zip`) | reader and **writer** as library |
| xml | none general; the editor's pull parser; a purpose-built reader in `font/find/conf/xml` (`xt_`) | writer; one shared reader |
| utf-8 | `utf8_cp`, `utf8_seq`, `utf8_str`, `utf8_class`, `utf8_word_*` (string based) | cp-list helpers (the plan uses `int[]` text) |
| lists | `lst_*`, `lget/lset`, `push`/`pop` | insert-at, delete-range, splice |
| process, files | `exec_run`, `exec_ls`, `fs_*` incl. `fs_list`, `fs_rename`, `fs_mktemp`, `fs_mtime` | none: enough for a file picker and for driving `soffice` |
| tests | inline cases, `given`/`then`, casework tools | struct literals in cases exist (SPEC 1.2); harness prints structs |

**Directory room.** `idc` caps a directory at three `.id` files plus
subdirectories. **Superseded: the 3-entries-per-directory limit has been dropped (E0701 is retired, `idlayout --room` is gone), so the "free slot" reasoning below, W0 and risk 6.2 no longer constrain the layout; the paused idstd restructure is re-planned around a flatter tree.** Today `idstd/core/data/seq/byte/` is `inflate, sha256, ttf`,
`idstd/core/text/` is `chr, fmt, str`, `idstd/gfx/kit/` is `gui, space`, and
`idstd/gfx/kit/gui/` is `core, font, tb`: only `gfx/kit/` has a free slot. Any
addition elsewhere needs a restructure first (work package W0). Free slots are
checked with `idc/.idc-cache/idlayout --room` (docs/UI.md section 11); not run
for this plan.

W0 has since been done, as moves only: `byte/` is `pack/inflate`, `sum/sha256`,
`ttf`; `core/text/` is `atom/{chr,fmt}`, `str`; `core/data/seq/lst/` is
`base/{access.id,make/}`, `w`; `gfx/kit/wid/` exists with a README only (it now
fills `gfx/kit/`'s third slot; `wid/` itself has three free). `idlayout --room`
shows `pack/` and `sum/` with two free slots each, and `core/text/` and `lst/` with one.
`core/text/xml` and `byte/{pack/zip,sum/crc32}` are the slots A1 and A2 fill; the
slot for A7 (`lst_insert` and friends) is the one in `lst/`.

### 2.4 Feature by feature

| ids | what exists | what is missing |
| --- | --- | --- |
| F1, F3, F4 | nothing writes anything (`docs/EDITOR.md` "Nothing writes an `.odt` back") | the whole write path, dirty tracking, dialogs |
| F2 | `ed_load` reads a path from `argv` (`app/doc/in/load.id`) | file picker widgets |
| F5 | unmodelled text leaks into the surrounding run | opaque blocks, preserved zip parts |
| E1 | typing, Backspace, Delete (`app/run/key/`) | Enter, merge, empty-paragraph caret |
| E2 | Left/Right/Home/End-ish via `ed_step`/`ed_seek` over one global index | Up/Down by column, word, line, page, over paragraphs |
| E3 | none | selection model, mouse, painting |
| E4 | `gfx_clip_set/get`, `gui_tb` clipboard protocol | in-app rich fragment, paste across paragraphs |
| E5 | `gui_tb` snapshot undo (single line) | operation log over a document |
| E6, E7, E8 | none | find engine and bar, counts |
| C1 | faux bold and italic, glyph drawn twice or sheared | real faces, underline, strike |
| C2 | one family per run, `pt` size read from automatic styles | families list, combobox, size stepper, discovery by style |
| C3, C4, C5 | none | colour in the model, super/sub, clear |
| P1-P6 | none (`text:h` handled as a paragraph) | paragraph properties, lists, styles with parents, page break |
| G1-G3 | none (fixed 600 px wide layout, `ed_page(640, 480)`) | page model, pagination, header/footer |
| I1-I6 | none | everything (see section 5, phase 2) |
| V1-V4 | one page, no scrolling | pages on a canvas, scroll, zoom, status bar |
| R1-R10 | none | the ribbon and every widget it needs |

### 2.5 Drift found while reading (raise, do not silently fix)

1. `docs/UI.md` 3.1 says "`id` has no structs and no allocation of records";
   `docs/SPEC.md` 1.2 and `docs/STRUCTS.md` say structs are implemented.
2. `editor/NAMES.md` lists `inf_` under `lib/zip/` and says the font adapter
   owns `tt_`/`ras_`; the DEFLATE decoder and the TrueType module are idstd's
   (NAMES 1.15, 1.20).
3. `docs/EDITOR.md` says "163 assertions across five suites" and then lists
   three suites; `editor_ttf.sh` and `editor_ras.sh` are gone but the
   Python-based suites remain, against the no-Python rule.
4. `docs/UI.md` section 6 reads as a widget set; only the text box exists.

---

## 3. Architecture

### 3.1 Document model

#### 3.1.1 Shape

```
Doc
  body   Body     paragraphs, page setup, revision counter
  fmt    Fmt      interned character and paragraph properties, styles, list definitions
  ext    Ext      fonts, hyperlink targets, preserved zip parts

Para
  txt    Text     code points and the runs that cover them
  lay    Lay      this paragraph's layout, refilled in place
  pprop  int      interned paragraph-property row id
```

Text is `int[] cps` (one code point per cell, so an offset is an index and a
caret is a number, as in the editor today) plus `Run[] runs`; runs cover the text
contiguously, adjacent runs with equal properties are merged, an empty paragraph
has one zero-length run so it can still hold the caret and carry the properties
typed into it.

#### 3.1.2 Interned property rows

Properties are **rows of ints interned in a table** (`Tab`): the id of a row is
its index, equal rows get equal ids. A run holds one id, a paragraph holds one.
Consequences, all wanted:

* "Same properties" is an int compare, so run merging and undo records are cheap.
* The ODT writer emits one automatic style per distinct row actually used, which
  is what ODT's `office:automatic-styles` is.
* A row is never mutated. "Make this bold" is `fmt_with(fmt, id, field, value)`
  returning another id.
* A record-as-list row is the house convention (idstd README) and the way
  through the three-field limit; the field offsets are constants in
  `word/conf.id` (`word_c_*` for character rows, `word_p_*` for paragraph rows).

Character row (unset is -1; flags are two ints so "unset" is distinct from "off"):

| field | meaning |
| --- | --- |
| `style` | character style id, 0 for none |
| `font` | index into `ext.fonts`, -1 unset |
| `size` | half-points, -1 unset |
| `color` | `0xRRGGBB`, -1 unset (automatic) |
| `hl` | highlight `0xRRGGBB`, -1 none |
| `on` | bits: 1 bold, 2 italic, 4 underline, 8 strike, 16 superscript, 32 subscript |
| `set` | which of those bits are specified |

Paragraph row: `style`, `align` (-1 unset, 0 left, 1 centre, 2 right, 3 justify),
`ind_left`, `ind_right`, `ind_first` (twips), `sp_before`, `sp_after` (twips),
`line` (percent of single; 100 = single, -1 unset), `brk` (1 = page break before),
`list` (list definition id, 0 none), `level` (0-2), `kind` (0 text, 1 opaque).

**Effective value** of a field is resolved at layout and format-state time, never
stored: direct row, then character style, then the paragraph's style chain
(`style` -> `rel.parent` ... -> default style), then the document default.
`style_eff_c(fmt, pstyle, cprop, field)` and `style_eff_p(fmt, pprop, field)` are
the two resolvers; layout caches the result per `(pstyle, cprop)` in a list so a
paragraph resolves each distinct pair once.

#### 3.1.3 Styles, ODT's way

`Style` is `(name, rel, fmt)`: `rel = [family, parent, next]` (family 0 paragraph,
1 character; parent and next are indices into `styles`, -1 none), `fmt = [cprop,
pprop]` (row ids). Named styles are `office:styles` in `styles.xml`; **automatic
styles** (`T1`, `P1` in `content.xml`) are not stored as styles at all: on read
each one is flattened into a row (its `style:parent-style-name` becomes the row's
`style` field; its own properties become the other fields), on write each used row
becomes one again. This keeps the model free of the named/automatic split while
keeping the file faithful to what LibreOffice writes.

Built-in set created by `fmt_default()`: Normal (the default), Title, Subtitle,
Heading 1, 2, 3 (`next` = Normal), List Paragraph, Quote. Names are the ODT
names LibreOffice uses ("Standard", "Heading_20_1") on the wire and Word's
names in the UI; the mapping is one table in `word/conf.id`.

#### 3.1.4 Lists

`ListDef` (in `Sty`): per-level `(kind, format, start, indent_left, hanging)` as an
int row; kinds bullet and number; formats decimal, alpha lower/upper, roman
lower/upper, and a bullet code point. A paragraph with `list != 0` is an item at
`level`. Numbers are **computed**, never stored: `lay` walks the paragraphs once
per layout pass, keeping a counter per `(list, level)`, resetting deeper levels
when a shallower item appears. ODT mapping: `text:list` / `text:list-item`
nesting with `text:list-style-name` (read: flatten the nesting to
`(list, level)`; write: re-nest from levels).

#### 3.1.5 Units

* Model lengths: **twips** (1/1440 in, 1/20 pt). A4 is 11906 x 16838. ODT lengths
  (`cm`, `mm`, `in`, `pt`) are converted on read and written back as `in` with
  four decimals; a value not on a twip boundary moves by less than one twip
  (guess: this is harmless; the round-trip suite in 5.4 B5 measures it).
* Font sizes: half-points.
* Layout: **layout units (lu) = 1/64 px at 96 dpi**, the pen unit the font layer
  already uses (UI.md 7). A twip is 64/15 lu; each property converts once, with
  a rounding rule per property, never cumulatively.

#### 3.1.6 What we cannot edit is preserved, not dropped

A `Para` with `pprop.kind == 1` is an **opaque block**: a table, a section, a text
box, a TOC, anything the reader does not model. Its `Text` holds a short
placeholder (for example `[Table]`), and the verbatim XML of the element is kept in
`ext.parts` (`Part(kind=raw)`), referenced by the block's first code point being a
private-use marker plus an index. The block is drawn as a grey box, selectable,
deletable as a unit, and written back byte for byte. Inline objects (an image in a
paragraph) are the same at run level: a one-code-point run holding a marker, so
the paragraph's text is otherwise editable. Zip entries the model does not know
(`Pictures/`, `Thumbnails/`, `Configurations2/`) are kept as `Part(kind=file)` and
re-stored. Decision 7.4 is whether this is the right policy.

### 3.2 Edit operations, selection and undo

#### 3.2.1 Positions and selection

`Pos(para, off)`: paragraph index and code-point offset in `txt.cps`. `Sel(anchor,
caret, goal)`: a selection across paragraphs is the range between the two
positions in document order; `goal` is the x (in lu) kept for Up/Down, -1 when
not set. Both are structs, so **copy fields, never alias**: a saved selection in a
`Txn` is built field by field.

The text-box rules are reused as rules, not as code: a word is a run of one
`utf8_class` (`utf8_class(cp)` is public and takes a code point, so it works on
`int[]`); double click selects the run under the click, triple selects the
paragraph; Ctrl+Left/Right/Backspace/Delete use the same classes
(`docs/UI.md` 7a "The word rule"). `utf8_word_*` take strings, so the edit core
calls idstd's `int[]` twins `utf8_cps_word_next(int[], int)`, `utf8_cps_word_prev`,
`utf8_cps_word_lo`, `utf8_cps_word_hi`, `utf8_cps_pivot`, `utf8_cps_run_next`,
`utf8_cps_run_prev` and `utf8_cps_cls_at` (NAMES.md 1.19a); the word tree keeps
no copy of the rule.

#### 3.2.2 Operations

Everything the user can do is a sequence of six primitive operations. Each is
applied by `op_apply(doc, op)` which **returns its inverse**, so undo is "apply
the inverse, push the result on redo".

| kind | arguments (`at`) | `data` | inverse |
| --- | --- | --- | --- |
| `INS_TEXT` | para, off, cprop | the code points | `DEL_TEXT` of the same span |
| `DEL_TEXT` | para, off, count | (filled by apply: deleted cps and the runs they spanned) | `INS_TEXT` + `SET_RUNS` |
| `SPLIT` | para, off | new paragraph's pprop | `JOIN` |
| `JOIN` | para | (filled by apply: the removed paragraph's pprop and boundary) | `SPLIT` |
| `SET_RUNS` | para, lo, hi | the replacement runs, encoded `len, cprop, link` triples | `SET_RUNS` with the old runs |
| `SET_PPROP` | para, new | (filled: old) | `SET_PPROP` |
| `INS_PARA` / `DEL_PARA` | index | a whole paragraph snapshot | each other |
| `SET_PAGE` | field, value | (filled: old) | `SET_PAGE` |

User commands are **transactions**: `Txn(ops, before, after)`. Typing a character is
a one-op `Txn`; deleting a three-paragraph selection is `DEL_TEXT`, `JOIN`, `JOIN`
(or `DEL_PARA`); paste is `INS_TEXT` plus `SPLIT`s plus `INS_PARA`. `before`/`after`
are the selections to restore, so undo puts the caret back where it was.

**Coalescing** follows `gui_tb`'s rule (UI.md 7a "Undo"): a typed character joins
the open `Txn` while it continues a word; a space/punctuation/word start, any
caret move, selection, paste, cut, delete, formatting or undo closes it. `Hist.open`
is the index of the open `Txn` or -1. A new edit empties `redo`. Typing into a
selection is delete + insert in one `Txn`.

**Formatting** is `SET_RUNS` over the selected span of each paragraph, built by
`run_patch(Text, lo, hi, field, value, mask)`: split runs at `lo` and `hi`,
change the interned id of each covered run through `fmt_with`, merge equal
neighbours. A toggle is computed from the **whole selection**: if every character
has the flag on, turn it off; otherwise turn it on (Word's behaviour).
**Pending properties** with no selection (toggle bold, then type): `Ctl.typing`
holds a character-row id applied by the next insert, cleared by any caret move.

**Paragraph split/merge rule** (a choice the oracle can check): Enter splits and the
new paragraph gets the old paragraph's `pprop`, except after a style whose `next`
differs (Heading -> Normal). Backspace at offset 0 merges into the **previous**
paragraph and keeps **its** properties, as LibreOffice does. (Word keeps the
following paragraph's mark; LibreOffice is the oracle here, see decision 7.4's
neighbours and risk 6.9.)

#### 3.2.3 Clipboard

`Frag(txts, pprops, partial)`: copy slices the selection into a fragment (the
first and last paragraphs partial). `Ctl.clip` holds the last fragment. On copy the
fragment is stored **and** its plain text (paragraphs joined by `\n`) goes to
`gfx_clip_set`. On paste, `gfx_clip_get()` is compared with the plain text of
`Ctl.clip`; equal means the user pasted what we copied, so the rich fragment is
inserted; different means foreign text, inserted as plain text in the typing
properties. Fragment property ids are valid because there is one document per
process (decision 7.8 touches this).

#### 3.2.4 Find

`find_next(Doc, Pos from, int[] needle, int flags) -> int` returns 1 and sets a
caller-supplied `Pos` pair; `flags` bit 1 match case, bit 2 backwards. Matching is
per paragraph (a match does not span paragraphs in v1). Replace All is one `Txn`.

### 3.3 Layout

#### 3.3.1 Faces

The font layer grows (work packages A3a, A3b):

* `gui_face(string family, int px, int style) -> int`: a handle for family,
  pixel size and `style` bits (1 bold, 2 italic), cached on `(family, px, style)`
  without building strings per call. Discovery learns each file's style
  (already read from the `name` table, `docs/UI.md` 7) and prefers a real
  Bold/Italic/Bold Italic file; if none, the handle is flagged synthetic.
* `gui_face_real(int f) -> int`: bit 1 bold is real, bit 2 italic is real.
* `gui_cp_adv(int f, int cp, int next) -> int`: advance in 64ths including
  kerning against `next` (0 for none). One call per code point, no strings.
* `gui_cp_draw(int f, int x64, int base, int cp, int color) -> void`: draws one
  glyph with its baseline at `base`; applies synthetic bold (extra coverage pass
  one pixel over) and italic (shear) when the face is flagged synthetic, so the
  editor never needs to know.
* `gui_face_file(string path, int px, int style) -> int`: a face from a font
  file, for deterministic cases that must not depend on the machine's fonts.
* `gui_font_families() -> string[]`: installed family names for the combobox.

The existing string API stays (the text box uses it); both read one glyph cache
per handle.

#### 3.3.2 One paragraph

`lay_para(Doc, int i, int width_lu, Faces)` fills `para.lay` in place:

* `lines`: stride 6 per line, `[lo, hi, y, asc, desc, width]` (cp range, top y
  relative to the paragraph, ascent and descent in lu, used width).
* `pen`: one entry per code point, its x in lu from the line's left edge
  **after** alignment and justification, so drawing and hit-testing never redo
  arithmetic.
* `h`: the paragraph's total height including space before and after.

Algorithm, in order: resolve each run to a face and a colour; walk code points
accumulating advances (`gui_cp_adv(f, cp, next_cp)`, the next code point crossing a
run boundary is looked up in the next run) into a tentative pen; remember the
last break opportunity (after a space, after `-`, before a CJK ideograph; later
UAX 14); on overflow break there, or at the glyph when the word is longer than the
line; trailing spaces **hang** (do not count toward the width and are not
justified). Per line: `asc` = max ascent of its runs (superscript/subscript
adjust by the ODT `style:text-position` percentage), `desc` = max descent,
line height = `(asc + desc) * line% / 100`, the extra leading goes above the text,
baseline = top + `asc` + leading. **Mixed fonts and sizes on one line** are
exactly this max rule. Alignment shifts the line by the leftover width; justify
distributes the leftover over the line's spaces in whole lu with the remainder
spread left to right (the last line of a paragraph is left-aligned). First-line
and hanging indents, left/right indents and list labels (the label is laid out
as a pseudo-run to the left of the first line, in the paragraph's first run's
face) change the line's available width and start. Tabs advance to the next
default stop (36 pt multiples, v1).

The pass allocates no struct and no string: `lines` and `pen` are emptied and
refilled. Whether that reuses their storage is unmeasured (docs/UI.md 3.3 says
the same of its rectangle list); B3a must measure it (6.3).

#### 3.3.3 Pagination and incremental update

`Pages(starts, tops, count)`: for page `k`, `starts[2k], starts[2k+1]` is the
`(paragraph, line)` it begins with; `tops[i]` is paragraph `i`'s y in the
continuous document in lu (a cumulative sum of paragraph heights with page gaps
inserted), so hit-testing a click is a binary search. Pagination walks the
paragraphs, placing lines on a page of content height (page height minus margins,
minus header/footer in v2); a paragraph with `brk` or a paragraph that does not
fit starts the next page; a paragraph is split between pages at a line boundary
(widow/orphan control v2).

**Incremental**: every edit marks the touched paragraphs stale (`lay.h = -1`).
`view_relayout(View)` re-lays out only stale paragraphs, then re-paginates from
the first changed paragraph and stops when a page's start matches its old value.
A width or page-setup change marks everything stale. Typing in a 100-page document
therefore costs one paragraph plus a short pagination tail.

#### 3.3.4 Hit testing and the caret

`lay_hit(View, int x_lu, int y_lu) -> ` fills a `Pos`; `lay_caret(View, Pos, int[]
out)` writes `[page, x, y, height]`. Both use `tops`, `lines` and `pen` only, no
font calls, so they are testable without a font and exact by construction (the
caret and the glyph agree because both read `pen`).

#### 3.3.5 Zoom does not change layout

Layout always runs at 100% (96 dpi). Zoom `z` (percent) only scales at draw time:
glyph size `px * z / 100` (a second face handle, `gui_face(family, px*z/100,
style)`), positions `lu * z / 100 / 64`. Consequence: line breaks and page
breaks are identical at every zoom, which is what Word users expect. Cost: at
fractional zoom glyph advances are not the sum of the zoomed advances; the drawn
position comes from the 100% pen, so glyphs are placed correctly and may differ
from the zoomed face's own spacing by a fraction of a pixel (acceptable, and
visible only as slightly uneven spacing at odd zooms; judged by a human, not
measured here).

### 3.4 Rendering and scrolling

`view_draw(View, Cam, int w, int h)`: grey canvas; for each page intersecting the
viewport (computed from `Pages` and the camera): white sheet, shadow; for each line
intersecting the clip (binary search by `y`): per run segment, highlight
rectangles, glyphs via `gui_cp_draw`, underline and strike rectangles from the face
metrics, hyperlink colour; then the selection (one rectangle per line), then the
caret (blink as the text box does, `gui_textbox_tick`). `Cam(x, y, zoom)` is the
scroll offset in document lu and the zoom. The wheel scrolls `y`; `Ctrl+wheel`
changes zoom (mods from `gfx_mods()`); a vertical scrollbar widget (A5a) shows
position; "ensure caret visible" runs after every caret move. A redraw happens only
when a dirty flag is set by an event, an edit, a tick that changed the caret, or a
resize; the first measured cost to watch is a full-frame repaint of a
1280x800 surface (about 1 M cells, against UI.md's 294 400 for 640x460), which B6
must measure and, if over budget, answer with dirty rectangles.

Needs from idstd: `sf_l_clip(x, y, w, h)` / `sf_l_unclip()` honoured by every
primitive (A4), and an alpha rectangle for selection and shadow.

### 3.5 The ribbon and its widgets

#### 3.5.1 Layout: idml for the chrome, an id flow for the strips

idml has no pixel unit and no content-sized children (`fit`/`fill` are parsed and
ignored; UI.md section 10), so a ribbon of ~60 controls whose groups are as wide
as their contents cannot be expressed as percentages. The plan (decision 7.2,
recommended option B):

* `word/conf.id` holds the chrome's idml as a `string[]` joined at start-up
  (the binary is self-contained, no runtime file lookup). It defines the skeleton:
  quick-access bar, tab strip, ribbon body, canvas, status bar, find bar (gated by
  `?@find`), and the overlay layer for popups and dialogs. Heights that are fixed
  in pixels are `@ribbon_h` and friends: `gui_bind` returns `px * 10000 /
  window_h` basis points, recomputed on resize.
* Inside the ribbon body, **groups and controls are placed by an id flow solver**
  (`strip_place`): controls report a natural size (label width from
  `gui_text_width`, icon size, kind), the solver places them left to right in
  group columns of up to three rows (large buttons span all rows), groups side by
  side with a separator and a caption. If the window is too narrow, v1 sets a
  minimum width (R9 is v2).
* Colours, fonts and sizes are constants (`idstd_wid_*` for widgets, `word_ui_*`
  for chrome); idml carries the structure and the class names.

#### 3.5.2 Ribbon model (data, not code)

The ribbon's definition is a table in `word/conf.id` (list constants are allowed,
memory decision 2026-09-13b): rows `[tab, group, kind, cmd, icon, label, tip,
key]` as parallel `int[]`/`string[]` lists. Everything else is derived: layout,
tooltips, shortcut text, the shortcut dispatch table. `Ribbon(items, rects, state)`
holds the table references, the placed rectangles and a per-item `state` cell
(0 off, 1 on, 2 mixed, 3 disabled).

**Commands** are ints (`cmd_*` in `conf.id`). Function values cannot be stored in a
list, returned or used on wasm (SPEC 1.1), so a command table of handlers is
impossible: `cmd_run(App, int cmd)` is a dispatcher over ranges
(`chain`-linked blocks, each at most three actions, SPEC action limit), and
`cmd_state(App, int cmd) -> int` is its read-only twin that fills the toggles. The
ribbon never calls document code: it returns the cmd id, the app calls
`cmd_run`. A dropdown or gallery returns `cmd` plus a value (`cmd_run_arg(App, cmd,
int arg)`).

#### 3.5.3 New widgets (idstd, `gfx/kit/wid/`)

All follow the text box's protocol (UI.md 7b): a struct holding a rectangle and
state, `*_place`, `*_event(w, kind, ev) -> bits` (1 redraw, 2 activated, 4
dismissed), `*_draw`, with the program owning the event loop and focus. Shared
helpers (`wid_hit`, `wid_press`, theme colours) exist once; the uniqueness rule
forces that anyway (button, toggle and checkbox have near-identical event code).

| widget | struct | behaviour |
| --- | --- | --- |
| button | `GuiButton(v, label, icon)` | normal, hover, pressed, disabled; activates on release inside |
| toggle | `GuiToggle(btn, state, group)` | button with on/off/mixed painting |
| split button / dropdown | `GuiDrop(btn, items, open)` | click body = action, click arrow = popup menu |
| popup menu | `GuiMenu(items, rects, hot)` | overlay layer, keyboard Up/Down/Enter/Esc, dismiss on outside click |
| combobox | `GuiCombo(box, list, sel)` | a `gui_textbox` plus a popup list; typed value or a pick |
| colour grid | `GuiColors(palette, rects, sel)` | Word's 10x6 theme grid and 10 standard colours, "automatic"/"no colour" |
| gallery | `GuiGallery(items, rects, scroll)` | style tiles drawn in their own style |
| scrollbar | `GuiScroll(v, thumb, range)` | track, thumb, arrows, drag, wheel |
| tooltip | `GuiTip(text, x, y)` | after hover delay; one at a time |
| dialog | `GuiDialog(title, body, buttons)` | modal overlay with a backdrop, Enter/Esc |
| icon | `vec_icon(id, px, color, x, y)` | see 3.5.4 |

#### 3.5.4 Icons

Icons are drawn in `id`, tinted at draw time:

* **v1 baseline (always available):** letters (B, I, U with underline, S
  struck, A with a colour bar, x2/x2) set in the UI face, and rectangles
  (alignment bars, indent arrows, bullet dots and bars) via `d2_l_rect`. Word's
  own Home tab is mostly this.
* **Vector icons (A6):** a path string per icon (`M 3 4 L 12 4 Q ...` , a small
  SVG subset), parsed once at start-up into flattened integer contours, rasterised
  by the **same exact-area coverage code the font module already has**
  (`idstd/core/data/seq/byte/ttf/ras/`), extracted behind a public entry
  (`ras_fill`) so there is one rasteriser, not two. Bitmaps are cached per
  `(icon, size)` and tinted per use (coverage x colour), so a frame builds no list
  and no string. Undo/redo arrows, folder, floppy and the paste clipboard need it;
  decision 7.6 is whether to depend on it in v1 or ship the baseline first.

#### 3.5.5 Event routing

One loop in `ui/app`: `gfx_event` -> if a dialog is open, it gets everything; else
if a popup is open, it gets everything and a click outside dismisses it; else mouse
events go by rectangle to ribbon, canvas, scrollbar, status bar or find bar; key
events go to the focused text box (find bar, combobox) else to the shortcut table
(3.7) else to the canvas (caret keys, TEXT events insert). Clicking a ribbon
control must **not** steal the document's selection: the canvas keeps the
selection and a "document has focus" flag; the text box rule "a press outside gives
the keyboard up" (UI.md 7b) is how the find bar loses focus.

### 3.6 ODT reading and writing

#### 3.6.1 Where the code lives

| piece | home | why |
| --- | --- | --- |
| CRC-32 | `idstd/core/data/seq/byte/sum/` | generic; the zip reader and writer both need it |
| ZIP reader and writer | `idstd/core/data/seq/byte/pack/zip/` | generic, and the editor's reader is the only copy: it moves out as a struct-based module (`Zip`, `ZipW`), prefix `zr_`/`zw_` |
| DEFLATE compressor | `idstd/core/data/seq/byte/pack/deflate/` | pairs with `inflate`; v2 |
| XML reader (struct-based pull parser) and writer | `idstd/core/text/xml/` | the editor's `xml_` is a global-state parser and idstd's font-config reader (`xt_`) is a second, purpose-built one; one shared library is what "duplicates go to idstd" asks for |
| ODT model mapping (elements to rows, styles, lists, page layout) | `word/io/odt/` | ODT-specific, one project |

New prefixes (`zr_`, `zw_`, `xr_`, `xw_`, `crc_`, `df_`) are chosen so that nothing
collides with the legacy editor's `zip_`/`xml_`/`odt_` while both are alive
(function names are program-wide; idstd is merged into every build,
`editor/NAMES.md`).

#### 3.6.2 The writer, in order

1. `mimetype`: first entry, **stored**, no extra field, content
   `application/vnd.oasis.opendocument.text`.
2. `META-INF/manifest.xml`: `manifest:file-entry` for `/` (with
   `manifest:media-type` the same string and `manifest:version="1.3"`), `content.xml`,
   `styles.xml`, `meta.xml`, plus every preserved part.
3. `meta.xml`, `styles.xml` (fonts `office:font-face-decls`, `office:styles`:
   default style, named styles, list styles, `office:automatic-styles`
   with `style:page-layout`, `office:master-styles` with the `Standard` master page).
4. `content.xml`: `office:font-face-decls`, `office:automatic-styles` (one `P<n>`
   per used paragraph row, one `T<n>` per used character row, `L<n>` per list),
   `office:body/office:text` with `text:p`/`text:h` (outline level from the
   style), `text:span`, `text:s`/`text:tab`/`text:line-break` for runs of spaces
   and tabs (XML collapses literal runs of spaces), `text:list` nesting, `text:a`
   for hyperlinks, `fo:break-before="page"` for page breaks, opaque blocks verbatim.
5. Entries are **stored** in v1 (LibreOffice opens stored ODTs); v2 adds deflate
   (C1). The ZIP writer emits local headers with real CRC-32 and sizes (no data
   descriptors), then the central directory, then the end record; it refuses
   Zip64 sizes with a named error.

Property mapping (written and read): bold `fo:font-weight="bold"`, italic
`fo:font-style="italic"`, underline `style:text-underline-style="solid"` plus
width/colour, strike `style:text-line-through-style="solid"`, size
`fo:font-size="12pt"`, family `style:font-name` (`svg:font-family` in the
face-decl), colour `fo:color`, highlight `fo:background-color`, super/sub
`style:text-position="super 58%"`/`sub 58%`, alignment `fo:text-align`
(`start|center|end|justify`), indents `fo:margin-left`/`-right`/`fo:text-indent`,
spacing `fo:margin-top`/`-bottom`, `fo:line-height` as a percentage, page
`fo:page-width`/`-height`/`fo:margin-*`/`style:print-orientation`.

### 3.7 Shortcuts (v1)

`Ctrl+N O S`, `F12` (Save As, when F-keys arrive as events, else `Ctrl+Shift+S`),
`Ctrl+Z`, `Ctrl+Y`/`Ctrl+Shift+Z`, `Ctrl+X C V A`, `Ctrl+B I U`, `Ctrl+L E R J`,
`Ctrl+F H`, `Ctrl+Enter`, `Ctrl+[`/`]` font size, `Ctrl+Shift+L` bullets,
`Ctrl+Alt+1/2/3` headings, `Ctrl+0`/`Ctrl+wheel` zoom, `Ctrl+Home/End`, `Ctrl+arrows`,
`Tab`/`Shift+Tab` list level. The table is data in `word/conf.id`:
`[mods * 4096 + key, cmd]` pairs.

### 3.8 Where each piece lives, summarised

| piece | home | package |
| --- | --- | --- |
| directory room, moves | `idstd/core/data/seq/byte`, `idstd/core/text` | W0 |
| CRC-32, ZIP read/write | `idstd/core/data/seq/byte/{sum,pack}` | A1 |
| XML writer | `idstd/core/text/xml/write` | A2 |
| XML reader | `idstd/core/text/xml/read` | A2r |
| font style discovery, family list | `idstd/gfx/kit/gui/font/find` | A3a |
| code-point text API, faux styles | `idstd/gfx/kit/gui/font/face`, `seam` | A3b |
| clip, alpha rect, window title, list helpers | `idstd/gfx/px/l`, `idstd/sys/win/gfx`, `idstd/core/data/seq/lst` | A4, A7 |
| widgets | `idstd/gfx/kit/wid/{ctl,pop}` | A5a, A5b, A5c |
| path rasteriser, icons | `idstd/core/data/seq/byte/ttf/ras` (entry), `idstd/gfx/kit/wid/vec` | A6 |
| document model | `word/core/doc` | B1 |
| edit, selection, undo, clipboard, find | `word/core/edit` | B2 |
| layout, pagination, hit testing | `word/core/lay` | B3a, B3b |
| ODT read | `word/io/odt/read` | B4a, B4b |
| ODT write | `word/io/odt/write` | B5a, B5b |
| canvas view, scroll, zoom | `word/ui/page` | B6 |
| ribbon data, layout, paint, events | `word/ui/ribbon` | B7a, B7b |
| app shell, file ops, dialogs, status/find bars, CLI | `word/ui/app` | B8, B10 |
| oracle driver, corpus | `wordcheck/` | B9 |

---

## 4. Seams

These are the contracts. A package may add functions under them; it may not
change a signature without a note in this file. Notation: `name(type a, ...) ->
type`. A struct is declared in a file of its own (SPEC 1.2); one to three fields.
Exact field names count for uniqueness (STRUCTS Q4), so names below are final.

### 4.1 Document structs (`word/core/doc`, owner B1)

```
struct Pos { int para; int off; }
struct Sel { Pos anchor; Pos caret; int goal; }
struct Run { int len; int cprop; int link; }
struct Text { int[] cps; Run[] runs; int rev; }
struct Lay { int[] lines; int[] pen; int h; }
struct Para { Text txt; Lay lay; int pprop; }
struct Tab { int[] rows; int width; int[] slots; }
struct Style { string name; int[] rel; int[] fmt; }
struct Sty { Style[] styles; ListDef[] lists; int rev; }
struct ListDef { string name; int[] levels; int kind; }
struct Fmt { Tab chars; Tab paras; Sty sty; }
struct Page { int[] size; int[] margin; int[] hf; }
struct Part { string name; int[] bytes; int kind; }
struct Ext { string[] fonts; string[] links; Part[] parts; }
struct Body { Para[] paras; Page page; int rev; }
struct Doc { Body body; Fmt fmt; Ext ext; }
```

`Page.size = [w, h, orient]` twips (orient 0 portrait, 1 landscape);
`Page.margin = [top, right, bottom, left]`; `Page.hf = [header_h, footer_h,
flags]` (reserved for v2, written and read as zero in v1). `Tab.slots` is the
open-addressing index into `rows` (row `r` starts at `r * width`).

Constants (`word/conf.id`): `word_c_style word_c_font word_c_size word_c_color
word_c_hl word_c_on word_c_set` (character row offsets, width 7);
`word_p_style word_p_align word_p_left word_p_right word_p_first word_p_before
word_p_after word_p_line word_p_brk word_p_list word_p_level word_p_kind` (width 12);
flag bits `word_f_bold` ... `word_f_sub`.

### 4.2 Model API (B1; everyone else calls it)

```
doc_new() -> Doc
doc_title(Doc d) -> string
doc_count(Doc d) -> int
para_len(Para p) -> int
para_cp(Para p, int off) -> int
para_run(Para p, int off) -> int
para_cprop(Para p, int off) -> int

tab_intern(Tab t, int[] row) -> int
tab_get(Tab t, int id, int field) -> int
tab_with(Tab t, int id, int field, int value) -> int
tab_with_bits(Tab t, int id, int bits, int on) -> int

fmt_default(Fmt f) -> void
style_find(Fmt f, string name) -> int
style_eff_c(Fmt f, int pstyle, int cprop, int field) -> int
style_eff_p(Fmt f, int pprop, int field) -> int
style_bits(Fmt f, int pstyle, int cprop) -> int

text_insert(Text t, int off, int[] cps, int cprop) -> void
text_delete(Text t, int lo, int hi) -> void
text_runs_set(Text t, int lo, int hi, int[] runs) -> void
text_patch(Text t, int lo, int hi, Tab chars, int field, int value) -> void
text_merge(Text t) -> void

body_split(Body b, int para, int off) -> void
body_join(Body b, int para) -> void
body_insert(Body b, int index, Para p) -> void
body_remove(Body b, int index) -> void
```

`tab_with` returns the id of the row equal to row `id` with `field` set. Every
function that edits a `Text` keeps the run invariants (covering, non-empty except
the single run of an empty paragraph, merged). Cases in B1 pin exactly those
invariants.

### 4.3 Edit API (`word/core/edit`, owner B2)

```
struct Op { int kind; int[] at; int[] data; }
struct Txn { Op[] ops; Sel before; Sel after; }
struct Hist { Txn[] undo; Txn[] redo; int open; }
struct Frag { Text[] txts; int[] pprops; int partial; }
struct Ctl { Sel sel; Hist hist; Frag clip; }

op_apply(Doc d, Op o) -> Op
txn_begin(Ctl c) -> void
txn_end(Ctl c) -> void
hist_undo(Doc d, Ctl c) -> int
hist_redo(Doc d, Ctl c) -> int

ed_type(Doc d, Ctl c, int cp) -> void
ed_enter(Doc d, Ctl c) -> void
ed_back(Doc d, Ctl c, int word) -> void
ed_delete(Doc d, Ctl c, int word) -> void
ed_move(Doc d, Ctl c, int dir, int unit, int extend) -> void
ed_select_all(Doc d, Ctl c) -> void
ed_select_word(Doc d, Ctl c, Pos p) -> void
ed_set_char(Doc d, Ctl c, int field, int value) -> void
ed_toggle(Doc d, Ctl c, int bit) -> void
ed_set_para(Doc d, Ctl c, int field, int value) -> void
ed_set_style(Doc d, Ctl c, int style) -> void
ed_clear_format(Doc d, Ctl c) -> void
ed_page_break(Doc d, Ctl c) -> void
ed_copy(Doc d, Ctl c) -> string
ed_cut(Doc d, Ctl c) -> string
ed_paste(Doc d, Ctl c, string text) -> void
sel_state(Doc d, Ctl c, int field) -> int
find_next(Doc d, Pos from, int[] needle, int flags, Pos hit) -> int
find_replace_all(Doc d, Ctl c, int[] needle, int[] with, int flags) -> int
count_words(Doc d) -> int
```

`dir` is -1 left/up, +1 right/down; `unit` 0 char, 1 word, 2 line, 3 paragraph,
4 page, 5 document; the line and page units call layout through a function value
the caller passes at start-up (`ed_layout_hooks`, stored in an export), so
`core/edit` does not depend on `core/lay`. `sel_state` returns 0 off, 1 on, 2
mixed for flag fields and the effective value (or -2 for mixed) for the others.
Every edit function ends with `txn_end` unless it coalesces.

### 4.4 Layout API (`word/core/lay`, owners B3a, B3b)

```
struct Face { int[] hnd; int[] key; int zoom; }
struct Pages { int[] starts; int[] tops; int count; }
struct View { Doc doc; Pages pages; Face faces; }

face_for(Face f, Fmt fmt, int pstyle, int cprop, int zoom) -> int
lay_para(View v, int i, int width_lu) -> void
lay_all(View v) -> void
lay_relayout(View v) -> int
lay_paginate(View v, int from) -> int
lay_page_count(View v) -> int
lay_hit(View v, int page, int x_lu, int y_lu, Pos out) -> void
lay_caret(View v, Pos p, int[] out) -> void
lay_line_of(View v, Pos p) -> int
lay_line_start(View v, Pos p, Pos out) -> void
lay_line_end(View v, Pos p, Pos out) -> void
lay_move_line(View v, Pos p, int dir, int goal, Pos out) -> void
lay_sel_rects(View v, Sel s, int page, int[] out) -> int
```

`lay_relayout` returns the number of paragraphs relaid. `lay_caret` writes `[page,
x, y, h]` in lu from the page's top-left. The View also owns the numbering
counters pass for lists.

### 4.5 Font seam (idstd, A3a/A3b; as in 3.3.1)

```
gui_face(string family, int px, int style) -> int
gui_face_file(string path, int px, int style) -> int
gui_face_real(int f) -> int
gui_cp_adv(int f, int cp, int next) -> int
gui_cp_draw(int f, int x64, int base, int cp, int color) -> void
gui_fonts_find_style(string family, int style) -> string
gui_font_families() -> string[]
```

Until A3a lands, A3b implements `gui_face` over `gui_fonts_find` (regular only) so
B3 and B6 are never blocked.

### 4.6 ODT API (`word/io/odt`, owners B4, B5)

```
odt_load(string path, Doc d) -> int
odt_load_bytes(int[] zip, Doc d) -> int
odt_save(string path, Doc d) -> int
odt_save_bytes(Doc d) -> int[]
odt_error(int code) -> string
```

Return 0 on success, otherwise a code whose message names the fix (the project's
"errors must name the fix" rule). `odt_load` fills an empty `Doc` made by
`doc_new`. Nothing in these two files may touch the window.

#### 4.6a The styles reader (`word/io/odt/read/styles`, owner B4b)

B4a (content) and B4b (styles) meet at these functions and nowhere else. B4b
reads `styles.xml` and the automatic styles, font faces and list styles of
`content.xml`; it never reads the body. B4a reads the body and asks B4b what each
style name means.

```
struct OdtSty { string[] keys; int[] ids; int[] over; }
ost_new() -> OdtSty
ost_load(Doc d, int[] styles_xml, int[] content_xml, OdtSty k) -> int
ost_error(int code) -> string
ost_fault_at(int[] xml) -> int

ost_para(OdtSty k, string name) -> int
ost_over(OdtSty k, string name) -> int
ost_text(OdtSty k, string name) -> int
ost_list(OdtSty k, string name) -> int
ost_merge(Doc d, int under, int over) -> int
```

`ost_load` is called once, on a `Doc` from `doc_new`, with the bytes of the two
parts. It fills `d.fmt.sty` (named styles, list styles), `d.ext.fonts` and
`d.body.page`, and fills `k`. It answers 0, or `ost_e_styles` (50) or
`ost_e_content` (51) when that part is not well-formed XML before the body;
`ost_error` words the fix and `ost_fault_at(xml)` gives the byte (-1 when
well-formed). B4 owns `odt_error` codes 1 to 99 and B5 100 to 199; B4b uses 50 to 59.

What B4a does with a paragraph or run, with `name` the file's style name as
written (`Heading_20_1`, `P1`, `T3`; `""` and an unknown name give the defaults):

| element | call | result |
| --- | --- | --- |
| `text:p`, `text:h` `text:style-name` | `ost_para(k, name)` | the paragraph row (`word_p_style` set, `brk` and `list` flattened from the style chain); store it as `Para.pprop` |
| inside `text:list` | `tab_with(d.fmt.paras, row, word_p_list, ost_list(k, outer_list_name))`, then `word_p_level` | list and level are the content reader's; only the outermost list's name counts |
| text of that paragraph | `ost_over(k, name)` | the character row an **automatic** paragraph style's own text properties amount to (`P1` with a font size); `-1` for none and for named styles, whose properties the style chain already resolves. Start every run from `max(over, 0)` |
| `text:span` `text:style-name` | `ost_text(k, name)` then `ost_merge(d, enclosing, that)` | the run's `cprop`: the span's fields laid over the enclosing run's (the paragraph's `over` for an outermost span); fields the span leaves unspecified keep the enclosing value, flags merge bit by bit, a character style on the span replaces the enclosing one |

What `ost_load` decides, so the content reader need not:

* Lengths are twips (`cm mm in pt pc px`, exact rational rounding half away from
  zero), font sizes half-points; a `%` font size is resolved against the style it
  inherits from when the styles are read (12 pt when nothing gives a size); a `%`
  `fo:line-height` is the percentage and a length line height is left unset.
* Named styles are found in the model by model name and family (`Standard` is
  Normal, a `style:display-name` wins, otherwise each `_20_` is a space) and
  replace its rows in place, so the index of Heading 1 is stable; styles the
  model lacks are appended. **Normal is the default paragraph style with
  `Standard` laid over it**, and a paragraph style with no parent gets Normal as
  its parent. Nothing the file leaves unset is filled in from the built-in
  rows, so a field no style sets stays `-1` (the layout's default applies).
* Automatic styles are flattened into rows and never become model styles
  (3.1.3); the writer's names (`WP<n>`, `WT<n>`, `WL<n>`) and LibreOffice's
  (`P1`, `T1`, `L1`) are read the same way, from either part. A name defined in
  both parts is the content part's.
* Font families come from `style:font-name` through `office:font-face-decls`
  (`svg:font-family` unquoted) or `fo:font-family`, deduplicated into `ext.fonts`.
* List styles keep levels 1 to 3 (kind, bullet code point or number format, start,
  left indent, hanging indent in twips; the label-alignment and the older
  space-before/min-label-width spellings); the others are dropped. Levels a list
  style does not describe keep the built-in bullet defaults.
* `d.body.page` is the layout of the master page the first paragraph's style
  names, else of the first master page: width, height, orientation (from
  `style:print-orientation`, else from the shape) and four margins.
* Not read: headers and footers, tab stops, `fo:margin` shorthand, line numbering,
  letter spacing, borders, shading of paragraphs, asian and complex fonts.

### 4.7 idstd archive and XML seams (A1, A2, A2r)

```
crc_32(int[] xs, int lo, int hi) -> int
crc_update(int crc, int[] xs, int lo, int hi) -> int

struct Zip { int[] bytes; int[] dir; string[] names; }
zr_open(int[] bytes) -> Zip
zr_count(Zip z) -> int
zr_name(Zip z, int i) -> string
zr_find(Zip z, string name) -> int
zr_read(Zip z, int i) -> int[]
zr_ok(Zip z) -> int
zr_why(Zip z) -> string

struct ZipW { int[] out; int[] dir; string[] names; }
zw_new() -> ZipW
zw_add(ZipW z, string name, int[] data, int method) -> void
zw_finish(ZipW z) -> int[]

struct XmlW { int[] out; string[] open; int state; }
xw_new() -> XmlW
xw_decl(XmlW w) -> void
xw_start(XmlW w, string name) -> void
xw_attr(XmlW w, string name, string value) -> void
xw_text(XmlW w, string text) -> void
xw_end(XmlW w) -> void
xw_done(XmlW w) -> int[]

struct XmlR { int[] src; int[] st; string[] strs; }
xr_open(int[] src) -> XmlR
xr_next(XmlR r) -> int
xr_get(XmlR r, int k) -> string   // k is xr_k_name (the element name) or xr_k_error (the first fault)
xr_attr(XmlR r, string name) -> string
xr_text(XmlR r) -> string
xr_depth(XmlR r) -> int
```

`xr_next` returns an event code (1 start, 2 end, 3 text, 4 empty element, 0 done,
-1 error); names are as written (`text:p`) in v1, with `xr_ns` resolution an
optional later addition; the **pull model is kept** (events, not a tree) because
a tree of structs would never be freed. `zw_add` method 0 stored, 8 deflate
(v2); `mimetype` is written first by the **caller**, the writer only keeps
insertion order. `xw_text` escapes `& < >` and `xw_attr` also `"`.

### 4.8 Ribbon and widget seams (B7a, A5)

```
struct GuiButton { int[] v; string label; int icon; }
btn_new(string label, int icon, int cmd) -> GuiButton
btn_place(GuiButton b, int x, int y, int w, int h) -> void
btn_event(GuiButton b, int kind, int[] ev) -> int
btn_draw(GuiButton b) -> void

struct Ribbon { int[] items; int[] rects; int[] state; }
rib_build(int tab) -> Ribbon
rib_place(Ribbon r, int x, int y, int w, int h) -> void
rib_event(Ribbon r, int kind, int[] ev) -> int
rib_cmd(Ribbon r) -> int
rib_arg(Ribbon r) -> int
rib_draw(Ribbon r) -> void
cmd_run(App a, int cmd) -> void
cmd_run_arg(App a, int cmd, int arg) -> void
cmd_state(App a, int cmd) -> int
key_cmd(int mods, int key) -> int
```

Widget names carry the `gui_` prefix in idstd (`gui_btn_*` etc.) to match NAMES
1.19; the short names above are for reading. `rib_event` returns the same bit
protocol as `gui_textbox_event`; `rib_cmd` is the command to run after bit 2.

### 4.9 App seam (B8)

```
struct App { Doc doc; Ctl ctl; Ui ui; }
struct Ui { View view; Ribbon rib; Shell shell; }
struct Shell { string path; int dirty; int[] cam; }
app_new() -> App
app_frame(App a) -> int
app_open(App a, string path) -> int
app_save(App a, string path) -> int
app_title(App a) -> string
```

CLI modes of the binary (the test surface for the oracle driver, no window):
`word --text IN.odt` prints the plain text; `word --dump IN.odt` prints a
normalised paragraph/run/property dump; `word --roundtrip IN.odt OUT.odt` loads and
saves; `word --render IN.odt OUT.ppm [--page N] [--zoom Z]` lays out and paints one
page; `word --pages IN.odt` prints the page count and the first paragraph on each
page; `word --script FILE [IN.odt [OUT.odt]]` replays recorded events (a text script of
key, text and mouse events, and the shell's own: new, open, save, close, dialog
buttons) against a document, in an application with no window, and saves it to OUT
when given, so an editing session is a testable string (the same idea as
`idstd_gui_tbt_play`; the verbs are listed in `word/NAMES.md`, section B8, and an
upper case verb is `ed_play`'s). `--render` writes a binary PPM (P6). A line that is
none of these prints the usage and answers 2.

#### 4.9a The `--dump` format (defined by B4b; shared by B4a, B5a, B8, B11)

`word --dump IN.odt` prints `ndump_doc(Doc d) -> string` (`word/io/odt/read/styles/out/dump`):
UTF-8, one record per line, LF line ends, a final LF. It is the one text form of
a `Doc` that two documents share when they look the same, whatever their row ids,
style numbering or run boundaries: B4a and B4b compare it with LibreOffice's, B5a
compares it before and after a round trip, B2's undo cases may use it too. Its
other side is `wordcheck`'s oracle, which makes the same text from the `fodt`
that `soffice --convert-to fodt` writes for the same file, with its own code
(`wordcheck --oracle N` prints it).

```
page w=11906 h=16838 orient=0 top=1134 right=1134 bottom=1134 left=1134
para 0 style="Heading 1" align=- left=- right=- first=- before=240 after=120 line=- brk=0 level=0 list=-
run b=1 i=0 u=0 s=0 sup=0 sub=0 size=36 color=#ff0000 hl=- link="http://x" font="Liberation Sans" text="Chapter\tOne"
para 1 opaque
para 2 style="Normal" align=1 left=720 right=0 first=-360 before=0 after=120 line=115 brk=1 level=1 list=n:0:1:1134:283
```

* One `page` line, then for each paragraph in order a `para` line and its `run`
  lines. An opaque block (`kind` 1) is `para N opaque` and nothing else; an empty
  paragraph has no run lines.
* A line is a record word and `key=value` pairs in the order above, one space
  apart. A value is a bare token or a double-quoted string.
* **Every value is effective**: resolved through the run's character style, the
  paragraph's style chain and the default style, never a row id and never the name
  of an automatic style. `-` means no layer sets it. Lengths are twips, `size` is
  half-points, `color` and `hl` are `#rrggbb` in lowercase, the six flags are 0 or 1
  (`b i u s sup sub`), `align` is 0 left, 1 centre, 2 right, 3 justify, `line` is
  percent of single, `brk` is 1 when the paragraph's style chain has a page break
  before it. A length of exactly -1 twip prints 0 (the model's -1 means unset).
* `style` is the **named** style the paragraph sits on (an automatic style prints
  its parent), by the model's name: `Standard` is `Normal`, a display name wins,
  otherwise `_20_` reads as a space.
* `list` is `-` outside a list; inside one it is the level the paragraph sits on:
  `b:CODEPOINT:LEFT:HANG` for a bullet, `n:FORMAT:START:LEFT:HANG` for a number
  (FORMAT 0 decimal, 1 lower alpha, 2 upper alpha, 3 lower roman, 4 upper roman;
  indents in twips); `level` is 0 to 2. The list definition's id never appears.
* **Runs are merged**: adjacent runs whose printed fields (all but `text`) are
  equal are one run with their texts joined, so where a writer chose to split
  spans does not matter. `link` is the target in quotes or `-`; `font` is the
  family in quotes or `-`.
* `text` is quoted: `\"`, `\\`, `\t`, `\n`, `\r`; printable ASCII as itself;
  every other code point as `\u{hex}` in lowercase with at least four digits;
  **every code point U+E000 to U+F8FF, and every code point from `word_o_marker`
  (U+F0000, where the readers keep an inline object's marker plus its index) to
  U+FFFFD, prints as `\u{e000}`** (whichever index it carries). A tab is `\t`, a line break `\n`, `text:s c`
  is `c` spaces.
* `page` is the page of the master page the first paragraph's style names, else of
  the first master page, in the sizes of `Page` (3.1.5): `orient` is 0 portrait,
  1 landscape. The other master pages of a file are not part of a `Doc`, so not
  of a dump.

`wordcheck --dump N WORDBIN [ASSETS]` converts fixture N with `soffice
--convert-to fodt`, runs `WORDBIN --dump` on the same `.odt`, and prints `N STEM
dump=OK` (exit 0), or `N STEM dump=FAIL` and one line per differing field,
`pN rM FIELD: ours=A theirs=B` (`page FIELD`, or `pN FIELD` for a paragraph record;
`records differ` when the words or the number of fields do not match), exit 1;
2 for a missing fixture. `ASSETS` defaults to `wordcorpus`; a directory of your
own with an `odt/` inside and files named `NN_name.odt` works.


---

## 5. Phased plan

### 5.1 Conventions that apply to every package

* Every function has two cases or an explicit CLI opt-out (docs/TESTS.md); case
  counts are verified with `idc/tools/casework.sh list`, and a package that
  deletes functions to go green is a failure (count cases before and after).
* No inline comments; no function with more than three actions; three entries per
  directory; no duplicate logic; one concern per change.
* A case that writes `/tmp` uses `fs_mktemp` (randomised names), never a fixed path, and registers it with `fs_drop_exit` (docs/TESTS.md).
* No command over 60 s (memory: sixty-second rule; three-minute task limit).
  Anything slower (every `soffice` run) is **index-addressable and resumable**: the
  driver takes a fixture index and processes that fixture only, and a full sweep is
  the caller looping.
* Parallel `idc` runs clobber idstd's `.gen.o` (memory: concurrent verify race):
  each agent builds in its own workspace copy with its own `IDSTD_HOME`.
  "harness did not build" with `errors=1/failed=0` means a race, not a red case.
* Subagents cannot write under `/home/preland/git` (memory: subagent write
  guard): they work in a workspace copy and the main session merges. `NAMES.md` and
  `idstd/conf.id` are shared files every idstd package edits; each package adds
  rows in its own section only and merges are done one at a time, never
  union-merged.
* New idstd names need `NAMES.md` rows and the `idstd_` prefix rules for
  internals (`idstd/run.sh` enforces).
* Build-time budget per package: measure `idc` of the package's program and of a
  hello program before and after; note the delta in the commit. See 6.1.

### 5.2 Phase 0 (serial, small)

| id | package | directories | depends | acceptance |
| --- | --- | --- | --- | --- |
| W0 | idstd room: `byte/{pack,sum,ttf}` with `inflate` moved to `pack/inflate` and `sha256` to `sum/sha256`; `core/text/{atom/{chr,fmt},str,xml}` with `chr` and `fmt` moved under `atom/`; a free slot in `core/data/seq/lst`; `gfx/kit/wid/` created empty | `idstd/core/data/seq/byte`, `idstd/core/text`, `idstd/core/data/seq/lst` (moves only), `idstd/NAMES.md` file columns | decision 7.5 | `idc ../idstd` exits 0 with the library's cases green; `idstd/run.sh` passes; `idlayout --room` shows the new slots; no function body changed (diff is renames plus NAMES.md paths) |

The editor/word split is not part of W0: `word/` is a new root (decision 7.1) and
nothing moves out of `editor/` until cutover.

### 5.3 Phase 1: the v1 word processor

Ends when B11 passes: a person can create, open, edit, format, find, replace, save
and re-open plain documents, and LibreOffice opens what we save.

Waves are dependency layers; **everything inside one wave runs in parallel**
(directories do not overlap within a wave, only through the shared `NAMES.md` /
`idstd/conf.id`, handled by sequential merge). A package may start early against
the seam in section 4 with a stub, as noted.

#### Wave 1 (no package depends on another one; all in parallel after W0)

| id | package | directories | depends | acceptance |
| --- | --- | --- | --- | --- |
| A1 | CRC-32; ZIP reader (struct-based, CRC checked) and stored-entry ZIP writer; `mimetype`-first ordering helper | `idstd/core/data/seq/byte/sum/crc32`, `idstd/core/data/seq/byte/pack/zip` | W0 | `crc_32("123456789") = 0xCBF43926`; round trip of 0, 1, 300 and 70 000 byte entries and of an empty archive; reader accepts `editor/test_assets/empty.zip` and a LibreOffice-written `.odt` (committed under `wordcorpus`) with every CRC verified; one flipped bit in an entry is reported as a named CRC error; `soffice --headless --convert-to txt` opens an `.odt` whose parts were written by `zw_*` (manual first, then B9) |
| A2 | XML writer (struct, escaping, declaration, attribute order = call order, nesting check) | `idstd/core/text/xml/write` | W0 | output of a hand-built tree equals expected bytes; `& < > "` escaping cases; unbalanced `xw_end` is a named error; output is accepted by the reader of A2r and by `soffice --convert-to txt` when it is `content.xml` of a fixture |
| A2r | XML reader: the editor's pull parser re-founded on a struct, byte offsets in every error, entities, CDATA, comments, DOCTYPE skipped | `idstd/core/text/xml/read` | W0 | the editor's own `lib/doc/xml` cases ported and green (they are the spec); reads `content.xml`, `styles.xml` of the corpus; fuzz: 1000 truncations of a real `content.xml` give an error or end, never a trap (index-addressable sweep); event stream of the writer's output equals the writer's input |
| A3a | Font discovery by style (parse subfamily from the `name` table the scan already reads; add weight/slant to the cache record; `gui_fonts_find_style`, `gui_font_families`) | `idstd/gfx/kit/gui/font/find/**` | W0 | on this machine DejaVu Sans resolves Bold to `DejaVuSans-Bold.ttf`, Oblique to `DejaVuSans-Oblique.ttf`; an unknown style falls back to Regular and says so; cache file version bumps and an old cache is ignored, not trusted; `gui_font_families` is sorted and unique; all existing font cases still pass |
| A4 | `sf_l_clip`/`sf_l_unclip` honoured by `sf_l_pset` and `d2_l_rect`; alpha rectangle; `gfx_title(string)` native (Linux; macOS translation marked uncompiled); wheel-with-mods check | `idstd/gfx/px/l`, `idstd/gfx/plane`, `idstd/sys/win/gfx` | W0 | pixel cases: rect crossing a clip edge draws only the inside; nested clips intersect; alpha blend of known colours equals hand-computed; `gfx_title` changes the title (checked by `xdotool getwindowname` in a headless X run: manual, recorded) |
| A7 | List helpers: `lst_insert`, `lst_delete`, `lst_splice` for `int[]` and `string[]` | `idstd/core/data/seq/lst/**` (the slot W0 made) | W0 | cases at both ends, empty list, a splice that grows and one that shrinks; trap behaviour out of range is stated and cased |
| B1 | Document model: structs, interning table, style set and defaults, resolvers, text and run primitives, paragraph split/join, default document | `word/core/doc/**`, `word/conf.id` (row offsets) | none (uses `utf8_*`, `lst_*`) | the 4.2 API with cases pinning run invariants after every primitive (covering, merged, empty-paragraph run); a randomised-but-seeded script of 2000 primitive calls keeps the invariants; `style_eff_c` resolves a three-level chain and a character style over a paragraph style; **publishes the struct files first** (within an hour) so B2-B7 can compile against them |
| B7a | Ribbon data and logic without drawing: the table of tabs/groups/controls, command ids, shortcut table, group/column placement solver given control sizes, tooltip text and shortcut text, `cmd_state` plumbing signature | `word/ui/ribbon/model`, `word/conf.id` (ribbon and key tables) | none | every command id appears once in the table and in a shortcut/ribbon/menu route (a case walks the table and checks no id is orphaned, none duplicated); placement of the Home tab at widths 1280, 1024, 900 gives rectangles that do not overlap and fit the width (arithmetic cases, rect lists compared exactly); `key_cmd(ctrl, 'b')` = bold |
| B9 | Oracle driver and corpus | `wordcheck/**`, `wordcorpus/**` | none (needs only the CLI contract of 4.9 and `soffice`) | corpus of 12 documents generated by `soffice --convert-to odt` from small `.fodt`/`.html` sources written in the repo (plain, headings, bold/italic/underline mix, colours, lists three levels, page break, A4/Letter/landscape, long text 20 pages, unicode, empty paragraphs, a table, an image); the driver prints one line per fixture and takes an index (`wordcheck N`); an isolated LibreOffice profile (`-env:UserInstallation=file://` under `fs_mktemp`) so runs do not collide; runs batch several files per `soffice` start; the first fixture completes inside 60 s on a cold start (measure; mitigation in 6.7) |

#### Wave 2 (needs wave 1's seams; parallel within the wave)

| id | package | directories | depends | acceptance |
| --- | --- | --- | --- | --- |
| A3b | Code-point font API and synthetic styles; `gui_face`, `gui_face_file`, `gui_face_real`, `gui_cp_adv`, `gui_cp_draw`; a handle cache keyed on `(family, px, style)` with no string building | `idstd/gfx/kit/gui/font/face/**`, `idstd/gfx/kit/gui/font/seam/**` | A3a signature (stubs over `gui_fonts_find` until it lands) | `gui_cp_adv` equals `gui_text_x` differences for a string on the existing synthetic font (so width, caret, draw still agree, UI.md 7); kerning pair "AV" present in `gui_cp_adv(.., 'A', 'V')` against the font's own table via the existing `.tests/font` method (od + awk); a face with no real bold reports `gui_face_real` bit 1 clear and `gui_cp_draw` paints different pixels from regular (count pixels, hand-built font) |
| A5a | Widgets, base: theme constants, button, toggle, scrollbar, tooltip, shared hit/press helpers | `idstd/gfx/kit/wid/ctl/**` | A4 (clip) | headless cases against `sf_l_*`: a pressed button draws the pressed colour at a known pixel; release outside does not activate; a drag of the scrollbar thumb from y0 to y1 changes the offset by the exact ratio; tooltip appears only after the delay (frozen clock as the text box does) |
| A5b | Widgets, overlays: popup menu, dropdown/split button, gallery, overlay stack with outside-click dismiss | `idstd/gfx/kit/wid/pop/**` | A5a protocol (struct and event bits agreed in 4.8) | keyboard Up/Down/Enter/Esc cases; click outside returns the dismissed bit and the click is **also** delivered to what is under it; a menu near the right/bottom edge flips inside the window |
| A6 | Vector paths and icons: public rasteriser entry extracted from `ttf/ras` (`ras_fill`), SVG-subset path parser to contours, tinted icon cache, the v1 icon set | `idstd/core/data/seq/byte/ttf/ras/**` (entry only), `idstd/gfx/kit/wid/vec/**` | A4 | the existing ttf bitmap cases still pass byte-identical (the extraction changes no glyph); a 10x10 square path covers exactly 100 cells at full coverage; a half-pixel-offset square has the hand-computed edge coverage; each icon renders non-empty at 16 and 24 px; a human looks at a contact sheet (PPM) before sign-off (colour/shape taste is not measured) |
| B2 | Edit core: selection, movement, typing, Enter, Backspace/Delete (char and word), formatting commands, paragraph commands, style apply, clipboard fragments, undo/redo with coalescing, find and replace, word count | `word/core/edit/**` | B1 | for each operation: apply then undo restores the document byte-for-byte (a canonical dump function `doc_dump` compares before and after: this is the central witness); the six primitives each have an inverse-of-inverse case; "type 'hello world', undo, redo" matches the `gui_tb` steps ("hello " and "world"); deleting a selection across three paragraphs then undo; bold toggled over a mixed selection turns on, over an all-bold selection turns off; copy then paste into a second paragraph keeps run properties; `find_next` with match case on and off; Replace All is one undo step; a scripted 2000-keystroke session (via the `--script` player) ends equal to the expected dump and **also** survives undo-to-empty |
| B3a | One-paragraph layout: face resolution, breaking with hanging spaces, justification, mixed fonts and sizes per line, baselines, indents and first-line/hanging, list labels and counters, default tabs, line and paragraph spacing | `word/core/lay/para/**` | B1; A3b (use `gui_face_file` on committed Liberation Sans for deterministic cases) | arithmetic cases worked by hand in each case's header (as UI.md section 9 does): "AAAA BBBB" in a face with known advances wraps at the computed width; a line holding 12 pt and 24 pt runs has the 24 pt ascent and descent; justify gives every non-last line the full width with remainder distribution; hanging indent label sits at `left - hanging`; numbering `1. 2. 3.` then a level-2 item then back to `4.`; superscript lifts by the configured percentage; no struct and no string allocated per pass (checked by running 10 000 passes under `ID_FREE_STATS`/memory counter and reading the growth, 6.3) |
| B4a | ODT read, content: paragraphs and headings, spans, `text:s`/`tab`/`line-break`, lists, hyperlinks, page-break-before, opaque capture of everything unmodelled, preserved zip parts | `word/io/odt/read/content/**` | B1, A1, A2r | `word --text` equals `soffice --convert-to txt:Text` on every corpus fixture (the oracle; exact string compare after normalising the trailing newline); paragraph count equals the count of `text:p`/`text:h` read independently with the XML reader; the table fixture yields one opaque block and its XML is preserved byte for byte; an unknown element's text is never silently merged into a run; malformed input gives a named error with a byte offset |
| B4b | ODT read, styles: `styles.xml` and `content.xml` automatic styles into rows, parent chains, default style, list styles, page layout (`fo:page-width`...), font-face-decls, unit conversion | `word/io/odt/read/styles/**` | B1, A1, A2r | `word --dump` compared with `soffice --convert-to fodt` of the same file, parsed by A2r, on bold/italic/underline/strike/size/colour/highlight/alignment/indent/spacing for every corpus paragraph (the dump normalises both sides; mismatches print the paragraph index and field); page size of the A4, Letter and landscape fixtures equals LibreOffice's; unit conversion cases for `cm mm in pt` and `%` |
| B5a | ODT write, content: `content.xml` with automatic styles from used rows, runs, lists, links, page break, opaque blocks verbatim | `word/io/odt/write/content/**` | B1, A1, A2 | for every corpus fixture: `word --roundtrip` output, then **(i)** our reader gives an identical `--dump` (self round trip), **(ii)** `soffice --convert-to txt` equals the original's, **(iii)** `soffice --convert-to fodt` normalised equals the original's normalised fodt for modelled properties; LibreOffice exits 0 on each |
| B5b | ODT write, package: `mimetype` first and stored, `manifest.xml`, `meta.xml`, `styles.xml` (named styles, list styles, page layout, master page, font decls), preserved parts | `word/io/odt/write/package/**` | B1, A1, A2 | the first 38 bytes of the file are a local header for `mimetype` with method 0 and the exact content after it (byte-exact case); `manifest.xml` lists every entry; LibreOffice opens a document that contains only a title and saves it unchanged in content; every CRC is verified by our reader; a document with a preserved image part keeps it byte for byte |

#### Wave 3 (needs wave 2)

| id | package | directories | depends | acceptance |
| --- | --- | --- | --- | --- |
| B3b | Pagination, incremental relayout, hit testing, caret geometry, line movement, selection rectangles | `word/core/lay/page/**` | B3a, B1 | page count of 1, 2, 20 page synthetic documents is arithmetic (lines x line height / content height) and the case shows the arithmetic; a `brk` paragraph starts a page; editing the middle of a 100-paragraph document relays out exactly one paragraph (counted by the return value) and repaginates until the page starts match; `lay_hit` followed by `lay_caret` returns the same position for every offset of a three-line paragraph; `lay_move_line` keeps the goal x across a short line; **pagination oracle**: `word --pages` against the page count of `soffice --convert-to pdf` for the text-only fixtures, tolerance 1 page, the PDF page count read from the `/Type /Page` objects (guess that LibreOffice writes them uncompressed; if not, use `/Count` of the page tree; confirm at implementation) |
| B6 | Canvas: pages on grey, shadow, scrolling and camera, zoom, painting of runs/underline/strike/highlight/links/selection/caret, mouse hit and drag selection, ensure-visible | `word/ui/page/**` | B3b, B2, A3b, A4, A5a (scrollbar) | `word --render` produces a PPM whose structure is asserted, not its pixels (the editor's own render-test philosophy: `docs/EDITOR.md` "What is tested"): sheet where expected, no ink outside the sheet, ink left of the right margin, a bold run has more ink than the same text regular, the selection rectangle covers exactly the selected lines (rect list compared), the caret is one pixel wide at the `lay_caret` x; scroll to the last page and the first line of it is at the top; zoom 200 doubles the sheet width; **frame cost**: a 1280x800 repaint of a 20-page document is timed and printed (not asserted) so a budget can be set |
| B7b | Ribbon painting and events over the widgets: tab strip, groups, captions, toggles following `cmd_state`, dropdowns (font, size, styles gallery, colours, line spacing, margins, size, orientation), tooltips, quick-access bar | `word/ui/ribbon/draw/**`, `word/ui/ribbon/event/**` (a second ribbon directory, split from B7a's `model/` by the three-entry rule) | B7a, A5a, A5b | headless: click on the Bold button yields `cmd_bold` after the release; a toggle in state 1 paints a different pixel at its centre than state 0 (hand pixels); the Home tab fits at 1024 px (rect cases); every tooltip string is non-empty and has its shortcut; hovering a control 500 ms (frozen clock) shows exactly one tooltip |
| A5c | Widgets, composite: colour grid, combobox over the text box, dialog (modal, backdrop, default button), file-list widget | `idstd/gfx/kit/wid/pop/**` second tree or `idstd/gfx/kit/wid/ctl/**` (whichever W0 left room in) | A5a, A5b | colour grid returns the exact `0xRRGGBB` of the clicked swatch and "automatic" returns -1; combobox typing a size filters, Enter commits, Esc reverts; a dialog blocks events to what is below (a case sends a click under the backdrop and sees no activation); file list over `exec_ls` sorts directories first |

#### Wave 4 (integration)

| id | package | directories | depends | acceptance |
| --- | --- | --- | --- | --- |
| B8 | App shell: main loop and event routing (3.5.5), window title and dirty marker, file operations (New, Open, Save, Save As with the in-app picker, unsaved-changes dialog), File menu, command dispatch `cmd_run`/`cmd_state`, status bar (page X of Y, words, zoom), CLI modes of 4.9 | `word/ui/app/**` | all of waves 1-3 | `word --script` replays: type, Enter, bold a word, save, reload, `--dump` equals the dump before saving; New then close with no changes exits without a dialog, with changes shows it (headless: the dialog state is observable); title shows the file name and `*` when dirty; the oracle driver passes its self round-trip lane on every fixture; run in a real window once by hand and record what happened (not asserted) |
| B10 | Find and replace bar, word count wiring, `Ctrl+F/H`, highlight all, replace and replace all with the 5-undo rule | `word/ui/app/bar/**` | B8, B2, A5c | `--script` cases: find "the" in a 3-paragraph fixture selects the first, next moves, wrap-around reports; replace all count equals the oracle's (`soffice` headless macro is not used; the expected count is computed by the plain-text oracle: count occurrences in `soffice --convert-to txt` output); undo after replace all restores the dump |
| B11 | v1 hardening and acceptance: the full oracle sweep, the 10 000-keystroke memory test, large-document timing, fixes | none new (fixes in owners' trees, one at a time) | B8, B10 | see 5.5 |

#### Parallelism summary for phase 1

| group | packages that run at the same time | blocked by |
| --- | --- | --- |
| P-A (idstd libraries) | A1, A2, A2r, A3a, A4, A7 | W0 |
| P-B (editor core, wave 1) | B1, B7a, B9 | nothing in `word/` (B1 publishes its struct files first) |
| P-C (wave 2) | A3b, A5a, A5b, A6, B2, B3a, B4a, B4b, B5a, B5b | wave 1 seams |
| P-D (wave 3) | B3b, B6, B7b, A5c | wave 2 |
| P-E (wave 4, serial) | B8, then B10, then B11 | wave 3 |

Waves 1 and 2 together hold up to 6 + 3 + 10 packages; a team of five to eight
agents can keep them full. Wave 3 has four.

### 5.4 Phase 1 end-to-end acceptance (B11)

1. **Oracle sweep** over the whole corpus, resumable by index, the whole sweep a
   loop around `wordcheck N` (each index under 60 s): read parity (`--text`,
   `--dump` vs `soffice` `txt` and `fodt`), write parity (LibreOffice opens our
   output, text equal, modelled properties equal), self round trip, page-count
   tolerance.
2. **Edit-save-reopen**: scripted sessions on three fixtures; the saved file is
   opened by LibreOffice, converted to `txt`, and compared with the expected text.
3. **Memory**: a 10 000-keystroke script on a 20-page document; memory growth
   from the runtime's counters stays under an explicit budget set after the first
   measurement (not guessed here), and the run is under 60 s. Otherwise B2/B3a
   own the leak.
4. **Typing latency**: typing into the middle of a 100-paragraph document relays
   out one paragraph; the time of that relayout and of the repaint is printed.
5. **Build budget**: cold idstd pre-check and the `word` build are each measured
   and recorded; either over 45 s is escalated (6.1).
6. **By hand**: open a real document from the user's disk, edit, save, open in
   LibreOffice, read it. Recorded as "worked / did not", not asserted.
7. **Cutover** (decision 7.7): once 1-6 hold, the legacy editor and its Python
   suites move to `obsolete/`, `docs/EDITOR.md` is replaced by a pointer to this
   file, `idc/tests/editor*.sh` retire.

### 5.5 Phase 2: the next release

Each is its own package or small chain; directories are named so two can run in
parallel. None starts before B11.

| id | package | tier items | depends | notes and acceptance |
| --- | --- | --- | --- | --- |
| C1 | DEFLATE compressor (fixed then dynamic Huffman, lazy matching), `zw_add` method 8 | F3 smaller files | A1 | `inf_inflate(deflate(x)) = x` over 200 seeded inputs; compressed ODT opens in LibreOffice; ratio recorded |
| C2 | Headers, footers, page numbers (`text:page-number`, `text:page-count` fields): model fields, layout reserving height, ODT master-page header/footer, UI (Insert tab: Header, Footer, Page Number) | G3 | B3b, B5b | page numbers on 3 pages read "1 2 3"; LibreOffice's rendering of our footer text matches via `txt` |
| C3a-d | Tables: (a) model and ops (cells as paragraph groups), (b) ODT read/write, (c) layout (column widths, row heights, cell wrap, row splitting across pages), (d) UI: insert grid, add/remove rows and columns, borders | I4 | B4a/B5a, B3b | round trip of the corpus table; cell text equals `txt`; undo of every table op |
| C4a-d | Images: (a) PNG decoder over `inf_inflate`, (b) layout of an inline object, (c) ODT `draw:frame`, `Pictures/`, (d) insert and resize UI | I5 | B3b, B4a | decoded pixels equal the file's (ImageMagick `convert` produces the reference PPM in the test driver); round trip keeps the `Pictures/` bytes |
| C5 | Hyperlink dialog, edit, remove, `Ctrl+click`, symbols dialog | I3, I6 | A5c | dialog flows via `--script` |
| C6 | Rulers, tab stops with leaders, indent markers | V5, P8 | B6 | marker drag changes `ind_left` by the right twips |
| C7 | Page Setup dialog, Modify Style dialog, style creation | G7, P10 | A5c | styles survive a round trip through LibreOffice |
| C8 | PDF export: PDF writer with the TrueType font embedded (`/FontFile2`, a `ToUnicode` map, `Widths`) | F7 | B3b, C1 optional | PDF opens in LibreOffice (`soffice --convert-to txt` of the PDF via its import filter) and the extracted text equals the document's; no `pdftotext` is installed here, so this is the only text oracle; layout identical to the canvas because it draws from `Lay` |
| C9 | File backstage page, recent files | F6 | B8 | order and de-duplication cases |
| C10 | Widow/orphan, keep with next, exact line spacing, font fallback | P7, C9 | B3b, A3b | arithmetic cases |
| C11 | Format Painter, change case, autocorrect/auto-list | C6, C8, E10 | B2 | `--script` cases |
| C12 | Collapse/adapt ribbon to narrow windows | R9 | B7b | rect cases |

Later (not scheduled): print, `.docx`/`.rtf` import, JPEG, columns/sections,
footnotes, TOC, comments and tracked changes, spell check, right-to-left and
shaping, drawing objects, equation editor, macros, macOS-only polish, Alt key tips.

---

## 6. Risks and language limits

| # | risk | why it bites here | mitigation |
| --- | --- | --- | --- |
| 6.1 | **Build time under the 60 s rule.** idstd's library pre-check runs once per library content and is cached; any idstd edit invalidates it for every program. UI.md measured about 10 s cold with the toolkit slice (5 s before) and noted an unused-constant cost on every program (1.3 s warm, 14.9 KB). This plan adds zip, xml, deflate, widgets, vectors, font changes and their cases: a guess is +20-40 s cold | every parallel agent pays the cold check after each idstd merge; the editor/`word` tree itself grows to many hundreds of functions with cases | measure at each package merge (budget +3 s per package, escalate at 45 s total, hard limit 60 s); keep cases cheap (no soffice, no big loops); ask for the compiler to drop unreachable constants (UI.md already proposes it); keep `word/` a separate root so only its own cases run; a package that blows the budget splits its cases |
| 6.2 | **Three entries per directory and three functions per file** at idstd and `word/` scale | the room in idstd is nil outside `gfx/kit/` (2.3); a ribbon with 60 controls is a lot of tiny files | W0 first, then every package uses `idlayout --room`; depth is a feature (the path is the answer, HACKING.md); the ribbon is **data**, not code, so it costs table rows, not functions |
| 6.3 | **No freeing for strings, structs and per-line lists.** Strings are never freed on any target; structs are not freed; lists are freed only when escape analysis proves they do not escape and a list stored in a struct field is "kept" (SPEC 1.2 "Memory"; MEMORY.md) | a paragraph relaid on every keystroke, a status string per frame, a struct per line would grow memory without bound | text is `int[]`; layout refills lists and allocates no struct or string; no string built per frame (the status bar string is rebuilt only when its numbers change); B3a/B11 run the 10 000-keystroke test and read the runtime's counters (`ID_FREE_STATS=1`, MEMORY.md 2a); if the list refill does not reuse storage (unmeasured, UI.md 3.3) the fix is a `lst_clear`-style helper in A7 |
| 6.4 | **Performance of full re-layout and repaint.** About 3000 glyphs per page; 100 pages = 300 k code points. `gui_cp_adv` per code point is a glyph-table lookup (guess: about a microsecond, so ~0.3 s for a full relayout); a full 1280x800 repaint is about 1 M cell writes plus a present of a 64-bit-cell `int[]` (UI.md measured 4 ms per 2025 glyphs first draw, 2 ms cached, against 59 ms uncached) | opening a large document, resizing, zooming | incremental layout per paragraph (3.3.3); layout at 100% so zoom does not relayout; the first open lays out lazily (visible pages first, the rest in slices of at most 30 ms between events, resumable); dirty rectangles if the repaint exceeds budget; measure both numbers in B6 and B11, do not trust the guess |
| 6.5 | **Multi-face fonts.** Discovery today picks Regular only (UI.md 7); a family may lack Bold or Italic; `.otf` CFF fonts are skipped; ODT documents name fonts the machine lacks (Calibri, Times New Roman) | wrong metrics, different line breaks than LibreOffice | A3a/A3b; rely on fontconfig aliases (already modelled) so Times New Roman maps to Liberation Serif, metric-compatible; synthetic bold/italic as the honest fallback; the default font is `serif`/`sans-serif`; record substitution in a status-bar warning |
| 6.6 | **The action limit and no function values in lists or returns.** A dispatcher over 80 commands, and key handling, are long `if` chains; a block does three actions and an `if`/`else` costs two (`app/run/key/dispatch.id` says so) | long chains of two-way branches are the editor's present shape | commands are ints routed by range with `chain`; the ribbon table is data; `cmd_run_arg` takes the value so dropdowns do not multiply commands; function values only where SPEC 1.1 allows (the layout hooks of 4.3, stored in an export) |
| 6.7 | **`soffice` as an oracle under 60 s.** Cold start of LibreOffice is slow (a guess: 5-20 s); parallel instances share a profile lock; no `pdftotext`, `pdfinfo` or `xmllint` here (checked with `which`); `unzip` and ImageMagick exist | a naive loop hits the limit or deadlocks | batch several files per start; an isolated profile per run under `fs_mktemp`; index-addressable driver; `txt` and `fodt` as oracles (both readable by our own XML reader); PDF only for page counts and C8; if the first cold start alone exceeds 60 s, the driver starts `soffice` listening in the background in one call and converts in later calls (to be confirmed by trying) |
| 6.8 | **Layout parity with LibreOffice is approximate.** LibreOffice's line breaking, spacing and font choices differ from ours; no per-line oracle exists | "pages match" is not a claim we can make exactly | the oracle compares text, properties and page counts (tolerance 1); pixel and look judgements are a human's (the user's instruction: do not benchmark taste); the doc says "approximately" wherever it applies |
| 6.9 | **ODT semantics that differ between Word and LibreOffice** (paragraph mark ownership on merge, spacing collapse, `fo:line-height` meaning, list indentation inheritance) | users expect Word; the only oracle is LibreOffice | follow ODT/LibreOffice (our file format and our oracle); list the deliberate divergences from Word in the user manual later; each is a case |
| 6.10 | **Name collisions: a name has one type per unit; function names are program-wide; one declaration per struct for the whole program** (SPEC 1.2, STRUCTS Q10) | the legacy editor uses `zip_`, `xml_`, `odt_`, `lay_`, `ed_`; idstd merges into every build; ~15 new structs plus 3 field names that look like `int` names elsewhere | new prefixes for new idstd modules (`zr_ zw_ xr_ xw_ crc_ df_`); `word/NAMES.md` declares the vocabulary up front; the new app is a separate root so it cannot collide with the legacy tree; struct field names are scoped to the struct (Q5) |
| 6.11 | **Structs: no `==`, no `print`, constructors only as initialisers, no struct constants** | a `Pos` compare is two field compares; a default `Sel` has to be built by a function that assigns fields | helpers `pos_eq`, `pos_lt` in B1; `doc_dump` prints the document as text and is the equality oracle for tests; tests construct structs with `given` setups or constructor literals (SPEC 1.2 "In a test case") |
| 6.12 | **Struct reference aliasing** | a `Sel` stored in a `Txn` and then mutated changes history | `sel_copy` is the only way to store one; a case mutates the live selection after saving and checks the saved one |
| 6.13 | **ZIP/PDF/XML written in `id` need bit-exact correctness; no external checker in repo** | one wrong CRC and LibreOffice rejects the file | CRC known vectors; our reader re-checks everything we write; LibreOffice opening the file is the independent oracle; `unzip -t` is available for a manual cross-check (not in the repo's tests) |
| 6.14 | **Case-binding and vacuous-test hazards** (memory: case-binding, vacuous test check, expected-tuple prefix) | wave 2 inserts functions between functions and their cases; round-trip tests that compare a value to itself | each package's acceptance names the **witness** (what has to break for the case to go red); `casework mutate` is used on the central cases (undo restores dump; hit/caret agree; CRC vector), never `git add -A` after it (memory: mutate rewrites files) |
| 6.15 | **idml limits** (no px, no content sizing, no `Repeat`/`define` expansion, 3-children/4-levels rules not enforced natively) | the ribbon cannot be literal idml | decision 7.2: idml for the chrome skeleton, an id flow for ribbon strips; the toolkit's pending `define`/`Repeat`/`fit` work is **not** on this plan's critical path |
| 6.16 | **Window system gaps**: title is fixed at open, F-keys are not events, no HiDPI, no drag-and-drop, clipboard text only and no INCR when serving (large copies refused), the macOS shim is uncompiled | features that need them slip | A4 adds the title; F-keys use alternatives (3.7); large pastes are limited to one X request on the sending side only: document the limit in the UI (a copy of more than that is refused with a status message, to be confirmed in A4's measurement) |
| 6.17 | **Round-trip fidelity of ODT written by LibreOffice** (hundreds of attributes; nested spans; `text:soft-page-break`; change tracking; fields) | silent loss on save is the worst failure of an editor | preserve-by-default policy (3.1.6): unmodelled elements and parts are kept verbatim; the corpus includes documents with features we do not model; the oracle checks that those survive a round trip |

---

## 7. Decisions that need the user

Each is a real fork. Recommendations are marked; none is taken.

**7.1 Where the new application lives.**

| option | tradeoff |
| --- | --- |
| A. a new root `word/` beside `editor/`, legacy retired at cutover (**recommended**) | agents cannot break the legacy 163 assertions; no name collisions with `zip_`/`xml_`/`odt_`/`lay_`/`ed_`; the legacy is a reference until parity. Costs: two trees for a while, and "duplicates across projects go to idstd" applies to anything copied from `editor/` that survives |
| B. rewrite `editor/` in place | one tree and one doc (`docs/EDITOR.md`), no cutover. The legacy's globals, one-unit vocabulary and Python-based suites are in the way of every package, and parallel agents would collide immediately |

**7.2 How the ribbon is laid out.**

| option | tradeoff |
| --- | --- |
| A. idml only | faithful to "idml is for layout"; needs the toolkit to implement `fit`/`fill`, `define` expansion, `Repeat`, a pixel unit and `pad`/`gap`, none of which exist (UI.md section 10). Weeks of toolkit work before a ribbon exists |
| B. idml skeleton plus an id flow solver for the strips (**recommended**) | ships now; idml owns chrome structure, bindings and classes; the flow solver is a few functions. Splits "layout" across two mechanisms |
| C. pure id | smallest and quickest; abandons the idml contract for the app and wastes the toolkit's main selling point |

**7.3 Are headers, footers and page numbers in v1?**

| option | tradeoff |
| --- | --- |
| A. v2 (**as the plan has it**) | v1 ships about a week sooner; letters and essays without page numbers are "plain documents" |
| B. v1 | many real documents want a page number; adds model fields, a layout reservation, master-page ODT work and an Insert-tab UI (about 3 packages) before the v1 gate |

**7.4 What happens to content we cannot edit (tables, images, fields)?**

| option | tradeoff |
| --- | --- |
| A. preserve verbatim as opaque blocks, show a grey placeholder, never lose it on save (**recommended**) | safe for real documents; the user can open anything and save without damage; placeholders are ugly until v2 |
| B. refuse to open documents containing them | simplest, honest, and makes the editor useless on most real files |
| C. drop with a warning | simplest model; silent damage on the next save |

**7.5 Directory restructuring of idstd for room (W0).** Moving `inflate` and `sha256`
under `pack/` and `sum/`, and `chr`/`fmt` under `atom/`, changes paths other
projects may reference (functions are program-wide names, so calls are unaffected;
`NAMES.md` file columns and any tool that reads paths are). Alternatives: (A) do
the moves (**recommended**); (B) put the new modules in `gfx/kit/` (the only free
slot) under a misleading name; (C) keep ZIP/XML/CRC inside `word/` and accept that
a second project needing them will move them later (against "duplicates go to
idstd", and the editor's zip reader already has a second user: the legacy tree).

**7.6 Vector icons in v1?** (A) the baseline of letters and rectangles first, vector
icons in phase 1 as a separate package that does not block the v1 gate
(**recommended**: A6 is in wave 2 and can slip); (B) require vector icons for the
gate; (C) rectangles and letters only for ever. The tradeoff is looks against one
extra package on the critical path (it touches the TrueType rasteriser's module).

**7.7 Retiring the legacy editor and its Python-based tests.** Moving `editor/` to
`obsolete/` and retiring `idc/tests/editor*.sh` is a move/deletion the user must
approve (the plan will not do it unasked). Options: (A) move to
`obsolete/editor-v0/` at cutover (**recommended**); (B) keep both indefinitely;
(C) delete. Also: whether the Python zlib/zipfile comparison may stay until A1
lands, or the zip suite should be ported to the id reader first.

**7.8 One document per window, and what New/Open do.** (A) one document per
process; New and Open replace it after the unsaved-changes prompt, and a second
window is a second process started by the user (**recommended**: simplest, and
makes the clipboard fragment's property ids valid); (B) tabs or multiple documents
in one process, which needs fragment property remapping through `tab_intern` of
resolved rows and a document switcher in the UI; (C) New/Open spawn a new process
with `proc_spawn` of the running binary (the binary's own path is not exposed to
`id`; `argv[0]` is a guess that fails when started through `PATH`).
