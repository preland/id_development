# What an `id` program means

> **Status: normative, and executable.** Every claim here is a case under
> `tests/conform/`, run on every target by `tests/conform.sh`. §10 records
> where the targets do not meet it yet.

This document says what `id` code *does*, independently of how it is compiled.
Everything here is a promise every code-generation target must keep.

## Why it exists

Until now the answer to "what does this program do" was "whatever the C the
compiler emitted does". That was workable while there was one target. There is
not: `idc.py` has emitted LLVM IR and WebAssembly since `f229d52`, and the
three have **already drifted**. A shift wider than the type gives three
different answers today — the C target defines it through a runtime helper,
the LLVM target emits a raw instruction whose result is poison, and the WASM
target masks the shift count. Nothing reports this, because nothing was
looking.

Nothing *could* have been looking. `tools/parity.sh`, which has caught almost
every bug in this compiler, compares the **text** two compilers emit. That is
only a question that exists while both of them emit C, and it says nothing
about a target that emits something else. It stays exactly as useful as it has
always been for the two C-emitting compilers, and it is structurally incapable
of growing into the cross-target gate.

`tests/conform.sh` is that gate: it builds each case in `tests/conform/` every
way the toolchain allows, runs it, and requires the same stdout, exit code and
stderr from each. This document is what those cases are checking, written down
so that a disagreement has a right answer instead of a majority vote.

**The C target is the reference.** Where this document merely records existing
behaviour it says so; where it *chooses*, it says that too, and names what has
to change.

---

## 1. Types

Five scalar types and one type constructor. `T[]` is a list of `T`, and nests.

| type | width | representation |
| --- | ---: | --- |
| `int` | 32 | two's complement, signed |
| `word` | 64 | two's complement; the type of an address in the flat store |
| `float` | 64 | IEEE-754 binary64 |
| `string` | — | an immutable sequence of bytes |
| `void` | 0 | no value |

A list is a heap-allocated growable sequence with **reference semantics**:
passing one to a function and mutating it is visible to the caller. This is
how `id` gets shared mutable state, and it is the one place in the language
where assignment does not copy.

Width is a promise, not an implementation note: `int` is 32 bits on every
target, including targets whose natural word is wider.

## 2. Integer arithmetic

### 2.0 How an integer is written

Three spellings, all producing the same kind of value — the base is a way of
writing a number, not a property the number keeps:

```
255      decimal
0xff     hexadecimal, 0x or 0X
0b1010   binary, 0b or 0B    (== 10)
```

A literal too large for `int` is a `word`. There is no digit separator, no
octal, and no exponent form for integers (`float` has none either — see §3).

### 2.1 Overflow wraps

`int` and `word` arithmetic that exceeds the type's range **wraps**, modulo
2³² and 2⁶⁴ respectively.

```
2147483647 + 1   ==  -2147483648
100000 * 100000  ==   1410065408
```

This is a **choice**, and it is deliberately stronger than C, where signed
overflow is undefined. Today's C target gets the specified answer only because
gcc happens to wrap; an optimiser is entitled to assume overflow cannot happen
and produce something else. Making this true rather than lucky needs `-fwrapv`
on the C target, or arithmetic routed through unsigned. **The C target does not
do this yet** — see §10.

Wrapping was chosen over trapping because `id` compiles to code that runs at C
speed and a check on every arithmetic operation is the one cost that would
change that; and over promotion (Python's answer) because a language with a
flat store and a 64-bit machine word has already committed to fixed-width
integers. If a trapping or arbitrary-precision integer is wanted later, it
belongs as a *different type*, not as a change to this one.

### 2.2 Division truncates toward zero

`/` truncates toward zero and `%` takes the sign of the dividend, which is C's
rule and the one most readers expect.

```
(0 - 7) / 2  == -3      (0 - 7) % 2  == -1
7 / (0 - 2)  == -3      7 % (0 - 2)  ==  1
(0 - 7) / (0 - 2) ==  3
```

Division and remainder by zero **trap** (§7). So does the one division that
overflows, `MIN / -1`; `MIN % -1` is `0` rather than a trap, because the
answer is representable even though the quotient is not.

### 2.3 Shifts are defined for every count

For a value of width `W` (32 for `int`, 64 for `word`):

| count | `a << n` | `a >> n` | `ushr(a, n)` |
| --- | --- | --- | --- |
| `n < 0` | trap | trap | trap |
| `0 <= n < W` | shift, wrapping within `W` | arithmetic (sign-filling) | logical (zero-filling) |
| `n >= W` | `0` | `0`, or `-1` if `a < 0` | `0` |

```
1 << 31  == -2147483648      (0 - 1) >> 35 == -1
1 << 32  ==  0                       4 >> 35 ==  0
1 << 35  ==  0                (0 - 8) >> 1  == -4
```

`>>` is the arithmetic shift; the logical one is spelled `ushr`, so which is
meant is visible where it happens rather than implied by a declaration
elsewhere.

This matches the C target today, which routes both `int` and `word` shifts
through `id_shl`/`id_sar`. It does **not** match the other two targets — see
§10.

### 2.4 Bitwise and logical operators

`& | ^ ~ << >>` require integral operands (`int` or `word`); `float` is
rejected at compile time. `&& || !` likewise take integral operands and yield
`int` `0` or `1`.

Mixing `int` and `word` in one operation widens to `word`.

## 3. Floats

`float` is IEEE-754 binary64 with the usual arithmetic. `%` on a float is a
compile error. Mixing `int` or `word` with `float` in an arithmetic or
comparison operator widens to `float`.

**Printing is lossy, and this is recorded rather than chosen.** A float reaches
text through C's `%g`: six significant digits, trailing zeros dropped,
exponent form beyond that range.

```
print(2.0)          →  2
print(1.0 / 3.0)    →  0.333333
print(0.1 + 0.2)    →  0.3
print(123456789.5)  →  1.23457e+08
```

`0.1 + 0.2` is not `0.3`, and a float does not survive a round trip through
`print`. A shortest-round-tripping representation (what Python, JavaScript and
Rust print) would be the better answer, but changing it would move the output
of every program in the tree and every golden file in `idstd`, so it is a
separate piece of work. It is written down here so that the WASM target — which
does not implement float printing at all — implements *this* and not something
of its own.

**Float literals have no exponent form.** `1.0e20` does not lex. A literal is
digits, a point, digits.

## 4. Strings

A `string` is an immutable byte sequence. There is no mutation operator; `+`
builds a new string.

- `+` with a `string` on either side concatenates, converting the other operand
  (`"lucky " + 7` is `"lucky 7"`).
- `==` and `!=` compare contents, not identity.
- `len(s)` is the length in **bytes**. `id` has no notion of a character; a
  multi-byte UTF-8 sequence is that many bytes.
- `charat(s, i)` is the byte at `i`, or `-1` if `i` is outside the string.
  Reading past the end is a value, not a trap — it is how a scanner detects
  end-of-input.
- `chr(n)` builds a one-byte string.
- `to_int(s)` parses a leading integer.

**A string cannot contain a NUL byte.** This is a consequence of the C
representation that has already cost something real: `idstd` abandoned a
planned function over it. It is recorded as a limitation rather than a design
decision, and a target is not free to lift it, because a program that works on
one target and not another is the thing this document exists to prevent.

## 5. Lists

- `[a, b, c]` builds a list; `[]` builds an empty one where the type is known.
- `xs[i]` reads, `xs[i] = v` writes; both **trap** on an index outside
  `0 <= i < len(xs)`. There is no silent drop and no growth by assignment.
- `push(xs, v)` appends; `pop(xs)` removes and returns the last element and
  **traps** on an empty list; `len(xs)` is the count.
- Lists have **reference semantics** (§1). Two names for one list see each
  other's writes.
- A `float` stored in a list survives unchanged: cells are uniform 64-bit and
  a float is stored by bit pattern, not by conversion.
- `(import xs)[i] = v` is rejected at compile time. Index-assignment is only
  recognised through a plain identifier, so writing through an imported global
  directly used to compile to a discarded comparison and do nothing; pass the
  list to a helper that takes it as a parameter.

## 6. `word` and the flat store

One flat, byte-addressed memory, shared by the whole program. An address is an
ordinary `word`, so a record is an offset, an array is a stride, and taking an
address is arithmetic — none of which needs syntax.

- `alloc(n)` reserves `n` bytes and returns their address. **Address 0 is never
  returned**, so it can mean null. Allocations are 8-byte aligned.
- `store_size()` is the high-water mark.
- `peek8/16/32/64(addr)` and `poke8/16/32/64(addr, v)` load and store, **little
  endian**.
- Every access is bounds-checked against the high-water mark and **traps**
  outside it. This is the entire reason the store is a primitive rather than a
  library: the mistake that silently corrupts memory in C is a clean abort
  here.
- `str_of_mem(addr, n)` and `mem_of_str(s)` bridge bytes and strings.
- `udiv`, `umod`, `ult`, `ushr` are the unsigned readings of `/ % < >>`. The
  plain operators keep their signed meaning.

**There is no way to release memory.** `alloc` is a bump pointer; the arena
behind lists and strings is freed only at process exit. This is a property of
the language today, not of the C target, and every target must be honest about
it rather than quietly collecting garbage — a program whose memory is reclaimed
on one target and not another has no portable memory behaviour at all. Fixing
this is the open question in `docs/GAPS.md`; until it is fixed it is a promise,
and it is the reason `id` is currently a language for programs that exit.

## 7. Traps

A trap writes one line to **stderr** and exits with status **1**. It is not
catchable; `id` has no exceptions.

| condition | message |
| --- | --- |
| `/` or `%` by zero | `id: division by zero` / `id: remainder by zero` |
| `MIN / -1` | `id: division overflow` |
| shift by a negative count | `id: shift by a negative amount` |
| list index outside the list | `id: index N out of bounds (len M)` |
| `pop` of an empty list | `id: pop from empty list` |
| flat-store access outside the store | `id: store address N out of range (size M)` |
| a list grown past its capacity limit | `id: list capacity overflow` |
| a size computation that overflows | `id: allocation size overflow (WHAT)` |
| allocation refused by the host | `id: out of memory (N bytes)` |

The exact text is part of the specification, not an implementation detail:
these messages are what a user sees when their program fails, and a target
that words them differently makes the language feel different.

## 8. Program structure and I/O

- `main(int argc, string[] argv)` is the entry point. Its `int` return is the
  process exit status. `argv[0]` is the program name, whose spelling depends on
  how the program was launched and is therefore **not** specified.
- `print(x)` writes a value and a newline to stdout; `put(s)` writes without
  one; `flush()` flushes.
- `input()` reads one line from stdin, without its newline, and returns `""` at
  end of input. `read_all()` reads the whole of stdin.
- An exported variable is initialised when its declaring function runs, not
  before. Reading one earlier is rejected at compile time when the exporting
  function is unreachable from `main`, and is otherwise the programmer's
  responsibility.

## 9. Deliberately unspecified

Naming these keeps them from being discovered as bugs later:

- `argv[0]`'s exact spelling.
- The printed spelling of a NaN. `0.0 / 0.0` prints `-nan` under glibc and
  `nan` through LLVM, because the two disagree about the sign bit of the NaN
  they produce, not about anything `id` decides. The infinities *are*
  specified: `1.0 / 0.0` is `inf` and `-1.0 / 0.0` is `-inf`.
- The address `alloc` returns, beyond "nonzero, 8-aligned, and distinct from
  every other live allocation".
- The order in which unrelated top-level definitions are emitted.
- Timing: `ticks()` is monotonic milliseconds from an unspecified origin.
- The order the operands of one operator are evaluated in. This is listed here
  as a description of today rather than as a choice: §10's S11 says why, and
  says it should stop being unspecified.
- Anything reached through a native backend, which is by definition
  platform-specific — but see `backends/*/backend.json`, whose `abi` block is
  the contract in `id`'s own types.

## 10. Where the targets do not meet this specification today

Found by writing this document and running `tests/conform.sh`. Each is a bug
against the spec, not a permitted variation.

On its first run `tests/conform.sh` reported **61 cases, 142 passed, 9 failed,
32 gaps**. Every one of the nine was previously invisible, and three of them
were wrong answers rather than missing features.

It now reports **173 passed, 0 failed, 10 gaps**. The three wrong answers are
fixed, and `word` and the flat store — 21 of the 30 builtins, and everything
in §6 — work on all three targets. The 10 remaining gaps are one missing
feature, float-to-string on WASM, and they are all of it.

| # | what | affected | state |
| --- | --- | --- | --- |
| **S1** | Overflow wraps only because gcc chooses to; C calls it undefined. Needs `-fwrapv` or unsigned-routed arithmetic. Not currently observable, which is exactly why it is worth fixing before an optimiser makes it so. | C | open |
| **S2** | Shifts with a count outside `0..W` gave three different answers: `(0 - 8) >> 32` was `-1` (§2.3) on C, `0` on LLVM, and `-8` on WASM, which masks the count to 5 bits. Both now route through helpers that give §2.3's answer. | LLVM, WASM | fixed |
| **S3** | `str_of_int` was wrong for `INT_MIN`: `2147483647 + 1` printed `-./,),(-*,(`, because the digit loop negated a negative value, which overflows, and every digit then came out as `'0' - d`. It now folds into the negative half of the range, which is always representable. | WASM | fixed |
| **S4** | `int` division and remainder by zero did not trap: LLVM raised SIGFPE (exit 136) and WASM aborted (exit 134) where C prints a line and exits 1. The checked-division fix recorded as C2 in `docs/GAPS.md` had been applied to the C runtime only. | LLVM, WASM | fixed |
| **S5** | Float-to-string is not implemented, so printing or concatenating a float fails to compile — the 10 remaining gaps, and now the only one left. | WASM | open |
| **S6** | `word`, the flat store and the unsigned builtins were rejected — 21 of 30 builtins, making §6 unimplementable. LLVM now calls the C runtime's helpers (which it already links); WASM implements the store in its own WAT over linear memory, which is its natural home. Only the real-time I/O builtins remain C-only, and those are genuinely platform-bound. | LLVM, WASM | fixed |
| **S7** | Because of S6, `idstd` did not build — `core/data/buf/buf.id` uses `word`. Fixed with S6. | LLVM, WASM | fixed |
| **S8** | Calls resolved at link time are refused, so no program using a native backend builds. | LLVM, WASM | open |
| **S9** | Only the C target is reachable from `bin/idc`, the primary compiler; the other two exist only in `idc.py`. | — | open |
| **S10** | The flat store sits at a fixed 1 MiB offset in the same linear memory the string/list heap grows through, so **the heap is capped at 1 MiB**. Passing it used to overwrite the store and read back garbage with nothing reported — a 400 000-element list made `peek64` return `71772820526333952` where C returned `123456789`. The heap now aborts with `id: out of memory` instead, which is §7-legal, but the cap is real and the other two targets do not have it. The proper fix is to place the store above the heap and grow it with `memory.grow`, checking the heap against its actual base rather than a constant. | WASM | mitigated |

| **S11** | **The order the operands of one operator are evaluated in is not specified, and the targets differ.** The C target inherits C's, which is unspecified between the arguments of a call, so `"pop=" + pop(xs) + " len=" + len(xs)` prints the length before *or* after the pop depending on the C compiler. The LLVM target evaluates left to right, because its lowering emits instructions in the order it walks the tree. Found by `tests/kernel.sh`, which runs the same source on both runtimes and requires them to agree. | C, LLVM | open |

**S11 needs a decision, not an implementation.** Left to right is the answer
most readers expect and the one the LLVM target already gives; making the C
target agree means sequencing every operand through a temporary, which changes
the emitted C for every program and therefore every byte-parity check in the
suite. Until it is decided, an expression whose operands have effects on each
other means two things.

S5–S8 are missing implementation, and are what `docs/BACKENDS.md` is the plan
for. S6 is the one that matters most: it is 21 of the 30 builtins, it is what
makes S7 true, and the flat store is the primitive an `id`-written runtime
would be built on — so closing it is what turns a second target from a
translation of the C emitter into a target in its own right.

`docs/BACKENDS.md` is the plan for the compiler restructuring these imply.
