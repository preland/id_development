# The LLVM target, and the IR it is printed from

> **Status: a plan, being executed.** "Where this stands" is the only section
> that describes reality; everything else is the shape being built toward.
> Each step lands with `idc/tools/parity.sh` still MATCH on the C target and
> `idc/tests/conform.sh` green on every target.

`idc/bin/idc` has one code generator, and it emits C. This document is the second
one, and the reason it is not simply a third copy of `gen_expr`.

## Why an IR, and not an AST walk

`idc/idc.py` (since deleted) emitted C, LLVM IR and WAT from three near-duplicate AST walks. Copying
that shape into the self-hosted compiler would be the obvious move and it is
the wrong one, for a reason that has nothing to do with duplication:

**an AST walk cannot optimise.** Constant folding across a branch, dead-store
elimination, common-subexpression elimination, licm, inlining — every one of
them needs to see the program as a graph of operations with explicit data
flow, not as a tree of syntax. `docs/BACKENDS.md` proposes a `tgt_*` interface
that the AST walk asks how to spell each construct; that is the right seam for
*translation* and the wrong one for *compilation*, and this repository wants
the second. The goal is output that matches what a systems language gets from
its optimiser, and no amount of asking a target how to spell `+` gets there.

So the second target is not a second walk. It is:

```
AST  ──lower──▶  IR (SSA, CFG)  ──passes──▶  IR  ──print──▶  LLVM IR text
```

and the C target stays exactly where it is, an AST walk, byte-parity-locked
against `idc/idc.py`. The two do not share a spelling layer, because they are not
doing the same job. If the C target is ever rebuilt on the IR, it will be
because the IR earned it, not because an interface was declared first.

`docs/BACKENDS.md`'s step order (Python target, then LLVM) is superseded by
this document for the same reason: the interface it wanted to validate is not
the interface being built.

## Where the code lives

```
idc/compiler/parse/
  front/            lex, parse                        → AST      (unchanged)
  mid/              checks, types                     → tables   (unchanged)
  back/
    drive/          target-independent driver
      run/            args, the checks gate, DCE, target dispatch
      sink/           emit_line -- every emitted byte leaves through here
    ir/             the intermediate representation
      core/           the instruction store, accessors, the IR text dump
      build/          AST → IR lowering
      opt/            the passes, and the pipeline that orders them
    tgt/
      ast/            the S-expression dump (`idparse ast`)
      c/              the C emitter -- an AST walk, unchanged
      ll/             the LLVM IR printer -- an IR walk
```

`back/` was `drive/ emit/ out/` before this work and is `drive/ ir/ tgt/`
after; nothing inside the C emitter changed, only where it sits. Parity was
MATCH across the move, which is the only reason a move that size is safe.

## The IR

One flat instruction store, in the same parallel-list style as the AST, because
`id` has no structs and because the AST has already proved the idiom at this
scale.

**A value is an instruction.** The id of an instruction *is* the id of the
value it defines; an instruction that defines nothing (a `store`, a branch, a
`ret`) simply has no users. This is LLVM's own model and it removes an entire
table.

```
iop      string   the opcode
ity      string   the id type of the value defined, "" if none
ia       int      operand A -- a value id, or -1
ib       int      operand B -- a value id, or -1
istr     string   auxiliary text: a call target, a literal, a compare predicate
ilist    int[]    auxiliary values: call arguments, phi incoming values
iblk     int[]    auxiliary blocks: branch targets, phi incoming blocks
ihome    int      the block this instruction belongs to
```

Blocks and functions are two more sets of columns:

```
bfunc    int      the IR function this block belongs to
binsn    int[]    its instructions, in order
blabel   string   its label
bpred    int[]    its predecessors, computed rather than built

fnname   string   the id function's name
fnret    string   its return type
fnpar    int[]    its parameters, as `param` instructions
fnblk    int[]    its blocks, entry first
fnnode   int      the AST node it was lowered from
```

### Opcodes

| opcode | means | operands |
| --- | --- | --- |
| `const` | a literal | `istr` is the literal text |
| `param` | a function parameter | `istr` is its name |
| `global` | the address of an exported global | `istr` is its name |
| `add` `sub` `mul` `sdiv` `smod` `udiv` `umod` | integer arithmetic | `ia`, `ib` |
| `fadd` `fsub` `fmul` `fdiv` | float arithmetic | `ia`, `ib` |
| `and` `or` `xor` `shl` `sar` `ushr` | bitwise | `ia`, `ib` |
| `icmp` `fcmp` | comparison, `istr` is the predicate | `ia`, `ib` |
| `not` `neg` | unary | `ia` |
| `zext` `sext` `trunc` `sitofp` `fptosi` `bitcast` | conversion | `ia` |
| `alloca` | a stack slot for a local | `ity` is the slot's type |
| `load` | read a slot or a global | `ia` |
| `store` | write one | `ia` = address, `ib` = value |
| `call` | a call, `istr` is the callee | `ilist` = arguments |
| `br` | unconditional branch | `iblk[0]` |
| `cbr` | conditional branch | `ia` = condition, `iblk[0]`, `iblk[1]` |
| `ret` | return | `ia`, or -1 for void |
| `phi` | an SSA merge | `ilist` values, `iblk` blocks, positionally paired |

**A `const` is never printed as an instruction.** It has no home block and
prints as its literal wherever it is used, which is what LLVM IR wants and
what makes constant folding a rewrite of one operand rather than a rewrite of
the instruction stream.

### Lowering is deliberately dumb

`back/ir/build/` produces **alloca form**: every local is a stack slot in the
entry block, every read is a `load`, every write is a `store`, every `if` and
`while` is a pair of blocks and a `cbr`. There is no cleverness and no attempt
to produce good IR.

That is a choice, not a shortcut. Alloca form is obviously correct — there are
no phis to get wrong, and a variable's value is always in exactly one place —
so the lowering can be trusted without a proof. Everything good about the
output then comes from the passes, which is where it can be tested, measured
and improved independently. A program compiled with every pass turned off must
still run correctly, and that property is worth more than the IR being pretty.

### Passes

`back/ir/opt/` holds them. The pipeline is a list of pass names per `-O` level,
walked by a dispatch chain — `id` has no function pointers, so a pass table is
a chain of `if` on a name, and `docs/DISPATCH.md`'s `select` would collapse it
if it ever exists.

| pass | what it does | why it is first |
| --- | --- | --- |
| `mem2reg` | promotes allocas to SSA values, inserting phis | every other pass is blind while values live in memory |
| `constfold` | folds operations on constant operands | |
| `dce` | drops instructions with no users and no effects | what the other passes leave behind |

`-O0` runs none. Any level above 0 runs the same fixed sequence, once per
function (`back/ir/opt/run/pipe/run.id`): predecessors, `mem2reg`, `constfold`,
`dce`, `constfold`, `dce`. There is no `simplifycfg`, `gvn`, `inline` or `licm`
yet, and no `-O2` pipeline that repeats to a fixed point; those are the passes
this section's rationale argues for, not ones that exist.

**`mem2reg` places phis maximally and then removes the trivial ones**, rather
than computing dominance frontiers: a phi is inserted for every promotable slot
in every block with more than one predecessor, the function is renamed in
reverse post-order, and a phi whose incoming values are all one value (or that
value and itself) is replaced by it, to a fixed point. On the reducible CFGs
that `if`/`while` produce this reaches the same answer as the frontier
algorithm, and it is a page of code rather than three.

### Loop versioning

The lowering of a `while` asks the C emitter's analysis (`back/tgt/c/emit/prog/code/body/fast/`,
docs/PERFORMANCE.md section 5, item 5) which of its list accesses it can prove in range once,
before the loop. When there are any, the loop is lowered twice behind one guard
(`back/ir/build/stmt/flow/loop/`): in the guarded copy those accesses call the runtime's
`id_list_cell` and `id_list_cell_set`, which do not check, and the other copy is the loop as
written, so a loop that would trap still traps at the same iteration with the same message.
The analysis states its guard as tokens in reverse Polish form, not as text (`lpg`, documented in
`tgt/c/emit/prog/code/body/fast/state.id`): names and literals, `wide`, `len` and `cap`, sums,
differences and products of N operands, comparisons, and `|` to end a clause. The C emitter prints
them as one C condition (`fast/render/`); `loop/guard/` builds them in 64 bits, with
`id_list_len_raw` and `id_list_cap_raw`, which answer -1 for a list that is not there. A token it
does not know gives the loop up, so the checked loop is always the fallback, and `tests/conform.sh`
counts the clauses of the guards each target builds for every conformance program with a loop,
so a token one target stops understanding is a failure there rather than a slowdown. The
runtime is the C one, so a freestanding build (`--freestanding`, `--runtime`) and
`-O0`, whose IR `tools/idrun` interprets, are not versioned.

## The runtime, and why builtins are inlined rather than called

`idc/idc.py`'s LLVM target (since deleted) linked the C runtime: every builtin is a `call` to an
external `id_*` symbol implemented in C and compiled by `clang` alongside the
`.ll`. That is the fastest way to a working target and it is where this one
starts too — but it cannot be where it ends, because it makes the LLVM target
*more* dependent on C than the C target is, and a microkernel cannot link
libc.

The end state is that the `id_*` helpers are themselves written in `id` and
compiled by this compiler. That is circular unless something is primitive, so
these are lowered **inline**, to instructions rather than calls:

- `alloc(n)` — a bump pointer over a linker-provided region: load, round up,
  compare against the limit, store, return the old value.
- `peek8/16/32/64`, `poke8/16/32/64` — a bounds compare and a `load`/`store`.
  (`peek8s/16s/32s`, `peek8u/16u/32u`, `bits_of_float`, `float_of_bits`, `bits32_of_float`,
  `float_of_bits32` are hosted runtime helpers only, and a freestanding build that calls one has an
  undefined `id_...` symbol at link time. `fail` is the exception: the freestanding runtime
  defines `id_fail`, which writes `id: MSG` to the serial port and stops the machine.)
- `store_size()` — a load.
- the arithmetic builtins `udiv`, `umod`, `ult`, `ushr` — instructions.

Everything else — lists, strings, `print`, `input` — is an ordinary `id`
function in the freestanding runtime, written over those primitives. Inlining
them is also better code than calling them, so this is not a cost paid for the
kernel's benefit.

A trap is a `call` to `id_trap`, which the freestanding runtime provides.

**Function values and closures** (`docs/SPEC.md` 1.1.1). A function value is a
`ptr` to an object the module never looks inside, so the same module runs on
every runtime, `tools/idrun` included, whatever its object layout is. A function
named as a value is `call ptr @id_fn_plain(ptr @idfn_a_NAME__0, ptr @id_NAME)`,
`bind(NAME, v1, ..., vk)` is `@id_clo_make(ptr @idfn_a_NAME__k, i32 k)` and one
`@id_clo_set(ptr, i32, i64)` per value (a list value first goes through
`@id_clo_copy`), and a call through a value reads the adapter with
`@id_clo_fn(ptr)` and calls it with the object first. The module defines the
adapters, one per (function, number of values) pair it uses: `@idfn_a_NAME__k`
takes the object and the unbound parameters, reads the bound ones with
`@id_clo_cell(ptr, i32)` and calls `@id_NAME`. The C runtime these `id_*` names
come from is `back/tgt/c/runtime/closure/c/`, and a native's function-pointer
parameter is given `@id_fn_raw(ptr)`, which stops a closure.

**String layout.** A `string` is a `ptr` to NUL-terminated bytes with the byte
count in the `size_t` just before them (`docs/MEMORY.md`, F2e). A literal is a
private global holding `<{ i64, [n x i8] }>` plus a private alias for the
address of the bytes, which is what every use of the literal names; the count is
the literal's length up to its first NUL, which is what a `strlen` said before
the count existed. `main`'s `argv` strings are built with `id_str_of_cstr`. The
count is `i64`, so a 32-bit LLVM triple would need `i32` there to match the
runtime's `size_t`. The freestanding runtime writes the same count in every
string it builds (`idc/runtime/lang/str/`, `mem/store/arena/bridge.id`) and
`len` is a load of it, so one literal means the same thing under either runtime.

## Where this stands

**The target works, self-hosts, and is the one `idc/tests/conform.sh` holds the
language to.** Measured on this checkout:

```sh
idc/bin/idc PATH --target llvm -o OUT        # build through the LLVM target
idc/bin/idc PATH --target llvm -O0           # ... with every pass off
idc/bin/idc PATH --target llvm --emit-llvm F # ... writing the IR instead
```

* **`back/` restructured** into `drive/ ir/ tgt/`, with the C emitter moved
  unchanged into `back/tgt/c/` and the S-expression dump into `back/tgt/ast/`.
  `idc/tools/parity.sh` MATCH on `idc/compiler/parse`, `idc/compiler/lex` and every demo
  across the move.
* **The IR exists** (`back/ir/core/`), the lowering produces alloca form
  (`back/ir/build/`), and the printer emits LLVM IR (`back/tgt/ll/`).
* **62 of 62 conformance cases pass** through `idc/bin/idc --target llvm`, first
  run -- integers, floats, strings, lists, the flat store, `word`, and all five
  traps with their exact messages and exit codes. `idc/tests/conform.sh`'s `llvm`
  target is now this one rather than `idc/idc.py`'s.
* **It compiles the compiler, and the result is a fixpoint.** `idc/bin/idc
  idc/compiler/{lex,parse} --target llvm` builds both stages; the LLVM-built pair
  emits C byte-identical to the C-built pair's, and LLVM IR byte-identical to
  it too.
* **The optimiser runs by default** (`-O1`): predecessors, mem2reg, the
  truth-test fold, dead-code elimination, twice. On the compiler's own source
  it removes **33% of the emitted IR** (33 219 lines to 22 301). `sumto`
  becomes a loop with two phis and no memory traffic at all.

* **It frees what the C target frees.** The lowering asks the same escape
  analysis and emits the same three hooks: a null in each owned local's slot, a
  free of the old value at every store, and a free of every owned slot before
  each return (`back/ir/build/`, docs/MEMORY.md section 4). `tests/conform/free/`
  requires C, LLVM and wasm to free the same number of lists.

Two bugs the fixpoint check found, both worth recording because neither was
visible in a program's *output*:

* **The lowering depended on C's argument evaluation order.** Two calls that
  each emit instructions, written as two arguments of one call, were emitted in
  whichever order the C compiler chose -- so the gcc-built compiler and the
  clang-built one produced different (both correct) IR. Every such site now
  sequences through a local.
* **Two columns of one instruction shared a list.** `ir_leaf` passed the same
  empty list as both the operand list and the block list, and a list is a
  reference, so mem2reg pushed a phi's incoming *value* and read it back as a
  *block*. This is the language's own sharp edge, in the compiler that
  implements it.

### Not done yet

* **Performance is behind the C target.** The `id-llvm` and `id-c` columns of
  `bench/results/results.md` (docs/PERFORMANCE.md) are the current figures.
  Expected at this stage: every
  builtin is still a call into the C runtime, and there is no inlining, no GVN
  and no licm. The store builtins becoming instructions is the first item, and
  it is also what the kernel needs (below).
* **Constant folding is deliberately absent.** `id` specifies that overflow
  wraps, and this compiler is compiled by a C compiler for which signed
  overflow is undefined -- so folding `a * b` would compute it by the rule it
  is meant to implement. It needs the folds routed through `word`.
* **`asm` is not lowered.** `docs/ASM.md` maps it onto `call asm sideeffect`;
  nothing does that yet, and the kernel is what needs it.
* **The runtime is still C.** `--target llvm` asks the compiler for the C
  prelude with external linkage (`--target crt`, once generated from the deleted `idc/idc.py`'s
  `RUNTIME` by `idc/tools/gen_runtime_id.py`) and links it with clang. That file
  exists only until the runtime is written in `id`; see `docs/KERNEL.md`.
* **Native backends** (`--backend`) are C-target only, as they were.
