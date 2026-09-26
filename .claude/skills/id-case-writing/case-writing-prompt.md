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

## Where a new fixture goes

A `given` may name any function anywhere in the program, so a fixture you
write does not have to sit beside the function under test. Put it in the
nearest file with fewer than 3 functions, or the nearest directory with fewer
than 3 entries. To find them, run (after any build, which keeps the binary
current):

```sh
idc/.idc-cache/idlayout --room {PROJECT_PATH} DIR
```

It prints up to 10 rows, nearest to DIR first: `file PATH N` (N more
functions fit) and `dir PATH N` (N more entries fit). `idc/.idc-cache/idlayout
{PROJECT_PATH} build` lists every layout violation at once, where a build
stops at the first. Only if nothing reasonable has room, group two or more related
existing files into a new subdirectory named for what they share. Never name
it after one of the moved files: `x/x.id` (a file named like its directory),
`x.id` beside `x2.id` (numbered siblings), directories named like their parent,
and generic names (helper, util, misc, common, stuff, tmp, temp) are all
compile errors.

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
- Scalar parameters (`int`, `string`, ...) are passed by value: on the
  expected side their positions always echo the literal you passed, never a
  value the function computed. Only list arguments carry changes back.
- `main` needs two cases like any other function.

**Module state — `given`, `then`, `(import NAME)`** (only when the packet
shows your function reads or writes an export):

```
given SETUP (ARGS):(EXPECTED) then CHECK:(VALUE)
```

- `given SETUP` names a zero-parameter `void` function from the packet's
  candidate list (or a nearby fixture) that runs before the call, before
  arguments are built.
- Setups compose: `given A given B (ARGS):(EXPECTED)` runs `A`, then `B`,
  before the call. A later setup that re-exports a name replaces what an
  earlier one left there.
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
- A list argument in `then calls NAME:(ARGS)` is compared in its state at
  the end of the case, not its state when `NAME` was called.

**What a function reads, and a function whose job is to stop:**

- `stdin "TEXT"`, after any `given`s and before the argument tuple, is the
  case's whole standard input: `read_all()` returns it, `input()` returns its
  lines in order and then `""`. Without it a case gets empty stdin. One per
  case, and TEXT must be a string literal:
  `given full_env stdin "ident x\n" ():() then last_tkind:("ident")`
- `then traps:("TEXT")` passes only if the call stops its process with a
  runtime trap (or a signal) whose message contains TEXT. The expected side
  must be `()`, and no other `then` may accompany it:
  `():() then traps:("out of range")`

## Writing cases that mean something

Before writing any case, answer: **what would have to break for this to go
red?** If the answer does not name the behaviour the function exists to
perform, do not write that case — it is decorative.

Specific patterns that have wasted real time and must not recur:

- `then prints:("")` on a function that does not print is a tautology — true
  of nearly every function whether or not it works.
- `then traps:("uninitialised export")` in a case with no `given` proves only
  that the runtime guards an unset export, which is true of any function that
  reads one. It is not one of a function's two behaviours.
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
   idc/bin/idc {PROJECT_PATH} --allow-untested --emit-c SCRATCH/idxcheck.c; echo EXIT $?
   ```
   (from the repo root that contains `idc/`; SCRATCH is a directory of your
   own, never a fixed `/tmp` name another agent could be writing too). A
   clean run is EXIT 0 and prints nothing but warnings; a failing case prints
   `FILE:LINE: test failed: ...` naming it. A dead build can print nothing at
   all, so always check EXIT.
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

- The state it needs can only be made by a function that takes parameters,
  or only exists partway through the function itself, so no chain of
  zero-parameter `given`s can build it.
- An honest case would need a program outside the project's Nix devshell,
  would leave files behind, or would push the project's build past 60
  seconds.
- The packet's candidate `given`/`then` lists are both empty for an import
  this function genuinely needs, and you cannot justify writing a new
  zero-parameter setup/check yourself within this batch's file/directory
  slot budget.

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
