# gym: the command line

`idc/bin/idc gym -o gym` builds the program; `gym --help` lists the options. Every command takes
`--pack DIR` and `--log FILE` (the log is the only state, `log/FORMAT.md`) and `--now MS` (the clock,
default the real one), so a whole session can be scripted and replayed exactly. Exit status: 0 done,
1 refused by a rule of the design, 2 a command line that cannot be run. A refusal prints
`refused: ` and the reason; nothing is written to the log.

| command | does |
| --- | --- |
| `gym session start [--seed N]` | plans the session, records it in the log, prints the plan and the first prompt |
| `gym answer --text A --confidence 50\|70\|90\|99 [--seconds N]` | checks the answer, logs the attempt, prints verdict, reference and why; refused without a confidence |
| `gym hint [--url URL]` | the next rung; only after an attempt, never in the warm-up, never after a tap-out; through the model when it answers, else the pack's own words; logs `hint_shown` |
| `gym tapout [--confidence C] [--seconds N]` | shows the answer and the worked example, logs a tapped-out attempt |
| `gym next` | moves on once the item has an attempt; after the last item prints the cooldown and closes the session |
| `gym score` | retention, transfer, calibration, independence, fluency, each with its sample size and definition |
| `gym why ITEM` | the reason the item is on the plan |
| `gym pack check DIR` | validates a pack |
| `gym grade --item ID --text A [--url URL]` | grades one answer through the model (the old gymprobe) |
| `gym` or `gym window` | opens the window (ui/README.md); `--script S.txt [--dump] [--render-after O.ppm]` replays a script on the same engine without one |

Layers: `session/` is the engine (pure functions of a replayed log, plus the operations that append to it),
`cli/` turns options into engine calls and engine results into text, `golden/` replays a scripted session as
cases.
