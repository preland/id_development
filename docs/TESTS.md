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
given SETUP (ARGS):(EXPECTED) then CHECK:(VALUE) [CONSTRAINTS]
```

Most cases are just `(ARGS):(EXPECTED)`:

- **`ARGS`** — the arguments, as `id` literals, in order. `()` for none.
- **`EXPECTED`** — the value the call must produce, as an `id` literal.
- **`CONSTRAINTS`** — optional, in square brackets. See below.
- **`given SETUP`** and **`then CHECK:(VALUE)`** — optional, for functions
  whose behaviour is module state. See "Module state" below.

**At least two cases per function.** One case documents an example; two start
to describe behaviour. The compiler requires two and does not care which two,
which is a floor rather than a target.

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
- **`then CHECK:(VALUE)`**, after the expected values and before the
  constraints, as many as the case needs, names a function in the build that
  takes no parameters and returns a value. It is called after the call and
  after the counters are read, and its result is compared with `VALUE` at its
  return type exactly as an expected value is. A check that does not hold
  fails the case:

  ```
  err.id:9: test failed: err_report("x") then count() = 1, expected 2
  ```

- **`(import NAME)`** may be an element of `ARGS` or `EXPECTED` — at the top
  of the tuple, not inside a list literal, and never a check's value — in a
  case that has `given`. It is the export's value where it is read: after the
  setup for an argument, after the call for an expected value. So an address
  can be handed in by name:

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

Every rule about these is decided from the case line and the declarations it
names — nothing is discovered by running the case — and each is an error at
the case's line:

| written | error |
| --- | --- |
| `given` naming no function | `'given' names 'nope', which is not a function in this build` |
| `given` naming a function with parameters | `'given' names 'f', which takes 1 parameter(s); a setup takes none and returns void` |
| `given` naming a function that returns a value | `'given' names 'ret1', which returns int; a setup takes none and returns void` |
| `then` naming no function | `'then' names 'nope', which is not a function in this build` |
| `then` naming a function with parameters | `'then' names 'f', which takes 1 parameter(s); a check takes none and returns the value it compares` |
| `then` naming a `void` function | `'then' names 'st', which returns void; a check takes none and returns the value it compares` |
| a check with more or fewer than one value | `a 'then' check compares exactly one value, not 2` |
| `(import NAME)` as a check's value | `a 'then' check compares a literal; (import g) may only be an argument or an expected value` |
| `(import NAME)` in a case without `given` | `(import g) needs a 'given': an export has no value in a case until a setup has run` |
| `(import NAME)` of a name nothing exports | `(import zz): 'zz' is not an exported variable` |
| `(import NAME)` exported by a function the setup does not reach through the call graph | `(import h): 'h' is exported by 'other', which the setup 'st' does not reach, so nothing sets it before the call` |
| `(import NAME)` whose type is not exactly the one at that position | `this case gives (import xs), a int[], where a int is required` |

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

These are rules of `idc/bin/idc` only; `idc/idc.py` does not parse the form
(see the status below). They are tested in `idc/tests/tests_feature.sh`.

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
| `time` | once per loop iteration and once per function call, **plus the bytes each runtime helper actually touches** — `concat` charges both operands, `len` charges the string, `charat` charges a memo miss |
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
  quadratic for months with nothing to notice) — and it does not catch an
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
build: every case in the build — in the program's own tree, its dependencies
and the standard library — together with the functions those cases can reach,
their work counted, and a generated entry point that runs every case. It runs the harness first, and only if every case passes
does it produce what was asked for. `--emit-c` and `--emit-llvm` run the cases
too, and there is no flag that turns them off: the point is that there is no
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

A case has 10 seconds of wall time and 1 GiB of address space; a case that
runs out of either fails the same way. Scaling claims are judged once every
case has passed, since a count from a case that failed measures nothing.

The harness is built for and run on the machine doing the build. A build whose
cases cannot run there — `--freestanding`, or a `--triple` other than the
host's — is refused with that reason rather than built without them. A build
with no cases anywhere has no harness to refuse, so a tree that writes none
(the kernel, the runtime) still builds freestanding — but only with
`--allow-untested`, now that cases are required ("An open question", below).
A program that uses a native backend gets the
backend linked into its harness as well, so a tested function that calls into
one really runs.

`idparse --harness` writes the harness ahead of the program on the same
stream, so one parse produces both, and the program is emitted exactly as it is
without the flag — `idc/tools/parity.sh` still compares it with `idc/idc.py`
byte for byte, for a program built without `idstd`. The harness's code is
`idc/compiler/parse/back/tgt/c/emit/prog/test/`. `idc/idc.py` runs cases only
under `--tests`, in one process.

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

- **`--allow-untested`** turns the minimum off for one build. It is deprecated
  from the day it exists: a build that passes it prints, once, on stderr,

  ```
  idc: warning: --allow-untested is deprecated and will be removed once every function has its test cases
  ```

  and nothing else changes — not the exit status, not stdout, not any other
  diagnostic. It is a command-line flag only, so every build that relies on it
  says so where it is invoked, and `grep -r -- --allow-untested` is the list of
  builds still to fix.
- Every case that *is* written runs on every build either way, and a failure
  fails the build. `--allow-untested` skips no case; it only stops counting
  them. (`idc/idc.py` has neither the default nor the flag, and still spells
  running cases `--tests`.)

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
one whose behaviour is already pinned by `idc/tools/parity.sh` and
`idc/tests/conform.sh`.

### An open question: a freestanding build cannot comply

A `--freestanding` build (and `--runtime`, which implies it) refuses a build
that has any case, because the harness runs on the machine doing the build and
a freestanding program has none to run on ("How it runs"). With two cases
required, that leaves a freestanding program no state that builds without the
flag. Without cases:

```
u.id:1: error: function 'add' has 0 test case(s); --require-tests needs at least 2 (see docs/TESTS.md)
```

and with them, whether or not `--allow-untested` is passed:

```
idc: this build has 2 test cases, and a --freestanding build has no host to run them on
```

So the kernel (`kernel/prog`) and the `id`-written runtime (`idc/runtime`),
which `idc/tools/kbuild.sh` builds freestanding, pass `--allow-untested` with no
cases — the one use of the flag that writing cases cannot remove. Their
functions are counted in the table below, so the removal check cannot demand
the flag's deletion while they are short of cases; but writing those cases
would not let the kernel build without the flag either, so this question has
to be settled before the count can reach zero.

This is not decided. The shapes visible from here: run a freestanding tree's
cases hosted, against the same source built for the host (what
`idc/tests/kernel.sh` already does by hand for the shell's demonstrations);
exempt freestanding builds from the minimum permanently, which makes the kernel
the one place a function may drift; or accept cases in a freestanding build and
not run them, which is a way to get output from a program whose cases have
never passed. Deleting `--allow-untested` waits on this as well as on adoption.

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
> **How far adoption has actually got**, measured rather than remembered —
> this paragraph used to read "Cases written so far: 0, of 6816", which was
> true when written and false four commits later in the same session. A status
> block a human maintains is a status block that lies, and this one was lying
> about the adoption of the rule it describes. So the numbers are generated:

<!-- generated: adoption -->
| repository | functions | cases written | functions short of two cases |
| --- | ---: | ---: | ---: |
| `id_development` (with editor, idem, kernel) | 5828 | 343 | 5540 |
| `idstd` | 213 | 346 | 59 |
| `c2id` | 1051 | 0 | 1051 |
| `linux_id` | 0 | 0 | 0 |
| **total** | **7092** | **689** | **6650** |

**Functions short of two cases: 6650 of 7092 (6.2% complete).** Generated by
`idc/tools/statusgen.sh`; `idc/tests/run.sh` fails if it is stale. A repository
with no `.id` beside this checkout counts zero.
<!-- end generated -->

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
- **A setup takes no arguments.** Cases that need different state need
  different setups. A setup with arguments would need literals again, which is
  the limit the form exists to get past.
- **An `(import NAME)` argument has no size**, so a scaling claim on a case
  that passes an address takes `n` from its other arguments only.

There used to be a third, milder one: every case in a build ran as sequential
calls in one shared `main`, with no isolation, so a case that corrupted state
took down every other module's cases with it. `idc/bin/idc` runs each case in a
process of its own, which ends that; `idc/idc.py --tests` still does not.
