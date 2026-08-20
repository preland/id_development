# nativeapp — "id · todo", a native GUI powered by id + idml

The web demo's todo app, ported to a **native windowed application** — no web
stack, no browser. It renders into a software framebuffer via id's native
graphics backend (`backends/gfx`, an X11/Cocoa window), and every pixel is drawn
in pure `id`.

- **idml** owns the UI. `ui/todo.idml` declares the layout and palette; it is
  resolved to absolute pixel geometry in `id/todo/view/layout.gen.id`.
- **id** owns everything at runtime: state/logic (the *same* append-only todo
  model as the web demo — `id/todo/model/logic/`), the framebuffer drawing
  (`id/gfx/`), an 8×8 bitmap font (`id/gfx/draw/text/glyphs.gen.id`), keyboard
  handling, and the frame loop.

The build uses **only the id compiler** — no other tooling in the loop. The
app's dependency (the software-graphics backend) is declared in a one-line
`id/import.id` manifest, so the whole build is `id nativeapp/id`:

```
  id/import.id  ─ import "../../backends/gfx" ─┐  (dependency manifest, not source)
                                               ▼
  id/**.id  ──────────────  id nativeapp/id  ──▶  ./todoapp   (native window)
                                               │
                         draw framebuffer ◀── id renderer ── id todo logic + input
```

The two `*.gen.id` files (the bitmap font and the idml-resolved layout) are
committed id source, so the build never runs anything but the compiler. They
are only regenerated — offline, via Node — when the font table or `ui/todo.idml`
changes: `scripts/regen.sh`. That step is *not* part of building or running.

## Build & run

```sh
# from the repo root -- just the id compiler on the project directory:
./bin/id nativeapp/id -o nativeapp/todoapp
./nativeapp/todoapp

# or the convenience wrapper (same thing):
cd nativeapp && ./build.sh && ./todoapp
```

`id/import.id` attaches the gfx backend, so there is no `--backend` flag and no
Node in the build. (`id` wraps the self-hosted `bin/idc`, which falls back to the
reference compiler `idc.py` for the backend's extern declarations — see the repo
README on self-hosting.)

**Keyboard** (the gfx backend delivers only character keys, so no mouse / arrows):

| key            | action                                  |
| -------------- | --------------------------------------- |
| any printable  | type into the new-todo field            |
| Enter          | add the typed todo                      |
| Backspace      | erase a character                       |
| Tab            | move the selection cursor down the list |
| Esc            | toggle the selected todo done/undone    |
| close window   | quit                                    |

## Off-screen verification

The rendering is pure id, so it needs no display to *test*. `--shot` renders one
seeded frame and dumps it as a PPM, which converts to a PNG:

```sh
./todoapp --shot > frame.ppm
magick frame.ppm frame.png     # (ImageMagick) — a real screenshot of the UI
```

This is how the app was developed and checked without a live window.

## Why it looks the way it does (id's constraints)

Every `id` file holds ≤3 functions, every block ≤3 actions, every directory ≤3
entries — so the app is a wide, shallow tree of tiny functions (`gfx/` drawing,
`todo/view/` rendering split into one-concern helpers, `todo/ctrl/` a chain of
one-decision key handlers). The bitmap font stores each glyph row as an integer
bitmask (id has no bitwise ops, so pixels are tested with `/` and `%`).
