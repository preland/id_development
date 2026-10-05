# Starting a project

> **Status: current.** Every command and every error message below was run
> against this tree on the date of the last commit to touch this file. If one
> does not reproduce, that is a bug in this document.

[`TUTORIAL.md`](TUTORIAL.md) teaches the *language* — it writes one program,
`demos/wordcount`, and explains why `id` makes you spread it out. This document
is the other half: the *project*. How a directory becomes a program, where the
binary goes, what a `conf.id` is for, how the standard library gets in, what
happens when you need something the language does not have, and — mostly —
what goes wrong at each of those steps and what the compiler says when it does.

Read `TUTORIAL.md` first if you have never written `id`. Read this when you are
about to start something of your own.

The worked example is a Caesar cipher: text in on stdin, shifted text out.
It is small enough to fit here and large enough to hit six of the traps.

---

## 1. One file

Start with a single file. `idc` takes exactly one path, and a `.id` file is a
valid one.

```
// caesar.id
main(int argc, string[] argv) {
  string text = read_all();
  int i = 0;
  string out = "";
  while(i < len(text)) {
    out = out + shift_one(charat(text, i));
    i = i + 1;
  }
  print(out);
} return int 0;
```

```sh
idc/bin/idc caesar.id --allow-untested -o caesar
```

Every build in this document passes `--allow-untested`. The compiler requires
two test cases per function (§9), and neither this program nor the standard
library it merges has them all yet; the flag is the way to build anyway, and
it says nothing about it -- `id` has no warnings, only errors.

Two errors, and they are worth reading in order:

```
caesar.id:1: error: a block in 'main' performs 5 actions; the limit is 3 (each statement, if, else, and while is one action; return is free) [E0201]
  |
1 | main(int argc, string[] argv) {
  |
  = why: a block that does more than three things is hard to read and to test at a glance, so the language caps it; ...
  = help: continue the function into a chain: end this segment with `} chain (same parameters) {` and write the remaining statements after it ...
caesar.id:6: error: no such function 'shift_one' [E0304]
  |
6 |   string s = shift_one(charat(text, i));
  |              ^^^^^^^^^
  = why: a call names a function this program defines, a builtin, or a function of the standard library, and nothing by this name is any of them
  = help: check the spelling of 'shift_one', or define it as a function; the builtins are: print, input, read_all, len, ...
```

Each diagnostic is a head line (`FILE:LINE: error: MESSAGE [CODE]`), the source
line with a caret under what it names, and why and help lines; `idc --explain
E0201` gives the long explanation (`docs/ERRORS.md`), and `--diagnostics=json`
gives one JSON object per diagnostic (`docs/DIAGNOSTICS.md`).

The first is the rule everyone meets first. The second is the last one to fix —
`shift_one` genuinely does not exist yet.

**The second rule is about nesting.** `shift_one(charat(text, i))` above is
accepted: **a call's argument may hold one level of call.** A call inside a call
is fine; a call inside a call inside a call is an error (SPEC §7.1), and the
inner result gets a name:

```
shift_one(charat(text, i))         fine -- one level down
shift_one(prev(charat(text, i)))   rejected -- two levels

int c = charat(text, i);
string s = shift_one(prev(c));     the same thing, said in two steps
```

This is not the 3-action rule in disguise; it is separate, and it is one of the
things that most changes how `id` code looks. Expect a named temporary now and
then, where you would have nested twice. `demos/fsdemo/end/cleanup.id`
explains the other reason it is a good idea anyway: operands of one expression
are not ordered, so two calls in one expression can run in either order.

> **Pitfall 1.** A call's argument may hold one level of call, not two. Name
> the value first when it would be a second.

## 2. A directory is a program

Fixing the above means more functions than fit in a file, which means a
directory. A project is a *tree*, every `.id` file in it is compiled together,
and calls resolve across all of them with no imports between your own files.

```
caesar/
├── main.id     main, rotate, rotate_loop
└── shift.id    rotate_step, shift_one, shifted
```

```
// caesar/main.id
main(int argc, string[] argv) {
  string text = read_all();
  string out = rotate(text);
  print(out);
} return int 0;

rotate(string text) {
  string s = "";
  int i = 0;
  s = rotate_loop(text, i, s);
} return string s;

rotate_loop(string text, int i, string s) {
  string r = s;
  while(i < len(text)) {
    r = rotate_step(text, i, r);
    i = i + 1;
  }
} return string r;
```

```
// caesar/shift.id
rotate_step(string text, int i, string r) {
  int c = charat(text, i);
  string out = shift_one(c);
  r = r + out;
} return string r;

shift_one(int c) {
  string out = chr(c);
  if(chr_is_lower(c) == 1) {
    out = shifted(c, 97);
  } else if(chr_is_upper(c) == 1) {
    out = shifted(c, 65);
  }
} return string out;

shifted(int c, int base) {
  int off = c - base + 3;
  int m = off - 26 * (off / 26);
  string out = chr(m + base);
} return string out;
```

```sh
idc/bin/idc caesar --allow-untested
printf 'Attack at dawn!\n' | ./build/caesar
Dwwdfn dw gdzq!
```

Two things happened that were not asked for.

**The binary went to `build/`.** With no `-o`, the output is named after the
project directory and written into `build/`, which is `.gitignore`d — built
binaries never land in the source tree. `-o` overrides both: `-o /tmp/caesar`.
That makes `build/` at a project's root **output, never source**: nothing under
it is compiled and it does not count toward the 3-entry limit, so a tree that
has been built in place compiles exactly as a clean one does. Do not put `.id`
files there.

**`chr_is_lower` and `chr_is_upper` were never defined.** They are `idstd`'s,
and `idstd` is in every build already. See §4.

## 3. The limits, and when they bite

A file holds **at most 3 functions**. A directory holds **at most 3 entries**,
counting `.id` files and subdirectories together. The second is the one that
interrupts you, because it triggers on a directory you were not editing:

```
caesar: error: a project directory may contain at most 3 files and directories
  combined, but this one has 4 (.id files and subdirectories); split it into
  subdirectories
```

The fix is always the same shape — push a pair of files down a level and name
the level after *the stage of work*, not the data type:

```
caesar/
├── conf.id
├── main.id
└── shift/
    ├── shift.id
    └── more/
        └── tail.id
```

The *function* limit has a second remedy, and often the better one. A function
that has run out of actions can continue into a `chain` instead of handing the
rest of its work to a helper:

```
parse_line(string src, int i) {
  int a = skip_space(src, i);
  int b = read_word(src, a);
  int c = skip_space(src, b);
} chain (string src, int i) {
  int d = read_word(src, c);
} return int d;
```

Each segment gets its own three actions, the parameters are restated exactly as
written the first time, and everything the earlier segments declared is still in
scope. A function and its chains count as **one** function against the file's
three — so continuing does not push a file over the limit, while splitting out a
helper does. Reach for a chain when the next step is only ever used here, and
for a real function when it is worth a name a caller elsewhere could use.

Occasionally the next step *cannot* be moved up. An `if`/`else` is one statement
costing two actions — one for the `if`, one for the `else` — so a segment with a
single slot left can neither hold it nor be continued by a chain, because a
chain may only follow a segment that used all three. `blank` is the way out: a
statement that takes an action slot and does nothing.

```
classify(int n) {
  int lo = n - 1;
  int hi = n + 1;
  blank;
} chain (int n) {
  if (n > 0) {
    print(hi);
  } else {
    print(lo);
  }
} return void;
```

`blank` is accepted only where it is needed — a chain must follow, and that
chain's first statement must be too large to have been written in the slot the
`blank` occupies. Pad a segment anywhere else and the compiler rejects it,
because the padding is standing where real work belonged.

Plan for this. A project that will have twelve functions needs three levels,
and deciding what the levels *mean* early is much cheaper than renaming them at
the point the compiler forces the issue. If you find yourself making a
directory called `utils/` you have already lost — it will fill up in a week and
tell you nothing.

**A directory may not have the same name as its parent directory.** Names like
`engine/engine/` or `parse/parse/` are rejected: the inner directory says
nothing about why it exists or what it holds. Name it after the stage of
processing or the concept it groups, not the root. `engine/opt/` (optimization),
`parse/emit/` (code emission), or `engine/debug/` say what the directory holds.

**A file may not have a generic name.** Names like `helper.id`, `util.id`,
`misc.id`, `common.id`, `stuff.id`, or `temp.id` are rejected. These names do
not indicate what the file holds, making it impossible to name what you are
importing and encouraging developers to dump unrelated functions into a single
file. Name the file after what it contains: `arith_helper.id` for arithmetic
helpers, `string_util.id` for string utilities, etc.

**An entry may not be a numbered copy of its sibling.** In one directory, a
name that is another entry's name followed by digits is rejected --
`chunk2.id` beside `chunk.id`, `pane2/` beside `pane/`, and `x_2.id` beside
`x.id` all name the same thing twice instead of saying what the second one
holds:

```
a: error: file 'a/chunk2.id' is a numbered copy of 'a/chunk.id'; name it for
  what it holds
```

Two numbered entries with no un-numbered sibling -- `x2.id` beside `x3.id`,
with no `x.id` -- are rejected too, as numbered siblings of each other:
neither is more "the real one" than the other. An entry with digits but no
sibling that strips to the same stem, like `md5.id` or `d3/` alone, is fine.

**A file may not have the same name as its own directory.** `a/loop/loop.id`
is rejected the same way `engine/engine/` is: the file says nothing the
directory didn't already say.

```
a: error: file 'a/loop/loop.id' has the same name as its directory; name it
  for what it holds
```

This does not apply to a file directly in the project's own root --
`caesar/caesar.id` is fine -- because the root's name is just where the
project was checked out, not a level of the tree it wrote.

> **Pitfall 2.** The entry limit fires on a directory you did not touch, at the
> moment you add one file. Leave room. Name directories and files for what they
> hold, not their data type or role in the project.

**Dead code is still checked.** A function nothing calls is not emitted, but it
still obeys every rule:

```
caesar/dead.id:1: error: a block in 'never_called' performs 4 actions; the
  limit is 3 ...
```

That is deliberate — code that stopped being checked because nothing called it
is how a library rots.

### Decomposition warnings

Two more things are reported, but a build with one still succeeds — they are
**warnings**, `FILE:LINE: warning: ...` on stderr, both from a normal build and
from `--check`. Each is a shape the 3-action and 3-function limits produce
often enough, once code is split to fit them, that it is worth naming rather
than leaving for a reader to notice by hand.

**A pure forwarder** — a function whose body is exactly one statement that
calls another function with its own parameters, all of them, unchanged, in
the same order, and returns that call's result (or returns void right after):

```
helper.id:5: warning: 'forwarder' only forwards to 'callee'; call 'callee' directly
```

The fix is to delete `forwarder` and call `callee` at every site that used to
call it. Not reported: `main`; a `native`; a function whose name is also read
as a function value elsewhere in the unit (it may exist only to adapt to a
`func(...)` type there); and a forwarder whose signature does not match its
callee's — it narrows, widens or drops a parameter, which is adapting, not
forwarding.

**A generated parameter name** — a parameter whose name ends in `_v` or
`_v<digits>` (the name `--fix` gives a call it hoists into a local, above) or
matches this compiler's own `ret_i`/`ret_s`/`ret_li`/... return-local
convention:

```
helper.id:1: warning: parameter 'asset_at_v' of 'helper' has a generated name; name it for what it holds
```

the parameter carries a mechanically-generated spelling into every caller
that reads it, rather than a name chosen for what the value is. A local
named this way is not reported — it never leaves the function, so it costs a
reader nothing. Measured across idstd, 8 of its own public functions forward
a `--fix`-hoisted local this way (`lset`'s `idstd_v` being the one every
program calls); that is a real instance of the same question the exclusions
above ask for the other two warnings — is the public name worth carrying, or
should the library rename the parameter — left to a human rather than
decided by the checker.

### Two functions that read different imports

Not a warning: an **error**. Two functions whose logic is identical except for
a single imported value — one reads `(import ia)` where the other reads
`(import ib)`, and everything else is the same up to the spelling of their own
variables — are one function written twice, with the value as the parameter it
should have been:

```
work.id:11: error: function 'use_b' and 'use_a' (defined at work.id:6) differ only in the imported value they read ((import ib) in one, (import ia) in the other); parameterise one function and pass the value in -- replace the import with a parameter, call that one function from both places, and delete the other
```

The pair is found from the duplicate-logic fingerprint (`mid/form/unique/`),
which writes an import as the position at which the function first read it
and keeps the names beside the text, so a different name is a different
function there and the same text with one name different is this error. It
says nothing when anything else differs (a literal, a callee, a second
import), when more than one import differs (that is two values to
parameterise). A function of one statement is no exception: `s1_of` was
`ns1[id]` and `s2_of` `ns2[id]`, and the fix is the same -- there is no named
accessor of a module's global, the call site reads `(import ns1)[id]` itself,
and a test states a global's state with `then (import NAME)`, or a field of a
struct global with `then (import NAME).field` (docs/TESTS.md), or, where that
is refused, with one check function that states the whole state. Two
functions identical in every way, imports included, are still the
duplicate-logic error.

A difference only in a literal is never reported, by an error or a warning. A
named accessor, a fixture or a message per constant is how `id` is written; a
literal-only pair that is really one function (the byte-range predicates of
`idstd`, the cube's three axes) is fixed by writing it once, not by a check.

### Every rule at once: `--check` and `--fix`

```sh
idc/bin/idc caesar --check --allow-untested
```

runs the lexer, the parser and every rule over the tree and stops: no C, no
`cc`, no test cases, no link. It prints exactly what a build prints before it
emits anything, and exits 1 if there was a diagnostic. On a tree that breaks
rules a build stops there too, so the two take the same time; on one that
does not, `--check` skips the rest — 9 s against 14.5 s for the compiler's
own parser, 0.15 s against 1.5 s for `demos/solitaire`.

```sh
idc/bin/idc caesar --fix --allow-untested
```

rewrites the tree's own `.id` files — not a dependency, not the standard
library — where a violation has exactly one mechanical repair that cannot
change what the program does:

| violation | what `--fix` writes |
| --- | --- |
| a call two levels deep in a call's argument | the inner call as a new local just before the statement, `<callee>_v`, and the name in its place |
| an argument that is not itself a call but has a call two levels deep inside it | the whole argument as a new local, `<callee>_a0` (`_a1`, ...) for the callee it is an argument of, and the name in its place -- not one local per call inside it |
| a return clause that is not a name or a literal | the value as the body's last statement, `ret_i` (`ret_s`, `ret_w`, `ret_li` ...), returned by name |
| an argument that narrows (`word` to `int`) | a local of the parameter's type, which converts exactly as the argument would |
| a comparison beside a bare bitwise operator | the parentheses the diagnostic names |

It prints each edit as `FILE:LINE` with the lines before and after, then each
violation it refused and why, then what is left by kind. A second run makes no
edit.

What it keeps, and what it refuses:

- **Order.** Operands and arguments run left to right (SPEC §7). When a call
  has to be named, every other call, division or shift evaluated before it
  moves too, in order, since a name bound early must not skip past one:
  `bump(c) * 10 + twice(bump(c))` becomes two locals, not one. An index read
  or an `import` evaluated before it moves only when some call that also
  moves could write (`fix/plan/decide/touch/`) — otherwise it is read exactly
  where it stood, and reads whatever the calls before it left there, same as
  before the rewrite. The accepted cost: two reads that would both trap may
  now report in a different order than they did before `--fix`.
- **A `while` condition, the right of `&&` or `||`, an `else if` condition.**
  Refused: a name bound first would run when the original did not, or only
  once. The composition wants a function.
- **Names.** A new name is free across the unit — no function, export or
  builtin by that name, not declared in the function, and not a different type
  anywhere in the unit — so `len_v` may become `len_v2`. In a tree whose every
  local carries the `idstd_` prefix, or the standard library itself, new names
  carry it too.
- **The action limit.** A name is a statement, so a block can go over 3. The
  edit is still made and the limit reported, because splitting a block is a
  design decision and the named steps are what a person splits.

Everything else — the limits, constant functions, type errors — is left as it
is and listed.

## 4. The standard library is already there

`idstd` is imported by default. You do not name it, and you did not above:
`chr_is_lower` resolved because the library is in every build. It is found
from, in order, `--std DIR`, `$IDSTD_HOME`, then an `idstd` directory beside
this repository.

```sh
idc/bin/idc caesar --allow-untested --no-std      # build without it
idc/bin/idc caesar --allow-untested --std ../idstd
```

The habit to build is: **before writing a small helper, assume `idstd` has
it.** It has about 128 functions — `fx_min`, `fx_max`, `str_split`, `lst_sort`,
`chr_is_digit`, `fmt_int`, `lset`. If you write your own anyway:

```
caesar/mine.id:1: error: function 'chr_is_lower' already defined at
  /home/you/git/idstd/core/text/atom/chr/range.id:28
caesar/mine.id:4: error: cannot assign a int value to string 'r'
caesar/mine.id:6: error: function 'chr_is_lower' returns int but the expression
  has type string
caesar/mine.id:1: error: variable 'c' is declared twice in function
  'chr_is_lower'
```

**Only the first line is the problem.** The other three are the type checker
reading your function through the library's signature for the same name. This
is the general shape of `id` diagnostics and the most useful habit in this
document: **fix the first error and rebuild.** Do not work down the list.

> **Pitfall 3.** One real error produces a cascade. Read the top line only.

**The other direction is a rule too: a function written in two projects moves
into `idstd`.** Once the same function exists in any two projects, for any
reason — copied, vendored, or written twice independently — it is added to
`idstd` with its cases, and every project deletes its copy and calls the
library's. Two copies drift apart, and a reader can no longer tell which one a
call means. The compiler cannot see across projects, so this is found with
`idc/tools/dupscan.sh`, listing each project root separately:

```sh
idc/tools/dupscan.sh "$PWD/demos/moonbuggy" "$PWD/demos/solitaire" "$PWD/../idstd"
```

Run it whenever a change touches more than one project.

### The library is loaded by use

The library is in every build, but a build parses, checks and compiles only the
part of it your program reaches. A four-line program does not pay for two
thousand functions, and a library ten times the size would not change what it
costs. What this means in practice:

- **What is reached.** Every identifier in your program names something: a
  call, a function value, an export you `import`, a constant, a type. The
  library functions those names are, and whatever their bodies reach in turn,
  are loaded. The rest of the library is not read. A name you *write* is an
  identifier too, so a function, variable or constant of yours that shares a
  name with a library one loads that one, and the ordinary "already defined"
  error is what you see, exactly as before.
- **What is still checked against all of it.** A program may not repeat a
  library function's body without calling it, so the library hands the
  compiler an index of every function it did not load: its fingerprint and the
  imports it reads. A function of yours that does what a library function does
  is rejected with the same words whether or not you call the original, and
  the diagnostic is on whichever of the two the build reads second
  (`mid/names/symbols/check/conflict/more/core/ext/`).
- **What is not checked.** An error inside a library function nothing of
  yours reaches — a type error, a rule broken, a case that fails — does not
  fail your build. It fails the library's own: `idc idstd` builds the whole
  library as a project, and `idstd/run.sh whole` is that build. The cases of
  the library functions you *do* reach are run for you, once per change of
  those functions, and a failure is reported as the library's, never yours.
- **The cost, and what is cached.** The first build after the library changes
  reads each changed file once and keeps what it found, under the file's
  content hash, in `$CACHE/stdidx` (override with `IDC_STD_IDX_DIR`). A file
  that did not change is not read again, and one that only moved is not read
  at all. A build that reaches the same functions of an unchanged library
  re-parses nothing of it.
- **Seeing it.** `IDC_TIMES=1` prints how many library functions the build
  loaded, and the wall time at each stage of it (`planned` is the end of reading
  the project and the library's index, `frontend` the end of the parse).
- **Switching it off.** `IDC_STD_FULL=1` merges the whole library as it did
  before, for a diagnosis or a comparison. So do `--fingerprints`, `--calls`,
  `--list-untested`, `--fix` and `--emit-sources`, a program that lives inside
  the library's own tree (the suites under `idstd/.tests`), and a library the
  index cannot describe — one with a syntax error, an `asm` declaration, a name
  defined twice, or a `conf.id` line that is not one constant.

The emitted C is the same whichever way the library is merged, up to three
things. A whole merge prints an empty `/* exported variables */` comment when
the program reaches no export of the library. A local that is passed to a
library function is freed at the end of its function more often, because the
analysis that decides it treats a function a test case names in `then calls`
as one that keeps its arguments, and the library's own cases are no longer in
the build. And a project with no `main` (§6) holds the library functions it
reaches rather than every function of the library, which is what a library
object linked into a program wants.

### The trap with no line number of its own

Two `idstd` modules hold state, and state in `id` is an `export` inside a
function body — so the global does not exist until that function has run.
Calling `fx_sin` without calling `fx_trig_init` first used to be a segfault.
It is now caught:

```
idstd/core/math/trig/tab.id:39: error: 'fx_sintab' is exported by
  'fx_trig_init', which nothing calls -- an export is initialised when its
  declaring function runs, so this reads an uninitialised global. Call
  'fx_trig_init' from main's setup chain
```

The fix is one line at the top of `main`:

```
main(int argc, string[] argv) {
  fx_trig_init();
  int v = fx_sin(90000);
  print(v);
} return int 0;
```

```sh
./build/trig
1000
```

(`fx_sin` takes degrees scaled by 1000, so 90 degrees is `90000` and the result
`1000` is 1.0 at the same scale. `idstd` is fixed-point throughout; there is no
float mirror yet.) The same applies to `err_init`. If you write a module of
your own that exports state, it inherits the same obligation.

> **Pitfall 4.** An `export` is a statement, not a declaration. Anything that
> holds state needs its initialiser called from `main`.

## 5. `conf.id`: what the project depends on, and what it holds constant

The shift is hard-coded as `3` above. A project's **root** may carry a
`conf.id` naming the trees it depends on and then the constants it is built
with:

```
// caesar/conf.id
int rot = 3;
```

```
// caesar/shift/...
int off = c - base + (import rot);
```

```sh
idc/bin/idc caesar --allow-untested && printf 'Attack at dawn!\n' | ./build/caesar
Dwwdfn dw gdzq!
```

Change the one line to `int rot = 13;`, rebuild, and nothing else moves:

```
Nggnpx ng qnja!
```

A constant is an ordinary exported global that needs no function of the
project's own to initialise it — a scalar is emitted at file scope with its
value attached, so it holds it before `main` runs; a list is built by the
compiler's own generated code, the first thing every entry point runs (below).
Either way it is exactly what §4's `export` cannot promise: readable from
`main`'s first statement on, with nothing the project wrote required to make
that true. Two rules follow from "ordinary exported global":

```
caesar/clash.id:2: error: 'rot' is an exported global (by 'conf.id'); another
  variable cannot reuse that name -- read the global with 'import rot'
```

and imports must come before constants; an `import` after one is an error.

This is also the only place a constant can live. A function whose whole job is
to return one -- `rot() { } return int 3;` -- is rejected with the declaration
to write here instead (`docs/SPEC.md` §7.2).

A constant whose type is a list (`int[]`, `string[]`, etc.) is allowed too:

```
string[] names = ["a", "b", "c"];
```

A list has no constant form in C or LLVM -- building one allocates, which is
work, and work runs in a function -- so the declaration still holds no
initialiser at file scope. Every kept list constant is instead built by one
function, `idc_const_init`, that every entry point calls before anything else
runs: `id_main`'s first statement on every target, hosted or freestanding, and
a test case's first statement in the harness, since each case is a process of
its own. The declaration order in conf.id is the build order.

A constant is only emitted if the code that is emitted reads it, exactly as a
function is only emitted if it is reachable: a library can keep a large table
of constants in its `conf.id` and a program that reads none of them pays for
none -- not a global, and for a list not a line of the start-up initialiser. A
constant read only by a list constant's initialiser is kept for that reason. A
project with no `main`, and a `--freestanding` build, keep every constant, as
they keep every function. The constants are still parsed and type-checked
whether or not they are emitted.

A scalar constant may be initialised from an earlier scalar constant,
`int b = (import a);`. A file-scope initialiser has to be a constant
expression, and a read of another global is not one, so the parser replaces the
import with `a`'s own initialiser: `b` is built as if it had been written
`int b = <a's initialiser>;`. A case that reads `b` is still keyed on `a`'s
tokens. Only a bare `(import a)` is folded: `int b = (import a) + 1;` still
reaches the C compiler as a non-constant initialiser and fails there. A list
element may read a constant either way, because a list is built in
`idc_const_init`.

A conf.id list constant is still a constant: it is locked once built, and
mutating it -- `push`, `pop`, or an index-assignment, whether directly or
through an alias -- traps (`docs/SPEC.md` §8). Writing through `(import
names)` directly is caught at compile time, naming the constant:

```
conf.id:1: error: 'push' cannot mutate 'names', a list constant; pass it to a
  function that takes the list as a parameter instead
```

An alias cannot be caught that way (`int[] xs = (import names); push(xs, "z");`
type-checks -- `xs` is an ordinary local, and the compiler cannot always tell
where a list came from), so the runtime traps instead:

```
id: cannot mutate a constant list
```

A function whose whole job is to build and return a list is rejected the same
way a scalar-returning one is, now that the list has a legitimate home in
conf.id (`docs/SPEC.md` §7.2).

**Only a root's `conf.id` is a manifest.** The name is reserved everywhere else
rather than silently ignored:

```
caesar/sub/conf.id:1: error: 'conf.id' is the dependency manifest and is only
  read at the root of a project or a dependency. Here it is neither compiled
  nor read, so anything it defines silently does not exist; rename it
```

> **Pitfall 5.** `conf.id` at the root is a manifest. `conf.id` anywhere else
> is an error, not a config file.

### Depending on another tree

```
import "../mylib"
```

The dependency is merged as source, transitively, and its own `conf.id` is
followed. Every rule applies to it — including the 3-entries-per-directory
limit — with one exception that matters: **a name keeps one type within a
compilation unit, and an imported tree is its own unit.** Your `int s` and a
library's `string s` do not collide. Inside your own tree they do, and that is
where it still bites:

```
caesar/shift.id:3: error: argument 'c' of 'shift_one' expects int, got string
caesar/shift.id:8: error: chr expects an int, got string
caesar/shift.id:9: error: argument 'c' of 'chr_is_lower' expects int, got string
```

Every one of those lines is in `shift.id`. The cause was a brand-new file
declaring `noisy(string c)` — and no diagnostic names it. When a type error
appears in a file you did not edit, look for a new declaration of that name
somewhere else in the tree.

> **Pitfall 6.** A name has one type across your whole tree. Breaking that
> reports the error everywhere *except* where you broke it.

### Importing part of a tree

A dependency does not have to be a root. `import "../engine/gfx"` merges that
one directory -- which is how a test gets a renderer without the window backend
the whole engine names. The directory has no `conf.id` of its own, but its code
reads the engine's constants, so it takes them from its **enclosing root: the
nearest directory above it that has a `conf.id`**. A constant keeps one home
however little of its tree you import.

- **Only the constants come along.** The enclosing root's `import` lines are not
  followed: leaving the rest of the tree out is why you imported part of it.
  Whatever the part needs, name in your own `conf.id`.
- **A root's constants are taken once**, however it is reached -- whole, through
  one subdirectory, or through several. Importing `engine/core/util` and
  `engine/gfx` side by side declares nothing twice.
- **A directory with its own `conf.id` is a root**, and reads only that one.
- **One name, two `conf.id`s, is an error** that names both declarations:

  ```
  app/conf.id:2: error: constant 'lib_k' is already declared at
    /home/me/lib/conf.id:2; a constant has one home -- rename one of them
  ```

- **A `conf.id` below the directory you import is still nested**, and still an
  error. Nesting is judged against the tree being built or imported, never
  against the directories above it.
- The rule is for `conf.id` imports. The project you build, a `--backend`
  directory and the standard library read only their own `conf.id`.

## 6. A project with no `main` is a library

```sh
idc/bin/idc lib --allow-untested -o lib.o
file lib.o        # ELF 64-bit LSB relocatable
```

Nothing is pruned — every function is an entry point — and everything is still
checked.

To call the library from C, Python or JavaScript instead of linking the `.o`
into another id program, build it with `--lib`: that produces a shared library,
a static archive and a C header for the functions named in the root `conf.id`'s
`string[] lib_exports = [...];` (`docs/INTEROP.md`, "id as a library"). That one
line is read by the driver and by nothing else: the program never sees it, so it
is not a constant in the sense above and a dependency's own list never clashes
with yours.

A library that needs code from the program using it takes that code as a
function value ([`SPEC.md`](SPEC.md) §1.1), not as a name the program must
define:

```
run_frame(func(int) return void step, int dt) {
  step(dt);
} return void;
```

A library that calls a name its user defines instead makes every program that
links it define that name, games or not — which is why `idem`'s engine, calling
`g_step` and five siblings, needs `idem/stub/` for everything that is not a
game ([`TODO.md`](TODO.md) 13). A function value is passed or stored where the
reader can see it, and a program that does not need the seam does not supply
one.

## 7. When the language does not have it

`id` has no file I/O. The builtins are stdin and stdout and nothing else, so a
"file program" in `id` is a filter and the caller picks the files with
`< in > out`. When that is not enough, a **native backend** supplies functions
at link time, and the standard library carries three: files (`sys/io/fs`), a
software window (`sys/win/gfx`) and an OpenGL window (`sys/win/gl`). There is
nothing to name: `fs_open`, `fs_read`, `fs_write`, `fs_close`, `fs_size`,
`fs_exists`, `fs_list`, `fs_remove` and `fs_error` are ordinary calls in every
program. The backend declares each of them in `id`, as a function whose body
is native code:

```
native fs_open(string path, string mode) return int;
```

Its directory is merged into your build like any dependency, so a call into it
is checked like any call: the wrong number or type of arguments, or a
misspelled name, is the same error it would be for a function you wrote.
`demos/fsdemo` is ~40 lines of `id` that never names C, and has no `conf.id`.

A backend of your own is a directory with a `backend.id`, its sources and its
`native` declarations, anywhere in a tree the build collects — your project, or
a `conf.id` import. The driver finds it by its `backend.id`.

**Which implementation you get is chosen for you.** The build has a target
triple, derived from the machine you are on unless you say otherwise, and the
backend's `backend.id` is indexed by the platform in it. Nothing in your
source changes when the platform does.

`backend.id` is how a backend says what to link, in `id`'s own constant
declarations — `string[] c_linux_sources = ["fs_posix.c"];` — and it is the
one `.id` file in a backend that is never compiled: the driver reads it, so
none of its names reaches your program (`docs/BACKENDS.md`).

```sh
idc/bin/idc demos/fsdemo --allow-untested            # x86_64-unknown-linux-gnu here
```

**A backend costs nothing until you call it.** Attaching one merges its
declarations; it is compiled and linked only when something reachable from
`main` calls one of its natives (and, for the test harness, only when a case
reaches one). The standard library carries `gfx` and `gl`, and a program that
never draws still links no X11.

`--triple` overrides the platform, and when a native you reach has no
implementation for the platform you asked for, the build stops at the call
that reaches it, before anything else about the build is refused:

```sh
idc/bin/idc demos/gl3d --allow-untested --triple aarch64-apple-darwin
demos/gl3d/loop/frame.id:8: error: native 'glwin_poll', reached from main by
  this call, is implemented by backend 'gl', which has no support for platform
  'darwin' (building for 'aarch64-apple-darwin'); it is implemented for: linux
```

A native declared outside any attached backend is the same kind of error — it
names the call and the platform, and says the declaring file is not in an
attached backend — rather than a linker error about `id_<name>`.

`--backend DIR` chooses another implementation of one backend for one build:
DIR holds a `backend.id` whose `name` is that backend's, and its sources, and no
declarations. The declarations every call was checked against stay where they
are, and DIR's sources for the platform are compiled and linked instead. Two
for one backend is an error.

The same applies to `asm` functions, which are selected by exact triple with no
wildcard and no fallback:

```
error: no 'asm' definition of 'dbl' for target 'aarch64-unknown-linux-gnu';
  defined for: x86_64-unknown-linux-gnu
```

**What `--triple` does not do is cross-compile.** It picks sources and asm
overloads; the C target still compiles with your `cc`, so asking for a platform
your compiler does not target is refused rather than faked:

```sh
idc/bin/idc demos/fsdemo --allow-untested --triple aarch64-apple-darwin
idc: cannot build for 'aarch64-apple-darwin' here: the C target compiles with
  the host's cc, which targets 'linux', not 'darwin'.
idc: pass --cc with a cross compiler for 'darwin', or use --target llvm, which
  hands the triple to clang.
```

> **Pitfall 7.** A native's *name* is reserved like any function's, in every
> program: the standard library declares `fs_open`, `gfx_open`, `gl_width` and
> the rest, so a program that defines one collides with it. Its parameter names
> are not variables and reserve nothing, so no name your program exports or
> declares can collide with one of them. A native of a backend of your own
> exists only when its directory is in the build; call one without it and the
> error is `no such function`, the same error a misspelling gets.

## 8. When you do not believe the compiler

```sh
idc/bin/idc caesar --allow-untested --emit-c caesar.c
```

writes the generated C instead of building. It is the fastest way to find out
what a construct actually costs, and the fastest way to confirm that the thing
you think is being called is the thing being called:

```c
char* id_shifted(int c, int base);
...
        out = id_shifted(c, 97);
```

`--keep-c` keeps it *and* builds. `--emit-llvm` and `--target llvm` are the
same idea one layer down.

## 9. Tests

A test case lives beside the function it tests, under its return clause, and
the compiler requires at least two per function on every build. Two for
`shifted`, whose body is in §2:

```
shifted(int c, int base) {
  ...
} return string out;
(97, 97):("d")
(120, 97):("a")
```

A function with fewer is a compile error. `--allow-untested` turns that off
for a build that does not have its cases yet — every build above — silently,
and goes once every function has its cases. While the standard library still
lacks some, a build that merges it needs the flag even when its own
functions are all tested. See [`TESTS.md`](TESTS.md), "Enforcement, and the
migration".

---

## The checklist

Seven things, in the order you will meet them.

1. **A call's argument may hold one level of call, not two.** Name the inner value when a call would sit two deep.
2. **3 functions per file, 3 entries per directory.** The directory limit fires
   on a directory you were not editing. Plan the levels early. A `chain`
   continues a function without adding to the file's three.
3. **Read the first error only.** One mistake produces a cascade; the lines
   below the first are consequences.
4. **Anything that exports state needs its initialiser called from `main`** —
   `fx_trig_init`, `err_init`, and anything of yours that does the same.
5. **`conf.id` is a manifest, and only at a root.** Elsewhere it is an error.
   Imports before constants.
6. **A name has one type across your whole tree** — and the errors appear
   everywhere except where you broke it.
7. **A backend is part of the build, not the source.** The platform is chosen
   from the target triple; an unsupported one stops the build by name.

## Where to go next

- [`TUTORIAL.md`](TUTORIAL.md) — the language, through one worked program.
- [`SPEC.md`](SPEC.md) — what is guaranteed, independent of backend.
- [`../README.md`](../README.md) — every builtin and every rule, in one list.
- [`../idc/README.md`](../idc/README.md) — what `idc/bin/idc` does under the hood.
- `demos/` — `hello`, `calc`, `adventure`, `wordcount`, `fsdemo` are the small
  teaching set; `demos/solitaire` is what a real program looks like at scale.
