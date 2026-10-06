# The document editor

> **Status: it reads and draws.** Everything below is checked by
> `idc/tests/editor.sh` (its suites and their assertion counts are what that
> script prints), none of them against a golden blob.

```sh
idc/bin/idc editor -o editor
./editor DOC.odt FONT.ttf                  # a window
./editor DOC.odt FONT.ttf --ppm page.ppm   # an image, which is how it is tested
```

An `.odt` is a ZIP holding XML. Opening one means inflating a DEFLATE stream,
parsing the XML, resolving the styles it names, reading a TrueType font,
turning glyph outlines into anti-aliased coverage, breaking lines against a
page width, and putting the result on a surface. All of that is `id`.

## Why this one

`docs/KERNEL.md` proves the language reaches the machine. This proves it
reaches a *format* — several formats, none of them designed for it, all of
them full of the things a language is bad at: bit-packed Huffman codes, a
central directory read backwards from the end of a file, big-endian tables of
signed 16-bit deltas, quadratic Béziers, and a winding rule.

The two together are why `docs/FRICTION.md` (retired; `git show 479234a^:docs/FRICTION.md`) exists. A kernel finds what a
language cannot say about hardware; a document reader finds what it cannot say
about data. They found mostly the same things, which is what makes the list
worth acting on.

## What is in it

```
editor/
  lib/
    zip/    DEFLATE (RFC 1951) and the archive
    doc/    an XML pull parser and the ODT model
    font/   the editor's one font, as an adapter over idstd's `ttf_`
  app/
    doc/    reading the file, writing the image
    view/   layout, drawing, the window
```

The three library modules were written independently and build as one
compilation unit with no name collisions, which is what `editor/NAMES.md` is
for: `id` gives a name one type across a whole program, so a shared vocabulary
is a coordination problem before it is a language one.

### The archive

Stored, fixed-Huffman and dynamic-Huffman blocks, the code-length alphabet
with its repeat codes, and LZ77 back-references copied forwards because the
ranges overlap — that is how a run of one byte is expressed. Checked against
node's `zlib` and Info-ZIP `unzip` at test time, then fuzzed over 120 raw streams
and 94 archive entries. **No CRC-32 check**, no Zip64, and no compression
method but 0 and 8; each is reported rather than guessed at.

### The document

A pull parser — events, not a tree, which is what a language with three
actions per block can express without a tree of allocations. It reports
malformed input with a byte offset, including an end tag naming the wrong
element and an element still open at end of file. On top of it: paragraphs,
runs, and the automatic styles that give each run its font, size, weight and
slant. An empty `<text:p/>` survives as an empty paragraph, because a blank
line in a document is content.

Namespace prefixes are **not** resolved — `text:p` is the name as written.
Only `pt` sizes are read, and only the literal words `bold` and `italic`.

### The font

The font is idstd's (`kit/media/font/ttf`, NAMES.md 1.20), not the editor's:
it was this directory's `lib/font` and was moved out and rewritten so that the
standard GUI toolkit can use it too. `editor/lib/font` is now an adapter of a few
functions that keeps the editor's one face in two exports and answers the
questions the layout and the drawing have always asked -- `tt_load`, `tt_glyph`,
`tt_advance`, `tt_upem`, `tt_line`, and `ras_scale` with `ras_w`, `ras_h`, `ras_bx`,
`ras_by` and `ras_cov` for the bitmap of the glyph last scaled.

What changed for the editor: an `OTTO` (CFF) font is still refused, but a damaged
font is now a printed reason and a 0 from `tt_load` rather than a trap; coverage
is the exact area of the outline in each pixel instead of a 4 by 64 sample; a
composite placed by matching points is placed rather than put at the origin. The
editor does not yet use kerning (`ttf_kern`), so its text is laid out as before.

Everything about how the font is checked -- the hand-assembled fonts the cases
run on, the awk reader of the font tables the real-font expectations came from,
the truncation and damage sweeps -- is in idstd's `.tests/font` and NAMES.md.
`editor_ttf.sh` and `editor_ras.sh`, which checked the old code against a Python
reader and a second rasteriser, are gone with it.

### Layout and drawing

Line breaking against a page width, baselines from the font's own ascender,
descender and line gap, and a pen kept in **64ths of a pixel** — rounding each
advance to a whole pixel accumulates several characters of drift over a line.

One face. A document naming a bold or italic face and a program given one font
file gets **faux bold** (the glyph drawn twice, a pixel apart) and **faux
italic** (sheared a fifth of its height), which is what a renderer does when
the face it wants is not the face it has. It is an honest approximation rather
than the wrong weight silently.

Breaking happens *at* the glyph that overflows rather than at the last space,
so a long word is split rather than moved. Doing it properly means making
already-placed glyphs mutable after the fact.

## What is tested, and how

| suite | checks | reference |
| --- | ---: | --- |
| `editor_zip.sh` | 11 | node's `zlib` and `unzip`, at run time |
| `editor_doc.sh` | 25 | the fixture's own `content.xml` |
| `editor_render.sh` | 13 | the shape of the page, not its pixels |

The font is tested where it lives: idstd's inline cases on two hand-assembled
fonts and `.tests/font` on the real ones (NAMES.md 1.20).

The render test is deliberately structural. A pixel-exact golden would break on
a different build of DejaVu, which is a fact about the font and not about this
program. What must not change is that the document has five paragraphs, that
one is empty and shows as a gap, that the 18 pt heading is taller than the
12 pt body, that nothing is drawn past the page width, and that rendering the
same document twice gives the same page.

## Editing

The window is editable. A printable key inserts at the caret, Backspace removes
the character before it, Delete the one under it, and the arrows move it;
Escape or the close button quits. `q` used to quit and no longer does — it is a
letter now.

The caret is **one number: the index of the code point it sits before**, counted
over the document's runs in reading order. That works because layout emits
exactly one glyph per code point, so glyph number *k* is code point number *k*
and the caret's pixel position is a lookup rather than a second walk. A code
point rather than a byte, so the caret cannot land inside a two-byte letter and
delete half of it.

Editing changes the model (`odt_txts`), never the pixels: a keystroke marks the
page stale and the next frame lays it out and draws it again. That is the same
path a resize takes, which is why a resize and a keystroke cannot disagree
about what is on screen.

What editing does *not* yet do:

* **Nothing writes an `.odt` back.** The ZIP layer decompresses and does not
  compress; writing one means emitting stored (uncompressed) entries.
* **Enter does not split a paragraph.** A paragraph break is a change to the
  run table's shape, not to a run's text, which is the next piece of work.
* **No selection, and no undo.**
* **An empty paragraph cannot hold the caret**, because it owns no run for the
  caret to be an offset into.

## Not done
* **One font file at a time.** The reader holds any number of faces, but the
  adapter keeps one, so `tt_load` replaces the last. Real bold and italic faces
  need an adapter that keeps one face per style and a glyph cache keyed by face,
  which is the obvious next piece.
* **No tables, images, lists, footnotes or page breaks.** An unmodelled
  element's text lands in the surrounding run rather than being dropped.
* **No scrolling.** The window shows one page.
* **No CRC check on the archive**, so a corrupt entry comes back wrong rather
  than reported.
