# `gl` — a hardware-accelerated graphics backend for `id`

Where [`backends/gfx`](../gfx/README.md) presents a software framebuffer that
`id` paints one pixel at a time, `gl` hands geometry straight to a GPU. It's a
second, sibling backend directory — not new entry points bolted onto `gfx.h` —
so a program picks its floor or its ceiling at build time, and the frame-loop
shape (`open` → loop of `draw → present → poll` → `close`) is identical either
way:

```sh
./idc.py demos/gl3d --backend backends/gl -o gl3d && ./gl3d
# a 640x480 window with a spinning, per-vertex-shaded cube. Close it (or Esc / q) to quit.
```

## The seam

The entire contract is [`gl.h`](gl.h). The window/input primitives are the
*same names and contract* as `gfx.h` on purpose — switching a program from the
software floor to the GPU path never changes its loop shape, only what it calls
each frame to draw:

| function | meaning |
| --- | --- |
| `gfx_open(w, h, title)` | open a GPU-backed `w`×`h` window, return 1/0 |
| `gfx_poll()`            | one event, non-blocking: `-2` quit, `-1` none, `>=0` key code |
| `gfx_close()`           | tear the context/window down |

New, GPU-specific primitives layer on top:

| function | meaning |
| --- | --- |
| `gl_begin_frame(r, g, b)`  | clear the color+depth buffers to `(r,g,b)` (0..255 each) |
| `gl_mat_identity()`, `gl_mat_perspective(...)`, `gl_mat_rotate_x/y/z(deg_x1000)`, `gl_mat_translate(...)`, `gl_mat_mul(a, b)` | build a 4x4 matrix, return an opaque **handle** |
| `gl_set_projection(handle)`, `gl_set_modelview(handle)` | load a handle's matrix onto the GL projection/modelview stack |
| `gl_draw_tris(verts, colors, count)` | draw `count` triangles from flattened `int[]` vertex/color lists |
| `gl_end_frame()`           | swap buffers, pump events, log a frame count, advance `GFX_MAX_FRAMES` |

Like `gfx`, `GFX_MAX_FRAMES` (checked in `gl_end_frame` instead of `gfx_present`,
since that's this backend's "one frame is done" moment) makes headless runs
self-terminating: after *N* frames, the next `gfx_poll()` reports quit (`-2`).

## The float problem, and how this backend solves it

`id` has no convenient way to build the float matrices a GPU pipeline needs (no
float literals worth relying on, no bitwise ops for bit-casting). Rather than
touch `idc.py` (out of scope for this backend) to add float support, **all
matrix math lives here, in C**, and the `id`/native seam only ever crosses
plain integers:

- Angles and translations cross as integers **scaled by 1000** ("milli-units"):
  an `id` int `y` passed to `gl_mat_translate` means "translate by `y/1000.0`
  units"; a `deg_x1000` passed to `gl_mat_rotate_y` means "rotate by
  `deg_x1000/1000.0` degrees." This is the same trick
  `demos/gfxdemo/fb/color.id`'s `rgb(r,g,b)` uses to pack a pixel — plain
  integer arithmetic standing in for something the language can't spell
  directly.
- A built matrix is **never marshalled back into `id`**. Each `gl_mat_*`
  builder returns a small int **handle** — an index into a fixed pool of 4x4
  matrices (`g_mat[1024][16]` in `gl_linux.c`) that lives entirely on the
  native side. `id` just threads handles between calls:
  `gl_mat_mul(gl_mat_translate(...), gl_mat_mul(gl_mat_rotate_y(...), gl_mat_rotate_x(...)))`
  builds a full modelview matrix without a single float ever crossing into
  `id`. This is simpler than round-tripping 16 bit-cast floats through an
  `IdList*` (the alternative the task description offered) and just as
  legitimate a lowering — see `gl.h` for the full rationale.
- Vertex data (`gl_draw_tris`'s `verts`/`colors`) *does* cross as `IdList*`,
  but every element is a plain int: a milli-unit coordinate, or a packed
  `0xRRGGBB` color (the same convention `gfx.h`'s framebuffer already uses).

`demos/gl3d` (see its own README) is the concrete proof: it builds an
eight-corner cube and a 12-triangle face table with pure integer arithmetic and
array literals, and drives the whole rotation/projection pipeline through
`gl_mat_*` handles — no `id`-side float ever appears.

## Platforms

- **Linux** ([`gl_linux.c`](gl_linux.c)) — Xlib + GLX. Chooses a
  double-buffered RGBA visual with a 16-bit depth buffer, creates a legacy
  (compatibility-profile) GL context with `glXCreateContext`, and draws with
  immediate-mode `glBegin`/`glEnd` — the simplest path that reliably works
  against mesa, per the guidance to prefer "actually renders via GPU" over
  modern-GL purity. **Validated**: built and run inside `tools/devshell.sh`
  against a live X server (XWayland), reporting a real GPU renderer string
  (`GL_RENDERER=... (radeonsi, ...) GL_VERSION=4.6 (Compatibility Profile)
  Mesa ...` in this environment) and rendering 120 frames of a spinning cube
  before exiting 0 via `GFX_MAX_FRAMES`.
- **macOS** — not implemented. `backend.json` has no `darwin` entry, so
  building `demos/gl3d --backend backends/gl` on macOS fails fast with a clear
  "backend has no support for platform 'darwin'" error rather than silently
  doing the wrong thing. The natural next step is a CGL/`NSOpenGLContext`
  backend behind this same `gl.h` (mirroring how `backends/gfx/gfx_macos.m`
  sits next to `gfx_linux.c`); not attempted here since this environment can
  only build and validate the Linux path.

## How it links

Same mechanism as `gfx`: `idc --backend backends/gl` reads
[`backend.json`](backend.json), compiles `gl_linux.c` on Linux, and links
`-lGL -lX11 -lm` (the `-lm` is for `tan`/`sin`/`cos` in the matrix builders —
easy to miss since desktop Linux usually auto-links libm through other
dependencies, but not guaranteed here).

## Known rough edges

- Same K&R-prototype-free `extern` linking as `gfx` (see its README) — a
  future `idc` feature for typed external declarations would let `cc` fully
  type-check backend calls instead of only checking them at the `id` side.
- The matrix pool (1024 slots) is a ring buffer with no explicit free; handles
  from many frames ago silently become invalid once overwritten. Fine for a
  demo that rebuilds a handful of matrices every frame and never holds a
  handle across frames; a long-lived-handle use case would need real
  allocation/refcounting.
- No window-resize handling (fixed viewport at `open` size, like `gfx`).
  Pointer/mouse events aren't surfaced, only keys and close.
- `gl_draw_tris` assumes `verts`/`colors` are large enough for `count`
  triangles; it clamps to whatever's actually there rather than erroring, so a
  short list silently draws fewer triangles instead of crashing (matches
  `gfx_present`'s "missing pixels read as black" philosophy of failing soft).
