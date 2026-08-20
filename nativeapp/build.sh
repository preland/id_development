#!/usr/bin/env bash
# Build the native "id . todo" app with ONLY the id compiler -- no other tooling
# in the loop. The app's dependency (the software-graphics backend) is declared
# in id/import.id, so the whole build is just the id compiler on the directory:
#
#   ./bin/id nativeapp/id
#
# The generated sources it needs -- the bitmap font (id/gfx/draw/text/
# glyphs.gen.id) and the idml-resolved layout (id/todo/view/layout.gen.id) --
# are committed. They only need regenerating if you change the font table or
# ui/todo.idml; that's an offline step (scripts/regen.sh, which uses Node) and
# is NOT part of building or running the app.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/.." && pwd)"

exec "$REPO/bin/id" "$HERE/id" -o "$HERE/todoapp"
