# `asm` functions

Some things cannot be written in a language — reading a timestamp counter,
issuing a memory barrier, a system call. `id` gets to them through a function
whose body is instructions rather than statements, and which is declared for
one specific platform.

## Form

```
asm "x86_64-unknown-linux-gnu" cpu_ticks() {
  "rdtsc"
  "shl $32, %%rdx"
  "or %%rdx, %%rax"
  "mov %%rax, %[ret]"
} return word ret;
```

* the `asm` keyword introduces the declaration;
* the string literal after it is the **platform triple** the body is written
  for;
* the signature, and the post-brace `return` clause, are ordinary `id`;
* the body is a sequence of **string literals**, one instruction per line, in
  place of statements.

Operands are referred to by name: `%[a]` for a parameter called `a`, and
`%[ret]` for the value the `return` clause names. A literal `%` — a register
name, say — is written `%%`, as it is in C, because a single `%` introduces an
operand reference. Nothing else is in scope —
an `asm` body cannot call functions, read imports or declare variables, which
is the point: it is a leaf.

## Overloading by platform

The same function may be declared once per platform:

```
asm "x86_64-unknown-linux-gnu" cpu_ticks() {
  "rdtsc"
  "shl $32, %%rdx"
  "or %%rdx, %%rax"
  "mov %%rax, %[ret]"
} return word ret;

asm "aarch64-unknown-linux-gnu" cpu_ticks() {
  "mrs %[ret], cntvct_el0"
} return word ret;
```

This is the **only** place `id` allows two functions to share a name, and they
are distinguished by a literal — the triple — which is exactly what the
function-uniqueness rule already counts as a real difference.

The compiler is told its target with `--triple`, defaulting to the host. It
selects the body whose triple matches exactly. Signatures must agree across
overloads; a mismatch is an error.

## An unsupported platform is a compile error

Building for a target with no matching body fails, naming what was available:

```
prog.id:12: error: no 'asm' definition of 'cpu_ticks' for target
'riscv64-unknown-linux-gnu'; defined for: x86_64-unknown-linux-gnu,
aarch64-unknown-linux-gnu
```

This is deliberate and is the whole reason the triple is part of the
declaration. The alternative — silently compiling a stub, or falling back to a
generic implementation — produces a program that builds everywhere and is
wrong somewhere, which is the failure mode inline assembly is most known for.

A portable path is still available and stays explicit: write an ordinary `id`
function with a different name and choose between them at the call site.

## What the backends do with it

`asm` is a target question, so it goes through `tgt_asm` like everything else
(`BACKENDS.md`).

* **C** — GCC extended asm: the instruction lines joined with `\n\t`, the
  `return` name as an output operand, parameters as inputs, and — for now —
  `volatile` with a `"memory"` clobber on every block. That is conservative
  and costs optimisation, but the alternative is asking authors to write
  clobber lists correctly, and a wrong clobber list is a miscompile that
  appears under `-O2` six months later.
* **An interpreted target** (Python) — has no way to execute instructions, so
  no triple will match and the error above fires. That is the correct
  behaviour, not a gap.
* **LLVM IR** — maps onto `call asm sideeffect`, whose operand syntax is close
  enough to the C form to share the constraint construction.

## Deliberately not included

* **Clobber lists.** Every block is treated as clobbering memory. Revisit only
  with a way to verify the declaration.
* **A `"*"` wildcard triple.** It would defeat the point: the error above is
  the feature.
* **Constraint letters.** Operands are register-allocated (`"=r"` / `"r"`).
  Memory and immediate constraints can be added when something needs them,
  and should be added as syntax rather than by letting raw constraint strings
  through.
