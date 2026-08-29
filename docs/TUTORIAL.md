# Writing your first `id` program

> **Status: current.** The program it builds is `demos/wordcount`, which the
> suite builds on every run.

We are going to build **wordcount**: it reads text on stdin and prints each
distinct word with how many times it appeared.

```
$ printf 'the cat and the hat\nthe cat sat\n' | ./wordcount
the 3
cat 2
and 1
hat 1
sat 1
```

The finished program is in [`demos/wordcount`](../demos/wordcount) — 16
functions across 5 files and 5 directories, which sounds like a lot for
something you would write in six lines of Python. By the end you should
understand why `id` spreads it out like that, and be able to tell when the
shape is helping you and when you are fighting it.

Every code block below was compiled and run. If one does not work for you,
that is a bug in this document.

---

## 1. The shape of a function

```
add(int a, int b) {
  int sum = a + b;
} return int sum;
```

Two things are unusual, and both are deliberate.

(Calling that local `s` is fine, and `sum` is used here only because it reads
better. It was *not* fine until recently — `s` is a `string` in the standard
library, and the one-type-per-name rule used to reach across that boundary.
Section 8 has the story, because the rule still applies inside your own tree.)

**The `return` clause comes after the closing brace**, and it names the type
and the expression. There is no `return` statement inside the body — you
cannot leave a function early. A function has one exit, always at the bottom,
and you can see it without reading the body.

**Variables are declared with their type and are function-scoped.** `s` is
assigned inside the braces and returned after them, because declarations are
hoisted to the function, not the block.

Save this as `add.id` with a `main` and build it:

```
main(int argc, string[] argv) {
  print(add(2, 3));
} return int 0;
```

```sh
idc/bin/idc add.id -o add && ./add     # 5
```

`main` is the entry point, its `int` return becomes the exit code, and
`idc/bin/idc` takes exactly one argument: a file, or a project directory.

## 2. The rule of 3, and your first compile error

Here is the natural way to write the top of wordcount:

```
main(int argc, string[] argv) {
  string[] words = [];
  int[] counts = [];
  string text = read_all();
  tally(text);
} return int 0;
```

It does not compile:

```
main.id:1: error: a block in 'main' performs 4 actions; the limit is 3
```

**Every block may perform at most 3 actions.** A statement is one action, an
`if` is one and each `else` another, a `while` is one. The `return` clause is
free. And this applies to *every* block, not just function bodies — the inside
of an `if` gets its own budget of 3.

There is also a **nesting limit of 2**: a `while` inside a function is depth
1, an `if` inside that `while` is depth 2, and there is no depth 3.

This is the rule that shapes everything else. You do not get to write a
20-line function that does four things; you write four functions and one that
calls them. The fix here is to give the tables their own function:

```
main(int argc, string[] argv) {
  init();
  tally(read_all());
  report();
} return int 0;
```

Three actions. Read it aloud and it is the whole program: set up, count,
print.

> **The habit to build:** when you hit the limit, do not look for a way to
> squeeze the statements together. Look for the *name* of the thing the extra
> statements were doing. `init` was always there; the limit just made you
> say it.

## 3. Sharing state: `export` and `import`

`words` and `counts` need to be visible to several functions. A variable is
private to its function unless it is exported:

```
init() {
  export string[] words = [];
  export int[] counts = [];
} return void;
```

Everyone else reads them with `(import words)`. There is no other way to touch
another function's variable, and an exported name is reserved program-wide —
no other variable may be called `words`.

**An export does not exist until its declaring function has run.** Reading one
before that is reading uninitialised memory. This is why `init()` is main's
first action, and the compiler will catch the worst version of the mistake:
if nothing reachable from `main` ever calls the function that declares an
export, reading it is a compile error.

## 4. Scanning text without a substring

`id` gives you `len(s)`, `charat(s, i)` (the byte at `i`, or `-1` past the
end), and `chr(n)`. There is no `substr`, no `split`, and no regex. A word is
extracted a character at a time:

```
slice(string s, int a, int b) {
  string out = "";
  while(a < b) {
    out = out + chr(charat(s, a));
    a = a + 1;
  }
} return string out;
```

Note there is no `break` and no `continue`. A loop runs until its condition is
false, so the condition has to carry everything — which is why the walk is
written as "where does the next step start" rather than "scan until I see a
space":

```
tally(string text) {
  int i = 0;
  while(i < len(text)) {
    i = step(text, i);
  }
} return void;

step(string text, int i) {
  int j = i;
  if(is_space(charat(text, i)) == 1) {
    j = i + 1;
  } else {
    j = take_word(text, i);
  }
} return int j;
```

`step` returns the next index either way. The loop stays one action, and every
branch of the decision is visible in one screenful.

## 5. Records are parallel lists

`id` has no struct. A row is an **index that means the same thing in every
column**:

```
words[i]   "the"   "cat"   "and"
counts[i]   3       2       1
```

So "look up a word" is "find its index", and "bump its count" is "write column
2 at that index". This is the single most important idiom in the language, and
every real `id` program is built on it — including the compiler, whose symbol
table is six parallel lists.

Lists have **reference semantics**: passing one to a function and mutating it
is visible to the caller. That is how `id` gets shared mutable state, and it
is what makes the next section work.

## 6. The trap everyone hits

You want to increment a count. You write:

```
(import counts)[k] = (import counts)[k] + 1;
```

and the compiler rejects it. Index-assignment is only recognised when the
target starts with a plain name, and `(import counts)` does not. (This used to
compile into a discarded comparison and silently do nothing, which is why
there is now an error with the fix in it.)

The fix is to hand the list to a function that takes it as a parameter:

```
inc(int k) {
  lset((import counts), k, (import counts)[k] + 1);
} return void;
```

`lset` is `lset(int[] xs, int i, int v) { xs[i] = v; }` — and you do not write
it, because **the standard library already has it**. `idstd` is imported by
default; you just call it.

If you do write your own, you get this:

```
add.id:16: error: function 'lset' already defined at .../idstd/core/data/lst/lst.id:21
add.id:16: error: function 'lset' has the same signature and logic as 'lset'
```

and you would get the second error *even if you named yours something else*,
because two functions may not share a signature and a body up to renaming.
The language is telling you there is already one. Call it.

> **The habit to build:** before writing a small helper, assume `idstd` has
> it. `fx_min`, `fx_max`, `fx_abs`, `str_find`, `lst_sort`, `chr_is_digit` and
> about 120 others are already there.

## 7. Growing into a tree

Sixteen functions do not fit in one file, because **a file holds at most 3
functions** and **a directory holds at most 3 entries** (files and
subdirectories combined). A program grows by nesting:

```
wordcount/
├── main.id            main, init
├── scan/
│   ├── scan.id        tally, step, is_space
│   └── word/
│       └── word.id    take_word, word_end, slice
└── tally/
    ├── tally.id       bump, find, maybe
    └── add/
        ├── add.id     add, inc
        └── report.id  report, line
```

Every `.id` file in the tree is compiled together as one program, and function
calls resolve across all of them automatically — there are no imports between
your own files. So the tree is purely about *reading*: the path to a function
is a sentence about where it belongs.

```sh
idc/bin/idc demos/wordcount -o wordcount
printf 'the cat and the hat\nthe cat sat\n' | ./wordcount
```

> **The habit to build:** name directories after the *stage of work*, not the
> data type. `scan/` and `tally/` are the two things this program does. A
> directory called `utils/` would fill up in a week and tell you nothing.

## 8. Things that will bite you

Every one of these is real and has bitten someone in this repository.

**A short local name collides with another function in your own tree, not
with the library.** Write the most obvious possible function:

```
add(int a, int b) {
  int s = a + b;
} return int s;
```

`s` is a `string` in the standard library, and this used to be three errors
pointing inside `idstd` at code you had never seen, with nothing naming your
file. It compiles now: the one-type-per-name rule applies within a compilation
unit — your tree, or one imported tree — and not across them. Your `int s` and
the library's `string s` are two different names.

Inside your own tree the rule is unchanged, and that is where it still bites:
`int s` in one file and `string s` in another is an error, wherever the two
files are.

**String `+` in a loop is quadratic, and nothing is ever freed.** `id` has no
garbage collection and no `free`; the arena is released when the process
exits. Building a 200 000-character string one character at a time costs about
20 GB and 9 seconds. `slice` above is fine because a word is short — but never
do it over a whole file. For big text, write bytes into the flat store with
`poke8` and call `str_of_mem` once.

**There is no `break`, no `continue`, no early `return`, and no `for`.** Loops
carry their exit in the condition. If that gets awkward, it usually means the
body wants to be a function that returns the next state — which is what `step`
does.

**`=` in an expression means equality.** Assignment is a statement, so a bare
`=` inside an expression compiles to `==`. This is convenient right up until
you write `x = 1;` meaning a comparison, so a statement that is only a
comparison is now an error.

**Block comments do not exist.** `/* ... */` is a compile error telling you to
use `//`.

**Integer overflow wraps** (32-bit), division truncates toward zero, and
division by zero traps with a message rather than a core dump. Indexing a list
out of bounds traps too. See [`SPEC.md`](SPEC.md) for the full list of what is
guaranteed.

**A name has one type across your whole program.** If `i` is an `int`
anywhere in your tree, it is an `int` everywhere in it. This is why `id` code
uses short, boring, consistent names — and why picking `s` for a string in one
function and a struct-ish index in another will not compile. An imported tree
is a separate unit and keeps its own vocabulary.

## 9. Where to go next

- Read [`demos/adventure`](../demos/adventure) (120 lines, 3 files) for input
  handling, then [`demos/solitaire`](../demos/solitaire) (1150 lines) for what
  a real program looks like at scale.
- [`README.md`](../README.md) has the complete list of builtins and rules.
- [`SPEC.md`](SPEC.md) is what the language guarantees, independent of which
  backend you compile with.
- `idc/bin/idc PATH --emit-c out.c` shows you the C your program became, which is
  the fastest way to understand what a construct actually costs.

### An exercise

`wordcount` prints words in first-appearance order. Make it print them
**most-frequent first**. You will need a sort, `idstd` has `lst_sort` for
`int[]`, and you will discover that it cannot sort one list by another —
which is a real limitation of the language today, not a gap in your
understanding. Solving it teaches you more about `id` than another page of
this document would.
