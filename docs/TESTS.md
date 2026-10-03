# Tests are part of a function

A function in `id` is not finished when its body is written. It is finished
when the cases underneath it pass:

```
add(int a, int b) {
  int s = a + b;
} return int s;
(1, 2):(3)
(0, 0):(0)
```

Those two lines are not a comment and not a separate file. They are part of
the declaration, the compiler runs them, and a program whose cases do not pass
does not build.

## Why at the compilation layer

`id` already refuses to compile a program that breaks one of its rules. Every
one of those rules is about *shape* — how long a block is, how deep it nests,
whether two functions do the same thing. None of them is about whether the
code is right.

A separate test suite answers that question, but only when someone runs it,
and only for the functions someone remembered to cover. Putting the cases in
the declaration makes three things true that a suite cannot:

- **A regression is a compile error**, at the function that broke, named by
  the case that caught it — not a failure in a distant file discovered later.
- **There is no untested function**, because a function without cases is not a
  function the compiler will accept.
- **The cases are documentation that cannot rot.** The example next to `add`
  is checked on every build, so it cannot drift from what `add` does — which
  is exactly what happens to the examples in a comment, and has happened twice
  in this repo already (`docs/GAPS.md` E2, and the stale fallback text in the
  README).

## The form

After the `return` clause, one case per line:

```
given SETUP stdin "TEXT" timeout N (ARGS):(EXPECTED) then CHECK:(VALUE) [CONSTRAINTS]
```

Most cases are just `(ARGS):(EXPECTED)`:

- **`ARGS`** — the arguments, as `id` literals, in order. `()` for none.
- **`EXPECTED`** — the value the call must produce, as an `id` literal.
- **`CONSTRAINTS`** — optional, in square brackets. See below.
- **`given SETUP`** (or **`given SETUP(LIT, ...)`**) and **`then CHECK:(VALUE)`** —
  optional, for functions whose behaviour is module state. See "Module state"
  below.
- **`stdin "TEXT"`** and **`timeout N`** — optional, after any `given` and
  before `ARGS`: the case's standard input, and its wall-time limit in
  seconds (default 30). See "What a function reads" below.

**At least two cases per function.** One case documents an example; two start
to describe behaviour. The compiler requires two and does not care which two,
which is a floor rather than a target.

**A function and its `chain` continuations share one pair.** The segments are
one function and execute as a unit, so a case exercises all of them and the
cases go after the final `return` clause as usual — not a pair per segment. The
converse is worth knowing when you edit: giving an existing function a chain, or
folding a function into one as a chain, changes what the pair has to describe,
so its cases need rewriting rather than carrying over.

**`main` is a function like any other, and needs its two as well.** Its cases
are usually about parameter handling and edge cases — no arguments, too many,
an argument that does not parse:

```
main(int argc, string[] argv) {
  int n = len(argv);
  int r = n - argc;
} return int r;
(1, ["prog"]):(0)
(3, ["prog", "a", "b"]):(0)
```

**And they must be two different cases.** Writing the same case twice is the
cheapest way to satisfy a two-case minimum without producing any evidence, so
a duplicate is an error:

```
add.id:5: error: this test case is identical to an earlier one; two cases
          must describe two behaviours (see docs/TESTS.md)
```

Cases are compared as tokens, so `(1,2):(3)` and `(1, 2) : (3)` are the same
case and spacing cannot smuggle one past. The same case text under two
*different* functions is not a duplicate. Unlike the two-case minimum, this is
checked always rather than under `--require-tests`: it is wrong in a program
that writes cases voluntarily too, and a program with no cases has no
duplicates, so there is nothing to phase in.

A `void` function is tested by what it leaves behind. Because a list has
reference semantics, the expected side describes the arguments *after* the
call:

```
fill(int[] xs, int n) {
  int i = 0;
  while(i < n) {
    push(xs, i);
    i = i + 1;
  }
} return void;
([], 3):([0, 1, 2])
([], 0):([])
```

## Module state: `given`, `then`, `(import NAME)`

Some functions do their work somewhere a case's two tuples cannot see.
`err_report` returns `void` and changes exported globals; a buffer function
takes an address that only exists once `alloc()` has returned it. Three
optional parts of a case cover them:

```
err_setup() {
  export int[] err_n = [0];
} return void;

err_report(string msg) {
  int[] c = (import err_n);
  c[0] = c[0] + 1;
} return void;
given err_setup ("x"):("x") then count:(1)
given err_setup ("y"):() then count:(1)

count() {
  int n = (import err_n)[0];
} return int n;
```

- **`given SETUP`**, before the arguments, names a function in the build that
  takes no parameters and returns `void`. The case's process calls it first —
  before the arguments are built and before the counters are zeroed, so
  `[time:…]` and `[mem:…]` count only the call under test.
- **`given SETUP(LIT, ...)`** names a setup that takes parameters and calls it
  with the literals written in the parentheses: one per parameter, each held to
  the parameter's type as a case's own arguments are, and the function still
  returns `void`. It is what replaces a zero-parameter fixture whose only job
  is to call another function with fixed values:

  ```
  mem_new() {
    export int[] ab = [0, 0, 0];
  } return void;

  total(int[] m) {
    int s = m[0] + m[1] + m[2];
  } return int s;
  given mem_new given lset((import ab), 1, 7) ((import ab)):(7)
  given mem_new given lset((import ab), 0, 2) given lset((import ab), 2, 3) ((import ab)):(5)
  ```

  Any function of the build may be the setup, a library one included: `lset`
  is idstd's, which sets one element of a list.

  An `(import NAME)` among the literals is the value the export holds once the
  setups written BEFORE this one have run, so `given mem_new given
  lset((import ab), ...)` works and the reverse order is an error. Setups run
  in the order written, and each one's arguments are built just before it is
  called. Bare `given SETUP` still means a setup with no parameters, and the
  two can be mixed in one case. Whether the parentheses after a name are the
  setup's arguments or the case's own tuple is decided by what follows the
  matching `)`: the case's tuple is always followed by `:`, a setup's
  arguments never are, so `given f(1) (2):(3)` and `given f (1):(2)` read as
  they look, with or without a space.
  The literals are part of the case's tokens, so changing one changes its
  cache key and the case runs again (tested in `idc/tests/cache.sh`).
- **`then CHECK:(VALUE)`**, after the expected values and before the
  constraints, as many as the case needs, names a function in the build that
  takes no parameters and returns a value. It is called after the call and
  after the counters are read, and its result is compared with `VALUE` at its
  return type exactly as an expected value is. A check that does not hold
  fails the case:

  ```
  err.id:9: test failed: err_report("x") then count() = 1, expected 2
  ```

- **`(import NAME)`** may be an element of `ARGS` or `EXPECTED` — at the top of
  the tuple or inside a list literal, nested lists included, and never a
  check's value — in a case that has `given`. It is the export's value where
  it is read: after the setup for an argument, after the call for an expected
  value. So an address can be handed in by name, and `main`'s `argv` can carry
  an exported path:

  ```
  buf_setup() {
    export word gb = alloc(8);
  } return void;

  fill3(word p) {
    poke8(p, 3);
  } return void;
  given buf_setup ((import gb)):((import gb)) then first_byte:(3)
  given buf_setup ((import gb)):() then first_byte:(3)
  ```

  A case's process starts with every export unset, so a function under test
  that reads an export its `given` does not set -- or a case with no `given`
  at all -- traps with `id: read of an uninitialised export (its declaring
  function has not run)`, whatever the export's type, rather than reading 0 or
  crashing; `then traps:("uninitialised export")` pins that down. The check is
  in the test harness only: a program's own C has none (docs/SPEC.md 8).

Every rule about these is decided from the case line and the declarations it
names — nothing is discovered by running the case — and each is an error at
the case's line:

| written | error |
| --- | --- |
| `given` naming no function | `'given' names 'nope', which is not a function in this build` |
| `given NAME` of a function with parameters | `'given' names 'f', which takes 1 parameter(s), but this 'given' passes 0; a setup is called with one literal per parameter, as in 'given f(1, 2)', and with none as 'given f'` |
| `given NAME(...)` with the wrong number of literals | `'given' names 'f', which takes 3 parameter(s), but this 'given' passes 2; ...` |
| a literal of the wrong type among a setup's arguments | `this case gives a string where a int is required` |
| a function's name among a setup's arguments | `a setup's arguments are literals or (import NAME); 'mk' is a function name, which only a case's own arguments may pass` |
| `given` naming a function that returns a value | `'given' names 'ret1', which returns int; a setup returns void, since the harness has nothing to compare its result with` |
| `then` naming no function | `'then' names 'nope', which is not a function in this build` |
| `then` naming a function with parameters | `'then' names 'f', which takes 1 parameter(s); a check takes none and returns the value it compares` |
| `then` naming a `void` function | `'then' names 'st', which returns void; a check takes none and returns the value it compares` |
| a check with more or fewer than one value | `a 'then' check compares exactly one value, not 2` |
| `(import NAME)` as a check's value | `a 'then' check compares a literal; (import g) may only be an argument or an expected value` |
| `(import NAME)` in a case without `given` | `(import g) needs a 'given': an export has no value in a case until a setup has run; a setup's own arguments are read before it runs, so an (import NAME) there needs an earlier 'given' that sets it` |
| `(import NAME)` of a name nothing exports | `(import zz): 'zz' is not an exported variable` |
| `(import NAME)` exported by a function the setup does not reach through the call graph | `(import h): 'h' is exported by 'other', which the setup 'st' does not reach, so nothing sets it before the call` |
| `(import NAME)` whose type is not exactly the one at that position | `this case gives (import xs), a int[], where a int is required` |

The setup-argument and list-element rows are tested in
`idc/tests/invalid/given_args_*.id` and `idc/tests/invalid/list_import_*.id`,
and their working forms in `idc/tests/tests_feature.sh`.

The reachability is the dead-export check's, seeded from the setup instead of
`main`: the setup itself, or anything it calls, may be what exports the name.
The type must match exactly because an export already has a type; a literal is
built at whatever type it is given, but an export used as another type is a
conversion nobody wrote.

Setups and checks are ordinary functions. The two-case minimum applies to them
as to anything else, and their own cases can use `then`. The duplicate rule
compares the whole case, `given` and every `then` included, so two cases that
differ only in a check are two cases. `given` and `then` are keywords, and
cannot be the name of a function, a variable or a parameter.

An `(import NAME)` argument adds nothing to a case's `n` (below): `n` is
written into the harness from the literals, before anything runs.

**A function's name** may be an element of `ARGS` or `EXPECTED` too, where the
position's type is a function type (docs/SPEC.md 1.1): that function, as a
value. A function that takes a function value needs two cases like any other,
and a function's name is as fixed as a literal -- nothing runs to produce it --
so it needs no `given`:

```
apply(func(int) return int f, int x) {
  int r = f(x);
} return int r;
(twice, 3):(6)
(twice, 5):(10)
```

The function's signature must be exactly the position's type
(`this case gives 'shout', a func(string) return void, where a func(int) return int is required`),
the name must be a function of the build -- any other name is still a
variable where a literal belongs
(`a test case takes literals only (a number, a string, or a list of those); 'nope' is not a function in this build, which is the only name a case may pass`) -- and the
harness carries the named function whether or not anything else calls it. It
adds nothing to `n`. A failing case prints a function value as
`a function value`: the running harness has the pointer, not the name.

**A struct** (docs/SPEC.md 1.2) is written as its constructor, anywhere a value
of its type may be: an argument, an expected value, a `then` check's value, or a
setup's argument. Its arguments are case literals in turn, so a field that is a
list, `(import NAME)` or another struct is written the way it is anywhere else.
A struct is a reference, so the expected side of a `void` function describes the
struct after the call, exactly as it does a list:

```
shift(Point p, int dx) {
  p.x = p.x + dx;
} return void;
(Point(1, 2), 3):(Point(4, 2))
(Point(0, 0), 5):(Point(5, 0))
```

The name must be the struct the position declares, with one value per field, each
fitting its field (`this case builds a Size where a Point is required`,
`struct 'Point' takes 2 field(s) (x, y), but this case gives 1`); a name that is
no struct is the same mistake a variable always was
(`... 'nope' is not a struct`). A failing case prints the structs in it as they
were written, `shift(Point(1, 2), 3) = Point(4, 2), expected Point(9, 2)`. A
struct adds nothing to `n`. Because a struct's file holds nothing else, the
function and its cases are in another file, and a test program that uses one is
a directory, not a single file.

These are rules of `idc/bin/idc`, the only compiler (the Python one, `idc.py`, is deleted). They are tested in `idc/tests/tests_feature.sh`.

## What a function printed, and what it called

Two more kinds of `then` clause, usable on any case, `given` or not:

```
greet(string name) {
  print("hi " + name);
} return void;
("a"):() then prints:("hi a\n")
("b"):() then prints:("hi b\n")

warn(string msg) {
  eprint("warning: " + msg);
} return void;
("full"):() then eprints:("warning: full\n")
("low"):() then eprints:("warning: low\n")
```

- **`then prints:("text")`** -- the exact bytes the call under test writes to
  **stdout** must equal the string literal, same escapes as a string literal
  anywhere else. `print` always ends a line, so a case comparing one `print`
  call writes the trailing `\n` in its expectation, exactly like the example
  above; a function that writes nothing is tested against `prints:("")`.
- **`then eprints:("text")`** -- the same, for what `eprint` writes. Only
  `eprint`'s own output (and `stdio_write_mem`'s, below) is captured; a runtime trap's message (`docs/TESTS.md`,
  "How it runs") ends the case before any `then` clause runs, so there is
  nothing here for it to be confused with.
  idstd's `stdio_write_mem` (bytes to fd 1 or 2) counts as `print` and `eprint`:
  fd 1 shares stdout's stream and fd 2 writes where `eprint` does, so both are
  captured, in order with them. An `fs_` handle opened on `/dev/stdout` has an
  offset of its own, goes around that stream, and has no defined order against
  `print`; use `stdio_write_mem`.
- **A captured NUL fails the case.** A `prints`/`eprints` value is a string
  literal, which cannot hold a NUL byte, so no expectation can equal output
  that has one. A case whose call wrote a NUL fails saying so, rather than
  comparing only the bytes before it; check such bytes with a `then` function
  that reads them back instead.
- **Only the call under test is captured.** A `given` setup's own output, and
  a `then` check's, run outside the window that is compared -- before it is
  opened and after it is closed, respectively -- so neither reaches
  `prints`/`eprints` at all, the same way neither is counted toward `time` or
  `mem`.
- A mismatch is reported the way a check's is, with both sides escaped so a
  newline is visible instead of splitting the line:

  ```
  greet.id:4: test failed: greet("a") prints = "hi a\n", expected "bye a\n"
  ```

```
helper(int x) {
  int y = x + 1;
} return int y;
(1):(2)
(5):(6)

runner(int n) {
  int h = helper(n);
} return int h;
(1):(2) then calls helper:(1)
(2):(3) then calls helper:(2)
```

- **`then calls NAME:(ARGS)`** -- at least one call to `NAME`, made during the
  call under test (directly, or by anything it calls, however deep), received
  exactly these arguments, compared the same way a case's own arguments are.
  **Several `then calls` clauses**, naming the same function or different
  ones, are matched **in order, as a subsequence** of the calls actually
  made: each clause must find a match that happened after the one before it.
- **`then calls NAME:[N]`** -- exactly `N` calls to `NAME` were made during
  the call under test, regardless of their arguments or when they happened.
- `NAME` must be a function of the build with a body to record into: a
  builtin is rejected, pointing at `prints`/`eprints` instead (a builtin's
  effect is its output, not a call the harness can see into), and so is a
  `native` (its body belongs to a backend, not to `id`). The argument count
  and types of the `:(ARGS)` form are checked against `NAME`'s own
  parameters, exactly like a case's own arguments are against the function
  under test's.
- **Recording starts when the call under test starts and stops when it
  returns.** A `given` setup's calls and a `then` check's calls are never
  recorded, the same reasoning as `prints`/`eprints`: only the window under
  test is observed.
- A call through a function value is recorded under the name of the function
  it resolves to at run time, because the harness instruments the callee, not
  the call site -- it does not need to know where a call came from.
- A mismatch on the `:(ARGS)` form shows the expected call, then the calls
  to `NAME` it was compared against, written the way a clause writes them --
  at most five, then how many more:

  ```
  runner.id:9: test failed: runner(1) calls helper(2) did not match any of the 1 recorded call(s) to 'helper': helper(1)
  ```

  When an earlier clause on the same case already matched, only the calls
  after that match could have matched this one; those are the ones listed
  first, and the calls before it are listed apart as skipped:

  ```
  runner.id:12: test failed: runner(1) calls helper(1) did not match any of the 1 recorded call(s) to 'helper' after the previous clause's match: helper(3); 2 earlier call(s) were skipped: helper(1), helper(2)
  ```

  A list argument is recorded by reference, not copied, so it is compared
  and shown in the state the case left it in -- the message says so
  whenever it shows one -- and a list longer than 16 elements is cut
  short with `...`:

  ```
  runner.id:12: test failed: runner(1) calls helper([0, 0], 1) did not match any of the 1 recorded call(s) to 'helper': helper([7, 0], 1) (list arguments show their final state)
  ```

  The `:[N]` form shows the count directly:

  ```
  runner.id:11: test failed: runner(1) calls helper[2], expected 3
  ```

- **Every call is counted, but only the first 65536 calls to a name keep
  their arguments**, so a function called millions of times inside a case
  cannot run the case out of memory. `:[N]` is exact however many calls
  there were. A `:(ARGS)` clause that finds no match among the kept calls,
  when later calls went uncaptured, fails saying so rather than passing or
  claiming the call was never made:

  ```
  runner.id:15: test failed: runner(70000) calls helper(65536) did not match any of the 65536 recorded call(s) to 'helper': helper(0), helper(1), helper(2), helper(3), helper(4), ... (65531 more); recording overflowed: 4464 later call(s) were counted but their arguments were not kept (at most 65536 per function)
  ```

Like `given`/`then`/`(import NAME)`, these are rules of `idc/bin/idc`:
there was once a second compiler that did not parse `prints`, `eprints` or
`calls`; it is deleted. Recording happens only in harness builds: the C a normal build
emits is unaffected, whether or not any case in the unit uses `calls` --
proved by comparing `--emit-c` before and after this feature, byte for byte.
Tested in `idc/tests/tests_feature.sh`; the compile errors above (unknown
name, a builtin, a native, wrong arity) are in `idc/tests/invalid/`.

## What a function reads, and a function whose job is to stop

**`stdin "TEXT"`**, after any `given` and before the argument tuple, is the
case's standard input:

```
load() {
  string src = read_all();
  load_at(src, 0);
} return void;
given full_env stdin "op =\nkw return\n" ():() then last_tkind:("kw")
given full_env stdin "ident x\n" ():() then last_tkind:("ident")
```

TEXT is an ordinary string literal. Before the function runs, the case's own
process gets TEXT as its whole stdin: `read_all()` returns it, and `input()`
returns its lines in order and then `""`. It is done at the process level, so
every reader behaves as it does in production. A case without the clause gets
empty stdin. At most one per case: `a case may have at most one 'stdin'
clause`; a non-string is `stdin's value must be a string literal, found '...'`.

**`then traps:("TEXT")`** is for a function whose correct behaviour is to stop
the program:

```
try_fault() {
  peek64(0x140000000);
} return void;
():() then traps:("out of range")
():() then traps:("5368709120")
```

The case passes only if the call stops its process with a trap whose message
contains TEXT. A runtime trap is matched against its `id: ...` line; death by
a signal counts too, matched against `killed by signal N (NAME)`. Running out
of time, or exiting with no message, is not a trap. If the call returns, the
case fails (`... expected a trap containing X, but it returned`); if it traps
differently, both messages are shown. The expected side must be `()`, and no
other `then` may accompany `traps`, because nothing after a trap is captured.
`given` works as usual. One `traps` per case, with one string; each misuse is
an error at the case's line, tested in `idc/tests/invalid/traps_*.id`.
`stdin`, `timeout` and `traps` are keywords, like `prints` and `calls`.

**`timeout N`**, after any `given` and any `stdin` and before the argument
tuple, is the number of seconds that one case may run:

```
given fx stdin "a\n" timeout 90 (1):(2) then prints:("x")
```

N is a positive integer literal. Only that case's wall-time limit changes,
from the default 30 seconds to N; a case without the clause keeps 30, and the
report for a case that overruns names its own limit (`did not finish within
90 seconds`). At most one per case, and it comes after every `given` and
`stdin`. Each misuse is an error naming the fix: a second one (`a case may
have at most one 'timeout' clause`), a value that is not a positive integer
literal (`timeout's value must be a positive integer literal`), `timeout`
ahead of a `given` or `stdin`, and `timeout N` with no argument tuple after
it; tested in `idc/tests/invalid/timeout_*.id`. The clause is part of the
case's tokens, so changing it changes the case's cache key and the case runs
again.

## Constraints are counted, not timed

A constraint states how the function scales:

```
total(int[] xs) {
  ...
} return int sum;
([1, 2, 3, 4]):(10)[time:O(n), mem:O(1)]
([1, 2, 3, 4, 5, 6, 7, 8]):(36)[time:O(n), mem:O(1)]
```

The constraint is on **both** cases, and that is not decoration: a claim about
scaling is a claim about two points, so it has to be written on the two cases
being compared. A constraint carried by only one case is an error (below).

`time` and `mem` accept `O(1)`, `O(log n)`, `O(n)`, `O(n log n)`, `O(n^2)`.

**Nothing is timed with a clock.** Wall time depends on the machine, the load,
the allocator and the weather, so a build that fails on a busy laptop and
passes on an idle one is not a test — it is a coin flip that occasionally
tells the truth. Instead the runtime keeps two exact counters:

| counter | incremented |
| --- | --- |
| `time` | once per loop iteration and once per function call, **plus the bytes each runtime helper actually touches** — `concat` charges both operands, `len` charges the string, `charat` charges nothing: it is one load of the stored length |
| `mem` | by the number of bytes each allocation requests |

The second half of the `time` row is what makes the counter measure the right
thing. Counting only generated code would call this function linear:

```
build(int n) {
  string out = "";
  int i = 0;
  while(i < n) {
    out = out + "x";
    i = i + 1;
  }
} return string out;
```

It is one loop, so by the generated code's own arithmetic it is `O(n)` — but
each `concat` copies the whole string built so far, so the work is quadratic
and the memory retained is quadratic too. With the helpers counted it is
caught:

```
build.id:10: error: [time:O(n)] does not hold for 'build': time is 15 at n=4
             and 2145 at n=64, where O(n) allows at most 960
```

Both are deterministic: the same program on the same input gives the same
numbers on every machine, every run. A scaling claim is then a comparison of
two counts rather than a measurement, and it either holds or it does not.

`n` is the **size of the case's input**: the length of a list or string
argument, or the value of an integer argument. When a function has several
arguments, `n` is the largest.

**A scaling constraint needs two cases carrying it, with different `n`.** With
one point there is no curve. The compiler says so rather than guessing:

```
sum.id:8: error: [time:O(n)] needs a second case with a different input size
          to compare against; this is the only case that carries it
```

Given two counts `c1` at `n1` and `c2` at `n2`, the claim holds when `c2` is
no more than the claimed growth from `c1`, with a constant factor of slack —
`O(n)` allows `c2 <= c1 * (n2/n1) * k`, and so on. The slack exists because a
function has a fixed setup cost that dominates at small `n`; it is why the
message above asks for a *different* size rather than a bigger one.

## What this does not do

Stated plainly, because a test feature that overstates itself is worse than
none:

- **It does not prove a bound.** It compares two points on a curve. A function
  that is O(n) up to the sizes tested and O(n²) beyond passes. This catches
  the regression where a linear function silently becomes quadratic — which
  is the failure this repo actually had (`docs/GAPS.md` §3: `id_charat`
  called `strlen` on every access, and every text-processing program was
  quadratic for months with nothing to notice; strings now carry their length,
  so `charat` is not charged) — and it does not catch an
  adversarial input.
- **It counts work, not wall time**, so it will not catch a change that makes
  the same number of byte-touches slower — a worse cache pattern, say. That
  is the price of being reproducible, and it is the right trade: a
  regression in asymptotics is a bug, and a regression in constant factor is
  a benchmark's job.
- **It reads module state only through functions.** A `then` check is a call
  to a function that returns something, so state that no function returns
  needs one written to return it — which is usually the better shape anyway.
- **It cannot test a function whose inputs are neither literals nor made by a
  setup** — anything taking a file handle, a window, or a backend resource.
  Those are exempt and the compiler says which, rather than pretending.

## How it runs

`id` has no interpreter yet (`docs/BACKENDS.md` step 4), so the cases cannot
be folded at compile time. Instead `idc/bin/idc` builds a **harness** on every
build: every case in the program's own tree and its `conf.id` dependencies,
together with the functions those cases can reach, their work counted, and a
generated entry point that runs every case. It runs the harness first, and
only if every case passes does it produce what was asked for.

**Libraries are checked on their own first.** The standard library, and any
attached native backend directory that holds `id` code with cases, is a
library unit: its cases run once, as a check of the library itself, before
the program's harness, and are left out of the program's. A failure there
fails the build with a message that names the library and says it is not the
program's fault:

```
idc: the standard library at /path/idstd failed its own test cases (this is not an error in your program):
```

That result is cached by the library's content and the compiler and `cc`
identity, so a warm build pays nothing for it. A library function the
program's cases call is still compiled into the harness as a callee; only its
own cases move. `--no-std` skips the standard library's check.

**A case that passed is not run again until something it can reach changes.**
Each case is keyed on its own tokens and on everything it can reach: the
functions it calls, the exported variables it reads (through the function that
declares them), and the `conf.id` constants it reads, directly or through the
initialiser of another constant. Editing a constant nothing reads reruns no
case; editing one reruns exactly the cases that read it. What the source cannot
say -- the compiler, `cc` and the host -- is part of every key. A case that
reaches a `native` or an `asm` routine, or carries a scaling claim, is never
cached. `IDC_CASE_STATS=1` prints how many cases were already passed and how
many ran (`idc/tests/cache_reach.sh` counts reruns with it); `IDC_NO_CACHE=1`
runs every case.

**A case runs in the root of the source tree that owns its function**: the
project root for the program's own cases, and a dependency's root for the
cases of a library imported through `conf.id`. So a case or a setup can name a
file by a path relative to its own tree, and it finds the same file however
that tree is built — alone, or imported by another project (the editor's font
cases load `test_assets/DejaVuSans.ttf`; idem's engine cases load `../test_assets/…`
from beside the engine). A library's pre-check runs from its own root, the
same place. And **every case gets empty standard input** unless it supplies
its own (`stdin`, below): a case never reads the terminal or the harness's
input. `--emit-c` and `--emit-llvm` run the cases too, and there is no flag that turns them off: the point is that there is no
way to get output from a program whose cases fail.

**Each case runs in a process of its own.** A case that traps, crashes or
corrupts module state takes no other case with it, and the flat-store
addresses a case sees are the ones it would see alone — they do not depend on
what the cases before it allocated. A case's `given` setup runs in that same
process, so what it builds is the case's alone. Every failing case is
reported at its own line, and the build stops:

```
add.id:4: test failed: add(1, 2) = 3, expected 4
quot.id:6: test failed: quot(7, 0) trapped: id: division by zero
down.id:4: test failed: down(0) was killed by signal 11 (Segmentation fault)
```

**Cases run callees first.** The harness orders cases by the call graph: a
function's cases run after the cases of every function it calls, and
functions in one recursive cycle keep their source order. Once a function has
a failing case, the cases of every function that calls it, directly or
through others, are not run. Each is reported at its own line as `not run`,
naming the callee whose case failed, and the summary counts them. So the
first failure in the output is the deepest one, and a broken leaf does not
bury itself under its callers' failures. A case that was not run never
counts as passed, and the build still fails. A function named only by
`given` or `then` is not a dependency.

A case has 30 seconds of wall time -- or the N of its own `timeout N` clause
-- and 4 GiB of address space; a case that runs out of either fails the same
way. Scaling claims are judged once every
case has passed, since a count from a case that failed measures nothing.

The harness is built for and run on the machine doing the build. A
`--freestanding` tree's cases run there too, against the same source compiled
for the host: the kernel's cases run on every kernel build, and a failing one
stops it. Functions that reach an `asm` body cannot run on the host and are
exempt from the minimum; the compiler names each one.
A program that uses a native backend gets the
backend linked into its harness as well, so a tested function that calls into
one really runs.

`idparse --harness` writes the harness ahead of the program on the same
stream, so one parse produces both, and the program is emitted exactly as it is
without the flag. The harness's code is
`idc/compiler/parse/back/tgt/c/emit/prog/test/`.

When the interpreter target lands, the harness stops being a subprocess and
becomes an evaluation inside the compiler; the syntax and the diagnostics do
not change.

## Enforcement, and the migration

The rule "every function has at least two cases" is **on by default** in
`idc/bin/idc`, on every build and every compilation unit — the program, its
dependencies and the standard library. A function with fewer is a compile
error, with the diagnostic `--require-tests` has always given:

```
err.id:27: error: function 'err_init' has 0 test case(s); --require-tests needs at least 2 (see docs/TESTS.md)
```

It is the default because a case is the only record of what a function did
when it was written. A function without one can drift — start returning
something else for an input nobody wrote down — and nothing notices; a function
with two carries a static statement of its behaviour, checked on every build,
to diagnose unexpected behaviour against later. `--require-tests` is still
accepted, and restates the default.

The tree does not have its cases yet (the table below), so there is a way out:

- **`--allow-untested`** turns the minimum off for one build, silently — `id`
  has no warnings: something is allowed or it is not, and this is allowed
  until the tree has its cases. Nothing else changes — not the exit status,
  not stdout, not any other diagnostic. It is a command-line flag only, so
  every build that relies on it says so where it is invoked, and
  `grep -r -- --allow-untested` is the list of builds still to fix.
- Every case that *is* written runs on every build either way, and a failure
  fails the build. `--allow-untested` skips no case; it only stops counting
  them.

**Every build in these repositories passes the flag today**, and not only for
want of cases in its own code: `idstd` is merged into every build that does not
say `--no-std`, and 59 of its functions have fewer than two (measured
2026-09-13 — all of `sys/err` and `core/data/buf`, and the trig half of
`core/math`, among them). Until they have them, a program whose own functions
all have their cases still needs `--allow-untested`, or `--no-std`, to build.

**The flag is deleted when no function is short of two cases.**
`idc/tests/run.sh` (`core`) reads the count below and fails while it is zero
and `idc/bin/idc` still has `--allow-untested`, saying to delete it. The count
is functions, not cases — each case is credited to the function it is written
under — so functions with many cases cannot hide one with none. It covers every
tree a build here passes the flag for, the kernel and runtime included.

The order that gets there: `idstd` first (a standard library is where an
untested function costs the most, and today it holds back every other build),
then new code, then the compiler's own source last — it is the largest and the
one whose behaviour is already pinned by `idc/tests/conform.sh`.

### A freestanding build's cases

This used to be an open question: whether a `--freestanding` build could
comply at all. It is settled the first way it listed. A freestanding tree's
cases run hosted, against the same source built for the host ("How it
runs"), so a freestanding tree can be cased like any other.

### Where the rollout actually stands

> **Status, 2026-09-13.**
>
> **`--require-tests` is enforced by the primary compiler.** It used to exist
> only in `idc/idc.py` — the self-hosted compiler parsed cases and ignored them,
> which meant the rule was not a rule of the language, only of the bootstrap
> that is being retired. `idc/bin/idc --require-tests` now applies it, with the
> same diagnostic text, checked against `idc/idc.py` case by case in
> `idc/tests/tests_feature.sh`. The check is
> `mid/names/limits/shape/cases/`, a sibling of the action limit: a rule about
> the shape of a declaration, and the only one of them that is a minimum.
>
> **How far adoption has actually got** is not written here, because any
> number written here is out of date by the next merge. Ask for it:
> `idc/tools/statusgen.sh` prints functions and cases per repository, and
> `idc/bin/idc TREE --list-untested` lists every function in one tree that is
> still short of two cases.
>
> **Duplicate cases are rejected, in the self-hosted compiler only.** `idc/idc.py`
> does not have this rule and will not get it: it is stage 0 of a bootstrap
> being retired, and a new rule added there is a line that has to be deleted
> later. This is the first rule where the two compilers deliberately differ,
> so it is tested in `idc/tests/tests_feature.sh` against `idc/bin/idc` alone rather
> than in `idc/tests/invalid/`, which requires both to agree.
>
> **Every written case runs on every build of the primary compiler.**
> `idc/bin/idc` builds a harness beside the program and runs it before it
> produces anything (see "How it runs"), so a case that does not pass is a
> compile error, with no flag either way. Whether a case fits its function —
> its argument count, its expected values, the types of its literals — is
> checked on every build as well, in
> `mid/names/limits/shape/cases/more/fit/`. `idstd`'s 230 cases all pass
> under it.
>
> **`given`, `then` and `(import NAME)` are understood by the primary compiler
> only.** `idc/idc.py` lexes `given` as an ordinary identifier, and after a
> return clause it reads one as the start of the next function, so any file
> containing the form fails there: `expected '(', found 'SETUP'`. `idc/idc.py`
> merges `idstd` into everything it compiles by default, so that used to keep
> the form out of `idstd`: the suite built the compiler, the demos that use the
> library and the graphics demos through `idc/idc.py` with `idstd` merged, and
> one `given` in `idstd` failed all of them.
>
> **No build in the suite that merges `idstd` goes through `idc/idc.py` any
> more.** They are `idc/bin/idc` builds; `idc/idc.py` runs only with
> `IDC_NO_STD=1`, or in `idc/tests/stdlib.sh` against the fixture library,
> which never reads the real one. What moved, and what was lost with it:
>
> - `idc/tests/run.sh` (`core`): the lexer, parser, calculator and `idview`
>   builds, and `moonbuggy` and `solitaire`, are `idc/bin/idc` builds. The
>   checks that compared `idc/idc.py`'s C for `compiler/lex` and
>   `compiler/parse` with the self-hosted compiler's are now "self-hosting
>   parity with bin/idc": `idc/bin/idc --emit-c` against the lexer and parser
>   it built, run over the same source. Lost: an independent implementation
>   agreeing with the compiler on the compiler's own source and `idstd`.
>   What is left of that is `idc/idc.py` agreeing on programs without the
>   library — the parity checks in `core`, `idc/tests/self_host_build.sh`,
>   `idc/tests/stdlib.sh` and `idc/tests/invalid.sh`.
> - `idc/tests/backends.sh`: the six "backend build (idc.py)" checks on the
>   graphics demos are gone; the six `idc/bin/idc` builds beside them stay.
> - `idc/tools/parity.sh` builds its stages with `idc/bin/idc` and compiles the
>   program under test without the library on both sides, so it can no longer
>   be pointed at the compiler. `idc/tools/regen_bootstrap.sh --check` is what
>   says the compiler's own C did not change.
> - `idc/tools/idtest.sh` runs a module's cases with `idc/bin/idc`.
>
> Outside this suite, two builds still put `idstd` through `idc/idc.py`:
> `c2id` builds itself with it (`c2id/tools/c2id.sh`, `c2id/tests/run.sh`),
> because it does not yet obey two rules `idc/bin/idc` enforces
> (`docs/GAPS.md` B6/B7), and `idem`'s `IDEM_COMPILER=idc.py` switch selects it
> on request. A `given` in `idstd` breaks both.
>
> **The two-case minimum is the default, as of 2026-09-13.** A build that lacks
> cases passes the deprecated `--allow-untested` ("Enforcement, and the
> migration", above), and every build in these repositories does.
>
> Next: cases for `idstd`'s 59 functions that lack them, per the order above,
> starting with `sys/err` and `core/data/buf`, whose cases can be committed now.

> **Update: `idc.py` is deleted.** Every sentence above that says `idc.py`
> parses, rejects or builds something describes the project as it stood on
> 2026-09-13, when there were two compilers. There is one now, `idc/bin/idc`;
> `--target wasm` is built by it, `c2id` builds with it, and the `idem`
> `IDEM_COMPILER` switch is gone.

### What the case format cannot express

Found by writing `idstd`'s cases rather than by reasoning about the syntax, so
it is a measurement and not a worry. Two whole classes of function had no
expressible case while a case was only two literal tuples:

- **Functions whose meaning is in module state.** All 13 of `sys/err`:
  `err_report` takes a string and returns `void`, and everything it does lands
  in exported globals. A case could compare only the return value or the
  arguments after the call, so `(args):(same args)` passed whether or not the
  function did anything, and a zero-parameter function had nothing to compare
  at all.
- **Functions taking a flat-store address.** All 6 of `core/data/buf`, and
  `str_blit`, `fmt_pad_fill` and friends. An address is only valid once
  `alloc()` has returned it, and a case argument had to be a literal.

Both are expressible now ("Module state", above): a setup makes the state or
the allocation, `(import NAME)` passes the address in, and a `then` check reads
back what the function left. What remains:

- **A check reads state only through a function.** There is no way to compare
  an export directly except as an argument or expected value of the function
  under test, so state that no function returns needs a function written to
  return it.
- **A setup's arguments are literals.** `given NAME(LIT, ...)` passes literals
  and exports an earlier setup set; it cannot compute an argument, and a
  function's name is not one (a setup's function values are not carried into
  the harness as a case's own are). State that takes real code to build still
  needs a setup function of its own.
- **An `(import NAME)` argument has no size**, so a scaling claim on a case
  that passes an address takes `n` from its other arguments only.

There used to be a third, milder one: every case in a build ran as sequential
calls in one shared `main`, with no isolation, so a case that corrupted state
took down every other module's cases with it. `idc/bin/idc` runs each case in a
process of its own, which ends that.
