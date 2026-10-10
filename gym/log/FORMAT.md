# The learner's event log

One text file per learner, **append-only**: nothing in `gym/log/` rewrites,
truncates or deletes it. One line per event. The clock is always an argument
(`time`, milliseconds since the Unix epoch), never read inside the logic, so a
log can be replayed and tested exactly.

## Line format

Fields are separated by a single TAB. The first two are always the time and the
kind of event.

```
TIME <TAB> attempt       <TAB> ITEM <TAB> ANSWER <TAB> CONFIDENCE <TAB> VERDICT <TAB> HINTS <TAB> SECONDS <TAB> TAPPED <TAB> GRADE
TIME <TAB> hint_shown    <TAB> ITEM <TAB> RUNG
TIME <TAB> session_start
TIME <TAB> session_end
TIME <TAB> session_plan  <TAB> IDS <TAB> PHASES <TAB> REASONS
TIME <TAB> session_next  <TAB> ITEM
TIME <TAB> cooldown_note <TAB> NOTE
```

| field | meaning | values |
| --- | --- | --- |
| `TIME` | when, in ms since the epoch | 1 to 18 digits |
| `ITEM` | the item id | non-empty |
| `ANSWER` | exactly what the learner typed | any text, escaped (below), cut to 2000 bytes |
| `CONFIDENCE` | the confidence stated before the answer | `50`, `70`, `90` or `99` |
| `VERDICT` | what the checker said | `correct`, `incorrect` or `unparseable` |
| `HINTS` | rungs of the ladder used before answering | `0` to `4` |
| `SECONDS` | time taken | 1 to 7 digits |
| `TAPPED` | the learner asked for the full answer | `yes` or `no` |
| `GRADE` | the learner's own grade, if given | empty, `correct`, `partial` or `incorrect` |
| `RUNG` | which rung was shown | `1` to `4` |

`attempt` lines have exactly 10 fields, `hint_shown` 4. The
`GRADE` field is last and may be empty, so such a line ends in a TAB.

`session_start` and `session_end` have 2 fields, `session_plan` 5 and
`session_next` and `cooldown_note` 3. `NOTE` is the one line the learner wrote on the cool-down screen
(escaped like `ANSWER`, non-empty); it is written by the window and no metric reads it.

## The current session

A running session is nothing but these lines; no other file holds state, so every
`gym` command is a function of the log and the clock it is given.

- `session_plan` is the record of the current session (the last one in the log).
  `IDS` is the comma-separated item ids in the order they will be met, `PHASES`
  the comma-separated phase of each (`warmup`, `main` or `transfer`), `REASONS`
  one line per item (the planner's "why am I seeing this", with line breaks
  escaped). The three lists must have the same length and at least one item, or
  the line is skipped like any bad line. The plan is fixed when the session
  starts; later answers never change it.
- `session_next` says the learner moved on from `ITEM`. It is appended only once
  the item has an attempt (an answer, or a tap-out).
- The item on screen is the plan's item number *n* + 1, where *n* is the count of
  `session_next` lines after the plan. It is **waiting** when the attempts after
  the plan number *n*, **committed** when they number *n* + 1. A hint is given
  only for a committed item, never in the `warmup` phase, never after a tap-out,
  and at most four rungs; each is a `hint_shown` line. The session is **over**
  when *n* equals the number of items, and **closed** after a `session_end`.
- Starting a session while another is open appends a `session_end` first, then
  `session_start`, then the new `session_plan`.
- A tap-out is an `attempt` with an empty `ANSWER`, verdict `incorrect`, `HINTS`
  4, `TAPPED` `yes` and the confidence given (50 when none is).

## Escaping

`ITEM` and `ANSWER` are escaped so they cannot contain a TAB or a line break:
backslash is `\\`, TAB is `\t`, line feed is `\n`, carriage return is `\r`. An
unknown escape (`\q`) reads back as written.

## Reading a log

`log_replay` reads the whole file. A line that is not exactly one of the shapes
above (wrong field count, a number that is not digits, a confidence of 80, an
unknown kind, a half-written last line) is **skipped and counted**, never fatal;
a blank line is neither. A log that does not exist replays as an empty one.

The result keeps the good events as parallel tables (time, kind, fields) in file
order, plus `skipped` and `lines`. Tables derived from it:

- per item: how many attempts and the time of the latest (`log_item_summary`);
- per concept: the same, summed over the items of each concept, from a pack's
  item-to-concept pairs (`log_concept_summary`).

## Writing a log

`log_record_attempt`, `log_record_hint`, `log_record_session`, `log_record_plan`
and `log_record_next` build the line,
refuse it unless the reader would accept it (answering -1 and writing nothing),
and append it with one write at the end of the file, creating the file if it is
not there.

## Free answers: pending attempts and the `graded` line

The checker cannot decide a `free` answer (prose or a proof). Such an answer is logged as an ordinary `attempt`
with the verdict `pending`, and later settled by one more line:

```
TIME <TAB> graded <TAB> ITEM <TAB> VERDICT <TAB> SOURCE <TAB> MET
```

| field | meaning | values |
| --- | --- | --- |
| `VERDICT` | the verdict the pending attempt takes | `correct` or `incorrect` |
| `SOURCE` | who graded it | `model` (the grader) or `self` (the learner marking the rubric) |
| `MET` | the rubric lines marked met, one 1 or 0 each | `1,0,1`; empty for a model grade; at most 64 bytes |

A `graded` line has exactly 6 fields. **The file is never rewritten**: when it is replayed, the verdict of the
newest `pending` attempt at the same item *before* the graded line is replaced, in memory only, by the graded
verdict (`log_settle`), so every reader sees one attempt with its final verdict. An attempt still `pending` counts
for nothing: the planner, the scoreboard and the cooldown skip it. `gym next` refuses while the item on screen
is pending. A `graded` line with no pending attempt before it changes nothing. A model "partly" is logged as
`incorrect`.
