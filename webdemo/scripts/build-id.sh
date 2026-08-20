#!/usr/bin/env bash
# Compile the id todo project (webdemo/id) to WebAssembly and place it where the
# Next app can serve it (public/todo.wasm). Uses idc.py's wasm backend, which
# exports every id function + id_alloc + memory for the JS runtime to drive.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WEBDEMO="$(cd "$HERE/.." && pwd)"
REPO="$(cd "$WEBDEMO/.." && pwd)"

mkdir -p "$WEBDEMO/public"
echo "[build:id] compiling webdemo/id -> public/todo.wasm"
"$REPO/idc.py" "$WEBDEMO/id" --target wasm -o "$WEBDEMO/public/todo.wasm"
echo "[build:id] done ($(wc -c < "$WEBDEMO/public/todo.wasm") bytes)"
