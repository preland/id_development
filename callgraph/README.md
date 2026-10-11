# callgraph

A viewer for the call graph of an `id` program, and the first user of idstd's graph kit (`graph_` in
`core/data/graph/`, `graph_view_` in `kit/ui/graph/`). The tree holds only the reading of the data and the command line;
the layout and the painting are in the kit, so another tool can draw a graph the same way.

```
idc idstd --calls > calls/idstd.txt
idc callgraph -o callgraph
callgraph --stats calls/idstd.txt
callgraph --dump calls/idstd.txt --root graph_levels --depth 3
callgraph --render calls/idstd.txt OUT.ppm --root graph_levels --depth 2
```

`--stats` prints the number of functions and of distinct call edges (a `call` and a `value` row for the same pair
are one edge), without and with the calls of builtins. `--dump` prints `label x y layer` for each box of the tree of
what the root calls to the depth; a label ends in `*` when the box repeats a function drawn out elsewhere in the
tree. `--render` writes the same picture as a binary PPM. Builtins are left out of the picture.

Layout: `ingest/` reads the rows into two bundles of lists (`conf.id` says which is which), `view/` builds the tree
and its layout, `render/` paints it and writes the file, `cli/` is the command line.

## Interaction

```
callgraph calls/idstd.txt --root graph_depth_first [--depth 2]
callgraph --script S.txt calls/idstd.txt --root graph_depth_first [--depth 2] [--dump] [--render-after OUT.ppm]
```

The first opens a window (wheel zooms about the pointer, a drag pans, a click selects, a double click or Enter on the
selection expands or collapses what it calls, `/` text Enter searches the boxes on screen, Esc clears; hovering a box
shows its file:line, its number of cases and the first line of the comment above it). The second replays a script, one
event per line (`wheel X Y DY`, `down X Y [BUTTON [CLICKS]]`, `move X Y`, `up X Y`, `key NAME`, `text STR`, `size W H`,
`#` for a note) and then prints the camera, the selection, the search text and the boxes, and writes the picture.

`golden/*.txt` are scripts over `golden/mini.calls` and `golden/*.out` what they must print:

```
callgraph --script golden/expand.txt golden/mini.calls --root main --depth 2 --dump | diff - golden/expand.out
```

Headless: `GFX_MAX_FRAMES=60 idc/tools/headless.sh ./callgraph calls/idstd.txt --root graph_depth_first` (needs Xvfb).
