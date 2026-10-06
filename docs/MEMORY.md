# Freeing memory before exit

> **Status: a design, and a first slice of it.** docs/SPEC.md section 6 says the
> compiler frees a list or string it can prove never escapes, and keeps
> anything it cannot prove, and that every target frees the same allocations
> unless a target is systemically unable to. This document says how that can be
> done in this compiler, what the slice frees today (function-local lists on
> every target, and the list elements of a list of lists that the list
> provably owns) and which decisions are still open. Section 2a lists each
> target and why any is exempt; section 8 lists the open forks (F1, shallow or
> deep, was decided deep on 2026-10-02; section 3.2 says how far it goes).

Counts and sizes that change (how many allocations a build makes, how big a
binary is) are not written here. Section 9 gives the commands that produce
them.

## 1. How allocation works today

Every target allocates. Four allocators are different programs (the wasm32-wasi
build is the C one):

**C target, and the LLVM target, which links the same C.** The runtime
prelude is one string in `idc/compiler/parse/back/tgt/c/runtime/prelude.id`
(`extern.id` is the same text with external linkage, which is what the LLVM
target links; docs/LLVM.md, "The runtime"; keep the two in step by hand). Every
heap block goes through
`id_alloc`/`id_realloc`, which prepend a two-pointer header and link the block
into one doubly linked list; an `atexit` hook frees the whole list. So the
process does not leak, and a list the compiler frees is returned early.

- A **string** is a `char*` to NUL-terminated bytes with their byte count in
  the `size_t` just before them (decided 2026-10-02, F2e below). A heap string
  is one `id_alloc` block laid out `[count][bytes][NUL]`, built by
  `id_str_new`/`id_str_from`: the result of `+`, `chr`, `str_of_int`,
  `str_of_mem`, `input`, `read_all`, and now each `argv` element
  (`id_str_of_cstr`). A **literal** is a `static const` object of the same
  layout in the image (`ID_S`), not a block. So a `string` value may or may
  not be a heap block, and nothing in its type says which -- that half of F2
  is unchanged by the layout.
- A **list** is a header (`len`, `cap`, `data`) plus a separate cell array,
  both from `id_alloc`. Cells are 8 bytes whatever the element type; a string
  cell is a pointer. Growth is `id_realloc` of the cell array.
- The **flat store** (`alloc`, `peek`, `poke`) is one byte array that only
  grows, bump-allocated, addressed by `word`. It is not the list/string arena
  and this document does not propose to free it (section 3.6).
- `id_slen` is one load of the stored count. The eight-entry memo it replaced
  was keyed on the **address** of the string, which is why freeing a string
  once had to clear it; a freed string now has nothing stale to forget.

**Freestanding target (`--freestanding`, the kernel).** `idc/runtime/` is
ordinary `id`: `mem_alloc` is a bump pointer in the first words of the arena,
lists and strings are built on it. A string there is the same `[count][bytes]
[NUL]` layout (`lang/str/`, `mem/store/arena/bridge.id`), and the memo that
used to live in the arena is gone.
A bump pointer cannot give a block back, so lists take their header and cells
through size-class free lists (`mem/store/arena/more/pool.id`), whose heads sit
at the front of the arena, after the bump pointer; `list_free`
(`lang/list/more/drop.id`) is the runtime's `id_list_free`. Strings and the
flat store still only bump.

**WASM.** `idc/bin/idc --target wasm` compiles the C target's own C for
wasm32-wasi (wasi-libc has `malloc` and `free`), so it allocates and frees
exactly as the C target does. The Python compiler that once held a WAT
generator with a bump allocator, `idc/idc.py`, is deleted. (docs/BACKENDS.md,
docs/RELIANCES.md and docs/SPEC.md S12 may still say the self-hosted driver has
no wasm target; idc/bin/idc accepts `--target wasm`.)

**Natives.** A `native` function is C the program links. It receives the same
`char*` and `IdList*` and may keep them.

## 2. What the compiler proves today (the slice)

Landed in `idc/compiler/parse/mid/types/check/store/assign/rule/escape/`, one analysis that the C emitter and the LLVM lowering both ask (section 4). Its three directories: `flow/` (`walk/`, the use rules, and `sum/`, the summaries), `own/` (which locals are owned, and the emit hooks) and `deep/` (which owned lists also own their elements, section 3.2):

1. **Parameter summaries.** For every function, one bit per parameter: set when
   the body may keep that parameter past the call. A clear bit is a proof that
   the caller may free what it passed once the call returns. A second mask of
   bits, one per list parameter, says the callee may break the ownership of
   the *elements* of that list (section 3.2). Both masks are 15 bits wide;
   a function with more than fifteen parameters keeps and breaks everything.
2. **Owned locals.** A local of list type is *owned* when it is declared in the
   function, is not exported, every store into it is a list literal, and no
   use of it keeps it.
3. **Frees.** An owned local is freed at every `return` of its function, and
   the value it replaces is freed when it is assigned again, which is what
   makes a declaration inside a loop free once per pass. The free is shallow
   (header and cells) unless the list also owns its elements (section 3.2),
   in which case it is `id_list_free_deep`: each element is freed as a list,
   then the list.

The use rules are a default-deny table (`flow/walk/`): a use of `xs` is harmless only
in these positions, and anywhere else it is treated as keeping the list.

| position | keeps `xs`? |
| --- | --- |
| operand of an operator, an index base or index, a condition, an expression statement | no |
| argument to a builtin, except the value argument of `push` | no |
| argument to an id function, at parameter `i` | bit `i` of its summary |
| argument to a native, an `asm` function, a call through a function value, a function a `calls` clause records | yes |
| element of a list literal, value of `ys[i] = v`, value argument of `push` | yes |
| right of `=`, or of a declaration (an alias), an export's value | yes |
| `return xs`, the return clause | yes |

Four more positions decide whether `xs` also owns its **elements** (section
3.2). They never make `xs` itself kept; they only withhold the deep free:

| position | breaks the ownership of the elements of `xs`? |
| --- | --- |
| `xs[i]` read into a keeping position (a store, a return, an argument the callee keeps, an alias) | yes |
| `xs[i]` read and only looked at (an operand, `len(xs[i])`, `xs[i][j]`, an argument the callee does not keep) | no |
| `push(xs, v)` or `xs[i] = v` where `v` is not a list literal; a list literal `[a, b]` stored in `xs` with an element that is not a list literal | yes |
| `xs` passed to an id function at parameter `i` whose second-mask bit is set | yes |

Summaries are computed on demand and memoised in `esc_pe` (seeded at C emission;
an empty table means the analysis is off, which is how the test cases that
never run the emitter see no freeing). While a function is being summarised
its row holds "keeps everything", so recursion is sound and is imprecise only
inside the cycle. A fixpoint over the call graph would be more precise (fork
F7).

Two rules in the table exist for a reason that is easy to miss:

- **A `calls` clause keeps its arguments.** The harness's recorder
  (`test/unit/more/rec/`) stores the arguments of every recorded call by
  pointer, for up to 65536 calls per function, and compares them after the call
  returns (`docs/TESTS.md`: "list arguments show their final state"). A caller
  that freed a local it had passed to a recorded function would leave the
  recorder holding a dangling list. So a recorded function's parameters are
  treated as kept at every call site. This is the one place where the test
  harness changes what is provable, and it is the general shape of the harness
  problem: the harness is a caller that keeps values, so it must be a
  *consumer in the analysis*, not an afterthought.
- **A `native` keeps everything.** idstd's natives are C. Their bodies are not
  visible, and a list-consuming native (a buffer it retains) is possible.

### What the slice does not do

Strings, return-value ownership, exports, and temporaries (section 3.2 says
which list elements are freed). Each is a section below.

### 2a. Which targets free what

The rule (docs/SPEC.md section 6): every target frees the same allocations,
unless a target is systemically unable to. "The same" is checked, not assumed:
`idc/tests/conform/free/` builds each program on C, LLVM and wasm, runs it with
`ID_FREE_STATS=1` (the runtime prints `id: freed N lists` at exit) and requires
the same N from all three, with `ID_FREE_GUARD=1` so a wrong free is a trap.

| target | frees lists | why not, if not |
| --- | --- | --- |
| C | yes | |
| LLVM, hosted | yes | |
| `idc/bin/idc --target wasm` | yes | it is the C output recompiled, so it frees as C does |
| freestanding (`--freestanding`, `--runtime`) | yes | |

No target is systemically unable to free a list. The elements of a deep-owned
list (section 3.2) are freed by every target the same way: the C runtime and
`extern.id` have `id_list_free_deep`, the LLVM lowering calls it for the same
locals (`lw_drop` asks `esc_free_fn`, which the C emitter asks too), `--target
wasm` is the C one, and the freestanding runtime has `list_free_deep`
(`idc/runtime/lang/list/more/init.id`). Each frees every element as a list and
then the list, so the count in `ID_FREE_STATS` is the same on all of them
(`tests/conform/free/04` to `06`). Two differences remain that are not about
which lists are freed:

- **The guard is hosted-only.** The freestanding runtime has no stderr and
  nothing to exit to, so a use after a wrong free is not a trap there. It marks
  a freed header (cap -1) so a second free of the same list is ignored until the
  block is reused; that is all.
- **Strings are not freed on any target.** The freestanding runtime also gives
  the old cell array back when a list grows, as the hosted `id_realloc` does;
  that is the runtime's own bookkeeping and no analysis is involved.

## 3. What escape analysis has to prove, by kind of value

The general statement is the one SPEC section 6 gives: a value may be freed
when the scope that made it ends if it is never returned, exported, stored in
another list, or kept by a callee. The kinds of value differ in what "a name
for it" can be.

### 3.1 Lists, shallow (landed)

The proof obligations are the three in section 2. The free is shallow because
the elements of a list are separate objects that any other name may share. A
shallow free can never double-free and never frees something somebody else
holds; it leaves the elements to the arena.

### 3.2 Lists, deep (landed for list elements, in the narrow form)

Decided 2026-10-02 (F1: deep). To free the elements too, the analysis must
prove the list **owns** them: each element was built for this list, no other
name, list, export or return value holds it, and it was not read out into a
keeping position. Two things make that harder than section 3.1:

- Reading an element (`xs[i]`) mints a new name for it. The read must be in a
  non-keeping position, and so must every later use of what the read produced.
  That is a flow question about a *different* value, so the analysis needs
  value-level facts ("this name holds an element of `xs`"), not just
  name-level ones.
- The elements are frequently aliases by construction: `push(rows, row)` stores
  a list some other name also holds. Ownership has to be transferred, not
  assumed.

**What landed** (`escape/deep/`, hooks in `own/free/`, the runtime on every
target). A local `xs` whose declared type is a list of lists (`int[][]`,
`string[][]`, `Point[][]`, deeper too, but only the outer elements count) is
*deep-owned* when all of these hold:

1. it is owned in the shallow sense (section 2);
2. every element that goes into it is a **list literal**: the literals of a
   declaration or assignment `xs = [[1], []]`, the value of `push(xs, [..])`
   and of `xs[i] = [..]`. A literal is a fresh block that nothing else holds
   yet, which is the whole of "built for this list". A name or a call's result
   is not (flag bit 8 of the walk);
3. no element is read out into a position that keeps it (flag bit 4): a store,
   a return, an alias `row = xs[i]`, an argument whose callee keeps it;
4. `xs` is passed only to callees that do neither of the above to *their*
   parameter (the second summary mask, section 2).

Then `xs` is freed with `id_list_free_deep`: each cell is freed as a list
(shallowly), then `xs`. The elements' own elements are not touched: a
`string[][]` frees its row lists and leaves every string, and an `int[][][]`
frees the middle lists and leaves the innermost.

Why this is sound without tracking flow. Elements can be read only in
positions that look at them and let go within the statement, so no name for an
element outlives the statement that read it; and nothing stores into the list a
block someone else can reach. So there is no stale alias to find, and a free at
a function exit, or when the declaration runs again, cannot dangle. The price
is that an alias `row = xs[i]` is refused even when `row` itself never escapes.

**What did not land, and why each is a separate step.**

- **Moves.** `row = []; ...; push(rows, row)` stores a name, so `rows` is not
  deep-owned. Allowing it needs a transfer rule: `row` must be a local
  declared with one literal, moved once per execution of that declaration (not
  from inside a loop that outlives it), and never read after the move while
  `rows` could have been freed. That is flow facts about a different value
  (the first bullet above). It is the idiom csvq's parser uses, and one reason
  deep frees do not reach csvq (section 9).
- **Moves through a callee.** `csv_keep(st, rows, ..., row, ...)` stores its
  parameter into another parameter. A summary of "parameter i is stored as an
  element of parameter j" would let the caller check the actual for `i`.
- **Fresh returns (F8).** `xs = f()` is not owned, so a list of lists a
  function returns is never freed by its caller, and `sorted` in csvq's
  `srt_rows` keeps elements of `rows` that `rows` still holds.
- **The replaced element.** `xs[i] = [..]` leaves the element it replaced
  unfreed, because nothing proves no alias took it first; with the alias rule
  above it could be freed.
- **Struct elements.** A list of structs holds structs, and a struct's fields
  are not followed (section 3.5b); a `Point[]` is not a deep candidate.

### 3.3 Strings

Immutable, so aliasing is harmless to *correctness*; it only matters to *when*
the block may be released. Two extra facts are needed that lists do not need:

- **Is it a heap block at all?** A literal and an `argv` element are not. A
  free of one is undefined behaviour. The analysis must prove a string fresh
  on **every** path that reaches the free, and the dominant idiom defeats that:
  `string s = ""; ... s = s + x;` is a literal on the path where the loop does
  not run (fork F2).
- **The length memo.** Gone: the length is in the string (F2e), so a free
  has nothing to clear.

`a + b + c` also makes a temporary per `+`; the inner result has exactly one
reader and is provably dead after the outer `+`. That is the cheapest string
proof there is (an unnamed value consumed once by a builtin that copies), and
it is independent of everything else (fork F3 asks whether to do it first).

### 3.4 Exports and imports

`docs/PROJECT.md` section 4: an `export` is an assignment to a global from
its declaring function, and `(import x)` reads it. Two properties help: the
set of *writers* of an export is exactly one function, and the set of
*readers* is every `(import x)` expression in the program, all visible to the
compiler, because there are no pointers to globals and `(import x)[i] = v` is
rejected.

What that buys: when the declaring function runs again, the old value is dead
**if** no reader ever let it escape. The kv trial ("can never reclaim
superseded values") is this case. The proof is whole-program: every
`(import x)` read must be in a non-keeping position (same table as section 2),
and every read that binds a name must have that name's own uses checked. One
read that stores the imported list in another list, returns it, or passes it
to a keeping callee makes the old value live. A `conf.id` constant is locked
and never freed.

What it does not buy: the declaring function may run many times and in any
order; "the old value" is whatever the last run stored. The free is a free of
the previous contents of the global at the export statement, which is exactly
the free-the-replaced-value rule the slice already emits for locals.

### 3.5 Function values

A function value is a named top-level function (SPEC section 1.1) or a closure
`bind` makes from one (SPEC section 1.1.1): a **partial application that copies
what it fixes**, so a closure captures no variable of the function that made it.
That keeps the hardest part of the problem out: there is no environment that
can point into a frame, and nothing a closure holds is shared with a name that
can change it. What remains is a call through a value: the callee is unknown at
the call site. Because a function value can only be a name, or a `bind` of one,
written at a line the compiler can find, the set of functions a given function
*type* can denote is finite and known. A call through a value can therefore use
the **meet of those functions' summaries** instead of "keeps everything", which
the slice uses today (fork F6 asks whether to do the meet).

**What a closure owns, and who frees it.** A closure is one runtime block
(`id_clo_new`: a header and the captured cells), and each list it captured is a
copy the runtime made (`id_clo_copy`: a new list of the same cells, locked with
`id_list_lock`, so a write to it is the trap `id: cannot mutate a constant
list`). Strings and function values are shared, because they are immutable. All
of these are ordinary allocator blocks, so they are released with the rest at
exit; **none is freed earlier in this slice**. The analysis needs no new row
for them:

| position | keeps `xs`? |
| --- | --- |
| a list passed as a value of `bind` | no: `bind` copies it, and `bind` is a builtin, which the table already treats as not keeping |
| a closure local or parameter | it is not a list, so it is neither owned nor freed |
| a call through a closure | the same row as a call through any function value: keeps its arguments |

What it would take to free a closure's blocks early is the same thing it takes
for a string (section 3.3): proving the value fresh and dead. A closure is the
easier case, because it is built in one expression whose every part is a fresh
block the closure alone holds (`id_clo_copy` is a fresh list), so a local that
is assigned only from `bind`, and is never returned, exported or passed to a
callee that keeps it, could free the object and each copied list at its
function's exit. That is not built, and nothing above depends on it. A closure
that is stored in an export, or handed to `thr_map`'s worker threads, is never
a candidate.

### 3.5b Structs

A struct (SPEC section 1.2) is a list at run time, one cell per field, so it is
a reference that can hold lists and strings. The analysis is **not
field-sensitive**: a list stored in a field is treated as kept, always, until
someone proves otherwise per field. Both ways a list gets into a struct already
land on a "keeps" row of the table in section 2: the constructor `Point(xs)` is
a call to a name that is no function of the program, which "keeps everything"
(`esc_opaque`), and `p.f = xs;` is an index assignment, whose value is kept. A
local list that went into a struct is therefore never *owned*, so it is never
freed at its function's return and the struct never dangles; and a struct local
is not a list, so it is not freed at all in this slice. Two cases in
`mid/types/check/store/assign/rule/escape/walk/` pin both rows, and
`idc/tests/tests_feature.sh` runs a program that returns a struct holding a list
the function made, under `ID_FREE_GUARD=1`. A field-sensitive analysis could
free a list a struct holds when the struct dies, which needs the struct to be
provably owned first; that is future work and nothing here decides it.

### 3.6 Words and the flat store

`word` is an integer. A `word` can hold an address in the flat store, and the
store can hold anything `poke` puts there. Nothing in the type system says what
a `word` refers to, so a store block is not freeable by escape analysis and this
document proposes nothing for it. The `s2w`/`w2s`/`l2w`/`w2l` casts that turn a
string or list into a `word` exist only in the freestanding runtime's `asm`
layer (`docs/KERNEL.md`); any program that used them on a value would have to be
treated as keeping it. The C runtime does not expose them to id code.

### 3.7 Values captured by harness cases

Covered in section 2 for `calls` clauses. The rest of the harness is unproblematic:
the arguments of a case are built by the harness and owned by it, and a callee
never frees a parameter; `given` setups run ordinary functions; `then` checks
compare values after the call.

## 4. Where frees are inserted

Not in the analysis. The analysis (mid) answers `owned?` for a name in a
function and `keeps?` for a parameter of a function; a backend asks those and
emits. On the C target (the LLVM lowering, `back/ir/build/`, does the same
things at the same places; each C bullet is followed by where LLVM does it):

- **Function exit.** Before every `return`, the final one and each early one.
  The return value is a name or a literal (SPEC 7.1), computed after the frees,
  which is sound because an owned list is never the value returned. LLVM:
  `lw_ret_val` (the final return clause and an early `return` both go through
  it) calls `lw_free_all`, which loads and frees every owned slot.
- **Before overwrite.** When an owned name is assigned, the old value is freed
  *after* the new one is computed (the new value's expression may read the old
  list). LLVM: `lw_store_at` loads the old value of an owned slot before the
  store and frees it after (`lw_old`, `lw_drop`).
- **The declaration.** Locals are hoisted (`id` is function-scoped), so an owned
  local is declared `= NULL` and `id_list_free(NULL)` is a no-op; a branch that
  never runs the declaration frees nothing. LLVM: `lw_alloca_tail` stores a null
  into each owned slot in the entry block (`lw_own_init`); a name declared in
  two arms of an `if` has two slots and only the one `lw_slot` resolves, which
  is the one the lowering reads and writes, is loaded.
- **Which free.** Every place above that frees a name asks `esc_free_fn(fn,
  nm)` (`escape/deep/own.id`) for the runtime function to call:
  `id_list_free` or, for a deep-owned list, `id_list_free_deep`. LLVM: `lw_drop`
  takes the slot's name for it. A backend that frees must ask, or it frees
  fewer allocations than the others and the parity cases notice.
- **Which function.** The analysis asks `esc_cur()`, which reads `sqbase[0]`.
  The C emitter sets it in `emit_def`; the LLVM lowering sets it with
  `esc_enter` in `lw_func_tail`, and `ir_lower` seeds the summaries with
  `esc_seed` as `def_all` does.
- **Not at scope end.** `id` has no block scope: a declaration inside an `if`
  or `while` is visible to the rest of the function, so there is no earlier
  "scope end" to free at, and freeing at the next write is the earliest point
  that is always safe.

**What the structure makes cheap.** Functions are tiny (a block holds 3
actions, nesting is 2 deep) and control flow is structured, so a walk over a
function's body is one pass and needs no CFG. There are at most two loops
deep, no `goto`, no exceptions, and every exit is an explicit `return`, so
"every exit" is a syntactic fact. The cost of this is that precision comes from
summaries, not from flow sensitivity: a helper that takes a list and pushes onto
it is the normal shape, so the interprocedural part is where the value is.

## 5. Memory safety

**No use after free.** That is the contract: a free is emitted only for a name
that section 2 proved is referenced by nothing else. The proof is conservative
everywhere it can be: default-deny use table, unknown callees keep, recursion
keeps, natives keep, recorded functions keep.

**The guard.** A proof can still be wrong. `ID_FREE_GUARD=1` in the environment
(and always in a test harness) makes `id_list_free` quarantine instead of
release: the cells are filled with `0xDD`, the header is marked freed (`len`
-1, `cap` INT_MIN), and the block stays linked so it is released at exit and
never reused. A later use traps with

    id: use of a freed list (the compiler's escape analysis freed a list that was still reachable)

and exits 1 like every other trap (SPEC section 8). The checks are in the cold
paths of the existing trap branches plus one test in `id_list_len`.
Freeing the same list twice traps the same way. `id_list_free_deep` frees each
element through `id_list_free`, so an element is quarantined and trapped on
the same terms as a list: a read of an element after a wrong deep free is the
trap above, and so is a deep free of an element a shallow free already
released. (`tests/conform/free/05-deep-refused` is built so that each way an
element can escape is read by the caller after the function returns; editing
the emitted C of any one of its four functions to free deep traps.) The guard
is best-effort for strings (none are freed yet) and exact for lists. An AddressSanitizer build
of the emitted C with the guard off is the stricter check for a real free.
The LLVM target links `extern.id`, which carries the same helpers
(`id_list_free`, `id_freed_trap`, `id_null_read` and the checks in the list
accessors), so the guard behaves the same there. `ID_FREE_STATS=1` prints
`id: freed N lists` at exit on both, which is what the parity cases count. The
freestanding runtime has neither (section 2a).

**Bounds and OOM traps.** Unchanged. A freed list in guard mode fails the
existing bounds check; an out-of-memory trap is a different program state
entirely (nothing freed, so nothing to be wrong about). Because traps call
`exit`, the `atexit` arena sweep still runs, and it frees blocks that are still
linked: `id_list_free` unlinks what it frees, so the sweep never frees twice.

**The length memo.** There is none. It was keyed by address, which made a
string free clear its entry; `id_slen` now reads the count the string carries
(F2e), so freeing a string, when the analysis gets there, has no side table to
keep in step.

**A list that is not heap.** `id_args` holds the strings `id_str_of_cstr` made
from `argv`, which are heap blocks. The slice never frees a string. Lists are always heap blocks: there is no list literal in
the image (constants are built at startup by `id_list_lit`).

## 6. The arena

The arena is one linked list of blocks. The slice leaves it in place: a freed
block is unlinked and handed to `free()`, so the exit sweep sees only what
was never freed. This keeps the exit-time guarantee ("nothing outlives the
process") and is what makes a wrong free in guard mode safe (the block stays
linked and the sweep frees it once).

The arena as a *design* is what limits the next steps. It stores no sizes, so
poisoning a string needs the length, and it cannot be compacted or
region-reset. If regions ever become useful (fork F4), the place to put one is
here.

## 7. What `id`'s rules make easy, and where they do not

| rule | what it gives | where it stops |
| --- | --- | --- |
| Single-owner exports, `(import x)[i] = v` rejected | the readers of an export are a syntactic set; the writer is one function | the *values* read are ordinary lists, and a read that binds a name needs the whole section 2 check on that name |
| Function values are named functions, or a `bind` of one that copies what it holds (SPEC 1.1.1) | a call through a value captures no variable; the candidate set is finite | the call site still has to use the set (F6), and a closure's blocks are not freed early (section 3.5) |
| 3 actions per block, nesting 2, structured control | a function body is one walk; every exit is syntactic | precision is interprocedural, not local |
| One type per name per unit | a name identifies a variable in a function; no alias by shadowing | the same name in two functions are two variables, so summaries are keyed by function |
| Return clause is a name or a literal | the returned value is always a name; `return xs` is one syntactic form | none |
| Duplicate-logic and two-case rules | every new function is small and tested | the test-writing cost of an analysis is most of its cost (section 9) |
| Lists have reference semantics | aliases exist only through names, assignments and parameters, all visible | *any* alias of a list is indistinguishable from the original, so the use table must be default-deny |
| Strings are immutable | aliasing cannot corrupt | a free is still a free; F2, F3 |

The properties that do **not** hold: lists can be elements of lists (so
ownership is not a tree until someone proves it), `(import x)` returns a list
not a copy, natives and `asm` are opaque, and a `word` is an address that may
alias anything in the store.

## 8. Open design forks

Nothing below is decided. Each is stated with what it costs and what it buys.

**F1. Shallow or deep frees.** Shallow (landed) frees header and cells of an
owned list and leaves the elements. Deep also frees elements that the list owns.
Deep needs value-level ownership (section 3.2) and is what reclaims `parts` in
`wr_quote`, the split pieces, and `rows` in the csvq `sort` (which is most of
the live floor). Shallow is provable with the machinery in this slice; deep needs
a second analysis (who else holds this element?) and changes what a list of
lists means to the optimiser. *Trade:* shallow is complete-for-what-it-does and
small; deep is where the large memory wins are and where a wrong proof frees
live data. **Decided 2026-10-02: deep.** What landed is the narrow form of
section 3.2 (list elements built by literal, no name for them read out); it
changes nothing in csvq's `sort` (section 9), because `rows` there is filled
by a callee storing a name and `sorted` aliases its elements, so what reaches
the big floor is moves, summaries of stores into a parameter, and F8, not the
free itself.

**F2. Literal or heap.** A string may be a literal or an `argv` pointer. Options:
(a) prove freshness on every path (sound, defeated by `""` initialisers);
(b) rewrite initialisers so a fresh-or-literal local starts from a heap `""`
(changes allocation counts, costs one allocation per call);
(c) tag blocks so `id_free` can refuse a pointer that is not one (reads before a
literal, which is undefined behaviour unless the runtime owns the address
range);
(d) allocate all strings from ranges the runtime owns so membership is a range
test (changes the arena);
(e) represent strings as `(ptr,len)` with a bit for "owned" (the "string that
carries its own length" option `docs/FRICTION.md` already names).
*Trade:* (a) is free and weak; (e) fixes the length memo, the literal question
and the `strlen` cost together and is a language-level change; (b)-(d) are
runtime-only.

**F2e. Decided 2026-10-02: strings carry their length** (the user merged
length-prefixed strings). The count sits in the word before the bytes, the
bytes stay NUL-terminated, and the eight-entry memo is removed. What that
settles and what it does not:
- Settled: the memo, and the `strlen` cost of `len`, `concat` and `charat`.
  Every producer writes the count (`id_str_new`/`id_str_from`; `ID_S` and
  `ID_SK` for literals; `id_str_of_cstr` for `argv` and for a wasm host; the
  LLVM module's `{i64, [n x i8]}` literals and the freestanding runtime's own
  builders), so no consumer measures.
- Not settled: whether a string is a heap block. A literal is still a static
  object, so the "is it a heap block at all?" question of F2 stands. The
  count is not an ownership bit; F2's "owned" bit was not added.
- NUL: a NUL still never enters a string. `chr(0)`, `str_of_mem`, `input` and
  `read_all` trap rather than truncate, as before. A literal's `\0` escape
  still ends the literal there, on every target, because the stored count is
  the length up to it.

**F3. Order: temporaries first or named locals first.** Freeing an unnamed
temporary consumed by a copying builtin (`a + b + c`, `chr(c)` inside `+`) is
provable with no summaries and no flow. Freeing named locals needs the
summaries. *Trade:* temporaries are a smaller win but land without the
interprocedural machinery; named locals are where the csvq sort wins.

**F4. Free list or regions.** The slice calls `free()` per block. Alternatives:
per-function regions (release everything a function allocated and did not
return), which ignore ownership of individual blocks but need "did not
escape" for the *set*; or a size-class free list in the runtime instead of
`malloc`. *Trade:* regions are the cheapest at run time and the least
precise; the free-list is what the freestanding target needs anyway (no
`free()`).

**F5. Every target. Decided 2026-09-30: every target frees the same
allocations unless it is systemically unable to.** The options were (a) land
the C target and document the drift, (b) one runtime-independent representation
every backend reads, (c) restrict the promise to targets whose allocator can
free. The decision is the promise, with an exception only for a target that
cannot. Applying it (section 2a): LLVM and the freestanding runtime were "not
done", not unable, and now free; `--target wasm` in `idc/bin/idc` already did
because it is C; the WAT generator in `idc.py`, the one exception, is deleted.
The analysis stays target-independent and each backend emits the three
hooks of section 4 itself; there is no shared table, so a fourth backend has to
repeat them, and `conform/free/` is what notices if one does not.

**F6. Calls through function values.** Keep everything (today), or use the meet of
the summaries of every function of that type that occurs as a value. *Trade:*
keep-everything is always sound and costs precision only where id code calls
through a value; the meet is small and
depends on the list of "functions named as values", which the compiler already
collects for reachability.

**F7. Summary precision.** On-demand memoised with "keeps everything" inside a
cycle (today) versus a fixpoint over the call graph. *Trade:* the fixpoint
recovers precision for mutually recursive walkers (the compiler's own
parse/emit recursion); the on-demand form is half the code and cannot be wrong
in the unsafe direction.

**F8. Who owns the returned value.** A function that returns a fresh list (a
constructor like `str_split`) hands the caller an owned value. Recording that
("returns fresh") lets the caller own what it receives, which is what frees
`parts` in `wr_quote`. It needs a `return`-path proof and the literal/heap
answer of F2 for strings. *Trade:* biggest remaining win for lists after F1;
requires each function's "every return returns a fresh block" summary and a
second bit per function.

**F9. Natives.** Keep everything (today). Alternatives: a declaration form that
says which parameters a native keeps (syntax, which SPEC section 6 rules out for the
freeing itself, but not obviously for the contract of foreign code), or an
audit of idstd's natives recorded in one place. *Trade:* today's answer makes
any list passed to an fs or gfx native immortal; any other answer adds a
contract someone has to keep true.

**F10. The harness and memory.** The harness is a caller that keeps values. The
slice makes recorded functions' parameters kept. The alternative is to have the
recorder copy the arguments it keeps. *Trade:* copying makes the harness safe
against any future analysis and costs memory and a deep-copy rule for lists of
lists; the `calls`-keeps rule is one line and only ever makes the analysis more
conservative.

**F11. Guard default.** The guard is on in harness builds and opt-in by
environment variable elsewhere. The alternative is a release build that keeps
the guard on (quarantine instead of free), which gives up the memory win.
*Trade:* none for the harness; for shipped programs it is the question of
whether a wrong proof is a trap or corruption. On the freestanding target the
question is already answered, as corruption, because there is nowhere to trap
to.

## 9. Measurements and verification

Commands assume the private workspace layout (`idstd` next to `id_development`)
and `IDSTD_HOME` exported.

**csvq sort, 1,000,000 rows, peak resident set.** Program: the csvq trial.
Input: `csvq gen 1000000`. Command: `csvq sort name FILE`.

| build | peak RSS | time | stdout md5 |
| --- | ---: | ---: | --- |
| before (no frees) | 1,127,124 KB | 4.0 s | f8040cf68b902fc9f192f399600633e7 |
| after (this slice) | 814,436 KB | 3.8 s | f8040cf68b902fc9f192f399600633e7 |

Both targets, same input, same machine, rerun 2026-09-30 with
`ID_FREE_STATS=1` for the count. "Before" is the same binary run with
`ID_FREE_GUARD=1`, which quarantines every free instead of releasing it, so the
only variable is the release:

| target | frees released | peak RSS | time | lists freed | stdout md5 |
| --- | --- | ---: | ---: | ---: | --- |
| C | no (guard) | 1,128,032 KB | 4.01 s | 2,575,553 | f8040cf68b902fc9f192f399600633e7 |
| C | yes | 814,176 KB | 3.89 s | 2,575,553 | f8040cf68b902fc9f192f399600633e7 |
| LLVM | no (guard) | 1,127,692 KB | 4.44 s | 2,575,553 | f8040cf68b902fc9f192f399600633e7 |
| LLVM | yes | 814,284 KB | 4.35 s | 2,575,553 | f8040cf68b902fc9f192f399600633e7 |

The two targets free the same number of lists and land within 0.02% of each
other. `csvq count` on the LLVM build peaks at 432,844 KB, the same floor.

**With deep frees (2026-10-02).** The same four rows were rerun with the
compiler that has section 3.2: C without frees 1,127,328 KB, C with 814,176
KB, LLVM without 1,127,756 KB, LLVM with 814,220 KB; 2,575,553 lists freed on
both; stdout md5 unchanged; `csvq count` 432,800 KB. Nothing moved, and the
reason is in the emitted C, not in the measurement: `grep -c
'id_list_free_deep('` over csvq's C finds no call, because csvq builds its
lists of lists by passing a name to a callee that stores it (`csv_keep`), and
`sorted` in `srt_rows` holds elements `rows` holds. Peak RSS is the live data
at the moment of the sort, which no free can lower; the saving available there
is the garbage made *on top of* it (section 9, the instrumented run), and that
is `parts` and the like (F8), not the elements of a list of lists.

**The compiler building itself.** Peak RSS of the stage-1 build of
`compiler/parse` (`IDC_STAGE_PARSE` pinned to the original `bootstrap/idparse.c`
built with `cc`, against the regenerated one): 2,804,588 KB and 2,805,124 KB.
The regenerated `bootstrap/idparse.c` contains no call of
`id_list_free_deep` in any function body: the compiler has no list of lists the
deep rule accepts, so it frees nothing there either.

The table above these two is the original C measurement, taken when the slice
landed: a 28% reduction with identical output. The floor is the live data:
`csvq count` on the same file peaks at 432,852 KB, so the slice removed
about 45% of the garbage the sort made on top of it. Hand-freeing the one
remaining list the slice cannot prove (`parts` in `wr_quote`, returned fresh by
`str_split`: F8) brings the same program to 751,596 KB, which is the size
of the win F8 is worth on this program.

What the garbage is, from an instrumented run (200,000 rows, allocation sites
counted by caller): the output phase builds `parts` in `wr_row`, `bs` in
`str_join_blit` and a split list in `wr_quote` per row or field; the first two
are what the slice frees.

**Test coverage of the analysis.** Every function has two or more cases. A
cases-only check is weak (section 10), so mutations were applied by hand (several
at a time) and each turned a case red (`r = ctx` to `r = 1`, `push` argument
index, the freshness test, the bit extraction, the duplicate-free guard,
the `= NULL` initialiser); two survived until cases were added for them
(the `else` arm of a nested declaration, and the `calls` clause rule).

**The guard.** `ID_FREE_GUARD=1` on the csvq commands `sort`, `select`,
`filter`, `stats`, `head`, `count` gives output identical to the unfreed
build. A `return` edited by hand to read a list after freeing it is silent without the guard and traps with it (exit 1, the message in section 5); compiled with `-fsanitize=address` the same edit is a heap-use-after-free, and the unedited csvq `sort` on 200,000 rows is clean under ASan with the same output as the unfreed build. The compiler itself, built with its own analysis, was run under the
guard over the whole `compiler/parse` tree and its cases: emitted C identical,
no trap.

## 10. What is not verified


- ASan ran on csvq `sort` at 200,000 rows only, not on the compiler or the
  cases. The guard sees a use of the list header or cells after the free; it
  cannot see a stale copy of an element pointer into an element freed deep
  unless the element's own header or cells are read; the cases in
  `tests/conform/free/` run under the guard, ASan was not run on them.
- The deep rule (section 3.2) is argued, not proved: its soundness rests on
  "an element is read only in positions that look and let go". Cases exist for
  each escape the analysis names (`conform/free/05-deep-refused`, one function
  per way) and each was made to trap by editing the emitted C to free deep; no
  case exists for a way nobody thought of. Elements reached through a struct
  field or an `asm`/native function are covered only by those being "keeps
  everything".
- Deep frees reach no real program in this repository that was measured: not
  csvq's `sort`, not the compiler building itself (section 9). Their effect on
  memory is shown only by the `kfree` fixture on the freestanding target and
  the conformance counts.
- `tests/fixtures/kfree` (the deep list in `probe_freed`) and the
  freestanding `list_free_deep` were run by the steps recorded in the report
  of 2026-10-02, not by a full `tests/kernel.sh`.
- `extern.id` and `prelude.id` are two hand-kept copies of one text. They had
  drifted (extern had no `id_null_read`, no free helpers, no freed-list
  checks) and now agree on the list runtime, checked by reading a diff of the
  two outputs, not by a test. Nothing fails if they drift again.
- The LLVM lowering's unit cases test each hook on a hand-built function
  (`lwo_fixture`); the programs in `tests/conform/free/` and csvq are what test
  the lowering end to end, and they are three programs and one trial.
- The freestanding free lists were exercised by `tests/fixtures/kfree` (the
  arena stops growing for freed lists, still grows for kept ones, the sums are
  right) and by booting the kernel and typing at its shell. `tests/kernel.sh`
  runs the first; it was not run as a whole here because the private workspace
  has no `kernel/` and `tools/qmon` takes longer than a minute to build.
  The new block of kernel.sh was run on its own against a copy of the kernel's
  boot files.
- The freestanding guard against a list freed twice is a cap of -1 on the
  header; it cannot tell a second free from a free of a block already reused.
- Falsification was done by hand, in batches, against the analysis's own
  cases; the emission hooks were exercised by the csvq and self-build runs.
- Cases that build the fixture AST with `given esc_fix` test the analysis on
  three hand-built functions. They do not test the analysis on code the
  parser would produce from text.
- The cost of the analysis in compile time was not measured.
- `tests/run.sh` sections that build `demos/` could not run: the private
  workspace has no `demos/`.
