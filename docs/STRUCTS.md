# Records in `id`

> **Status: implemented (v1).** The language is specified in `docs/SPEC.md`
> section 1.2. What was built is the decision list under "Decisions needed"
> with the recommendations taken: reference semantics (Q1 B), no `drop` (Q2),
> three fields (Q3), field names count in structural uniqueness (Q4), fields in
> their own namespace (Q5), `Point(1, 2)` as an initialiser only (Q6), struct
> literals in cases (Q7), struct-typed exports but no struct constants (Q8),
> lists of structs but no `==` or `print` (Q9), one declaration per program
> (Q10, read as "a struct is declared once for the whole program", not "one
> struct per program"), no layout and no `peek` (Q11). The sections above the
> decisions are the proposal as first written, and its recommendation (value
> semantics, `init` returning the struct) is **superseded**; they are kept for
> the reasoning, not as the design. It is written down first because a record is
> the largest thing `id` has ever added, it interacts with every rule the
> language already has, and three of those interactions had no obvious answer.

`docs/FRICTION.md` (retired; `git show 479234a^:docs/FRICTION.md`) asks for this four times, from four directions:

* **§1**, a Huffman decoder keeps five values that belong together and has to
  spell them `xs[0]` through `xs[4]`.
* **§14**, a font's seven metrics are the module's interface and become one
  list plus five accessor functions whose whole job is to name an index.
* **§20**, a point is two numbers that always move together and there is no way
  to say so; in the rasteriser every one is two adjacent cells and a comment.
* **§16**, a flag is a number with its name in a comment beside it.

The first three are the same request. This document is the answer to them.

## The shape

A struct is declared in **its own file**, and that file may contain the struct
and nothing but its `init` and its teardown. Every other function that works on
the struct is an ordinary `id` function, in an ordinary file, beside every
other function.

```
// editor/lib/geom/point.id

struct Point {
  int x;
  int y;
}

init(Point p, int x, int y) {
  p.x = x;
  p.y = y;
} return void;

drop(Point p) {
} return void;
```

and then, anywhere else:

```
// editor/lib/font/ras/pen.id

ras_from(Point pen, int x, int y) {
  pen.x = x;
  pen.y = y;
} return void;
```

This is the shape the language already has for everything else: a thing is
declared in one place, and the code that acts on it is spread by *what the code
does* rather than by what it acts on. A method list would be the first place in
`id` where a function's home was decided by its first argument, and
`docs/FRICTION.md` (retired; `git show 479234a^:docs/FRICTION.md`) §6 is already the record of how much that decision costs
when the language gets it wrong.

`init` and `drop` are in the struct's file because they are the two functions
that are *about the struct existing* rather than about anything it is for.

## What the rules say about it

**Uniqueness.** Two structs with the same field types in the same order, up to
renaming, are one struct and the second is a compile error — the same rule
functions have, for the same reason. `struct Point { int x; int y; }` and
`struct Size { int w; int h; }` collide, and that is correct: they are the same
type and the program should say which one it means. A struct whose fields
differ in type, count or order does not collide.

**Three fields.** The action limit is three, and a struct's field list is not a
block, so nothing in the existing rules bounds it. The proposal is that it
should be bounded anyway, at three, for the reason every other three exists:
the seven-field font metrics record of §14 is exactly the thing that should be
two records. This is the first thing worth arguing about.

**Names.** A field name is scoped to its struct, so `p.x` and `s.x` may be
different types. This is the first exception `id` would have to "a name has one
type across a whole program", and it is unavoidable: without it every record in
a program would have to agree on what `x` means.

A directory has no entry limit, so a struct costs a file and nothing more.

## The three things with no obvious answer

### 1. A struct is a reference, and freeing it must be the compiler's job

`docs/SPEC.md` §6: memory is meant to be freed before exit (decided
2026-09-26), by the compiler proving that a list or string never escapes and
freeing it when its scope ends, with no syntax marking the free. Today `alloc`
is still a bump pointer and the arena is freed only at process exit; that is a
gap in the implementation (`docs/MEMORY.md` says what the first slice frees),
not a property of the language.

So a struct's storage is reclaimed the same way, by the same analysis, and
`drop` is not how it is freed: a hand-written free is exactly the syntax the
decision excludes (Q2). What `drop` could still do is release something the
struct *holds* that is not memory: a file handle, a device, a lock.

The open part is the escape analysis, not the arena: it has to become
field-sensitive (a list stored in a struct field counts as stored; a struct
passed to a callee that keeps a field counts as kept), and a value struct with
list fields makes "never escapes" harder to prove than a reference struct.

### 2. Nothing says when `drop` runs

`id` has no scopes that end, no destructors, and no `defer`. The candidates:

* **Never automatically.** `drop(p)` is an ordinary call the programmer makes.
  Simplest, and it makes `drop` a convention rather than a language feature —
  at which point it does not need to be in the struct's file at all.
* **At the end of the declaring function.** Predictable, and wrong for every
  record that is returned or stored.
* **Not at all, and no `drop`.** The narrowest thing that is still useful, and
  the easiest to widen later.

### 3. Value or reference

Lists are references and everything else is a value. A struct could be either,
and the answer decides what `f(p)` means when `f` writes to `p.x`.

* **Reference**, like a list. Consistent with the one aggregate `id` already
  has, and it is what §20's rasteriser pen wants — a point passed to a helper
  that moves it. Costs an allocation per record and makes `drop` matter more.
* **Value**, like an `int`. No allocation, no aliasing, and a record can live
  entirely in registers — which is what §1's Huffman decoder wants, five values
  in one loop. But then `init(p, ...)` cannot work, because `p` would be a
  copy, and the constructor has to *return* a struct instead.

These two want opposite answers, and they are the two motivating cases.

## The recommendation

Value semantics, no `drop`, three fields, and `init` returning the struct:

```
struct Point {
  int x;
  int y;
}

init(int x, int y) {
  Point p = Point;
  p.x = x;
  p.y = y;
} return Point p;
```

Because it is the smaller language: no allocation, no lifetime, no aliasing,
and nothing that has to be explained before a record can be used. It answers
§1, §14 and §20 — the rasteriser's pen becomes a returned value rather than a
mutated one, which is a rewrite of six functions rather than a reason not to.
Reference semantics can be added later as a second thing; value semantics
cannot be taken away.

What it does not answer is a record that owns a resource, which is what `drop`
was for. That case is `fs_open`'s handle today and it is an `int`, and it can
stay an `int` until a struct has a defined release (Q2).

## Then, a tuple

`docs/FRICTION.md` (retired; `git show 479234a^:docs/FRICTION.md`) §20 asks for a pair as the first record, and it should be
the first one built, because it is the one that proves the design: a point is
two `int`s, it is passed and returned constantly, and the rasteriser has six
functions that carry one as two parameters and eleven numbers in one `int[]`
where a human would write three points and a pen.

## Decisions needed

Written 2026-09-30 from `trials/` (jsontool, csvq, kv, httpd) and the rules as
`idc/bin/idc` enforces them. Nothing here is implemented. Each question lists
options, what the trials would have gained, and a recommendation (marked
**Recommend**; a recommendation is a guess until the user picks).

**What the trials show.** csvq, kv and httpd thread their state as parallel
lists: kv passes `string[] keys, int[] vals, int[] used, int[] st, word[] ea`
to about every function, and `st` is a record by index (`st_live`, `st_dead`,
... are conf.id slot numbers); httpd's `int[] mt` is `[code, keep, n,
bodyless]` and is written by `hd_flags`; csvq's `int[] st` is a cursor read as
`st[(import s_wid)]`. Every `chain` restates the whole parameter list, every
case restates every argument, and every fixture exports one name per list.
The state is also **mutated in place by callees that return something else**
(`load_file` returns a status code and updates `st`). That last fact decides
question 1.

### Q1. Value or reference (STRUCTS.md "three things" 3)

| option | example | tradeoff |
| --- | --- | --- |
| A. value (the proposal) | `Cursor c = advance(c);` | no allocation; but a function returns one thing, so `load_file` cannot return its code and the updated state. A struct with a list field still aliases that list, so "no aliasing" is not true of the trials' records. `Row[]` needs inline layout in the flat store. |
| B. reference | `bump(Cursor c) { c.pos = c.pos + 1; } return void;` | what `int[] st` already is; one allocation per record, which the memory decision frees when the record does not escape. `Row[]` is a list of addresses, like `string[][]` today. |
| C. both, two keywords | `struct Point` (value), `record Store` (reference) | covers §20 and the trials; two things to learn and explain. |

Trials benefit most from **B** (all three cited functions below mutate state
they were handed). **Recommend B.** This reverses the recommendation already
in this file; the hinge is the single return value. If the user wants A, the
trials' `st` counters cannot become structs without changing how the programs
return errors.

### Q2. When `drop` runs, and whether it exists (the proposal's 2)

| option | example | tradeoff |
| --- | --- | --- |
| A. no `drop` | (nothing) | the file holds only the struct; consistent with SPEC §6, where "no syntax marks" a free. |
| B. `drop` called by hand | `drop(p);` | a convention, and a syntax-marked free the memory decision rules out; a double free is possible. |
| C. `drop` run by the compiler at scope end | | needs the escape analysis anyway, and is wrong for returned records. |

No trial holds a resource in a record (kv's handle is an `int`). **Recommend A.**
This also makes STRUCTS.md's first "no obvious answer" stale: see the drift
note under Interactions.

### Q3. The three-field limit

| option | example | tradeoff |
| --- | --- | --- |
| A. hard 3, nest to get more | `struct Store { Table t; Log l; }` | matches the other threes; needs struct-in-struct, which is free under reference (Q1 B) and copies under value. |
| B. no limit | `struct Conn { int keep; int left; string[] out; int[] mt; }` | one record per idea, but the first unbounded list in the language. |
| C. limit 3 for value structs only | | only meaningful under Q1 C. |

kv's 5 lists become `Table{keys,vals,used}` + `Log{path,st,ea}`; httpd's
4 become `Conn` + `Bufs`. Both nest naturally, and the `st` of 7 counters
needs three small structs, which is the split the proposal wants. **Recommend A.**

### Q4. Structural uniqueness (missed by the proposal's own list)

As written, `struct Point {int x; int y;}` and `struct Size {int w; int h;}`
are one struct. httpd's `Stat{int sz; int mtm;}` and `Span{int keep; int
left;}` collide on day one, and so would any second pair in any program; the
struct's name and its fields' names are exactly what §16 wanted to keep.

| option | example | tradeoff |
| --- | --- | --- |
| A. structural, as proposed | second `{int,int}` is an error | the tuple, and nothing more; destroys the naming value. |
| B. field names count | `{x,y}` and `{w,h}` both allowed, `{x,y}` twice rejected | keeps the rule's intent (no copy-paste structs) and the names; two pairs with the same field names still collide. |
| C. no struct uniqueness | | two identical structs coexist and are different types; conflicts with "duplicates go to idstd". |

**Recommend B.** Function fingerprints must then include the struct type and
field names read, or two functions over different structs compare equal.

### Q5. Names: fields, variables, types

Fields are scoped to the struct (proposal). Still undecided: (a) does a field
name collide with an export or conf.id constant (`rot` may not be reused as a
variable)? (b) struct-typed locals, `Cursor c` here and `Conn c` there, are
the same one-type-per-name hazard as `int s`/`string s`, and worse, because
each struct adds a short-name vocabulary. **Recommend:** fields live in their
own namespace, exempt from the export/constant rule; variables keep the
existing rule, and the diagnostic names the new declaration (PROJECT.md
"Pitfall 6" says today's never does).

### Q6. Construction (the proposal's `init`)

Missed: function names are global, so two structs cannot each have `init`.
The proposal's own example also costs 1 + N actions: a three-field struct is
4 actions, one over the limit, and needs a `chain` inside the struct's file.

| option | example | tradeoff |
| --- | --- | --- |
| A. `init` per struct, named by convention | `point_init(int x, int y)` | works today's rules; a file per struct plus its init, and chain for 3 fields. |
| B. zero value, then assign | `Point p = Point; p.x = 1;` | no function; 1 + N actions. |
| C. constructor expression | `Point p = Point(1, 2);` | one action for any size; and as a call argument it counts as one level of call (SPEC §7.1). |

**Recommend C**, allowed only as an initialiser, and the struct file then
holds only the struct (closing the question of `init` in it).

### Q7. Test-case literals

A case takes literals only; `(import g)` may be an argument or an expected
value, never a check's value (TESTS.md).

| option | example | tradeoff |
| --- | --- | --- |
| A. positional list literal | `([1, 2], 7):([3, 2])` | no new syntax (a list literal already takes its type from its position); unreadable for nested structs. |
| B. constructor literal | `(Point(1, 2), 7):(Point(3, 2))` | same spelling as Q6 C; the compiler checks it against the position's type. |
| C. setups only | `given pt_t_a ((import pt_a)):((import pt_a))` | zero harness change, but then each case needs an exported struct, which is the 9-export fixture again, and no `then` can compare one. |

The trials' cases are dominated by `given ... (import x), (import y), ...`;
with one struct that is one import. **Recommend B**, with C still available.
The harness must print a struct in a failing case; today it can print ints,
strings and lists.

### Q8. Constants and exports of struct type

An export is one name with one owner (`'x' is already an exported global`).
A struct-typed export is fine. A struct constant in conf.id is not settled:
it is built by `idc_const_init` like a list, may hold list fields, and a
"locked" list inside an unlocked struct has no rule. A struct-returning
function whose whole body is literal assignments is the constant-wrapper
shape the language forbids. **Recommend:** no struct constants in v1; exports
of struct type allowed and initialised like lists (a read before the owner ran
traps, including in a case).

### Q9. Lists and equality

`Row[]` would replace csvq's `string[][] rows` + `int[] lines` pair. Under
Q1 B it is a list of addresses. `==` and `print` on a struct are undecided.
**Recommend:** v1 allows struct-typed list elements under B, forbids `==` and
`print` on structs (compare fields), and the harness compares by field.

### Q10. Which unit a struct belongs to

An imported tree is its own unit for struct identity, so a struct declared
in idstd and the same struct in a program are two types, and a program cannot
pass one to an idstd function. Options: (a) nominal by unit, (b) one struct
per whole program, an identical declaration elsewhere a duplicate. **Recommend
(b)**, consistent with "duplicates across two projects go to idstd".

### Q11. Layout

kv's 13-byte record header (`rec_off_kind`, `rec_off_klen`) is a byte layout
read with `peek`, and structs do not help it. **Recommend** stating that a
struct has no defined layout and cannot be `peek`ed, so nobody expects it to.

## Evidence

Signatures shortened; the structs are those in Q3.

1. `trials/kv/store/ops/edit/del/remove.id:2`, `db_del`.

   ```
   db_del(string path, string[] keys, int[] vals, int[] used, int[] st, word[] ea, string key)
   db_del(Store s, string key)
   ```

   7 parameters to 2. Its `chain` restates 7 and its four cases each write
   six `(import db_t_...)` arguments; they become one `(import db_t_store)`.
   `hmap_get(keys, vals, used, key, ...)` becomes `hmap_get(s.t, key, ...)`.

2. `trials/httpd/core/web/res/route/file/ser/serve.id:1`, `hd_reply`.

   ```
   hd_reply(int code, string fp, int sz, int mtm, int keep, int left, string[] out, int[] mt)
   hd_reply(Reply r, Conn c)
   ```

   8 parameters to 2, with `Reply{int code; string fp; Stat s}`,
   `Stat{int sz; int mtm}`, `Conn{int keep; int left; Bufs b}`,
   `Bufs{string[] out; int[] mt}`. The call chain `hd_ok` -> `hd_reply` ->
   `hd_full` passes the same `keep, left, out, mt` through all four levels.
   Shows Q4 too: `Stat` and a `{keep,left}` struct are both `{int,int}`.

3. `trials/csvq/data/read/parse/row/record.id:27`, `csv_row`.

   ```
   csv_row(word base, int d, int[] st, string[][] rows, int[] lines, string[] diag)
   csv_row(Src s, Cursor c, Sink k)
   ```

   6 parameters to 3, and `st[(import s_wid)]` becomes `c.wid`, removing the
   index constants from conf.id. `csv_keep` (same file, line 13) drops from 6
   parameters to `csv_keep(Cursor c, Sink k, string[] row, int ln)`.

What it does not fix: `csv_keep`'s two-way `push(rows, row); push(lines, ln)`
pair stays two lists unless Q9's `Row[]` is taken.

## Interactions with the rules as enforced today

| rule | result |
| --- | --- |
| Action limit | `p.x = v;` is one action, like `st[i] = v;`, so in-place code costs the same. Conflict: Q6's `init` for a 3-field struct is 4 actions (chain in the struct file). A constructor expression (Q6 C) avoids it. |
| One type per name | Conflict with "field names scoped to the struct" is deliberate (Q5). New hazard: struct-typed variable names. The compile error blames the wrong file today (PROJECT.md Pitfall 6). |
| Uniqueness (functions) | Fingerprints must include struct types and fields, or functions over different structs match. |
| Uniqueness (structs) | Conflict: structural uniqueness forbids a second `{int,int}` (Q4). |
| Test-case literals | Conflict: "literals only" has no struct form (Q7). `then` checks compare one literal at the check's return type, so a struct-returning check needs Q7 B. |
| Exports' single owner | No conflict for exports of struct type. `init` returning a struct cannot itself be the owner in the struct's file (an export is a statement in a function), so the owner is whichever function calls it; a setup in a case owns its fixture. |
| Memory freeing (SPEC §6, 2026-09-26) | Conflict with `drop`: a hand-written free is the syntax the decision excludes (Q2). Escape analysis must become field-sensitive: a list stored in a struct field counts as stored, a struct passed to a callee that keeps any field counts as kept. A value struct with list fields (Q1 A) makes "never escapes" harder to prove than a reference struct. Every target must free the same allocations. |
| 3 functions per file | No conflict; a struct costs a file, so kv-sized trees gain 3 to 5 small files. |
| `--target wasm` | No conflict of its own: `bin/idc` builds wasm from the C target's C, so a struct lowered for C reaches wasm with it (see Phase 4). |

## Effort

Sizes are guesses (S under a day, M a few days, L about a week); the compiler
is itself written in `id` under its own limits, so every change is also a
file-layout exercise. Not sized against a measurement.

1. **Parser (M).** `struct` declaration, `T.f` read and assign, type name in
   declaration and parameter position, constructor expression (Q6 C).
   Approve this alone to get syntax with no semantics.
2. **Checker (L).** struct table, field types, nominal/uniqueness rule (Q4),
   one-type-per-name changes (Q5), fingerprints, the diagnostics that name
   the fix, and the escape analysis extension (memory decision).
3. **Backends C and LLVM (M).** Reference structs lower to a flat-store
   address plus field offsets, so the two backends need only `peek/poke` at
   constant offsets; bounds checks come with it. Value structs (Q1 A) would
   be L, since each target needs aggregate passing and returning.
4. **Backend WASM (S).** `--target wasm` recompiles the C target's C, so a
   struct lowered to store offsets for C needs nothing more there; a
   separate WAT backend in `back/tgt/` would be a new port (BACKENDS.md).
5. **Harness (M).** struct literals in cases (Q7), printing, `given` with
   struct exports, duplicate-case comparison.
6. **idstd adoption (M, after 1 to 5).** `fx_*` and any `string[] + int[]`
   pairs; each conversion is its own change with cases. Needs Q10.

The first shippable slice is 1 to 3 with reference structs and Q6 C, without
struct lists or constants (Q8, Q9).
