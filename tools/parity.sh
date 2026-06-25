#!/usr/bin/env bash
# Differential test: does the id-written compiler emit the same C as idc.py?
#
#   tools/parity.sh prog.id              # one file
#   tools/parity.sh demos/calc           # a directory (all its .id files)
#   tools/parity.sh a.id b.id            # several files, in order
#
# Exit 0 if the emitted C is byte-identical, else 1 (and shows the diff).
set -u
cd "$(dirname "$0")/.."

IDC=./idc.py
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT

# expand directory args into their sorted .id files (matching idc.py)
files=()
for a in "$@"; do
    if [ -d "$a" ]; then
        for f in "$a"/*.id; do files+=("$f"); done
    else
        files+=("$a")
    fi
done

# build the two compilers (lexer + parser/codegen) once
$IDC demos/idc_in_id      -o "$TMP/idlex"   2>/dev/null || { echo "lexer build failed"; exit 2; }
$IDC demos/idc_in_id_parse -o "$TMP/idparse" 2>/dev/null || { echo "idparse build failed"; exit 2; }

# C from idc.py
$IDC "${files[@]}" --emit-c "$TMP/py.c" >/dev/null 2>&1 || { echo "idc.py failed on input"; exit 2; }
# C from the id-written compiler (lexer | parser+codegen) over the concatenation
cat "${files[@]}" | "$TMP/idlex" | "$TMP/idparse" > "$TMP/id.c"

if diff "$TMP/py.c" "$TMP/id.c" >/dev/null; then
    echo "MATCH   $*"
    exit 0
else
    echo "DIFFER  $*"
    diff "$TMP/py.c" "$TMP/id.c" | head -40
    exit 1
fi
