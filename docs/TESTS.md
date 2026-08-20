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
(ARGS):(EXPECTED)[CONSTRAINTS]
```

- **`ARGS`** — the arguments, as `id` literals, in order. `()` for none.
- **`EXPECTED`** — the value the call must produce, as an `id` literal.
- **`CONSTRAINTS`** — optional, in square brackets. See below.

**At least two cases per function.** One case documents an example; two start
to describe behaviour. The compiler requires two and does not care which two,
which is a floor rather than a target.

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
- **It cannot test a `void` function that only writes exports.** The expected
  side describes arguments, and an export is not one. Such a function needs a
  wrapper that returns what it wrote, which is usually the better shape
  anyway.
- **It cannot test a function whose inputs are not literals** — anything
  taking a file handle, a window, or a backend resource. Those are exempt and
  the compiler says which, rather than pretending.

## How it runs

`id` has no interpreter yet (`docs/BACKENDS.md` step 4), so the cases cannot
be folded at compile time. Instead `idc` builds a **harness**: the program's
functions, plus a generated entry point that runs every case and reports the
first failure. It runs the harness, and only if it passes does it produce the
program the user asked for. `--emit-c` runs the tests too — the point is that
there is no way to get output from a program whose cases fail.

When the interpreter target lands, the harness stops being a subprocess and
becomes an evaluation inside the compiler; the syntax and the diagnostics do
not change.

## Enforcement, and the migration

The rule "every function has at least two cases" is **not on by default
today**, and the reason is arithmetic: this repository has 1828 functions,
`idstd` has 201, and `../linux_id` has 1379. Turning the requirement on
without writing 6816 cases first would mean nothing in any of the three
repositories compiles.

So there are two switches:

- `--tests` runs every case that *is* written, and fails the build on a
  failure. This is safe to turn on everywhere immediately, and should be.
- `--require-tests` additionally rejects a function that has fewer than two.
  This is the end state, and it is reached one directory at a time.

The order that keeps the tree building: turn `--tests` on everywhere, then
`--require-tests` on `idstd` first (201 functions, and a standard library is
where an untested function costs the most), then new code, then the
compiler's own source last — it is the largest and the one whose behaviour is
already pinned by `tools/parity.sh` and `tests/conform.sh`.

### Where the rollout actually stands

> **Status, 2026-08-19.**
>
> **`--require-tests` is enforced by the primary compiler.** It used to exist
> only in `idc.py` — the self-hosted compiler parsed cases and ignored them,
> which meant the rule was not a rule of the language, only of the bootstrap
> that is being retired. `bin/idc --require-tests` now applies it, with the
> same diagnostic text, checked against `idc.py` case by case in
> `tests/tests_feature.sh`. The check is
> `mid/names/limits/shape/cases/`, a sibling of the action limit: a rule about
> the shape of a declaration, and the only one of them that is a minimum.
>
> **Cases written so far: 0, of 6816.** That number is the honest state of
> this document. The syntax has existed on both sides for a while and nothing
> in any of the three repositories uses it, which is the failure mode the rule
> is meant to prevent, showing up in the rule's own rollout.
>
> **`--tests` is not yet in the self-hosted compiler.** Running a case needs a
> generated entry point that calls each function and compares; only `idc.py`
> emits one. `--require-tests` needs no such thing — it is a count — which is
> why the enforcing half landed first and the executing half has not.
>
> Next: `idstd`, per the order above.

### What the case format cannot express

Found by writing `idstd`'s cases rather than by reasoning about the syntax, so
it is a measurement and not a worry. Two whole classes of function have no
expressible case, and `--require-tests` would reject every one of them today
with no way for the author to comply:

- **Functions whose meaning is in module state.** All 13 of `sys/err` are
  like this: `err_report` takes a string and returns `void`, and everything it
  does lands in exported globals. A case can only compare the return value or
  the arguments after the call, so `(args):(same args)` passes whether or not
  the function did anything. Zero-parameter functions are worse — there is
  nothing to compare at all, and the case is vacuously true.
- **Functions taking a flat-store address.** All 6 of `core/data/buf`, and
  `str_blit`, `fmt_pad_fill` and friends. An address is only valid once
  `alloc()` has returned it, and a case argument must be a literal — no calls.
  A literal address would also depend on how much every *other* case in the
  build had already allocated, so it is not merely awkward but nondeterministic.

Both are real limits of "a case is two literal tuples", not oversights. The
rule cannot be turned on for a directory containing either kind until the
format grows a way to say *set this up first* — which is a language design
question, not a rollout question, and it is the thing standing between
`--require-tests` and `idstd`.

There is also a third, milder one: every case in a build runs as sequential
calls in one shared `main`, with no isolation, so a case that corrupts state
takes down every other module's cases with it.
