# `gl3d` — a real-time 3D engine in `id`

The GPU counterpart to `demos/gfxdemo`: instead of painting an `int[]`
framebuffer pixel by pixel, this program builds a cube mesh once, then every
frame composes rotation/projection matrices and hands triangles straight to
the GPU through `backends/gl` (see [its README](../../backends/gl/README.md)
for the native side of this seam).

```sh
./idc.py demos/gl3d --backend backends/gl -o gl3d && ./gl3d
# a 640x480 window with a spinning, per-vertex-shaded cube. Close it (or Esc / q) to quit.
```

`GFX_MAX_FRAMES=120 ./gl3d` renders 120 frames and exits 0 on its own — no
window-close needed — the same headless hook `demos/gfxdemo` uses.

## Why the matrix math isn't in `id`

`id` has no float literals worth relying on and no bitwise ops, so building
projection/rotation matrices in `id` itself isn't practical. Per the backend's
documented design (`backends/gl/gl.h`, `backends/gl/README.md`), **all matrix
math lives natively in `gl_linux.c`**; `id` only ever passes plain integers
across the seam and threads opaque matrix **handles** between calls:

```
scene/render/frame.id:

compose_rotation(int t) {
  int ry = gl_mat_rotate_y((t * 2000) % 360000);   // t*2 degrees, scaled x1000
  int rx = gl_mat_rotate_x((t * 1000) % 360000);   // t degrees, scaled x1000
} return int gl_mat_mul(ry, rx);

modelview(int t) {
  int r = compose_rotation(t);
  int tr = gl_mat_translate(0, 0, 0 - 5000);        // push back 5 units on -Z
} return int gl_mat_mul(tr, r);
```

No float ever appears on the `id` side: every "degrees" or "unit" value is an
integer scaled by 1000 ("milli-units" -- the same packing trick
`demos/gfxdemo/fb/color.id`'s `rgb(r,g,b)` uses for pixels), and every
`gl_mat_*` call returns a handle (a small int index into a native matrix pool)
instead of a matrix. `id` composes the scene by threading handles through
`gl_mat_mul`, never by touching a float.

## The mesh

A cube, 8 corners numbered 0..7, addressed by plain arithmetic instead of bit
tricks (`demos/gl3d/scene/mesh/geom/corners.id`):

```
corner_x(int i) { } return int ((i % 2) * 2 - 1) * 1000;
corner_y(int i) { } return int (((i / 2) % 2) * 2 - 1) * 1000;
corner_z(int i) { } return int (((i / 4) % 2) * 2 - 1) * 1000;
```

The 6 faces are a 36-entry table of corner indices (12 triangles * 3,
`geom/face.id`), one color per corner (`geom/color.id`), and
`scene/mesh/meshbuild/` walks vertex slots 0..35 to flatten both into the
`int[]` lists `backends/gl`'s `gl_draw_tris(verts, colors, count)` expects: 9
milli-unit ints per triangle for `verts`, 3 packed `0xRRGGBB` ints per triangle
for `colors`. This is the same "build the buffer, flush once" shape
`gfxdemo`'s framebuffer uses, just for triangles instead of pixels.

## Project tree (rule of 3)

```
demos/gl3d/
  main.id                    -- opens the window, builds the scene once, loops
  loop/                       (2 files)
    loop.id                   -- spin/tick, same shape as demos/gfxdemo/loop
    frame.id                  -- one frame: render(t), then poll
  scene/                       (2 entries)
    mesh/                        (3 entries)
      geom/                        (3 files: corners.id, face.id, color.id)
      meshbuild/                   (3 files: vertbuild.id, vertpush.id, colorbuild.id)
      api.id                    -- mesh_init(), tri_count()
    render/                      (3 files: init.id, frame.id, draw.id)
```

Every directory holds at most 3 entries, every function body at most 3
actions, nesting never exceeds 2 deep — the same fractal decomposition
`demos/gfxdemo` and `demos/engine` use, applied to matrix composition and mesh
flattening instead of framebuffer fills.

## Verified

Inside `tools/devshell.sh` (X11 + GLX + mesa on the `PATH`):

```
$ ./idc.py demos/gl3d --backend backends/gl -o /tmp/gl3d
$ GFX_MAX_FRAMES=120 /tmp/gl3d
gl_linux: opened 640x480 window, GL_RENDERER=AMD Radeon RX 7900 XTX (radeonsi, navi31, ACO, DRM 3.64, 7.0.10) GL_VERSION=4.6 (Compatibility Profile) Mesa 26.1.1
gl_linux: rendered 1 frame(s)
gl_linux: rendered 60 frame(s)
gl_linux: rendered 120 frame(s)
gl_linux: GFX_MAX_FRAMES=120 reached, synthesizing quit
gl_linux: closing after 120 frame(s) rendered
$ echo $?
0
```

`GL_RENDERER` confirms the frames were actually rasterized by a real GPU
(mesa's `radeonsi` driver against the machine's AMD GPU), not a software
fallback.

## Known rough edges

- The cube is unlit (per-vertex colors interpolated by the fixed-function
  pipeline, no `GL_LIGHTING`) -- correctness and motion are the point here, not
  shading; `backends/gl` doesn't expose a lighting primitive yet.
- Face winding isn't consistently CW/CCW-normalized across all 6 faces (backend
  disables `GL_CULL_FACE` specifically so this doesn't matter); a mesh that
  needed backface culling would need the winding audited face by face.
- The projection matrix is built once in `scene/render/init.id` assuming a
  fixed 640x480 (aspect 4:3, hard-coded as `1333` = 1.333*1000); there's no
  window-resize handling in `backends/gl` yet for it to react to.
