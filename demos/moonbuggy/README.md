# Moon Buggy — a real-time side-scroller in id

Drive a buggy across the lunar surface on the id terminal engine, idstd's
`sys/io/term` (`term_init`, `term_text`, `term_render`, `term_key`). The terrain
scrolls toward you and craters open in the ground; jump them or crash. This game
and `demos/solitaire` each used to bundle a copy of that engine under `engine/`;
the project is now only `game/` (the buggy's own code).

```sh
./idc.py demos/moonbuggy -o moonbuggy
./moonbuggy
```

## Controls

- **space** (or **j**) — jump
- **q** — quit
- **r** — restart after a crash

## How it works

The game runs the engine's frame loop on a clock (`sleep_ms(70)` per frame).
Each frame it reads the latest key, applies vertical physics (a velocity +
gravity parabola), scrolls the terrain one column and spawns craters at random,
checks for a crash (on the ground over a crater), repaints, and flushes. All
state lives in one exported `mb` list; the terrain is the exported `ground`
list. See [`mb.id`](mb.id) for the index map.
