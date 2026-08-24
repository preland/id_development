# The document editor

> **Status: it reads and draws.** Everything below is checked by
> `tests/editor.sh` — 163 assertions across five suites, none of them against a
> golden blob.

```sh
bin/idc editor -o editor
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

The two together are why `docs/FRICTION.md` exists. A kernel finds what a
language cannot say about hardware; a document reader finds what it cannot say
about data. They found mostly the same things, which is what makes the list
worth acting on.

## What is in it

```
editor/
  lib/
    zip/    DEFLATE (RFC 1951) and the archive        49 + 25 functions
    doc/    an XML pull parser and the ODT model      91 + 47
    font/
      ttf/  the table directory, cmap, glyf, metrics  115
      ras/  flattening and scanline fill              ~60
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
Python's `zlib` and `zipfile` at test time, then fuzzed over 120 raw streams
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

`head`, `hhea`, `maxp`, `hmtx`, `cmap` formats 4 and 12, `loca`, `glyf`, and
composite glyphs with all three 2×2 transform forms. Outlines come out in font
units as contours of on- and off-curve points, with the implied on-curve
midpoints deliberately **not** inserted: doing so would renumber the points,
and `gvar`, hinting and point-matched composites are all indexed by the font's
own numbering.

Verified against a `struct`-only reference over every contour of every glyph of
all 143 TrueType fonts on the machine it was written on. Nine deliberate
mutations were each caught — and the first three sweeps missed four of them,
which is why there are now three sweeps and a third font: DejaVu and Liberation
between them contain *zero* composites with a 2×2 matrix, so that whole branch
was unexecuted until the suite went looking for a font that had one.

CFF (`OTTO`) fonts are refused by name rather than by a trap.

### The rasteriser

Contours flattened to edges — implied midpoints, contours that begin
off-curve, contours with no on-curve point at all — then a scanline fill by the
**nonzero winding rule**, which is not the same as even-odd for a glyph whose
contours overlap, and composites produce those routinely.

Supersampled 4 in y by 64 in x, deliberately unequal: another y sample is
another pass over every edge, another x column is one more cell of a prefix
sum. Each crossing is recorded as a ±1 *difference* at its column and a prefix
sum turns the differences back into a winding number — which removes the sort
that a span fill would need, because addition does not care what order the
crossings arrive in.

Two independent references check it: a second rasteriser (sorted-crossing span
fill) compared cell for cell, and the signed area the flattened polygon
encloses, which answers "is it the right *amount* of ink" from geometry with no
sampling grid in it. Seven mutations, all caught.

No hinting, no dropout control, no stem darkening. Below about 12 px the result
looks thin, which is what unhinted rasterisation looks like.

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
| `editor_zip.sh` | 11 | Python's `zlib` and `zipfile`, at run time |
| `editor_doc.sh` | 25 | the fixture's own `content.xml` |
| `editor_ttf.sh` | 40 | a `struct`-only font reader in the script |
| `editor_ras.sh` | 74 | a second rasteriser, and enclosed area |
| `editor_render.sh` | 13 | the shape of the page, not its pixels |

The render test is deliberately structural. A pixel-exact golden would break on
a different build of DejaVu, which is a fact about the font and not about this
program. What must not change is that the document has five paragraphs, that
one is empty and shows as a gap, that the 18 pt heading is taller than the
12 pt body, that nothing is drawn past the page width, and that rendering the
same document twice gives the same page.

## Not done

* **No editing.** It reads and draws; nothing writes an `.odt` back.
* **One font file at a time.** `tt_load` fills exported lists, so a second font
  replaces the first. Real bold and italic faces need a glyph cache keyed by
  face, which is the obvious next piece.
* **No tables, images, lists, footnotes or page breaks.** An unmodelled
  element's text lands in the surrounding run rather than being dropped.
* **No scrolling.** The window shows one page.
* **No CRC check on the archive**, so a corrupt entry comes back wrong rather
  than reported.
