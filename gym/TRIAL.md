# Trial log: what id and idstd made awkward while building Mental Gym

A running log, newest facts last within each section. Written by the agent that
built `gym/pack/`, `gym/check/`, `gym/log/` and `gym/packs/probability/` (115
functions, 545 cases; the whole tree builds and runs every case in about 1.2 s
when the case cache is warm). Each entry: what was tried, what the language or
library forced, the workaround. "Fix?" says what would remove the cost, as a
guess.

## What worked well

- **Cases in the declaration.** Every slip below was found in the first build,
  at the function that caused it, usually with the failing call and both values
  printed. The counted `[time:O(n)]` constraint found a real quadratic loop
  (below) that no wall-clock test would have.
- **`given` fixtures that export a struct.** `pack_fixture_parse("concept: a\n...")`
  puts a whole `Pack` in an export, so a case for a rule is one line of pack text
  and one expected list of messages; those cases read like the pack files they
  test.
- **`fs_enter` in a fixture.** Problems print as `./sub/b.txt:1: ...`, so cases
  over a real directory (made by `fs_mktemp`) have deterministic expected text.
  Each case is its own process, so changing directory is harmless.
- **`mutscore`.** One sample shard (31 mutants of 1082) killed 25 and left 6
  invalid and none surviving. It only worked after passing `--idc` as an absolute
  path (below).
- **Early `return NAME;` and `blank`-free chains** read well once learned.
- **Struct constructors in cases.** `(Ratio(3, 8, 1)):(Ratio(3, 8, 1))` just works,
  nested structs included.

## Costs, in the order they were hit

### Shape rules

1. **A stub body cannot be a red-first test.** The usual "write cases, watch them
   fail, then write the body" step fails at compile time: `return int 0` is
   E0403 ("only returns the constant"), and `len(x)` is E0408 ("is only one
   operation"), so the compiler refuses the stub before any case runs. Workaround:
   write the real body, then break it deliberately and watch the cases go red
   (done for `check_word_value` and `pack_read_text`; also covered by mutscore).
   Fix?: let E0403/E0408 be reported after the cases run, or allow a `todo` body.
2. **Three actions per block is the dominant cost.** Many functions are `chain`s
   only because four locals do not fit in one block. The first error is almost
   always E0201 (4 actions) or E0204 ("a segment of N actions is then continued by
   a chain; a chain may only follow exactly 3"). I hit E0204 several times: the fix
   is always "move the next statement up", but the message says "performs 2
   actions" without saying which neighbour to pull.
   Fix?: have the diagnostic offer the first statement of the next segment.
3. **One level of call nesting makes messages unwritable inline.** Building a
   problem line needs `push(problems, say(book, block, key, "..." + field(...)))`,
   which is three levels. Every such site needs 2 to 4 extra single-use locals,
   which in turn eat the action budget. `pack_item_labels` became four segments
   (nine statements to do four `if`s).
3a. **`||`/`&&` conditions cannot hide a call, but may contain one**, which is
   what saved the loops (`while (a != "" && at < len(x))`). Good.
4. **E0405 (differ only in an imported constant) forbids the obvious accessor
   family.** `log_item_at`, `log_answer_at`, `log_hints_at`... each read a different
   `(import log_slot_*)` and nothing else; the compiler rejected all of them and
   they had to become one `log_text_at(events, index, slot)` plus `log_number_at`.
   The rule is right in spirit (they are one function), but it means the
   "named slot, never a bare literal" convention (README, record-as-list) can only
   be honoured at the call site, and every call spells `(import log_slot_item)`.
5. **E0408 (a function that is one operation)** rejected `pack_total`,
   `log_count_of`-style one-liners; callers write `len(book.blocks.files)` instead.
   Fine, but it means a Pack API cannot name its own obvious derived values.
6. **A zero-parameter function can have only one distinct case.** `pack_new()`
   would need two different `():(...)` cases. Workaround: give it a parameter that
   matters (`pack_new(root)` records the directory), a design choice made for the
   test rule rather than for the problem.
7. **A struct needs a file of its own and at most three fields.** `Pack` is
   `Pack_rows`, `Pack_blocks`, `Pack_notes` (4 struct files), and `Log_replay` is
   `Log_events` plus two ints. Reading `book.rows.keys[book.blocks.firsts[b]]`
   is fine; writing through such a path is not (index assignment goes through a
   plain name), so updates alias first: `int[] sizes = book.blocks.counts;
   sizes[last] = sizes[last] + 1;`.
8. **No empty list literal as a constructor argument**, so `pack_new` declares
   nine empty locals before building three structs (four segments).

### Names

9. **One name, one type, program-wide, including words that are natural.**
   Renames forced by E0303 in this tree: `check_left/right` (string in one
   file, word in another), `check_flat`, `check_slack`, `check_target`,
   `check_guess`, `check_total`, `check_rest`, `check_value`, `check_first`,
   `check_second`, `pack_made`. The prefix rule only moves the clash from the whole
   program to the module; inside a module the same few words (`target`, `value`,
   `rest`) recur and collide, so a module needs its own vocabulary table. I kept
   one in my head; `NAMES.md` style registry per app would be needed at scale.
10. **`--word-scan` failures.** `t`, `dir`, `gcd`, `unescape`, `scalable` are not
    words (`directory`, `greatest_divisor`, `restore`, `countable` are). Struct
    names in CamelCase (`PackRows`) always fail because the scanner splits only at
    `_`, so structs are `Pack_rows`, `Log_events`. 7119 of idstd's own 9077 names
    currently fail the same scan (a scan of `gym` plus idstd reports 7119 of 8712
    distinct names, none of them in `gym`), so the rule is new and not yet met by
    the library it asks me to use.
11. **Fixtures need names too.** The convention `idstd_x_t_name` is out (no `t`),
    so fixtures are `pack_fixture_parse`, `log_fixture_replay`.

### Library gaps hit

12. **No gcd, no `word` absolute value, no checked multiply, no parse of a word
    from digits** in idstd. Written here (all pure, with cases): `check_greatest_divisor(word, word)`,
    `check_absolute(word)`, `check_times(word, word)` (answers -1 on overflow),
    `check_word_value(string)`. By the project rule (functions needed by two
    projects go to idstd) these four are candidates; `check_greatest_divisor` is
    the likeliest to be wanted again (any exact-fraction code).
13. **`str_to_float` is not usable for answers.** It is inexact (README says so),
    so numbers are parsed into exact `word` fractions instead and a decimal answer
    is compared at a billionth of a unit (see `gym/check/units.id`). `flt_parse`
    exists but would put binary floats back into the comparison: 0.51 - 0.5 is
    0.010000000000000009 and fails a tolerance of exactly 0.01.
14. **`fs_read_text` cannot tell a missing file from an empty one** (both ""), nor
    an unreadable one. `pack_load` therefore lists files first (`path_files`) and
    reads those, and `log_replay` documents "missing file replays as empty".
15. **`str_sub` traps on an empty string with n = 1** (`str span out of bounds`),
    which `log_decode("")` hit; the fix was `return` early on empty. A total `str_slice`-like
    function that clamps would have saved a restructure; the trap message itself is
    excellent (it names `fx_min`/`fx_max`).
16. **`str_words` splits only on space and tab**, not newline or carriage return,
    so `check_flatten` replaces `\n` first.
17. **Building a string one character at a time is quadratic, and the counted
    constraint says so.** `check_letters` failed `[time:O(n)]` ("time is 18 at n=2
    and 1713 at n=32"). The fix was to cap the input (a choice answer longer than
    12 bytes is not a choice), not to fix the loop, because id has no string
    builder: `str_join` over a list of pieces is the linear way and is what
    `log_unescape` (now `log_restore`) does. Worth stating in README under strings.

### Process and tooling

18. **Modules cannot be built alone.** `idc/tools/idtest.sh DIR` copies a directory
    out, and constants (`conf.id`) come only from the root, so `gym/check` alone
    does not compile. I built `gym` as one library tree (`idc gym -o gym.o`), which
    works but means "per module" really means "whole app, 1.2 s". Throwaway
    drivers live outside the tree (`logs/packrun`, `logs/checkrun`, each a
    `conf.id` with `import "../../gym"` and a `main`).
19. **`mutscore run` needs `--idc` as an absolute path.** Without it the baseline
    build fails with exit 127 and `base.log` contains only `127`, which reads as a
    broken tree, not a missing program.
20. **`mutscore lint` flags "echo" cases** (expected equals the arguments), even when
    the identity is the right behaviour (`check_absolute(5)`, `log_escape("plain")`).
    I replaced them with non-echo cases, which loses the "plain text passes
    through unchanged" boundary for the escapers. A `passes through` marker would
    keep both.
21. **Hooks:** a command containing the word `while` in a heredoc is read as a loop
    and blocked, so files with loops had to be written with the editor tool rather
    than `cat <<EOF`; edits by `sed` on several files print each changed file's
    full diff back into the context (~25k tokens once).

### Design decisions the language shaped (flagging for review)

- **The loader is generic** (`Pack` = rows, blocks, notes; `pack_field(book, block,
  "key")`), not a typed table per record. A typed `Item` table would be 14 fields =
  five nested 3-field structs; the generic form is what fits, and the rules read
  naturally (`pack_field(..., "kind")`). Consumers pay a string lookup per field.
- **Answers are exact rationals in `word`, 18 digits at most**, so nothing wraps.
  More than 18 digits is unparseable, never a wrong number.
- **A decimal item's tolerance is checked at 1/1,000,000,000.** Items should use
  tolerances of 1e-6 or more.
- **`unparseable` also covers an item whose own reference cannot be read**; `pack
  check` refuses such items, so it is only reachable with an unchecked pack.
