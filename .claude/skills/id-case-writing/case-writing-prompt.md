# Per-agent prompt template

The orchestrator sends one copy of everything below, per batch, to one Haiku
agent (Agent tool, `model: "haiku"`). Replace `{PROJECT_PATH}` and `{PACKET}`
before sending. Everything under the `---` is the literal message body.

---

You are writing `id` test cases for a small batch of functions in
`{PROJECT_PATH}`. You do not need to read any other file for the case syntax
or the rules below — they are complete. Do not explore the rest of the tree
beyond what your packet already shows you; if you find you need to, that is
itself worth reporting (say what was missing), not a reason to go searching.

## The packet

Below is one section per function in your batch: its file:line, its current
source (including any existing cases), how much room is left in its file (max
3 functions) and directory (max 3 entries, `.id` files and subdirectories
together), which exported globals its call closure transitively reads and
which function declares each one, every zero-parameter `void` function
already known to transitively reach all of those declaring functions
(candidate `given` setups), every zero-parameter value-returning function
already known to read one of those exports directly (candidate `then`
checks), and nearby fixtures already in use in this part of the tree.

```
{PACKET}
```

These candidate lists were computed by tracing the real call graph — trust
them for reachability. They are not a mandate: if a listed `given` reaches
the right export but leaves the state in a shape that does not actually
support the concrete example you want to write, do not force it. Say so and
either pick a different candidate or refuse the function.

## The case syntax

A case goes directly below a function's `return` clause, one per line, at
least two per function, and no two identical (compared as tokens — spacing
never makes two cases different):

```
name(int a, int b) {
  int s = a + b;
} return int s;
(1, 2):(3)
(0, 0):(0)
```

- `(ARGS):(EXPECTED)` — arguments as `id` literals in order (`()` for none),
  the value the call must produce, as a literal.
- A `void` function is tested by what it leaves behind. Because a list has
  reference semantics, the expected side describes the argument *after* the
  call: `([], 3):([0, 1, 2])`.
- `main` needs two cases like any other function.

**Module state — `given`, `then`, `(import NAME)`** (only when the packet
shows your function reads or writes an export):

```
given SETUP (ARGS):(EXPECTED) then CHECK:(VALUE)
```

- `given SETUP` names a zero-parameter `void` function from the packet's
  candidate list (or a nearby fixture) that runs before the call, before
  arguments are built.
- `then CHECK:(VALUE)` names a zero-parameter value-returning function
  (from the packet's candidate list, or one you write) called after the call
  under test; its result is compared to `VALUE`. Several `then` clauses are
  allowed on one case.
- `(import NAME)` may appear inside `ARGS` or `EXPECTED` (top level of the
  tuple, not inside a list literal) in a case that has a `given` — it is the
  export's live value: after setup for an argument position, after the call
  for an expected-value position. Requires the setup to transitively reach
  `NAME`'s declaring function (the packet already checked this for every
  candidate it lists).

**What a function printed or called** (usable with or without `given`):

- `then prints:("text")` — exact stdout the call under test wrote (only the
  call under test's window; a `given`'s and a `then`'s own output are not
  captured).
- `then eprints:("text")` — the same, for stderr.
- `then calls NAME:(ARGS)` — at least one call to `NAME`, made during the
  call under test (directly or transitively), received exactly these
  arguments. Several `then calls` clauses are matched in order as a
  subsequence of the calls actually made.
- `then calls NAME:[N]` — exactly `N` calls to `NAME` were made, regardless
  of arguments.

## Writing cases that mean something

Before writing any case, answer: **what would have to break for this to go
red?** If the answer does not name the behaviour the function exists to
perform, do not write that case — it is decorative.

Specific patterns that have wasted real time and must not recur:

- `then prints:("")` on a function that does not print is a tautology — true
  of nearly every function whether or not it works.
- A bare `():()` on a `void` function asserts nothing. Give it a `then` that
  reads something the function actually changed, or arguments/state whose
  after-value the call actually affects.
- Two cases asserting the identical thing carry one case's information. The
  compiler only rejects byte-identical cases — two cases that differ in an
  argument slot the function ignores are not caught, but are just as
  useless. Make your second case exercise a genuinely different behaviour
  (a different branch, a boundary, an error path), not the same path with a
  different irrelevant number.
- An expected value that is arithmetic on the function's own argument
  (`return j + 1` tested by expecting `j + 1`) passes even with the
  function's real logic deleted. Use a concrete literal the real
  computation produces, not a restatement of the formula.
- A return value **coupled** to a write is not a witness: a function that
  returns the thing it just wrote returns the same value whether the write
  landed in the right cell, the wrong cell, or the wrong row entirely. Check
  the write independently — read it back through a different function, or a
  `then` that inspects the actual state.
- For a state writer, witness the **value** that landed (a specific cell, a
  computed sum), not the **shape** (`len()`). `len()` cannot see a write into
  a cell that already existed.
- Prefer a positive witness (`then calls helper:(3)`, an exact returned
  value) over a negative one (`then calls helper:[0]`) when you have a
  choice — folding aside, a negative case alone only proves something did
  not happen, not that the right thing did.
- **Pin the boundary, not just the happy path.** The end of a string, the
  empty list, zero, one-past-the-last index. If both your cases are
  "normal" inputs, you have one behaviour documented twice, not two.

## Verify and falsify

After writing a function's two (or more) cases:

1. Build and run every case in the project:
   ```sh
   idc/bin/idc {PROJECT_PATH} --allow-untested --emit-c /tmp/idxcheck.c
   ```
   (from the repo root that contains `idc/`). A clean run prints nothing but
   the deprecation warning; a failing case prints `FILE:LINE: test failed: ...`
   naming it.
2. **Falsify by hand** — this is required, not optional, for every function
   you mark DONE. Temporarily break the function's actual logic in a way
   your new cases are supposed to catch (flip a comparison, change a
   literal, delete a statement), rerun the build above, and confirm a case
   now fails and names the right line. Then restore the original code
   exactly and rerun once more to confirm it is clean again.
   (`idc/tools/casework.sh mutate` exists for this but is currently known to
   report false `INVALID` verdicts on some inputs — do the break-rebuild-
   restore cycle by hand with `Edit`/`git diff` rather than trusting it.)
3. If a mutation you tried does not turn any case red, your cases do not
   pin down that part of the function — go back and fix the case, not the
   mutation.

## Refuse rather than fabricate

Some functions cannot be honestly cased. Refuse with a one-line reason
instead of writing a decorative case:

- The function reads `read_all()`/`input()` (stdin) and the case format has
  no way to supply input.
- The state it needs is the composition of two fixtures and there is no
  slot in a `given` (a setup takes no arguments — docs/TESTS.md) to combine
  them.
- The packet's candidate `given`/`then` lists are both empty for an import
  this function genuinely needs, and you cannot justify writing a new
  zero-parameter setup/check yourself within this batch's file/directory
  slot budget.
- It is a rule-6 fold candidate the packet flagged (should not appear in
  your batch, but if it does: do not case it, report it instead).

A refusal with a stated reason is a better result than a case that passes
for the wrong reason.

## Report

For each function in your batch, one of:

```
DONE: <name> (<file:line>)
<the two+ cases you wrote>
verify: <exact command> -> <exact relevant output line(s)>
falsify: <what you broke> -> <exact failing line it produced>, restored and reverified clean
```

```
FAILED: <name> (<file:line>)
<what you tried, the exact compiler diagnostic or wrong behaviour, and why you stopped>
```

```
REFUSED: <name> (<file:line>)
<the specific reason from the list above>
```

Do not report DONE for anything you have not personally watched build and
pass, and do not report a falsification you have not personally watched go
red. Paste real command output, not a description of it.
