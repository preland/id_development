# `galaxy` -- a spiral-galaxy particle viewer, written in `id`

```sh
tools/devshell.sh './idc.py demos/galaxy --backend backends/gl -o galaxy'
./galaxy
```

6000 small, additively-blended, light-emitting points arranged into a
3-armed spiral galaxy, hardware-rendered via `backends/gl`'s `gl_draw_points`
primitive. The galaxy slowly rotates about its own vertical axis, and a
tilted, pulled-back camera looks down on the whole disk. Close the window
(or press Esc / `q`) to quit; `GFX_MAX_FRAMES=N` makes a headless run
self-terminate after `N` frames.

## What it does

At startup (`galaxy/render/init.id`) the sine table is built, the PRNG is
seeded, and the entire particle cloud -- 6000 points -- is generated once
into two flat `int[]` lists, `pos` (3 milli-unit ints per point) and `col`
(1 packed `0xRRGGBB` per point), exactly the shape
`backends/gl/gl.h`'s `gl_draw_points(positions, colors, count, size_x1000)`
wants. Every frame then just rotates that static cloud with one extra
matrix multiply and resubmits it -- see "Swirl" below.

## The spiral, without floats

`id` has no float literals worth relying on and no bitwise ops, so all
angle math is table-driven integer arithmetic:

- **Sine table** (`galaxy/math/trig/table.id`): `sin(0..90 deg) * 1000`,
  computed offline in Python and pasted in as a 91-entry `int[]` literal.
  `sin90(i)` looks a value up directly.
- **Quadrant reduction** (`galaxy/math/trig/norm.id` +
  `galaxy/math/trig/angle/{sin,quad,cos}.id`): `sin_deg(d)` normalizes any
  integer degree into `0..359` (`norm_deg`/`fix_neg`, since `%` follows C
  truncating semantics and can go negative), splits it into quadrant
  `q = n/90` and remainder `r = n%90`, and reflects `r` through the table
  per quadrant (`sin(90+r)=cos(r)=sin90(90-r)`, `sin(180+r)=-sin(r)`,
  `sin(270+r)=-cos(r)`). The dispatch is a small tree of 2-function calls
  (`sin_q` -> `sin_q01`/`sin_q23`) rather than one long `if`/`else if`
  chain, to keep every block at or under the 3-action limit. `cos_deg(d)`
  is just `sin_deg(d + 90)` -- no separate table.
- **PRNG** (`galaxy/math/rng/{rng,rng2,lset}.id`): the same Park-Miller
  minimal-standard generator (Schrage's method, no overflow, no bitwise
  ops) copied from `demos/moonbuggy`/`demos/gl3dgame`. `rng_range(n)` is a
  uniform pick in `0..n-1`; `noise_range(half)` is symmetric jitter in
  `-half..+half`, reused for angle jitter, disk-height jitter, and
  color-channel noise alike.
- **Per-particle shape** (`galaxy/particles/shape/{radius,theta}.id`):
  radius `r` is `u*u/1000` for `u` uniform in `0..1000` -- squaring a
  uniform variable compresses its mass toward zero, giving the "denser
  toward the core" distribution with no floats and no real inverse-CDF
  sampling. `theta` is `arm_base(i) + r*60/1000 + noise_range(20)`: one of
  3 arms 120 degrees apart, plus a winding term proportional to radius (so
  the angle sweeps further round the further out a particle sits -- the
  actual "spiral"), plus +-20 degrees of scatter.
- **Cartesian + color** (`galaxy/particles/look/`): `x = r*cos_deg(theta)/1000`,
  `z = r*sin_deg(theta)/1000` (`position/xz.id`); `y` is a PRNG sample
  within a radius-dependent thickness that shrinks from 300 milli-units at
  the core to 60 at the rim (`position/y.id`, "thin disk, thicker core").
  Color interpolates from a hot yellow-white core `(255,240,180)` to a
  cool blue-ish rim `(80,120,255)` by `radius_frac` (0..1000), with a small
  PRNG wobble per channel, then packs to `0xRRGGBB` (`color/{pack,tint,util}.id`)
  the same way `demos/gl3d`'s corner colors do.

## The additive-particle look

All 6000 points are submitted in one `gl_draw_points` call
(`galaxy/render/pipeline/draw.id`), which the backend renders with
additive blending (`glBlendFunc(GL_SRC_ALPHA, GL_ONE)`) -- overlapping
particles accumulate into bright glowing cores instead of the topmost
point simply covering the rest, which is what makes the dense core and
the arm crossings read as *brighter* than the sparse outskirts. The frame
clears to near-black (`gl_begin_frame(0, 0, 8)`) so the glow has somewhere
to pop against.

## Swirl: rigid rotation, not per-particle recompute

The task's two options were a cheap rigid whole-cloud rotation, or a
nicer but pricier differential shear (inner particles orbiting faster
than outer ones, positions rebuilt every frame). This demo takes the
rigid option (`galaxy/render/swirl.id`): the cloud is built once and every
frame just composes one extra `gl_mat_rotate_y(swirl_deg(t))` into the
modelview, `swirl_deg(t) = (t * 300) % 360000` milli-degrees -- 0.3
deg/frame, a full turn roughly every 20s at 60fps. At 6000 static points
this is trivially cheap (one matrix multiply/frame, no per-particle
trig), and visually indistinguishable from a real rigid rotation since
the whole disk (not just the camera) turns. A differential shear is the
natural next step if the budget allows revisiting this file.

## Camera

`galaxy/render/pipeline/camera.id`'s `camera_rig()` tilts the disk 55
degrees and pulls the view back 12 units on `-Z`
(`gl_mat_mul(gl_mat_translate(0,0,-12000), gl_mat_rotate_x(55000))`), the
same translate-then-rotate composition `demos/gl3dgame`'s `build_view`
uses, so the ~5-unit-radius disk (`particles/shape/radius.id`'s
`max_radius()`) sits well inside the frustum and reads as a disk seen
from above rather than edge-on. `camera_proj()` rebuilds the perspective
matrix from `gl_aspect_x1000()` **every frame** (rather than caching it
once like `demos/gl3d` does) specifically so a runtime window resize
never stretches the image -- see "Verified run" below, where the WM's
auto-tiling actually exercises this.

## The `id`/native split

Only `gfx_open`/`gfx_poll`/`gfx_close` and the `gl_*` primitives
(`gl_begin_frame`, `gl_mat_*`, `gl_set_projection`/`gl_set_modelview`,
`gl_draw_points`, `gl_end_frame`, `gl_aspect_x1000`) cross into
`backends/gl`'s native code. Every angle, radius, color and matrix
*argument* crossing that seam is a plain integer (milli-units/milli-degrees
or a packed `0xRRGGBB`); the sine table, the PRNG, the spiral-arm math and
the frame loop are all portable `id` with no backend dependency beyond
those calls.

## Rule-of-3 layout

```
demos/galaxy/
  main.id                              -- gfx_open, scene_init, loop
  loop/{loop,frame}.id                 -- frame loop + periodic status line
  galaxy/
    math/
      trig/table.id                    -- the 91-entry sine table
      trig/norm.id                     -- angle normalization
      trig/angle/{sin,quad,cos}.id     -- quadrant-reduced sin/cos
      rng/{rng,rng2,lset}.id           -- Park-Miller PRNG + range helpers
    particles/
      gen/{gen,add}.id                 -- build the pos[]/col[] lists
      shape/{radius,theta}.id          -- polar placement (radius/angle)
      look/position/{xz,y,push}.id     -- polar -> Cartesian + disk thickness
      look/color/{pack,tint,util}.id   -- radius -> color
    render/
      init.id                          -- one-time seed + build + print
      swirl.id                         -- swirl angle + status line
      pipeline/{frame,camera,draw}.id  -- per-frame matrices + GL calls
```

Every directory holds at most 3 `.id`-files-and-subdirectories (README.md
never counts), every file at most 3 functions, every block at most 3
actions, nesting depth at most 2 -- deep dispatch (e.g. the sine
quadrant split) is a chain of small named functions instead of a pyramid
of nested branches.

## Verified run

Built clean inside the dev shell (only the expected "not defined in any
input file" `extern` warnings for backend calls):

```
$ tools/devshell.sh './idc.py demos/galaxy --backend backends/gl -o /tmp/galaxy'
id dev shell: cc=.../gcc-wrapper-15.2.0/bin/cc  python3=Python 3.13.13
demos/galaxy/galaxy/render/pipeline/camera.id:12: warning: call to function 'gl_mat_translate' which is not defined in any input file; it must be provided at link time
... (backend extern warnings only, no errors)
```

Headless run, 65 frames, exits 0:

```
$ tools/devshell.sh 'env DISPLAY=:0 GFX_MAX_FRAMES=65 /tmp/galaxy'
id dev shell: cc=.../gcc-wrapper-15.2.0/bin/cc  python3=Python 3.13.13
gl_linux: opened 1024x768 window, GL_RENDERER=AMD Radeon RX 7900 XTX (radeonsi, navi31, ACO, DRM 3.64, 7.0.10) GL_VERSION=4.6 (Compatibility Profile) Mesa 26.1.1
gl_linux: rendered 1 frame(s)
gl_linux: resized to 3800x930, viewport updated
gl_linux: resized to 3792x922, viewport updated
gl_linux: rendered 60 frame(s)
gl_linux: GFX_MAX_FRAMES=65 reached, synthesizing quit
gl_linux: closing after 65 frame(s) rendered
galaxy: 6000 particles, seed 1337
frame 0 particles 6000 swirl_millideg 0
frame 60 particles 6000 swirl_millideg 18000
EXIT=0
```

This confirms: `gl_draw_points` is called once per frame with all **6000**
particles; the swirl angle genuinely advances frame to frame (`0` ->
`18000` milli-degrees over 60 frames, matching `300` milli-deg/frame);
the window manager auto-tiled/resized the window mid-run (two
`resized to ...` lines) and the per-frame `camera_proj()` ->
`gl_aspect_x1000()` rebuild kept the projection correct through it with
no extra code; and the process exits 0 after `GFX_MAX_FRAMES` fires.

## Rough edges

- The swirl is a rigid whole-cloud rotation, not a differential shear --
  every particle currently orbits at the same rate, so the arms don't
  visibly "wind up" further over time the way a real differential
  rotation curve would. `galaxy/render/swirl.id` is where that upgrade
  would go (rebuild `pos` each frame from each particle's stored radius
  and an angle that decreases with radius, instead of one shared matrix).
- Headless runs can't show pixels, so correctness here rests on the
  build succeeding, the frame/particle-count/swirl-angle log lines above,
  and the same `gl_draw_points` contract `backends/gl/README.md` already
  documents and validates independently.
