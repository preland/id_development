# `gl3dgame` — "Cube Hunter", a real-time interactive 3D game in `id`

Where `demos/gl3d` is a static spinning cube, this is an actual *game*: a
GPU-rendered scene with a player you steer, a target you chase, static
obstacles for depth, and score you rack up, all driven by real WASD input
polled once per frame.

```sh
./idc.py demos/gl3dgame --backend backends/gl -o gl3dgame && ./gl3dgame
```

## The game

- **You** are the blue cube, always drawn dead-center: a chase camera tilted
  down 20 degrees and pulled back 9 units follows you everywhere, so the
  *world* moves around you rather than you moving across the screen.
- **The target** is the spinning gold cube. Walk your cube onto its grid cell
  and you score a point; it immediately respawns at a fresh pseudo-random
  cell elsewhere on the grid.
- **The pillar field** is 8 static gray cubes scattered around the origin —
  obstacles/landmarks with no gameplay effect of their own, there so the
  scene has more than one moving part and so the (enabled) depth buffer has
  something to sort against as you move past them.
- **Controls**: `w`/`a`/`s`/`d` move one grid step (forward/left/back/right on
  the ground plane the camera looks down at); `q` or Esc quits (so does the
  window's close button).
- Movement is **unbounded** — there's no world edge to hit. Since every
  object is drawn relative to your position (see below), the scene looks
  identical no matter how far you wander.

## The `id` / native split

Exactly the division of labor `backends/gl/README.md` documents: **all**
matrix math (rotation, translation, projection, multiplication) lives
natively in `gl_linux.c`; `id` only ever threads opaque matrix **handles**
and plain integers. The one discipline this game adds on top of
`demos/gl3d`: it **never holds a matrix handle across frames**. `demos/gl3d`
builds its projection matrix once at startup and reuses that handle for the
program's whole (short) run; this game instead rebuilds the camera-view and
projection matrices *fresh every frame* (`world/scene/render/frame.id`),
because the matrix pool is a fixed-size ring buffer with no explicit free
(`backends/gl/README.md`'s "known rough edges") — a long play session here
creates far more matrices per frame (one per pillar, per frame) than the
short cube demo ever did, so the pool wraps repeatedly. As long as no handle
survives past the frame it was built in, wrapping is harmless; this game
leans on that instead of on a handle staying valid forever.

All game logic — grid position, collision, scoring, the PRNG, key-to-motion
mapping — is portable `id` with plain integer arithmetic. Only
`gfx_open/poll/close` and the `gl_*` calls cross into native code.

### Camera-relative rendering

Every object's modelview is `view * translate(object_pos - player_pos)`
(scaled to milli-units by the grid spacing, 1600). The player itself is
therefore always drawn at `view`'s own origin — no extra translate needed —
which is what makes "camera follows player" free: nothing about the camera
rig changes when you move, only the *relative* positions of everything else.

### Collision

`world/game/target/hit.id`'s `hit_test()` is an integer AABB check: the
player cube's half-extent (500 milli-units) plus the target's (400) is less
than one grid spacing (1600), so — given grid-snapped movement — the two can
only overlap when `abs(px-tx) = 0 && abs(pz-tz) = 0`. `check_hit()` runs every
frame from `world/world.id`'s `world_update`.

## Project tree (rule of 3)

```
demos/gl3dgame/
  main.id                        -- opens the window, world_init(), loop()
  loop/                           (2 files)
    loop.id                      -- spin/tick, same shape as demos/gl3d/loop
    frame.id                     -- one frame: poll -> update -> render
  world/                          (3 entries)
    world.id                     -- world_init/world_update/world_render
    game/                         (3 entries: state/, input/, target/)
      state/                        (3 entries)
        state.id                 -- the `mb` state list (px,pz,tx,tz,score) + gs_get
        mutate.id                -- gs_set + the generic lset helper
        rng/                       (2 files: rng.id, rng2.id -- Park-Miller PRNG,
                                     the same generator demos/moonbuggy uses)
      input/                        (2 files: keys.id, move.id)
      target/                       (2 files: hit.id, respawn.id)
    scene/                        (2 entries: mesh/, render/)
      mesh/                         (3 entries)
        geom/                         (2 files: corners.id, face.id --
                                        cube geometry parameterized by a
                                        half-extent, generalized from
                                        demos/gl3d's fixed-size cube)
        meshbuild/                    (3 files: vertbuild.id, vertpush.id,
                                        colorbuild.id)
        objects/                      (3 files: player.id, target.id,
                                        pillars.id -- one mesh-init function
                                        per object kind + the static pillar
                                        layout)
      render/                       (3 entries)
        init.id                   -- scene_init(): build all 3 meshes
        frame.id                  -- render(t): rebuild view+proj, dispatch draw
        draw/                        (3 entries)
          draw.id                  -- draw_all/draw_foreground/draw_dynamic
          instances.id              -- draw_player/draw_target/target_mv
          pillars/                     (2 files: loop.id, instance.id)
```

Every directory holds at most 3 entries (`.id` files + subdirectories), every
function at most 3 actions, nesting never exceeds 2 deep — the fractal
decomposition `demos/gl3d` and the other engine demos use, applied to a
stateful, input-driven scene instead of a single static mesh.

## Verified

Inside `tools/devshell.sh` (X11 + GLX + mesa on the `PATH`):

```
$ ./idc.py demos/gl3dgame --backend backends/gl -o /tmp/gl3dgame
$ GFX_MAX_FRAMES=200 /tmp/gl3dgame
gl_linux: opened 800x600 window, GL_RENDERER=AMD Radeon RX 7900 XTX (radeonsi, navi31, ACO, DRM 3.64, 7.0.10) GL_VERSION=4.6 (Compatibility Profile) Mesa 26.1.1
gl_linux: rendered 1 frame(s)
gl_linux: rendered 60 frame(s)
gl_linux: rendered 120 frame(s)
gl_linux: rendered 180 frame(s)
gl_linux: GFX_MAX_FRAMES=200 reached, synthesizing quit
gl_linux: closing after 201 frame(s) rendered
pos 0,0 score 0
pos 0,0 score 0
pos 0,0 score 0
pos 0,0 score 0
$ echo $?
0
```

`GL_RENDERER` confirms real GPU rasterization. Left idle (no key input),
the player never reaches the target, so score stays 0 — exactly the
"fine to leave idle" headless case.

**With real interactive input** (the game genuinely responds to keys, not
just idle-renders): using `xdotool` to focus the window and send actual X11
`d`/`s` KeyPress events at the live GPU window (`DISPLAY=:0`, no
`GFX_MAX_FRAMES` shortcuts, `GFX_MAX_FRAMES=1000` just as an eventual
self-terminate safety net) —

```
pos 0,0 score 0
pos 0,0 score 0
pos 0,0 score 0
pos 1,0 score 0
pos 1,1 score 0
pos 2,2 score 0
score: 1
pos 3,3 score 1
pos 3,3 score 1
...
```

The player walked from `(0,0)` to `(3,3)` one grid step per keypress,
registered the hit on the target that started at `(3,3)`, printed `score: 1`,
and the target respawned elsewhere (subsequent frames hold at `score 1`
since the player stopped moving) — collision, scoring, and respawn all
confirmed live against the real GPU/X11 path, not just inferred from reading
the source.

## Known rough edges

- Movement is one full grid cell per keypress, not continuous/analog motion
  — `gfx_poll()` surfaces at most one key per frame and the backend has no
  key-up events, so "held key = continuous motion" isn't expressible without
  a native change; a discrete "tap to step" feel was chosen instead.
- `id` has no way to print to stderr specifically (only `print()`, which
  writes to stdout — see `idc.py`'s lexer/codegen, there is no such builtin);
  game-state lines (`pos ...`, `score: ...`) go to stdout while the backend's
  own frame-count logging goes to stderr (`backends/gl/gl.h`'s
  `gl_end_frame`). Both show up together in an unredirected terminal run,
  which is what the verification above captures.
- Target respawn doesn't exclude the player's current cell, so on rare
  occasions a respawn could land exactly where the player already is
  (immediately re-triggering a hit next frame). Cosmetic at worst — it just
  means a lucky extra point, not a crash or a stuck state.
- All cubes are flat single colors (no per-vertex gradient like `demos/gl3d`)
  and there's no ground plane — a deliberate scope cut to keep the mesh code
  small; the pillar field stands in for a floor to anchor depth perception.
- Per `backends/gl/README.md`, there's no window-resize handling and no
  lighting; this game's camera also doesn't rotate with the player (a fixed
  top-down-ish chase rig, not a first-person look), which keeps the
  modelview math to translate/rotate compositions instead of needing a
  general look-at matrix.
