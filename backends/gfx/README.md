# `gfx` — a platform-agnostic graphics backend for `id`

A windowed graphics backend, built the way the terminal engine was: a tiny set
of native primitives that `id` drives from its own frame loop. Where
`demos/engine` keeps an off-screen **character** buffer and flushes it to a
terminal with ANSI escapes, `gfx` keeps an off-screen **pixel** buffer and
presents it to a real OS window. The drawing logic stays in portable `id`; only
the window and the blit are native.

```sh
./idc.py demos/gfxdemo --backend backends/gfx -o gfxdemo && ./gfxdemo
# a 320x200 window with a sliding, color-cycling box. Close it (or Esc / q) to quit.
```

## The seam

The entire contract between `id` and the platform is [`gfx.h`](gfx.h) — five
integer-returning functions:

| function | meaning |
| --- | --- |
| `gfx_open(w, h, title)`  | open a `w`×`h` window, return 1/0 |
| `gfx_present(fb)`        | blit the `int[]` pixel buffer (`0xRRGGBB`, row-major, top row first) and pump events |
| `gfx_poll()`             | one event, non-blocking: `-2` quit, `-1` none, `>=0` key code |
| `gfx_close()`            | tear the window down |

`id` never names a platform API; it only calls these. That seam is exactly
`id`'s segmentation philosophy applied to portability: the platform-specific
code is quarantined behind a handful of names, and the whole rule-of-3 `id` tree
above it (`demos/gfxdemo`) is identical on every OS.

### Why these signatures

`idc` resolves a call to an undefined function as `extern int id_<name>()`,
satisfied at link time (see the README's "Functions link across files"
section). So every backend entry point is named `id_*`, returns `int`, and
takes arguments lowered the way `idc` lowers them (`int`→`int`, `string`→`char*`,
`int[]`→`IdList*`). The framebuffer is passed as one `int[]` so a whole frame
crosses the boundary in a single call, not a million per-pixel ones — the same
"build the buffer, then flush once" shape the terminal engine uses.

## How it links

`idc` grew a `--backend DIR` flag. It reads `DIR/backend.json`, picks the entry
for the host platform, compiles that platform's sources to objects, and appends
them plus the platform link flags to the final `cc` invocation. Nothing is
hard-coded in the compiler — a backend is self-describing:

```json
{ "platforms": {
    "darwin": { "sources": ["gfx_macos.m"], "cflags": ["-fobjc-arc"],
                "link": ["-framework", "Cocoa", "-framework", "QuartzCore"] },
    "linux":  { "sources": ["gfx_linux.c"], "cflags": [],
                "link": ["-lX11"] } } }
```

## Platforms

- **macOS** ([`gfx_macos.m`](gfx_macos.m)) — Cocoa + QuartzCore via the system
  toolchain (no third-party libraries). A layer-backed `NSView` draws the
  framebuffer as a `CGImage`. `id` keeps its own loop, so the app is
  `finishLaunching`ed once and events are pumped non-blockingly with
  `nextEventMatchingMask:…distantPast` each frame. **Built and run.**
- **Linux** ([`gfx_linux.c`](gfx_linux.c)) — Xlib `XPutImage` over a software
  framebuffer, `-lX11` only. Same header, same contract; this is the concrete
  proof the seam is portable. **To be validated on first Linux build.**

Adding Windows (GDI/`StretchDIBits`) or a Wayland backend is one more source
file plus a `backend.json` entry — no change to `id` code or to the compiler.

## Path to true-native rendering

Today the only primitive is "present a software framebuffer," which is the most
portable floor and keeps all drawing in `id`. The header is built to grow a
second tier *without breaking the first*: add entry points like `gfx_rect`,
`gfx_blit`, or a GPU pipeline (Metal on macOS, Vulkan on Linux) backed
per-platform, while `gfx_present` stays as the always-available fallback. `id`
programs opt into the faster path by calling the new names; the framebuffer path
keeps working everywhere it always did.

## Known rough edges (first slice)

- The link-time `extern` mechanism declares backend functions K&R-style (no
  prototype), so `cc` warns `-Wdeprecated-non-prototype` and a future C23-only
  toolchain would reject it. The clean fix is a small `idc` feature for typed
  external declarations; tracked as future work, not needed to run today.
- No window-resize handling yet (the surface is fixed at `open` size; the image
  scales to fit). Pointer/mouse events aren't surfaced — only keys and close.
- `gfx.h`'s `IdList` must stay byte-identical to `idc.py`'s runtime `IdList`; if
  that layout ever changes, update both.
