# The kernel, and the runtime under it

> **Status: it boots.** `idc/tools/kbuild` (in `id`) builds it and QEMU runs it; the
> serial output below is copied from a run. "What is not there yet" is the
> honest list.

```sh
idc/tools/devshell.sh 'idc/bin/idc idc/tools/kbuild -o /tmp/kbuild && /tmp/kbuild idc'
qemu-system-x86_64 -kernel idc/build/kernel.elf -serial stdio -display none -no-reboot
```

```
id kernel: booted
hello from a language with no libc
...                                       (the language demonstrations)
fb: 640x480 at 0x00000000fd000000
id shell -- an in-memory filesystem, and no libc under it
type help for the commands
/ $ ls
README
bin/
doc/
/ $ cd bin
/bin $ cat hello
echo hello from a kernel with no operating system under it
/bin $ uname
id kernel -- x86_64, no libc, no operating system under it
/ $ fault
fault: reading 0x140000000, which has no page behind it

*** fault: page fault (vector 14, error 0)
*** at 0x0000000000100280
*** halted
```

That is a *graphical* shell: the same text is on a 640x480 framebuffer, drawn
glyph by glyph from an 8x16 font, and `idc/tools/fbtext` reads it back off the
screen by matching each cell against that same font. `idc/tools/qmon` is what
gets both out of QEMU in the first place -- it boots the kernel, types at its
serial port, and asks QMP for a screenshot -- and `idc/tests/kernel.sh` asserts
on both -- a console that wrote to the serial port and drew nothing would pass
every other check and fail that one.

The shell reads the PS/2 keyboard and the serial port through one function, so
a person types at it and a test types at it the same way.

Everything after the first two lines is ordinary `id` that says nothing about
where it runs -- so `idc/tests/kernel.sh` builds the same source hosted, on the C
runtime, and requires the two to print the same thing line for line. That is
the check that says the `id`-written runtime is *right* rather than merely
present: a wrong `str_of_int` produces a kernel that boots and lies.

It has already earned itself twice. It found that the demonstration was
shifting by a negative count, which the C runtime traps on and a kernel cannot;
and it found `docs/SPEC.md` §10's S11 -- that the two targets disagree about
the order the operands of one operator are evaluated in, so an expression that
pops a list and measures it at once prints a different length on each.

## Why a kernel

Not because `id` needs an operating system. Because a compiler that emits calls
into a C runtime has not proved anything about the language it compiles — the
hard parts are still being done by someone else's code, and every claim about
what `id` can reach is really a claim about what libc can reach.

A kernel removes that. It runs with no operating system beneath it, no C
library beside it, and no runtime it did not compile from `id` source. If a
string can be concatenated there, `id` can concatenate a string. If it cannot,
the gap was always there and libc was hiding it.

That is the whole argument, and it is why this lives in the repository rather
than in a demo.

## What is actually in the binary

| piece | written in | why |
| --- | --- | --- |
| `kernel/prog/` | `id` | the kernel |
| `idc/runtime/` | `id`, over a handful of `asm` functions | strings, lists, the arena, arithmetic, serial output |
| `kernel/boot/boot.S` | assembly | the boot protocol: a stack, paging, long mode |
| `kernel/boot/kernel.ld` | a linker script | where the pieces land |

`clang` appears twice in `idc/tools/kbuild` — once assembling `boot.S`, once
compiling the emitted LLVM IR — and never as a C compiler. `ld.lld` links.
Nothing else runs, and no object in the image came from C source.

### The floor

`idc/runtime/` is ordinary `id` down to a small number of `asm` functions, and
those are one instruction each. They exist because below them there is no `id`
left to write:

* `ld8` / `st8` / `ld64` / `st64` — a load and a store at an address. The
  language has `peek8` and `poke8`, but those *are* what the runtime is
  implementing, so it cannot use them.
* `s2w` / `w2s` — an address as a number and back. `id` has no cast, and giving
  it one to serve a runtime detail would be a language change.
* `com1_out` — a byte to a port. A port is not memory; `out` is the only way
  there.
* the division and shift instructions, which `id` spells with operators that
  compile to calls into this same runtime.

Every one is emitted **`noinline`**, and that is load-bearing rather than a
hint: an `asm` block clobbers whatever registers its instructions name and `id`
has no syntax for saying so. Out of line, a clobbered register is a
caller-saved one the ABI already lets a call destroy. Inlined, it would be a
register the caller had something live in. The rule the bodies follow is the
matching one: **read every operand before writing any fixed register**, because
the allocator may have put an operand in the register about to be overwritten.

## How a build differs from a hosted one

Two flags, and nothing else:

* **`--freestanding`** — no C-ABI `main` wrapper. The boot stub jumps straight
  to `id_main`; a wrapper marshalling an `argv` nobody passed would be a symbol
  named `main` in a program with no C library to call it. The result is always
  an object file, compiled `-ffreestanding -fno-builtin -mno-red-zone` for the
  `x86_64-unknown-none` triple.
* **`--runtime`** — this project *is* the runtime. It may define a function
  named after a runtime helper (that is the point of it), and its module emits
  no `declare` block, because a declaration beside a definition of one symbol
  is not something LLVM accepts.

The kernel has a library under it: idstd's `core/` tier, the part of the
standard library that is pure `id` and freestanding. `idc/tools/kbuild` stages
`idc/build/std_core/`, a copy of `$IDSTD_HOME/core` (else the `idstd` beside the
checkout) with a `conf.id` of just the constants that tier reads, and builds
`kernel/prog` with `--std idc/build/std_core`. The runtime is built `--no-std`:
it is what the library stands on. Uniqueness is whole-program, so the kernel may
not define a function core has (`lset`, `sset` and `wset` were such copies and
are gone), and a freestanding program that reaches `fail` links the runtime's
`id_fail`. An `IDC_NO_STD=1` in the environment overrides `--std`, so unset it
to run `kbuild` (`idc/tests/kernel.sh` does).

Test cases are the one place a freestanding build touches the host. They run
there, in a harness built from the same source for the machine doing the build,
and the object is built only if every one passes (`docs/TESTS.md`, "A
freestanding build runs its cases on the build host"). A function that reaches
something with no host implementation cannot run there: an `asm` function with
no body for the host's triple (`in8`, `lidt_load`, `cpu_halt`), a native, or,
in `--runtime`, a function named after a runtime helper. Such a function is
exempt from the two-case minimum, with a note naming what it reaches, and a case
under it is an error. What it does is checked by `idc/tests/kernel.sh`, which
boots the image. The kernel and the runtime still build with `--allow-untested`
until their other functions have their cases.

String comparison is the one lowering that differs: hosted it calls `strcmp`
and gets libc's, freestanding it calls `id_strcmp` and gets the runtime's. A
freestanding module links nothing unprefixed.

## Booting

QEMU's `-kernel` takes a 64-bit ELF through the **PVH** boot protocol, declared
by an ELF note naming a 32-bit entry point. Its Multiboot support is Multiboot
1 and ELF32 only, which a kernel holding 64-bit code cannot be — so PVH is what
the note declares, and a Multiboot 2 header sits beside it so a real bootloader
can load the same image.

Entry is 32-bit protected mode with paging off. `boot.S` walks the usual road:
a stack, an identity map of the first gigabyte with 2 MiB pages, PAE, long mode
in `EFER`, paging on, a GDT with a 64-bit code segment, a far jump into it, and
`call id_main`. Above the image, `heap_base` is where the arena starts and
`heap_limit` is where the identity map stops.

## Where this departs from the specification

`docs/SPEC.md` describes a hosted program. Four of its promises cannot be kept
here, and each is a deliberate deviation rather than an oversight:

* **A trap has nowhere to go.** §7 says a trap writes one line to stderr and
  exits 1. A kernel has neither. Division by zero is a `#DE` fault, which the
  kernel's IDT (`kernel/prog/sys/trap/idt/`, installed by `idt_init` at boot)
  sends to a panic path (`kernel/prog/sys/trap/panic/`): one line naming the
  vector, the error code and the faulting address on the serial port, then the
  machine stops. That is a trap, spelled for a machine with no stderr.
* **Only lists are given back.** §6 says the arena is released at process exit.
  There is no process, so a list the compiler proves unreachable goes onto a
  free list in the runtime (`runtime/mem/store/arena/more/pool.id`) and is
  reused, and a list that grows hands its old cells back. Strings and `alloc`
  are handed out and never returned, and the identity map is the ceiling. There
  is no stderr to trap to either, so the hosted runtime's use-after-free guard
  does not exist here (docs/MEMORY.md 2a).
* **`fail` has no stderr or exit.** `fail(msg)` writes `id: MSG` to stderr
  and exits 1 hosted. The runtime's `fail` (`idc/runtime/io/fail.id`) writes
  the same line to the serial port with `put` and `print`, which allocate
  nothing, then writes ACPI's shutdown register (port 0x604, what the panic
  path's `poweroff` writes) and spins on `hlt`, so it never returns.
* **Floats are absent.** `id_box_f`, `id_unbox_f` and float printing are not
  implemented, so a kernel that uses a `float` fails to link. Enabling SSE is a
  handful of `CR0`/`CR4` bits and belongs with the rest of CPU setup, not with
  the runtime.

## What is not there yet

This is a kernel in the sense that nothing is under it, not in the sense that
it does anything an operating system does. In rough order of what unblocks the
most:

1. **Faults that can be handled.** The IDT and the panic path report a fault
   and stop the machine; nothing yet turns one into an event the kernel
   recovers from (a page fault answered by mapping the page, say), which is
   what `docs/SPEC.md` §7's traps become once something can catch them.
2. **A physical frame allocator** over the memory map the boot protocol hands
   over, instead of a bump pointer over whatever is above the image.
3. **Paging the kernel actually manages**, rather than the identity map the
   boot stub builds once.
4. **A timer and a scheduler**, which is where "microkernel" starts meaning
   something.
5. **User mode and a syscall boundary**, which is where it starts being one.
