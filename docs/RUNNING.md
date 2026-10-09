# Running the kernel and the editor

> **Status: a description.** Every command below was run to write this page,
> and the output shown is the output it produced.

Everything below needs the dev shell, which carries the toolchain — `clang`,
`lld`, `qemu`, X11, `node`, `unzip`:

```sh
nix develop                      # or `direnv allow` once, then it is automatic
```

`idc/tools/devshell.sh '<cmd>'` runs a single command in that shell if you would
rather not stay in it. Every command here assumes the repository root.

---

## The kernel

### Build it

```sh
idc/bin/idc idc/tools/kbuild -o /tmp/kbuild && /tmp/kbuild idc   # -> idc/build/kernel.elf
```

That compiles `idc/runtime/` and `kernel/prog/` through the LLVM target, assembles
`kernel/boot/{boot,isr}.S`, and links with `ld.lld` over `kernel/boot/kernel.ld`.
No C compiler is involved: `clang` appears twice, once as an assembler and once
as an LLVM IR compiler.

### Look at it

```sh
qemu-system-x86_64 -kernel idc/build/kernel.elf -vga std -serial stdio
```

A window opens with a 640×480 framebuffer. It prints its boot lines, runs its
self-demonstrations, draws three colour bands and a diagonal, scrolls forty
lines of text past the bottom of the screen, and drops into the shell. **Type
in the QEMU window** — the PS/2 keyboard works.

Add `-display none` to run it headless; the serial port carries the same text.

### Drive it

The shell reads the keyboard *and* the serial port through one function, so
anything you can type you can also pipe:

```sh
printf 'help\nls\ncd bin\ncat hello\nuname\nmem\nhalt\n' \
  | qemu-system-x86_64 -kernel idc/build/kernel.elf -display none -serial stdio
```

Commands: `help ls cd pwd cat echo mkdir touch write rm clear uname mem halt
fault`. `write PATH TEXT` is the whole editor. `fault` reads an address with no
page behind it, so you can see the fault handler:

```
/ $ fault
fault: reading 0x140000000, which has no page behind it

*** fault: page fault (vector 14, error 0)
*** at 0x00000000001002d0
*** halted
```

### Photograph it

`idc/tools/qmon`, in `id`, boots it, types at it over the serial port, and
captures the framebuffer; `idc/tools/fbtext`, also in `id`, reads that capture
back as text by matching each 8×16 cell against the kernel's own font. That pair
is how the shell is tested, and it is the fastest way to see what is on screen
without a window. `idc/tools/buildrun` builds either one (with the standard
library, whatever `IDC_NO_STD` says) and runs it, and `--stdin` hands it
buildrun's own standard input, which fbtext reads the kernel's `conf.id` from:

```sh
idc/bin/idc idc/tools/buildrun -o /tmp/buildrun
/tmp/buildrun idc qmon idc/build/kernel.elf --wait 4 --type "ls;cd bin;uname" \
        --settle 2 --shot /tmp/screen.ppm
/tmp/buildrun --stdin idc fbtext /tmp/screen.ppm < kernel/prog/conf.id
```

`--keys "l s ret"` sends real PS/2 key events instead, which is how to exercise
the keyboard path rather than the serial one.

### Check it

```sh
idc/tests/kernel.sh              # the kernel's checks
```

---

## The editor

### Build it

```sh
idc/bin/idc editor --allow-untested -o editor
```

`--allow-untested` because neither the editor nor `idstd` has all its test
cases yet; it is deprecated ([`TESTS.md`](TESTS.md)).

That is the whole thing: `editor/lib/{zip,doc,font}` and `editor/app`, plus the
`fs` and `gfx` backends its `conf.id` names.

### Look at it

```sh
FONT=$(fc-match -f '%{file}' 'DejaVu Sans')
./editor idc/tests/fixtures/sample.odt "$FONT"
```

A window opens with the document rendered at 640×480. Escape or `q` closes it.
The listing on stdout is the *model* — what the ODT layer made of the file,
before any pixels:

```
[0] 1 run(s)
    italic 18pt DejaVu Serif: A document, read by id
[1] 1 run(s)
    regular 12pt DejaVu Sans: This paragraph is plain text at twelve points. It is long...
[2] 3 run(s)
    regular 12pt DejaVu Sans: Styles change mid-paragraph: 
    bold 12pt DejaVu Sans: this run is bold
    regular 12pt DejaVu Sans:  and this one is not. Entities survive too & so do <angle...
[3] 0 run(s)
[4] 1 run(s)
    regular 12pt DejaVu Sans: Numbers 0123456789 and punctuation .,;:!?()-- render from...
```

`[3]` has no runs: that is the empty paragraph, and it becomes a blank line on
the page rather than disappearing. `italic 18pt DejaVu Serif` is what the
document *asks* for -- given one font file, the heading is drawn sheared, which
is the faux italic `docs/EDITOR.md` describes.

### Render it to a file

```sh
./editor idc/tests/fixtures/sample.odt "$FONT" --ppm /tmp/page.ppm
```

A PPM, which most viewers open directly. To read it in a terminal:

```sh
node - /tmp/page.ppm <<'EOF'
const d = require("fs").readFileSync(process.argv[2]);
let p = 0;
const h = [];
while (h.length < 3) { const n = d.indexOf(10, p); h.push(d.toString("latin1", p, n)); p = n + 1; }
const w = Number(h[1].split(/\s+/)[0]);
for (let y = 0; y < 200; y += 2) {
  let s = "";
  for (let x = 0; x < 300; x++) s += " .*#"[Math.min(3, (255 - d[p + (y * w + x) * 3]) >> 6)];
  console.log(s.trimEnd());
}
EOF
```

### Try it on your own document

Any `.odt` LibreOffice writes:

```sh
./editor ~/Documents/whatever.odt "$FONT" --ppm /tmp/page.ppm
```

It will show you what it made of it. What it does *not* do is listed at the end
of [`docs/EDITOR.md`](EDITOR.md) — no tables, images, lists or footnotes, one
font face at a time, and no scrolling, so only the first page's worth is drawn.
`buildrun idc mkodt` (`idc/tools/buildrun`, see "Photograph it") regenerates the fixture if you want a smaller thing to poke at.

### Check it

```sh
idc/tests/editor.sh              # the editor's suites
```

---

## Everything at once

```sh
idc/tools/devshell.sh 'idc/tests/run.sh'          # the whole suite (over a minute: run it by section)
idc/tools/devshell.sh 'idc/tests/run.sh --list'   # the sections, to run one
```

No step may run longer than a minute, so a script that would is cut into
sections: `run.sh`'s, each warm under the minute. A section names what it holds
(`conform_float`, `invalid_1of4` to `invalid_4of4`, `stdlib_dce`,
`self_host_build_project_2`, `kernel_boot`); `run.sh --list` prints them with their
indices. The scripts behind them take the same pieces as arguments
(`idc/tests/backends.sh --list`, `idc/tests/self_host_build.sh --list`,
`idc/tests/conform.sh AREA...` with `AREA:K/N` for the Kth of N parts of an area,
`idc/tests/invalid.sh K N`, `idc/tests/stdlib.sh 1|2|3`, `idc/tests/kernel.sh build|boot|kfree`).
What a stopped run had finished is kept (parsed sources, compiled units, passed
cases, the library's pre-check), so running the same command again continues
instead of starting over; `run.sh --resume` does the same for whole sections.
A cold cache is another matter: the first build after a compiler change
rebuilds the compiler's own stages, which takes minutes. `idc/tools/regen_bootstrap.sh`
takes the steps `stages`, `lex`, `parse-front`, `emit` and `compare`, each one
result line, and skips a step whose inputs have not changed.

## Where to look for what to work on next

* [`docs/KERNEL.md`](KERNEL.md) — "what is not there yet", in order.
* [`docs/EDITOR.md`](EDITOR.md) — the same, for the editor.
* [`docs/STATUS.md`](STATUS.md) — what is measured: which trees exist, which
  functions still lack their cases, how the cases are distributed.
