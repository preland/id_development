# Error codes

> **Status: describes current practice.** Every code below is emitted by the
> tree, and `idc/tests/diagnostics.sh` fails when a code has no section here,
> when a section's examples do not behave as written, or when a section's code
> is not emitted.

Every diagnostic that has moved to the diagnostic record (`docs/DIAGNOSTICS.md`)
carries a stable code in square brackets, after its severity in the human form and
at the end of its first line in the plain one:

```
error[E0501]: function 'add' has 0 test case(s); --require-tests needs at least 2 (see docs/TESTS.md)
  --> add.id:1:1
  in add
```

That is the human form, the default on a terminal; `in add` is the function the diagnostic is in.
`--diagnostics=plain`, the default when stderr is piped, keeps
the one-line head `FILE:LINE: error: MESSAGE [CODE]`:

```
add.id:1: error: function 'add' has 0 test case(s); --require-tests needs at least 2 (see docs/TESTS.md) [E0501]
```

`idc --explain E0501` prints the section of this file headed `## E0501`: what
the error means, why the rule exists, and a program that breaks it beside one
that does not. The same text is what a person or an agent reads when a
diagnostic's one-line `why` is not enough.

How the examples are used: `tests/diagnostics.sh` builds every `id` block under
an `Incorrect:` label and requires its code in the output, and builds every one
under `Correct:` and requires success. A block written ```` ```id ```` is built
with `--allow-untested` (the two-case rule is not what it is about);
```` ```id tests ```` is built with every rule, test cases included; ```` ```text ````
is for what a single file cannot show (a directory tree, a `conf.id`) and is not
built. A code is only ever added to the compiler together with its section here.

Codes are grouped by what broke: `E01xx` syntax, `E02xx` the size limits, `E03xx`
names and scope, `E04xx` uniqueness, `E05xx` test cases, `E06xx` types, `E07xx`
the project tree.

## E0101 expected one token, found another

The parser needed a particular token to finish what it was reading and met a
different one. The token it names is almost never where the mistake is: a
missing `;`, `)` or `}` is noticed one token late, so look at the line before.

A syntax error is followed by diagnostics that are only its echo: the parser skips
tokens to recover, and the later stages read what is left (`int x 5;` also gives
`unexpected token ';'` and `undefined variable ';'`). They are not hidden. Each
says `= note: follows from the error at FILE:LINE above` (`"follows"` in the JSON),
and fixing the error above it removes them.

Incorrect:

```id
main(int argc, string[] argv) {
  int x 5;
} return int 0;
```

Correct:

```id
main(int argc, string[] argv) {
  int x = 5;
} return int x;
```

## E0102 unexpected token

An operator stands where an expression or a statement has to start. `id` has
line comments only, so a `/* ... */` block comment is reported here too: it
cannot end a comment before the end of a line, and so can never hide code.

Incorrect:

```id
main(int argc, string[] argv) {
  int x = ;
} return int x;
```

Correct:

```id
main(int argc, string[] argv) {
  int x = 1;
} return int x;
```

## E0201 a block performs more than three actions

A block holds at most three actions: each statement, `if`, `else` and `while`
counts as one, and `return` is free. A function that needs more continues into
a `chain`, which restates the parameters and starts a new block, or splits
into two functions. The limit keeps every block short enough to read at a
glance and to test.

Incorrect:

```id
main(int argc, string[] argv) {
  int a = 1;
  int b = 2;
  int c = 3;
  int d = 4;
} return int d;
```

Correct:

```id
main(int argc, string[] argv) {
  int a = 1;
  int b = 2;
  int c = 3;
} chain (int argc, string[] argv) {
  int d = a + b + c;
} return int d;
```

## E0202 code is nested more than two levels deep

An `if` or `while` inside another is level two; a third inside those is
rejected. Move the innermost block into its own function: it gets its own two
levels of nesting and its own test cases.

Incorrect:

```id
main(int argc, string[] argv) {
  int i = 0;
  while(i < 2) {
    if(i == 1) {
      while(i < 3) {
        i = i + 1;
      }
    }
    i = i + 1;
  }
} return int i;
```

Correct:

```id
settle(int i) {
  while(i < 3) {
    i = i + 1;
  }
} return int i;

main(int argc, string[] argv) {
  int i = 0;
  while(i < 2) {
    if(i == 1) {
      i = settle(i);
    }
    i = i + 1;
  }
} return int i;
```

## E0203 too many functions in one file

A file holds at most three functions, so the tree and not the file carries the
structure. A function and its `chain` segments count as one. The directory it
moves to may itself be full (a directory holds at most three files and
directories, E0701): `idc/.idc-cache/idlayout --room PROJECT_ROOT DIR` lists the
nearest places that have room.

Incorrect:

```id
one(int x) {
  int y = x + 1;
} return int y;

two(int x) {
  int y = x + 2;
} return int y;

three(int x) {
  int y = x + 3;
} return int y;

main(int argc, string[] argv) {
  int a = one(argc);
} return int a;
```

Correct:

```id
one(int x) {
  int y = x + 1;
} return int y;

two(int x) {
  int y = x + 2;
} return int y;

main(int argc, string[] argv) {
  int a = one(argc);
} return int a;
```

## E0204 a chain follows a segment that had room

A `chain` continues a function that has run out of its three actions. A segment
that still had room should have kept writing: there is one way to continue a
function, not two. (`blank` pads a segment only when the chain's first
statement is too large to move up.)

Incorrect:

```id
main(int argc, string[] argv) {
  int a = 1;
  int b = 2;
} chain (int argc, string[] argv) {
  int c = a + b;
} return int c;
```

Correct:

```id
main(int argc, string[] argv) {
  int a = 1;
  int b = 2;
  int c = a + b;
} return int c;
```

## E0301 undefined variable

The name is not declared anywhere in the program. A variable exists from its
declaration to the end of the block that declares it; a parameter is a variable
of its function. Check the spelling first: a typo is the usual cause.

Incorrect:

```id
main(int argc, string[] argv) {
  print(total);
} return int 0;
```

Correct:

```id
main(int argc, string[] argv) {
  int total = 3;
  print(total);
} return int 0;
```

## E0302 variable declared twice in one function

A name means one variable inside a function. Declaring it again would make every
later use ambiguous; assign to the first instead.

Incorrect:

```id
main(int argc, string[] argv) {
  int n = 1;
  int n = 2;
} return int n;
```

Correct:

```id
main(int argc, string[] argv) {
  int n = 1;
  n = 2;
} return int n;
```

## E0303 one name, two types

A name keeps one type across the whole program, so one name always means one
kind of value wherever a reader meets it. Two functions may each have a local
called `total`, but only if both are `int`.

Incorrect:

```id
first(int a) {
  int total = a + 1;
} return int total;

second(int a) {
  string total = "" + a;
} return string total;

main(int argc, string[] argv) {
  int x = first(argc);
  string y = second(argc);
} return int 0;
```

Correct:

```id
first(int a) {
  int total = a + 1;
} return int total;

second(int a) {
  string text = "" + a;
} return string text;

main(int argc, string[] argv) {
  int x = first(argc);
  string y = second(argc);
} return int 0;
```

## E0304 no such function

A call names a function the program defines, a builtin, or a function of the
standard library; nothing by this name is any of them. A typo is the usual cause.
A standard-library function is only found when idstd is (`--std DIR`, or
`$IDSTD_HOME`); `idstd/NAMES.md` lists what it has.

Incorrect:

```id
main(int argc, string[] argv) {
  int n = lenn("abc");
} return int n;
```

Correct:

```id
main(int argc, string[] argv) {
  int n = len("abc");
} return int n;
```

## E0305 a variable belongs to another function

A variable is private to the function that declares it. To share one, the
declaring function exports it (`export TYPE NAME = ...;`) and the reader says so
with `(import NAME)`; or the value is passed as an argument.

Incorrect:

```id
setup() {
  int level = 3;
} return void;

main(int argc, string[] argv) {
  setup();
  print(level);
} return int 0;
```

Correct:

```id
setup() {
  export int level = 3;
} return void;

main(int argc, string[] argv) {
  setup();
  int l = (import level);
  print(l);
} return int 0;
```

## E0306 calling a variable

A call runs a function by its name. A variable holds a value, and only a variable
of a function type (`func(...) return T`) can be called.

Incorrect:

```id
main(int argc, string[] argv) {
  int thing = 1;
  int r = thing();
} return int r;
```

Correct:

```id
main(int argc, string[] argv) {
  int thing = 1;
  int r = thing + 1;
} return int r;
```

## E0307 variable used outside its scope

A variable exists from its declaration to the end of the block that declares it.
A use before the declaration, or after the block has closed, is rejected where
it is written.

Incorrect:

```id
main(int argc, string[] argv) {
  print(n);
  int n = 1;
} return int 0;
```

Correct:

```id
main(int argc, string[] argv) {
  int n = 1;
  print(n);
} return int 0;
```

## E0308 a variable named like a function

A function and a variable cannot share a name, because a call and a read of the
name would look alike. Rename the variable.

Incorrect:

```id
size(int x) {
  int y = x + 1;
} return int y;

main(int argc, string[] argv) {
  int size = 3;
} return int size;
```

Correct:

```id
size(int x) {
  int y = x + 1;
} return int y;

main(int argc, string[] argv) {
  int width = 3;
} return int width;
```

## E0309 a local named like an exported global

An exported global is visible to the whole program through `import`, so a local of
the same name would hide it from the reader. Read the global with `(import NAME)`
or give the local another name.

Incorrect:

```id
setup() {
  export int level = 3;
} return void;

main(int argc, string[] argv) {
  int level = 1;
} return int level;
```

Correct:

```id
setup() {
  export int level = 3;
} return void;

main(int argc, string[] argv) {
  int depth = 1;
} return int depth;
```

## E0401 two functions with one name

A function is called by its name alone, so a name can mean only one function.
Rename one; if the two do the same thing, keep one and call it from both places.

Incorrect:

```id
twice(int x) {
  int y = x * 2;
} return int y;

twice(int x) {
  int y = x * 3;
} return int y;

main(int argc, string[] argv) {
  int a = twice(argc);
} return int a;
```

Correct:

```id
twice(int x) {
  int y = x * 2;
} return int y;

thrice(int x) {
  int y = x * 3;
} return int y;

main(int argc, string[] argv) {
  int a = twice(argc);
} return int a;
```

## E0402 two functions with the same signature and logic

Two functions with the same parameter types, return type and logic are one
function written twice, however their parameters and locals are spelled, and
every later fix would have to be made twice. Delete one and call the other from
both places, or make them genuinely differ. The diagnostic names both places.

Incorrect:

```id
double_it(int x) {
  int y = x * 2;
} return int y;

twice(int n) {
  int m = n * 2;
} return int m;

main(int argc, string[] argv) {
  int a = double_it(argc);
} return int a;
```

Correct:

```id
double_it(int x) {
  int y = x * 2;
} return int y;

main(int argc, string[] argv) {
  int a = double_it(argc);
} return int a;
```

## E0403 a function that only returns a constant

A value that never changes is a constant, and a constant belongs in `conf.id`,
where every reader finds it, not behind a function every caller has to open. The
diagnostic gives the declaration to write and says how to read it.

Incorrect:

```id
limit() {
} return int 10;

main(int argc, string[] argv) {
  int n = limit();
} return int n;
```

Correct:

```text
conf.id:
  int limit = 10;

main.id:
  main(int argc, string[] argv) {
    int n = (import limit);
  } return int n;
```

## E0405 functions that differ only in an imported value

Two functions that differ only in which imported global they read are one
function written twice; the value is the only thing that varies, so it belongs in
a parameter.

Incorrect:

```id
use_a(int x) {
  int y = x + (import ia);
  int z = y * 2;
} return int z;

use_b(int x) {
  int y = x + (import ib);
  int z = y * 2;
} return int z;

main(int argc, string[] argv) {
  export int ia = 3;
  export int ib = 4;
  int a = use_a(1);
} chain (int argc, string[] argv) {
  int b = use_b(1);
  print("" + a + " " + b);
} return int 0;
```

Correct:

```id
use(int x, int shift) {
  int y = x + shift;
  int z = y * 2;
} return int z;

main(int argc, string[] argv) {
  int a = use(1, 3);
  int b = use(1, 4);
  print("" + a + " " + b);
} return int 0;
```

## E0501 a function has fewer than two test cases

A function is finished when two cases pass. The cases sit directly under the
function, one per line as `(ARGS):(EXPECTED)`, run on every build, and so
document the function and cannot drift from it (`docs/TESTS.md`). They must
describe two different behaviours, and each must be able to fail if the function
is wrong. The diagnostic offers a skeleton to fill in (`idc --diagnostics=json`
gives it as an edit with placeholders).

Incorrect:

```id tests
add(int a, int b) {
  int s = a + b;
} return int s;

main(int argc, string[] argv) {
  int c = add(1, 2);
  print(c);
} return int 0;
(1, ["x"]):(0)
(2, ["x", "y"]):(0)
```

Correct:

```id tests
add(int a, int b) {
  int s = a + b;
} return int s;
(1, 2):(3)
(0, 0):(0)

main(int argc, string[] argv) {
  int c = add(1, 2);
  print(c);
} return int 0;
(1, ["x"]):(0)
(2, ["x", "y"]):(0)
```

## E0502 a test case repeats an earlier one

The two-case minimum is a floor on evidence, not on line count, and the cheapest
way to meet it is to write the same case twice. Cases are compared as tokens, so
changing the spacing does not make one different. The diagnostic names the case
it repeats.

Incorrect:

```id tests
add(int a, int b) {
  int s = a + b;
} return int s;
(1, 2):(3)
(1, 2):(3)

main(int argc, string[] argv) {
  int c = add(1, 2);
  print(c);
} return int 0;
(1, ["x"]):(0)
(2, ["x", "y"]):(0)
```

Correct:

```id tests
add(int a, int b) {
  int s = a + b;
} return int s;
(1, 2):(3)
(0, 0):(0)

main(int argc, string[] argv) {
  int c = add(1, 2);
  print(c);
} return int 0;
(1, ["x"]):(0)
(2, ["x", "y"]):(0)
```

## E0503 a case passes the wrong number of arguments

A case calls the function under test with its first tuple, so that tuple holds one
literal per parameter.

Incorrect:

```id tests
add(int a, int b) {
  int s = a + b;
} return int s;
(1):(1)
(0, 0):(0)

main(int argc, string[] argv) {
  int c = add(1, 2);
  print(c);
} return int 0;
(1, ["x"]):(0)
(2, ["x", "y"]):(0)
```

Correct:

```id tests
add(int a, int b) {
  int s = a + b;
} return int s;
(1, 2):(3)
(0, 0):(0)

main(int argc, string[] argv) {
  int c = add(1, 2);
  print(c);
} return int 0;
(1, ["x"]):(0)
(2, ["x", "y"]):(0)
```

## E0504 a case expects more values than the function has parameters

After the call, a case's second tuple lists the parameters' values left to right.
It may stop early, but it cannot name more parameters than the function takes.
This arises for functions that return nothing and leave their result in an
argument, such as a list they fill.

Incorrect:

```id tests
fill(int[] xs) {
  push(xs, 1);
} return void;
([]):([1], 2)
([5]):([5, 1])

main(int argc, string[] argv) {
  int c = argc;
  print(c);
} return int 0;
(1, ["x"]):(0)
(2, ["x", "y"]):(0)
```

Correct:

```id tests
fill(int[] xs) {
  push(xs, 1);
} return void;
([]):([1])
([5]):([5, 1])

main(int argc, string[] argv) {
  int c = argc;
  print(c);
} return int 0;
(1, ["x"]):(0)
(2, ["x", "y"]):(0)
```

## E0505 a case expects the wrong number of return values

A function that returns a value is checked against exactly that one value, so the
expected tuple of its cases holds one literal.

Incorrect:

```id tests
add(int a, int b) {
  int s = a + b;
} return int s;
(1, 2):(3, 4)
(0, 0):(0)

main(int argc, string[] argv) {
  int c = add(1, 2);
  print(c);
} return int 0;
(1, ["x"]):(0)
(2, ["x", "y"]):(0)
```

Correct:

```id tests
add(int a, int b) {
  int s = a + b;
} return int s;
(1, 2):(3)
(0, 0):(0)

main(int argc, string[] argv) {
  int c = add(1, 2);
  print(c);
} return int 0;
(1, ["x"]):(0)
(2, ["x", "y"]):(0)
```

## E0601 a comparison and a bitwise operator without parentheses

The bitwise operators bind tighter than the comparisons in `id` and looser in C,
so a reader who knows the other table reads the line differently. The rule asks
for the grouping to be written down. The diagnostic's edit is the same line with
the parentheses the current precedence implies.

Incorrect:

```id
main(int argc, string[] argv) {
  int flags = argc;
  int on = 0;
  if(flags & 4 == 4) {
    on = 1;
  }
} return int on;
```

Correct:

```id
main(int argc, string[] argv) {
  int flags = argc;
  int on = 0;
  if((flags & 4) == 4) {
    on = 1;
  }
} return int on;
```

## E0602 the return clause has the wrong type

A function's return clause must have exactly the type the function declares, so
that every caller can rely on what it gets back. Convert the value before
returning it, or change the declared type.

Incorrect:

```id
describe(int n) {
  string s = "n" + n;
} return int s;

main(int argc, string[] argv) {
  int d = describe(argc);
} return int d;
```

Correct:

```id
describe(int n) {
  string s = "n" + n;
} return string s;

main(int argc, string[] argv) {
  string d = describe(argc);
} return int 0;
```

## E0604 cannot compare these two types

`==` and `!=` compare two strings or two numbers, and `<` `<=` `>` `>=` compare
two numbers; `id` has no ordering on strings and no silent conversion between a
string and a number. Convert one side first (`to_int(s)` makes a number of a
string, and `"" + n` a string of a number).

Incorrect:

```id
main(int argc, string[] argv) {
  int hit = 0;
  if(argv[0] == 1) {
    hit = 1;
  }
} return int hit;
```

Correct:

```id
main(int argc, string[] argv) {
  int hit = 0;
  if(argc == 1) {
    hit = 1;
  }
} return int hit;
```

## E0605 a call passes the wrong number of arguments

A call passes exactly the arguments the function declares, in order, so that every
parameter gets a value. The diagnostic's help shows the signature.

Incorrect:

```id
inc(int n) {
  int m = n + 1;
} return int m;

main(int argc, string[] argv) {
  int r = inc(1, 2);
} return int r;
```

Correct:

```id
inc(int n) {
  int m = n + 1;
} return int m;

main(int argc, string[] argv) {
  int r = inc(1);
} return int r;
```

## E0606 an argument has the wrong type

An argument must have exactly the type of its parameter; `id` converts nothing
silently. Pass a value of the parameter's type, or convert it first.

Incorrect:

```id
inc(int n) {
  int m = n + 1;
} return int m;

main(int argc, string[] argv) {
  int r = inc("nope");
} return int r;
```

Correct:

```id
inc(int n) {
  int m = n + 1;
} return int m;

main(int argc, string[] argv) {
  int r = inc(to_int("1"));
} return int r;
```

## E0701 a directory holds more than three entries

A directory holds at most three files and directories (`conf.id` and `backend.id`
do not count), so every listing reads at a glance and the tree carries the
structure. The diagnostic lists the entries, and names the nearest places that
`idlayout --room` finds with room. Group related entries into a subdirectory named
for what they have in common.

Incorrect:

```text
p/a.id  p/b.id  p/c.id  p/d.id
```

Correct:

```text
p/a.id  p/b.id  p/rest/c.id  p/rest/d.id
```

## E0702 a file with a generic name

A name like `util.id`, `helper.id`, `misc.id` or `common.id` says nothing about
what the file is for, so unrelated code collects in it. Name the file for what it
holds; the functions in it say what that is.

Incorrect:

```text
p/util.id
```

Correct:

```text
p/lines.id
```

## E0703 a file named like its directory

A file named like the directory that holds it (`loop/loop.id`) says nothing about
why it exists. Name it for what it holds, or merge it into the directory's other
files.

Incorrect:

```text
p/loop/loop.id
```

Correct:

```text
p/loop/scan.id
```

## E0704 a directory named like its parent

A directory named like the one that holds it (`loop/loop/`) says nothing about
why it exists. Name it for what it holds, or merge it into the parent.

Incorrect:

```text
p/loop/loop/scan.id
```

Correct:

```text
p/loop/scan.id
```

## E0705 a numbered copy

A sibling numbered after another (`chunk.id`, `chunk2.id`) says only that it came
second, not what it is for. Name each for what it holds, so that the names say how
they differ.

Incorrect:

```text
p/chunk.id  p/chunk2.id
```

Correct:

```text
p/chunk_read.id  p/chunk_write.id
```

## E0706 `import.id` is now `conf.id`

The project manifest has one name, `conf.id`: it holds the project's constants as
well as the dependencies it names. Rename the file, in the same directory, with
the same contents.

Incorrect:

```text
p/import.id
```

Correct:

```text
p/conf.id
```

## E0707 a `conf.id` below the root

A `conf.id` is read only at the root of a project or of a dependency. Anywhere
else it is neither compiled nor read, so anything it defines silently does not
exist. Rename the file for what it holds, or move its constants and imports to the
`conf.id` at the root.

Incorrect:

```text
p/conf.id  p/sub/conf.id
```

Correct:

```text
p/conf.id  p/sub/limits.id
```
