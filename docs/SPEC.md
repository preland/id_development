# What an `id` program means

> **Status: normative, and executable.** Every claim here is a case under
> `idc/tests/conform/`, run on every target by `idc/tests/conform.sh`. §10 records
> where the targets do not meet it yet.

This document says what `id` code *does*, independently of how it is compiled.
Everything here is a promise every code-generation target must keep.

## Why it exists

Until now the answer to "what does this program do" was "whatever the C the
compiler emitted does". That was workable while there was one target. There is
not: `idc/idc.py` has emitted LLVM IR and WebAssembly since `f229d52`, and the
three have **already drifted**. A shift wider than the type gives three
different answers today — the C target defines it through a runtime helper,
the LLVM target emits a raw instruction whose result is poison, and the WASM
target masks the shift count. Nothing reports this, because nothing was
looking.

Nothing *could* have been looking. `idc/tools/parity.sh`, which has caught almost
every bug in this compiler, compares the **text** two compilers emit. That is
only a question that exists while both of them emit C, and it says nothing
about a target that emits something else. It stays exactly as useful as it has
always been for the two C-emitting compilers, and it is structurally incapable
of growing into the cross-target gate.

`idc/tests/conform.sh` is that gate: it builds each case in `idc/tests/conform/` every
way the toolchain allows, runs it, and requires the same stdout, exit code and
stderr from each. This document is what those cases are checking, written down
so that a disagreement has a right answer instead of a majority vote.

**The C target is the reference.** Where this document merely records existing
behaviour it says so; where it *chooses*, it says that too, and names what has
to change.

---

## 1. Types

Five scalar types and two type constructors. `T[]` is a list of `T`, and
nests. `func(T1, T2) return R` is a function type (§1.1).

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

**A narrowing conversion is written down.** A declaration or an assignment may
narrow -- `int n = a;` where `a` is a `word` -- because the type it narrows to
is named on the line that does it. An **argument may not**: the parameter's
type is in another file, so `take(a)` would read as if nothing happened while
dropping half of a `word`. Declare a local of the parameter's type and pass
that. Widening is exact and needs no ceremony in either place. This is the
same strictness `xs[a]` has always had, which used to look inconsistent with
both of the others.

### 1.1 Function values

A library sometimes needs code from its user: an engine runs a frame by calling
the game's step. `id` says that with a value whose type is a function type,
rather than by having the library call a name every user must define.

```
tick(int n) {
  print("tick " + n);
} return void;

run_frame(func(int) return void step, int dt) {
  step(dt);
} return void;

main(int argc, string[] argv) {
  run_frame(tick, 16);
} return int 0;
```

**The type.** `func(T1, T2) return R` lists parameter types only, with no
names; `R` may be `void`, and `func() return void` takes nothing. A parameter
type may itself be a function type. Brackets after the return type belong to
the return type: `func(int) return int[]` returns a list. `func` is a keyword
and cannot be a name. However it is spaced, a function type is one type: two
spellings are the same type exactly when they list the same types in the same
order, and a name that is a function type in one place has that same type
everywhere in its unit, as every name does (§1).

**The values.** A value of a function type is a named top-level function
written in `id` -- one of the program's, the standard library's, or a `native`
declaration. Nothing else is: there are no lambdas, no closures and no partial
application, and a builtin (`print`, `len`, ...) or an `asm` function is not a
value. A function's name where a value is expected denotes that function, and
its signature must be the type exactly: the same parameter types in the same
order and the same return type. There is no conversion between function types;
`func(int) return void` does not accept a function taking a `word`.

**Where one may be.** A parameter, a local, and an export read with
`(import NAME)` -- which is how a library stores a value its user hands it:

```
eng_setup() {
  export func(int) return void eng_step = tock;
} return void;

frame() {
  func(int) return void g = (import eng_step);
  g(16);
} return void;
```

Nowhere else. Not an element of a list, and so not in a list type (there is no
way to spell one); not a function's return type; not an operand of any
operator, comparisons included; not an argument to a builtin; not a condition.
A test case passes one by naming the function where the argument goes --
`(tick, 16):(tick, 16)` -- or through `(import NAME)` after a `given` setup has
stored it (docs/TESTS.md).

**Calling one.** `step(dt)`, where `step` is a parameter, local or export of a
function type. The arguments are checked against the type -- how many, and each
against its parameter type, with the narrowing rule above -- and every rule of
§7.1 applies unchanged: no call inside an argument, a return clause is a name or
a literal.

**Why this much and no more.** A call through a value hides which function
runs, which is the one thing `id`'s rules otherwise never hide. What stays
visible is the type: it is written on the declaration of the name being called,
in the same function or in the export, and every diagnostic about a call
through one names it. Values that could be built at run time, returned, or kept
in a list would let a call's function come from anywhere the value travelled;
a named function stored or passed at a line the reader can find cannot.

**What the compiler says.** Where a function type is expected, the message
names both signatures; where no function value may be at all, it names the
value's type.

| written | error |
| --- | --- |
| `func(int) return void f = pair;` where `pair` takes two ints | `cannot initialize func(int) return void 'f' with a func(int, int) return void value` |
| `f = twice;` where `twice` returns int | `cannot assign a func(int) return int value to func(int) return void 'f'` |
| `run_frame(shout, 16)` where `shout` takes a string | `argument 'step' of 'run_frame' expects func(int) return void, got func(string) return void` |
| `step(dt, dt)` | `'step' is a func(int) return void, which takes 1 argument(s), got 2` |
| `step(label)` with a string | `argument 0 of 'step' (a func(int) return void) expects int, got string` |
| `step(w)` with a word | `argument 0 of 'step' (a func(int) return void) narrows word to int; declare a int local and pass that` |
| `int[] xs = [tick];` | `a function value cannot be an element of a list: element 0 is func(int) return void` |
| `func(int) return void[] fs` | `'func(int) return void[]': brackets after a function type's return type belong to the return type, and void[] is not a type; a function value cannot be an element of a list` |
| `} return func(int) return void f;` | `'pick' returns func(int) return void; a function value cannot be a function's return type -- store it in an export, or pass it to the function that calls it` |
| `func(int) return func(int) return void` | `a function type cannot return a function value; pass the function, or store it in a local or an export` |
| `func(int dt) return void` | `a function type lists parameter types only: write 'int', not 'int dt'` |
| `tick + 1` | `'+' cannot take a function value: its left operand is func(int) return void; a function value can only be passed, stored or called` |
| `print(tick)` | `'print' cannot take a function value: argument 0 is func(int) return void; a function value can only be passed to a function written in id, stored or called` |
| `if(step)` | `a condition cannot be a function value (func(int) return void); call it, and test what it returns` |
| `func(string) return void f = print;` | `'print' is a builtin, not a function defined in id; only a function written in id can be a value -- write one that calls 'print' and pass that` |
| `int func = 1;` | `'func' is a keyword (it begins a function type, see docs/SPEC.md) and cannot be used as a name` |
| `int thing = 1; thing();` | `'thing' is a variable, not a function` -- unchanged: only a variable of a function type can be called |

`-tick`, `!tick` and `tick[0]` draw the existing unary and index messages,
which name the type.

**Uniqueness and reachability.** A function named as a value keeps its name in
the fingerprint the duplicate-logic rule compares (docs/HACKING.md), as a
called function does, so two functions that differ only in which function they
pass are different logic. A call through a parameter or local is that
variable's position, like any other use of it, so renaming the parameter does
not make a second function. A function named as a value is reachable exactly as
a called one is: it is emitted, and an export it declares is live.

**On the targets.** The C target spells a function type as a pointer to
function through `__typeof__` -- `__typeof__(void (*)(int)) step` -- names a
function value `id_NAME`, and calls through the variable, whose prototype
converts the arguments. The LLVM target, `--freestanding` included, spells it
`ptr`, names a function value by its symbol (`ptr @id_tick`) and calls through a
loaded pointer (`call void %v7(i32 16)`), converting each argument to the
parameter type the function type spells. WASM does not have function values
(§11, S12).

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

Division and remainder by zero **trap** (§8). So does the one division that
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

**A comparison and a bitwise operator in one expression must be grouped with
parentheses.** The bitwise operators bind tighter than the comparisons in `id`
and looser in C, so an expression that relies on either table can only be read
by someone who knows which one applies. A comparison (`== != < <= > >=`, and
the bare `=` that means equality inside an expression) whose left or right
operand is an unparenthesized bitwise operation (`& | ^ << >>`) is a compile
error, and so is a bitwise operation whose operand is an unparenthesized
comparison. The diagnostic shows how the current precedence groups it:

```
flags & 4 == 4       error: 'flags & 4 == 4' mixes a bitwise '&' with a comparison '==';
                     parenthesize it as the current precedence reads it: '(flags & 4) == 4'
(flags & 4) == 4     ok
flags & (4 == 4)     ok
```

The second form cannot be written without parentheses today, because a
comparison binds looser and only reaches a bitwise operand through them; the
rule names it anyway, since it is about the reader and not about this table.
The parentheses are grouping only: they change neither the emitted code nor a
function's fingerprint for the uniqueness rule. Unary `~` is out of scope -- it
binds tighter than every binary operator and cannot be misread -- and so are
`&&` and `||` next to a bitwise operator. `idc.py` does not have this rule.

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

- `[a, b, c]` builds a list. **A list literal has no type of its own**: it
  takes the type of the slot it is going into -- the declared type, the
  parameter's type, or the function's return type -- and every element is
  checked against that type's element type, the first no differently from the
  rest. So `word[] xs = [0, 0, 0]` is a `word[]` literal, and
  `int[] xs = ["a"]` names element 0. `[]` is the same rule with no elements
  to check.
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

## 7. Evaluation order

**The operands of an operator, and the arguments of a call, are evaluated left
to right.** So are the elements of a list literal, and the two sides of an
index assignment: the list, then the index, then the value.

```
"a=" + bump(c) + " b=" + bump(c)      the first bump runs first
"pop=" + pop(xs) + " len=" + len(xs)  len sees the shorter list
f(step(c), step(c))                   the first argument is the first step
```

Most expressions give the same answer whichever order they are evaluated in,
which is why this was unwritten for a long time. It stops being true the moment
two operands share state -- and the two programs that found it are the two that
would: a DEFLATE bit reader, where every read advances the stream so the order
*is* the format, and a line of a document that pops a list and then measures
it.

This is a **choice**, made here rather than left to each target, and it is the
one the majority of languages a reader will have used make. The alternative --
declaring the order unspecified and requiring programmers to avoid the
situation -- was rejected for a specific reason: `id` has no way to *say* that
an expression has an effect, so a rule the programmer must obey is a rule
nothing can check. An order everything obeys needs no checking.

It is deliberately a property of the language and not of a flag. If it ever
needs to be configurable, the thing to configure is the target, not the
program: a program that reads differently depending on a build setting is
worse than either order.

### 7.1 The shape of an expression

Two rules, and one idea behind both: **a value that takes a step to compute is
given a name, and the name is what the reader of the line sees.**

**A call may not be an argument to a call.** Not at any depth: the argument
expression must contain no call anywhere inside it.

```
int n = lm_len(s2w(s));        rejected
word a = s2w(s);               the same thing, said in two steps
int n = lm_len(a);

int n = f(x) + g(y);           fine -- neither call is inside the other's
                               argument list
```

**A return clause is a name or a literal.** Nothing else: no call, no
operator, no index, no list literal.

```
} return int n;                a name
} return int 0;                a literal
} return string "";            a literal
} return void;                 nothing

} return int i + 1;            rejected -- name it
} return int lm_len(a);        rejected
} return int xs[0];            rejected
} return int[][] [tab, row];   rejected, and it never parsed anyway: the `[`
                               after the type reads as another dimension of it
```

Neither rule buys the compiler anything. Both are about the reader. `id` fixes
the order operands are evaluated in (§7) precisely because two operands can
share state — and the expression that most easily hides shared state from a
reader is the one with a call buried inside another call's arguments, where
neither the order nor the fact that there are two steps is visible. Naming the
intermediate makes both visible, in the order they happen.

The cost is real and is not hidden here: **the action limit is unchanged**, so
a block that gains a name may have to give up a statement, and a function that
gains a statement may have to become two. Across this repository the two rules
cost about 1600 new names and several hundred new functions. That is the trade,
made deliberately: `docs/FRICTION.md` §14 and §15 are what the other side of it
was costing.

Two shapes cannot be repaired by naming, and both become a function instead:

* a nested call in a `while` condition — a name bound before the loop is
  computed once where the loop needs it every iteration;
* a nested call to the right of `&&` or `||` — a name bound before the `if` is
  computed even when the operator skips it.

```
while(is_alnum(charat(src, i))) {     rejected

while(is_alnum_at(src, i)) {          the composition, as a function
```

### 7.2 A function is not a constant

**A function that only returns one scalar constant is rejected.** Such a
function is a constant under a function's name: every caller has to open it to
learn that it never changes. A value that never changes is declared as one, in
the project's `conf.id` (`docs/PROJECT.md` §5), and read with `(import name)`.
A directory imported on its own, with no `conf.id` of its own, reads the
constants of its enclosing root -- the nearest directory above it that has a
`conf.id` -- and none of that root's imports, so the constant has one home
however much of its tree a program imports.

```
ch_nl() {                      rejected
} return int 10;

funcs_per_file() {             rejected -- a local initialised to a literal
  int n = 3;
} return int n;

zero(int a) {                  rejected -- the parameter is never used
} return int 0;

k() {                          rejected -- 2 * 1000 folds to 2000
  int n = 2 * 1000;
} return int n;
```

```
p.id:1: error: 'ch_nl' only returns the constant 10; declare it in conf.id as
  'int ch_nl = 10;' and read it with (import ch_nl)
```

Precisely, a function is rejected when it is not `main`, not a `native`
declaration, and returns `int`, `word`, `float` or `string`; when every
statement of its body declares a local of its own (not an `export`) or assigns
one, each time to a value that is a literal or an operator over literals the
compiler folds; and when its return clause is such a literal or one of those
locals. A call, an `import`, a parameter, a loop, a branch or a write through
an index anywhere in the body makes it a function. So do these, deliberately:

- **A list.** `} return int[] ps;` over `int[] ps = [2, 3, 5];` builds a fresh
  list on every call, so each caller owns what it got. A shared constant could
  not behave that way.
- **Assigning a parameter.** `reset(int a) { a = 5; } return int a;` uses its
  parameter; a parameter is not one of the function's own locals.

Folding is the compiler's existing constant fold for integers, and only it: a
value it does not reduce -- `-1` written with the unary operator, a float
expression, a local initialised from another local -- is not recognised as a
constant, and such a function is accepted. A negative result is spelled in the
diagnostic as the subtraction that folds (`int n = 0 - 1;`).

## 8. Traps

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

## 9. Program structure and I/O

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
- A variable exists from its declaration to the end of the block that declares
  it; a function's return clause sees the body's top-level declarations. A use
  anywhere else, including before the declaration, is rejected at compile time.

## 10. Deliberately unspecified

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
- Nothing about the order operands are evaluated in: §7 chooses it.
- Anything reached through a native backend, which is by definition
  platform-specific — but see the `native` declarations in `idc/backends/*/`,
  which are the contract in `id`'s own types.

## 11. Where the targets do not meet this specification today

Found by writing this document and running `idc/tests/conform.sh`. Each is a bug
against the spec, not a permitted variation.

On its first run `idc/tests/conform.sh` reported **61 cases, 142 passed, 9 failed,
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
| **S9** | Only the C target is reachable from `idc/bin/idc`, the primary compiler; the other two exist only in `idc/idc.py`. | — | open |
| **S10** | The flat store sits at a fixed 1 MiB offset in the same linear memory the string/list heap grows through, so **the heap is capped at 1 MiB**. Passing it used to overwrite the store and read back garbage with nothing reported — a 400 000-element list made `peek64` return `71772820526333952` where C returned `123456789`. The heap now aborts with `id: out of memory` instead, which is §7-legal, but the cap is real and the other two targets do not have it. The proper fix is to place the store above the heap and grow it with `memory.grow`, checking the heap against its actual base rather than a constant. | WASM | mitigated |

| **S11** | **The C target does not evaluate operands left to right**, which §7 now requires. It emits one C expression per `id` expression, and C does not sequence the arguments of a call: gcc evaluates them right to left, so `"pop=" + pop(xs) + " len=" + len(xs)` prints the length *before* the pop. The LLVM and WASM targets both conform, because both emit instructions in the order they walk the tree. Found by `idc/tests/kernel.sh`, which runs the same source on both runtimes and requires them to agree. | C | open |

**S11 is now an implementation, not a decision.** §7 chose. Making the C target
conform means hoisting an operand into a temporary whenever two operands of one
expression both contain a call -- which is expressible as a pure expression
rewrite, through the comma operator and a depth-indexed array of temporaries in
the runtime prelude, so it needs no restructuring of the emitter. What it costs
is byte-parity: every emitted line with two calls in it changes, and `idc/idc.py`
would have to change with it to stay identical.

The other way there is `docs/LLVM.md`'s: the C target printed from the IR,
whose lowering is already left to right. That fixes it for free and abandons
byte-parity deliberately rather than as a side effect.

`idc/tests/conform/order/` holds the cases. `idc/tests/conform.sh` names the C target's
non-conformance rather than failing on it, so that removing the exemption is
how the fix gets noticed.

| **S12** | **Function values (§1.1) do not exist on WASM.** They are implemented in `idc/bin/idc`, whose targets are C and LLVM; the WASM target is still built by `idc/idc.py`, which is being retired and refuses `func` as a type. `idc/tests/conform.sh` names `wasm:fn` as known apart, so the gap is counted rather than hidden. It closes with `docs/TODO.md` 9b, `--target wasm` in `idc/bin/idc`. | WASM | open |

S5–S8 are missing implementation, and are what `docs/BACKENDS.md` is the plan
for. S6 is the one that matters most: it is 21 of the 30 builtins, it is what
makes S7 true, and the flat store is the primitive an `id`-written runtime
would be built on — so closing it is what turns a second target from a
translation of the C emitter into a target in its own right.

`docs/BACKENDS.md` is the plan for the compiler restructuring these imply.
