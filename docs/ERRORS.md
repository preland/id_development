# Error codes

> **Status: describes current practice.** Every code below is emitted by the
> tree, and `idc/tests/diagnostics.sh` fails when a code has no section here,
> when a section's examples do not behave as written, or when a section's code
> is not emitted. Retired codes are listed at the end and are never reused.

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
the project tree, `E08xx` pure functions.

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

Two more spellings are reported here with their own message. A `.` that starts
an expression (`.5`, `.e5`) is not a float literal, which needs a digit before
the point. A `#!` anywhere but the first line of a file is not a comment: only
line 1 may be a shebang, so that `./script.id` can run; move the line to the top
or turn it into a `//` comment.

## E0103 a float literal with an exponent that has no digits

A float's exponent is `e` or `E`, an optional `+` or `-`, and at least one digit.
`1e` and `1e+` name no number. They are not read as `1` followed by a variable
called `e`, which would report an undefined variable for a mistake in a number.

Incorrect:

```id
main(int argc, string[] argv) {
  float x = 1e;
} return int 0;
```

Correct:

```id
main(int argc, string[] argv) {
  float x = 1e5;
  print("" + x);
} return int 0;
```

## E0104 a float literal too large to represent

A `float` is an IEEE-754 binary64 and its largest finite value is about
`1.7976931348623157e308`. A literal that rounds to infinity cannot be written:
`1e999`, or any value at or above `2^1024 - 2^970`, the exact point where
round-to-nearest-even leaves the largest finite value. A literal too small to
represent rounds to zero, as it does in C, and is accepted.

Incorrect:

```id
main(int argc, string[] argv) {
  float x = 1e999;
} return int 0;
```

Correct:

```id
main(int argc, string[] argv) {
  float x = 1.7976931348623157e308;
  print("" + x);
} return int 0;
```

## E0105 an opening bracket is never closed

A `(` or `[` needs its `)` or `]`. The parser does not supply a missing one at
the end of the statement: the diagnostic is at the token where the closing bracket
was expected, and its `related:` line names the line the unclosed bracket opened
on. With several brackets open on one line the fix is the one the parser reports,
the outermost bracket that is still open, so the missing closer goes last, just
before the `;`, `{` or `:` named in `at`.

The same check covers a function's parameter list, a call's arguments, an array
literal, an index, an `if` or `while` condition, a case's `(args):(expected)`
tuples, and an expression in a `conf.id` constant.

Incorrect:

```id
main(int argc, string[] argv) {
  int x = (1 + (2 * 3);
} return int x;
```

Correct:

```id
main(int argc, string[] argv) {
  int x = (1 + (2 * 3));
} return int x;
```

## E0106 a closing bracket nothing opened

A `)` or `]` where an operand belongs closes nothing: the brackets on the statement
do not balance. Either the bracket is one too many, so delete it, or an opening
bracket is missing earlier in the statement.

Incorrect:

```id
main(int argc, string[] argv) {
  int x = (1 + 2));
} return int x;
```

Correct:

```id
main(int argc, string[] argv) {
  int x = (1 + 2);
} return int x;
```

## E0107 an integer literal that does not fit 64 bits

A `word` is 64 bits, so the largest integer literal is `18446744073709551615`,
which is also `0xffffffffffffffff`. A literal with one more bit used to wrap
around without a message and store a different number than the one written, so
it is refused where it is written. The same limit holds for a hex literal of
more than 16 significant digits and a binary literal of more than 64. Leading
zeros do not count.

Incorrect:

```id
main(int argc, string[] argv) {
  word huge = 18446744073709551616;
  print(huge);
} return int 0;
```

Correct:

```id
main(int argc, string[] argv) {
  word huge = 18446744073709551615;
  print(huge);
} return int 0;
```

## E0108 a string escape \x without two hex digits

In a string literal `\xHH` is the one byte whose value is the two hex digits
`HH`: `"\x1b"` is ESC and `"\x41"` is `A`. It is exactly two digits on every
target, so `"\x01aaaa"` is a `\x01` followed by four ordinary `a` characters;
C's own rule reads as many digits as follow, and the compiler writes the literal
so that rule never applies. A `\x` with fewer than two hex digits after it names
no byte, and is refused where it is written. `\x00` is the NUL byte and is
refused for the reason `\0` is (docs/SPEC.md, section 4).

Incorrect:

```id
main(int argc, string[] argv) {
  string s = "a\x4";
  print(s);
} return int 0;
```

Correct:

```id
main(int argc, string[] argv) {
  string s = "a\x04";
  print(s);
} return int 0;
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
structure. A function and its `chain` segments count as one. Move the extra
functions into a new file in the same directory, named for what they do.

Incorrect:

```id
one(int x) {
  int y = x + 1;
} return int y;

two(int x) {
  int y = x * 2;
} return int y;

three(int x) {
  int y = x - 3;
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
  int y = x * 2;
} return int y;

main(int argc, string[] argv) {
  int a = one(argc);
} return int a;
```

## E0204 a chain follows a segment that had room

A `chain` may only follow a segment of exactly 3 actions, not fewer. A segment
that still had room should have kept writing: there is one way to continue a
function, not two. The fix is to move the chain's first statement up into the
short segment until it has 3 actions. If that statement is an `if`/`else` (2
actions) and only one slot is free, pad the segment with `blank`, which is
accepted only in that case.

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

The whole program is one scope: its own tree and every tree it imports. The
standard library is in it too. A name the library also declares has the
library's type, so a variable of yours named like one of the library's and
typed differently is reported at your declaration, with the library's as the
related location. The library's declaration cannot change with your program;
rename yours. A build that loads only the functions it reaches reports the same
pair as one that loads the whole library, because the library's index records
every variable it declares and its type.

```text
app.id:3: error: variable 'n' is declared string here but int in the standard library [E0303]
  at: n
  why: a name must keep one type across the whole program, the standard library included, so that one name always means one kind of value wherever it appears
  help: rename this variable so that it differs from the library's; the library's declaration is the one that cannot change
  related: idstd/core/num.id:12: note: the standard library's declaration, which is int
```

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

## E0310 a parameter with a generated name

A parameter named for how it was made, not for what it holds, carries that
spelling into every caller that reads it. The spellings are `_v` or
`_v<digits>` (what `--fix` names a call it hoists into a local) and the
`ret_i`, `ret_s`, `ret_li` family of return locals. Rename the parameter to what
it holds, in the signature and at every use in the body. A local with such a
name is not reported: it never leaves its function.

Incorrect:

```id
helper(int asset_at_v) {
  int total = asset_at_v + 1;
} return int total;

main(int argc, string[] argv) {
  int n = helper(argc);
} return int 0;
```

Correct:

```id
helper(int asset) {
  int total = asset + 1;
} return int total;

main(int argc, string[] argv) {
  int n = helper(argc);
} return int 0;
```

## E0311 a name with a piece that is not a word

A name is read by people who did not write it. `fb_w` means one thing to its author
and nothing to anyone else; `framebuffer_width` means what it says. Every
identifier the program declares (a function, a parameter, a local, an export, a
conf.id constant, a struct and its fields) is split on `_`, and each piece must be
a word: in `idc/data/words/english.txt` (an English dictionary, one lowercase word
per line) or in `idc/data/words/allowed.txt` (valid names that are not English:
brands and coding terms such as `utf8`, `json`, `wayland`, `ttf`; a line starting
with `#` is a comment). The lookup ignores case. A piece with a digit in it, a
one-letter piece and an empty piece (a leading, trailing or doubled `_`) are never
words unless allowed.txt lists them. File and directory names are not checked.

The check runs only under `idc PATH --word-scan` (use it with `--check`); an
ordinary build does not read either file. It judges each distinct name once and
ends with one line of totals. The fix is to spell out each piece it names, or, if
the piece is a real term the dictionary does not know, to add it to allowed.txt.

Incorrect:

```text
idc app.id --check --word-scan
fb_w(int fb_h) {
  int fb_a = fb_h * 2;
} return int fb_a;
```

Correct:

```text
idc app.id --check --word-scan
framebuffer_width(int framebuffer_height) {
  int framebuffer_area = framebuffer_height * 2;
} return int framebuffer_area;
```

## E0312 a keyword used as a name

A keyword is a whole word that begins a type, a statement or a clause: `int`,
`float`, `string`, `word`, `void`, `if`, `else`, `while`, `return`, `break`,
`export`, `import`, `chain`, `pure` and the rest. A local, a parameter or a
function spelled as one cannot be told from the syntax it shares the word with,
and before this check it went on to the C backend, where `int int;` is the first
place anyone found out. The keywords that begin a test case (`given`, `then`,
`prints`, `eprints`, `calls`, `stdin`, `timeout`), `func` and `struct` say so in
their own messages.

A keyword as one `_` piece of a longer name is a different word and stays
legal: `int_total` and `while_open` are ordinary names.

Incorrect:

```id
main(int argc, string[] argv) {
  int int = 3;
  print(int);
} return int 0;
```

Correct:

```id
main(int argc, string[] argv) {
  int int_total = 3;
  print(int_total);
} return int 0;
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
  int y = x + 3;
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
  int y = x + 3;
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

When the earlier function is in idstd, the project's copy is the one deleted and
every caller calls idstd's. This is the rule working as intended, not a false
positive: a function idstd already has is never written again in a project. If
the project cannot reach idstd's (a freestanding build that does not link the
layer it lives in), report it; the answer is a change to idstd, not a second
copy.

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

## E0406 a function that only forwards to another

A function whose whole body is one call to another function, passing its own
parameters unchanged and in the same order and returning the result, adds a name
to read and a call to follow and says nothing the target does not. Delete it and
call the target at every site that called it; test cases the forwarder carried
move onto the target. Not reported: `main`, a `native`, a function read as a
function value somewhere in the program (it may exist to adapt to a `func(...)`
type), and a function whose signature differs from its target's, which adapts
rather than forwards.

Incorrect:

```id
callee(int x) {
  int y = x * 2;
} return int y;

forwarder(int x) {
  int z = callee(x);
} return int z;

main(int argc, string[] argv) {
  int n = forwarder(argc);
} return int 0;
```

Correct:

```id
callee(int x) {
  int y = x * 2;
} return int y;

main(int argc, string[] argv) {
  int n = callee(argc);
} return int 0;
```

## E0407 functions that differ only in the values of their literals

Two functions with the same signature and the same logic, whose only difference
is the value of a literal (an integer, a word, a float, a string or a
character), are one function written twice. The diagnostic names both places.
Two functions that also agree on every literal are E0402 instead.

What the fix is depends on how much the functions do. When each is more than one
operation on its inputs, the value is the only thing that varies, so it belongs
in a parameter: the help says to keep one function, make each literal that
differs a parameter, and call it from both places.

When each is itself only one operation on its inputs (E0408's shape, with literals allowed: after substituting its locals, one
operator, index, field read or call whose operands are parameters, literals or
`(import NAME)`), a
parameter would only keep a second spelling of that operation. The help then
says to write the expression at each call site of each function and delete both;
a literal that means something is named once as a constant in conf.id, not
passed in.

Incorrect:

```id
add_one(int x) {
  int y = x + 1;
} return int y;

add_two(int x) {
  int y = x + 2;
} return int y;

main(int argc, string[] argv) {
  int a = add_one(argc);
  int b = add_two(argc);
  int c = a + b;
} return int c;
```

Correct:

```id
main(int argc, string[] argv) {
  int a = argc + 1;
  int b = argc + 2;
  int c = a + b;
} return int c;
```

For functions that do more than one operation, the parameter is the fix:

```id
add_by(int x, int step) {
  int y = x + step;
  int z = y * 2;
} return int z;

main(int argc, string[] argv) {
  int a = add_by(argc, 1);
  int b = add_by(argc, 2);
  int c = a + b;
} return int c;
```

## E0408 a function that is one operation on its inputs

A function that is only one operation on its parameters is a second spelling of
that operation: `cell(string[] xs, int i) { string v = xs[i]; } return string v;`
is `xs[i]` under a name every reader has to open to learn it is nothing more.
The call site should write the operation itself. It is the family of E0403 (a
function that only returns a constant), E0406 (a pure forwarder) and E0407.

A function with a body, other than `main` and a native, is reduced by
substituting each local into the expression that uses it. The leaves are
parameters and `(import NAME)`. Every other node is one operation: an operator,
an index or field read, a call to any function or builtin, a list literal. The
function is reported when all of these hold:

- the reduced expression is exactly one operation;
- no operand is a literal (`xs[0]`, `x + 1` and `f("a", x)` are not reported: a
  literal is a value that deserves a name, which a constant in conf.id gives it
  without a function);
- nothing reads the function as a function value, in a function body or in a
  case (`bind(f, 3)`);
- it is not a test fixture: not named by a `given` or a `then` of any case
  (`then CHECK(LIT, ...)` included), and not a helper that only such fixtures
  call;
- its name is not one the runtime provides: a function named for a builtin or a
  runtime routine (the reserved names, and `eprint`) is the freestanding
  implementation of it, as `poke8(word a, word v) { st8(a, v); } return void;`
  is in `idc/runtime`, and generated code calls it by that fixed name, so there
  is no call site to write the expression at.

A function with an `if`, `while` or `chain`, with a local that is unused or used
twice, with an assignment, or with any statement that is no part of the one
expression is never reported. Neither is one with a local that converts, such as
`word aw = a;` or `int x = w;`, since the declared type is the point of it. The
report says VALUE (the function returns the expression) or VOID-CALL (a void
function whose only statement is a call).

The fix is to write the expression at each call site and delete the function,
moving its cases to a caller that still pins the behaviour. The scan runs after
every other check has passed, so a program with another error reports that
first.

Incorrect:

```id
cell(string[] xs, int i) {
  string v = xs[i];
} return string v;

main(int argc, string[] argv) {
  string a = cell(argv, 0);
} return int 0;
```

Correct:

```id
main(int argc, string[] argv) {
  string a = argv[0];
} return int 0;
```

## E0409 an operation that cannot change its value

An operation whose result is always the value it was given is padding: it looks
like work, hides the real expression from the reader, and leaves the code doing
exactly what it did without it. The cases it is reported for are these, each an
`int` operation (a float `x + 0.0` is left alone, since it turns `-0.0` into
`0.0`):

- `e + 0`, `0 + e` and `e - 0`;
- `e * 1`, `1 * e` and `e / 1`;
- `e * 0` and `0 * e`, a product with a literal zero: it is `0` whatever `e` is, so
  `x + 0 * (y)` never depends on `y`;
- `- (- e)`, a negation of a negation;
- a sum in which a term is added and subtracted again, as `a + b + b - b`: the
  sum is flattened through its `+` and `-` into signed terms, and two terms with
  opposite signs that are the same expression cancel, in whatever order they were
  written (`b + a - b` too). A term that contains a call is never the same as
  another, because a call may have an effect.

`0 - e` and `1 / e` are not reported: they are not `e`. A constant from conf.id
that happens to be 0 or 1 is not a literal, so `x + (import offset)` is not
reported either. A `+` chain that contains a string literal is string
concatenation, not a sum, and is left alone: `"built " + n + 0` appends the digit
`0`, and `"left " + (a - b)` is not one sum with the text. (A chain of strings
with no literal in it, such as `name + 0` for a string `name`, cannot be told
from an `int` sum without types and would be reported.)

It is an error whatever the reason it was written. The usual reason is another
rule: E0408 refuses a function that is one operation on its inputs, and writing
`x + y + 0` makes the function "two operations" without making it anything else.
That is not the fix for E0408 (write the expression at the call site), and a
rule that pushes anyone to write it needs a different fix, which is worth
reporting rather than working round.

The report names the function, the operation and which shape it is. The fix is
to remove the operation.

Incorrect:

```id
main(int argc, string[] argv) {
  int n = argc + 0;
} return int n;
```

Correct:

```id
main(int argc, string[] argv) {
  int n = argc;
} return int n;
```

## E0410 a local that is declared and never read

A local that is declared and then never read is dead weight: every reader has to
find out that nothing uses it. Reading it means appearing as a variable in an
expression after its declaration, up to the end of its function -- a condition,
an argument, the right side of an assignment, an index, the return clause.
A local that is assigned after its declaration (`x = f(y);`) is not reported
either: the assignment is how a call's result is taken and ignored, and the call
is the point. An exported local (`export int
name = ...;`) is read by other functions as `(import name)`, so it is never
reported, and neither is a parameter or a constant from conf.id.

Only a local given an expression that does nothing is reported: operators over
variables, literals and `(import NAME)`. A local given a call, or an index (which
traps when it is out of range), is how a function that returns a value is run for
its effect -- `int r = init_ir();` -- and dropping the declaration would drop the
effect, so it is not reported.

The usual reason for such a local is a rule worked round: `int pad = dt;` added so
that a function has "more than one statement". If a rule made you add it, that
rule needs a different fix -- report it. The fix for the local itself is to remove
the declaration.

Incorrect:

```id
main(int argc, string[] argv) {
  int pad = argc;
  int n = argc + 1;
} return int n;
```

Correct:

```id
main(int argc, string[] argv) {
  int n = argc + 1;
} return int n;
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
  int s = a + b + 1;
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
  int s = a + b + 1;
} return int s;
(1, 2):(4)
(0, 0):(1)

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
  int s = a + b + 1;
} return int s;
(1, 2):(4)
(1, 2):(4)

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
  int s = a + b + 1;
} return int s;
(1, 2):(4)
(0, 0):(1)

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
  int s = a + b + 1;
} return int s;
(1):(1)
(0, 0):(1)

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
  int s = a + b + 1;
} return int s;
(1, 2):(4)
(0, 0):(1)

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
  int s = a + b + 1;
} return int s;
(1, 2):(3, 4)
(0, 0):(1)

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
  int s = a + b + 1;
} return int s;
(1, 2):(4)
(0, 0):(1)

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

## E0607 a constructor's argument is a call

`Point(1, 2)` builds a struct on a line of its own, where the next line can see
what it is. Its arguments are the same: values already named, a literal, a field
read, a list literal or an operation on names. A call in one, whether a function
or a builtin such as `len`, is a second action hiding inside the first, and the
reader of the next line cannot see what the struct was built from. It is the
constructor's own form of the call-nesting rule (docs/SPEC.md, section 7.1), one
step stricter: a function's argument may hold one level of call, a constructor's
may hold none.

A function that exists only to build a struct (`point_new(int x, int y)` that is
only `Point p = Point(x, y);`) is not the fix: it is E0408, one operation on its
inputs. Declare the value first, then build the struct.

Incorrect:

```text
// main.id
main(int argc, string[] argv) {
  Point p = Point(1, len(argv));
} return int 0;

// point.id
struct Point {
  int x;
  int y;
}
```

Correct:

```text
// main.id
main(int argc, string[] argv) {
  int count = len(argv);
  Point p = Point(1, count);
} return int 0;

// point.id
struct Point {
  int x;
  int y;
}
```

## E0608 an integer literal does not fit the int it is stored in

An `int` is 32 bits, from -2147483648 to 2147483647. A literal outside that
range is a `word` (docs/SPEC.md, section 2), and a declaration or an assignment
may narrow a `word` to an `int`, but a literal is the one value whose size is
known on the line: `int big = 3000000000;` would keep only the low 32 bits and
print -1294967296, with nothing to say a number had been dropped. The literal
`-2147483648` is fine, since it is the lowest `int`; `-2147483649` is not.

Incorrect:

```id
main(int argc, string[] argv) {
  int big = 3000000000;
  print(big);
} return int 0;
```

Correct:

```id
main(int argc, string[] argv) {
  word big = 3000000000;
  print(big);
} return int 0;
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

## E0801 a pure function writes an export

A function marked `pure` promises that its result depends on its arguments alone
and that calling it changes nothing the rest of the program can see
(`docs/SPEC.md`, "Pure functions"). An `export` declaration is how a function
assigns an export, and an export is state every function can read, so a pure
function has none. Return the value and let the caller store it, or remove `pure`.

Incorrect:

```id
pure bump(int x) {
  export int counter = x;
} return int x;

main(int argc, string[] argv) {
  int r = bump(1);
} return int r;
```

Correct:

```id
pure bump(int x) {
  int y = x + 1;
} return int y;

main(int argc, string[] argv) {
  export int counter = bump(1);
} return int 0;
```

## E0802 a pure function calls a builtin that does I/O or reads state

A pure function may call only the builtins `len`, `push`, `pop`, `to_int`,
`charat`, `chr`, `str_sub`, `udiv`, `umod`, `ult` and `ushr`. `print`, `put`, `flush`,
`eprint`, `input`, `read_all`, `getkey`, `sleep_ms` and `ticks` do I/O or read the
clock, and `alloc`, `store_size`, `peek*`, `poke*`, `str_of_mem` and `mem_of_str`
read or write the flat store, which holds state that is not an argument. Do the
call in the caller and pass the result in, or remove `pure`.

Incorrect:

```id
pure shout(int x) {
  print(x);
} return int x;

main(int argc, string[] argv) {
  int r = shout(1);
} return int r;
```

Correct:

```id
pure shout(int x) {
  int y = x + 1;
} return int y;

main(int argc, string[] argv) {
  int r = shout(1);
  print(r);
} return int 0;
```

## E0803 a pure function calls a function that is not pure

Whatever a callee writes or prints is an effect of the caller, so a pure function
may call only functions marked `pure` and natives declared `pure native`. A native
is impure unless its declaration says otherwise, because the compiler cannot see
its C. Mark the callee `pure` and fix what it then reports, or stop calling it.

Incorrect:

```id
inner(int x) {
  int y = x + 1;
} return int y;

pure outer(int x) {
  int y = inner(x) * 2;
} return int y;

main(int argc, string[] argv) {
  int r = outer(1);
} return int r;
```

Correct:

```id
pure inner(int x) {
  int y = x + 1;
} return int y;

pure outer(int x) {
  int y = inner(x) * 2;
} return int y;

main(int argc, string[] argv) {
  int r = outer(1);
} return int r;
```

## E0804 a pure function reads an export that a function writes

A pure function may read an export only when it is a constant of `conf.id`, which
is built before `main` and never assigned again. Any other export is assigned by
some function, and a read of it makes the result depend on when it ran. Pass the
value as a parameter, or declare it in `conf.id`.

Incorrect:

```id
setup() {
  export int level = 3;
} return void;

pure peek_it(int x) {
  int y = x + (import level) + 1;
} return int y;

main(int argc, string[] argv) {
  setup();
  int r = peek_it(1);
} return int r;
```

Correct:

```id
setup() {
  export int level = 3;
} return void;

pure peek_it(int x, int lv) {
  int y = x + lv + 1;
} return int y;

main(int argc, string[] argv) {
  setup();
  int r = peek_it(1, (import level));
} return int r;
```

## E0805 a pure function calls a function value that is not a pure parameter

A call through a function value runs a function the compiler cannot see from the
call, so a pure function may make one only through a parameter declared
`pure func(...) return ...`, which obliges every caller to pass a pure function.

Incorrect:

```id
pure apply(func(int) return int f, int x) {
  int y = f(x) + 1;
} return int y;

pure inc(int x) {
  int y = x + 1;
} return int y;

main(int argc, string[] argv) {
  int r = apply(inc, 1);
} return int r;
```

Correct:

```id
pure apply(pure func(int) return int f, int x) {
  int y = f(x) + 1;
} return int y;

pure inc(int x) {
  int y = x + 1;
} return int y;

main(int argc, string[] argv) {
  int r = apply(inc, 1);
} return int r;
```

## E0806 a pure parameter is given a function that is not known to be pure

A parameter declared `pure func(...) return ...` promises the callee that whatever
it calls through the parameter writes no export and does no I/O. The compiler
checks that where the function is a name: at every call, the argument has to be
the name of a function marked `pure`, or a pure parameter of the caller. A local or
an export that holds a function value is refused, because what it holds is decided
where it is assigned.

Incorrect:

```id
pure apply(pure func(int) return int f, int x) {
  int y = f(x) + 1;
} return int y;

inc(int x) {
  int y = x + 1;
} return int y;

main(int argc, string[] argv) {
  int r = apply(inc, 1);
} return int r;
```

Correct:

```id
pure apply(pure func(int) return int f, int x) {
  int y = f(x) + 1;
} return int y;

pure inc(int x) {
  int y = x + 1;
} return int y;

main(int argc, string[] argv) {
  int r = apply(inc, 1);
} return int r;
```

## E0807 `pure` is not before a function type

`pure` is written before a function's name, before `native`, and before a
parameter whose type is a function type, where it says that the function a caller
passes is pure. Before any other type it promises nothing, so it is refused.

Incorrect:

```id
pure id2(pure int x) {
  int y = x;
} return int y;

main(int argc, string[] argv) {
  int r = id2(1);
} return int r;
```

Correct:

```id
pure id2(int x) {
  int y = x;
} return int y;

main(int argc, string[] argv) {
  int r = id2(1);
} return int r;
```

## Retired codes

A retired code is no longer emitted, has no section above, and is never reused for
another diagnostic.

| Code | Was | Retired because |
| --- | --- | --- |
| E0701 | a directory holds more than three entries | a directory has no entry limit; the 3-functions-per-file limit (E0203) stays |
