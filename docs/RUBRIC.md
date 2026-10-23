# The A-grade rubric

> **Status: approved by the user (D29).** It says what a row of the ecosystem assessment has to show
> before it is graded A. Nothing here is built; the plan ids (P1.1, P2.3a, ...) are the items in
> `.claude/plan.json`. Anything marked *(proposal)* was invented while drafting, not derived from a decision.
> Figures that change (function counts, benchmark ratios, case counts) are never written here; they are in
> [`STATUS.md`](STATUS.md) or come from the command a section names.

## 1. What an A is

Decided (D1): a row is graded A when **all four** of these hold.

| part | what it proves | one-line test |
| --- | --- | --- |
| (a) flagship | the language can build the real thing | the flagship in section 4 builds and passes its checklist |
| (b) perf bar | not slower than C where C is the yardstick | every benchmark of the row is at most 1.25x the C reference's wall time |
| (c) blind trial | a newcomer can do it from the docs | a fresh Sonnet agent with only the docs builds the small variant within its budget |
| (d) soak/limits | it keeps working under load and over time | the row's slope, long-lived and limit checks pass |

Decided (D5): a row's A is a **Linux A**. The platform pass (aarch64 Linux, macOS M4, Windows 11) is a separate
item (X.3) and does not change a Linux grade. *(proposal)* Grades below A, so a partial row is still recorded:
**B** is three of the four parts, **C** the flagship alone, **D** a prototype that builds but fails its
checklist, **F** nothing. Only A is a goal; the lower letters show progress in section 6.

### The 60-second rule applies to every check

No test, benchmark step, trial step or soak step may take more than 60 s. A longer check is split into
**steps** that are index-addressable (`STEP k of K`) and resumable (a step finds earlier results on disk and
skips finished ones). The one exception is R14's recorded live-audio gate (D18), which is manual. A benchmark
input is sized so the C reference takes about half a second (`docs/PERFORMANCE.md`, section 1); a blind trial
is one session bounded by tool calls, with build and test commands under 60 s each.

### Soak, common protocol (D11)

A soak never measures wall hours. Each row's soak (d) has two kinds of check; the row's **Soak/limits** entry
says what each measures. The iteration count of a step is fixed by the row and cannot be lowered to pass.

1. **In-step slope, every row.** *(proposal)* A step runs a fixed N iterations, samples the resource (RSS,
   descriptors, latency) at N/4 and at N, and fails if growth over the last three quarters exceeds the row's
   threshold. K steps at increasing N separate per-iteration growth (a leak) from one-off growth (a cache).
2. **Long-lived process, on rows where one can stay up** (daemon, server, game, DAW, desktop apps; marked
   **Long-lived**). A control script starts the process once and writes its pidfile; each step finds it by the
   pidfile, drives a fixed workload and samples `/proc/PID` (RSS, descriptors, threads). Pass: RSS at the end
   of step k minus RSS at the end of step 2 stays under the row's bound for all k; descriptors and threads are
   constant. *(proposal)* A stale pidfile fails the step; it never restarts the process. One-shot rows (R1, R2,
   R12) have no long-lived check.

## 2. The perf bar (b), common protocol

Decided (D7): **1.25x gcc -O2 wall time on every row**, I/O-bound rows included; a row with no benchmark has
no A. Decided (D17): **only a quiet-machine run can grant an A.** A run on a loaded machine (`meta.txt` load
average) is `advisory`: recorded and shown, never counted.

Each benchmark has a **named C reference**, a single-file C program written as a competent C programmer writes
it first, in `bench/ref/c/` beside the existing ones; the id program is under `bench/id/NAME/`. The method is
`docs/PERFORMANCE.md`, section 3:

* `gcc -O2 -ffp-contract=off` for the reference; id built with `idc/bin/idc`, default target (`id-c`).
* Both pinned with `taskset -c CORE`, one at a time, alternating rounds (C, id, C, id, ...); the metric is the
  **median of per-round id/C wall-time pairs**, at least five rounds, with min and max recorded.
* Both print the same bytes; the harness compares **output hashes**. A mismatch is `FAIL`, whatever the time.
* Wall time and peak RSS from `time -f '%e %M %U %S'` on the benchmark process only. *(proposal)* RSS is
  recorded, not graded; over 4x the C reference's RSS is flagged for review.
* *(proposal)* Inputs target 0.5 to 1 s of C time so five rounds fit 60 s; otherwise rounds are addressed by
  index through the harness's resumable `results.tsv`.
* **I/O-bound rows** use the same bar with C using the interface the plan item commits to (D9: epoll plus
  sendfile/splice, io_uring only if a benchmark misses 1.25x). Load generator, files and machine are the same
  for both programs. *(proposal)* Network benchmarks run over loopback, generator pinned to another core.

Existing benchmarks (nbody, spectral, fannkuch, mandel, btrees, fasta, knuc, sortb, strbuild, expr, csv, json)
are reused where a row names them. Their ratios are in `STATUS.md`, "Benchmarks"; a ratio above 1.25 there is
work for P1.7 and P1.8, not an exemption.

## 3. The blind trial (c), common protocol

Unless a row says otherwise:

* The agent is a fresh **Sonnet** session with no memory and no repository history. *(proposal)* It gets
  `docs/`, the `idstd` source tree and a one-paragraph brief; not the flagship's source, other trials, or
  compiler internals. It works in an empty project directory in the repository's nix shell and may run `idc`
  and what it builds.
* **Budget:** a count of tool calls per row; reading a file counts. Exhausting it ends the trial.
* **Pass:** (1) `idc` builds with no `--allow-untested` and no suppressed warnings; (2) its test cases pass
  and each function has the two cases `docs/TESTS.md` requires; (3) the brief's hidden behaviour script
  passes; (4) the budget was not exceeded.
* **Recorded, not graded:** the first diagnostic the agent could not act on, and each place it searched for a
  builtin or idstd function and did not find it (X.1). Several on one trial is a doc bug, even on a pass.
* Decided (D20): three sessions; the row passes with **2 of 3**.
* After a doc change caused by a trial's findings, the trial is re-run on a new agent; a fix is not accepted on
  the strength of the agent that found it.

## 4. The rows

Each row: **flagship**, **perf bar**, **blind trial**, **soak/limits**, **depends on**. Linux only (D5).

### R1 Simple CLI

- **Flagship.** `idgrep`, a line-oriented text tool, in a new tree `trials/idgrep`.
  - [ ] Documented idstd argument parser: short and long flags, values, `--`, generated `--help`.
  - [ ] Files or standard input; fixed strings and a documented regex subset (classes, anchors, `*`, `+`, `?`,
    alternation).
  - [ ] `-i`, `-v`, `-c`, `-n`, `-l`, `-r`; exit status 0 / 1 / 2 as grep's; errors name the file.
  - [ ] Binary-safe: a NUL does not end the line (P1.2). Every function has two cases, no exemption.
- **Perf bar.** `bench/id/grep` vs `bench/ref/c/grep.c`, two benchmarks (fixed string; `[a-z]+@[a-z]+`) over a
  generated 64 MB file of random words with one match per ~1000 lines, in page cache.
- **Blind trial.** "Build a tool `wc2` taking `-l`, `-w`, `-c` and file names (or `-` for stdin), printing one
  line per file and a total, exiting 2 with a message on a missing file. Use idstd for arguments." 60 tool
  calls. Hidden script: five inputs incl. an empty file, no trailing newline, a missing name.
- **Soak/limits.** *(proposal: thresholds)* Slope: (1) a 1 GB file streamed in 20 steps of 50 MB; RSS slope 0,
  peak under 32 MB. (2) A 100000-file tree walked in steps of 5000; descriptors equal at each step's start and
  end. Limit: (3) a 100 MB line is read by `-c` without trapping. Long-lived: none.
- **Depends on.** P1.2; P1.1; P1.7 for the bar.

### R2 Sorting

- **Flagship.** `idstd` sort (stable, and unstable via introsort or pdqsort *(proposal: implementer's choice)*)
  plus a `sort` tool `trials/idsort`.
  - [ ] `sort_int`, `sort_float`, `sort_str`, and sort by key function (`func(T) return R`).
  - [ ] Stable variant documented and tested stable (equal keys keep order).
  - [ ] CLI: `-n`, `-r`, `-k`, `-u`, `-s`; external merge sort beyond the `-S` memory budget.
  - [ ] Perf-bounded cases `[time:O(n log n), mem:O(n)]` on two points (docs/TESTS.md).
- **Perf bar.** `bench/id/sortint`, `sortstr`, `sortkey` vs C `qsort` and a hand-written pdqsort *(proposal)*;
  within 1.25x of the **faster** of the two. Inputs: 10 million random 64-bit ints; 1 million 16-byte strings;
  1 million records by a 32-bit key. The existing `sortb` stays a regression check and does not satisfy this.
- **Blind trial.** "Sort records by `last` ascending then `first` descending, stable, using idstd, with test
  cases." 40 tool calls. Also: no hand-written sort (a second sort is a duplicate-logic compile error).
- **Soak/limits.** Slope: (1) adversarial inputs (sorted, reverse, all-equal, organ-pipe, quicksort-killer),
  1 million each, one per step, each within 2x of random-input time. (2) External sort of 2 GB: 40 steps of
  50 MB run generation, then 10 merge steps; peak RSS under the `-S` budget plus 10%. Long-lived: none.
- **Depends on.** P1.4; P1.7; P1.3 for 64-bit keys.

### R3 Website, frontend and backend

- **Flagship.** `trials/httpd` grown into a link-sharing board over HTTPS: `GET /` and assets,
  `POST /api/links`, `GET /api/links?tag=...`, `DELETE /api/links/ID`.
  - [ ] HTTP/1.1: keep-alive, chunked, ranges, ETag, gzip, redirects, exact `Content-Length`, size limits
    (P2.3b). TLS 1.3 with a certificate chain from files (P2.3a).
  - [ ] Many connections on the epoll loop (P1.5c), not a thread each; state in the embedded database,
    surviving restart (P2.1c).
  - [ ] Frontend: an idml page compiled to wasm calling the API (the `id_webdemo` route; `id_webdemo` is a
    sibling repo at `~/git/id_webdemo`, not part of `id_development`), plus a no-script HTML fallback.
  - [ ] Documented log line format; SIGTERM drains in-flight requests.
- **Perf bar.** `bench/id/httpd` vs `bench/ref/c/httpd.c` (single-threaded epoll, `sendfile`, hand-written
  parser; D9). (1) static 4 KB keep-alive, 64 connections; (2) static 1 MB; (3) JSON list of 100 rows from
  memory. One checked-in load generator drives both servers *(proposal: in `bench/ref/c/`)*. Metric: wall time
  for 200000 requests. Plain HTTP carries the bar; TLS is reported against a C reference linking OpenSSL once
  P2.3a exists *(proposal)*.
- **Blind trial.** "Serve `./public` on port 8080; `GET /api/time` returns `{"now": <int>}`; `POST /api/echo`
  returns the body as JSON; 404 for a missing file, 413 over 1 MB." 80 tool calls. Hidden script: an id test
  client, three requests over one kept-alive connection.
- **Soak/limits.** Slope: (1) 20 steps of 20000 requests; RSS growth per step under 1% of step 1's peak after
  step 2, descriptors constant. Limits: (2) 100, 1000, 5000, 10000 idle keep-alive clients, one count per step;
  no trap, a random client answered within 1 s. (3) 1000 clients sending a byte per second are dropped by the
  timeout without blocking others. (4) A 10 GB range is served in 1 MB pieces without RSS growth.
  **Long-lived:** one server across all steps, found by its pidfile.
- **Depends on.** P2.3a, P2.3b, P2.1c, P1.5c, P1.8, P1.1, P1.2; P3.1; P2.3c only if the board uses WebSocket
  *(proposal: it does not)*.

### R4 Daemon

- **Flagship.** `idqueued`, a job-queue daemon with a Unix-socket control interface and CLI client, in
  `trials/idqueued`.
  - [ ] Daemonises or stays foreground under a supervisor; pidfile; readiness via `sd_notify` (P2.5c).
  - [ ] Jobs (command and arguments) on a Unix socket, run under a concurrency limit, state in the embedded
    store (P2.1c); survives a crash and restarts with the queue intact.
  - [ ] SIGHUP re-reads config without dropping jobs; SIGTERM drains.
  - [ ] Size-rotated log file, no unbounded in-memory log; reaps children (no zombies); per-job timeout.
- **Perf bar.** `bench/id/queued` vs `bench/ref/c/queued.c`, a C daemon of the same protocol (epoll,
  `fork`/`exec`). (1) enqueue-and-complete 100000 `/bin/true` jobs, 8 workers; (2) 1 million status queries on
  one connection. Final state dump compared by hash.
- **Blind trial.** "A daemon on a Unix socket accepting `add N` and `get`, keeping a running total, writing a
  pidfile, exiting cleanly on SIGTERM and removing pidfile and socket. Also the client." 60 tool calls. Hidden
  script: 1000 `add` lines from 10 clients, a signal, then total, missing pidfile, missing socket.
- **Soak/limits.** Slope: (1) 20000 jobs per step; zombie and descriptor counts constant at each step's end.
  Limits: (2) 100000 queued jobs reload from disk in under 60 s. (3) Kill -9 in a random step; the next step
  finds the queue intact. **Long-lived:** 50 steps against one daemon found by its pidfile; RSS at step k minus
  step 2 under 1 MB.
- **Depends on.** P1.1, P1.5c, P2.5c, P2.1c, P1.8.

### R5 Linux kernel module

- **Flagship.** `idkmod_echo`, a loadable `.ko` written in id that registers `/dev/idecho`. Decided (D12): it is
  tested in a **disposable QEMU VM built by nix**; `insmod` and `rmmod` must work for real against that VM's
  kernel; there is no mock shim and no host-kernel run.
  - [ ] Builds against the VM kernel's headers by an `idc` target (P1.6c); no C source beyond the checked-in
    declarations of kernel types.
  - [ ] `module_init` / `module_exit`, leveled `printk`, module parameters.
  - [ ] Character device `open`/`read`/`write`/`release` with a bounded `kmalloc`/`kfree` ring buffer; a timer
    or workqueue entry appending a tick counter; locks via kernel spinlock/mutex APIs through the C ABI.
  - [ ] Loads, runs and unloads cleanly in the VM; `lsmod` shows reference count 0 afterwards.
  - [ ] Every function has two cases that run on the host (the `STATUS.md` `asm` exemption is the true
    boundary only).
- **Perf bar.** `bench/ref/c/kmod_echo.c`, a C module of the same interface, built and loaded in the same VM.
  (1) 1 million 64-byte `write`s then 1 million `read`s; (2) 100 load/unload cycles. Metric: wall time of one
  shared C user-space driver, 5 alternating rounds pinned inside the VM *(proposal)*. `.ko` size reported only.
  D17 applies to the host running the VM.
- **Blind trial.** "A kernel module creating `/dev/hello` that returns `hello\n` on read and ignores writes.
  Build with `idc` for the kernel at `KDIR`." 80 tool calls. Run condition: `insmod` in the VM image (the
  brief gives its start command), `cat /dev/hello`, `rmmod`. The agent has no way to run on the host kernel.
- **Soak/limits.** Slope: (1) 100 load/unload cycles in 5 steps of 20; `slabtop`/`kmemleak` show no growth,
  use count 0 each time. (2) 8 processes writing concurrently, 10 steps of 1 million writes; no oops in
  `dmesg`, contents match a shared checksum. Limit: (3) a write larger than the buffer errors, never overruns.
  **Long-lived:** the VM and loaded module stay up across (2), found by the qemu pidfile; `/proc/slabinfo` at
  step k within 1 MB of step 2.
- **Depends on.** P1.6c, P1.6a, P1.6b (a table of function pointers).

### R6 Web app

- **Flagship.** `id_webdemo` (a sibling repo at `~/git/id_webdemo`) grown into a task-board app: lists, cards,
  drag to reorder, offline-capable, synced to the R3 backend.
  - [ ] State and logic in id compiled to wasm; the whole view in idml (as `flappy-game`, `idml-integration`).
  - [ ] Persists to `localStorage`/IndexedDB via the JS interop layer; syncs when online.
  - [ ] Routing (back button), form validation, keyboard operation, focus order, accessible roles.
  - [ ] Growable wasm heap (P1.1c); a 5000-card board does not trap.
  - [ ] Verified in a real browser by the browser check, not only node; the production build is one static
    directory with content-hashed asset names.
- **Perf bar.** Decided (D15): **both** bars apply. (1) Compute: `expr`, `json`, `strbuild`, `sortb` on
  `--target wasm` under node vs the same C compiled to wasm with the same toolchain (`clang --target=wasm32
  -O2`), node pinned, 1.25x *(proposal: the C reference is compiled to wasm because the claim is about the
  id compiler)*. (2) UI: rendering 5000 cards and moving one in a headless browser is at most 1.25x of a
  hand-written JS/DOM reference (`bench/ref/js/board.js`), the median of page-recorded `performance.now()`
  differences over 5 rounds.
- **Blind trial.** "With idml and the wasm target, build a page with a counter and a text field: typing shows
  the length, the button increments the counter, the counter survives reload. Provide the HTML." 60 tool
  calls. The browser check loads it headlessly, types, clicks, reloads, reads the DOM.
- **Soak/limits.** Slope: (1) 200 add/remove cycles of 5000-card boards in 10 steps of 20; wasm heap at each
  step's end does not grow after step 2. Limits: (2) 100000 cards load without trapping, or say they cannot.
  (3) Offline for 100 edits, then online: the backend ends with all 100, in order. **Long-lived:** one headless
  browser held open across steps (pidfile); JS and wasm heap at step k within the bound of step 2.
- **Depends on.** P1.1c, P1.1, P3.1, R3's backend; P2.3c only if sync uses WebSocket *(proposal)*.

### R7 Desktop app

- **Flagship.** `idnotes`, a plain-text and Markdown note taker on the app kit (P3.4), new tree `idnotes`;
  small on purpose, so the row proves the framework.
  - [ ] Undo/redo, autosave to a recovery file, crash recovery on next start.
  - [ ] Native file dialogs, recent files, drag-and-drop of a file onto the window.
  - [ ] Clipboard (text, rich text), IME composition, HiDPI scaling (P3.2).
  - [ ] Menus and shortcuts from one table, shown in menus; find and replace; word wrap with bidi and
    complex-script shaping (P3.3).
  - [ ] Accessibility tree exposed, every control reachable and labelled; follows `idtheme`, light and dark.
- **Perf bar.** Decided (D16): the reference is **a C widget on the same font rasteriser**
  (`bench/ref/c/notes_edit.c`, same shared buffer *(proposal: no SDL)*) vs `bench/id/notes_edit`. (1) insert 1
  million characters one at a time into a 10 MB document, laying out after each batch of 1000; (2) open and lay
  out a 50 MB file; (3) find-all over 10 MB. Final text and line-break table hashed. Frame time at 60 Hz is
  reported separately.
- **Blind trial.** "With the idstd app kit, build a window with a text area and Save and Load buttons that
  read and write a file named in a path field; Ctrl+S saves." 80 tool calls. Hidden script: the kit's headless
  input injection, then a file compare.
- **Soak/limits.** Slope: (1) 10000 edit/undo/redo operations in 10 steps; RSS bounded by the app's undo cap,
  flat after it. Limits: (2) a 500 MB file opens read-only or refuses naming the limit. (3) Kill -9 mid-edit in
  a random step; the next start recovers every edit up to the last autosave. **Long-lived:** the app runs
  headless across steps (pidfile); RSS and descriptors at step k within 1 MB of step 2 after the cap.
- **Depends on.** P3.1 to P3.4, P1.1.

### R8 Word processor

- **Flagship.** `quill` (docs/QUILL.md) to daily-driver; its checklist is the spec, this rubric adds the gates.
  - [ ] `.odt` and `.docx` open/save with a round-trip test (text and QUILL.md's styles equal) on `quillcorpus`;
    the corpus opens with a documented unsupported-features list and no trap.
  - [ ] Styles, lists, tables, images, headers/footers, footnotes, page layout, print-to-PDF.
  - [ ] Spell check, word count, regex find and replace; undo/redo, autosave, recovery; track changes read and
    written; a 300-page document edits without a visible stall.
- **Perf bar.** `bench/id/quill_layout` vs `bench/ref/c/layout.c`, the same line-breaking and pagination
  algorithm in C over the same font metrics *(proposal: not LibreOffice, whose feature set differs)*. (1)
  paginate a generated 300-page, 1.5-million-word document; (2) re-paginate after a one-character edit on page
  1; (3) save to `.odt` (zip + XML, P2.1b). Page-break table hashed.
- **Blind trial.** "With the `quill` model library, read an `.odt`, replace every `foo` by `bar` keeping
  formatting, write the result." 80 tool calls. Hidden script: two documents with bold runs and a table; XML
  checked.
- **Soak/limits.** Slope: (1) 1000 insert/delete/undo operations on a 300-page document in 10 steps; RSS flat
  after step 2. Limits: (2) corpus round-trip in steps of 10 documents; none trap. (3) A 5000-page document
  opens or refuses naming the limit. (4) A 100-file malformed `.docx` corpus (truncated zip, bad XML) in 4
  steps: errors, not traps. **Long-lived:** the editor runs headless across (1) (pidfile); RSS within 1 MB of
  step 2.
- **Depends on.** P3.3, P3.4, P2.1b, P1.1; P2.4a for images.

### R9 Image editor

- **Flagship.** `idpaint`, a layered raster editor, new tree `idpaint`.
  - [ ] Layers with blend modes (normal, multiply, screen, overlay), opacity, masks.
  - [ ] Brush, eraser, fill, selection (rectangle, lasso), move, crop, text.
  - [ ] Filters: gaussian blur, sharpen, levels, curves, hue/saturation.
  - [ ] PNG and JPEG open/save, WebP read (P2.4a); ICC read and sRGB conversion.
  - [ ] Canvas to 16384 x 16384 as tiles, only visible tiles resident when clean (P3.5); undo/redo by tile
    diff, memory-bounded; native project file preserving layers.
- **Perf bar.** `bench/id/gblur`, `blend`, `pngenc`, `jpegdec` vs plain C references with no SIMD intrinsics,
  so the bar tests P1.4's auto-vectorisation. Input: a generated 4096 x 4096 RGBA image. (1) gaussian blur,
  radius 8; (2) 8-layer multiply composite; (3) PNG encode; (4) 24 MP JPEG decode. Pixels or encoded bytes
  hashed; JPEG decode tolerance zero *(proposal: both use the same integer IDCT)*.
- **Blind trial.** "Read a PNG, apply a 3x3 box blur and a command-line brightness adjustment, write a PNG,
  using idstd's image library." 60 tool calls. Hidden script: a 64 x 64 image compared with zero tolerance.
- **Soak/limits.** Slope: (1) a 16384 x 16384 canvas, 10 steps of 100 brush strokes; resident memory bounded
  by the tile cache cap. (2) 500 undo/redo steps in 5 steps; RSS flat after the history cap. Limits: (3) a
  200-file corrupt PNG/JPEG corpus in 4 steps: errors, no traps. (4) A 40000 x 40000 image is refused with a
  message, not an OOM kill. **Long-lived:** the editor runs headless across (1) and (2) (pidfile); RSS within
  the tile cache cap of step 2.
- **Depends on.** P2.4a, P1.4, P1.1, P2.1b, P3.5, P3.1; P2.5b not required: a CPU compositor meets the bar
  *(proposal)*.

### R10 Video editor

- **Flagship.** `idcut`, a timeline editor, new tree `idcut`.
  - [ ] MP4/MKV import (demux in id, P2.4c; decode via FFI, D3).
  - [ ] Video and audio tracks; cut, trim, split, move, cross-fade, speed change, text overlay.
  - [ ] Frame-accurate scrubbing with a frame cache; playback in sync with audio; GPU effects (P2.5b).
  - [ ] H.264/H.265 and audio export to MP4 (encode via FFI, D3); project save/reload; proxies for 4K.
- **Perf bar.** Only what id itself does is graded (D3). `bench/id/mp4demux`, `yuv2rgb`, `scale`, `mixdown`
  vs C. (1) demux a 2 GB MP4, build the index; (2) YUV420 to RGBA, 1000 4K frames; (3) bilinear 4K to 1080p,
  1000 frames; (4) mix 16 one-hour tracks at 48 kHz. Hashes compared. End-to-end export of a fixed 60 s
  project is **reported** against `ffmpeg`, not graded *(proposal: it measures the FFI library)*.
- **Blind trial.** "Open an MP4, extract frames 0, 100, 200 as PNGs, write a new MP4 of frames 100 to 199, with
  the media library." 100 tool calls. Hidden script: frame count and first-frame hash via the reference
  decoder.
- **Soak/limits.** Slope: (1) 30 steps of 100 scrub-and-seeks over a 4K one-hour source; frame-cache RSS
  bounded, VA surface count constant. Limits: (2) a 6-hour, 200-clip timeline saves and loads in under 60 s.
  (3) Truncated, corrupt and zero-length media give an error naming the file. (4) Export runs in 10 s
  segments, one per step. **Long-lived:** the editor runs headless across (1) (pidfile); RSS and VA surfaces
  within bound of step 2.
- **Depends on.** P2.4c, P2.5b, P3.5, P1.5, P1.6, P1.4, P3.4. Last by the plan.

### R11 Game engine

- **Flagship.** `idem` (`idem/engine`) shipping one real game from `idem/games` with a threaded frame loop.
  *(proposal)* A small top-down action game with a level editor from `idem/editor`.
  - [ ] `--check` passes for engine, editor and games (P0.4).
  - [ ] Fixed-timestep simulation, rendering and audio on separate actors, joined by channels (P1.5a).
  - [ ] 2D renderer: sprite batching, tilemap, text, particles; GPU path.
  - [ ] Keyboard, mouse, gamepad; rebinding saved to disk. Audio: mixer, positional pan, Ogg streaming (P2.4b).
  - [ ] Asset pipeline with `idem/packer`; hot reload in debug; save/load; deterministic replay from recorded
    input.
  - [ ] 60 fps on the reference machine with 5000 sprites and 1000 entities.
- **Perf bar.** `bench/id/idem_sim` vs `bench/ref/c/sim.c`: entity update, uniform-grid collision and
  sprite-batch build, headless, same seed. (1) 100000 entities, 600 ticks; (2) sprite batch for 100000
  sprites, 600 frames; (3) replay of a 10 minute recorded input. Final state hash compared. Frame rate is
  reported, not graded.
- **Blind trial.** "With idem, a square moves with the arrow keys, collects coins appearing at random
  positions, shows a score; Escape closes. Use the engine's loop and input, no main loop of your own." 100 tool
  calls. Hidden script: headless run on a recorded input; score and frame hash at tick 600 compared.
- **Soak/limits.** Slope: (1) 60 steps of 3600 ticks (headless, faster than real time); RSS flat after step 3;
  frame time at step 60 within 1.25x of step 3. (2) 10000 entity spawn/despawn cycles. Limits: (3) the same
  input gives the same state hash over 20 runs. (4) A missing asset gives an error and a placeholder, no trap.
  **Long-lived:** one headless game process across all 60 steps (pidfile); RSS within 1 MB of step 3.
- **Depends on.** P0.4, P1.5a, P1.5b, P3.5, P2.4b, P2.5a, P1.1, P1.4.

### R12 Monero verifier

- **Flagship.** `idxmr`, a block and transaction verifier syncing the Monero testnet (D4), new tree `idxmr`. It
  verifies; it does not mine, hold keys or send.
  - [ ] Monero P2P with levin framing and handshake, on testnet.
  - [ ] Header and chain checks: RandomX proof of work in **interpreter mode** (D4), difficulty, timestamps,
    checkpoints.
  - [ ] Transaction checks: CLSAG ring signatures, Bulletproofs+, key image uniqueness, outputs, fees.
  - [ ] Keccak-256, Ed25519 field and group ops, Blake2b, AES for RandomX (P2.2a to P2.2c), each with
    published test vectors as cases.
  - [ ] Verified chain in the embedded store (P2.1c); resumable sync from genesis to the current testnet
    height, outputting the verified block count.
- **Perf bar.** Decided (D13): **per-primitive C references taken from the Monero source** (each extracted into
  one C file, `gcc -O2`). No full-`monerod` sync comparison. (1) Keccak-256 of 1 GB in 1 KB messages; (2)
  Ed25519 scalar and group ops, 20000 each; (3) RandomX interpreter, 2000 hashes *(proposal: light mode,
  256 MB cache; no JIT, per D4)*; (4) CLSAG verification of 1000 signatures, ring 16; (5) Bulletproofs+ verification of 1000 two-output range
  proofs *(proposal: size)*, added by D26. Outputs hashed.
- **Blind trial.** "Implement Keccak-256, verify the vectors in `vectors.txt`, then print the Keccak-256 of a
  hex string from stdin. Use idstd's bytes type." 60 tool calls. Hidden vectors: empty input, a block
  boundary, 1 MB. Shipped idstd crypto may be used. A full-verifier trial is out of scope *(proposal: too
  large for one session; this proves discoverability of the crypto layer)*.
- **Soak/limits.** Slope: (1) sync in steps of 500 blocks, each under 60 s, the verified height monotone and
  persisted; 20 steps with no divergence from known testnet block hashes; RSS flat (state is on disk).
  Limits: (2) 10000 fuzzed blocks and transactions in 10 steps, each rejected with a code, none traps. (3) A
  10-block reorg is handled. (4) The constant-time harness (P2.2d) shows no secret-dependent timing variance in
  the Ed25519 and field code beyond its threshold. Long-lived: none; each step is a fresh process resuming
  from the store.
- **Depends on.** P2.2a to P2.2d, P2.3, P2.1c, P1.2, P1.3, P1.1, P1.8.

### R13 CLAP plugin

- **Flagship.** `idsynth`, a monophonic subtractive synthesiser CLAP plugin with a filter and a GUI. Decided
  (D14): **CLAP is required for the A**; VST3 is a later step on the same core, not part of the A.
  - [ ] Freestanding shared object (no libc; P1.6c) exporting `clap_entry`.
  - [ ] Parameters (cutoff, resonance, attack, release, waveform) with automation and host state save/restore.
  - [ ] Audio callback runs id code on the host's real-time thread as the real-time actor kind (D8): no
    allocation, no locking, proven by the compiler. MIDI notes; 8-voice polyphony.
  - [ ] GUI embedded in the host window (P3.1, P3.2); audio and UI actors share state over channels only.
  - [ ] Passes `clap-validator`; loads and plays in a real host (Ardour).
- **Perf bar.** `bench/id/synth_render` vs `bench/ref/c/synth.c` (same voice and filter in C), rendered
  offline: 8 voices, 10 minutes at 48 kHz, 64-frame blocks. Output hashed. Also graded as the real-time claim:
  the median over rounds of the longest block is at most 1.25x the C reference's *(proposal: worst case
  matters more than the mean)*.
- **Blind trial.** "A CLAP gain effect with one parameter `gain`, -60 to +12 dB, passing `clap-validator`." 80
  tool calls. The build is a `.clap` file and every validator test passes.
- **Soak/limits.** Slope: (1) longest-block time over 100 steps of 60 s of offline audio stays under half the
  buffer period at 64 frames and 48 kHz *(proposal: 0.67 ms)*, zero blocks over. (2) 1000 parameter changes per
  step, 10 steps: output finite, no denormal slowdown. Limits: (3) zero audio-thread allocations, by an
  allocation-hook counter in a test build. (4) 100 validator load/unload cycles in 5 steps, no leak.
  Long-lived: none for the plugin; the long-lived host is R14's.
- **Depends on.** P1.5b, P1.6a, P1.6b, P1.6c, P3.1, P3.2, P1.4.

### R14 DAW

- **Flagship.** `iddaw`, a small digital audio workstation, new tree `iddaw`.
  - [ ] Audio and MIDI tracks; clips with trimming, fades, looping; mixer with gain, pan, sends, master bus,
    peak and RMS meters.
  - [ ] Hosts CLAP plugins (R13) on the audio actor and saves their state in the project.
  - [ ] MIDI recording and piano-roll editing; ALSA and JACK backends (P2.5a); records from an input device;
    plays at 64-frame buffers without dropout on the reference machine.
  - [ ] Imports WAV, FLAC, Ogg; exports WAV and FLAC (P2.4b). Project save/load; undo/redo; autosave.
- **Perf bar.** `bench/id/mixdown` vs `bench/ref/c/mixdown.c`: offline render of a fixed 64-track project (gain,
  pan, a biquad per track, a send reverb) for 10 minutes at 48 kHz, plus the same with 8 instances of the R13
  plugin. Output hashed; worst block time compared as in R13.
- **Blind trial.** "With idstd's audio and MIDI modules, render a MIDI file to a 44.1 kHz WAV with a sine voice
  per note." 80 tool calls. Hidden script: WAV length and the RMS of three windows at tolerance 0 *(proposal:
  the sine comes from a table of the documented size, so it is exactly reproducible)*.
- **Soak/limits.** Slope: (1) 64 tracks for 100 steps of 60 s of audio (offline); zero dropouts, longest block
  under half the period. (2) 500 edits and undos in 5 steps; RSS flat. Limit: (3) a crashing or hanging plugin
  is isolated by its watchdog and the project continues. **Long-lived:** the DAW runs headless across (1) and
  (2) (pidfile); RSS and descriptors within 1 MB of step 2.
- **Live gate (D18).** The A also includes **one recorded manual live-audio gate**: a person plays a fixed
  project through the real ALSA device for 10 minutes (D24) on the reference machine and reads the
  xrun count from ALSA. Pass is 0 xruns; the record carries the count, N and the machine. It is the only
  clock-bound, non-automated check; every other check stays in steps of 60 s or less. A change to the audio
  path makes the record stale.
- **Depends on.** R13, P2.4b, P2.5a, P3.4, P3.5, P1.5.

## 5. Common failures that do not count toward an A

*(proposal)*

* `--allow-untested`, an exemption added to meet a row, or a case that proves nothing (silent, echo, bare,
  count, or constant-then, per `STATUS.md`, "Shape") does not count toward "its cases pass".
* A benchmark whose C reference was written to be slow (unoptimised structure, no `-O2`) is a bug in the
  reference; the review in section 6 includes a read of it.
* A perf bar met only with `--target c` flags the default build does not use; a perf record from a loaded
  machine (D17); output hashes compared on a program that prints nothing (each benchmark's output includes a
  checksum of the work done); a soak that fits 60 s only because it does less work.

## 6. Recording and re-checking a grade (X.2)

**Where.** Decided (D19): grades live in **a section of `docs/STATUS.md`**, generated by `statusgen` from
`grades/*.tsv`. There is no separate `GRADES.md`. Per `docs/README.md`, a changing number is never written by
hand in a doc; the plan points to that section.

**A record (one line per check, appended to `grades/RN.tsv`).**

| field | content |
| --- | --- |
| row | `R1` to `R14` |
| part | `flagship`, `perf:BENCH`, `trial:k`, `soak:STEP`, `live` (R14 only) |
| result | `pass`, `fail`, `advisory` |
| value | ratio, tool calls used, slope, xrun count or count, as the part defines |
| commit | git revision of the tree checked |
| tool versions | `gcc --version`, `idc` build hash, `clang` for LLVM rows |
| machine | the harness `meta.txt`: CPU, core pinned, load |
| date, log | day of the run; path of the saved output, so the grade can be inspected |

**Computing the letter.** `statusgen` takes, per row, the latest record per part. A part passes only if its
latest record is `pass`; any `fail` or `advisory` (a loaded-machine run, D17) makes it not passing. The trial
part passes with 2 of the latest 3 `trial:k` records (D20). The letter follows section 1. A record older than
the row's last change to a depended-on plan item is **stale**, not a pass.

**Re-checking** (X.2: after each phase, re-run the assessment) *(proposal)*:

1. After a phase completes, re-run every row whose "Depends on" gained a `done` id.
2. A row whose compiler, idstd or runtime inputs changed is re-run in steps of 60 s; the harness reports
   `K left` until all steps are recorded, as `mutscore` does.
3. An `advisory` perf record is re-run on a quiet machine, never accepted.
4. The blind trial (3 sessions) is re-run when the docs, diagnostics or idstd's public names change in the
   brief's area, otherwise at most once per phase. Transcripts are kept; findings go to X.1.
5. Weekly, all cached checks re-run on the schedule the project uses for cases (alignment 2026-10-09). A row
   whose grade drops is reported at once. The manual live-audio gate is not in this run; a person re-records
   it after an audio-path change.

**Regression.** A row at A that fails any part on a re-check is shown as A-with-a-red-part until fixed; it is
neither silently downgraded nor silently kept *(proposal: so a flaky check is visible)*.

**Review.** Before a row is first marked A, the user (or a reviewer who did not write the flagship) reads the C
references, benchmark inputs, trial brief and hidden script, and soak step definitions. The rubric cannot
detect a reference written to be slow or a brief written to be easy; this is that check.

**Linux only.** A record is a Linux record; the platform pass (X.3) adds records with a `platform` field and
does not change the Linux grade.

## 7. Decisions

* D11: soak is an in-step slope on every row plus a long-lived process (by pidfile) where one can stay up.
* D12: R5 runs in a disposable nix-built QEMU VM; real `insmod`/`rmmod`, no mock.
* D13: R12 perf is per-primitive C references from Monero; no `monerod` sync.
* D14: R13 requires CLAP for the A; VST3 is a later step, not part of the A.
* D15: R6 has both bars: wasm compute vs C-to-wasm, and headless-browser UI vs JS.
* D16: R7's UI-latency reference is a C widget on the same rasteriser.
* D17: only a quiet-machine perf run can grant an A; loaded runs are advisory.
* D18: R14's A includes one recorded manual live-audio gate; all else is automated.
* D19: grades live in a `docs/STATUS.md` section generated by `statusgen`.
* D20: the blind trial passes with 2 of 3 sessions.
* D24: R14's live gate runs for 10 minutes.
* D25: R5, R6, R9 and R10 also run a long-lived process across soak steps.
* D26: R12 adds Bulletproofs+ verification as a fifth perf reference.
