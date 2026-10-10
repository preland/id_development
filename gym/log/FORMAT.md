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

`attempt` lines have exactly 10 fields, `hint_shown` 4, session lines 2. The
`GRADE` field is last and may be empty, so such a line ends in a TAB.

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

`log_record_attempt`, `log_record_hint` and `log_record_session` build the line,
refuse it unless the reader would accept it (answering -1 and writing nothing),
and append it with one write at the end of the file, creating the file if it is
not there.
