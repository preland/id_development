# Diagnostics

> **Status: the foundation is built; most diagnostics are not on it yet.** What
> exists is described under "The record", "The formats" and "Migration status".
> What is not done is under "Next steps". Counts in this file that can change
> (how many diagnostics are migrated, how many cases pass) are asked of the tree
> with the commands given, not written down: see "Querying the state".

The goal: `idc`'s output is good for a person at a terminal and good enough that a
local model such as a Qwen 27B can fix its program from the output alone. The
bar is rustc, Elm and rust-analyzer for the diagnostics, and ruff and clippy for
the fix suggestions. The standing rule since 2026-09-22 is that every diagnostic
names the fix, not only the violation.

## The record

A diagnostic is built in one place, `diag` in
`idc/compiler/parse/mid/names/symbols/check/conflict/more/core/diag/`, and has:

| field | what | in the plain text |
| --- | --- | --- |
| code | `E0123`, stable, one per kind of diagnostic (`docs/ERRORS.md`) | ` [E0123]` at the end of the head line |
| severity | `error`; `id` has no warnings, so no diagnostic is a `warning` (`note` is only the severity of a `related:` line) | `error:` in the head line |
| file, line | where; the line is always known | `FILE:LINE:` at the start of the head line |
| column, end column | the span to underline, in bytes from 1 | not printed; found by `at` |
| message | the violation, one line | the rest of the head line |
| at | the text on that line to underline | `  at: TEXT` |
| why | why the rule exists, one line | `  why: TEXT` |
| fixes | zero or more `help:` lines, each with zero or more edits | `  help: TEXT`, then `  edit: ...` |
| related | other places that matter | `  related: FILE:LINE: note: TEXT` |
| function | the function the diagnostic is in; `tools/iddiag` finds it in the source (below) when the compiler did not print one | `  in: NAME`, added by `iddiag`, not by the compiler |
| follows | the earlier diagnostic this one only echoes (below) | `  follows: FILE:LINE: error: MESSAGE [CODE]`, added by `iddiag`, not by the compiler |

The compiler does not know columns (its tokens carry lines), so a diagnostic names
the text to underline (`at`) and `tools/iddiag` finds it on the line: the first
whole-word occurrence. When the text is not on the line, the line is shown without
a caret and an edit that names it is reported as `unresolved` rather than guessed.
Column plumbing from the lexer (`idlex --cols` already has it) is a next step.

API, in `idc/compiler/parse/mid/names/symbols/check/conflict/more/core/diag/`:

| function | what |
| --- | --- |
| `diag(code, loc, msg, at, why, help)` | head line, then `at`, `why`, `help` lines when they are not empty; raises the failure flag. `loc` is `FILE:LINE` |
| `diag_edit(applicability, op, line, needle, text)` | an `edit:` line for the `help:` before it |
| `diag_related(loc, msg)` | a `related:` line |
| `diag_fn_loc(fn, line)`, `diag_prog_loc(row)`, `tc_at(node)`, `case_loc(case)` | the `FILE:LINE` of a function and a line, a row of `prog`, an AST node, a test case |
| `syn_diag`, `tc_diag`, `case_diag` | `diag` at the token the parser is on (also marks the syntax broken), at an AST node (also counts for the type check cache), at a test case |
| `diag_sig(fn)` | `g(int p, string q)`, for a help line that says how to call it |

An edit is `APPLICABILITY  OP  LINE  NEEDLE  TEXT`, tab-separated, with `\\`, `\n`,
`\t` as the only escapes:

| applicability | meaning (rustc's names, less "unspecified") |
| --- | --- |
| `machine` | applying it gives a correct program (JSON `machine-applicable`) |
| `maybe` | applying it gives a program that may not do what was meant (`maybe-incorrect`) |
| `placeholder` | the text has parts the author has to fill in (`has-placeholders`) |

| op | meaning |
| --- | --- |
| `replace` | the first whole-word `NEEDLE` on `LINE` becomes `TEXT` |
| `after-function` | `TEXT` is added after the function declared on `LINE`: after its return clause and the test cases under it |

**Adding a diagnostic** is: pick the next free code in its group; give the site a
`diag(...)` call with `at`, a one-line `why` and a `help` that says what to write;
add an edit if one is unambiguous; add the `## E0xxx` section to `docs/ERRORS.md`
with an `Incorrect:` and a `Correct:` example (`tests/diagnostics.sh` builds both
and fails when the code is missing from the incorrect one, when the correct one
does not build, and when a code the tree emits has no section); and update the
cases that pin the old text (`then prints:`) deliberately, never by deleting them.
Keep the old message wording when it is already good: the `tests/invalid/` files
and the tools that read `idc`'s output match on it.

## The formats

`idc PATH --diagnostics=human|json|plain` (default `auto`: human when stderr is a terminal, plain when it is piped or redirected; `IDC_DIAGNOSTICS` sets
the default; the flag is the one the driver reads, `tools/iddiag` does the work).
Diagnostics go to stderr in every format, as they always have, and the exit status
does not depend on the format.

**plain** is what the compiler prints and what a build nested inside another
prints. It is grep-friendly: every head line is `FILE:LINE: error: MESSAGE [CODE]`,
so `grep ': error:'` and an editor's problem matcher work on it. The head line of
the human form is not this one (below), which is why the default is auto: a piped
build, which is what every tool that parses `idc`'s output has, prints plain, so
`grep ': error:'`, `casework.sh`, the `tests/*.sh` scripts and the local-model
rails (`models/qwen-id/rails`) see the head they always did. `--diagnostics=human`
or `IDC_DIAGNOSTICS=human` forces the snippet form into a pipe. The indented lines
are only for `tools/iddiag`.

```
a.id:1: error: function 'add' has 0 test case(s); --require-tests needs at least 2 (see docs/TESTS.md) [E0501]
  at: add
  why: a function is finished when two cases pass: ...
  help: write two cases directly under the function, ...
  edit: placeholder	after-function	1		(ARG1_1, ARG1_2):(EXPECTED1)\n(ARG2_1, ARG2_2):(EXPECTED2)\n
```

**human** is plain run through `tools/iddiag`, with rustc's head: `error[CODE]:
MESSAGE`, then `--> FILE:LINE:COLUMN` (the column only when `at` is found on the
line), then `in FUNCTION`, then the source line with a caret run under `at`, then
`= why`, `= help`, `= edit` and `= note` lines, and a summary naming the codes that
have an explanation. When one code repeats, only its first diagnostic prints the
why and help in full; the rest say `(as for the first [E0501] above)`. Colour is on
only when stderr is a terminal, `TERM` is not `dumb` and `NO_COLOR` is unset or
empty; `--color=always|never|auto` overrides.

```
error[E0501]: function 'add' has 0 test case(s); --require-tests needs at least 2 (see docs/TESTS.md)
  --> a.id:1:1
  in add
  |
1 | add(int a, int b) {
  | ^^^
  = why: a function is finished when two cases pass: ...
  = help: write two cases directly under the function, ...
  = edit: add after the function declared on line 1 (fill in the placeholders):
  + (ARG1_1, ARG1_2):(EXPECTED1)
  + (ARG2_1, ARG2_2):(EXPECTED2)
error: aborting due to 1 previous error
Some errors have detailed explanations: E0501.
For more information about an error, try `idc --explain E0501`.
```

**json** is one object per line, for agents and editors, on stderr like the others.
Every line of the stream that is not a diagnostic is `{"kind":"text","text":...}`
and the last line is a summary:

```
{"kind":"diagnostic","severity":"error","code":"E0501","file":"a.id","line":1,
 "column":1,"end_column":4,"function":"add",
 "message":"function 'add' has 0 test case(s); ...",
 "why":"a function is finished when ...",
 "fixes":[{"description":"write two cases directly under the function, ...",
   "applicability":"has-placeholders",
   "edits":[{"file":"a.id","line":4,"column":1,"end_line":4,"end_column":1,
             "text":"(ARG1_1, ARG1_2):(EXPECTED1)\n(ARG2_1, ARG2_2):(EXPECTED2)\n"}]}],
 "related":[],"follows":null,"rendered":"error[E0501]: ... (the human text, without colour)"}
{"kind":"summary","errors":1,"codes":["E0501"]}
```

Lines and columns are 1-based, columns count bytes, an end is exclusive, and an
edit replaces `[line:column, end_line:end_column)` with `text` -- the coordinates of
`idc --fix`'s `@R` records. A fix's `applicability` is `machine-applicable`,
`maybe-incorrect`, `has-placeholders`, `none` (advice with no edit), or
`unresolved` (an edit names text that is not where it says). `code` is `null` for a
diagnostic that has not moved to the record yet. Messages the bash driver itself
prints (a missing argument, a failed native check) are not diagnostics of the
program and are not in the stream; see "Next steps".

`function` is the name of the function the diagnostic is in, or `null`; `follows`
is `{"file","line","code"}` of the earlier diagnostic this one echoes, or `null`.

`idc --explain CODE` prints the `## CODE` section of `docs/ERRORS.md`; the code may
be lower case or a bare number; an unknown code lists the ones that exist.

### Follow-on diagnostics

After a syntax error the parser skips tokens to recover and the later stages read
what is left, so `int x 5;` also gives `unexpected token ';'` and `undefined
variable ';'`. They are kept and tagged, not suppressed: a hidden error is worse than a
labelled one. `tools/iddiag` adds a
`follows:` line to a diagnostic (`run/sum/mark/follow/`), which the human form
shows as `= note: follows from the error at FILE:LINE above` and the JSON carries
as `follows`. The plain form is as the compiler printed it. The heuristic, in order:

1. A diagnostic follows the first earlier syntax error (a code `E01xx`) of the same
   file and the same line, whatever its own kind: the second error the parser
   reports on a line and every semantic error on it are echoes of the first.
2. A semantic diagnostic whose message quotes something that is not a name (its
   first `'...'` starts with a character that is not a letter or `_`, as in
   `undefined variable ';'` or `a block in ':'`) follows the nearest earlier
   syntax error of its file, the last one at or above its line, else the last one.
   Only recovery makes a symbol out of punctuation.
3. Nothing else is tagged. A real error on the next line of the same function
   (`undefined variable 'z'`) is a mistake of its own and carries no note.

Known gaps: a syntax error that has no code yet (the `syn_err` sites listed under
"Next steps") is not a root, so what follows from it is not tagged; an echo of a
multi-line statement that lands on a later line, and a keyword read as a name
(`undefined variable 'then'` on another line), are not tagged either. The fix for
the first is to give the remaining syntax errors an `E01xx` code.

### The function a diagnostic is in

`in FUNCTION` and `"function"` come from the source: the nearest line at or above
the diagnostic's that begins in column 0 with a name and `(` (`tools/lib/fnhead`),
so a diagnostic on a test case is in the function the case is under, and one above
the file's first function is in none. The compiler prints no such line yet; an
`  in: NAME` line it prints itself would be used as it stands.

### Finding a function: `idc --where`

`idc --where NAME [PATH]` prints `FILE:LINE: SIGNATURE -> RETURN_TYPE` for the
function `NAME` in PATH (a project directory, default `.`) and, when PATH has none,
in the standard library (`--std`, `$IDSTD_HOME`, or the idstd beside the tree).
`FILE::NAME` keeps only the functions of the file whose path ends with FILE. It
reads the source as text (`tools/idwhere`, `tools/lib/fnhead`), so it needs no
build slot and never rebuilds the compiler, so it answers without a cache at the
speed of reading the files (time `idc/bin/idc --where NAME PATH` on the compiler
tree to see; the search goes on into idstd when PATH has no such function).
A cached index was considered and left out because nothing needs it at that speed;
if one is added, key it by function name, not by path. Exit status 1 when no
function is found, with a message that names what to check.

## The rubric

A diagnostic is scored 0, 0.5 or 1 on each of six questions. The scores below are
the author's reading of the text against the questions, not a measurement.

| | question | 1 means |
| --- | --- | --- |
| L | exact location with a source snippet | the line and the text on it, underlined |
| E | what was expected | the rule or the limit is stated, not only the breach |
| W | why the rule exists | one line a reader can accept or argue with |
| F | a concrete fix | what to write, ideally as an edit that applies |
| O | one at a time | one diagnostic per mistake; no cascade of follow-ons |
| C | a stable code | it has one, and `--explain` knows it |

## Phase 1 audit

### Where diagnostics are produced, and how

| stage | where | how it is formatted | call sites (query below) |
| --- | --- | --- | --- |
| lexer | `compiler/lex` | never reports; a block comment becomes one `/*` token for the parser to name | 0 |
| parser | `front/` | `syn_err(pos, msg)` prints `FILE:LINE: error: MSG`, sets `synfail`; `expect_text` is the one site of "expected X, found Y" | `syn_err`, `syn_diag` |
| names and limits | `mid/names/` | `loc_at(fn, line)` or `prog_loc(row)` give the `FILE:LINE: error: ` prefix; each site `print`s it plus a message, and calls `note_failure()` (`var_report` for four of them) | `loc_at`, `prog_loc`, `var_report`, direct `print` |
| types | `mid/types/` | `tc_err(node, msg)`; the file and line come from the node's function and its recorded line | `tc_err`, `tc_diag` |
| structs | `mid/types/registry/.../struct/` | `sd_err(row, msg)` | `sd_err` |
| uniqueness | `mid/form/unique/` | `loc_at` plus `print` | `dup_loc` |
| test cases | `mid/names/limits/shape/cases/` | `case_err(case, msg)`; the line is the case's first token | `case_err`, `case_diag` |
| directory tree | `tools/idlayout` | `lay_msg(path, text)` builds `PATH:1: error: TEXT`; the walk reports every violation | `lay_msg`, `lay_diag` |
| driver | `bin/idc` | `echo "idc: ..." >&2` for its own failures, a handful of `FILE: error:` lines (constants, natives), `idc: internal error` | `echo ... >&2` |
| case failures | the harness the compiler emits (`back/tgt/c/emit/prog/test/`) | `FILE:LINE: test failed: CALL = ACTUAL, expected EXPECTED`; `not run:` for each case whose callee failed; one summary line | `test failed` |
| runtime traps | the C runtime held in `back/tgt/c/runtime/{prelude,extern}.id` | `id: MESSAGE` and exit 1; about a dozen messages; no source location | `id: ` |
| progress | `bin/idc` `progress*` | a one-line live status and a case counter, on a terminal only | `progress` |

Every `diag(`, `tc_err(`, ... site is found with `grep -rn 'tc_err(' idc/compiler` and
`grep -rn 'diag(' idc/compiler`; the tree's own state is asked, not recorded here.
The pinned wording of every diagnostic is also in its function's test cases
(`then prints:`) and in `idc/tests/invalid/*.id` (`// EXPECT:`).

### How often each fires (estimates)

No telemetry exists, so these are judgements from the evidence below and from the
rules' shape. H: met in most sessions of someone learning the language; M: met
by most programs of some size; L: rare.

| category | examples | frequency |
| --- | --- | --- |
| test cases | too few cases, repeated case, case argument counts, case/value types | H |
| size limits | actions per block, nesting depth, functions per file | H |
| names | undefined variable, no such function, scope, import/export | H |
| syntax | expected X found Y, unexpected token | H for a model, M for a person |
| uniqueness | duplicate logic, duplicate name, constant wrapper | M |
| types | return type, argument types, comparisons | M |
| tree shape | entries per directory, generic or numbered names | M (every project's first week) |
| structs, function values, natives | | L |
| runtime traps | index out of bounds, out of memory | M, and always after a build that passed |

### Evidence of what confuses an agent

Sources: the Qwen 27B evaluation (`/home/preland/models/qwen-id/eval/results.jsonl`,
`demo/wordfreq.run1-aborted.stream.jsonl`), the 2026-07-04 usability study, and the
author's own transcripts while building this slice. The eval keeps counts, not the
text of each refusal, so the per-attempt failures are known only where a transcript
survives.

| task (eval, thinking off) | outcome | write calls refused by the build | tool errors |
| --- | --- | --- | --- |
| greeting | pass | 0 | 0 |
| sum | fail | 10 of 10 | 11 |
| wordcount | fail | 14 of 14 | 14 |
| reverse | pass | 2 | 2 |
| primes | pass | 3 | 3 |
| stats | fail | 7 of 7 | 8 |
| fixfail | fail (`test cases deleted`) | 0 | 2 |
| brackets | fail (`not green at idc --check`) | 4 of 4 | 4 |

Five of eight tasks did not end green; the three failures with the most refusals
are the ones where the model tried 7 to 14 times and never converged. The one
transcript that survives (wordfreq) shows the refusal the model had to act on:

```
wordfreq/scan/words.id:17: test failed: words_of("the cat the dog the end") trapped: id: out of memory (12 bytes) (a case may use at most 4096 MiB)
wordfreq/main.id:16: not run: main(0, []) depends on words_of, whose case at wordfreq/scan/words.id:17 failed
idc: 2 case(s) failed; 2 more not run, because a function they call failed a case
...
wordfreq/scan/words.id:12: error: code in 'words_of' is nested too deeply (3 levels); the maximum is 2. Split the inner block into its own function
```

The top confusions, most damaging first:

1. **A trap in a case says what died, not where.** `out of memory (12 bytes)` for an
   infinite push loop names neither the loop nor the function; the model had to
   re-derive the bug by reading its own code. (Runtime traps carry no source line.)
2. **Case-failure floods.** One failing case prints a `not run:` line for every case
   that depends on it: 2 lines in the transcript above, 25 for one wrong expectation
   in a tool with ~60 cases while writing `tools/iddiag`, 100+ for one failed case in
   a function everything calls. The failing line is first, but it is not marked.
   (Collapsed since: see "Next steps", 2.)
3. **A violation at the function line, not the construct.** `nested too deeply` and
   the action limit report the function's line (or the block's), with no snippet and no
   pointer to which block; "split the inner block" does not say which is inner.
4. **A cascade after a syntax error.** `int x 5;` printed three errors: `expected '='`,
   then `unexpected token ';'`, then `undefined variable ';'`, the last of which is an
   artefact of the parser's recovery. A model fixes the last one first.
5. **Wording that names a rule but not the site.** `variable 'code' is declared int here
   but string elsewhere` did not say where elsewhere is (now a `related:` line). The
   duplicate-logic rule compares each *chain segment* on its own, but names whole
   functions: two functions flagged as the same because only their first segments were
   identical cost two builds here.
6. **Link-time and run-time discovery** (the 2026-07-04 study): an unknown builtin used
   to fail at the C linker and a `s.length` miscompiled; the first is fixed, and
   what is left of the study's list is design, not wording.
7. **Rules that need a number from elsewhere:** "too many functions in this file" did
   not say where to put them (the study's answer was "a new directory", because a
   directory then held three entries; that limit is gone, so the message now says
   "another file in the same directory").

### A scored sample of 30

Each cell is before/after for the questions L E W F O C. A diagnostic that has not
moved keeps its before.

| # | diagnostic | L | E | W | F | O | C | before | after |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | expected 'X', found 'Y' (E0101) | .5/1 | 1/1 | 0/1 | 0/.5 | .5/.5 | 0/1 | 2.0 | 5.0 |
| 2 | unexpected token (E0102) | .5/1 | .5/.5 | 0/1 | 0/.5 | .5/.5 | 0/1 | 1.5 | 4.5 |
| 3 | block comments not supported (E0102) | .5/1 | 1/1 | 0/1 | 1/1 | 1/1 | 0/1 | 3.5 | 6.0 |
| 4 | `break` is not inside a `while` | .5/.5 | 1/1 | .5/.5 | 0/0 | 1/1 | 0/0 | 3.0 | 3.0 |
| 5 | stdin's value must be a string literal | .5/.5 | 1/1 | 0/0 | .5/.5 | 1/1 | 0/0 | 3.0 | 3.0 |
| 6 | a block performs N actions (E0201) | .5/.75 | 1/1 | 0/1 | 1/1 | 1/1 | 0/1 | 3.5 | 5.75 |
| 7 | nested too deeply (E0202) | .5/.75 | 1/1 | 0/1 | 1/1 | 1/1 | 0/1 | 3.5 | 5.75 |
| 8 | too many functions in a file (E0203) | .5/.75 | 1/1 | 0/1 | 0/1 | 1/1 | 0/1 | 2.5 | 5.75 |
| 9 | chain after a short segment (E0204) | .5/.75 | 1/1 | .5/1 | 1/1 | 1/1 | 0/1 | 4.0 | 5.75 |
| 10 | undefined variable (E0301) | .5/1 | .5/1 | 0/1 | 0/1 | 1/1 | 0/1 | 2.0 | 6.0 |
| 11 | variable declared twice (E0302) | .5/1 | .5/1 | 0/1 | 0/1 | 1/1 | 0/1 | 2.0 | 6.0 |
| 12 | one name, two types (E0303) | .5/1 | 1/1 | 1/1 | 0/1 | 1/1 | 0/1 | 3.5 | 6.0 |
| 13 | no such function (E0304) | .5/1 | .5/1 | 0/1 | .5/1 | 1/1 | 0/1 | 2.5 | 6.0 |
| 14 | variable belongs to another function (E0305) | .5/1 | 1/1 | .5/1 | 1/1 | 1/1 | 0/1 | 4.0 | 6.0 |
| 15 | variable used outside its scope (E0307) | .5/1 | 1/1 | 1/1 | 0/1 | 1/1 | 0/1 | 3.5 | 6.0 |
| 16 | function already defined (E0401) | .5/1 | .5/1 | 0/1 | 0/1 | 1/1 | 0/1 | 2.0 | 6.0 |
| 17 | same signature and logic (E0402) | .5/1 | 1/1 | 0/1 | 1/1 | 1/1 | 0/1 | 3.5 | 6.0 |
| 18 | function only returns a constant (E0403) | .5/1 | 1/1 | 0/1 | 1/1 | 1/1 | 0/1 | 3.5 | 6.0 |
| 19 | function has too few test cases (E0501) | .5/1 | 1/1 | 0/1 | .5/1 | 1/1 | 0/1 | 3.0 | 6.0 |
| 20 | test case repeats an earlier one (E0502) | .5/.75 | 1/1 | 0/1 | .5/1 | 1/1 | 0/1 | 3.0 | 5.75 |
| 21 | case passes the wrong number of arguments (E0503) | .5/.75 | 1/1 | 0/1 | 0/1 | 1/1 | 0/1 | 2.5 | 5.75 |
| 22 | this case gives a string where a int is required | .5/.5 | 1/1 | 0/0 | 0/0 | 1/1 | 0/0 | 2.5 | 2.5 |
| 23 | comparison mixed with bitwise (E0601) | .5/1 | 1/1 | 0/1 | 1/1 | 1/1 | 0/1 | 3.5 | 6.0 |
| 24 | return clause has the wrong type (E0602) | .5/.75 | 1/1 | 0/1 | 0/1 | 1/1 | 0/1 | 2.5 | 5.75 |
| 25 | cannot compare these types (E0604) | .5/.75 | .5/1 | 0/1 | 0/1 | 1/1 | 0/1 | 2.0 | 5.75 |
| 26 | call passes the wrong number of arguments (E0605) | .5/1 | 1/1 | 0/1 | 0/1 | 1/1 | 0/1 | 2.5 | 6.0 |
| 27 | argument has the wrong type (E0606) | .5/1 | 1/1 | 0/1 | 0/1 | 1/1 | 0/1 | 2.5 | 6.0 |
| 28 | 'put' takes a string, but argument 0 is int | .5/.5 | 1/1 | 0/0 | 1/1 | 1/1 | 0/0 | 3.5 | 3.5 |
| 29 | directory holds more than three entries (E0701) | .5/.75 | 1/1 | 0/1 | .5/1 | 1/1 | 0/1 | 3.0 | 5.75 |
| 30 | runtime trap: index out of bounds | 0/0 | 1/1 | 0/0 | 0/0 | 1/1 | 0/0 | 2.0 | 2.0 |

Totals out of 180: before 85.5, after 159.25 (47.5% to 88.5%). By question, over
the 30 (out of 30): L 14.5 to 24.75, E 27 to 29.5, W 3.5 to 25.5, F 11.5 to 25.5, O 29
to 29, C 0 to 25. The biggest gains are why and the code, which cost nothing to
add; the fix column moved most where the fix was a template (cases, parentheses). Last
among the unmoved are the ones nobody has touched yet (rows 4, 5, 22, 28, 30). The
after scores for L drop to .75 where the compiler names a line but no text to
underline, and none of the scores say anything about how well a model *acts* on a
message: that is measured by running the eval again (next steps).

## Migration status

A diagnostic is migrated when it is built by `diag` with a code, a why and a
help. The status is asked of the tree:

```
grep -rhoE '"E0[1-9][0-9][0-9]"' idc/compiler idc/tools --include=*.id | sort -u    # the codes in use
grep -c '^## E' docs/ERRORS.md                                                       # the codes explained
grep -rnE '[^a-z_](tc_err|syn_err|case_err|sd_err|var_report)\(' idc/compiler --include=*.id | grep -vc ':given'   # not yet migrated
```

| code | diagnostic | message kept from | edit |
| --- | --- | --- | --- |
| E0101 E0102 | expected token; unexpected token, block comment, a `.` or `#!` that starts nothing | yes | |
| E0103 E0104 | float exponent with no digits; float literal that overflows to infinity | new | |
| E0201 E0202 E0203 E0204 | actions; nesting; functions per file; chain after a short segment | head only: the fix text moved to `help` | |
| E0301 E0302 E0303 E0304 | undefined variable; declared twice; one name two types across the program and the library (`related:` the other declaration, the library's when the program's name collides with it); no such function (the builtin list moved to `help`) | head only | |
| E0305 E0306 E0307 E0308 E0309 | variable of another function; calling a variable; scope; named like a function; named like an export | head only | |
| E0310 E0406 | a parameter with a generated name; a function that only forwards to another | new | |
| E0401 E0402 E0403 E0405 | same name (`related:` the first); same logic (`related:` the other); constant wrapper; differ only in an import | yes | |
| E0501 E0502 E0503 E0504 E0505 | too few cases; repeated case (`related:` the first); case arity; expected arity; return arity | yes | E0501: `placeholder` skeleton after the function |
| E0601 E0602 E0604 E0605 E0606 | bitwise and comparison; return type; compare; call arity; argument type | yes | E0601: `machine` replace |
| E0702 E0703 E0704 E0705 E0706 E0707 | tree shape (`tools/idlayout`); E0701 (entries per directory) is retired and the limit is gone | yes | |

### Old to new (the pinned wording)

The head line of each kept its old text with ` [CODE]` appended, so a pin that
matched the old line still matches. These moved text out of the line, and the pins
that named it were updated:

| old (one line) | new |
| --- | --- |
| `... performs 4 actions; the limit is 3 (...) -- continue the function into a chain: ...` | head ends at `return is free)`; the chain advice is the `help` line |
| `code in 'f' is nested too deeply (3 levels); the maximum is 2. Split the inner block into its own function` | head ends at `maximum is 2`; the advice is the `help` line |
| `... takes 1 argument(s), got 0`, `... expects int, got string` | unchanged; `help` shows the signature |
| `no such function 'x'; available builtins: print, ...` | `no such function 'x' [E0304]`; the list is in `help` after `the builtins are:` (`tests/backends.sh`, `tests/self_host_build.sh` follow) |
| `variable 'x' belongs to function 'f'; read it with 'import x'` | head `... belongs to function 'f'`; `help: read it with (import x)` |
| `variable 'x' is declared T here but U elsewhere; a name must keep one type ...` | head ends at `elsewhere`; the rule is `why` |
| `variable 'x' is used on line N ...; a variable exists only from its declaration ...` | head ends at the line facts; the rule is `why` |
| `'x' is an exported global (by 'f'); another variable cannot reuse that name -- read the global with 'import x'` | head ends at `reuse that name`; the advice is `help` |
| `a segment of 'f' performs N actions ... all 3 actions -- move the chain's work ...` | head ends at `all 3 actions`; the advice is `help` |
| `... the same signature and logic as 'g' (defined at F:L); functions must be unique -- remove one ...` | head ends at `(defined at F:L)`; advice is `help`; `related:` names g |
| `function 'f' and 'g' (...) differ only in the imported value they read (...); parameterise one ...` | head ends at the values; advice is `help` |
| `a project directory may contain at most 3 ... but this one has N (.id files and subdirectories); split it into subdirectories (entries: a, b)` | retired with E0701: a directory has no entry limit |
| `'import.id' is now called 'conf.id' -- it holds constants as well as dependencies. Rename it` | head `'import.id' is now called 'conf.id'`; the rest is `why` and `help` |
| `file '...' has a generic name 'x'; name it for what it holds` | head ends at the name; the advice is `help` |

## Querying the state

The compiler's own cases pin the output of every migrated diagnostic, so
`idc/tests/run.sh core core_rest` is the check that none changed unintentionally;
`tests/run.sh invalid diagnostics diagnostics_docs_0 diagnostics_docs_1
diagnostics_docs_2` checks the examples and the formats. Use
`idc/tools/mapgen.sh --check` after adding functions (it regenerates
`compiler/parse/MAP.md`) and `idc/tools/regen_bootstrap.sh --check` after a change to
the compiler.

## Next steps

1. **The remaining diagnostics, by sink.** `tc_err`, `syn_err`, `case_err`, `sd_err`
   and `var_report` sites are the unmigrated ones (the grep above counts them).
   Do them a sink at a time, in the order of the frequency table: `case_err` (case
   values and types), `syn_err` (the `timeout`, `stdin`, `given` and `chain` forms),
   `tc_err`, `sd_err`. Each is a message, a why, a help and a section in
   `docs/ERRORS.md`; none is hard. The records of the ones already done are the
   templates.
2. **Case-failure display.** The format `FILE:LINE: test failed: CALL = ACTUAL, expected
   EXPECTED` is the right shape. The volume is done: the cases that did not run are
   one summary line, `idc: N case(s) failed; M more not run, because a function they
   call failed a case (the first failure was a case of 'words_of' at F:L; ...)`, and
   `IDC_SHOW_NOT_RUN=1` brings back a line for each. Still to do: the code frame of
   the failing case's line, and a name for the function that failed the case in the
   `FILE:LINE:` line itself rather than only in the summary (`--verbose`). A trap
   in a case should name the function that trapped; the runtime knows it. Make a
   case failure a diagnostic: `error[E08xx]: test failed`, so that `--diagnostics=json`
   carries `expected`, `actual` and the `call` as fields. The harness is C emitted
   from `back/tgt/c/emit/prog/test/`; the strings are in the runtime files other
   agents were editing, which is why this slice did not touch them.
3. **Progress output.** `bin/idc`'s live line and case counter are already good on a
   terminal and silent elsewhere. Missing: in `--diagnostics=json` mode, a stream of
   `{"kind":"progress",...}` events so an agent can tell a long build from a hung
   one (the 60-second rule); and an `idc: N errors` count in the TTY status line while
   errors accumulate.
4. **The driver's own messages.** About 85 `echo ... >&2` in `bin/idc` (a missing
   argument, a failed native check, `internal error`) are plain lines. Route the ones that
   are about the program (the native checks print `FILE: error:` already) through
   one `idc_error CODE MESSAGE WHY HELP` function that prints the plain form, and give
   them codes `E09xx`. The rest are usage errors and stay as they are.
5. **Columns from the lexer.** `idlex --cols` records spans for `--fix`; reading them
   in `diag` (a token index in, a column out) replaces `at`'s search with the exact
   span and lets a diagnostic name a token that occurs twice on a line.
6. **Did you mean.** `undefined variable` and `no such function` have the whole
   candidate set in hand (`dvname`, `fnames`, `bnames`); an edit-distance pick
   would turn the help into a `maybe` edit. Written in `id`, it is four short functions.
7. **A syntax error ends the diagnostics: decided, tagging.** After one the AST is
   not what was written, which is what `--fix` already assumes (`synfail`). The
   decision was to keep the later diagnostics and mark the ones that echo the syntax
   error `follows from the error at FILE:LINE above` (see "Follow-on diagnostics").
   What is left: give every `syn_err` an `E01xx` code so that all syntax errors are
   roots, and have the compiler print `follows:` itself, where it knows the token
   positions, instead of `iddiag` guessing from lines.
8. **The runtime traps** carry no location. A trap that names the function and the
   line it came from (the compiler has both at the call that emits the check)
   would remove confusion 1. It changes the generated C, so it waits for the agents
   editing the runtime.
9. **Measure it.** Re-run the Qwen eval (`models/qwen-id/eval`) with this build and
   compare refusals per task with the table above: that, not the rubric, is the
   test of whether the output is good enough to fix a program from.
10. **idlayout**, when several directories overflow, walks the tree once per
    directory for the rooms; cap it at the first few if a tree ever reports hundreds.
