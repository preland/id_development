# A GUI toolkit for `id`, laid out by idml

> **Status: design, plus a first slice that runs.** The slice is the idml parser
> and the layout pass, written in `id`, in `idstd/kit/ui/` (section 11), which
> is where the toolkit lives (decided; section 4). Everything else in this document
> is a proposal. The forks in section 12 are **not decided** except 1, 2 and 5; where
> the slice had to pick one to exist, it says which and why.

## 1. What this is for, and the contract it keeps

Native `id` programs want a window with buttons, text fields and lists, and the
user already has a layout language, idml, that describes such a screen in a few
lines. Today that path is split across four repositories and two languages: a
TypeScript parser turns `.idml` into a config, a Node script turns the config
into pixel rectangles, and the rectangles are pasted into `id` source
(`id_nativeapp/scripts/build-scene.mjs` writing `layout.gen.id`). This toolkit
replaces that path with `id` all the way down.

The contract is the one `idem/docs/IDML.md` section 1 already states, and this
toolkit adopts it unchanged:

> **idml is for layout and styling. `id` is for everything else.**

So the toolkit has two halves that never blur. idml says *where* and *how it
looks*. `id` owns state, logic, and every decision about what a click means. The
seam between them is the three forms idml already has (`idem/docs/IDML.md`
section 2): `@name` reads a value `id` publishes, a bare identifier such as
`addTodo` names the `id` function to run when an item is activated, and
`Repeat(@list)` with `@item.field` walks a list `id` publishes.

Non-goals for v1: styling that CSS does and idml does not (hover transitions;
shadows, borders, padding and gaps are now drawn from the design system's
classes, `idstd/kit/ui/theme/README.md`), animation, right-to-left or complex text, accessibility
trees, and any change to the idml language. Section 12 lists what would change
these.

## 2. Prior art, and what each piece leaves undone

| where | what it does | what is missing for a toolkit |
| --- | --- | --- |
| `idml/src/parser/idml-parser.ts` (2380 lines, TypeScript) | The reference grammar: tokenizer, recursive-descent parser, `define` expansion, `Table`/`Select` sugar, tiling and modularity validation, class-block guard, dark blocks. Produces a React `UIConfig`. | Needs Node. Validation rules (80-column lines, comments only in the header, children sum to 100, at most 3 children and 4 levels) live in the same file as the parse. |
| `idml/backends/id/` | An earlier `id` implementation: lex, then parse with layout **fused in** (no tree is kept), then paint to a PPM. Reads stdin. | No tree, so nothing to hit-test, focus or re-layout; bindings are parsed and dropped; hex colours are lowercase only; it has no test cases of its own (`verify.sh` is a shell script). Its README names the gap this toolkit fills: "Emit `layout.gen.id`" and "Data bindings". |
| `id_nativeapp/scripts/build-scene.mjs` and `regen.sh` | Parses `ui/todo.idml` with the TS parser, resolves percentages for a **fixed 640x460** window, finds nodes by `slot-*` class hooks, writes `layout.gen.id` (a flat `geo[]` and `pal[]`). | Build-time only: no resize, no second window size, the legend of indices is hand-kept, colours outside the six slots are fixed defaults, text positions use app constants (`+8`, `+10`). |
| `id_flappy`, `id_webdemo` | `id` compiled to wasm; idml renders the view in React; `@name` bound to exported `id` functions through `lib/id-runtime.ts` (only ints and strings cross). | Browser only. The bridge is JavaScript. |
| `idem/engine/game/load/ui/` | A third loader: its own parser, an immediate-mode walk that resolves and paints in one descent, leaf painters, text-field editing, mouse through `inp_*`. Centipercent integer tiling, `Col`/`Row`/`Stack`/`Layer`. | Immediate mode keeps no tree, so no focus order or hit-test without re-walking; its note that real idml's `#` comment rule broke its colours is the same trap the toolkit's scanner handles (`idem/docs/IDML.md` section 4). Names are `ui_*`, so it cannot coexist with a library that uses them. |
| `id_development/editor` | paragraph layout and wrapping, a caret, and an adapter over idstd's `ttf_` font (the TrueType parser and rasteriser moved to `idstd/kit/media/font/ttf`). | One font, no glyph cache, no widgets, no mouse. |
| `idstd` `kit/media/image/px`, `kit/media/font/bitmap`, `host/dev/win/gfx`, `host/dev/win/gl` | A list-of-ints surface (`sf_l_*`), rectangles (`d2_l_rect`), an 8x8 face (`txt_g8_*`), a PPM dump, a software window (`gfx_open`, `gfx_present`, `gfx_poll`, `gfx_mouse_*`) and an OpenGL window. | Low level: one global surface, no clip stack, no text measuring beyond `txt_g8_width`. |

The same tiler exists three times: in `build-scene.mjs` (JavaScript), in idml's
id backend, and in idem's loader (read, not measured with `dupscan`).
`docs/PROJECT.md` section 4 says a function written in two projects moves into a
shared library; that is the argument for building one toolkit rather than a
fourth loader.

## 3. Architecture

```
  .idml text
      |  gui_parse / gui_load      scannerless recursive descent, cursor in the tape head
      v
  tape (int[] records + string[])   the parsed document: variants, defines, routes, items
      |  (next)  gui_expand        define calls and Repeat rows become real nodes
      v
  tape, expanded
      |  gui_bind(board)           @ref dimensions and ?@ref gates get this frame's values
      v
  tape, bound
      |  gui_layout(w, h)          exact-fill tiling -> one x,y,w,h per node
      v
  rects (int[], 4 per record)
      |  (next)  widgets           measure, paint, hit-test, key events, state per node
      v
  paint list / framebuffer          sf_l_* surface, then gfx_present (or GL, or a canvas)
      ^
      |  (next)  events            gfx_poll + gfx_mouse_* -> hit test -> focus -> handler name
```

### 3.1 The tape

`id` has no structs and no allocation of records, and every function is at most
three actions, so a document is a **record-as-list** (the convention in
`idstd/README.md`): two lists. `int[] t` holds fixed-width records (26 ints
each: `(import idstd_gui_ns)`; the last six are the padding and gaps the design system's classes set), so a record is an index and a field is an offset.
`string[] s` holds every string, and a string is an index into it. **Zero means
"none" everywhere**: record 0 is the head, which nothing links to, and `s[0]` is
`""`, so a zeroed record is a valid empty one and no sentinel needs writing.

| record | what it is | notable fields (constants in idstd's root `conf.id`, `idstd_gui_f_*`) |
| --- | --- | --- |
| head (0) | the parse cursor, the first error, the root items, the variant and define chains, the route | `gui_h_pos`, `gui_h_err`, `gui_h_root`, `gui_h_var`, `gui_h_def`, `gui_h_route` |
| node | one idml item | kind (`gui_k_*`), name, parent, first/last child, next sibling, declared size `h`/`w` and **effective** size `eh`/`ew`, anchor, flags, class, visibility ref, variant, argument chain |
| arg | one argument of an item, a variant or a define | type (string, number, true, false, null, `@value`, handler, `~model`, `~@path`), text |
| prop | one `key: value` of a variant | key, value, as written |
| variant | `Name:Base` with class, props, default args | base kind, base name |
| define | `define Name(params) { body }` | params as args; the body's nodes are its children |

A parsed document is therefore a value a program can hold, pass, test and dump:
`gui_raw_all(t)` prints the records, and `gui_dump(t, s)` prints a readable
form (for example `Card()[82,100,top-left]`slot-card`{...}`) that the cases
compare against. Nothing is an opaque handle.

### 3.2 The parse

`gui_parse(src, t, s, dir, load)` reads idml text into the tape and returns 0 or
an error code (`gui_e_*`); `gui_load(path, t, s)` reads a file first and uses its
directory for imports. It is **scannerless**: each function looks at the next
significant character and dispatches (`gui_p_peek`, `gui_p_what`), because a
token list would need its own list and a scanner state, and idml's grammar is
decided by one character of lookahead everywhere except the top level (an
identifier followed by `:` is a variant), which `gui_p_what` settles with one
more look.

The cursor is a field of the head record. A failure (`gui_p_fail`) records the
**first** error, the text it happened in (an import is a different string), and
the place, then moves the cursor to the end, so every `while(more)` loop in the
parser stops without a single `if(failed)` check. `gui_diag(t, s)` turns that
into `line:column: message`, and every message says what to write instead
(idstd's root `conf.id`, `idstd_gui_e_msg`).

Two rules of real idml the scanner has to get right, both found in the prior art
above: a `#` starts a comment **only when it is the first non-blank character of
its line** (`fg: #f0e060` is a colour; idem's lexer stripped it, see
`idem/docs/IDML.md` section 4), and a dimension is a percentage with up to two
decimals (`21.88`), so sizes are **basis points** (hundredths of a percent, 100%
is `10000`), integers throughout.

Imports go through a function value, `gui_parse(..., func(string) return string
load)`, so the parser has no file API of its own: `fs_read_text` (idstd) reads files, a
test or a packed program passes something else. Paths resolve against the entry
file's directory, which is what `build-config.mjs` and `check-idml.mjs` do
(`resolve(dirname(entry), p)`), and a cycle stops at depth 8 with an error that
names the fix.

### 3.3 The layout pass

idml is not CSS flex. Its own validator (`idml-parser.ts`, `validateTiling`)
requires that a container's children **account for all of its space**: along the
main axis the children's percentages sum to 100 (or a `hug` child absorbs the
remainder), across it each child is exactly 100. The toolkit therefore needs no
flex solver: a container hands each child a slice of its own rectangle.

Rules, as implemented (`idstd/kit/ui/idml/layout/`, and pinned by cases):

1. `Row` tiles along the width, every other kind along the height.
2. A child's main size is `round_half_up(bp * extent / 10000)`, computed
   **per child, not cumulatively**. That is what `build-scene.mjs` does
   (`Math.round(pct/100 * rect.h)`, then `y += h`), so children can sum to one
   or two pixels more or less than their parent; the last child overflows rather
   than being trimmed. Matching the tool being replaced matters more than
   tidiness here.
3. `hug` children split the space the others leave, the remainder spread so the
   parts sum exactly.
4. The container's anchor places the run of children only when there is room
   left over and no `hug` child; it never shifts by a negative amount.
5. Across the axis a child is sized by its own percentage and placed by the
   container's anchor, so `[100,...]` fills and anything else is honoured.
6. `Overlay` children are out of flow: each is sized by its own percentages and
   placed by its **own** anchor inside the overlay.
7. A node gated off by a `?@ref` whose value is false takes no space.

`fx_align(start, room, size, a)` (idstd) is the one rounding rule for placing a box in
a span (centre rounds half up), used both for children and for text inside its
box; `(41, 57, 24, centre)` is `58`, the title's y in the todo app, which
`layout.gen.id` spells as a constant.

Allocation: `docs/SPEC.md` section 6 says memory is meant to be freed and today
the arena is freed only at exit, so a per-frame pass must not build strings or
lists. Layout builds no strings and no new lists (it empties and refills the
rectangle list it is given; whether that reuses the list's storage was not
measured); the parse allocates once per document, through `str_slice` for names
and text. Paint, when it lands, has to hold that line: no string is built per
frame.

Not in the slice: `fit` and `fill` (need intrinsic size, so need text measuring,
section 7), `scroll`/`overflow` (`pad` and `gap` are laid out when a design-system class sets them), `Repeat` content flow, `Table`
expansion, and `define` expansion. They are parsed; layout treats them as plain
tiles. Section 10 has the full table.

## 4. Where it lives

**Decided: `idstd/kit/ui/`.** The toolkit is the standard way to build a
graphical application in `id`, so it is part of the standard library, under the
library's own rules. The options that were weighed were its own tree imported
through `conf.id` (what the first slice was) and `idml/backends/id/`; the second
is still available as a place to mirror the parser and the conformance corpus,
but it is not the home.

What living in `idstd` means, each item enforced by `idstd/run.sh` or by the
compiler:

| rule | how the toolkit follows it |
| --- | --- |
| every parameter, local and internal function is `idstd_<name>` | parameters and locals are `idstd_gui_<name>`, because the bare `idstd_<name>` already means other things in the other modules (`idstd_t` is an `int`, a tape is an `int[]`); internal functions are `idstd_gui_<name>`; constants too (`idstd_gui_f_type`). A variable may not equal an internal function's name once prefixed, so `size` was `fsz` in the font seam; the font layer spells its names `idstd_gf_<name>` (NAMES.md 2.3) |
| every public function and export has a `NAMES.md` row | section 1.18 lists every function, 2.1 the variable families, 3 the test exports, 4 the constants |
| 3 entries per directory (since dropped), 3 functions per file | `gfx/` was full (`px`, `plane`, `space`), so `space` moved to `gfx/kit/space/` to make room beside `gfx/kit/gui/`; the tree under `gui/` is the slice's own layout, unchanged |
| the library's cases run in the library pre-check | they do: see "Cost" below |
| constants live in the root `conf.id` | the slice's `ui/conf.id` is idstd's root `conf.id`; `idstd/conf.id` is new |

The public surface is small on purpose: `gui_new`, `gui_parse`, `gui_load`,
`gui_diag`, `gui_dump`, `gui_bind`, `gui_layout`, `gui_rect_get`, `gui_find_cls`,
`gui_count`, `gui_is_node`, `gui_node_str`, and the three font
functions (section 7). The record layout (`gui_get`, `gui_put`, every
`gui_f_*`) is internal; an application reads a document through the readers, so a
field can be added without breaking one. `uicheck` (section 11) is written that
way and is the proof.

Two helpers the slice wrote are not layout, and went to the modules they belong
to: `fx_pct` and `fx_align` (basis-point share, and a box in a span) in
`core/math/fx/align.id`, and `fs_read_text` (a whole file as a string, the
loader `gui_parse` is handed) in `host/io/fs/data/text.id`. The tree's
path helpers (`gui_path_dir`, `gui_p_join`) are idml-specific import resolution
and stay.

**Cost.** The library's cases run once, in the pre-check, and are cached by the
library's content, so any edit to the library makes every program pay the cold
check once. What a program that never calls the toolkit pays is measured, not
written here: `idstd/run.sh` builds hello-world with and without the library and
prints the build time and binary size of each, and `IDC_TIMES=1` on any build
prints how many library functions it loaded. When this section was first
written an unused `conf.id` constant was emitted in every program, which made
the toolkit's constants a cost to everyone; the compiler now emits only the
constants the emitted code reads (docs/PROJECT.md §5), so that cost is gone.

## 5. How an application binds state and actions

The idml side is fixed (section 1). The `id` side has to supply: a **value
source** (`@remaining`, `@pipeLead!`, `?@isReady`), a **handler** for each bare
identifier (`addTodo`), a **model cell** for each `~name` (`~newtodo`, two-way),
and **list rows** for `Repeat(@list)` with `@item.field`.

**Decided (Fork 1): option C, binding tables are the core and function values
are a native-only convenience on top.** `func(T) return R` values
(`docs/SPEC.md` 1.1) can be passed and called but not stored in a list, not
returned, and do not exist on the wasm target (SPEC section 11, S8, S12), so a
seam built on them stops the toolkit's core from running on the web. The seam is
therefore a **board**: tables the application writes before a frame and the
toolkit reads, and a queue the toolkit fills and the application reads after it.
The function-value layer reads the application through callbacks, writes what
they answer into a board, and then does exactly what the table path does, so the
two paths cannot differ in what they bind; the parity cases (below) prove it.

### 5.1 The board

`GuiBd` is a struct (a reference: whatever takes a board changes the caller's
board), made by `gui_board()`. Under it are idstd's `hmap_` (a name table:
name to cell index), two parallel lists of cells (a number and a text per cell)
and the queue of fired handlers. **A name is one cell**, with a number half and a
text half; cell 0 is never written, so a name nobody wrote reads as `0` and `""`
and no reader needs a branch.

| kind | idml | the application writes | the toolkit reads |
| --- | --- | --- | --- |
| **value** | `@name`, `?@name`, a dimension `[@name,...]` | `gui_set_num(b, "name", v)`: basis points for a size, nonzero for a gate | `gui_num(b, "name")`; `gui_bind` does it for sizes and gates |
| **text** | `Text(@name)` | `gui_set_text(b, "name", s)` | `gui_text(b, "name")` |
| **row field** | `Repeat(@list)` with `@item.field` | `gui_set_num_at(b, col, row, v)`, `gui_set_text_at(b, col, row, s)`, and the row count as the value `list` | `gui_num_at`, `gui_text_at`, `gui_num(b, "list")` for the count |
| **model cell** | `Input(~name)`, `Checkbox(~name)` | `gui_set_text(b, "name", s)` for the starting text | writes back with `gui_edit(b, "name", s)`; the app reads `gui_text`, and `gui_num(b, "name")` counts the edits |
| **handler** | `Button("Add", addTodo)` | reads the queue after a frame | `gui_fire(b, "addTodo", arg)` queues it |

**Handlers.** The toolkit queues the bare identifier with an argument (the row
index for a handler inside a `Repeat`, else 0), in firing order. After a frame
the application reads `gui_fired(b)` entries with `gui_fired_name(b, i)` and
`gui_fired_arg(b, i)`, then calls `gui_fired_clear(b)`. A handler fires a frame
before the application sees it; that is the price of the toolkit never calling
out.

**Row addressing: a column key and a row index, not a synthesised key per cell.**
`@item.field` inside `Repeat(@list)` is the column `gui_col("list", "field")`
(that is `"list.field"`) at the row's index. The option the fork named,
`"todos.3.text"` built for every read, was rejected for one reason: **strings are
never freed** (`docs/MEMORY.md`), so a key built per row per field per frame
grows memory without bound. A column is a header cell, whose number half is the
rows it has room for, followed by one cell per row; the name table holds the
header. The toolkit builds the column key once, when it expands the `Repeat`
(the expansion pass is not built yet), and keeps it in the tape's strings; the
application passes a literal or a key it built once. A write past the end of a
column makes room (twice what was asked, at least 8, the old block abandoned), so
writing the same rows every frame allocates nothing. Consequences, stated: the
name `list` is both the list's count (a number) and, if the application also
wants it, a text; two `Repeat`s over the same list with the same field share a
column; and a row field is read by `(column, row)`, so no two-argument callback
type is needed on the table path.

**One name, one cell.** `@count` as a number, `@count` as text and `~count` as a
model are the same cell. That keeps the tables small and makes a model cell
usable as a value; an application that wants them apart uses two names.

**Layout reads through the seam.** `gui_bind(t, s, b)` writes the board's answers
into the tape's effective sizes and hidden flags (every dimension `[@name,...]`
and every `?@name` gate), and `gui_layout` reads only those, in basis points. A
name the board does not hold reads as 0, which is a zero-size, or hidden for a
gate; before this change a function answered it. Binding can run again after the
state changes and only the bound nodes move.

### 5.2 The function-value layer (native only)

Each takes callbacks as arguments, not registrations: nothing is stored, so there
is no initialisation order to get wrong.

| function | callback | what it does |
| --- | --- | --- |
| `gui_bind_fn(t, s, f)` | `func(string) return int` | the old `gui_bind`: `gui_pull_num` into a board of its own, then `gui_bind` |
| `gui_pull_num(t, s, b, f)` | `func(string) return int` | writes `f(name)` for every size and gate name on the tape |
| `gui_pull_text(t, s, b, f)` | `func(string) return string` | writes `f(name)` for every `@name` argument, except `item.` row fields |
| `gui_pull_rows_text(b, col, n, f)` | `func(string, int) return string` | writes `f(col, row)` for rows 0 to n-1 of the column |
| `gui_pull_rows_num(b, col, n, f)` | `func(string, int) return int` | the same for numbers |
| `gui_dispatch(b, f)` | `func(string, int) return void` | calls `f(name, arg)` for each fired handler in order, then clears the queue |
| `gui_push_model(t, s, b, f)` | `func(string, string) return void` | calls `f(name, text)` for every `~name` on the tape |

The row pulls take the column key rather than `list` and `field` so they build no
string. The `func(string) return int` of the slice's `gui_bind` is now
`gui_bind_fn`; `gui_parse`'s import loader is still a function value (section 12),
which is the one place the core still needs one.

### 5.3 What proves the two paths agree

The cases are in `idstd/kit/ui/idml/bind/` (the board in `bind/`, `fn/` the
layer, `real/par_*.id` the comparison). The flappy page is bound once through a board
and once with `gui_bind_fn` and laid out 288x512, and the two rectangle lists must
be equal; the pong page does the same at 640x480 with its one gate
(`?@waiting`); the todo page is filled with `gui_set_text` and with
`gui_pull_text` and the two boards must answer the same. Each comparison has a
case that binds the function path differently and wants the lists to differ, so
the comparison cannot pass by comparing two empty lists. Row fields,
`gui_pull_num` and handlers are checked the other way round: the table path and
the function path produce the same literal dump (the same expected string in a
case of each). `demos/about` is the application on the table path: a block count
and a `fresh` gate in values, the name box as the model cell `name`, the canvas
text as the text value `say`, and the button as the handler `draw`.

## 6. The widget set for v1

Mapped onto idml's builtin names (`gui_b_names`) and the kinds the parser
already assigns (`gui_k_*`):

| widget | idml | state the toolkit keeps per node (a parallel `int[]` indexed like `rc`) | events | paint |
| --- | --- | --- | --- | --- |
| **text** | `Text`, `Heading`, `Label`, `Link` | none | none (Link: activation) | string in `fg`, placed by anchor in its rect, clipped |
| **button** | `Button("label", handler)` | pressed, hovered | press inside, release inside = activate; Enter/Space when focused | `bg` rect, centred label |
| **text input** | `Input(~model, "placeholder")` | caret, (later) selection, scroll | printable keys, Backspace, Delete, Left/Right/Home/End, Enter = submit | `bg` rect, text, caret, placeholder when empty |
| **list / repeat** | `Repeat(@list) { row }` | row count, scroll | rows are children; events reach the row's own widgets | rows stacked at content height inside a scroll container |
| **checkbox** | `Checkbox(~model)` | none (the model is the state) | click or Space toggles | box and tick |
| **scroll container** | any `Row`/`Col` with `overflow: auto` | offset | wheel (`gfx_mouse_buttons` bits 3-4), drag | clip rect, thumb |
| **image** | `Image("name")` | none | none | nearest-neighbour blit of a named pixel list into the rect |

Focus order is tree order over buttons, inputs and checkboxes; Tab and
Shift-Tab move it, a click sets it. Hit testing walks the children back to
front (later siblings and overlays on top) and skips hidden nodes.

Each row of that table will be code under `idstd/kit/ui/` with its own cases; none of it
exists yet. What each needs from the platform is in section 8.

## 7. Text and fonts

idml sizes text in `vw` (`size: 1.45vw`): a fraction of the window width. The
fonts available, and what each costs:

| face | where | fit |
| --- | --- | --- |
| 8x8 bitmap, integer magnification | `idstd/kit/media/font/bitmap` (`txt_g8_draw`, `txt_g8_width`) | pure `id`, exact, trivially testable, ASCII only, steps of 8 px. `1.45vw` of 640 is 9.3 px: round to 1x or 2x. Not behind the seam any more |
| IBM VGA 8x16 (PSF) | `idem/engine/gfx/d2/text`, loader at `engine/game/load/asset/fmt/font/psf.id` | same properties, taller, a loader exists |
| TrueType, anti-aliased | `idstd/kit/media/font/ttf` (`ttf_open`, `ttf_glyph`, `ttf_advance`, `ttf_kern`, `ttf_render_at`, `ttf_px`) | real sizes, real widths, kerning (GPOS and kern), exact-area coverage for blending at whole or sub-pixel positions, any number of faces; no hinting, CFF outlines refused with a status. A face is a list; the font layer keeps the faces and a glyph cache. **The face behind the seam** |

**Decided (Fork 2): the editor's TrueType stack is the face**, and it is now behind the seam: the
layer in `idstd/kit/media/font/` (`NAMES.md` 1.21) opens a family by name against the machine's own
fonts, and draws anti-aliased glyphs with kerning, UTF-8 text and a glyph cache over `ttf_`.

**The font layer** (`gui_font_init()` once, then):

| function | meaning |
| --- | --- |
| `gui_font_open(family, px)` | a handle, or -1. `family` is a fontconfig-style name (`"sans-serif"`, `"monospace"`, `"DejaVu Sans"`), `px` the em height in pixels. An unknown family gets `sans-serif`, as fontconfig gives it |
| `gui_text_width(f, s)` | the width of `s` in pixels |
| `gui_text_draw(f, x, y_top, s, color)` | draw `s` with its top at `y_top`, blended over the list surface; the baseline is `y_top + gui_font_ascent(f)` |
| `gui_font_ascent(f)`, `gui_font_descent(f)`, `gui_font_line(f)` | the face's own vertical metrics in pixels at that size; descent is positive; `line` is the y step of the next line |
| `gui_text_x(f, s, i)` | the pixel offset of a caret placed before byte `i` (a code-point boundary) |
| `gui_text_hit(f, s, x)` | the code-point boundary whose caret is nearest pixel `x` (the earlier on a tie) |
| `sf_l_clip(x, y, w, h)`, `sf_l_unclip()` | clip every primitive on the list surface (`sf_l_pset`, `d2_l_rect`, `sf_l_blend`, `gui_text_draw`) to the rectangle, intersected with the clip already in force, until the matching unclip; the text box uses it so a long line stops at its border. They replace `gui_text_clip`/`gui_text_unclip`. `d2_l_arect(x, y, w, h, color, alpha)` blends a rectangle over what is there |

The pen is kept in 64ths of a pixel and every width, caret and metric rounds it the same way, so width,
caret, hit and draw agree exactly: glyph `i` is drawn where `gui_text_x` says its caret is, and
`gui_text_x(f, s, len(s))` is `gui_text_width`. Kerning between a glyph and the next is part of the
first glyph's advance, so a caret is placed after the kerning against the glyph that follows it.
Glyphs are cached per handle for each of four quarter-pixel positions, so a paragraph costs its
distinct glyphs once (2025 glyphs: 4 ms the first time and 2 ms after, against 59 ms to render them
afresh each time, on the machine this was measured on).

**How a family is found.** `gui_fonts_find` reads the fontconfig configuration the system uses
(`$FONTCONFIG_FILE` or `/etc/fonts/fonts.conf`, its includes, its `<dir>`s), scans the font directories
for TrueType files (`.otf` files with PostScript outlines are skipped, since `ttf_` cannot draw them),
reads each font's `name` table, and expands the name through the configuration's `<alias>` rules
(`prefer`, `accept`, `default`) the way fontconfig does; the first name of the expansion that is
installed wins, in its Regular or Book style. What it learns about each font file is cached per user
(`$XDG_CACHE_HOME/idstd/fonts-1.txt`) so a start-up reads only the files that changed. The model is
fontconfig's family expansion and nothing more: weights, slants, languages and fontconfig's other
properties are not modelled, and a family is chosen by name only, in its regular style.

**The old seam**, `gui_font_width(text, size)`, `gui_font_height(size)` and
`gui_font_draw(x, y, text, size, color)`, keeps its signatures and now means the default
sans-serif at a pixel size. `size` is an em height, so it no longer moves in steps of 8, and
`gui_font_height` is the face's line height.

The layer's cases pin arithmetic, not taste: a synthetic font small enough that every advance, kerning,
caret and bitmap placement is worked out by hand (a width of "AB" is 614 - 41 + 563 = 1136 sixty-fourths, 18
pixels), and `.tests/font` checks the real DejaVu Sans against numbers read from the font's own tables with
`od` and `awk`. Whether a rendering looks right is not something these can say; that is for a person
(`demos/about`, run headless and captured with `import -window root`).

Anchor-based text placement is already in the slice: `fx_align`.


## 7a. The text box model

`idstd/kit/ui/wid/textedit/` is the state and the operations of a single-line text
field, in pure `id` with no window and no font. A text box is a `GuiTb` struct
(a reference, so a function that takes one changes the caller's box): `text`
(UTF-8), `sel.caret` and `sel.anchor` (byte indexes; the selection is the bytes
between them), and an undo and a redo stack. Every byte index it stores or
returns is a code point boundary, for any text, valid UTF-8 or not.

**Events in.** The program feeds it what the window gives it:

| window event | call |
| --- | --- |
| KEY down (`ev[1]` key, `ev[2]` mods) | `int act = gui_tb_key(tb, key, mods)` |
| TEXT (`ev[1]` code point) | `gui_tb_text(tb, cp)` |
| MOUSE DOWN | `gui_tb_click(tb, gui_text_hit(f, tb.text, x + scroll), clicks, shift)` |
| MOUSE MOVE with the button held | `gui_tb_drag(tb, gui_text_hit(f, tb.text, x + scroll))` |

`gui_tb_key` handles the arrows, Home, End, Backspace and Delete (Ctrl: by word;
Shift: extend the selection) and Ctrl+A, Ctrl+C, Ctrl+X, Ctrl+V, Ctrl+Z,
Ctrl+Shift+Z and Ctrl+Y. A printable key does nothing there: its character comes
as TEXT. A key with Alt or Super held does nothing.

**The clipboard protocol.** `gui_tb_key` returns an action code, and that is the
whole protocol; the model never touches the clipboard.

| code | meaning | the program does |
| --- | --- | --- |
| 0 | not an editing key (Enter, Tab, Escape, Up, Down, a letter without Ctrl, Alt or Super held) | uses the key itself |
| 1 | handled: the box changed or the caret moved | redraws |
| 2 | copy (only when something is selected) | `gfx_clip_set(gui_tb_selected(tb))` |
| 3 | cut (only when something is selected) | `gfx_clip_set(gui_tb_cut(tb))` (which also removes the text) |
| 4 | paste | `gui_tb_paste(tb, gfx_clip_get())` |

Copy or cut with nothing selected answers 1, so the clipboard is never
overwritten with an empty string. A paste is cleaned to one line (`gui_tb_clean`:
tab, CR and LF become one space, other control bytes go) and cut to the length
limit. `gui_tb_rev(tb)` counts every change to the text, undo and redo included,
for a program that wants to fire an on-change.

**Selection by mouse.** `gui_tb_click(tb, byte, clicks, shift)`: one click puts
the caret there (with Shift it keeps the anchor and extends), two select the
word, three select everything. `gui_tb_drag` keeps the anchor fixed and moves
the caret; after a double click it extends by whole words, after a triple click
the selection stays everything. The pixel to byte step is the font seam's
`gui_text_hit`.

**The word rule.** Every code point has a class: space (ASCII space, tab, LF, CR,
the no-break space U+00A0, U+2000 to U+200A, U+3000), word (ASCII letters, digits
and `_`, and every code point above ASCII not listed below) or other (the rest
of ASCII, the C1 controls, the Latin-1 and general punctuation, `×` `÷`, arrows,
mathematical operators, symbols, CJK punctuation and pictographs; the table is
`idstd_gui_tb_cp_*` in `conf.id`). A run of one class is a word. Ctrl+Right goes
to the start of the next word: over the rest of the run the caret is in, then
over the spaces after it. Ctrl+Left goes back over spaces, then to the start of
the run before them. Ctrl+Backspace and Ctrl+Delete remove that same span.
Double click selects the run under the click (the run before it when the click
is at a word's right edge). There is no dictionary, so a run of Han or kana is
one word.

**Undo.** A step is the state before an edit, with its caret and selection, and
undo puts all of it back. Typing joins the open step while it continues a word:
"hello world" is the steps "hello " and "world"; a new step starts at the first
character of a word after a space or punctuation, when something is selected,
and after any caret move, click, undo or paste. A paste, a cut and each delete
are a step each. A no-op (Backspace at the start) is not a step and does not end
the open one. A new edit empties the redo stack. `gui_tb_set` forgets history.

**Scrolling.** `gui_tb_scroll(scroll, cx, tw, w)` takes the current scroll in
pixels, the caret's pixel x from the start of the text (`gui_text_x`), the text's
pixel width and the visible width, and returns the scroll that keeps the caret
inside `[0, w - 1]` without leaving a gap after the end. Draw the text at
`x - scroll`.

**Length limit.** `gui_tb_new(text, max)` and `gui_tb_limit(tb, n)`: `max` counts
code points, never bytes; 0 means no limit. Typing and paste are cut to fit, and
what does not fit is dropped.

The cases include a script player (`idstd_gui_tbt_play`) that replays a string of
events against a box, so a scenario such as "type a word, undo, redo" is one
line of a case.

## 7b. The text box widget

`idstd/kit/ui/wid/textbox/` (`NAMES.md` 1.19b) puts a window and a font on the model of 7a: a `GuiTextBox` is a
`GuiTb` with a rectangle, a font handle, a scroll, focus, a drag in progress and a caret clock. It draws on the
list surface and takes the events `gfx_event` gives, and it holds no clipboard or window state of its own: the
program passes each event in, calls `gui_textbox_tick` once a frame and `gui_textbox_draw` when the picture is stale.

| call | meaning |
| --- | --- |
| `gui_textbox_new(text, hint, font, max)` | a box with `font` (a `gui_font_open` handle), the placeholder `hint` shown while it is empty, and at most `max` code points (0 for no limit) |
| `gui_textbox_place(box, x, y, w, h)` | the rectangle the layout gave it (an idml node's `gui_rect_get`, found by class with `gui_find_cls`); call it after every layout |
| `gui_textbox_event(box, kind, ev)` | one `gfx_event`; answers bits: 1 redraw, 2 Enter was pressed in the focused box, 4 Escape was pressed in it and it let go of the keyboard |
| `gui_textbox_tick(box)` | once a frame: scrolls on while a drag rests past an edge, and answers 1 when the caret has blinked since the last `gui_textbox_draw` |
| `gui_textbox_draw(box)` | background, border (a 2 pixel focus ring when it has the keyboard), selection (blue with the keyboard, grey without), text clipped to the box and scrolled, or the placeholder when empty, and the caret |
| `gui_textbox_hover(box, x, y)` | sets the pointer's shape: the I-beam while `(x, y)` is inside the box, else the arrow; answers 1 inside |
| `gui_textbox_text(box)`, `gui_textbox_set(box, s)` | read and replace the text (`set` forgets undo history) |
| `gui_textbox_focus(box, on)`, `gui_textbox_focused(box)`, `gui_textbox_inside(box, x, y)`, `gui_textbox_cell(box, k)` | focus, hit test, and a cell of the box's small state back (0 x, 1 y, 2 width, 3 height, 4 scroll) |
| `gui_textbox_clock(box, ms)` | freezes the caret clock at `ms` (-1 reads `ticks()` again); cases use it |

**What the events do.** A left press inside the box takes the keyboard and puts the caret at the byte nearest the
pointer (`gui_text_hit` through the scroll): one click a caret, two the word, three everything, Shift keeps the
anchor (`gfx_mods`). A left press outside gives the keyboard up, so a click on a button unfocuses the box and
the button still sees it. Moving with the button held selects, reading the byte at the nearest point inside the
box so a pointer past either edge selects to the end of what shows, and `gui_textbox_tick` scrolls the text on
a step a frame, faster the further out the pointer is. Keys go to `gui_tb_key` and TEXT to `gui_tb_text`, only
while the box has the keyboard; the clipboard codes of 7a are carried out with `gfx_clip_set` (copy, cut) and
`gfx_clip_get` (paste, fetched only when a paste is asked for). The caret is solid for 530 ms after every
edit, caret move, click or drag step and then blinks at 530 ms, and only while the box has the keyboard.

**A program using it** (see `demos/about`): make the font layer (`gui_font_init`), the box and its placement
at start-up; per frame, `gfx_sync` and a layout when the size changed (then `gui_textbox_place` again), then each
`gfx_event` into `gui_textbox_event` first (a program's own handling of Esc or a letter key must check
`gui_textbox_focused` before the event, since the box takes the keys it uses), then `gui_textbox_tick` and
`gui_textbox_hover`, and `gui_textbox_draw` when anything answered with the redraw bit.

**Not done.** One line only (no wrapping, no Enter-for-newline), no input-method preedit display, no font
fallback (a code point the system sans face lacks draws as that face's missing-glyph box: CJK text
shows as boxes under DejaVu Sans), no right-to-left or combining-mark shaping, no mouse wheel or touch, no
drag-and-drop of selected text, and no clipboard INCR for text over one X request (a limit of `gfx_clip_set`).

## 8. Backends

| target | window and present | notes |
| --- | --- | --- |
| **native framebuffer** (first) | `host/dev/win/gfx`: `gfx_open`, `gfx_present(int[])`, `gfx_sync`, `gfx_show`, `gfx_event(int[])`, `gfx_mods`, `gfx_cursor`, `gfx_clip_set` and `gfx_clip_get`, `gfx_width/height` | `gfx_event` gives one event a call (key, text, mouse down with a click count, up, move, resize, quit, wheel); a mouse event carries no modifiers, so `gfx_mods()` is how a program learns whether Shift was down. The legacy `gfx_poll` and the polled mouse state still work. A resize is an event, and `gfx_sync` fits the surface to the window's real size before a frame is laid out. `gfx_cursor(1)` makes the pointer a text I-beam over the window and `gfx_cursor(0)` the arrow. See `idstd/host/dev/win/gfx/README.md` and `gfx.h`. |
| **GL** | `host/dev/win/gl`: `glwin_*`, `gl_draw_tris`, `gl_read_pixels` | the toolkit's paint list can become triangles (rects) without touching layout; text needs a glyph atlas or stays in the software surface uploaded as one quad. No textured-quad primitive exists yet. |
| **web** | today: idml's React renderer with `id` as wasm (`id_webdemo`, `id_flappy`) | the parser and layout are pure `id` and compile to wasm **if they use no function values and no natives**: `gui_parse` takes a loader function value, and wasm has none (S8, S12). `gui_bind` reads a board of tables (section 5), which is what makes the rest of the core runnable there; `gui_bind_fn` and the other function-value adapters are native only. |

The toolkit's painting talks to one interface: fill a rectangle, draw text, draw
an image, push and pop a clip rectangle. The software surface implements it with
`sf_l_*` (which needs a clip stack; `sf_l_pset` only clips to the surface today).
**Fork 3**: whether painting is immediate (widgets call the surface) or builds a
retained draw list the backend replays; the list is what lets GL and a canvas
share widgets, and costs one more list and one more function per primitive.

## 9. Testing without a display

The render is pure `id` into a list of pixels, so a test needs no window:
`sf_l_init(w, h)`, paint, read `sf_l_px`. The cases in this repository show the
shape that works under the compiler's rules, where a case's setup and checks
take no arguments:

* A **setup** builds the scene and exports it (`idstd_gui_t_todo` loads the real
  `todo.idml` from `idstd/.tests/assets/gui/`, because a case runs in its library's root).
* The **function under test** takes the coordinates as arguments, so one line is
  one pixel: `given scene (45, 60):(16777215)`.
* A **golden frame** is a dump the human approves, committed beside the case as
  a hash; `ppm_l_dump` writes the image to look at. Colours and proportions are
  not judged by the tooling.
* Every layout case is arithmetic done by hand in the case's header, then run.
  The layout and parse cases were falsified by mutation (break the code, see red,
  restore).
* `idc/tools/casework.sh mutate` is the tool for that last step.

Nothing here needs a 60-second budget: the todo layout is a few dozen rectangles.
A full-frame paint of a 640x460 surface is 294 400 pixel writes per frame, which
is the number to watch against the time limit when paint lands.

## 10. How much of idml v1 supports

Legend: **yes** is parsed and acted on; **parsed** is read into the tape and
ignored by layout; **no** fails with a message that names the fix.

| idml feature | parse | layout | notes |
| --- | --- | --- | --- |
| `#` comment lines, blank lines | yes | n/a | comments accepted anywhere; idml allows only the header block (Fork 4) |
| 80-column limit, sum-to-100 tiling, at most 3 children / depth 4 | no check | n/a | validation, not meaning; a separate `check` pass (next), so the parser accepts what idml would reject |
| `import "path"`, `import A, B from "path"` | yes | n/a | through the loader function value; names are read and not checked |
| `Name:Base`, class, `{ props }`, default args | yes | n/a | the variant's base kind decides the node kind |
| `define Name(params) { body }` | yes, kept as written | no | call sites are not expanded yet (next) |
| `dark { ... }` | skipped | n/a | no dark theme natively |
| route `./path`, `[scroll]` | yes | n/a | one page per file; a second route is an error |
| `Name(args)[h,w,anchor]{ children }` | yes | yes | all nine anchors and the single-word forms |
| arguments: string, number, `true`/`false`/`null`, `@v`, `~m`, `~@p`, handler, `{ }` block | yes | n/a | |
| `@ref` as a dimension, with or without `!` | yes | yes (via `gui_bind`) | `@ref ? A : B` is an error naming the fix |
| `?@ref`, `?!@ref` | yes | yes (via `gui_bind`) | hidden nodes take no space |
| conditional class `` `cls`?@ref `` | read, dropped | n/a | |
| `hug` | yes | yes | |
| `fit`, `fit-w`, `fit-h`, `fill`, `fill-w`, `fill-h` | yes | as plain tiles | need text measure |
| `Overlay` children anchored | yes | yes | `Modal` parsed as an overlay kind, not yet given a backdrop |
| `Repeat`, `Table`, `Select`, `Children` slot | yes | no | expansion is a separate pass (next) |
| `pad`, `gap`, `overflow`, `size` (vw), `radius`, `weight` props | stored as strings | no | read by the widget and paint passes; `radius`, `bg` and `fg` are also read by `gui_theme`, and padding and gap come from design-system classes (`p-2`, `gap-1`) |
| colours `#rgb`, `#rrggbb`, both cases | yes (text kept) | n/a | conversion to a pixel value is paint's |
| 2-decimal percentages | yes | yes | three or more decimals round half up at the third |

`id_webdemo/ui/todo.idml` fails to parse, at line 117, on `hug-w`: that spelling
is older than idml's current keywords (`fit-w`, see `idml-parser.ts` lines
917-929), so the TypeScript parser rejects it too (read from source; not run).
The idem games `fps` and `flappy` fail because they are written in idem's
invented declarations, which `idem/docs/IDML.md` section 1.2 says are not idml.

## 11. The first slice, and how to check it

The slice is part of `idstd`, in `idstd/kit/ui/` (a library: no `main`).
Commands run from the repository root with `IDSTD_HOME` set to the standard
library, which is a sibling checkout:

```sh
export IDSTD_HOME=$PWD/../idstd
timeout 60 idc/bin/idc ../idstd -o /tmp/idstd.o      # runs every case, the toolkit's included; exit 0 is green
idc/bin/idc ../idstd --check                         # the rules only
cd ../idstd && ./run.sh                              # NAMES.md, the idstd_ prefix, the suites
```

Any program that builds against `idstd` runs the toolkit's cases first, once,
in the library pre-check (`idc: the standard library at ... failed its own test
cases` names a failure, and is cached by the library's content). The cases read
their idml files from `idstd/.tests/assets/gui/`, because a case runs in its
library's root.

What is in it, under `idstd/kit/ui/` unless a path says otherwise:

| where | what | public names |
| --- | --- | --- |
| `idstd/conf.id` | every constant: record layout, kinds, error codes and messages, keyword tables | none: `idstd_gui_*` |
| `core/doc/tape/` | the record tape, its builders, and the readers an application uses | `gui_new`, `gui_count`, `gui_is_node`, `gui_node_str` |
| `core/doc/read/` | scanners, cursor, tokens, syntax, imports, diagnostics | `gui_parse`, `gui_load`, `gui_diag` |
| `core/doc/show/` | `idstd_gui_raw_all`, `gui_dump` and the test fixtures | `gui_dump` |
| `core/flow/` | binding and layout | `gui_bind`, `gui_layout`, `gui_rect_get`, `gui_find_cls`, the board (`gui_board`, `gui_num`, `gui_text`, `gui_set_num`, `gui_set_text`, `gui_edit`, the row and fire calls) and its function-value adapters (`gui_bind_fn`, `gui_pull_*`, `gui_dispatch`, `gui_push_model`) |
| `core/real/` | real documents as cases | |
| `font/` | the font seam and the font layer behind it (section 7) | `gui_font_open`, `gui_text_width`, `gui_text_draw`, `gui_text_x`, `gui_text_hit`, `gui_font_ascent`, `gui_font_descent`, `gui_font_line`, `gui_font_init`, `gui_fonts_find`, `gui_utf_cp`, `gui_utf_n`, `gui_utf_str`, and the old `gui_font_width`, `gui_font_height`, `gui_font_draw` |
| `idstd/.tests/assets/gui/` | `todo.idml`, `flappy/` (three files), `pong/`: byte-for-byte copies, plus small fixtures | |

`fx_pct` and `fx_align` are in `core/math/fx/align.id` and `fs_read_text` in
`host/io/fs/data/text.id`, where the next program that wants them finds them.

How many functions and cases there are is a query, not a number to write down:
`idc/tools/casework.sh list ../idstd/kit/ui` lists every function short of
its two cases, and the build runs every case.

`uicheck/` (at the repository root, beside `idc/` and `docs/`) is a small
program, not part of `idstd`: `main` in `uicheck/run/main.id`. It uses `idstd`
the way any application does, through the implicit standard library and the public
names above and nothing else, and is the command-line face of the toolkit:

```sh
timeout 60 idc/bin/idc uicheck -o /tmp/uicheck
/tmp/uicheck ../idstd/.tests/assets/gui/todo.idml --rects 640 460   # x y w h name class, one line per item
/tmp/uicheck FILE.idml --dump                                       # the parsed document as text
/tmp/uicheck FILE.idml                                              # "ok N records", or line:col: message, exit 1
```

Its cases need no file of `idstd`'s: it carries its own `uicheck/test_assets/tiny.idml`
and its own fixtures (`uicheck/show/fix/`), because a program that is built against
a library must not depend on that library's test fixtures.

### 11.1 Parity with `build-scene.mjs` on `todo.idml`

The expected values in `idstd/kit/ui/idml/real/` are **typed from
`id_nativeapp/id/todo/view/layout.gen.id`**, the committed output of
`build-scene.mjs`, not copied from this toolkit's output. For a 640x460 window:

| what | `layout.gen.id` | this toolkit | |
| --- | --- | --- | --- |
| card rect | `90 41 461 377` | `90 41 461 377` | same |
| input box | `90 117 341 45` | `90 117 341 45` | same |
| add button | `449 117 101 45` | `449 117 101 45` | same |
| badge | `431 41 120 57` | `431 41 120 57` | same |
| list area | `90 181 461 238` | `90 181 461 238` | same |
| title text origin | `90, 58` | `fx_align` on the title rect, anchor `center-left`, 216x24 text: `90, 58` | same |
| add label origin | `476, 132` | anchor `center`, 48x16: `476, 132` | same |
| badge text, y | `62` | anchor `center`, 16x16: `62` | same |
| input text, y | `132` | anchor `center-left`, 16x16: `132` | same |
| **badge text, x** | `439` (`badge.x + 8`) | `483` | **differs** |
| **input text, x** | `100` (`input.x + 10`) | `90` | **differs** |
| row height, pad (`46`, `8`) | constants | not in idml | app constants |
| muted, green, divider colours | fixed defaults in the script | not in idml | app constants |

Every difference has one cause: the script places those two texts at a fixed
offset from the left edge of their box (`build-scene.mjs` lines 113 and 116) and
ignores the anchor idml gives them (`center` for `BadgeNum`, `center-left` for
`Field`). The idml document has no way to say "8 px in"; a `pad` property, read
by the paint pass, is where that belongs (section 10). Until then a native app
that wants the old look passes the offsets itself. Also not compared: the colours
that idml does give (`bg: #eef1f6`, ...) are in the tape as strings, and turning
them into pixel values is paint's job, not the slice's.

Rounding: both tools round each child's size independently, half up. Integer
arithmetic equals `Math.round` except where the float product lands just under
a tie; none of the numbers in this file do, and whether any document does is not
checked beyond `todo.idml` and the flappy page (whose comments give 112 px for
21.88% of 512, which the toolkit reproduces).

### 11.2 The other real documents

`uicheck` over every `.idml` file found in the sibling repositories (run on this
machine; only the files copied into `idstd/.tests/assets/gui/` are cases):
`id_nativeapp/ui/todo.idml`, the three `id_flappy/ui/` files, `idem`'s pong,
`sandbox`'s chat, `plover_learning`'s trainer and three of idml's own examples
all parse (`err=0`). `id_webdemo/ui/todo.idml` and idem's `fps` and `flappy`
documents do not, for the reasons in section 10. Cases cover todo, flappy and
pong, all copied byte for byte (checked with `diff`); the others are a
measurement, not a guarantee.

## 12. Design forks

Each is a real choice with a cost on both sides. None of them is made here
except where the slice had to be something in order to exist; that is marked.

**Fork 1 - how the application feeds and commands the toolkit** (section 5) -- **decided: C, binding tables as the core and function values as a native-only convenience** (user decision). The board and its function-value layer are in section 5; `gui_parse`'s import loader is still a function value, and the one place the core needs one.

**Fork 2 - fonts** (section 7) -- **decided: the editor's TrueType stack**, behind the font seam. Options were 8x8 bitmap only, the VGA 8x16 PSF, or
the TrueType stack. It decides whether `fit`/`hug`/wrap can be exact, and
how `vw` sizes map to pixels.

**Fork 3 - immediate or retained painting** (section 8). Decides how much of the
widget code GL and a web canvas can share.

**Fork 4 - what the parser rejects.** idml's own parser enforces style rules
(80 columns, header-only comments, children sum to 100, at most 3 children and
4 levels). Options: the parser enforces them (a document that idml rejects never
loads natively), a separate `gui_check` pass enforces them (the slice), or
nothing enforces them natively and the TypeScript validator remains the only
gate. The middle option keeps a native app able to load a file the web build
refuses, which is either a feature or a drift.

**Fork 5 - where it lives** (section 4) -- **decided: `idstd/kit/ui/`**. The options were `idstd/gui`, its own tree, or idml's id
backend. The slice started in its own tree and has moved.

**Fork 6 - define expansion: at parse or at layout.** Expanding a `define` call
when parsing duplicates the body into the tape (simple, tape grows with use,
per-call parameters substituted once). Expanding at layout keeps the tape small
and makes every consumer handle calls. Expansion also has to decide what
`Children()` means for a call with no body.

**Fork 7 - one document or many.** The slice keeps a document as two lists the
caller owns, so any number can coexist; a window with several panes, or a menu
that is its own document, is then free. The cost is that every function takes
`(t, s)`.

## 13. What this makes removable

| tool | where | replaced by | status |
| --- | --- | --- | --- |
| `scripts/build-scene.mjs` | `id_nativeapp` | `gui_load` + `gui_layout` at start-up and on resize | The rectangles it produced for `todo.idml` are reproduced by the slice (section 11). The per-app geometry it also wrote (`titleX`, text origins) becomes `gui_align`; the `+8`/`+10` paddings become a `pad` property once paint reads it. |
| `scripts/regen.sh` | `id_nativeapp` | nothing: there is no generated file to regenerate | removable with `build-scene.mjs` |
| `layout.gen.id` | `id_nativeapp/id/todo/view/` | the parse at start-up | removable; it is generated and committed |
| `scripts/check-idml.mjs` | `id_webdemo` | `gui_load` then `gui_diag` (a parse error with line, column and a fix); the tiling and modularity checks need Fork 4's `gui_check` | parse half replaceable now |
| `scripts/build-config.mjs` | `id_webdemo`, `id_flappy` | an `id` program emitting idml's `UIConfig` JSON from the tape | **not replaceable yet**: the React renderer consumes that JSON, and nothing here writes it |
| `scripts/build-font.mjs` | `id_nativeapp` | an `id` program | untouched; it writes idstd's 8x8 face from public-domain data, out of scope |
| `scripts/build-id.sh`, `build-sprites.sh` | `id_webdemo`, `id_flappy` | build wrappers around `idc` and the sprite program | untouched |
| `idml/backends/id/verify.sh` | `idml` | `idc ui` (the cases) | removable once that backend is retired in favour of this tree |

No Python or shell tool inside `id_development` became unnecessary: the tools
above live in sibling repositories, which this change does not touch.
