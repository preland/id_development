# `flyover` — a terrain flyover simulator in `id`

A camera flies forward, forever, over procedurally-generated rolling hills,
hardware-rendered through the GPU backend (`backends/gl`). No floats, no
trig, no bitwise ops anywhere on the `id` side — every piece of "3D math" that
needs real numbers (the PRNG excepted, which is pure integer Park-Miller)
lives in `backends/gl/gl_linux.c`, exactly as `gl.h` intends.

```sh
tools/devshell.sh './idc.py demos/flyover --backend backends/gl -o flyover'
./flyover
```

Close the window (or press Esc / q) to quit. `GFX_MAX_FRAMES=N ./flyover`
self-terminates after `N` frames (see `backends/gl`), which is how this was
verified headlessly against a live GPU without leaving a window open.

## What it does

- Generates a 13×40 grid heightmap (520 cells) with an integer Park-Miller
  PRNG, then smooths it with 3 passes of neighbor-averaging into rolling
  hills — see "Terrain generation" below.
- Builds **one static triangle mesh** from the heightmap at startup (936
  triangles, colored by height: dark green valleys, brown hillsides,
  light/white peaks, then darkened slightly with distance for a cheap fog
  effect).
- Flies a camera forward over it continuously, looping seamlessly once it
  reaches the far edge (the terrain is 54.6 world-units deep; the camera
  covers it in about 10 seconds and wraps).
- Adds a little life via a slow vertical bob and a subtle bank roll, both
  driven by a pure-integer triangle wave (no trig).
- Rebuilds its projection matrix **every frame** from the window's live
  aspect ratio, so a runtime resize never stretches the image.
- Prints one status line to stdout roughly once a second: how far it's
  flown and its current altitude, in millimeters (milli-units).

## Controls

None — this is an auto-flight demo (the task explicitly allows this: "Auto-
flight is fine"). WASD steering was left as a listed bonus and not
implemented; see "Known rough edges" for what that would take.

## The `id` / native split

Everything geometric and game-logic-shaped is `id`: the heightmap, the
smoothing, the mesh-building index math, the height→color rule, the fog
falloff, and the per-frame camera composition. The only things that cross
into `backends/gl/gl_linux.c` are:

- `gfx_open` / `gfx_poll` / `gfx_close` — window/input, identical contract to
  `backends/gfx`.
- `gl_begin_frame` / `gl_end_frame` — clear + present.
- `gl_mat_identity` / `gl_mat_perspective` / `gl_mat_rotate_x` /
  `gl_mat_rotate_z` / `gl_mat_translate` / `gl_mat_mul` — all matrix math,
  returning opaque integer handles `id` just threads together (see
  `world/flight/view/view.id`).
- `gl_set_projection` / `gl_set_modelview` / `gl_draw_tris` — load matrices,
  submit the mesh.
- `gl_aspect_x1000` — the live aspect ratio for the per-frame projection
  rebuild.

`id` never sees a float. Angles and translations cross as integers scaled by
1000 (milli-units/milli-degrees); the mesh's `verts`/`colors` cross as
`int[]` of milli-unit coordinates and packed `0xRRGGBB` colors.

## Terrain generation without floats or trig

1. **Raw noise** (`world/terrain/heightmap/random/`): a Park-Miller PRNG via
   Schrage's method (same generator `demos/moonbuggy` and `demos/gl3dgame`
   use) fills all 520 grid cells with a random milli-unit height 0..3199.
2. **Smoothing** (`world/terrain/heightmap/smooth/`): 3 passes average each
   *interior* cell with its left/right/up/down neighbors and write the
   result back in place. Only interior cells (rows 1..38, columns 1..11 of a
   13×40 grid) are touched, so every neighbor read is guaranteed in-bounds —
   no edge-clamping helpers needed, the outermost ring just keeps its raw
   value. Three passes of this turns uniform noise into rolling hills.
3. **Meshing** (`world/terrain/mesh/`): rather than storing a giant explicit
   per-triangle vertex list, a flat "vertex slot" 0..2807 (936 triangles × 3)
   is decoded back into a grid corner index by pure arithmetic
   (`geom/index.id`) — the same shared-corner trick `demos/gl3d`'s cube uses,
   scaled up to a grid. `geom/coords.id` turns a corner index into a
   milli-unit `(x, y, z)`; `geom/color.id` turns it into a height-shaded,
   fog-darkened color. `meshbuild/` walks all 2808 slots once at startup and
   pushes the flattened `verts`/`colors` lists `gl_draw_tris` wants.
4. **Flight** (`world/flight/`): the terrain mesh never changes after step 3
   — only the camera's matrices are rebuilt, every frame, as pure functions
   of the tick `t` (no stored camera state at all): `flown(t)` is
   `(t * 90) % 54600` (54600 = 39 rows × 1400 spacing, the terrain's total
   depth), so the flight loops seamlessly forever; `altitude(t)` and
   `bank_deg(t)` add a gentle bob/roll via an integer triangle wave
   (`view/wave.id`).

## Rule-of-3 tree layout

Every directory holds at most 3 `.id` files/subdirectories combined (READMEs
don't count), every file at most 3 functions, every block at most 3 actions,
nesting at most 2 deep — enforced by `idc.py`. The tree:

```
demos/flyover/
├── main.id                       (main)
├── loop/                         -- the frame loop
│   ├── loop.id                   (loop, spin)
│   └── frame.id                  (frame, alive)
└── world/                        -- orchestration + the two subsystems
    ├── world.id                  (world_init, world_update, world_render)
    ├── terrain/                  -- generate once, static thereafter
    │   ├── heightmap/
    │   │   ├── gen.id            (terrain_init, alloc_heights, generate_heights)
    │   │   ├── random/           -- PRNG + raw fill
    │   │   │   ├── fill.id       (raw_fill, push_height, rng_height)
    │   │   │   ├── rng.id        (rng_seed, set_seed, pos_seed)
    │   │   │   └── rng2.id       (rng_next, schrage, fixup)
    │   │   └── smooth/           -- neighbor-averaging passes
    │   │       ├── smooth.id     (smooth_heights, smooth_rows, smooth_cols)
    │   │       └── cell.id       (smooth_cell, sum5, lset)
    │   ├── mesh/
    │   │   ├── build.id          (mesh_init, tri_count)
    │   │   ├── geom/             -- corner index/coordinate/color math
    │   │   │   ├── index.id      (local_of, corner_index, slot_corner)
    │   │   │   ├── coords.id     (corner_x, corner_y, corner_z)
    │   │   │   └── color.id      (corner_color)
    │   │   └── meshbuild/        -- flatten into gl_draw_tris' lists
    │   │       ├── vertbuild.id  (build_verts, fill_verts)
    │   │       ├── vertpush.id   (push_vertex, push_xyz)
    │   │       └── colorbuild.id (build_colors, fill_colors, push_color)
    │   └── color/                -- height-tier shading + fog
    │       ├── tiers.id          (height_color, height_color_high)
    │       ├── pack.id           (shade_low, shade_mid, shade_high)
    │       └── fog.id            (fog_scale, apply_fog)
    └── flight/                   -- rebuilt every frame; no stored state
        ├── view/
        │   ├── view.id           (build_view, compose_tilt_bank, forward_translate)
        │   ├── motion.id         (flown, altitude, bank_deg)
        │   └── wave.id           (triangle)
        ├── proj.id                (build_proj)
        └── draw.id                (draw_scene, clear_and_place, submit_tris)
```

## Verified run output

Build (inside the mandatory dev shell; the `extern`/link-time warnings are
expected — every backend call is an undeclared-until-link-time symbol, same
as `demos/gl3d`/`demos/gl3dgame`):

```
$ tools/devshell.sh './idc.py demos/flyover --backend backends/gl -o /tmp/flyover'
id dev shell: cc=.../gcc-wrapper-15.2.0/bin/cc  python3=Python 3.13.13
demos/flyover/loop/frame.id:10: warning: call to function 'gfx_poll' which is not defined in any input file; it must be provided at link time
... (13 more of the same, one per backend/extern call) ...
$ echo $?
0
```

Headless run against the live GPU (40 frames, per the "keep test runs short"
guidance):

```
$ GFX_MAX_FRAMES=40 /tmp/flyover
gl_linux: opened 900x560 window, GL_RENDERER=AMD Radeon RX 7900 XTX (radeonsi, navi31, ACO, DRM 3.64, 7.0.10) GL_VERSION=4.6 (Compatibility Profile) Mesa 26.1.1
gl_linux: rendered 1 frame(s)
gl_linux: resized to 930x1880, viewport updated
gl_linux: resized to 3840x2160, viewport updated
gl_linux: resized to 930x1880, viewport updated
gl_linux: resized to 3840x2160, viewport updated
gl_linux: GFX_MAX_FRAMES=40 reached, synthesizing quit
gl_linux: closing after 40 frame(s) rendered
frame 0  dist 0mm  alt 2800mm
$ echo $?
0
```

A second, slightly longer run (130 frames) confirms the camera is actually
moving and the per-frame aspect/projection rebuild is live (the window
manager auto-tiled/resized it mid-run, and the projection kept up — no
stretching):

```
$ GFX_MAX_FRAMES=130 /tmp/flyover
gl_linux: opened 900x560 window, GL_RENDERER=AMD Radeon RX 7900 XTX (radeonsi, navi31, ACO, DRM 3.64, 7.0.10) GL_VERSION=4.6 (Compatibility Profile) Mesa 26.1.1
gl_linux: rendered 1 frame(s)
gl_linux: resized to 930x1880, viewport updated
gl_linux: resized to 3840x2160, viewport updated
gl_linux: resized to 930x1880, viewport updated
gl_linux: resized to 3840x2160, viewport updated
gl_linux: rendered 60 frame(s)
gl_linux: rendered 120 frame(s)
gl_linux: GFX_MAX_FRAMES=130 reached, synthesizing quit
gl_linux: closing after 130 frame(s) rendered
frame 0  dist 0mm  alt 2800mm
frame 60  dist 5400mm  alt 3000mm
frame 120  dist 10800mm  alt 3200mm
$ echo $?
0
```

`dist` climbs linearly (90mm/tick × 60 ticks = 5400mm between lines) and
`alt` moves through its triangle-wave bob (2800 → 3000 → 3200mm), confirming
the camera math and the status-line math agree (they call the exact same
`flown`/`altitude` functions — no duplicated logic, no separately-tracked
state to drift out of sync).

## Known rough edges

- **No WASD steering.** The task listed it as an optional bonus; this demo
  is auto-flight only. Adding it would mean turning `flown`/`altitude`/
  `bank_deg` from pure functions of `t` into state mutated by `gfx_poll()`
  key codes (the same `lset`-on-an-exported-list pattern `demos/gl3dgame`
  uses for its player position) — a natural follow-up, not attempted here to
  keep the camera model simple and provably stateless.
- **Looping is a hard reset, not a tile.** `flown(t)` wraps modulo the
  terrain's total depth, so the flight loops forever, but the heightmap
  itself is generated once and never changes — the same 39-row landscape
  repeats every ~10 seconds rather than scrolling in fresh terrain. The task
  explicitly allows this simpler strategy ("scroll the camera forward across
  a large heightmap"); regenerating rows procedurally ahead of the camera
  (the fancier alternative it also mentions) would remove the repetition at
  the cost of needing a rolling/windowed heightmap instead of one generated
  once.
- **Smoothing is in-place, not double-buffered.** Each of the 3 passes reads
  some already-updated neighbors from earlier in the same pass (no second
  heights buffer is allocated). This is a deliberate simplification — it
  still converges to smooth rolling hills, just asymmetrically, and avoids a
  second exported list purely for correctness. See `heightmap/smooth/smooth.id`.
- **Fog is a brightness scale, not a sky-blend.** `color/fog.id` darkens
  distant colors toward black rather than blending them toward the sky-blue
  clear color, per the task's "scale color by distance" suggestion — cheaper
  than a per-channel blend, at the cost of reading as shadow rather than haze.

## A note on this worktree

This worktree's branch point predated the `backends/gl` GPU backend, the
`gl3d`/`gl3dgame` reference demos, and the `flake.nix`/`tools/devshell.sh` dev
shell — all four were only brought in locally (copied verbatim from the
integration branch, not edited) to make this deliverable buildable and
testable at all. No file outside `demos/flyover/` was modified.
