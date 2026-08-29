# Records in `id`

> **Status: a proposal.** Nothing here is implemented. It is written down first
> because a record is the largest thing `id` has ever added, it interacts with
> every rule the language already has, and three of those interactions have no
> obvious answer.

`docs/FRICTION.md` asks for this four times, from four directions:

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
`docs/FRICTION.md` §6 is already the record of how much that decision costs
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

**Three entries per directory** applies unchanged, so a struct costs a file.

## The three things with no obvious answer

### 1. A struct is a reference, and there is nothing to release it

`docs/SPEC.md` §6: `alloc` is a bump pointer and nothing is freed before the
process exits. So `drop` cannot reclaim a struct's storage — it can only
release something the struct *holds*: a file handle, a device, a lock.

That makes `drop` honest but narrow, and it makes a long-running program — a
kernel, a game loop, an editor — unable to make records in a loop. This is the
same limitation lists and strings already have, which is why it is not a reason
not to do this. It is a reason the arena has to be answered eventually, and the
answer will change what `drop` means when it arrives.

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
stay an `int` until the arena question is answered.

## Then, a tuple

`docs/FRICTION.md` §20 asks for a pair as the first record, and it should be
the first one built, because it is the one that proves the design: a point is
two `int`s, it is passed and returned constantly, and the rasteriser has six
functions that carry one as two parameters and eleven numbers in one `int[]`
where a human would write three points and a pen.
