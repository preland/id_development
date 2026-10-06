# Threads for `id`

> **Status: a design with a first slice built.** Sections 1 to 3 are the audit of
> what in the runtime is shared, the four options, and a recommendation; they are
> the user's to decide, and nothing in them is implemented beyond section 4.
> Section 4 is a prototype that needs no syntax change: the C runtime keeps its
> mutable state per thread, and idstd's `thr_map` runs a pure `func(int) return
> int` over `0..n-1` on several OS threads. Section 5 lists what must still
> change before it is safe by construction rather than by convention. Numbers
> that change (timings, counts) are in section 6 with the commands that produce
> them; do not copy them elsewhere.

Why now (`PLATFORM_ROADMAP.md` section 4, ranks 2 and 3): an audio real-time
thread, video decode beside the UI, a compositor's input/render split and
parallel compute (builds, image work) all need more than one thread, and `id`
has none. Threads touch every promise the language makes: memory safety,
determinability (prescriptive here, see the design-philosophy notes), deep
freeing and the arena (`docs/MEMORY.md`), the flat store, and test cases that
run at build time and must give the same answer every time.

## 1. Audit: what is shared today

Read: `idc/compiler/parse/back/tgt/c/runtime/{prelude,extern}.id` (the same C,
internal and external linkage), `idc/interop/idl.c` (`--lib`), `docs/MEMORY.md`,
the test harness's prelude under `back/tgt/c/emit/prog/test/unit/`. "Shared"
means a plain C global that every function of the program reads and writes.

| state | where | shared before this work? | what breaks under two threads |
| --- | --- | --- | --- |
| **The arena**: `id_arena_head`, `id_arena_hooked`, `id_nfree` | `id_alloc`, `id_realloc`, `id_block_free`, the `atexit` hook | yes, one doubly linked list of every heap block | `id_arena_link` and `id_arena_unlink` are unsynchronised pointer surgery on one list: two threads allocating at once lose a block or corrupt `prev`/`next`, and the exit-time `free` walk then double-frees or crashes. Every string and list goes through it, so a thread that so much as adds two strings corrupts it |
| **List allocation and growth**: `IdList` header plus separate cell array | `id_list_new`, `id_list_push` (`id_realloc` of `data`) | the list is shared by whoever holds the pointer | a list is a reference, so two threads holding one and pushing is a plain data race, and `push` moves `data` under the reader. Reading a list nobody mutates is safe |
| **The flat store**: `id_store`, `id_store_used`, `id_store_cap` | `alloc`, `peek*`, `poke*`, `str_of_mem` | yes, one byte array | `alloc` grows it with `realloc`, so a concurrent `peek` reads freed memory; two `alloc`s hand out the same address (`id_store_used` is read-modify-write). Store addresses are plain integers, so nothing says which thread owns one |
| **String memo caches** | gone | no state: `id_slen` is one load of the count stored before the bytes (`docs/MEMORY.md`, section 1) | nothing. The memo this item names was removed when strings got their count in front; strings are immutable, so sharing one is safe. The freestanding runtime (`idc/runtime/`) has no memo either |
| **Export globals**: every `export`ed variable and every `conf.id` constant | C globals assigned when the declaring function runs; constants are built before `main` | yes, one program-wide namespace | a function that writes an export races with every reader. List constants from `conf.id` are locked (`id_list_lock`, negative `cap`), so they are read-only and safe to read from every thread; an export written after threads start is not |
| **The free guard**: `id_fguard`, the freed-list marker | `id_list_free` | lazily initialised global | a benign-looking race on first use (TSan reports it); `id_list_free` on a list another thread is reading turns its length to -1. The compiler only frees *locals it allocated* (`docs/MEMORY.md` section 2), so a free is on the allocating thread's list unless a shared list is a *parameter*, and a parameter is never freed |
| **Trap handling**: `id_trap`, bounds, division, `exit(1)` | prints to stderr and calls `exit(1)`, from any thread | process-wide by nature | the process ends, which is the contract; but the message is whichever thread trapped first, so a program with two failing workers is not deterministic, and `exit` runs the `atexit` hook on the trapping thread while others run. In `--lib` mode `idl_exit` does `longjmp(idl_jb)` on one static `jmp_buf` |
| **`--lib` mode**: `idl_jb`, the arena mark/restore frame, `idl_lock` | `idc/interop/idl.c` | one `pthread_mutex_t` around every exported call, so a library is already serialised | calls from several host threads are safe but one at a time. The frame logic assumes one arena and one store (it marks and rewinds `id_arena_head` and `id_store_used`), so the runtime's per-thread state must stay a single set there: `idl_pre.h` defines `ID_TLS` empty |
| **I/O buffers**: `print`, `put`, `flush`, `input`, `read_all`, `getkey`, the raw-terminal state | libc `stdout`/`stdin` (locked per call by libc) plus `id_saved_termios`, `id_raw_active` | yes | libc keeps each call whole, so there is no memory error, but two threads' lines interleave in whatever order they run: output is nondeterministic. The terminal state is plain globals and is main-thread only |
| **`ticks`** | `clock_gettime(CLOCK_MONOTONIC)` | stateless | nothing racy. It is the one builtin whose result differs between runs by design; a worker that reads it is nondeterministic, like a worker that prints |
| **The test harness**: work counters (`time`/`mem` constraints), `idtc_rec_*` call recorders, `idtc_nc` | `back/tgt/c/emit/prog/test/unit/` | yes, `static` globals incremented on every call | a case that runs a threaded function increments them from several threads: a race, and a `time` constraint on such a case counts nondeterministically. Cases for `thr_map` itself state no `time`/`mem` constraint and no `calls` clause on the mapped function (section 5, item 6) |
| **The escape analysis's frees** | per function, on locals | not shared by construction | owned locals are allocated by the same function that frees them, so a worker frees only its own. Passing a list to a worker keeps it (a `native` keeps everything), so it is never freed early |

What this says: the state that is *wrong* to share is the arena, the store and
the free guard. They are bookkeeping, not program data, so they can be made
per-thread without changing what any single-threaded program computes. The state
that is *program data* (exports, list contents, I/O) is the language's, and
sharing it is a language decision (sections 2 and 3), not a runtime fix.

## 2. Options

Each option is a proposal for the user. Syntax is a sketch only; no syntax
change is made by this pass.

### (a) Share-nothing workers and message channels

Every thread has its own arena, flat store and copy of the exports; threads talk
only through channels that copy or move a value.

```
spawn(worker_fn, seed)            // returns a handle; worker_fn is func(Chan, Chan) return void
Chan c = chan_new(16);            // bounded, typed by the element: int, word, float, string, int[]
chan_send(c, [1, 2, 3]);          // deep-copies the list into the receiver's arena
int[] xs = chan_recv(c);          // blocks; messages arrive in send order
join(handle);
```

- **Runtime.** Per-thread arena/store/export copy (`__thread` on the same
  globals, plus a startup copy of exports, since each export has a declaring
  function that runs per thread). A channel is a mutex-protected queue of
  *serialised* values (a flat byte image of an int list, a string, a word); a
  receive rebuilds it in the receiver's arena. Blocking needs a condition
  variable. No lock is held while user code runs.
- **Test cases.** Deterministic if the program is: one sender and one receiver
  per channel gives a fixed order, so a case may `send` then `recv` on the
  calling thread, or spawn a worker and join it. A case may not race two
  senders on one channel (the compiler should reject a channel with more than
  one writer, which is the same single-writer rule exports want). `time`/`mem`
  constraints count per thread and are summed at join.
- **Deep free and ownership.** The cleanest of the four: a sent value is
  *copied* (or moved: the escape analysis can prove the sender never uses it
  again and hand the block over), so every block has exactly one owner thread
  and `id_list_free` never runs on another thread's block. Moves are an
  optimisation the analysis may add later; copies are correct on day one.
- **wasm.** Wasm threads need shared memory and atomics, which the wasi
  toolchain here does not build for (`__wasm__` keeps its state in plain
  globals). Run `spawn` as a coroutine-less serial call: `spawn` runs the worker
  to completion at the first `join`/`recv` that needs it. That is correct for
  workers that only talk through channels in a pipeline that cannot deadlock, and
  the compiler can reject the rest on the wasm target. JS hosts can offer
  Workers later.
- **Cost to single-threaded programs.** None if the thread-local storage is
  free (section 4 measures it) and the channel machinery is dead-code-eliminated
  when unused, as every idstd backend is.

### (b) Structured parallelism: `par_map` over pure functions

A fork-join map, with the compiler proving the function is pure.

```
int[] ys = par_map(row_sum, 600);          // [row_sum(0), ..., row_sum(599)]
int[] zs = par_map(blur_row, img_rows);    // a list in: f(list[i]); elements are read-only
```

- **Runtime.** What section 4 built: a worker pool, an atomic ticket for the next
  index, one slot per result, a join. The result is a pure function of the
  inputs, so it is identical for every thread count and every schedule.
- **Purity, proven by the compiler.** The same shape as the escape analysis
  (`docs/MEMORY.md` section 2): a per-function summary computed bottom-up. `f` is
  pure when it writes no export, calls no I/O builtin (`print`, `put`, `flush`,
  `input`, `read_all`, `getkey`, `sleep_ms`, `ticks`, `eprint`), mutates no list
  it was handed (it may build and mutate its own), calls no `native` that is not
  marked pure, and calls only pure functions. A call through a function value is
  impure unless the parameter's type says otherwise. The proof obligation
  matches what MEMORY.md already tracks (a parameter's "kept" bit); a "written"
  bit per list parameter and an "impure" bit per function are the additions.
- **Test cases.** The strongest of the four: `par_map(f, n)` must equal
  the serial loop, so a case is just the expected list, and a generated
  cross-check (`par_map` against `map_serial`, for several thread counts) is a
  conformance case, not a hope.
- **Deep free and ownership.** Each worker has its own arena, freed at join; a
  result that is a scalar needs no transfer, a list result is copied into the
  caller's arena at join (the cost of the model, and the reason section 4 starts
  with `int` results).
- **wasm.** `par_map` is its own serial loop on wasm; the output is identical by
  construction, so no feature is missing, only the speedup.
- **Cost to single-threaded programs.** None: a program that does not call it
  links no pool.

### (c) Shared-memory threads with locks or atomics

```
Thread t = thread_start(work_fn, arg);
Mutex m = mutex_new();   mutex_lock(m);   ...   mutex_unlock(m);
int old = atomic_add(counter, 1);         // counter is an export or a store cell
```

- **Runtime.** The arena needs a lock or per-thread arenas with cross-thread
  frees; list `push` needs a lock or must be forbidden on a shared list; exports
  need a memory model. A full model is a project: what a read of an unlocked
  export means, what `id_list_free` does to a list another thread reads, how
  the escape analysis treats a list handed to another thread (it must treat the
  thread start as a keeper, which is the `native` rule today).
- **Test cases.** Not deterministic in general: a data race or a lock-order bug
  is exactly what a build-time case cannot pin down. Cases would be limited to
  single-threaded behaviour of the locked structure, plus a "stress with a fixed
  schedule" harness that serialises threads at lock points, which tests a model
  of the program rather than the program.
- **Deep free and ownership.** A free is only safe after every thread that could
  hold the block has let go; that is a distributed proof the single-function
  escape analysis cannot make. Realistically a shared block is never freed
  (leaked to exit), which contradicts the "memory must be freed" decision.
- **wasm.** Needs SharedArrayBuffer, atomics, cross-origin isolation and a
  pthread-capable libc; none is in the current toolchain.
- **Cost.** Every shared access pays for the discipline unless the compiler
  separates shared from private data, which needs a type-system change.
- **Against the philosophy.** The restrictions exist so that what a program does
  is determinable from its own context. A lock is a statement about *other*
  threads, which are by definition not in the context. This option is the one
  that most contradicts it, and the one every library ecosystem the user wants to
  reach (a DAW SDK, a video library) is built on, which is why it is available at
  the FFI boundary (section 3).

### (d) A real-time tier

A function the compiler proves never allocates, never traps, never blocks, run
by a thread that is allowed to be the audio callback; fed by lock-free
single-producer/single-consumer rings.

```
realtime process_block(int[] ring_in, int[] ring_out, int frames) { ... } return void;   // attribute or a profile
ring r = ring_new(4096);           // a store region: head, tail, cells
int ok = ring_push(r, sample);     // producer thread only
int s  = ring_pop(r);              // consumer thread only; -1 when empty
```

- **Runtime.** A ring over the flat store with acquire/release head and tail,
  as natives (a `word` cell load/store with ordering); the realtime thread's
  arena and store are preallocated and never grown. A trap inside a realtime
  function cannot `exit`: it needs to return a status (a design fork, rank 3 in
  the roadmap).
- **Compiler.** The analysis is a call-graph property like purity: no
  allocation (`+` on strings, list literals and growth, `alloc`, `str_of_int`),
  no unbounded loop, no I/O, no call to anything not proven; bounds-checked
  indexing stays (a trap is a status instead of an exit, or the function must
  prove its indices). Whether "no trap" is provable or only "traps are returned"
  is the open fork.
- **Test cases.** Deterministic: a realtime function is pure on its ring cells,
  so a case is "this input block produces this output block", and the
  no-allocation claim is itself checked at build time by the analysis.
- **Deep free and ownership.** Nothing to free: that is the point.
- **wasm.** An `AudioWorklet` is the realtime thread there; the ring is a
  `SharedArrayBuffer`. Until then, serial.
- **Cost.** None for programs that do not use it.
- **Dependency.** It does not need (a), (b) or (c) first, but it needs the
  per-thread runtime state of section 4 and the purity analysis of (b) as a
  base, and the audio seam (M2) is the first customer.

## 3. Recommendation and order

Combine **(b), then (a), then (d)**, and keep **(c) out of the language**.

1. **Per-thread runtime state** (done in this pass, section 4). Prerequisite for
   every option, free for single-threaded programs.
2. **(b) `par_map` with a compiler-proved purity check.** It delivers the
   speedup the compute workloads need (image work, hashing, a parallel build's
   independent steps) while keeping every result deterministic and every case
   exact. The prototype's `thr_map` is the library half; the compiler half is
   the purity summary (section 5, item 1). Ship `thr_map` as an idstd function
   first, with the purity rule enforced by a diagnostic in a second step.
3. **(a) channels and `spawn` for long-lived workers** (video decode, compositor
   input). Built on the same per-thread runtime. Single-writer channels keep
   ordering fixed.
4. **(d) a real-time profile** when the audio seam needs an id callback. Its
   analysis reuses (b)'s purity machinery and adds an allocation bit.
5. **(c) only at the foreign boundary.** Shared-memory threads exist in the C
   shims id already links (audio, video, sockets); id talks to them through
   store rings, which is the SPSC ring of (d). Not offering locks and atomics in
   the language is the choice the philosophy supports; if the user disagrees, it
   is the largest fork in this document.

## 4. The prototype

What was built, without a syntax change:

- **The runtime keeps its arena, flat store and free guard per thread.** The
  seven globals are declared `ID_TLS`, which is `__thread` unless a build
  defines it away. `--lib` defines it empty (`idc/interop/idl_pre.h`) because
  that mode already serialises every call under a lock and its frame logic
  assumes one arena; a `wasm32` build defines it empty because there is no
  thread. `id_thread_enter()` and `id_thread_leave()` are the two entry points a
  thread uses: the first marks the thread's arena as hooked (so it does not
  register another `atexit`), the second frees every block the thread
  allocated, store included. Both are non-static so a native's separately
  compiled C can call them. Files: `prelude.id` and `extern.id` under
  `idc/compiler/parse/back/tgt/c/runtime/`, kept in step by hand as before.
- **idstd `sys/io/ipc/proc/thr/`** (self-contained, so a layout move carries it
  whole): `be/` is the backend (`thr.h`, `thr_linux.c`, `backend.id` linking
  `-pthread`, `map.id` declaring the natives `thr_run` and `thr_cpus`), `run/` is
  the id side (`thr_map`, `thr_map_serial`, with their cases and fixtures).
  `thr_run(f, n, threads, out)` starts `threads - 1` workers; the caller works
  too. Workers take indices from one atomic counter and write only `out[i]`, so
  the result list is independent of thread count and schedule. Each worker
  calls `id_thread_enter`, runs, and calls `id_thread_leave`.
- **`demos/thrdemo`**: a Mandelbrot image, one row per `thr_map` task, whose
  output (row count and a hash of the row sums) must be identical for the
  serial and every threaded run.

The contract the prototype relies on and the compiler does not yet check (the
list in section 5): `f` writes no export, does not print or read input, does not
mutate a list it was handed, and does not use a store address another thread
made. Reading a `conf.id` constant or a list an export holds is safe; the store
is per thread, so a foreign address traps (`store address ... out of range`)
instead of racing.

Targets: C and LLVM share the runtime, so both thread (the LLVM build was run,
section 6). `--target wasm` links `thr_serial.c` (`wasm_wasi_sources` in
`backend.id`), which runs the same job on the one thread and gives the same list;
`ID_TLS` is empty there.

The two new runtime names, `thread_enter` and `thread_leave`, are in the
compiler's reserved-name list (`resv_names_src` in `idc/compiler/parse/conf.id`),
which a stdlib test checks against the prelude; the unit case that counts that
list (`mid/form/unique/scan/more/reserved/runtime.id`) moved from 75 to 77.
Because the C runtime is part of what the compiler emits, the compiler's own
stage 0 (`idc/bootstrap/*.c`) was regenerated and now carries the per-thread
state as well.

## 5. What must change before this is safe by construction

The prototype is safe *for a pure `f`*, and nothing stops a caller from passing
an impure one. Ordered by how much each blocks:

1. **A purity check at the call.** The compiler must refuse `thr_map(f, ...)` when
   `f` is not pure, with a diagnostic that names the cause and the fix ("`f`
   writes the export `counter`; return the value and fold it after the join").
   Needs per-function summary bits beside the escape analysis's: *writes an
   export*, *calls an I/O builtin*, *writes a list parameter*, *calls a native
   not marked pure*, *calls a function value*. **Design fork:** how `thr_map`
   says its parameter must be pure. (i) a name list inside the compiler, no
   syntax change, brittle; (ii) a `pure` marker on a function type
   (`pure func(int) return int`), a syntax change the user must decide; (iii) a
   marker on the *callee* (`pure` before a function definition, checked), which
   also serves option (d)'s "no allocation" bit.
2. **Traps in a worker.** Today `exit(1)` from a worker ends the process with
   whichever message got there first. Deterministic behaviour needs a per-thread
   trap target (the `--lib` `longjmp` shape, one `jmp_buf` per thread), `thr_run`
   returning the lowest failing index, and the id side trapping with that
   index's message after the join.
3. **Results other than `int`.** A list or string result lives in the worker's
   arena, freed at `id_thread_leave`; it must be deep-copied into the caller's
   arena first (`id_list_adopt` is the existing shape). Floats and words need
   only a different cell type.
4. **Every native is single-threaded.** `fs_*` (a handle table), `proc_*`
   (`proc_slots`), `sock_*`, `gfx_*`, `gl_*` and `env_*` keep static state. A pure
   `f` calls none of them (rule 1); the check must treat natives as impure by
   default.
5. **The test harness's counters.** `time`/`mem` and the `calls` recorders are
   plain `static` globals. Either make them atomic, or count per thread and sum
   at join, so a constraint on a threaded function is deterministic. Until then,
   cases for a function that calls `thr_map` carry no constraint and no `calls`
   clause.
6. **`--lib` and TLS.** `ID_TLS` is empty in `--lib`, so the library keeps one
   arena and store; a host calling from several threads is serialised by
   `idl_lock` as before. Per-thread state for a library would need a frame per
   host thread.
7. **Wasm threads.** Only the serial fallback exists. `wasm32-wasi-threads` needs
   shared memory and a thread-capable libc, and `ID_TLS` would become `__thread`
   there.
8. **A conformance case.** `idc/tests/conform/` has no case for threads; one should
   assert `thr_map == thr_map_serial` for several thread counts on every target.
9. **Closures (`bind`, docs/SPEC.md 1.1.1) and `thr_map`.** A closure's captured
   values are copied at `bind` and immutable (a captured list is locked), which
   is exactly what a pure function run on several threads may read, so the data
   is not what stops `thr_map(bind(f, keys), n, t)`. What stops it is the
   native: `thr_run` takes a C function pointer, a closure has none, and
   passing one traps (`id: a closure cannot be passed to a native`). The
   workers' arenas are not a problem either, because a worker only reads the
   caller's blocks, which nothing frees while `thr_map` waits. **Design fork:**
   (i) leave it, so `thr_map` takes plain functions only and a program with
   state passes it through an export, as before; (ii) give `thr_run` the object
   and call `f->fn(f, i)` from C, which changes the one documented C ABI of a
   `func` parameter (docs/INTEROP.md) for this native only, by declaring it with
   a different type than `func`; (iii) add `thr_map_clo(f, n, t)` beside it,
   which hands C the object, so the plain-pointer contract of every other native
   is untouched. (iii) is the smallest and keeps the contract; the user decides.

## 6. Measurements

Machine: 12 CPUs, shared with other work (load average about 6 throughout), so
every figure is a median of 7 runs (5 for the cost check) with the runs
interleaved where two builds are compared. Commands run from the workspace root
with `IDSTD_HOME` set.

**Correctness.** All outputs are `hash 4135956`, which an independent C program
(`ref.c`, same arithmetic, `-ffp-contract=off`) also prints for the 1200 by 1200
image with 1000 iterations.

**Speedup**, `demos/thrdemo`, built with `idc demos/thrdemo --require-tests -O2`,
run as `taskset -c CPUS ./thrdemo 0` (0 = one thread per CPU in the mask):

| CPUs | threads | median ms | speedup | efficiency |
| --- | --- | --- | --- | --- |
| 0 (serial loop, `thr_map_serial`) | 1 | 738 | 1.00 | |
| 0 (`thr_map`, 1 thread) | 1 | 737 | 1.00 | |
| 0-1 | 2 | 394 | 1.87 | 94% |
| 0-3 | 4 | 196 | 3.76 | 94% |
| 0-5 | 6 | 135 | 5.47 | 91% |
| 0-7 | 8 | 118 | 6.25 | 78% |
| 0-11 | 12 | 88 | 8.39 | 70% |

The 8 and 12 CPU rows share cores with the other load on the machine, so they
understate the code; the 2 and 4 CPU rows are the cleanest. `thr_map` with one
thread costs the same as the plain loop (737 against 738 ms).

**The same image on the other targets**: `--target llvm` and `--target wasm`
(`wasmtime run`) print the same hash; wasm runs serially (0.79 s with
`4`, 0.77 s with `-1`).

**ThreadSanitizer.** `clang -fsanitize=thread -O1` over the emitted C plus
`thr_linux.c`. A program that maps `idstd_thr_t_tri` (which builds a list per
index) over 3000 indices on 4 threads: **0 reports** with `ID_TLS` as built;
**224 reports** from the same C compiled with `-DID_TLS=` (the arena list head,
`id_arena_hooked` and the rest shared). The demo under TSan on 4 threads: 0
reports. That the control fires is what makes the clean result mean something.

**What per-thread state costs a single-threaded program.** The same emitted C
built twice with gcc -O2 (`-DID_TLS=` against the default), alternating runs on
one pinned CPU, machine loaded:

| program | with TLS, median ms | without, median ms | note |
| --- | --- | --- | --- |
| `bench/id/btrees 17` | 5371 | 5253 | runs spread 4812-7088 against 5093-6649 |
| `bench/id/strbuild 16000000` | 3813 | 3954 | 3475-5465 against 3360-4918 |
| `bench/id/sortb 10000000` | 1912 | 1745 | 1550-2039 against 1630-1974 |

The differences (+2%, -4%, +10%) are inside the run-to-run spread, so this
measurement does not show a cost and does not show there is none. What it does
show: in `btrees`, `%fs:` accesses go from 4 to 15 instructions in the binary;
in an executable they are one segment-relative load. The place a real cost could
hide is a hot loop of `peek`/`poke`, which this does not isolate; if it
matters, `-DID_TLS=` is the escape hatch, and a driver flag that defines it
when no thread backend is reached would remove it by construction (not done:
the backend `cflags` apply to the backend's sources, not to the program).

Function bodies, builtins and every id program are otherwise unchanged by this
pass; the changes are the seven declarations and two functions in the runtime,
the `ID_TLS` define in `idl_pre.h`, and the new idstd module.
