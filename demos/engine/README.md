# A CLI game engine, written in id

A tiny terminal game engine in `id`, on top of the real-time I/O builtins that
`idc` grew for it. It keeps an off-screen character buffer, lets a game draw
into it, and renders the whole frame to the terminal with ANSI escapes — the
basis for an animated, full-screen, real-time game loop.

Two games are built on it: [`demos/moonbuggy`](../moonbuggy) (a real-time
side-scroller) and [`demos/solitaire`](../solitaire) (Klondike). Because a
project links no other project, each game **bundles** a copy of this engine
under its own `engine/` directory; this `demos/engine` is the standalone
reference copy (it has no `main`, so it builds to a `.o`).

```sh
./idc.py demos/moonbuggy -o moonbuggy && ./moonbuggy
./idc.py demos/solitaire -o solitaire && ./solitaire
```

## Runtime builtins it relies on

These were added to `idc` (and mirrored into the self-hosting runtime, so parity
holds) to make real-time terminal games possible:

- `put(s)` — write a string with **no** trailing newline (unlike `print`)
- `flush()` — flush stdout (the frame is built up with `put`, then flushed once)
- `getkey()` — poll a single key **without blocking**; returns its byte code, or
  `-1` if none. Raw, non-echo terminal mode is entered lazily on the first call
  and restored at exit.
- `sleep_ms(n)` — sleep `n` milliseconds (the frame pacer)
- `ticks()` — monotonic milliseconds, for timing and as a PRNG seed
- `pop(xs)` — remove and return the last element of a list (the complement of
  `push`); used heavily by solitaire's piles

## What the engine provides

- **Screen buffer**: `engine_init(w, h, seed)` allocates a `w*h` cell buffer
  (a byte-code list `scr` plus a parallel attribute list `scrc`). `clear()`
  blanks it each frame.
- **Drawing**: `set_cell`, `draw_text`, `draw_hline`, `draw_vline`, `draw_box`,
  all taking a color attribute (0 default, 1-7 colors, 8 bright, 9 reverse,
  10 red-on-white, 11 black-on-white, 12 white-on-green, 13 bold yellow).
- **Rendering**: `render()` homes the cursor, emits each row absolutely
  positioned (so a dropped byte can't shift the picture), collapses color runs
  into one SGR escape per change, and flushes.
- **Input**: `last_key()` drains all keys buffered since the last frame and
  returns the most recent (or `-1`), so input never lags the animation.
- **Terminal**: `term_setup()` / `term_done()` enter and leave full-screen mode.
- **PRNG**: `rng_seed`, `rng_next`, `rng_range(n)` — a Park-Miller generator via
  Schrage's method (no overflow, no bitwise ops, which `id` lacks).

## The frame loop

A game is a loop of: `clear()` → draw into the buffer → `render()` →
`last_key()` → act on the key → `sleep_ms(...)`. See the two games for the
pattern (moonbuggy paces on a clock; solitaire only needs to repaint on input).

Everything obeys `id`'s rules — 3 actions per block, 2-deep nesting, 3 functions
per file — so the engine is many tiny functions, like the rest of this repo.
