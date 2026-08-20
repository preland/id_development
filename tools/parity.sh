#!/usr/bin/env bash
# Differential test: does the id-written compiler emit the same C as idc.py?
#
#   tools/parity.sh prog.id        # a single .id file
#   tools/parity.sh demos/calc     # a project directory (its whole .id tree)
#
# Exit 0 if the emitted C is byte-identical, else 1 (and shows the diff).
#
# Not for a project that uses a native backend (demos/gfxdemo, demos/fsdemo,
# ...). Neither side of the comparison is told a backend is coming, so the
# calls it provides look like calls to nothing: idc.py stops, and idparse --
# run here without the --extern-ok that bin/idc passes it -- reports them
# instead of emitting the extern block. Those projects are checked the same
# way, with the backend attached, by tests/backends.sh.
set -u
cd "$(dirname "$0")/.."

IDC=./idc.py
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT

target="${1:?usage: parity.sh <file-or-project-dir>}"

# build the two compilers (lexer + parser/codegen) once
$IDC demos/idc_in_id       -o "$TMP/idlex"   2>/dev/null || { echo "lexer build failed"; exit 2; }
$IDC demos/idc_in_id_parse -o "$TMP/idparse" 2>/dev/null || { echo "idparse build failed"; exit 2; }

# C from idc.py
$IDC "$target" --emit-c "$TMP/py.c" >/dev/null 2>&1 || { echo "idc.py failed on input"; exit 2; }
# C from the id-written compiler. For a project, feed every .id file in the tree
# in the same order idc compiles them (sorted by full path); for a single file,
# just that file.
if [ -d "$target" ]; then
    find "$target" -name '*.id' | LC_ALL=C sort | xargs cat | "$TMP/idlex" | "$TMP/idparse" > "$TMP/id.c"
else
    "$TMP/idlex" < "$target" | "$TMP/idparse" > "$TMP/id.c"
fi

if diff "$TMP/py.c" "$TMP/id.c" >/dev/null; then
    echo "MATCH   $target"
    exit 0
else
    echo "DIFFER  $target"
    diff "$TMP/py.c" "$TMP/id.c" | head -40
    exit 1
fi
