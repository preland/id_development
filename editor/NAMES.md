# Names in `editor/`

The whole of `editor/` is **one compilation unit**, so the one-type-per-name
rule covers all of it: a name declared `int i` in the inflater is `int i` in
the rasteriser too. Three people writing three modules will collide on that
within an hour unless the vocabulary is agreed first, which is what this file
is. `idstd` is a *different* unit and constrains nothing here.

## The shared vocabulary

Reuse these rather than inventing a synonym. A synonym costs nothing to write
and one compile error to everybody else.

| name | type | means |
| --- | --- | --- |
| `i` `j` `n` `r` `at` `lo` `hi` `v` `b` `c` `x` `y` `w` `h` `k` `m` `px` | `int` | counters, indices, byte values, coordinates; `px` is a size in pixels per em |
| `g` | `int` | a glyph id -- the font module's central noun, so it gets a row of its own rather than being spelled differently in every file that touches one |
| `ok` `sign` `count` `total` | `int` | flags and tallies |
| `a` `p` `addr` `end` | `word` | addresses in the flat store |
| `s` `t` `name` `out` `path` `key` `val` `msg` | `string` | text; `msg` is a diagnostic |
| `raw` | `int` | a flag saying text is not to be decoded (CDATA) |
| `xs` `buf` `src` `dst` `tab` `row` | `int[]` | byte buffers and integer tables |
| `rows` `grid` | `int[][]` | tables of tables |
| `names` `parts` `strs` | `string[]` | text tables |

**Bytes live in `int[]`, one byte per cell.** Not in a `string`: a ZIP and a
TrueType file both contain NUL, and `docs/SPEC.md` §4 says a string cannot. Not
in the flat store either, except where a module says otherwise -- a list is
bounds-checked, and this is code reading attacker-shaped input.

## The prefix each module owns

Every function a module defines starts with its prefix. Functions are
program-wide in `id`, so this is the only namespace there is.

| prefix | module | what |
| --- | --- | --- |
| `inf_` | `lib/zip/` | DEFLATE decompression |
| `zip_` | `lib/zip/` | the archive: central directory, entry extraction |
| `xml_` | `lib/doc/` | the XML pull parser |
| `odt_` | `lib/doc/` | paragraphs, spans, styles |
| `tt_` | `lib/font/` | TrueType parsing |
| `ras_` | `lib/font/` | glyph rasterisation |
| `ed_` | `app/` | layout, drawing, the program |

## Reading bytes

Every module reads big- or little-endian integers out of an `int[]`. Those
helpers are shared rather than written per module, and they live in
`lib/zip/byte/` because the inflater needed them first:

```
rd_le16(int[] xs, int at) -> int    little endian, as ZIP and DEFLATE write
rd_le32(int[] xs, int at) -> word
rd_be16(int[] xs, int at) -> int    big endian, as TrueType writes
rd_be32(int[] xs, int at) -> word
rd_i16(int[] xs, int at)  -> int    big endian, signed: a TrueType coordinate
```

A single byte is `xs[at]`. There is no `rd_u8`, because writing one is a
compile error: `idstd`'s `lget` is already that function, and two functions
with one body may not coexist. The rule is right and the lesson is the
vocabulary -- a name for indexing is a name for nothing.

The 32-bit readers return a `word`. A full 32-bit field does not fit an
`int`, and a size with the high bit set coming back negative is
indistinguishable from a small file. They also use `a` for the intermediate,
because `r` is an `int` everywhere else in this unit and one name may not be
two types.

A read past the end of `xs` is a trap, and deliberately so: this is code that
reads files it did not write, and the alternative to a clean abort is a wrong
answer about a document.
