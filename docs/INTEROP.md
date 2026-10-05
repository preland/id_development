# Interoperating with other languages

> **Status: "id and JavaScript" describes what is built and is run by
> `idc/tests/wasm_js.sh`; every other section carries its own status.**

This file is shared between the interop slices; each section is written by the
slice that owns it. A change to another slice's section belongs in that slice.

## id and JavaScript

`idc --target wasm` builds an id program into a WebAssembly module, and since
this section was written it also writes the JavaScript that loads it:

```
idc PROJECT --target wasm -o build/app.wasm
build/app.wasm      the module
build/app.mjs       an ES module: load(), the project's public functions, IdTrap, createMemFs
build/app.d.mts     TypeScript declarations for app.mjs (the file tsc pairs with a .mjs)
build/app.d.ts      the same text, for tools that look for a .d.ts
```

```js
import { load } from "./app.mjs";
const app = await load();           // the app.wasm beside it; or a URL, bytes, a Response
console.log(app.greet("web"));      // strings, ints, floats and lists of them cross
app.dispose();
```

`app.mjs` is self-contained -- the runtime, the WASI imports, the marshalling
and the JS module of every backend the program reaches are in it -- and runs
unchanged in Node and, by construction, in a browser or bundler (tested only under Node v24; see "Not done"). `--no-js` writes the
`.wasm` alone, as before. Nothing is written when `node` is not on `PATH`,
and the driver says so.

The sources are `idc/tools/jsbind/` (`glue.mjs`, the runtime; `gen.mjs`, which
reads the wasm's imports and the root files' signatures and writes the
outputs; `shim.c`, the seven `idw_*` functions appended to the C before it is
compiled for wasm). `idc/tests/wasm_js.sh` is the test (`tests/run.sh wasm_js wasm_js_std`).

### What is public: the export rule

**Decision (a fork, see "Forks"):** the functions bound and exported are the
ones defined in the project's **root files** -- the files directly in the
directory named on the command line, or the one file when a file is named.
A subdirectory is how a project is built; a root file is what it shows. This is
the rule a C-ABI `--lib` mode is expected to use too, so one project has one
public surface for C, Python and JavaScript. `--exports all` exports every
function of the project and its imports, idstd excluded -- what `--target wasm`
did before this section, and what a project whose root is just a `conf.id`
needs. A project with no root function builds, says so, and exports none.

A function is bound when each parameter and its return are one of

| id | JS | notes |
|---|---|---|
| `int` | `number` | an integer in -2^31 .. 2^31-1; anything else is a `RangeError` before id runs |
| `float` | `number` | |
| `word` | `bigint` | 64-bit; a safe integer `number` is also accepted |
| `string` | `string` | UTF-8; a NUL in it is a `TypeError`, because an id string cannot hold one |
| `int[]`, `float[]`, `string[]` | `number[]`, `number[]`, `string[]` | copied both ways |
| `void` | `undefined` | return only |

A function with a struct, a function-typed or a nested-list parameter is not
bound (it is listed in the `.d.ts` as a comment and stays callable as
`raw.id_NAME`). A name that would collide with the instance's own members (`raw`,
`memory`, `alive`, `dispose`, `run`) gets a trailing `_`.

### Memory, ownership and traps

* **Copies, not views.** Strings and lists are copied across in both
  directions; JS never holds a pointer into wasm memory, which moves when
  memory grows.
* **Arguments are allocated in id's arena and stay there until `dispose()`**,
  because the compiler cannot say whether a callee kept them (stored a string
  in an export, pushed it onto a list) and freeing one that was kept is a
  use-after-free. So a loop of calls grows memory by the size of its arguments
  and results. `load(url, { freeArgs: ["fn1", "fn2"] })` (or `true`) releases
  the string and list arguments of the named functions after each call; it is
  safe only for functions that do not keep their arguments, and a wrong list
  corrupts the instance. **Returned** strings and lists are never released by
  the bindings, because a function may return what it also stored.
* **A trap is an exception.** id's runtime checks (index out of bounds,
  division by zero, out of memory, a freed list used, a NUL in a string)
  print `id: ...` on stderr and call `exit(1)`; WASI turns that into
  `proc_exit`, and the bindings throw `IdTrap` with `kind` ("exit", "trap" for
  a raw wasm trap, "stack" for recursion too deep), `code` (the exit status, 1
  for a trap) and `message`/`stderr` (the last line the program wrote to stderr
  during the call). The line also reaches the `stderr` sink once, as it would
  on a terminal.
* **A trapped instance is dead.** `exit` has already run the runtime's
  free-all, so the heap is gone; every later call throws "the instance is
  dead", `alive` is false, and the way on is `load()` again. (A JS exception
  from a sink or a backend module kills the instance the same way, because it
  unwound wasm frames.)
* **The layout is checked once, at load**: `idw_abi` reports sizeof/offset of
  the runtime's list header and string length word, and `load()` refuses a
  module built by an idc whose layout the glue does not read.

### Natives on wasm: how `backend.id` carries over

The C target links a backend's C (`backend.id`'s `c_PLATFORM_sources`). A wasm
module cannot call POSIX, `fork` or X11, and "the same C recompiled" is the
right answer for one part of one backend only. A native on wasm is answered in
one of three ways, tried in this order of preference, and **a backend is still
linked only when a native of it is reached** -- by the same rows `--natives`
gives the C target, and then by `wasm-ld --gc-sections`, which drops the code
that would have called the rest:

| tier | what answers the native | `backend.id` | cost |
|---|---|---|---|
| 1. libc over WASI | the builtins: `print`, `put`, `input`, `read_all`, `eprint`, `ticks`, `sleep_ms`, `getenv` | nothing; the runtime already does | none |
| 2. C for wasm32-wasi | a backend's own C that is libc and nothing else | `string[] wasm_wasi_sources = ["x.c"];` (+ `_cflags`, `_link`) | one clang compile, linked in |
| 3. JavaScript | everything the host must do: files, environment, sockets, windows | `string wasm_js = "x.mjs";` | the native stays an import, `env.id_NAME` |

Tiers 1 and 2 reach the host through WASI imports, which the generated module
answers (`fd_write`/`fd_read` for fds 0-2, `clock_time_get`, `poll_oneoff` for
`sleep_ms`, `random_get`, `environ_*`, `args_*`, `proc_exit`; every other WASI
function answers ENOSYS). **A JS module** is an ES module whose default export is
`function (host)` returning an object of natives by name, each taking and
returning what the wasm signature says (`i32` as a number, a `word` as a bigint,
a string or list as a pointer):

```js
export default function (host) {
  return {
    jsx_shout(sp) { return host.lowerString(host.str(sp).toUpperCase() + "!", "jsx_shout", "result"); },
  };
}
```

`gen.mjs` inlines the module into `app.mjs` by turning `export default function`
into a named function, so it is one file, and does it only for a backend whose
native the linked wasm really imports (read from the binary, not guessed): the
fixture `nobe` in `idc/tests/wasm_js/` attaches a backend and reaches nothing,
and its `.mjs` contains none of it. `host` offers `str(ptr)`, `lowerString(s)`,
`listSpan(ptr)` (`{len, data}` for an `int[]` argument: eight-byte cells, the
value in the low four), `span(addr, n)` (where a flat-store address lives in
memory), `u8`/`dv` (current views), `fs`, `env`, `run`, `opts`, `onClose(fn)`
and `raw`.

A native whose backend declares **neither** is refused at the call that
reaches it, in the C target's own words:

```
api.id:2: error: native 'nw_one', reached from this program by this call, is declared by
backend 'nw', which has no implementation for the wasm target; add `string wasm_js =
"FILE.mjs";` ... to its backend.id, or stop calling it from code this module keeps
```

**Why not WASI's file system.** wasi-libc's `fopen` works only on preopened
directories, so a path means something different from what it means to the C
target (`/tmp/x` is not `/tmp/x` unless the host maps it), `nftw`, `mkdtemp` and
`stat` coverage varies by host, and a browser has no WASI host to preopen
anything. Serving `fs_*` in JS makes a path mean the same thing on every target
-- Node's `fs` is the default in Node and an in-memory file system the default
in a browser -- and the host decides what a path reaches.

What exists: **idstd's `fs`** (all 22 natives: `stdio_*` in C over WASI, the rest
in `sys/io/fs/fs.mjs`; `fs_run` runs `/bin/sh` in Node and answers ENOSYS in a
browser) and **`env`** (`sys/io/ipc/env/env.mjs`). **`sock`, `proc`, `gfx` and
`gl` declare neither** and are refused if a program keeps a call to them. Time is
tier 1: `ticks()` and `sleep_ms` are `clock_time_get` and `poll_oneoff`; `sleep_ms`
blocks with `Atomics.wait` where it may and spins in a browser's main thread,
and `load(url, { clock, sleep })` replaces both for deterministic runs.

### The host options

`load(source?, options?)`; every option has a default for Node and for a browser.

| option | meaning |
|---|---|
| `stdout`, `stderr` | `(bytes: Uint8Array) => void`; default `writeSync` to fd 1/2 in Node, `console.log`/`console.error` by line in a browser |
| `stdin` | text, bytes or `(n) => bytes`; default fd 0 in Node, empty in a browser |
| `args` | `argv` for a program with `main`; `run(argv)` sets it |
| `env` | the environment the program sees; default a copy of `process.env`, `{}` in a browser |
| `fs` | `"node"`, `"memory"`, `createMemFs({ "/path": text })`, or any object with Node's synchronous `fs` methods |
| `clock`, `sleep` | replace the clock (ms) and `sleep_ms` |
| `run` | what `fs_run` does with a shell command |
| `freeArgs` | see "Memory" |

A program with a `main` is a WASI command: `app.run(argv?)` calls `_start` and
returns the exit status (a trap is still `IdTrap`); a library has no `run`.

### Two proofs, under the nixpkgs node (v24)

**(a) A Node CLI over an id-compiled module, on a real file.** `trials/jsontool`
(5 400 lines of id: a strict RFC 8259 parser, writer and path language),
unchanged, built with `idc trials/jsontool --target wasm`, driven by a
five-line Node script that `import`s the generated `jsontool.mjs` and calls
`run(process.argv.slice(2))`:

```js
import { load } from "./jsontool.mjs";
const m = await load(undefined, { args: ["jsontool", ...process.argv.slice(2)] });
process.exitCode = m.run();
```

`node idjt.mjs fmt package-lock.json` (idml's lockfile, 265 KB, real) writes
output **byte-identical** to `JSON.stringify(JSON.parse(text), null, 2) + "\n"`.
The generated `.d.mts` type-checks under `tsc --strict` (a consumer with two `@ts-expect-error` lines is in scratch). `get`, `keys` and `validate` work, stdin works, and the exit status is id's
(`validate` of broken input prints `<stdin>:2:1: error: expected ',' or ']'
after an array element (found end of input)` and exits 1). The files are read
through `fs.mjs` over Node's `fs`.

Wall time of one process per run, median of 15 (5 for 13 MB), node v24.15, the
output of the wasm and plain-JS columns compared byte for byte (identical). The
inputs are idml's lockfile and `[lock, lock, ...]` ×10 and ×50 (`scratch/jt/bench.mjs`):

| input | plain JS (`JSON.parse` + `stringify`) | id module under node | id native binary (C target) | `jq .` |
|---|---|---|---|---|
| 265 KB | 42 ms | 73 ms | 8 ms | 13 ms |
| 2.6 MB | 78 ms | 145 ms | 56 ms | 60 ms |
| 13 MB | 209 ms | 353 ms | 257 ms | 303 ms |

Node's own startup is 39 ms of every row. So the id parser-and-writer, run as
wasm, is 1.7-1.9x slower than V8's built-in `JSON` (which is C++ and does not
preserve number spelling or report positions), about 1.4x slower than the same id
program compiled natively at 13 MB, and never ahead of native `jq` (1.2-5.6x slower). Module load is 0.8 ms (compile + instantiate, 85 KB wasm).

**(b) The todo app, headless.** `id_webdemo` (an idml UI, all state and logic in
id) builds with the current compiler once its id is brought up to the language as
it is now (below), and runs in Node with jsdom as the DOM: React renders idml's
`todo.config.json`, the test types into the real `<input>`, clicks the real
Add button and the real toggles, and the page's text and id's own state agree at
every step:

```
empty  : "id . todo0 leftAddNothing yet - add your first task."
added  : "id . todo2 leftAddbuy milkwrite id" | id state: 2 todos, 2 remaining
toggled: "id . todo1 leftAdd✓buy milkwrite id" | id state: 2 todos, 1 remaining
```

The host code is `page.tsx`'s method table, with `rt.call("add", text)` replaced by
the typed `rt.add(text)`. What broke between the webdemo's compiler era and now:

| what | before | now |
|---|---|---|
| the compiler | `idc.py --target wasm` (deleted) | `idc/bin/idc --target wasm`, which recompiles the C target's C; `scripts/build-id.sh` must call it and name the project root |
| a function's return clause | `} return int len(import todos);` | rejected: a return clause is a name or a literal; every accessor needs a local |
| tests | none | two cases per function are required, so the stateful ones need `given init given add("x") ...`; `init` must say `} return void export todos;` |
| uniqueness | none | `toggle` (push to an imported list) is the same logic as idstd's `inf_emit`, and idstd is merged into every build; the app's own `toggle` had to change shape (a flag list flipped in place instead of an append-only log) |
| the host's WASI stub | `fd_write`, `fd_read`, `args_*`, `proc_exit` | the module also imports `environ_get`, `environ_sizes_get`, `fd_close`, `fd_fdstat_get`, `fd_seek`; the stub fails with `LinkError: Import #0 "wasi_snapshot_preview1" "environ_get": function import requires a callable` |
| string marshalling | `id_alloc(n+1)`, write bytes and a NUL | an id string now carries its byte length in the word before it; the old marshalling reads `len` as garbage. `greet("web")` (`"hi " + who`) returns `"hi "` -- **silently wrong, no error** -- while the webdemo's own `add`/`text` happened to keep working because they only store and echo the string. `lowerString` writes the header |
| the exports | every function plus `id_alloc` and `memory` | the root files' functions, plus `idw_*` helpers; `--exports all` for the old behaviour |

### Measurements

Sizes (bytes; gzip -9 in brackets). A hello-world is an id function that
concatenates two strings, with the whole of idstd merged and unreachable code
dropped by `--gc-sections`.

| module | .wasm | .mjs (runtime, unminified) |
|---|---|---|
| hello-world (1 function, no backend) | 28 707 (12 063) | - |
| 6 functions, strings and lists, no backend | 35 949 (14 509) | 26 382 (7 934) |
| the same plus fs and env (4 reached fs natives, 1 env) | 37 310 (15 028) | 34 928 (10 280) |
| todo app (7 functions) | 36 439 (14 572) | 24 189 (7 590) |
| `trials/jsontool` (5 400 lines, command) | 85 091 (29 099) | 32 943 (9 765) |

The `.mjs` is the runtime (about 21 KB) plus the inlined backend modules (fs.mjs
is 8 KB), so a program using fs pays 8 KB of JS for it and its wasm grows by
the imports only. libc's stdio and its WASI imports are most of the 28 KB floor.

Per-call cost, node v24.15, one process, 5 000 000 calls for ints and 20 000-200 000
for strings (`scratch/w/p5out/bench.mjs`; every number is ns per call):

| call | cost | note |
|---|---|---|
| plain JS `x => x + 1` | 1 | |
| raw wasm `id_bump(i)` | 8 | the boundary alone |
| binding `bump(i)` | 16 | argument check + try/catch + result |
| `nlen(s)` string in, int out: 0 / 16 / 4 096 bytes | 206 / 222 / 8 961 | the 4 096-byte figure is mostly memory growth: the arena keeps every argument (see below) |
| the same with `freeArgs: ["nlen"]`, 4 096 bytes | 3 379 | allocation and release, still ~0.8 ns/byte |
| `bang(s)` string in and out (`s + "!"`): 0 / 16 / 256 / 4 096 / 65 536 bytes | 446 / 487 / 1 003 / 17 914 / 290 654 | |
| `tally(int[n])` list in: 10 / 1 000 / 100 000 | 768 / 13 868 / 1 214 863 | ~12 ns per element |
| `dbl(int[n])` list in and out: 10 / 1 000 / 100 000 | 1 458 / 38 737 / 2 681 530 | |
| plain JS `xs.map(x => x * 2)`: 10 / 1 000 / 100 000 | 82 / 10 647 / 1 261 091 | |

The fixed price of a string argument is about 200 ns (a `TextEncoder.encodeInto`
straight into wasm memory plus one `malloc` in the arena); a list costs the same
per element as building the JS array it came from. The expensive part is memory:
the default keeps every argument and result in the arena, so 200 000 calls of
`nlen` on a 4 096-byte string end at 787 MiB of wasm memory, against 0.1 MiB with
`freeArgs`; `bang` of 65 536 bytes ×4 000 reaches 750 MiB. The first version of the
bindings measured 76 ns for `bump` and 43 900 ns for `nlen(4096)` before the
specialised arities and the in-place encode.

### Forks

1. **The export rule** (decided above, not final). Root-only matches a C-ABI
   `--lib` mode, but a root holds at most nine functions (three per file, three
   entries per directory, and a `conf.id`'s imports are not root), and every root
   function has to pass the uniqueness rule against the whole of idstd, so a public
   surface is thin wrappers that must each differ in logic from the function they
   wrap (see "Obstacles"). Options: (i) root-only, as built; (ii) every function
   (`--exports all`), which exports internals; (iii) an explicit list in
   `conf.id` -- a `string[]` constant is an exported global that reaches every
   build, which `backend.id` was invented to avoid; (iv) a marker on the function
   -- a language change, which this slice does not make.
2. **Who frees an argument.** The default is correct and leaks until `dispose()`;
   `freeArgs` is fast and the caller's promise. A compiler fact -- "this function
   never keeps parameter N", which the escape analysis already computes for its own
   frees (`docs/MEMORY.md`) -- would let the bindings choose per function and
   remove the option. Not built.
3. **Sync natives versus a browser.** `fs.mjs` is synchronous, because a native
   returns an `int`. In a browser that means the in-memory file system, filled
   beforehand; a native that waits on the network or on a user cannot be answered
   without Asyncify/JSPI, which is a toolchain change.

### Not done, and limits

* **Not run in a browser.** Every browser-side path (the line-buffered console sinks, the in-memory file system as the default, `Atomics.wait` falling back to a spin, no `process`) was written for one and exercised under Node by passing the options; no page was loaded.
* `sock`, `proc`, `gfx`, `gl` have no wasm implementation (S8 in `docs/SPEC.md`).
  A WebGL or canvas backend is the natural `wasm_js` for `gfx`/`gl`; a WebSocket one
  cannot be synchronous.
* The flat store (`alloc`, `peek*`, `poke*`) is not reachable from JS except through
  a native; there is no `store.read(addr, n)` yet, so binary data cannot be passed
  to an exported function (a string cannot hold a NUL).
* Struct parameters and nested lists are not bound.
* `stdio_read_some_mem` reads fd 0 with one `read(2)`, not through stdio's buffer
  (WASI has no `O_NONBLOCK`); do not mix it with `input()` on one stream. `fs_error`
  does not report a failure of a `stdio_*` call.
* A cold build is slow because every build compiles and tests idstd's cases: about
  30 s for a hello-world, 5-10 s when cached. `--no-std` builds are seconds.
* `app.mjs` is not minified (about 24 KB with the memory file system and the WASI
  shim; 7.6 KB gzipped).

### Obstacles (id itself)

* **A public surface cannot be thin.** `pick(xs, i) { xs[i] }` is rejected as the
  same logic as idstd's `lget`; `slurp(path)` that only calls `fs_read_text` draws
  "only forwards to ..."; both rules exist to stop duplication and both punish the
  one function whose job is to be a stable name. Wrappers had to add a constant to
  pass.
* **Names share the C namespace.** A function called `at` is rejected because the
  runtime already defines `id_at`; the same prefix is the wasm export name.
* **A return clause cannot be an expression**, so every accessor is two lines.
* **Stateful programs are expensive to test.** A case may name one `given` fixture
  per setup and read exports with `then (import x)`; a UI's state (the todo list)
  needed a fixture chain per case, and `init` may name only one of its two exports in
  `return void export`.
* **A string cannot hold NUL**, so every binary format goes through the flat store,
  which a JS host cannot reach.
* **An int is 32-bit**, so a JS `number` is exact; a `word` is a BigInt, slower to
  marshal than an int by a factor of the allocation.
* `-o dir/x.wasm` into a missing directory fails inside `wasm-ld`, with that
  message, not idc's (pre-existing).

## id as a library

> **Status: a description** of what `idc --lib` does today, tested by
> `idc/tests/lib.sh`.

An id project with no `main` builds into a library that C, Python, JavaScript
(Node) and anything else with a C foreign-function interface can call.

```sh
idc/bin/idc trials/csvlib --lib -o build/csv
#   build/libcsv.so   shared library (depends on libc only)
#   build/libcsv.a    static archive (link with -pthread)
#   build/csv.h       the C header
```

The project's cases run first, exactly as in any build: a library whose cases
fail is not built and leaves no file behind.

```c
#include "csv.h"

csv_table rows;
if (csv_rows(text, len, ',', &rows) == 0) {
    printf("%s\n", rows.row[1].items[2]);
    csv_table_free(&rows);
} else {
    fprintf(stderr, "csv: %s\n", csv_error());
}
```

`cc host.c -Ibuild build/libcsv.a -pthread`, or
`cc host.c -Ibuild -Lbuild -lcsv -Wl,-rpath,build`.

### Which functions are exported

**The top-level functions of the files directly in the project's root
directory** (for a single-file project, the functions of that file). Helpers
live in subdirectories and are not exported; the 3-entries-per-directory rule
means a project's root is already its facade, so the rule costs nothing to
follow. `main` cannot be exported: a project with one is refused, and the
message says to move what `main` does into root-level functions.

A function in the root that cannot cross the boundary (see the types below) is
an error that names the type and the fix, not a silent omission.

Other rules were considered:

| rule | needs syntax | why not (yet) |
| --- | --- | --- |
| every function outside idstd (what `--target wasm` exports) | no | exports helpers, test fixtures and every dependency's functions; the ABI becomes the whole program |
| names listed in `conf.id`, e.g. `string[] lib_exports = [...]` | no, a convention over a list constant | a second place to keep in step with the code, and the list is only a string until a tool reads it; the better choice if a project needs to export a deep function without a facade |
| an `export` marker on the declaration | **yes** | a language change, so it is a design fork; not taken |

### Types

| id type | as a parameter | as the result (`out` parameters) |
| --- | --- | --- |
| `int` | `int32_t` | `int32_t* out` |
| `word` | `int64_t` | `int64_t* out` |
| `float` | `double` | `double* out` |
| `string` | `const char* p, size_t p_len` | `char** out, size_t* out_len` |
| `int[]` `word[]` `float[]` | `const T* p, size_t p_len` | `T** out, size_t* out_len` |
| `string[]` | `const char* const* p, const size_t* p_lens, size_t p_count` | `NAME_strs* out` |
| `string[][]` | not accepted | `NAME_table* out` |
| `void` | | nothing |

Parameters are named `in_0`, `in_1`, ... after their position, because the
compiler's signature report keeps types, not names; the header's comment above
each function gives the id types. A function whose name starts with `NAME_` is
exported without doubling it (`csv_rows` in library `csv` is `csv_rows`).
Structs, `func(...)` values and lists nested more than the `string[][]` result
have no C form and are refused with the fix named.

Every exported function returns `int`:

| status | meaning |
| --- | --- |
| 0 | success; the `out` parameters hold the result |
| 1 | the id code trapped (index out of bounds, division by zero, out of memory, `exit`, a freed list...). `NAME_error()` says what. Every `out` is empty |
| 2 | an argument was invalid: a NUL byte inside a string (an id string cannot hold one; pass binary data as an `int[]`), or a NULL pointer with a nonzero length. Every `out` is empty |

`NAME_error()` returns a NUL-terminated message valid until the next call into
the library **on the same thread**. A successful call clears it.

### Ownership

* **Inputs belong to the caller** and are copied: the library never keeps a
  pointer to them after the call returns, and never writes through one.
  Because they are copies, an id function that mutates a list parameter does
  not change the host's array.
* **Results belong to the caller.** Everything returned through an `out` is
  `malloc`ed and must be released:
  * `string`, `int[]`, `word[]`, `float[]`: `NAME_free(ptr)`. A string result
    is NUL-terminated as well as counted. A list result is non-null on success
    even when empty.
  * `string[]`: `NAME_strs_free(&strs)`. One allocation holds the item
    pointers, the lengths and the bytes; `items[i]` are NUL-terminated.
  * `string[][]`: `NAME_table_free(&table)`.
  * An `out` of a failed call is empty (`NULL`/0) and needs no release.
* `NAME_error()`'s string is the library's, and is not freed.
* Nothing the id side allocates is visible to the host. Everything it
  allocated during a call is released when the call returns (below).

### Memory

An id program's heap is an arena that is freed only at process exit. That
suits a program and not a library, so a library call is a **frame**: the
arena is marked on entry and everything the call allocated (strings, lists,
`alloc`ed store memory) is freed on return, after the result has been copied
out. Measured: 800000 calls, a quarter of them traps, move resident memory by
less than 100 KB (`tests/lib/kit_host.c`).

The consequence is the **contract for a scoped library (the default)**: a
function must not leave an id heap value or flat-store contents behind for a
later call. In practice, no `export`ed variable written by one call and read
by another. conf.id constants are fine; they are built once, outside any
frame. Two guards exist, neither complete:

* a root-level function that declares an `export` is refused, because its
  value would dangle: the message names `--lib-state`;
* anything subtler (a helper three calls down that exports) is not detected.
  The symptom is a use of freed memory. Build with `--lib-state` while
  debugging to see whether that is the cause.

`--lib-state` builds a library that frees nothing per call. State persists
between calls (the pattern: a root function `reset()` makes an exported list
that `add()` and `total()` read), and memory grows until the host calls
`NAME_shutdown()`, which frees everything; id values made before it are gone
afterwards, so call the setup function again. `tests/lib/tally` is the
example.

### Traps

Every trap in the id runtime is a message on stderr followed by `exit(1)`:
list bounds, division by zero, shifts, store addresses, NUL in a string,
out of memory, a freed list, an id program's own `exit`. Inside a library the
two are redirected: the message is captured for `NAME_error()` and control
returns to the entry point by `longjmp`, which unwinds the frame and returns
status 1. The host process is not exited.

What cannot become an error return without a runtime redesign:

* **Stack overflow** from runaway recursion is a SIGSEGV. The runtime has no
  depth counter, and recovering from a stack fault needs a signal handler on an
  alternate stack that can still only abandon the process safely.
* **An infinite loop** never returns. There is no cancellation point.
* **Native backends** (idstd's `fs`, `env`, sockets, windows) act on the host
  process: a file the id code opened and did not close stays open if it traps
  between the open and the close, and `print` writes to the host's stdout.
* **Threads.** The runtime keeps its state in globals, so each library takes
  a lock around every call. Calls from several threads are safe and are
  serialised. A host that wants parallelism loads the library once per worker
  process.

### Linking, symbols, versions

The library's only exported symbols are `NAME_*`: the exported functions plus
`NAME_error`, `NAME_free`, `NAME_strs_free`, `NAME_table_free` and
`NAME_shutdown`. The runtime, idstd and backend code are hidden (version script
for the `.so`, `objcopy --keep-global-symbol` for the `.a`), so two id
libraries link into one program (tested). Code the exports do not reach is
removed (`--gc-sections`), which is why a library that uses only idstd's file
and string functions does not drag in X11 or sockets.

### Hosts

* **C**: above; `idc/tests/lib/*_host.c`.
* **Python** (ctypes): declare `argtypes`, pass `bytes` and lengths, define
  `Structure`s for `NAME_strs` and `NAME_table`, free what you are given.
* **Node**: Node 24 has no FFI. Node 26.2.0 ships `node:ffi` behind
  `--experimental-ffi`: `ffi.dlopen(path, { fn: { parameters: [...], result } })`,
  `buffer` for pointers to caller memory, `uint64` for `size_t` (a BigInt),
  `ffi.toString(ptr)` and `ffi.toBuffer(ptr, n)` to read results, `pointer`
  results as BigInt addresses.

### Call overhead

Measured on a loaded x86-64 Linux machine (load average about 15, so every
figure is a range over 2 to 5 runs, not a point). `stash1` is a void call that
writes one word to the flat store, `div` an `int`-in `int`-out call, `dot1000`
the dot product of two 1000-element `int[]` (copied in on every call), and
`csvsum1k` parses a 1000-row, 3-column CSV text with quoted fields and sums a
column (`trials/csvlib`, `csv_sum`). "Native" is the same work written in the
host language, not through the library. Scripts: the C host and the two
FFI hosts are kept with the session's scratch files, not in the repository.

| work | C: native | C: id library | Python: native | Python: ctypes | Node: native | Node: `node:ffi` |
| --- | --- | --- | --- | --- | --- | --- |
| `stash1` (call overhead) | 1.1-2.1 ns | 23.6-27.7 ns | 31-54 ns | 405-532 ns | 6-7 ns | 72-88 ns |
| `div` (int in, int out) | 1.4-2.7 ns | 22.5-32.8 ns | 35-56 ns | 548-858 ns | 10-13 ns | 212-231 ns |
| `dot1000`, arrays prebuilt | 192-247 ns | 780-1106 ns | 37-60 us (list, `sum(zip)`) | 1.6-2.4 us | 849-935 ns (`Int32Array`) | 990-1306 ns |
| `dot1000`, arrays built per call | | | | 166-261 us | | |
| `csvsum1k` | 55-143 us | 369-664 us | 166-256 us (`split`), 267-384 us (`csv` module) | 241-386 us | 151-185 us | 312-428 us |

What this says:

* The library's own fixed cost per call is about **23 ns** from C: the lock,
  `setjmp`, opening and closing the memory frame, and copying scalars. That is
  what a host pays before any id code runs.
* **Python's ctypes costs 0.4-0.9 us per call** and dominates everything small;
  against it the library's 23 ns is noise. A call that does real work
  (`csvsum1k`) is on par with the `csv` module and pure-Python splitting.
  Building a ctypes array per call (166-261 us for 1000 ints) costs far more
  than the call; keep arrays alive across calls when the data repeats.
* **Node's FFI costs 70-230 ns per call**, and a JS function costs 6-13 ns, so
  a trivial call is 10-30 times slower across the boundary and an id library
  only pays when it does more than roughly a microsecond of work. `dot1000`
  on prebuilt buffers is within 1.5x of JIT-compiled JavaScript.
* The id code itself, in C or in a host, is **3.5-5x slower than hand-written C
  on list-heavy work** (`dot1000`, `csvsum1k`): lists are heap cells with a
  bounds check per access, inputs are copied into them, and strings are
  counted copies. The boundary is not where that goes.

### Files

* `idc/bin/idc`: `--lib`, `--lib-state`.
* `idc/tools/libgen/`: an id program that turns the compiler's signature
  report (`idparse --fingerprints`) into the header and the wrappers.
* `idc/interop/idl_pre.h`, `idc/interop/idl.c`: the entry-point machinery
  every library is built with (lock, trap redirection, frames, marshalling).
* `idc/tests/lib.sh` (sections `lib`, `lib_csv`), `idc/tests/lib/`.
* `trials/csvlib`: a library over `trials/csvq`'s CSV parser.

## Calling C from id

> **Status: measured on this tree, 2026-10-05.** Every command and number below was run unless a line says "not tested".

An `id` program can call an existing C library today, from a project of its own, without touching `idstd`. The mechanism is the native backend of [`BACKENDS.md`](BACKENDS.md) and [`PROJECT.md`](PROJECT.md) section 7: a directory with a `backend.id`, a C source and `native` declarations. This section says what that costs, shows it on two real libraries (zlib and SQLite), lists what the language cannot express, and describes `hdr2id`, a tool that writes the declarations and shims from a C header.

### 1. A project's own natives and backend

Nothing had to change in the compiler or in `idstd`. A backend is any directory, anywhere in the project tree, that holds a `backend.id`; the `native` declarations may sit in that directory or in any directory below it (`trials/sqlq/sq/conn/open.id` is three levels down). The driver compiles and links the backend's C only when a native it declares is reachable from `main` (or from a test case).

```
trials/gz/
  entry.id                 main
  zl/
    backend.id             how to link: sources, flags, libraries
    zl.c                   the shim: C over zlib, exporting id_zl_<native>
    zl.h                   the C prototypes (documentation, and what zl.c includes)
    pack.id  info.id       the native declarations
  work/ ...                ordinary id that calls them
```

`backend.id` for zlib (`trials/gz/zl/backend.id`):

```
string name = "zl";
string[] c_linux_sources = ["zl.c"];
string[] c_linux_cflags = [];
string[] c_linux_link = ["-lz"];
```

A native `native zl_gzip(word src, int n, word dst, int cap, int level) return int;` is emitted as the prototype `int id_zl_gzip(long long src, int n, long long dst, int cap, int level)`, so `zl.c` defines that symbol. The C ABI of each id type:

| id type | C type a shim sees | note |
|---|---|---|
| `int` | `int` | 32 bits always |
| `word` | `long long` | also an address in the flat store |
| `float` | `double` | |
| `string` | `char*` (take it as `const char*`) | NUL terminated, a length in front of it; read it, copy it if you keep it, never write it |
| `int[]`, `word[]`, `string[]`, a struct | `IdList*` | `typedef struct { int len, cap; long long* data; } IdList;` copied into each backend that uses it (`fs.h`, `gfx.h`, `sq.c`); one 8-byte cell per element or field |
| `func(A, B) return R` | a C function pointer | `int (*)(int)`, `int (*)(char*)` and so on, for scalar, string, word, float and list parameters |
| return `string` | `char*` | build it with `id_str_of_cstr(p)`, which the generated program exports; a plain `char*` has no length in front and breaks `len` |

Two entry points of the generated program are meant for C: `unsigned char* id_store_span(long long addr, long long n)` (a pointer into the flat store, bounds-checked, valid until the next `alloc`) and `char* id_str_of_cstr(const char*)`. Declare them `extern` in the shim. Bytes cross as store addresses: `alloc`, `poke8`, `mem_of_str`, `fs_load` on the id side; `id_store_span` on the C side. `zl.c` takes every span it needs before it calls zlib and allocates nothing in between.

How to link a system library, and what is awkward about it:

* `backend.id` is read by the shell, not compiled: only literal strings and string lists, no `$(pkg-config ...)`, no environment variables. `c_linux_link = ["-lz"]` works only if the build's `cc` already finds the library.
* In this repo's devshell zlib is found, but not because `flake.nix` asks for it: `flake.nix` does not name zlib, and its include directory and library directory are in the shell's `NIX_CFLAGS_COMPILE` and `NIX_LDFLAGS` because another input of the shell depends on it. SQLite is not there (`pkg-config sqlite3` answers "not found"). Tested workaround for one command:

  ```
  export NIX_CFLAGS_COMPILE="$NIX_CFLAGS_COMPILE -isystem /nix/store/...-sqlite-3.51.2-dev/include"
  export NIX_LDFLAGS="$NIX_LDFLAGS -L/nix/store/...-sqlite-3.51.2/lib -rpath /nix/store/...-sqlite-3.51.2/lib"
  idc/bin/idc trials/sqlq -o sqlq
  ```

  The durable fix is `sqlite` and `zlib` in the `buildInputs` of `flake.nix` next to `gfxLibs`, where the cc wrapper injects `-I`/`-L` and the rpath (not tested; the file is outside this workspace). `trials/sqlq` does not build in the stock devshell until that is done, so it is not in `idc/tests/run.sh`.
* A `pkg-config` key (`c_linux_pkg = ["sqlite3"]`) would remove the dependence on the devshell. It is a change to the `backend.id` format, not to the language, and it adds a `pkg-config` dependency to every build that names one. Not implemented; it is an option, not a need.

Other things the mechanism does that are worth knowing before the first backend:

* Natives count as functions: at most 3 per file, at most 3 entries per directory. The 19 natives of `sq` take seven files and three directories. Natives need no test cases; the `id` that wraps them does.
* A native's name is reserved program-wide; its parameter names are not variables. `sq_*`, `zl_*` and `zh_*` are prefixes this repo has not used.
* A project with no `main` builds to an object and ignores its backends (`idc: backend(s) ignored: this project has no main`); the cases of a library still link and run them.
* `c_header` in `backend.id` is optional (`hdr2id` output has none).
* The cases of a function that calls a native run it for real, so `gz`'s cases call `gzip`, `cmp` and `truncate` through `fs_run` and compare the program against them.

### 2. Two real libraries

Both are in `trials/`, obey every compiler rule, and have two or more cases per function. Neither touches `idstd` except through one addition, `fs_load` and `fs_save` (a whole file into the flat store and back, byte exact), which both programs needed and which therefore live in `sys/io/fs/data/mem/where/`.

#### zlib: `trials/gz`

`gz c IN OUT [LEVEL]` writes a gzip file, `gz d IN OUT` restores one. A buffer API: `zl_gzip`, `zl_gunzip`, `zl_bound`, `zl_crc32`, `zl_version`, over store addresses. `zl_gunzip` reads concatenated members as `gzip` does and tells "output buffer full" (-100) from "input ended inside a member" (-101), because zlib's own -5 cannot; `gz_inflate` starts from the ISIZE in the trailer and doubles on -100.

Checked against the `gzip` command line in both directions, 2026-10-05 (`time -f`, one run each):

| input | size | gz c: time, RSS | gzip -c: time, RSS | output: ours / gzip | gzip reads ours, gz reads gzip's |
|---|---|---|---|---|---|
| `SPEC.md`+`TESTS.md` | 111,348 B | 0.00 s, 2.4 MB | 0.00 s, 3.5 MB | 39,291 / 39,251 B | both identical |
| 3 MB of `/dev/urandom` | 3,000,000 B | 0.05 s, 10.3 MB | 0.05 s, 3.6 MB | 3,000,938 / 3,000,487 B | both identical |
| 20 MB of zeros | 20,000,000 B | 0.09 s, 67.7 MB | 0.02 s, 3.6 MB | 19,465 / 19,450 B | both identical |
| empty file | 0 B | (not timed) | (not timed) | byte-identical to `gzip -n` | both identical |
| 200 MB of zeros, level 1 | 200,000,000 B | 0.55 s, 526 MB | not run | 872,762 B | `gz d` back: `cmp` identical, 0.37 s, 526 MB |

The sizes differ because `gzip -c` writes the file name and time into the header and `gz` writes none (`gzip -n`); byte parity is not the claim, interchange is. What the table shows is the cost of the buffer API: the whole input and the whole output sit in the flat store, which only grows (section 5), so memory is a multiple of the file. A streaming `z_stream` API would not have that cost, and it is the part zlib's header makes hardest to map (section 4).

Falsified by hand: forcing the level in `zl.c` makes `gz_deflate`'s level 0 case red (25 instead of 28 bytes); dropping the member accumulation in `zl_gunzip` makes the two-member case red (1 instead of 1001); a doubling that stops after one step makes the same case red (-100).

#### SQLite: `trials/sqlq`

`sqlq DB SQL [ARG...]` runs one statement and prints its rows with tabs between cells. An `ARG` binds to the next `?`: a whole integer as an integer, `@FILE` as the bytes of that file (a blob), anything else as text. `sqlq DB blob OUT SQL [ARG...]` writes the first column of the first row, a blob, to `OUT`. Handle-based (connection, statement) and byte-buffer (blob in and out) in one program; 19 natives.

```
$ sqlq q.db "create table t(id integer primary key, name text, score real, pic blob)"
$ sqlq q.db "insert into t(name, score, pic) values (?, ?, ?)" alice 3 @pic.bin      # pic.bin: 100,000 random bytes
$ sqlq q.db "insert into t(name, score, pic) values (?, 2.5, null)" bob
$ sqlq q.db "select id, name, score, length(pic), pic from t order by id"
1	alice	3.0	100000	blob(100000)
2	bob	2.5	NULL	NULL
$ sqlq q.db blob out.bin "select pic from t where name = ?" alice          # prints 100000; cmp pic.bin out.bin: identical
```

Cross-checked against the `sqlite3` command line (3.53.3 reading what the 3.51.2 library wrote): the same two rows, `typeof(pic)` of `blob` and `null`, `pragma integrity_check` `ok`; and `sqlq` reading a database `sqlite3` wrote, including a NULL. Error paths: a syntax error prints `sqlq: near "selec": syntax error` and exits 1; an unwritable path prints `sqlq: cannot open /nonexistent/d.db: unable to open database file`, exit 1; too many arguments prints `column index out of range`, exit 1.

Falsified by hand: making `sq_slot` ignore the generation turns the stale-handle case red; ignoring the kind turns both cross-kind cases red (`sq_step` of a connection handle returned 100 because it stepped the statement that held the same slot, and `sq_changes` of a statement handle was served as a connection).

Build of each tree with `IDC_NO_CACHE=1`, cases included: `trials/gz` 35 s, `trials/sqlq` 45 s, `idc/tools/hdr2id` 45 s, on a machine whose load average was about 12.

### 3. C handles in id

`id` has no pointer type, so a C pointer cannot be a value. The convention already in `idstd`'s natives is a small integer that indexes a table kept in C: `fs` (`fs_open` answers a handle or -1, `fs_error()` says why, `FS_MAX_HANDLES` slots), `proc`, `sock`, `gl` (`gl_mat_*` answer an `int handle`). It has no generation, no kind and no message: `fs_open` takes the first free slot (`fs_posix.c`), so a closed handle's number is the next file's, and the old value then names the new file. Handle 0 is a valid handle.

What `sq.c` adds, and `hdr2id`'s shims copy: a handle is `(kind << 24) | (generation << 8) | slot`. The slot's generation advances when it is filled and when it is emptied, so a handle that outlived its object answers -1 instead of reaching whatever holds the slot now; the kind (1 connection, 2 statement) makes a handle of one table refused by the other's calls. Generation is 16 bits: a stale handle is caught until its slot has been reused 65,536 times. Both are cases in `trials/sqlq/work/fix/more/stale.id`, and both were seen to go red with the check removed.

What is still awkward, all of it measured or hit while writing the two programs:

1. Every handle is an `int`. Nothing in the type system says `db` from `stmt`; the kind bits catch the mistake at run time, once.
2. No destructor. A function that returns early leaves the handle open, and process exit does not close it. For `gzFile` that loses data: a program that called `zh_gzputs` on a file from `zh_gzopen` and exited without `zh_gzclose` left a 0-byte file (`gzip -dc`: "unexpected end of file"). The generated shims do not register an `atexit` close.
3. Errors and handles share `int`. -1 means "full table", "refused call" and "stale handle" in `sq.c`, and SQLite's own positive codes (100, 101, 1 to 26) run through the same returns, so each native needs its own written convention; `sq_errmsg(db)` is the reason channel, a global last-error native.
4. Tables are fixed at compile time (16 connections, 256 statements; 64 per tag in `hdr2id` output), and "table full" looks like "stale handle".
5. A handle protocol is verbose under the action limit: running one statement is open, prepare, bind each, step in a loop, finalize, close, and `sqq_go` needs three `chain` segments for one statement.
6. `sq_close` also finalizes the connection's statements and makes their handles stale; the same rule for gz files and streams has to be written for every library by hand.

### 4. Mapping gaps

Each row was run (`scratch/gaps`: a C file and a 15-line report program; the numbers in the "evidence" column are its output) or comes from `hdr2id`'s report on the two headers.

| C feature | what id can express | what it cannot | workaround and its cost |
|---|---|---|---|
| **Callbacks** | `func(...) return R` becomes a C function pointer: `apply2(inc1, 3)` = 5; the parameters may be `int`, `word`, `float`, `string` and `int[]` (`func(string)` = 5 for "hello", `func(word)` = 42, `func(float)` = 2.5, `func(int[])` = 3). C may keep the pointer and fire it from a later native (41 gave 42). State lives in an exported list: `each(4, addacc)` summed 0..3 and left 4 entries. | A closure: an id function captures nothing, and a C API with a `void* user_data` has no place to put it. A callback whose C signature takes pointers (`qsort`'s comparator takes `const void*`). And: a callback that calls `alloc` can move the flat store while C holds a span; measured, the span's address changed (1). | A trampoline shim: for `qsort` over the store, a 14-line C file with a static function pointer and a comparator that reads the two elements and calls the id function (sorted `3 9 1 7 5` to `9 7 5 3 1`). One shim per callback shape. C must never hold a span across a call back into id. |
| **Structs by value** | An id struct arrives as `IdList*`, one 8-byte cell per field in order: an `int` as itself, a `float` as the bits of a double, a `string` as a pointer, a `word` as itself (checked with `{float, string, word}`). A shim can read it: `{7, 3}` gave 703. | C returning a struct, or taking a C struct from a library that fills it: id has no way to make one, and the runtime's list constructor is `static`. A C `struct` in a library's own layout (`z_stream`, `gz_header`) cannot be declared at all. | Pass the fields as scalars and let the shim assemble the struct; keep a library-owned struct behind a handle created and filled by shim functions. The layout is the runtime's and is not documented as an interface: `IdList` is copied into three backends today. |
| **Lists out of C** | A caller-sized list filled by C: `gp_fill([0,0,0,0])` wrote 0 1 4 9. A list returned from C can be read (length 3, first 5). | C cannot grow a list it was given (a request for 8 cells on a 2-cell list can only answer -1), and `push` on a list C returned crashed with SIGSEGV (exit 139): its storage is `malloc`, the runtime grows and frees arena blocks. | Size the list from id; return counts; or use store addresses. A native that returns an `int[]` is not safe. |
| **Varargs** | Nothing: a native has a fixed arity. `hdr2id` reports 1 of zlib's 88 functions (`gzprintf`) and 6 of SQLite's 295. | Calling `printf`-style functions with an id-chosen shape. | One shim and one native per call shape, with the format string fixed in the shim, never forwarded from id (`gzprintf(f, "%s=%d\n", label, n)` as `native zh_printf_si(int file, string label, int n)`). `gzputs` already covers the plain-text case. |
| **Out-parameters** | A scalar `T*`: pass a store address, `alloc(8)`, `poke64` before, `peek64` after; the shim takes a span of exactly `sizeof(T)`. In/out works (zlib's `destLen`: 64 in, 16 out). A `T**` that returns a new object: the shim writes the new handle into 4 bytes of the store (SQLite's `sqlite3_open` through generated code gave handle 16777472). Two results from one call: an `int[]` the caller sized, or two 32-bit values in one `word` (11 and 22 round trip). | A real multiple return, and a C pointer an out-parameter should hand back that is not a handle or a scalar. | `compress` takes five id statements (allocate, set, call, read, print) where the hand-written `zl_gzip` takes one; cost is steps, not correctness. A buffer length that is another parameter is the only thing standing between `id_store_span` and a wrong span, which is why `hdr2id` refuses to guess when two parameters could be the length (`gzfread`'s `size` and `nitems`). |
| **Unsigned 32-bit** | `word` carries it: `crc32` as `word` is correct (907060870 for "hello", the trailer `gzip` writes). | An `unsigned` returned as `int` is negative above 2^31: 0xFFFFFFFF came back as -1. | Declare a 32-bit unsigned return as `word`; `hdr2id` maps `uInt` to `int` and `uLong` to `word`, so it gets this wrong for 32-bit unsigned values. |
| **Strings** | Text without NULs, in and out. | A NUL: the store held `97 0 98 0` and a string can only see `97`. | Bytes go through the store (`fs_load`, `mem_of_str`, `str_of_mem` which traps on a NUL); text through strings. |
| **Memory** | The store is a bump allocator; `alloc` is never freed individually. | Freeing, and any C allocation id could adopt. | A 200 MB file used 526 MB through a one-shot buffer API; streaming handles are the fix, and they are the caller-allocated-struct case above. |

### 5. Generating the declarations and shims

`hdr2id` (`idc/tools/hdr2id`, written in `id`, 41 files) reads a header that the C preprocessor has already flattened and writes a backend:

```
cc -E -I... zlib.h > zlib.i
hdr2id zh zlib.h z OUT < zlib.i          # PREFIX HEADER LIB OUTDIR; OUTDIR "-" writes nothing and prints the report
```

It writes `OUT/backend.id` (`name`, the source, `-lLIB`), `OUT/zh.c` (the shims, and a handle table of the kind described in section 3 for each opaque struct) and `OUT/natives/...` (the `native` declarations, three to a file, in a tree whose directories hold three entries and are named for the first function under them). It prints one row per function and a summary. It is a tokenizer, a statement splitter, a typedef table, a prototype parser, a classifier and an emitter, each in its own directory, each function with its cases.

What it maps, by the class it gives each parameter and return type:

| C type | id type | shim |
|---|---|---|
| `char`, `short`, `int`, `unsigned`, enums, `_Bool` | `int` | cast |
| `long`, `long long`, `size_t`, `off_t`, `uLong` | `word` | cast |
| `float`, `double` | `float` | cast |
| `const char *` (parameter or return) | `string` | the pointer; `id_str_of_cstr` on the way out |
| pointer to an incomplete struct (`gzFile`, `sqlite3 *`) | `int` handle | table lookup, error value when stale |
| `T **` where `T` is such a struct (`sqlite3 **`) | `word` address of 4 bytes | the shim passes a local and writes the new handle |
| `void *`, `Bytef *`, `char *` with one parameter named like a length (`len`, `size`, `count`, `items`, `memb`, `bytes`, `n`) | `word` store address | `id_store_span(addr, length)`; the length may be a value or `*pointer` |
| pointer to a scalar | `word` store address | `id_store_span(addr, sizeof(T))` |
| `void` return | `int` | returns 0 |

Left out, each with a reason that names the fix: `...`; function-pointer parameters; a struct by value or a pointer to a struct with fields the caller allocates (`z_stream`); a buffer with no single length parameter; a return of a pointer other than a string or a handle; `va_list`; arrays. Every function the tool maps is declared `#pragma weak` and its shim returns the error value when the address is null, because a header lists functions its library does not export: the first run on `sqlite3.h` failed to link on `sqlite3_win32_set_directory8`, `sqlite3_mutex_held`, `sqlite3_mutex_notheld` and `sqlite3_snapshot_recover`.

Coverage, `hdr2id` run on the preprocessed headers of this machine:

| header | functions | mapped exactly | mapped on an inferred length or out-parameter | left out |
|---|---|---|---|---|
| `zlib.h` (zlib 1.3.2) | 88 | 29 (32.9%) | 15 (17.0%) | 44 (50.0%) |
| `sqlite3.h` (3.51.2) | 295 | 169 (57.2%) | 14 (4.7%) | 112 (37.9%) |

Why the rest were left out:

| reason | zlib.h | sqlite3.h |
|---|---|---|
| caller-allocated struct (`z_streamp`) | 38 | 3 |
| callback parameter | 0 | 18 |
| buffer with no single length parameter | 2 | 36 |
| returns a pointer other than a string or handle | 2 | 37 |
| variable arguments | 1 | 6 |
| `va_list` or an unseen type | 1 | 1 |
| other class (`const char **pzTail`, `char ***`) | 0 | 11 |

The first count to read is zlib's 38 of 44: the whole streaming API takes a `z_streamp` the caller allocates, so what the generator cannot map in zlib is the part a program needs for large files. For SQLite, the 36 "buffer" rows are `void *` that are not buffers in the store at all: user data handed back to a callback (`pApp`, `pArg`, `pClientData`), UTF-16 text (`zSql`, `filename` of the `16` functions) and memory SQLite allocated itself (`sqlite3_free`, `sqlite3_msize`); the tool is right to refuse them. The 37 returns include `sqlite3_column_text` and `sqlite3_column_blob`, pointers into SQLite's memory, and the 18 callbacks include the destructor argument of `sqlite3_bind_text` and `sqlite3_bind_blob`; `trials/sqlq`'s hand-written `sq.c` (which copies with `SQLITE_TRANSIENT` and returns text through `id_str_of_cstr`) exists for exactly those, and for `sqlite3_prepare_v2`, whose `const char **pzTail` is one of the 11 other-class rows.

The generated code was run, not only counted:

* zlib: a program over the generated natives compressed 23 bytes to 16 with `zh_compress`, uncompressed them back to the same text with `zh_uncompress`, read `zh_zlibVersion()` (1.3.2), wrote a file through `zh_gzopen`, `zh_gzputs`, `zh_gzclose`, which `gzip -dc` read back, and a second `zh_gzclose` of the same handle answered -1.
* SQLite: a program over the generated natives read `sqlite3_libversion` (3.51.2), opened `:memory:` through the out-handle (`sqlite3_open` answered 0, handle 16777472), asked `sqlite3_changes` (0), closed it (0), and the stale handle then answered -1 to `changes` and to a second `close`.

What the heuristics cost: the buffer length comes from parameter names, so a library whose names do not say what the length is gets nothing mapped or, if two names tie, nothing guessed; a pointer to a scalar is taken as one element, so an `int *` that is really an array is mapped as one, and what C writes past it lands in the neighbouring bytes of the store (`id_store_span` checks that the span is inside the store, not what C does with it); the same holds for a buffer whose C function writes more than the length parameter says; a function is taken to release its handle when its name has `close`, `end`, `free`, `destroy`, `delete` or `release` and its first parameter is a handle; `uInt` is `int`. Those are the `HH` rows of the report, kept apart from the exact ones so the percentage does not hide them.

`c2id` (`c2id/`) was not reused: it translates C function bodies into id, not declarations into natives. Reading a declaration needs the parts of a C parser `hdr2id` has, and none of the part `c2id` is for.

### 6. Where id itself was the obstacle

* A native cannot return a list or a struct, and cannot take a `size_t`-wide length (`int` is 32 bits): everything bigger than 2 GB or structured goes through store addresses.
* There is no `handle` type, no destructor and no way to attach one: the generation and kind bits and the lack of automatic release are all in C, once per backend, written by hand or generated.
* Natives count against the 3-per-file and 3-per-directory limits, so the 183 natives `hdr2id` maps for SQLite are a tree three directories deep; the file names have to pass the numbered-copy rule (`compress`, `compress2` cannot be siblings), which the tool avoids by naming each file for its first native with a fixed suffix.
* A shim needs the runtime's `IdList` layout and two exported symbols, none of which is documented as an interface; `fs.h` and `gfx.h` and `sq.c` each carry a copy.
* The unique-function rule refused four test checkers of this work that differ from a checker `idstd` already has only in which export they read (`gz_t_src_len` and `gz_t_dst_len` against `idstd_exec_t_len_a`, `gz_t_src_text` against `idstd_fs_t_got`, `gz_t_head` against `idstd_fs_t_peek`), and two list-building helpers (`pl_args`, `wr_weak`) whose loops have the shape of others. A `then CHECK` function takes no parameters, so a case that wants "this file's size" cannot share one function between two files; it checks something else instead.
* The action limit makes every C-API call sequence a chain; a test fixture that opens, prepares and steps is four segments.
* `native` parameters are checked against the C prototype nowhere: a wrong `int` for `word` in a declaration compiles, links and corrupts a store address. `hdr2id` generates both sides from one source, which is the only protection there is today.
* A `backend.id` is skipped by the glob `*.id` of any shell command that deletes or lists a project's files; a `rm gp/*.id` in a scratch copy removed it and the next build said "not in an attached backend", which is accurate and not obvious.

### 7. Reproducing

All commands from the workspace root, `IDSTD_HOME` set to the `idstd` beside it:

```
idc/bin/idc trials/gz -o /tmp/gz && /tmp/gz c IN OUT 6 && gzip -dc OUT | cmp - IN
idc/bin/idc trials/sqlq -o /tmp/sqlq            # needs libsqlite3 visible to cc, see section 1
idc/bin/idc idc/tools/hdr2id -o /tmp/hdr2id
cc -E /path/to/zlib.h > zlib.i && /tmp/hdr2id zh zlib.h z - < zlib.i
```

The generated backend is used by copying `OUT` into a project and calling `zh_*` from its `.id` files.
