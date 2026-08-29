# Where this project is not written in `id`

> **Status: a survey with estimates.** The counts are measured. The costs are
> estimates, and each one says what it is anchored to — an existing piece of
> this repository of comparable size — rather than being a number with nothing
> behind it.

**66.1% of source lines here are `id`**: 28 962 lines across 1 489 files,
against 14 832 lines of everything else. This document is the other 34%: what
it is, why it is there, and what moving it would cost.

| what | lines | why it is not `id` | cost to move |
| --- | ---: | --- | --- |
| `idc.py` | 5 470 | ~~the bootstrap compiler~~ (that job is retired: `bootstrap/`) — now the reference implementation, the WASM target and the test runner | **medium**, and now unblocking rather than blocking |
| shell (`bin/idc`, `tests/`, `tools/`) | 6 203 | no way to run a process from `id` | **large**, and blocked on one builtin |
| the C runtime prelude | 433 | hosted programs need libc | **medium**, and an `id` twin already exists |
| `tools/*.py` (not `idc.py`) | 1 286 | sockets, ZIP, binary packing | **medium**, mixed |
| `backends/*.c` + `*.h` | 1 380 | this is the FFI boundary, by design | **should not move** |
| `kernel/boot/*.S` | 234 | code that runs before a calling convention exists | **mostly irreducible** |
| `editors/vscode-id/extension.js` | 259 | VS Code's extension host runs JavaScript | **medium**, and a shim survives |
| `flake.nix`, `.envrc` | 52 | declaring an environment is not programming | **not a reliance** |
| `backend.json` ×3, etc. | 293 | data | **small**, and low value |

---

## 1. `idc.py` — 5 470 lines of Python

**What it is.** The original compiler. It was the bootstrap until
`bootstrap/*.c` took that job; what is left is the reference implementation
that every differential suite builds against, the only implementation of
`--target wasm`, and the only thing that *runs* a `docs/TESTS.md` case.

**Why.** History, and a chicken-and-egg that is now cooked: a self-hosted
compiler needs a compiler to exist first — but only once, and the answer to
"which one" is now "the previous one, as C".

**Cost to move.** Two separable pieces.

*Retiring the bootstrap* is **done.** `bootstrap/idlex.c` and
`bootstrap/idparse.c` are the C those two stages emit about themselves, and
`bin/idc` builds stage 0 out of them with `cc`, then rebuilds both stages from
the working tree through it. Verified by `tests/self_host_build.sh`, which runs
a cold-cache build against a root whose `idc.py` is a directory: **this driver
no longer executes `idc.py` at all.** See `bootstrap/README.md`.

That was the piece worth doing first, for a reason beyond tidiness: **every
additive language feature was blocked on it.** `break`, `clear`, structs, a
binary literal — none of them could be used in `compiler/` while a frozen
`idc.py` had to compile that tree. The frozen thing is now a snapshot, and
`tools/regen_bootstrap.sh` moves it forward in one command, so a new construct
costs two commits (teach it, regenerate; then use it) instead of being
impossible.

What still holds `idc.py` here is `--target wasm`, the differential suites
(`tools/parity.sh`, `tests/invalid.sh`, `tests/self_host_build.sh` and the rest
build with both compilers on purpose), `--tests` — only `idc.py` *runs* a test
case — and §4's `tools/gen_runtime_id.py`, which does `import idc` and is the
one place `idc.py` is a Python library rather than a subprocess.

*Porting the WASM target* is **medium**: the LLVM target is 28 files of `id`,
and WASM is a comparable job. Anchor: `compiler/parse/back/tgt/ll/`.

## 2. Shell — 6 203 lines, and the single biggest lever

**What it is.** `bin/idc` (890 lines) is the driver: it walks a project tree,
enforces the three-entries-per-directory rule, reads `conf.id`, injects `#file`
markers, pipes source through `idlex | idparse`, and invokes `cc`, `clang`,
`llc` or `ld.lld`. The other 5 313 lines are `tests/*.sh` and `tools/*.sh`.

**Why.** One reason, and it is not a small one: **`id` cannot run a process.**
There is no `exec`, no `spawn`, no `system`. A compiler driver that cannot
invoke `cc` cannot be written in `id` at all, and neither can a test runner
that compares two compilers' output.

Secondary reasons: no directory listing (the `fs` backend does `open`, `read`,
`write`, `close`, `size`, `exists`, `remove` — and no `readdir`), and no
environment access.

**Cost to move.** **Large in volume, but gated on one small thing.** Add a
`spawn(argv, stdin) -> (status, stdout)` builtin and a `readdir`, and every one
of these scripts becomes an ordinary `id` program. Without them, none of them
can be. The volume is real — 6 200 lines is twice the editor — but it is
mechanical, and `tests/*.sh` is the least interesting code in the repository.

The honest ordering: **the builtin is the work; the port is typing.** And the
driver should go first, because a driver written in `id` is the strongest
possible argument the language can make for itself.

## 3. The C runtime prelude — 433 lines, and an `id` twin that already exists

**What it is.** 63 helpers emitted verbatim at the top of every generated C
file: the allocation arena, growable lists, the flat store with its bounds
checks, defined division and shifts, string building, and terminal I/O. It
lives as one string in `idc.py` and is regenerated into
`compiler/parse/back/tgt/c/runtime/runtime.id` by `tools/gen_runtime_id.py`,
so both compilers emit the same bytes.

**Why.** Two different reasons that are easy to conflate:

* The **C target emits C**, so it needs a C prelude. That is not a reliance to
  remove; it is what the target *is*. It disappears only if the C target does.
* **Hosted programs need an operating system.** The prelude calls exactly
  thirteen libc functions: `malloc`, `realloc`, `free`, `strlen`, `memcpy`,
  `fprintf`, `snprintf`, `fgets`, `fflush`, `read`, `write`, `exit`,
  `clock_gettime`.

**Cost to move: medium, and most of it is done.** `runtime/` — 46 files, about
100 functions, 21 of them `asm` blocks — already implements the same
primitives in `id` with no libc at all. That is what the kernel runs on:
`list_push`, `list_get`, `concat`, `charat`, `str_of_int`, `peek8`/`poke64`,
`sdiv`, `shl`, `mem_alloc`, all of it in `id`.

So the question is not "can this be written in `id`" — it is written, and it
boots. What is missing hosted-side is the syscall layer: `read`, `write`,
`exit`, `mmap` (for an arena that can grow) and `clock_gettime`, which on Linux
are five `asm` blocks of about four instructions each. Terminal raw mode
(`termios`) is an `ioctl` and is the fiddliest.

Estimate: **one file of syscalls plus wiring the LLVM target to link
`runtime/` instead of the C prelude.** The pieces exist; nobody has connected
them, because the C target was the only target when the prelude was written.

## 4. `tools/*.py` — 1 286 lines, mixed

| tool | lines | what blocks it |
| --- | ---: | --- |
| `flatten.py` | 565 | nothing — it is a one-off migration tool and should be deleted, not ported |
| `lint_idcpy.py` | 150 | nothing — it dies with `idc.py` |
| `qmon.py` | 142 | **sockets**. It drives QEMU over QMP, a JSON protocol on a TCP socket |
| `gen_runtime_id.py` | 121 | nothing — it dies with the C prelude |
| `mkfont.py` | 90 | file I/O only; portable today via the `fs` backend |
| `fbtext.py` | 86 | file I/O only; portable today |
| `mkodt.py` | 82 | ZIP writing, which the editor already does in `id` |
| `mkkeymap.py` | 50 | file I/O only; portable today |

**Cost.** Three of these (308 lines) evaporate when `idc.py` and the C prelude
go. Four more (308 lines) are portable **today** with no new language feature —
`mkfont`, `fbtext`, `mkkeymap`, `mkodt` are byte-shuffling programs and the
editor proves `id` does that well. Only `qmon.py` is genuinely blocked, on a
socket builtin.

Anchor: `editor/lib/zip/` is 28 files of `id` that inflate DEFLATE and read a
ZIP central directory. `mkodt.py` is easier than that.

## 5. `backends/` — 1 380 lines of C, and the one place to leave alone

**What it is.** Three native backends: `gfx` (X11 window and framebuffer),
`gl` (OpenGL), `fs` (POSIX file I/O). Each is a `.h` declaring the ABI, a `.c`
implementing it, and a `backend.json` stating the contract in `id`'s own types.

**Why.** This is the FFI boundary and it is **deliberate**. `docs/SPEC.md` §10
lists "anything reached through a native backend" as unspecified precisely
because it is platform-specific by definition. Moving X11 into `id` would mean
`id` speaking the X11 wire protocol, or calling C functions directly — and
either way the *headers* are still C.

**Cost.** For `gfx` and `gl`: **should not move.** The abstraction is right;
the language should reach the platform through a declared contract rather than
by absorbing it.

For `fs_posix.c` (138 lines): **genuinely movable.** It is eight functions over
`open`/`read`/`write`/`close`/`stat`/`unlink` — six Linux syscalls, which the
kernel already makes from `id` with `asm`. Worth doing as the proof that a
backend *can* be `id` when the platform interface is a syscall rather than a
library. Estimate: one day, and it removes the C compiler from the dependency
list for file I/O.

## 6. `kernel/boot/*.S` — 234 lines, mostly irreducible

**What it is.** `boot.S` (143 lines): the PVH ELF note, the 32-bit entry, the
GDT, four levels of page tables, the long-mode transition, the stack. `isr.S`
(91 lines): 32 interrupt stubs that push a vector number and jump to a common
handler.

**Why.** This is code that runs **before a calling convention exists**. There
is no stack, no `id` function can have been entered, and much of it is not
instructions at all — the GDT and the page tables are *data at fixed
addresses*, and the ELF note has to land in a specific section.

**Cost.**

* `boot.S`: **irreducible** in any honest sense. `id`'s `asm` blocks are
  function bodies with a return value; they cannot place a symbol in a named
  section, emit a table of bytes at an alignment, or run before a stack exists.
* `isr.S`: **partly movable.** The 32 stubs are the same three instructions
  with one immediate changed — exactly what a binary literal
  (`docs/FRICTION.md` §7) plus an `asm` block could generate. Saves perhaps
  60 of the 91 lines, and is worth doing mostly because it would prove the
  binary literal's worth.

## 7. `editors/vscode-id/extension.js` — 259 lines

**Why.** VS Code loads extensions into a JavaScript host. There is no
arrangement under which that file is not JavaScript.

**Cost. Medium, and a shim survives.** The real move is to make the extension a
thin client of a **language server** written in `id` — LSP is JSON over stdin
and stdout, and `id` has `read_all` and `print`. The parser, the diagnostics
and the structural rules are all already in `compiler/parse/mid/` and are
exactly what a language server reports. Estimate comparable to the editor's
XML layer: 40–50 files. The `.js` shrinks to perhaps 40 lines that launch the
server.

This is the highest-value item in the table that is not on the critical path:
it would make the language's own rules visible while typing, which is where
`docs/FRICTION.md` §11 (name collisions found only at compile time) actually
hurts.

## 8. What is not a reliance

* **`flake.nix`, `.envrc`** — declaring a toolchain is not programming, and Nix
  is the right language for it.
* **Markdown** — 9 044 lines of documentation.
* **JSON** — `backend.json` is data. It *could* be a `conf.id`, which would be
  a small, tidy win and would let the compiler read a backend's ABI with its
  own parser instead of a shell `awk` — but nothing is blocked on it.
* **LLVM IR, WAT, C output** — emitted, never written.

## The order that matters

1. ~~**Retire the bootstrap.**~~ Done: `bootstrap/*.c` is stage 0 and `bin/idc`
   never runs `idc.py`. This was the gate on every additive language feature,
   and it is open. What is left of `idc.py` — `--target wasm`, the differential
   suites, `--tests` — blocks nothing; it only keeps a second implementation
   alive, which is worth something until the first one has a written spec it
   cannot drift from.
2. **Add `spawn` and `readdir`.** Two builtins that convert 6 200 lines of
   shell from impossible to merely tedious, starting with `bin/idc`.
3. **Wire the LLVM target to `runtime/` and add the syscall file.** The
   hosted C prelude then becomes the C target's business alone.
4. **Move `fs_posix.c` into `id`.** Small, and it proves a backend need not be
   C when the platform speaks syscalls.
5. **An `id` language server.** Not on the critical path, and the best
   remaining argument the language could make for itself.

Everything after that is X11, OpenGL, a boot stub and a VS Code shim — which
is a reasonable place for a systems language to stop.
