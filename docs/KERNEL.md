# The kernel, and the runtime under it

> **Status: it boots.** `tools/kbuild.sh` builds it and QEMU runs it; the
> serial output below is copied from a run. "What is not there yet" is the
> honest list.

```sh
tools/devshell.sh 'tools/kbuild.sh'
qemu-system-x86_64 -kernel build/kernel.elf -serial stdio -display none -no-reboot
```

```
id kernel: booted
hello from a language with no libc
arith: sum=12 diff=2 prod=35
div: 9 2 -9 -2
udiv: 6148914691236517205 umod=0 ult=0
word: -9223372036854775808 9223372036854775807 -1
shift: 1024 -4 0 15
shift: -1 0 1 0
str: n=42 len=4 chr=A
str: at=110 int=-123 mem=n=4
cmp: 101
list: len=6 [0]=10 [1]=99 [5]=60
list: pop=60 len=5
store: 64=1234605616436508552 32=287454020
store: 16=51966 8=90
```

Everything after the first two lines is ordinary `id` that says nothing about
where it runs -- so `tests/kernel.sh` builds the same source hosted, on the C
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
| `runtime/` | `id`, over a handful of `asm` functions | strings, lists, the arena, arithmetic, serial output |
| `kernel/boot/boot.S` | assembly | the boot protocol: a stack, paging, long mode |
| `kernel/boot/kernel.ld` | a linker script | where the pieces land |

`clang` appears twice in `tools/kbuild.sh` — once assembling `boot.S`, once
compiling the emitted LLVM IR — and never as a C compiler. `ld.lld` links.
Nothing else runs, and no object in the image came from C source.

### The floor

`runtime/` is ordinary `id` down to a small number of `asm` functions, and
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

`docs/SPEC.md` describes a hosted program. Three of its promises cannot be kept
here, and each is a deliberate deviation rather than an oversight:

* **A trap has nowhere to go.** §7 says a trap writes one line to stderr and
  exits 1. A kernel has neither. Division by zero is a `#DE` fault, which
  without an IDT is a triple fault and a reset — which is a trap, just a louder
  one. An IDT and a real panic path is the first thing to build next.
* **There is no `free`, and now it is visible.** §6 already says the arena is
  released only at process exit. There is no process. Memory is handed out and
  never returned, and the identity map is the ceiling.
* **Floats are absent.** `id_box_f`, `id_unbox_f` and float printing are not
  implemented, so a kernel that uses a `float` fails to link. Enabling SSE is a
  handful of `CR0`/`CR4` bits and belongs with the rest of CPU setup, not with
  the runtime.

## What is not there yet

This is a kernel in the sense that nothing is under it, not in the sense that
it does anything an operating system does. In rough order of what unblocks the
most:

1. **An IDT and a panic path**, so a fault says what happened instead of
   resetting the machine. This is also what turns `docs/SPEC.md` §7's traps
   back on.
2. **A physical frame allocator** over the memory map the boot protocol hands
   over, instead of a bump pointer over whatever is above the image.
3. **Paging the kernel actually manages**, rather than the identity map the
   boot stub builds once.
4. **A timer and a scheduler**, which is where "microkernel" starts meaning
   something.
5. **User mode and a syscall boundary**, which is where it starts being one.
