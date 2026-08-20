#!/usr/bin/env bash
# Compile the id game (flappy/id) to WebAssembly and put it where Next can
# serve it. idc.py's wasm backend exports every id function plus id_alloc and
# the linear memory, which is all lib/id-runtime needs to drive it.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP="$(cd "$HERE/.." && pwd)"
REPO="$(cd "$APP/.." && pwd)"

mkdir -p "$APP/public"
echo "[build:id] compiling flappy/id -> public/flappy.wasm"
"$REPO/idc.py" "$APP/id" --target wasm -o "$APP/public/flappy.wasm"
echo "[build:id] done ($(wc -c < "$APP/public/flappy.wasm") bytes)"
