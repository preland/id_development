# Klondike Solitaire — in id

A full Klondike solitaire on the id game engine (bundled under `engine/`, since a
project links no other project): stock, waste, four foundations, seven tableau
columns, with colored cards and a cursor-driven, real-time interface. The project
is laid out as `engine/` (the bundled engine) and `game/` (the solitaire code).

```sh
./idc.py demos/solitaire -o solitaire
./solitaire
```

## Controls

- **a / d** (or **h / l**) — move the cursor left / right across the piles
  (stock, waste, the four foundations, the seven tableau columns)
- **space** (or **enter**) —
  - on the **stock**: deal a card to the waste (or recycle the waste back when
    the stock is empty)
  - on the **waste** or a **tableau column**: pick up the card (or the whole
    face-up run of a column)
  - with a card picked up: drop it on the cursor's pile if the move is legal
    (press on the same pile again to cancel)
- **q** — quit

The cursor pile is marked with `^^^` / `>`, a picked-up source with `+++` / `*`.

## Rules implemented

- Foundations build **up by suit**, Ace through King.
- Tableau columns build **down in alternating colors**; only a King may start an
  empty column. The whole face-up run of a column moves as a unit.
- Exposing a face-down card flips it up automatically.
- Win when all four foundations reach the King.

## How it works

All game state is exported `id` state: `stock`, `waste`, `found` (top rank per
suit), `tab` (the seven columns, an `int[][]`), `fd` (face-down count per
column), and `ui` (cursor / selection). A card is an int `0..51`
(`rank = c/4+1`, `suit = c%4`). The frame loop polls a key, mutates the piles
(using the engine's `pop`/`push` list ops), and repaints. It is many small
files because `id` caps every block at 3 actions, nesting at 2, and 3 functions
per file.
