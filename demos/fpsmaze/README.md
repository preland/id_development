# `fpsmaze` — a first-person shooter in a randomly-generated maze

A GPU-rendered, first-person view inside a maze that's carved fresh every
run: walk through it (WASD), turn to look around (Q/E), and shoot (Space)
red target cubes for score. Walls block movement — you can't walk through
them.

```sh
./idc.py demos/fpsmaze --backend backends/gl -o fpsmaze && ./fpsmaze
```

## Controls

| key | action |
| --- | --- |
| `w` / `s` | move forward / backward (along your facing direction) |
| `a` / `d` | strafe left / right |
| `q` / `e` | turn left / right |
| `space` | shoot (raycast along your facing direction) |
| Esc | quit (so does the window's close button) |

Arrow keys are **not** wired up: `backends/gl/gl_linux.c` only queues a key
when `XLookupString` produces an actual character (`if (n > 0)
key_push(...)`), and arrow keys don't produce one under the default X11
keymap — the same limitation `demos/gl3dgame`'s README notes. Q/E stand in
for turning instead.

## The maze: randomized DFS on an odd/even grid

`game/sim/maze` represents the maze as a flat `grid_w() x grid_h()` (15x13)
`int[]` (`1` = wall, `0` = open), using the classic "maze on a grid" trick:
**even** coordinates are always-wall pillars, **odd** coordinates are either
carvable *room* cells or the *wall* cell exactly between two adjacent rooms.
Generation is a randomized DFS / recursive backtracker
(`game/sim/maze/gen`), driven by two exported lists (`stackx`/`stackz`) used
as a stack via `id`'s own `push`/`pop` — no hand-rolled stack pointer needed:

1. Start at room `(1,1)`, mark it open, push it.
2. At the top of the stack, gather which of the 4 neighboring rooms (2 grid
   steps away) are still un-carved (`game/sim/maze/gen/logic/valid`).
3. If any exist, pick one uniformly at random (the Park-Miller PRNG in
   `game/util/rng`, seeded from `ticks()` so every run gets a different
   maze), knock down the wall between, and push the new room.
4. If none exist, pop (backtrack).
5. Repeat until the stack empties — every reachable room has been visited
   exactly once, producing a perfect maze (a spanning tree: exactly one path
   between any two rooms).

Verified structurally correct with a throwaway fixed-seed harness (single
width walls, fully connected, matches the odd/even grid convention):

```
###############
#...#.....#...#
###.#.###.#.#.#
#.#.#.#.#...#.#
#.#.#.#.#####.#
#...#.......#.#
#.#########.#.#
#.#.....#...#.#
#.#.###.#.###.#
#...#...#...#.#
#####.#######.#
#.............#
###############
```

## The sine-table trick

`id` has no `sin`/`cos` builtin and no reliable float literals to compute
one at runtime, so `game/util/trig/table.id` hardcodes a **91-entry quarter
wave** (`sin(0deg)*1000 .. sin(90deg)*1000`, computed offline in Python and
pasted as an `int[]` literal — the same "precompute it, paste it" idiom
`game/sim/maze/gen/core/dirs`'s direction table and `demos/moonbuggy`'s
craters use). `game/util/trig/sincos.id` + `quadhelp.id` fold any integer
degree into the table via quadrant symmetry:

```
q = (d mod 360) / 90         r = (d mod 360) mod 90
q=0: sin(d) =  table[r]        q=1: sin(d) =  table[90-r]
q=2: sin(d) = -table[r]        q=3: sin(d) = -table[90-r]
cos(d) = sin(d + 90)
```

Verified against known values: `sin(0)=0 cos(0)=1000`, `sin(90)=1000
cos(90)=0`, `sin(180)=0 cos(180)=-1000`, `sin(270)=-1000 cos(270)=0`,
`sin(45)=707` (≈√2/2·1000), `sin(-90)=-1000`, `sin(450)=1000` (wraps mod
360) — all correct.

Player yaw is a plain integer 0..359 (`game/sim/actors/player/state.id`).
The **forward vector** is derived so that a world point at `camPos +
forward*d` lands on the camera's `-Z` axis after `view =
rotate_y(-yaw)*translate(-cam)` (matching `backends/gl/gl.h`'s
column-vector, "b-applied-first" `gl_mat_mul` convention):
`forward = (-sin(yaw), -cos(yaw))`, and the strafe/"right" vector is forward
rotated -90 degrees: `right = (cos(yaw), -sin(yaw))`
(`game/sim/actors/player/move/vec`). Both are used for WASD movement *and*
for the shot raycast's direction.

## Movement, collision, and the raycast

**Collision** (`game/sim/actors/player/move/collide`): a movement delta is
applied one axis at a time (x, then z), each committed only if the
destination world point's grid cell (`game/sim/maze/coords`'s
`cell_x`/`cell_z`, the algebraic inverse of the grid→world mapping used to
place walls) isn't a wall — this makes the player slide along a wall on a
diagonal bump instead of stopping dead. The player is treated as a point,
not an AABB (a scope cut, see below).

**Shooting** (`game/sim/actors/target/hit/cast`): Space fires an integer
DDA — walk `shoot_step()` (150 milli-units) at a time along the facing
direction, up to 60 steps, checking each step's cell for a target (score +
respawn elsewhere) or a wall (stop). This is the same "step and check" loop
shape as the collision check, just iterated instead of one-shot.

## Verified

Clean build (only the expected backend-extern-linking warnings, same as
every `--backend` demo in this repo):

```
$ tools/devshell.sh './idc.py demos/fpsmaze --backend backends/gl -o /tmp/fpsmaze'
demos/fpsmaze/game/sim/gfx/draw/cells/targets/targetrow.id:3: warning: call to function 'gl_set_modelview' which is not defined in any input file; it must be provided at link time
... (11 more identical-shape warnings, one per gl_*/gfx_* call -- expected, see backends/gl/README.md)
```

Headless run, `GFX_MAX_FRAMES` self-terminating:

```
$ GFX_MAX_FRAMES=40 /tmp/fpsmaze
gl_linux: opened 800x600 window, GL_RENDERER=AMD Radeon RX 7900 XTX (radeonsi, navi31, ACO, DRM 3.64, 7.0.10) GL_VERSION=4.6 (Compatibility Profile) Mesa 26.1.1
gl_linux: rendered 1 frame(s)
gl_linux: resized to 930x1880, viewport updated
gl_linux: resized to 3840x2160, viewport updated
gl_linux: GFX_MAX_FRAMES=40 reached, synthesizing quit
gl_linux: closing after 41 frame(s) rendered
cell=(1,1) xz=(-12000,-10000) yaw=0 score=0
$ echo $?
0
```

`GL_RENDERER` confirms real GPU rasterization; the "resized to..." lines are
Hyprland auto-tiling the new window (expected in this environment, and proof
the live per-frame `gl_aspect_x1000()` projection rebuild — see
`game/sim/gfx/scene/view.id` — is exercised, not just theoretical).

**Real interactive input**, driven with `xdotool` against the live GPU
window (`DISPLAY=:0`, `GFX_MAX_FRAMES` only as an eventual safety net):

```
$ xdotool key --window $WID w w w w w d d d e e space   # (with small delays between)
...
cell=(1,1) xz=(-12000,-10000) yaw=0 score=0
cell=(1,1) xz=(-12000,-10000) yaw=0 score=0
cell=(1,1) xz=(-11790,-10350) yaw=8 score=0
```

`xz` moved from `(-12000,-10000)` to `(-11790,-10350)` (forward+strafe
composed) and `yaw` moved from `0` to `8` (Q/E turning) — both confirmed
live against the real GPU/X11 path. (This particular run's target didn't
happen to be in the line of fire, hence `score=0` here; see below for a
direct confirmation of the hit path.)

**Hit/score/respawn**, confirmed with a direct call (same functions the
real raycast uses, forcing a known target position first):

```
score=0 t0=(1,1)
try_hit(1,1)=1
score=1 t0=(3,3)
```

**Full raycast walking to a target and scoring**, player at `(1,1)` facing
east (`yaw=270`, target forced to grid cell `(3,1)`, two rooms east):

```
before score=0
after score=1 steps=20 t0=(3,3)
```

The ray walked 20 steps (`20*150=3000` milli-units) and registered the hit
as soon as it entered the target's cell span (well before reaching its
exact center at `4000` milli-units away) — confirming the DDA + per-cell
hit test both work end to end, not just the scoring side effect in
isolation.

**Player movement + wall collision**, walking forward repeatedly from the
same start: `z` decreases by `70` milli-units per step until it hits the
maze's boundary wall, then **stops exactly there** and further forward
presses have no effect — confirmed collision blocks movement at the correct
boundary, not one cell early/late:

```
x=-12000 z=-10000 ... cell=(1,1)
x=-12000 z=-10070 ... cell=(1,1)
...
x=-12000 z=-10980 ... cell=(1,1)   <- last successful step
x=-12000 z=-10980 ... cell=(1,1)   <- repeated: further "w" presses blocked
```

## The `id` / native split

Exactly the division of labor `backends/gl/README.md` documents: **all**
matrix math (rotation, translation, projection, multiplication) lives
natively in `gl_linux.c`; `id` only ever threads opaque matrix **handles**
and plain integers, milli-units, and packed `0xRRGGBB` colors. Both view and
projection matrices are rebuilt **fresh every frame**
(`game/sim/gfx/scene/frame.id`) rather than held across frames, since the
native matrix pool is an unfreed ring buffer (`backends/gl/README.md`'s
"known rough edges") — the projection specifically is rebuilt from the
*live* `gl_aspect_x1000()` every frame so a window resize never stretches
the image.

## Project tree (rule of 3)

Every directory holds at most 3 entries (`.id` files + subdirectories), every
function at most 3 actions, nesting never exceeds 2 deep, and no function
duplicates another's logic (idc's own compile-time checks caught several
attempts at this while building — e.g. `right_dz()` turned out to compute
exactly the same value as `fwd_dx()` by construction of the rotation, so it
just calls it instead of repeating the expression).

```
demos/fpsmaze/
  main.id                    -- gfx_open, game_init(), loop()
  loop/                       (2 entries)
    loop.id                  -- spin/tick, same shape as demos/gl3dgame/loop
    run/                       (3 entries)
      frame.id               -- frame(t): drain input -> render -> status
      status.id              -- throttled "cell/xz/yaw/score" stdout line
      input/                    (2 files: drain.id, handle.id --
                                  drains every buffered key per frame,
                                  since auto-repeat can queue more than one)
  game/                        (3 entries)
    world.id                 -- game_init()/init_actors(): seed, carve, spawn
    util/                       (3 entries)
      trig/                       (3 files: table.id, sincos.id, quadhelp.id
                                    -- the sine table, see above)
      rng/                        (3 files: Park-Miller PRNG, same generator
                                    demos/gl3dgame and demos/moonbuggy use)
      config/                     (3 files: dims.id, tune.id, tune2.id --
                                    every tunable constant, centralized)
    sim/                         (3 entries)
      maze/                        (3 entries: grid/, gen/, coords/ --
                                     storage, randomized-DFS generation, and
                                     the grid<->world coordinate mapping)
      actors/                      (3 entries: player/, target/, input/)
      gfx/                         (3 entries: mesh/, scene/, draw/ --
                                     cube geometry, view/projection setup,
                                     and the per-cell draw loops)
```

72 `.id` files in all. See each subtree's own files for narrower comments
(every file explains its own reasoning inline, following this repo's
existing convention).

## Known rough edges

- **The player is a point, not an AABB** — collision only checks the
  destination cell of the player's exact position, not a footprint radius.
  Fine at this grid spacing (walls are a full grid cell wide, `wall_half()`
  is half that), but a corner-clip is theoretically possible right at a
  cell boundary; not observed in testing.
- **No floor/ceiling distinction in the walls** — wall cubes span from
  `-wall_half()` to `+wall_half()` in Y and the camera sits at `eye_y()=0`,
  dead center; there's a single floor plane (`game/sim/gfx/mesh/objects/floor`)
  for depth grounding but no separate ceiling mesh.
- **Target respawn doesn't exclude the player's current cell or other
  targets' cells** — same scope cut `demos/gl3dgame`'s README notes for its
  own single target; with `num_targets()=3` a rare double-occupied cell is
  cosmetic at worst.
- **Arrow keys don't work** (see Controls above) — a `backends/gl` platform
  limitation (`XLookupString` returns no string for them under the default
  keymap), not something this demo's `id` code can work around without a
  native backend change.
- **Immediate-mode draw calls per wall cell** — `draw_walls` issues one
  `gl_set_modelview` + `gl_draw_tris` call per wall cell every frame (up to
  ~100 for this grid size); fine for a demo at this scale, but a larger maze
  would want instancing or a baked static VBO instead of walking the grid
  fresh every frame.
- **`id` has no stderr-specific print** — game-state lines (`cell=...`) and
  the backend's own frame-count/resize logging (`gl_linux.c`) both land on
  the same streams an unredirected terminal shows together, same as every
  other `--backend gl` demo in this repo.
