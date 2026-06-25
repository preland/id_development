# idc-in-id: status and blockers

The goal is to reimplement `idc.py` (lexer → parser → semantic checks → C
emission) in the `id` language itself. This directory contains **stage 1, the
lexer**, which works: it reads id source on stdin and prints a normalized token
stream, and it can tokenize its own source.

Getting even the lexer to run required adding language features that did not
exist before (see "Features added" below). The **parser and C emitter are not
built**, because they need capabilities the language still lacks. This file
records exactly what is missing, so the gaps can be closed deliberately.

## Features added to make the lexer possible

These were missing entirely and were added to `idc.py` for this demo:

- **`while` loops** — there was no iteration at all. A lexer must scan a string
  of unknown length. (Recursion technically works, but the 3-action limit makes
  a recursive scanner unwritable.)
- **`len(s)`** — string length.
- **`charat(s, i)`** — the byte code at index `i` (or `-1` past the end). The
  language could not look inside a string before this.
- **`chr(n)`** — a one-character string from a byte code, for rebuilding lexemes
  and output.
- **`read_all()`** — slurp all of stdin into one string. `input()` reads a
  single line and returns `""` on EOF, which is indistinguishable from a blank
  line — useless for reading multi-line source. `read_all()` sidesteps that.

## Hard blockers for the parser and code emitter

These are missing capabilities, not just inconveniences. Each one independently
prevents writing the next stage.

1. **No aggregate/record types.** An AST node is `BinOp(op, left, right)`,
   `IfStmt(cond, then, else)`, etc. The language has only flat primitives and
   arrays *of* primitives — there is no way to declare a node type with named
   fields, so the AST itself is unrepresentable.

2. **No growable arrays and no array-element assignment.** Arrays exist only as
   literals (`[1, 2, 3]`); `a[i] = x` is not a statement form (assignment is
   only `name = expr`). A parser needs a growable token buffer and child lists;
   neither can be built.

3. **No keyed maps.** Semantic analysis needs symbol tables: variable→owner,
   name→export, name→function signature. There is no dictionary type and no way
   to build one (no mutable storage to back it).

4. **Single return value, no multiple returns / out-params.** Recursive-descent
   parsing routines naturally return *two* things: the node parsed and the next
   cursor position. A function returns exactly one value of one type. The lexer
   dodged this by returning only the index and `print`ing tokens as a side
   effect — that trick does not generalize to building a tree.

5. **No mutable shared state across calls.** `export`/`import` is read-only for
   everyone but the owner, so helpers cannot advance a shared cursor or append
   to a shared output buffer. Combined with (4), there is no clean way to thread
   parser state through the call graph.

6. **No `string` → `int` conversion.** `str_of_int` (int→string) exists, but
   there is no inverse. The lexer prints `int 42` as text; a parser needs the
   numeric value. A `to_int(s)` builtin would be needed.

## Intentional constraints (not blockers -- the lexer complies with them)

These are deliberate design choices, and the lexer is written to honor them:

- **3 actions per block** + **maximum nesting depth of 2.** Every block (the
  function body and each branch/loop body) gets its own 3-action budget, and
  blocks may nest only two deep. This is why dispatch is a *chain* of one-
  decision functions (`scan_one -> scan_word -> scan_token -> ...`) instead of a
  pyramid of nested `if`/`else`. It forces small, shallow, named functions.
- **3 functions per file.** The 20-function lexer spans 7 files. Expected; the
  language grows programs by adding files.

## Variable naming (resolved)

The old program-wide unique-name rule forced hand-mangling (`src_a`, `src_b`,
...). It has been replaced by **type-consistency**: a name may recur across
functions as long as it always has the same type, so the dispatch chain now
just uses `src`/`i`/`ni` everywhere. Exported names stay reserved globally. The
intent (a name never means two different things) is preserved; the incidental
restriction (no two functions may share `i`) is gone.

## Other notes

- **No character literals or `char` type.** Character work is done with magic
  byte codes (`34` = `"`, `47` = `/`, `10` = newline). Workable, error-prone.

## Smallest unblock that would make the parser feasible

In rough priority: **(a)** record/struct types (or growable arrays + element
assignment) to represent the AST and token buffer; **(b)** a keyed map (or the
primitives to build one) for symbol tables; **(c)** multiple return values or
mutable out-params to thread the parse cursor; **(d)** `to_int`. Relaxing the
unique-global-name rule and the 3-action limit would turn the result from
"mechanically mangled" into something actually readable.
