#!/usr/bin/env bash
# OFFLINE regeneration of the committed generated id sources. This is the ONLY
# part of the project that uses Node, and it is NOT part of building or running
# the app -- the committed glyphs.gen.id + layout.gen.id are what `id` compiles.
# Re-run this only after you change the font table (build-font.mjs) or the UI
# (ui/todo.idml):
#   - build-font.mjs  ->  id/gfx/draw/text/glyphs.gen.id   (the 8x8 bitmap font)
#   - build-scene.mjs ->  id/todo/view/layout.gen.id       (idml -> pixel layout)
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NA="$(cd "$HERE/.." && pwd)"

echo "[font] -> id/gfx/draw/text/glyphs.gen.id"
node "$HERE/build-font.mjs" "$NA/id/gfx/draw/text/glyphs.gen.id"

echo "[idml] -> id/todo/view/layout.gen.id"
node "$HERE/build-scene.mjs"

echo "done. build the app with:  ../bin/id id   (no Node, no --backend)"
