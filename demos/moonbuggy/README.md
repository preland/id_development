# Moon Buggy — a real-time side-scroller in id

Drive a buggy across the lunar surface on the id game engine (bundled under
`engine/`, since a project links no other project). The terrain scrolls toward
you and craters open in the ground; jump them or crash. The project is laid out
as `engine/` (the bundled engine) and `game/` (the buggy's own code).

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
