# gym/ui

The Mental Gym window, part of the one `gym` program: a pure reducer, a paint, an engine layer that does what the
buttons ask through `gym/session` (so every button appends to the log), and a loop and a script replay around them.

```
idc/bin/idc gym -o gym
gym                                              the window (960 x 640), same as gym window
gym window --pack DIR --log FILE                 the window on a pack and a log; a session is planned when none runs
gym window ... --script S.txt --dump             replay a script, print the state it ends in
gym window ... --script S.txt --render-after O   replay a script, write the screen it ends on (binary PPM)
GFX_MAX_FRAMES=60 idc/tools/headless.sh gym window --pack gym/packs/probability --log LOG
```

`--now MS` (the engine's clock at the start; default the real clock), `--seed N` and `--url URL` are the options of
every other command, read by the same table. The engine's time is that clock plus the seconds the session clock has
counted, so a script that ticks the same seconds writes the same log byte for byte.

## Layout of the tree

| dir | job |
| --- | --- |
| `type/` | the three structs: `Session` (the state), `Event`, and `World` (the pack, the record of the log, the model url) |
| `reduce/` | the window's own rules (what is typed, picked, shown, ticked); reads no clock, no file, no window |
| `engine/` | the shell around the reducer: `gym_deliver` sends an event to the reducer or does the engine operation, `gym_derive` reads the whole screen state back from the log and the pack |
| `page/` | the idml page (in `conf.id`), tiling, the sixteen buttons and two text boxes, where each goes, which are enabled |
| `paint/` | state to pixels: session bar, the three screens, the widgets over them |
| `run/` | the window loop, mouse and key events, the script replay, the dump, the PPM writer, the command line |
| `golden/` | scripts, the logs two of them start from, what `--dump` must print for them, and the cases that replay them |

Files named `probe*` and `fixture*` and functions `gym_fixture_*` exist only for the inline cases.

## What is the window's and what is the log's

The state is `Session { int[] cells; string[] texts }` (`gym_cell_*`, `gym_text_*` in `conf.id`). Some of it is the
window's own and is never in the log: the screen showing, the picked confidence, the typed answer, the open
definition, the session clock, the cool-down line being typed. Everything else is read back after each engine
operation by `gym_derive` (`engine/derive.id`):

| from the log (`session_view`, the attempt, the hint events) | position in the plan, how many items, stage (waiting, committed, tapped out), correct, hint rungs showing, phase |
| --- | --- |
| from the pack | prompt, then (after the attempt) the reference answer and the rubric lines, the hint rungs |
| from `gym/score` | the five metric lines and the confidence table, as `gym score` prints them |
| from `session_cool_down_text` | the cool-down lines, once the session is closed |

So closing the window and opening it again on the same log lands on the same item. The hint rungs are the pack's
words unless the model reworded one in this window (the log keeps the rung number, not the words).

## Events

`Event { int kind; int value; string text }`, kinds `gym_event_*`:

| kind | name | does |
| --- | --- | --- |
| 1 | type | replaces the answer while the rep waits |
| 2 | confidence | 50, 70, 90 or 99 while the rep waits |
| 3 | submit | engine: `session_answer_item` (the gate says why not: no confidence, empty answer, an answer that cannot be read as the item's kind) |
| 4 | hint | engine: `session_hint_next`; gate: after a committed attempt only, never in the warm-up, never after a tap-out, four rungs |
| 5 | tap_out | engine: `session_tap_out`; only while the rep waits (after the attempt the answer is already on screen) |
| 6 | tick | the session clock moves on by `value` seconds; the seconds left in the phase are derived |
| 7 | next | engine: `session_move_on`; after the last item the session closes and the cool-down shows |
| 8 | screen | shows screen `value` (0 rep, 1 scoreboard, 2 cool-down) |
| 9 | define | opens a metric's definition, or closes it |
| 10 | note | the cool-down line being typed |
| 11 | key | Enter does what the screen's main button does (submit, next, keep the line), Esc closes a definition, Tab changes screen |
| 12 | save | engine: the cool-down line goes to the log as a `cooldown_note` event (log/FORMAT.md) |

Kinds 3, 4, 5, 7 and 12 are engine operations: `gym_deliver` calls `gym_perform`, which calls the engine with the
clock `origin + elapsed`, then `gym_adopt` replays the log and derives the new state. A refusal comes back as the
`notice` line on the outcome card and nothing is written. The other kinds are the reducer's, `gym_reduce(Session,
Event) -> Session`. The buttons are enabled by the engine's own gates (`session_answer_gate`, `session_hint_gate`,
`session_move_gate`, through `gym_seen` in `page/seen.id`), so Hint is greyed before the commit and in the warm-up.

A click in a script (`click X Y`) and in the window is the same thing: the button under the pointer sends its event.

## The session bar

The phase is the plan's: warm-up, main set and transfer are the phases the planner gave the item in play
(`log/FORMAT.md`), and the cool-down starts when the session closes (the cool-down screen shows by itself). The tick
clock only says how long the phase has run: seconds left is the phase's length (5, 13, 5 and 2 minutes) less the time
since the phase began, never below nothing; after the cool-down's two minutes the bar says the session is finished.

## Scripts

Words: `type TEXT`, `confidence N`, `submit`, `hint`, `tapout`, `next`, `tick SECONDS`, `screen N`, `define N`,
`note TEXT`, `save`, `key NAME`, `click X Y`; a line starting with `#` is a note. `golden/` holds seven, the dump each
must end in, and the two logs (`warmup.log`, `score.log`) the warm-up and scoreboard scripts start from:

```
gym window --pack gym/packs/probability --log LOG --now 1760000000000 --url http://127.0.0.1:1 --script gym/ui/golden/gate.txt --dump | diff - gym/ui/golden/gate.out
```

The same seven are cases (`golden/replay.id`), so they run on every build.
