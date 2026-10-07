# Freeing memory before exit

> **Status: a design, and the slices of it that have landed.** docs/SPEC.md
> section 6 says the compiler frees a list or string it can prove never
> escapes, and keeps anything it cannot prove, and that every target frees the
> same allocations unless a target is systemically unable to. This document
> says how that can be done in this compiler, what it frees today (a local
> list, struct or string that nothing keeps, on every target; the list
> elements of a list of lists that the list provably owns; the temporaries of
> a `+` chain; a block a function returns fresh, by whoever receives it, and
> one passed straight to a function that does not keep it) and which decisions
> are still open. Section 2a lists each target and why any is exempt; section
> 8 lists the forks (F1, shallow or deep, was decided deep on 2026-10-02;
> section 3.2 says how far it goes; F7 and F8 are landed, sections 2 and
> 3.1b).

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
heap block of 16 KB or less comes from a headerless size-class pool (decided
2026-10-06, F4): per-thread free lists carved from 256 KB chunks, a block's
size recovered from a list's `cap` or a string's count word. A larger block is
a `malloc` with a two-pointer header, linked into one list. At exit, and at
`id_thread_leave` for a thread's own pool, whole chunks are freed and the
large-block list is swept; there is no per-block sweep. `id_pool_has(p)`
answers whether an address lies in the pool's span, which is how a later step
tells a heap string from a literal (F2, option d).

- A **string** is a `char*` to NUL-terminated bytes with their byte count in
  the `size_t` just before them (decided 2026-10-02, F2e below). A heap string
  is one `id_alloc` block laid out `[count][bytes][NUL]`, built by
  `id_str_new`/`id_str_from`: the result of `+`, `chr`, `str_of_int`,
  `str_of_mem`, `input`, `read_all`, and now each `argv` element
  (`id_str_of_cstr`). A **literal** is a `static const` object of the same
  layout in the image (`ID_S`), not a block. So a `string` value may or may
  not be a heap block, and nothing in its type says which -- that half of F2
  is unchanged by the layout.
- A **list** is one block: the header (`len`, `cap`, `data`) followed by its
  first cells, `data` pointing at them, so the native ABI is unchanged. Cells
  are 8 bytes whatever the element type; a string cell is a pointer. Growth
  moves the cells to a separate block and leaves the header in place, because
  a list is a reference and every holder must see the same `IdList*`.
- The **flat store** (`alloc`, `peek`, `poke`) is one byte array that only
  grows, bump-allocated, addressed by `word`. It is not the list/string pool
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
   Two more bits describe the *result* of a function that returns a list, a
   struct or a string (section 3.1b): bit 30 is set when it may return a
   block that something else holds, the sign bit when the elements of what it
   returns may be held too. Every bit set (-1) is the answer for anything
   unknown, and is cautious for all three kinds of bit.
2. **Owned locals.** A local of list, struct or string type is *owned* when it
   is declared in the function, is not exported, every store into it is a
   block this function made (a list literal, a constructor, a fresh string, or
   a call of a function whose summary says it returns fresh), and no use of
   it keeps it. The return clause is not a use that keeps: what the clause
   returns is the value the name holds last, which the caller owns.
3. **Frees.** An owned local is freed at every `return` of its function except
   the one the return clause names, and the value it replaces is freed when it
   is assigned again, which is what makes a declaration inside a loop free
   once per pass. The free is shallow (header and cells) unless the list also
   owns its elements (section 3.2), in which case it is `id_list_free_deep`:
   each element is freed as a list, then the list.
4. **Temporaries.** A block that nothing names is freed by the caller: the
   result of a `+` that another `+` consumes (section 3.3), a fresh call
   passed straight to a function whose summary does not keep that parameter
   (`g(f(x))`), and the value of a fresh call used as a statement (`f(x);`).

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
never run the emitter see no freeing). A function that calls itself, directly
or through others, is solved as a whole (fork F7, decided and landed,
`flow/sum/scc/`): it starts from the empty summary (nothing kept, everything
fresh) and its body is summarised again, with every function that waits on it,
until no mask grows. The state is four tables parallel to `fnames` (`esc_pe`
the mask, `esc_st` 0 not started, 1 running, 2 finished but waiting on a
running function, 3 final; `esc_dp` its depth, or the shallowest running
function it waited on; `esc_mem` the waiting ones) and three cells (`esc_fx`:
depth, shallowest running function read in this pass, number of masks that
grew). It is Tarjan's lowlink on the way down and a repetition at the first
function of each cycle on the way back; a function outside any cycle is
summarised exactly once, as before.

Why the fixpoint is sound, and why the two directions are one. Every bit of
every summary is "may": a keeps bit, a second-mask bit, and the two result
bits all turn on when the body does something that could be unsafe, and all
turn on when anything the body reads is unknown. The summary of a body is
monotone in the summaries it reads (a callee with more bits set can only turn
more bits on in the caller). So the least fixpoint, reached by starting every
function in a cycle at "no bit set" and only ever or-ing, is the smallest
mask that is closed under the call graph. For the keeps bits that is the
least fixpoint the question needs: a recursive function keeps a parameter only
if some execution path stores, returns or passes it to something that keeps
it, and every such path is finite. For the result bits it is what the
question needs too, though it reads as "greatest" in the other spelling: a
function that returns the result of calling itself on a smaller input is fresh
if its base cases are, because the call it returns from is a call that
returned fresh by the same argument one level down. A cycle with no base case
never returns, so what it claims about a result is vacuous. An opaque function
(a native, a recorded one, a name that is no function) is final at once with
every bit set, and nothing in a cycle can lower that.

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

Exports (section 3.4), function values and closures (3.5), a struct's fields
(3.5b), the flat store (3.6), the elements of a list of strings or of structs,
and elements that reach a list by name or through a callee (section 3.2).
Strings, return-value ownership and temporaries have landed (sections 3.1b
and 3.3); section 3.2 says which list elements are freed.

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

- **The guard is hosted-only.** The freestanding runtime has no stderr
  (`fail` writes the serial port, then powers off), so a use after a wrong free is not a trap there. It marks
  a freed header (cap -1) so a second free of the same list is ignored until the
  block is reused; that is all.
- **The freestanding runtime owns no string.** Its strings are bump-allocated
  and there is nothing to give back to, so `esc_hosted` is false and no string
  is owned or consumed there. It also gives the old cell array back when a list
  grows, as the hosted `id_realloc` does; that is the runtime's own bookkeeping
  and no analysis is involved.

## 3. What escape analysis has to prove, by kind of value

The general statement is the one SPEC section 6 gives: a value may be freed
when the scope that made it ends if it is never returned, exported, stored in
another list, or kept by a callee. The kinds of value differ in what "a name
for it" can be.

### 3.1 Lists, shallow (landed)

The proof obligations are the three in section 2. The free is shallow because
the elements of a list are separate objects that any other name may share. A
shallow free can never double-free and never frees something somebody else
holds; it leaves the elements to be freed with the pool at exit.

### 3.1b Results: who owns what a function returns (landed, F8)

Decided 2026-10-06 and landed (`flow/sum/fresh/`). A function **returns fresh**
when every path out of it hands back a block that this very call made and
nothing else names. The summary says so in bit 30 (clear is fresh), for every
function whose return type is a list, a struct or a string; for any other
return type the question is not asked. The proof is local to the body, over
what section 2 already computes:

- the return clause is a list literal, or a name this function *owns* (section
  2), where the return clause itself is not counted as a use that keeps it:
  every store into the name is a block this function made, and nothing else
  was given it;
- every early `return` hands back a list literal (any other early return, a
  string literal included, takes freshness away, because the value may be held
  by another name or not be a heap block at all);
- a store of a *call* into the name counts as a block this function made when
  the callee's own bit 30 is clear, and a store of a struct constructor
  always does. Both are the summaries of section 2 read at the call, so the
  fixpoint of section 2 is what makes a recursive builder (`r = build(n - 1)`)
  fresh.

What the caller does with it, which is the whole of the win:

- `ys = f()` makes `ys` an owned local, so every rule of section 2 applies: it
  is freed at the function's exit (unless it is the name the return clause
  returns, whose last value is the caller's own caller's), and the value it
  replaces is freed when it is assigned again. A struct is a list at run
  time, so a local struct from a constructor or a fresh call is owned and
  freed the same way (shallowly: its fields are not followed, section 3.5b).
- `g(f(x))` with `f` fresh and `g` a function of the program whose bit for
  that parameter is clear frees the temporary after the call: the C target
  holds it in a variable of a GNU statement expression
  (`back/tgt/c/emit/prog/code/expr/call/temp_*.id`), the LLVM lowering calls
  the free after the call (`lw_tmp_free`); both ask `esc_tmp_free`. A builtin,
  a native and a constructor keep or are not asked. **Open decision (fork F12):**
  the statement expression is a GNU extension (gcc and clang take it under
  `-std=c11`, `-pedantic` does not), where docs/SPEC.md S11 promises ISO C11
  output. The ISO alternatives are a thread-local stack of pending temporaries
  popped by one runtime helper per result type, or temporaries hoisted to the
  line before the statement the way the sequencer's `idsq_` ones are (not
  possible inside a `while` condition). Neither is built.
- `f(x);` as a statement frees the result (`esc_discard`, `lw_discard`).
- a fresh string is also a fresh operand of `+` (`str_fresh_call`), so
  `f(x) + "a"` builds in the block `f` made.

The second result bit, the sign bit of the summary, says whether the
*elements* of the list of lists returned are the result's alone: it is clear
when the return clause is a list of list literals or a name that is
deep-owned (section 3.2) in the callee. The caller of such a function owns a
deep list (`esc_ndf` is what keeps bit 8 of its walk clear), and frees it with
`id_list_free_deep`. A list of strings or of structs is never deep-owned (the
runtime frees elements as lists), so this bit says nothing for them.

What is *not* fresh, and the cases that pin it (`tests/conform/free/14`): a
function that returns its parameter, one that stores the result in an export
first, one that returns an export, one that returns a string that may be a
literal, one with an early `return xs`. The guard turns a wrong claim of
freshness into a trap at the caller's next use.

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
- **Fresh returns (F8), partly.** Landed for the list itself and for a list of
  lists whose rows are literals (section 3.1b): `xs = f()` is owned, and deep
  when `f` returns its rows as its own. Not landed: a list whose rows reach it
  by name or through a callee (`str_split` pushes its pieces from a helper and,
  for an empty separator, pushes its own argument, so its result is fresh but
  its elements are neither fresh nor the result's alone), and a list of
  strings, which `id_list_free_deep` would free as lists. The pieces of a list
  of strings need their own runtime free (`id_str_free` per cell), a summary
  of "parameter i is stored as an element of parameter j" for the helper, and
  the empty-separator branch to stop pushing its argument. `sorted` in csvq's
  `srt_rows` still keeps elements of `rows` that `rows` still holds.
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

**What landed** (F2 option d, F3 temporaries first, decided 2026-10-06; the
rules are in `escape/own/str/` and the header of `own/str/own.id`). A heap
block is told from a literal by address (`id_pool_has`, section 1), but the
compiler does not need to ask: a local string is *owned* when every store into
it is a string literal (copied to the heap first, `esc_dup`, so every value it
holds is a block of its own) or a fresh string (a `+`, a builtin that makes a
string, and now a call of a function that returns fresh, section 3.1b), and no
use of it keeps it. The old value is freed when a store replaces it, and the
last one at the exit unless the return clause returns it. `s = s + x` with `s`
read once builds in `s`'s own block (`id_concat_f`). The temporaries of a `+`
chain are consumed by the next `+`. A freestanding build owns no string, its
strings being bump-allocated. `tests/conform/free/07` to `12` and `13` to `17`
pin these on C, LLVM and wasm.

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
freed at its function's return and the struct never dangles. A struct local is
owned like a list when every store into it is a constructor or a call of a
function that returns fresh (section 3.1b) and no use of it keeps it, and is
then freed *shallowly*: header and cells, never the fields. So the struct
`bt_make` returns is owned by its caller and the one `bt_check(bt_make(d))`
passes is freed after the call, while the list in its `kids` field and every
node under it stay with the pool. Two cases in
`mid/types/check/store/assign/rule/escape/walk/` pin both rows, and
`idc/tests/tests_feature.sh` runs a program that returns a struct holding a list
the function made, under `ID_FREE_GUARD=1`; `tests/conform/free/16` pins the
struct as owner and temporary. A field-sensitive analysis could free what a
struct holds when the struct dies, which needs the struct to be provably owned
(it is now) and each field to be provably the struct's alone; that is future
work and nothing here decides it.

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
  which is sound because the one name that is returned is left out of the
  frees (`esc_exit`: the name the return clause names is the caller's), and an
  early `return xs` makes `xs` kept, so it is not owned at all. LLVM:
  `lw_ret_val` (the final return clause and an early `return` both go through
  it) calls `lw_free_all`, which loads and frees every owned slot but that one.
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
is exact for lists (a use of a freed header or cell traps) and checked for strings only at a second free (`id_str_free` fills the block with 0xDD and marks the count, so a second free traps and a later read fails the size checks). An AddressSanitizer build
of the emitted C with the guard off is the stricter check for a real free.
The LLVM target links `extern.id`, which carries the same helpers
(`id_list_free`, `id_freed_trap`, `id_null_read` and the checks in the list
accessors), so the guard behaves the same there. `ID_FREE_STATS=1` prints
`id: freed N lists` at exit on both, which is what the parity cases count. The
freestanding runtime has neither (section 2a).

**Bounds and OOM traps.** Unchanged. A freed list in guard mode fails the
existing bounds check; an out-of-memory trap is a different program state
entirely (nothing freed, so nothing to be wrong about). Because traps call
`exit`, the `atexit` hook still runs: it frees whole pool chunks, so a block
freed early back into its free list is released with its chunk and never
twice.

**The length memo.** There is none. It was keyed by address, which made a
string free clear its entry; `id_slen` now reads the count the string carries
(F2e), so freeing a string, when the analysis gets there, has no side table to
keep in step.

**A list that is not heap.** `id_args` holds the strings `id_str_of_cstr` made
from `argv`, which are heap blocks; a string the compiler frees is always a block the function made (an owned string only ever holds heap copies, section 3.3), never one of these and never a literal. Lists are always heap blocks: there is no list literal in
the image (constants are built at startup by `id_list_lit`).

## 6. The pool

Until 2026-10-06 every block carried a two-pointer header and sat on one
linked list that an exit hook walked. Measured on btrees, that header, the
link and the separate cell block were most of the allocator's cost, so F4 was
decided for a headerless size-class pool (section 1). Nothing outlives the
process still holds, at chunk granularity: exit frees every chunk, and a
thread's chunks go when it leaves. A wrong free in guard mode is still safe,
because the guard quarantines instead of returning the block to a free list.
Under ASan a freed block is poisoned, so a read after a free is reported.

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

## 8. Design forks

Each is stated with what it costs and what it buys. Decided: F1 deep
(2026-10-02), F2e strings carry their length (2026-10-02), F5 every target
(2026-09-30), and on 2026-10-06 F2 option (d), F3 temporaries first, F4 the
headerless pool, F7 a call-graph fixpoint, F8 a "returns fresh" bit, and F11
the guard on in test builds and off otherwise with an ASan lane. F7 and F8 are
landed (sections 2 and 3.1b); F12 is landed in its first form and open as a
decision. The rest are open.

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
carries its own length" option `docs/FRICTION.md` (retired; `git show 479234a^:docs/FRICTION.md`) already names).
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

**F7. Summary precision.** *Decided 2026-10-06 and landed:* a fixpoint over the
call graph (section 2, `flow/sum/scc/`), not "keeps everything" inside a cycle.
The cost is the state and the repetition of a cycle's bodies, and being wrong
in the unsafe direction is a missed `or` rather than a missing rule (every bit
only ever turns on). The gain is precision for recursive builders and mutually
recursive walkers (the compiler's own parse/emit recursion).

**F8. Who owns the returned value.** *Decided 2026-10-06 and landed:* a
"returns fresh" bit per function that returns a list, a struct or a string
(section 3.1b), and a second bit for the elements of a list of lists. A caller
owns what it receives (`ys = f()`), frees a fresh block it passes straight to a
function that does not keep it (`g(f(x))`) and one it discards. *Open inside
it:* the pieces of a list of strings (section 3.2), and the fields of a struct
(section 3.5b).

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

**F12. How the C target gives back a temporary argument.** `g(f(x))` needs the
block `f(x)` made held somewhere until `g` returns. (a) A GNU statement
expression (landed): one variable per temporary, the call, the frees, and the
call's value, in `({ ... })`. (b) A thread-local stack of pending temporaries,
pushed as the argument is evaluated and popped, freeing, by one runtime helper
per result type that wraps the call. (c) Temporaries hoisted to the line before
the statement, as the sequencer does for `idsq_`, which cannot reach a `while`
condition. *Trade:* (a) is one expression and no runtime but is not ISO C11,
which SPEC S11 promises; (b) and (c) are ISO C, at the price of a runtime stack
that deep recursion grows, or of a statement-level rewrite with a hole in loop
conditions. The LLVM lowering has no such question: it calls the free after the
call instruction.

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

**Fresh returns (F7, F8).** The figures move with every change to the analysis
and are not written here; these are the commands that produce them, each a
control that differs from the treatment in one property (the compiler):

- *Parity.* `tests/conform.sh free` builds `tests/conform/free/13` to `17` on C,
  LLVM and wasm and requires the same stdout and the same
  `id: freed N lists/strings` from all three, under the guard. `14` is the
  case that must not free (a parameter, an export stored first, an export read
  back): its count is the same before and after, and a wrong claim of
  freshness is a trap there. Against a compiler built from the previous
  `bootstrap/idparse.c` the counts of `13`, `15`, `16` and `17` are zero.
- *Benchmarks.* Build `bench/id/NAME` with the stage compilers pinned
  (`IDC_STAGE_LEX`, `IDC_STAGE_PARSE`) to the old stage 0 and to the new
  stage 1, run each with `taskset -c N` and `/usr/bin/time -f '%e %M'` in
  alternating rounds, and compare the output md5 with `bench/ref/c`. The
  benchmarks that gain are those that build a list in a function and use it in
  another (csv's per-row `str_split`); btrees frees only the root struct of
  each tree, because the nodes under it hang off a field, and strbuild
  frees nothing it did not before.
- *ASan.* `IDC_STAGE_*` as above, `--cc` a one-line wrapper that runs
  `cc -fsanitize=address -fno-omit-frame-pointer -g "$@"`, run with and without
  `ID_FREE_GUARD=1`. The pool poisons a freed block under ASan, so a read of a
  freed list or string is a report, not a guess.
- *Compile time.* `time idc compiler/parse --allow-untested --emit-c F` with
  `IDC_NO_CACHE=1`, a binary of the new source built *by the old stage 0* (so
  both sides are compiled the same way) against the old stage 0 itself; peak
  resident set from `/usr/bin/time -f %M` on the same two. The 4096 MB ceiling
  is the build's own, not the analysis's.
- *Fixpoint.* `tools/regen_bootstrap.sh`, then a build, then
  `tools/regen_bootstrap.sh --check`: the compiler, built with its own
  freeing, emits byte-identical C.

## 10. What is not verified


- ASan has been run on csvq `sort` at 200,000 rows, and on the benchmarks
  btrees, strbuild, expr and csv and on the compiler building itself with the
  analysis of section 3.1b (section 9, "Fresh returns"); not on every case of
  `tests/conform/free/`, which run under the guard. The guard sees a use of the
  list header or cells after the free; it cannot see a stale copy of an
  element pointer into an element freed deep unless the element's own header
  or cells are read.
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
- The cost of the analysis in compile time is measured by `time idc compiler/parse --allow-untested --emit-c F` against a stage 0 built from `git show HEAD:idc/bootstrap/idparse.c` (section 9, "Fresh returns"); the figure is not written here because it moves with every change to the analysis.
- `tests/run.sh` sections that build `demos/` could not run: the private
  workspace has no `demos/`.
