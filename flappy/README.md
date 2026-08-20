# flappy — Flappy Bird in `id` + idml

A faithful Flappy Bird clone in which **`id` is the whole game** and **idml is the
whole view**. The browser contributes a clock, a keyboard and one line of
`localStorage`; it contributes no game logic and no artwork.

```sh
cd flappy
npm install
npm run dev      # http://localhost:3000
```

Tap, click, or press space / ↑ / enter. One press starts, flaps, and plays
again — which of those it means is decided in `id`.

## What lives where

| | |
|---|---|
| `id/` | The game. Physics, pipes, collision, score, medals, which screen you're on, and every measurement the view lays out with. Compiled to `public/flappy.wasm` by `idc.py --target wasm`. |
| `sprites/` | A second `id` program that **draws every image in the game** and prints it as SVG. There are no binary assets in this repository. |
| `ui/` | The view, in idml: `flappy.idml` (the layer stack), `parts.idml` (the pieces), `style.idml` (the styled variants). |
| `app/page.tsx` | The host. ~40 lines of wiring, of which every game-facing line is a one-line adapter from an idml method name to an `id` function. |
| `app/globals.css` | Colour, sprite backgrounds, transforms — the CSS idml has no prop for. |

`npm run build:all` runs the three build steps: `id` → wasm, `sprites` → SVG,
`.idml` → `app/flappy.config.json`. `predev`/`prebuild` run it for you.

## The playfield

Everything is expressed in the original's 288 × 512 pixels: the ground is 112 px
tall, a pipe is 52 px wide with a 26 px cap, gaps are 100 px and 172 px apart,
gravity is 1500 px/s², a flap is −420 px/s, and the world scrolls at 120 px/s.
`id` holds all of it in whole numbers — positions in centipixels, so motion is
smooth without a single float — and `view/` converts each one into the only
thing idml lays out with: a percentage of a parent.

That conversion is the interesting part of the design. idml has no notion of a
pixel, so the game never asks it for one. Instead `id` returns finished CSS
lengths (`"35.42%"`), the `.idml` binds them as dimensions, and the browser
resolves them against a stage whose size is the one thing CSS decides.

## Three things worth knowing

**Percentages can't be negative, so the scrolling layers overhang.** A pipe
leaving to the left needs a negative x, which a width-based layout can't
express. The pipe layer is therefore 150% of the board wide and pinned to its
right edge, and the ground layer 200% — an object sliding off the left is still
at a *positive* offset inside its own layer. See `pipe_lead` / `base_lead` in
`id/view/geom/layer.id`.

**A fixed-size box is what lets a fixed-size part exist.** A pipe's cap is
26 px whatever the pipe's height, but a percentage inside a varying-height box
isn't fixed. So the cap-gap-cap sandwich is its own 152 px element (`Neck`), and
inside *that* fixed box the caps are a fixed share. Nothing in the view needs a
pixel unit.

**Live dimensions.** idml eases a dimension into its new value over ~300 ms,
which is right for a sidebar and wrong for a falling bird. A dimension written
`@birdTop!` is marked *live*: the renderer applies each value at once. That
suffix was added to idml for this game (`src/parser/idml-parser.ts`,
`LayoutRenderer.tsx`).

## The art

`sprites/` holds the pixel art as characters — one character per pixel, `.` for
transparent — and an `id` program turns each into an SVG of run-length rects.
It also carries a 5×7 font, so `GET READY`, `GAME OVER`, the labels and the
score digits are all *drawn*, not typeset: `draw_word` assembles a word into
exactly the same row-strings a hand-drawn sprite uses and hands it to the same
renderer, which gives lettering its dark halo for free.

```sh
npm run build:sprites    # flappy/sprites -> public/sprites/*.svg (31 files)
```

## Driving it from the console

In development the page exposes a handle, which is how the game was tested
without a display:

```js
idFlappy.id.call('press')      // any exported id function, by name
idFlappy.step(120)             // advance 120 frames and re-render
idFlappy.id.call('score')
```
