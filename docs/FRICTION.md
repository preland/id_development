# Where `id` costs more than it should

> **Status: evidence, not opinion.** Every entry below is a thing that happened
> while writing two large programs in `id` — a kernel with a graphical shell,
> and a document editor that reads OpenDocument files. Each names the code that
> hit it. Nothing here is speculative, and nothing here is a complaint about a
> rule doing its job.

`docs/SPEC.md` says what a program means. `docs/GAPS.md` says what the compiler
cannot do yet. This document says what the *language* makes expensive, and it
exists because the only honest way to find that out was to write something big
enough to hurt.

The two programs were chosen because they need different things. A kernel needs
raw memory, fixed layouts, device registers and a command loop. A document
reader needs bit-level parsing, Huffman codes, a tree, and glyph outlines.
Between them they touch nearly everything the language has, and the friction
they found is mostly the *same* friction, which is what makes it worth writing
down.

---

## 1. There is no record, so there are magic indices

`id` has no struct. Structured data is parallel exported lists indexed by an
integer, which is the idiom the compiler itself uses (`compiler/parse/front/tree/`)
and which works well when the lists are named after what they hold.

It works much less well for a handful of values that belong together *inside*
one algorithm. The canonical Huffman decoder keeps five: a code, the first code
of the current length, an index into the symbol table, the length, and the
symbol. In C those are five locals. Here they are one `int[]` and five numbers:

```
lset(xs, 2, xs[2] + n);
lset(xs, 1, (xs[1] + n) * 2);
lset(xs, 0, xs[0] * 2);
```

which is `index += count; first = (first + count) << 1; code <<= 1`. The
inflater's author called it the least readable code in the module and they were
right.

The same shape appears in the kernel, where a framebuffer is a base address, a
width and a height:

```
fb_note(word a, word w, word h) {
  wset((import fb_st), 0, a);
  wset((import fb_st), 1, w);
  wset((import fb_st), 2, h);
} return void;
```

Here it is survivable, because three accessors give the three cells names. In
the decoder it is not, because the five change on every symbol and no accessor
can be cheap enough.

**What would fix it:** a record type, or — much smaller — a way to give a name
to a cell of a list at the point of declaration.

## 2. There is no `break`, so a search cannot stop

Every search in both programs wears the same shape: a two-cell cursor holding
"where I am" and "what I found", and a loop condition that tests both.

```
int[] buf = [len(xs) - 22, -1];
while(buf[0] >= 0 && buf[1] < 0) {
  zip_scan(xs, buf);
}
```

`zip_scan` keeps being called after it has found what it was looking for. It
just cannot say so. The same pattern is in `zip_find`, in the Huffman decoder,
and in the kernel's `pci_scan`, which walks all thirty-two PCI slots after
finding the display adapter in slot one:

```
pci_scan(word d, word a) {
  while(d < 32) {
    a = pci_at(d, a);
    d = d + 1;
  }
} return word a;
```

The cost is not the wasted iterations. It is that "found" has to be encoded in
the loop variable, so every search is two pieces of state and a compound
condition instead of one and a `break`.

## 3. A function cannot fail

There are no exceptions, no early return, and a function that promises an
`int[]` must produce one. So a parser that meets a malformed file has nowhere
to put the news. The inflater ends up here:

```
inf_fail(string s) {
  int[] xs = [];
  print("id: " + s);
  pop(xs);
} return void;
```

The `pop` of an empty list is deliberate: it is a trap, and a trap is the only
way to stop. The diagnostic goes to **stdout**, because `id` has no stderr, so
the error about a corrupt archive is written into the same stream as the bytes
extracted from it.

`idstd`'s `err_*` module is the sanctioned alternative, and it needs every
caller to have run `err_init` and to gate every later stage on `err_count()` —
which a function whose whole job is to return a buffer cannot do without
returning two things, which it also cannot do.

**What would fix it:** the smallest useful thing is a `print` that writes to
stderr. The real thing is a way to return a failure.

## 4. Three actions per block is one action too few for a four-way choice

The limit is 3, and `if / else if / else if / else` is four. So every
four-way decision is two functions, and the split falls in the middle of the
thing being decided:

```
inf_kind(...)   BTYPE 00 and 01
inf_comp(...)   BTYPE 10 and the error
```

There are five of these in the inflater alone (`inf_fix_lit`/`inf_fix_tail`,
`zip_init`/`zip_init2`, `inf_tabs`/`inf_tabs2`, `inf_kind`/`inf_comp`,
`inf_dec_next`), and the kernel's exception-name table would have been eleven
files if it had been written as branches instead of as a string that gets
split.

The limit is doing its job everywhere else. This is the one shape where the
number is wrong rather than the code.

## 5. Three entries per directory produces depth that stops meaning anything

Forty-nine functions of DEFLATE is seventeen files, and seventeen files under a
three-entry rule is nine levels:

```
editor/lib/zip/inf/blk/dyn/len/sp/mt/match.id
```

`sp/` is "split" and `mt/` is "match" because at that depth a directory exists
only to hold two more files. `docs/HACKING.md` says to name a directory after
the stage of work it holds; that advice runs out somewhere around `len/`.

The kernel hit the same wall from the other side. `kernel/prog/sys/gfx/` needed
device access, a framebuffer, a font and a console — four things — so one of
them had to become a child of another, and `con/` living inside `fb/` says
something about the code that is not true.

## 6. The uniqueness rule is right, and there is nowhere to put the answer

Copying a stored ZIP entry and cutting a run of code lengths in half are the
same three lines:

```
int[] buf = [];
int i = 0;
while(i < n) { push(buf, xs[at + i]); i = i + 1; }
```

The compiler rejected the second one, correctly — they are one function. But
the one function now lives in `arc/dir/ent/fld/find.id` and is called from
`inf_split`, six directories away, because an `id` tree has no place that means
"shared". The rule pushes code toward being factored and the directory rule
pushes it toward being scattered, and they meet in the middle.

The kernel has the same thing at a smaller scale: `lset` and `wset` are one
function at two types, allowed to coexist only because their signatures differ,
and there is no way to write it once.

## 7. Binary data has no literal, and a string cannot hold a NUL

The kernel needs a bitmap font and a keyboard map. Both are byte tables and
both are mostly zeros. `id` has no byte-array literal, and `docs/SPEC.md` §4
says a string cannot contain a NUL — so a font cannot be a string.

Both travel as hexadecimal text and are decoded at boot:

```
font_rom0() {
} return string "00000000000000000000000000000000...";
```

That is 6 000 characters of hex for 95 glyphs, and it is split across four
functions because the lexer builds a string literal by concatenation and that
is quadratic (§9). The decode is another twenty lines. In C it is one array.

## 8. An array literal cannot say what type it is

`[]` is typed from its context, so `word[] xs = []` works. `[0, 0, 0]` takes
its type from its first element, so `word[] xs = [0, 0, 0]` is rejected:

```
error: cannot initialize word[] 'fb_st' with a int[] value
```

There is no way to write a `word[]` literal at all. Every one in the kernel
starts empty and is filled by pushing, which turns a declaration into two
functions.

The same rule bites harder one level up: a list of lists cannot be built in a
return clause, because `return int[][] [tab, row];` parses the `[` as another
dimension of the type:

```
error: unexpected token ','
error: cannot initialize int[][] 'rows' with a int[][][] value
```

So returning a pair of lists costs three functions where one would do.

## 9. String building is quadratic, and it changes designs

`docs/TODO.md` item 10 records the measurement. What the two programs record is
the *consequence*: neither of them accumulates text.

The XML parser keeps offsets into its input and slices once. The ZIP reader's
byte dump goes through `alloc`/`poke8`/`str_of_mem` rather than `+`, because
200 KB of concatenation is about 20 GB of retained memory. The kernel's shell
keeps a line as an `int[]` of character codes and turns it into a `string` once,
at Enter.

Every one of those is the right design anyway. The problem is that it is not a
choice: the obvious code is unusably slow, and nothing says so until it is.

## 10. Evaluation order is unspecified, and a bit reader cannot live with that

`docs/SPEC.md` §10 S11 records that the two targets disagree about the order
the operands of one operator are evaluated in. For most code that is a
curiosity. For a bit reader it is the format:

```
lset(xs, 0, inf_bits(5) + 257);
lset(xs, 1, inf_bits(5) + 1);
lset(xs, 2, inf_bits(4) + 4);
```

Those three had to be three statements, because every `inf_bits` call advances
the stream and the order *is* the meaning. `inf_match` had to pull a length out
into a local before decoding the distance for the same reason. The natural
one-liner would decode correctly for a while and then produce garbage.

This is the rule the inflater's author reported being most afraid of, and it is
the one this repository should fix rather than document.

## 11. A name has one type across a whole program, and that is a coordination cost

Within one module the rule is a help. Across a kernel written by several hands
it is a constant tax: `c`, `r`, `v`, `i`, `d`, `x`, `p` all collided between
subsystems that never call each other. The framebuffer wanted `word c` for a
colour; the console wanted `int c` for a character; the font wanted `int r` for
a row and the demo already had `string r`.

Every collision is a compile error in a file the author has not opened.

The answer is a written vocabulary agreed before anyone starts — `editor/NAMES.md`
is one, and `idstd` has had `NAMES.md` for the same reason. That works. It is
worth saying plainly that it is *required* at this scale, rather than a nicety.

## 12. Two diagnostics that cost more than they should

**`return void` with an expression misparses.** `} return void f(x);` is not
valid — a void return clause takes no expression — but instead of saying so the
parser leaves the call in the token stream and reports it as a broken top-level
declaration:

```
error: undefined variable ')'
error: undefined variable 'word'
error: no such function 'con_copy'
error: undefined variable '{'
```

Four errors, none of them the mistake, in a file the mistake is not in. This
one cost time twice in one afternoon.

**A `word` may be assigned to an `int` but not used as an index.** These are
both legal:

```
int n = a;          // a is a word -- narrows, correctly
take(a);            // take(int n) -- narrows, correctly
```

and this is not:

```
print(xs[a]);       // error: array index must be int, got word
```

Both compilers agree, so it is the language's rule rather than a bug — but it
is inconsistent with assignment and with argument passing, and the workaround
is a local that exists only to change the type. One reader of a ZIP file
avoided it by reading the same four bytes twice as two 16-bit reads, which caps
that reader at 2 GB.

## 13. There is no way to empty a list, and the workaround changes its identity

`id` has no `clear`. `lset` cannot shrink a list, `pop` removes one cell, and an
exported list cannot be reassigned from outside the function that declared it.
The only way to empty one is to run its declaration again:

```
tt_clear() {
  export int[] ttends = [];
  export int[] ttpx = [];
  tt_clear2();
} return void;
```

That works -- `docs/SPEC.md` §8 says an export is initialised when its declaring
function runs -- but it does not empty the list. It makes a *new* list and
rebinds the name. So a consumer that held `(import ttpx)` across a call is
holding the previous glyph, silently, and the only thing saying so is a comment.

For a font whose outline lists are refilled once per glyph, that is the most
dangerous thing in the module, and it is dangerous because of an omission
rather than a rule.

## 14. Three exports per function, so a record of seven becomes a list and a comment

A font has seven metrics that belong together: units per em, glyph count,
ascender, descender, line gap, the number of horizontal metrics, and the
`loca` format. What that wants to be is seven exported `int`s. The action limit
allows three declarations per function, so it is one list and five accessors:

```
tt_upem() {
} return int (import ttmet)[0];
```

`tt_upem` exists because there is no way to give the index `0` a name. This is
§1 again, from the other end: not a record inside an algorithm, but a record
that *is* the module's interface.

## 15. A narrowing reader is nearly unwritable

`rd_be32` returns a `word`, correctly -- a full 32-bit field does not fit an
`int`. But a table offset is an `int`, and `word` is contagious: one `word` in
an offset expression widens all of it. So the font module has its own:

```
tt_u32(int[] xs, int at) {
} return int rd_be16(xs, at) * 65536 + rd_be16(xs, at + 2);
```

which is `rd_be32` with a different return type. It is legal only because
`rd_be32` uses a local and this does not. **Had the two bodies matched, the
duplicate-logic rule would have made a narrowing reader impossible to write** --
and the choice would have been between widening every offset in the module to
`word` or spelling the read out at every call site.

The same rule makes `rd_i8` impossible for a different reason: reading one byte
is `xs[at]`, which is already `idstd`'s `lget`, so the signed one-byte reader
can only be the sign half, called as `tt_i8(xs[at])`. Two signed readers with
different shapes for no reason a reader of the code can see.

## 16. A library has no way to name a constant

`conf.id` constants are read at a project root, so a *program* can name its
magic numbers. A module inside one cannot: the whole vocabulary of a binary
format -- `MORE_COMPONENTS` is 32, F2Dot14 1.0 is 16384, the x-or-y sign bit is
a shifted 8 -- stays as bare numbers with the name in a comment beside it.

```
if(k & 32 > 0) {
```

`editor/`'s own root could declare them, at the cost of reserving a
program-wide name for every flag in every format the editor reads. That is the
choice the language offers: a constant is global or it does not exist.

## 17. `charat` is O(n) on a long string, so text processing is quadratic

This is the largest measured cost in either program, by a very long way.

`id_charat` in the C runtime memoises the length of **one** string. A parser
alternating between the document it is scanning and the strings it is building
misses that memo on every call, and each miss is a `strlen` of the whole
document. Scanning is therefore O(n²) in the length of the input, with a
constant nobody would guess at from reading the code.

Measured on an OpenDocument `content.xml`:

| input | with `charat` | reading the flat store |
| ---: | ---: | ---: |
| 3.5 MB | **46.8 s** | **0.061 s** |
| 14 MB | 1.76 s (parse only, before the rest of the fix) | linear |

Scaling with `charat` was 4× per doubling. The fix was to stop using it on the
input at all: copy the document into the flat store once with `mem_of_str`, and
read it with `peek8`.

```
xml_ch(int i) {
  int c = 0 - 1;
  if(i >= 0 && i < xml_len()) {
    c = peek8(xml_base() + i);
  }
} return int c;
```

`len(s)` had to go the same way -- it is an un-memoised `strlen`, and it was
being evaluated three times per attribute as an end-of-input sentinel, so the
length is cached too. **After both, the parse is exactly linear**: 4000, 8000
and 16000 paragraphs take 0.060, 0.119 and 0.246 seconds.

`idstd`'s `str_findat` is unusable on a document for the same reason -- it calls
`str_eqat` at every position, and `str_eqat` alternates `charat` between the
haystack and the needle, which is the worst case of the memo on every
comparison.

**This is a runtime property, not a language rule**, and it is the one entry
here that makes correct, obvious code unusably slow rather than merely awkward.
The workaround is documented practice (`demos/idview`, `compiler/lex` and now
the XML parser all keep offsets and read the store), but it is a workaround: a
`string` that knew its own length would remove the whole class. Changing that
means changing the representation `docs/SPEC.md` §4 describes, which is why it
is written down here rather than done.

## 18. A dispatcher that returns a value can only ever be two-way

§4 said three actions is one too few for a four-way choice. The XML parser
found the sharper version: a function that *returns* something needs a local to
assign into, and that local is the first action -- so `if / else if / else` is
already 4 and a value-returning dispatcher is limited to **two** ways.

```
xml_mark(int i)  { int k = 0; if(xml_ch(i + 1) == 47) { k = xml_close(i + 2); } else { k = xml_mark2(i); } } return int k;
xml_mark2(int i) { int k = 0; if(xml_ch(i + 1) == 33) { k = xml_bang(i + 2);  } else { k = xml_mark3(i); } } return int k;
xml_mark3(int i) { int k = 0; if(xml_ch(i + 1) == 63) { k = xml_skip(i);      } else { k = xml_tag(i + 1); } } return int k;
```

Three functions to decide between four kinds of `<`. A `void` dispatcher gets
three ways, because it needs no local -- so the same decision costs a different
number of files depending on whether it produces a value.

The five predefined XML entities cannot be a chain of comparisons at all: five
branches is five actions, so they are a table and a search, rebuilt per call.

## 19. The uniqueness rule reaches across modules

The ODT layer needed a per-row comparison in a style-name lookup. It is
character for character the XML layer's `xml_pick2`, so it could not be
written -- and `odt_key` now calls `xml_pick2` directly, which is an ODT
function reaching into the parser's internals for a three-line helper.

The same rule merged decimal and hexadecimal character references into one
loop, since two loops differing only in `10` versus `16` are the same logic.
That one is the rule being right. The first is the rule being right and the
answer being in the wrong place, which is §6 again at module scale.

## 20. A two-dimensional program has no two-dimensional value

A point is two numbers that always move together, and there is no way to say
so. In the rasteriser every one is two adjacent cells of an `int[]`, and
setting the pen *and* the contour's home is four assignments -- which is one
more than a block holds, so it is two functions:

```
ras_from(int[] buf, int x, int y) {
  lset(buf, 2, x);
  lset(buf, 3, y);
  ras_home(buf, x, y);
} return void;

ras_home(int[] buf, int x, int y) {
  lset(buf, 7, x);
  lset(buf, 8, y);
} return void;
```

`ras_home` exists because 4 is more than 3. Six functions in that module carry
a point as two `int`s, and a quadratic pen carries eleven numbers at once:

```
ras_step(int[] buf, int x, int y, int j, int n) {
  ras_line(buf, ras_bez(buf[9], buf[4], x, j, n), ras_bez(buf[10], buf[5], y, j, n));
} return int j + 1;
```

`buf[9]`/`buf[10]` is where the curve started and `buf[4]`/`buf[5]` is the
control point. Nothing in the line says so. This is §1, and geometry is where
it hurts most.

## 21. Division truncates toward zero, and there is no floor

`docs/SPEC.md` §2.2 says so, and it is the right rule. What is missing is the
other one. `idstd` has `fx_abs`, `fx_min`, `fx_max`, `fx_clamp` and `fx_sign`,
and nothing that floors — so every program doing coordinate arithmetic writes
this:

```
ras_flr(int v) {
  int n = v / 64;
  if(v < 0 && n * 64 != v) {
    n = n - 1;
  }
} return int n;
```

A rasteriser is exactly where that bites, because it is the program where half
the coordinates are negative on purpose: everything above a glyph's baseline
is. Deleting those three lines costs 52 of the rasteriser's 74 assertions.
Nothing in the language or the library warns you, and the failure is a glyph
one pixel out rather than an error.

## 22. §4 and §18 both understate the limit

Neither said the number that matters is *branches plus shared setup*. The
contour-start decision is three-way and returns nothing, so §18 says it should
fit in one function. It does not, because the three branches share a line:

```
ras_open(int[] buf, int lo, int hi) {
  lst_fill(buf, 11, 0);
  if((import ttpon)[lo] == 1) { ... } else { ras_open2(buf, lo, hi); }
} return void;
```

The `lst_fill` is the first action, so the budget for branches is two, and a
three-way choice costs two functions.

---

## What this list is not

None of the rules above is wrong. The action limit, the uniqueness rule, the
one-type-per-name rule and the entry-count rule each caught real mistakes in
both programs — a duplicate function, a name meaning two things, a block doing
too much. The friction is the point of them.

What the list separates is the rules that cost something *and* bought
something, from the four that cost something and bought nothing:

* **§3**, a function cannot report failure. There is no upside to a parser
  writing "corrupt archive" onto the same stream as the data.
* **§8**, an array literal cannot say what type it is. This is an omission, not
  a discipline.
* **§10**, unspecified evaluation order. `docs/SPEC.md` should choose.
* **§12**, both diagnostics. A misparse should say what was misparsed.
* **§13**, there is no way to empty a list. The workaround rebinds the name and
  silently invalidates every reference to it, which is the only entry here that
  can produce a wrong answer rather than an awkward one.
* **§15**, a narrowing reader survives the uniqueness rule by accident. That is
  luck, not design.
* **§17**, `charat` is linear. This is the only entry that makes correct,
  obvious code 767 times slower than it needs to be, and the only one whose
  workaround every text-processing program in the language has had to
  rediscover.
* **§21**, there is no floor. One function in `idstd` closes it, and until it
  is there every program that touches a negative coordinate writes it again or
  is quietly wrong.

Those eight are the list worth acting on. Two of them -- §21 and a stderr for
§3 -- are a few lines each and would close the two entries that produce *wrong
answers* rather than awkward code.

## What cost nothing

Worth recording, because a list of friction reads as a list of complaints
otherwise. Across roughly nine thousand lines of `id` written for these two
programs:

* The **nesting-depth-2 rule** never once got in the way.
* The **action limit** found real faults early and, after the fact, left zero
  over-budget blocks to clean up — the shape it forces is a shape the code
  keeps.
* The **one-type-per-name rule** cost the rasteriser exactly one new name.
  Every other local came out of the vocabulary already written down, which is
  the whole argument for writing one down (§11).
* The **uniqueness rule** caught genuine duplicates in both programs — a copy
  loop written twice, two character-reference decoders differing only in their
  base — and in each case the merged function was the better code. The rest are the cost of rules that
also caught real mistakes -- a duplicate function, a name meaning two things, a
block doing too much -- in both programs, more than once.
