#!/usr/bin/env bash
# Draw every sprite. flappy/sprites is an id program that prints all of the
# game's art to stdout as SVG, each file behind a ">>>name.svg" marker; this
# splits that stream into public/sprites/. Nothing in the game's art comes from
# anywhere else -- there are no binary assets in this project.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP="$(cd "$HERE/.." && pwd)"
REPO="$(cd "$APP/.." && pwd)"
OUT="$APP/public/sprites"
BIN="$(mktemp -d)/mksprites"

echo "[build:sprites] compiling flappy/sprites"
"$REPO/idc.py" "$APP/sprites" -o "$BIN"

rm -rf "$OUT"
mkdir -p "$OUT"
"$BIN" | awk -v out="$OUT" '
  /^>>>/ { f = out "/" substr($0, 4); next }
  f      { print > f }
'
echo "[build:sprites] wrote $(ls -1 "$OUT" | wc -l) sprites to public/sprites"
