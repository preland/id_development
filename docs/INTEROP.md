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
reads the wasm's imports and the exported functions' signatures and writes the
outputs; `shim.c`, the seven `idw_*` functions appended to the C before it is
compiled for wasm). `idc/tests/wasm_js.sh` is the test (`tests/run.sh wasm_js wasm_js_std`).

### What is public: the export rule

**Decision (user, see "Forks"):** the functions bound and exported are exactly
the ones named in the project's root `conf.id`, on one line:

```
import "../csvq/data"
string[] lib_exports = ["csv_rows", "csv_sum"];
```

They may be defined anywhere in the project tree, or in a tree it imports; the
rest of the program is not exported, so a public surface is a choice and not an
accident of where files are. `idc --lib` reads the same list, so one project has
one public surface for C, Python and JavaScript. The list is read by the driver
(`resolve_export_list` in `idc/bin/idc`) and goes no further -- see "The
constant" below. Each of these is an error that names the fix, before the cases
run:

| mistake | what idc says to do |
|---|---|
| a library, or a wasm build of a project with no `main`, and no `lib_exports` | add the line to `PROJECT/conf.id`; a single file has no `conf.id`, so put it in a directory |
| an empty list, or one that is not `string[]` | name at least one function; write `string[] lib_exports = [...];` on one line |
| a name that is not a function of the project | check the spelling, or remove the entry |
| a name that is an idstd function | define a function of your own that calls it and list that |
| `main` | move what `main` does into a function and list that |
| the same name twice | remove one |

Two more are found later, because they need the compiled program. A listed
function whose signature cannot cross the boundary is an error in `libgen` (for
`--lib`) and in `gen.mjs` (for wasm): remove it from the list or list a function
that calls it. And in a wasm build of a program **with** a `main`, the compiler
keeps only what `main` reaches, so a listed function it never calls is not in
the module, and `gen.mjs` says so (`--no-js` skips that check). A command (a
program with `main` and no list) exports nothing and is driven by `run()`.

**`--exports all`** is a debugging escape and not an export rule: it exports
every function of the project and its imports, idstd excluded, whatever the
list says (or does not), and binds the ones that can cross, listing the rest in
the `.d.ts` as comments. `--exports list` is the default.

**The constant.** `lib_exports` is not compiled. `read_manifest` in
`idc/bin/idc` drops that one declaration when it collects `conf.id`'s constants
(a non-`string[]` one is an error there), the way `backend.id` is read by the
driver and never compiled. Kept as an ordinary constant it would have been
harmless to the unused-constant and one-type-per-name rules -- there is no such
unused-constant rule, and a no-`main` project keeps every constant -- but two
things went wrong with it: every library paid a global and a start-up
initialiser for a list the program never reads, and a library that imports
another library's tree failed with "constant 'lib_exports' is already declared
... a constant has one home" (tested). The cost of the choice is that the
compiler does not type-check the line, so the driver does the one check that
matters (string list) and `(import lib_exports)` is an unknown name. The
declaration must fit on one line, like every constant `read_manifest` takes.

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
| the exports | every function plus `id_alloc` and `memory` | the functions in conf.id's `lib_exports`, plus `idw_*` helpers; `--exports all` for the old behaviour |

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

1. **The export rule** (decided by the user: option iii). Root-only capped a
   public surface at nine functions and forced thin wrappers (see "Obstacles").
   Options were (i) root-only; (ii) every function (`--exports all`), which
   exports internals; (iii) an explicit list in `conf.id`, taken, read by the
   driver and not compiled (see "The constant" above); (iv) a marker on the
   function -- a language change, not taken. A list is a second place to keep in
   step with the code; the errors above catch a list that has fallen behind it.
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
  pass. (`lib_exports` removes the need for a facade of wrappers over the project's
  own functions; a function of idstd still cannot be exported as itself.)
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

**Exactly the functions named in `string[] lib_exports = [...];` in the
project's root `conf.id`**, wherever in the tree they are defined (the rule,
the six mistakes it refuses and the reason the line is not compiled are under
"What is public: the export rule", above; the wasm target reads the same
list). `main` cannot be exported: a project with one is refused, and the message
says to move what `main` does into a function and list that.

```
# trials/csvlib/conf.id
import "../csvq/data"
string[] lib_exports = ["csv_rows", "csv_errors", "csv_line", "csv_col", "csv_sum", "csv_cell"];
```

A listed function that cannot cross the boundary (see the types below) is an
error that names the type and the fix, not a silent omission.

Other rules were considered: every function outside idstd (exports helpers and
every dependency's functions, so the ABI becomes the whole program), the
functions of the root files (a surface of at most nine, and thin wrappers), and
an `export` marker on the declaration (a language change, so a design fork; not
taken).

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

* a listed function that declares an `export` is refused, because its
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
| **Lists out of C** | A caller-sized list filled by C: `gp_fill([0,0,0,0])` wrote 0 1 4 9. A list returned from C can be read (length 3, first 5). | C cannot grow a list it was given (a request for 8 cells on a 2-cell list can only answer -1). A list C returns is copied into a runtime-owned list at the call (`id_list_adopt`), so `push` on it works; the copy is shallow, an alias C handed back becomes a copy, C still owns and frees its original, and a negative length traps. | Size the list from id and return counts where C should write into id's list; a returned list is safe but costs a copy. |
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

## id instead of Python

The claim being tested: `id` can do the jobs people reach for Python for (a log
file, two CSVs, a directory walk, an HTTP call, a subprocess, a command line)
without the author giving up the rules. Six such scripts were written in `id`
from a written spec, each with its cases, each compared with a Python 3.13
one-off that does the same thing. Everything below was run; where a number is a
guess it says so.

Python was used for measurement only: `nix shell nixpkgs#python3` (Python
3.13.13) in a scratch directory, never in the repository. The test data (a 5 MB
access log, two CSVs, a 600-file tree, a git repository of 300 commits, a JSON
document) was generated by a throw-away `node` script in scratch. The machine
was shared and loaded (load average 9 to 12, with other builds and a model
server running), so every absolute time is inflated and noisy; ratios are the
evidence.

### 1. Script ergonomics

#### 1.1 Edit-to-result latency

A 50-line script: `scratch/wc`, three files, eight functions, 65 lines of code
and 16 of cases, reads stdin and prints the three most common words (built-ins
only, so it needs no `idstd`). Python does the same in six lines. Input: 4,000
lines, 40,000 words. Medians of 7 runs unless a cell says otherwise.

| path | cold | warm (nothing changed) | fresh edit |
| --- | ---: | ---: | ---: |
| `python3 wc.py < words` | 19 ms | 19 ms | 19 ms (no step) |
| the compiled binary, run only | 13 ms | 13 ms | |
| `idrun wc < words` (no cases run) | 250 ms | 250 ms | 250 ms |
| `idc wc --no-std` (cases run) | 690-750 ms | 180-580 ms | 810-1050 ms |
| `idc wc --no-std --allow-untested` | | | 680-1020 ms |
| `idc wc` with idstd (cases run) | | 630-640 ms | 5.1-5.9 s |
| `idc wc --allow-untested` with idstd | | | 4.6-5.4 s |

"Cold" is `IDC_NO_CACHE=1` (the compiler's own binaries stay cached); a
from-scratch bootstrap was not measured. "Fresh edit" changes one literal in
`main` before each of four builds, so no cache answers. A first `idc` of any
program that links `idstd` after `idstd` itself changed costs 20-90 s (the whole
library's cases run once); every later build reuses that.

What the table says:

- `idrun` has no cache and no C compiler, and costs about 250 ms per run on this
  machine, almost all of it the shell line that runs `idlex` and `idparse`. That
  is 13 times Python's start-up for a script that does nothing, and it does not
  grow with edits. It is the only path that is close to Python's edit-run loop.
- `idc` on a program without `idstd` is 0.7-1.0 s per edit; the case harness
  could not be told apart from the noise (with and without `--allow-untested`:
  0.81-1.05 s and 0.68-1.02 s). The C compiler is the cost, as
  [`INTERPRETER.md`](INTERPRETER.md) section 2 measured.
- `idc` on a program that uses `idstd` is **5-6 s per edit**, and 4.6-5.4 s of
  that remains with `--allow-untested`: it is the front end re-reading all of
  `idstd`, not the cases. A real script needs `idstd` (files, strings, lists), so
  this is the number a script author feels. Python is 100 to 300 times faster
  for this loop.
- For the real `trials/script/logtop` (15 functions, 35 case lines, links
  `idstd`): see the measured table in section 1.3.

#### 1.2 `idrun` as a script runner

`idc/tools/idrun` (milestone 1 of [`INTERPRETER.md`](INTERPRETER.md) section 7)
runs a `.id` file or a project directory without a C compiler. What now works,
each checked with a program that prints its argument count and the length of
stdin and returns 7:

| need | state | how it was checked |
| --- | --- | --- |
| shebang `#!/usr/bin/env idrun` | **works** (new) | `./hello.id a b < file` printed `argc=3 len=3`, exit status 7 |
| arguments | works | `argv[0]` is the path, then the arguments |
| stdin | works | `read_all()` and `input()` |
| exit status | works | the `int` returned by `main` |
| one file, or a project directory | works | `idrun hello.id` and `idrun wc/` (3 files) |
| a script that touches a file, the environment, a process or a socket | **does not run** | none of the six ports below can; `idrun` names the first undefined callee and stops |
| the script's own cases | parsed and required, **not executed** | `INTERPRETER.md` section 7; milestone 3 |

Three changes were made to `idrun` (all three are in the manifest):

1. **A leading `#!` line is blanked**, not removed, so line numbers in
   diagnostics stay right: the shell line `idrun` assembles uses
   `sed '1s/^#!.*//'` where it used `cat`. Falsified: with `cat`, `idparse`
   rejects line 1 (`unknown type '('`). `idc` itself still rejects a `#!` line;
   see fork F8 below.
2. **`idrun` found by bare name finds its own directory on `$PATH`.** A shebang
   `#!/usr/bin/env idrun` starts it with `argv[0] == "idrun"`, from which the old
   code derived `./../.idc-cache` and failed. It now searches `$PATH`, and works
   when `idrun` is installed beside `idc` (`idc/bin/idrun`, with `idc/.idc-cache`
   one level up) or when `IDC_CACHE_DIR` is set. Install:
   `idc/bin/idc idc/tools/idrun -o idc/bin/idrun`.
3. **The two list-freeing helpers the memory-safe emitter now calls
   (`id_list_free`, `id_list_free_deep`) are no-ops in the interpreter.** Before
   this, `idrun` refused every program: `idrun: 'id_list_free' is called but not
   defined`, so the interpreter as merged could not run even the 50-line
   script above. The interpreter never frees, which is what its design note
   already said about memory.

Two duplicates were also removed from `idrun` because they are now in `idstd`
and the duplicate-logic rule crosses the import boundary (section 3):
`dr_bytes`/`dr_fill` became `fs_read_bytes`, and `dr_env`/`dr_envget` became
`env_text`. `env_text` builds its string with `chr`, not through the flat
store, so `idrun` still leaves `alloc` and `store_size` as it found them.

#### 1.3 Cases in script mode, and what they cost

[`INTERPRETER.md`](INTERPRETER.md) F1 offers three readings: run the cases
in-process before `main`, waive them for a single-file script, or make them
lazy. None of those exists yet. Today a script's cases run only on the compiled
path, in a separate C harness, and `idrun` skips them. What that harness costs,
measured on `trials/script/logtop` (the real script; it links `idstd`):

| build of `logtop` (a fresh copy in scratch; load average 11.5) | three runs |
| --- | ---: |
| nothing changed (every case answered from the case cache) | 1.2 s, 1.5 s, 1.5 s |
| one literal edited, cases run | 4.1 s, 4.1 s, 4.3 s |
| one literal edited, `--allow-untested` (cases not run) | 5.4 s, 4.1 s, 4.1 s |
| cold: `IDC_NO_CACHE=1`, cases run | 36 s |
| `python3 logtop.py` on the same 5 MB log | 0.06 s |

Reading: **the cases are not what costs.** The case cache keys a case on the
function and its callees, so an edit re-runs only the cases it touched, and
`--allow-untested` saves nothing measurable against it (4.1 s either way, within
the noise of a loaded machine). What costs is the front end reading `idstd`
again: about 4 s of every edit. (Reasoned, not measured: the milestone-4
"prechecked `idstd` image" of `INTERPRETER.md` is what removes it.) The two
cases per function are therefore a cost in *lines* (section 2.1) and in
author time, not in the loop.

What the cases bought while writing six scripts: they found one real defect
(`lt_feed` counted a malformed line under the empty key; the case "a log with a
junk line" went red) and eight mistakes in my own expectations (a tie order, an
off-by-one position in a JSON literal, a wrong help line). They also cost: about
20 per cent of the lines of every script are case lines (19 to 20 in all six),
and where a script touches files or processes up to a fifth of its functions are
fixtures that exist only so a case can set something up or read something back
(`lt_t_tab`, 3 of 15 functions in (a); `rs_t_repo` and its helpers, 5 of 23 in
(e)). A script that
reads files needs a fixture for every file it reads.

My reading, as a recommendation and not a decision: **keep the two cases for
a script that is more than a page, and make `idrun` run them in-process (M3) so
they cost milliseconds**; the loop cost is not the cases, it is the `idstd` front end
(and, for a program without `idstd`, the C compiler). A one-file script under about 30 lines waives nothing today
because the rule has no size threshold; waiving it by a `#!` line would make a
second dialect (F1, F3), and every script above was a tree of 4 to 8 files from its first
version, which is exactly the "script that grows into a project changes
behaviour" case F1 warns of.

### 2. Six scripts, written from a spec

Each spec was written before the code, in the terms a person would give for the
Python version. Sources are in `trials/script/<name>/`; the Python twins are not
in the repository.

| | spec | input | output |
| --- | --- | --- | --- |
| (a) `logtop FILE [N]` | read an nginx combined-format access log; count requests per path (query string removed) and per status; report the request count, every status by count, and the top N paths (default 10); ties by name; a line that does not parse is counted as a request and as nothing else | 5 MB, 40,001 lines, ~2,000 paths | `requests: N`, `status 200: n`, `path /x: n` |
| (b) `csvjoin CUSTOMERS ORDERS` | join orders to customers on the customer id (RFC 4180 quoting), group by customer region: orders and total amount in cents, regions by total then name; orders with an unknown customer go to `(unmatched)` | 3,001 customers, 30,000 orders | `region: N orders, total X.YZ` |
| (c) `dupfind DIR` | find files with identical content under a tree: group by size, hash only the files whose size repeats, sort groups by size of group then path | 600 files in 40 directories | `N files, S bytes each:` and the paths |
| (d) `jsonfetch HOST PORT PATH` | GET a JSON document from a server (a `trials/httpd` serving a file), print the number of users, the total score and the users ranked by score with their tag counts | 500 users, 114 KB | `users: N`, `total score: T`, `K. name score (n tags)` |
| (e) `repostat REPO` | run `git log` and `ls -l` on a repository and parse both: commits, commits per author, first and last date, the longest subject, number and total size of files, the largest | 300 commits, 40 files | eight lines |
| (f) `lines [OPTIONS] [FILE...]` | `-n/--number`, `-m/--max N`, `-p/--prefix S`, `-s/--skip-blank`, `-h/--help`; each may come from an environment variable (`LINES_NUMBER`, `LINES_MAX`, `LINES_PREFIX`); stdin when no file; exit 2 on a usage error, 1 on an unreadable file | the 5 MB log | the lines, numbered or not |

#### 2.1 Results

Each id program's output was compared byte for byte with its Python twin on the
data above and was identical (`cmp`). Times are medians of 7 runs (5 for (d)),
the id binary against `python3 script.py`, both with a warm file cache.

| task | id LoC | py LoC | functions / files | id runtime | py runtime | time to write | id blockers |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| (a) `logtop` | 172 (120 + 35) | 21 | 15 / 6 | 71 ms (69-108) | 58 ms | ~25 min | no sort by key, no string sort, no way to list a hash table, no `str_lines`; the table is four lists threaded through five functions |
| (b) `csvjoin` | 183 (123 + 37) | 20 | 17 / 7 | 13 ms | 34 ms | ~20 min | the CSV parser is inside the `csvq` program (imported its `data/` dir, which worked); no money formatting; float to int by truncating assignment; state in seven exports |
| (c) `dupfind` | 207 (148 + 40) | 25 | 20 / 8 | 17 ms | 30 ms | ~25 min | no directory walk; a file as 8 bytes of store per byte for `sha256_hash`; new `path_last` broke `trials/httpd` (`hd_last`) |
| (d) `jsonfetch` | 115 (87 + 22) | 15 | 10 / 4 | 5 ms | 80 ms | ~35 min | no JSON reader, no HTTP client (both only inside programs); reading element i by path was 388 ms until a positional API existed; chunked bodies unsupported |
| (e) `repostat` | 246 (180 + 47) | 27 | 23 / 8 | 9 ms | 43 ms | ~30 min | no subprocess capture, no split on runs of spaces; the case needs a real git repository built by a 5-function fixture |
| (f) `lines` | 112 (79 + 22 + 5 of `conf.id`) | 29 | 9 / 4 | 60 ms (36-60) | 85 ms | ~15 min | no option parser; the first version was 485 ms because `opt_get` was called per line |

Run-to-run spread on this machine was about 1.5x (the same `lines` binary read
36 ms in one run and 60 ms in another, the Python twin 53 and 85 ms), so
**read a ratio under 2 as a tie**. On that reading: (a) is a tie with Python
(not faster, up to 1.8x slower), (b), (c), (e) and (f) are faster, and (d) is
faster mainly because Python's start-up and `urllib` import are in its time.
These are 5 MB inputs; a compiled program's advantage is real but small
compared with the 4 s edit loop of section 1.1.

Columns: **id LoC** is lines of `.id` source, code and cases together, as
`total (code + cases)` with blanks and comments left out of the parts; **py
LoC** is the Python twin; **functions** and **files** count the `id` tree.
"Time to write" is wall-clock minutes from the first file to the first green
build, including waiting for builds and interleaved library work; it is a guess
from file timestamps, not a stopwatch.

#### 2.2 Where `id` or `idstd` got in the way

Most of this was found by hitting it. Each item names what would confirm it.

*Missing library (filled in `idstd`, section 3):* no sort by a key and no
string sort (every group-by report needs both); no iteration over a hash table
(`hmap_` has `get`/`put`/`has`/`count` and nothing that lists its entries); no
lines/words split, no `str_replace`; no path join/base/extension, no glob, no
directory walk; no subprocess capture (`exec_run` takes six arguments and byte
lists); no argument parser, no environment read that returns a string; no JSON
reader outside the `jsontool` program; no HTTP client outside the `httpget`
program. Each of these was written once in `idstd` so the six scripts share it.

*The rules, as a script author meets them:*

- **Three actions per block and one nested call** turn every Python line that
  does two things into two or three `id` lines. The ratio of `id` lines to
  Python lines is 4x to 9x (table); this was not split between the action limit
  and the cases, which are about a fifth of the lines.
- **Three functions per file and three entries per directory** turn a
  15-line Python script into a tree of 4 to 8 files in 2 to 3 directories.
  Naming files is the slowest creative step: the compiler rejects a file named
  like its directory and several generic names (`temp.id`, `show/show.id`).
- **One type per name across the whole tree** was hit in two of the six scripts
  (`g` a string list in one file and an int in another in (c); a local `argv` in
  a helper in (e)), twice in `idrun` (`hit`, `r`) and three times in the new
  `idstd` modules (`idstd_path_p`, `idstd_path_at`, and the whole prefix
  `idstd_txt_`, which `gfx/` already owned). The diagnostic reports the clash in
  the file you are editing, not always the other declaration, so the fix is a
  search.
- **Two cases per function, none of which may read back what the call made**
  forces a check function for every export a function declares. A function
  that returns an `int` cannot be a `given` setup, so every "setup that also
  reports" is split in two. A case cannot name a `conf.id` constant, a
  computed string or a function's return in its expected value, so a test that
  needs a random scratch path exports it and checks through a function.
- **A function value carries no state**, so the generic sort takes its keys
  from an export and its comparator reads that export (`idstd_ord_ik`).
  Closures would remove an export and a fixture from every comparator.
- **`len(s)` is a `strlen`** and `charat` memoises one string, which the code has
  to be written around: a loop `while (i < len(s))` is quadratic and nothing
  warns.
- **No formatting.** Two decimals came from integer cents and a hand-written
  `cj_money`; floats are converted to `int` by assignment, which truncates
  silently (`float f = 12.34 * 100.0 + 0.5; int c = f;` is 1234 and the
  `+ 0.5` is the author's remembering to round).
- **An `hmap_` is four lists** (`keys`, `vals`, `used`, `cnt`) threaded through
  every function that touches it; (a) passes them through five functions and
  (e) through three. `Zip` is a struct in `idstd`; the table predates structs
  and would be the first thing a script author would ask to be one.

*The duplicate-logic rule crosses the import boundary, and a library addition
can break programs that never mention it.* Adding `path_last` to `idstd` made
`trials/httpd` stop building (`hd_last` has the same signature and logic);
adding `env_text` and `fs_read_bytes` did the same to `idc/tools/idrun`
(`dr_envget`, `dr_bytes`/`dr_fill`), and the identity-permutation helper of the
sort (first spelled `idstd_ord_ident`) did it to `trials/csvq` (`srt_iota`) and
to `word` (`rbe_iota`), `ord_by_strs` did it to `trials/csvq` (`sel_row`),
`str_replace` to `wordcheck` (`ofodt_swap`), and an internal `chr` loop in
`env_text` to `idc/tools/qmon` (`bytes_str`; the helper was inlined so the
library no longer has a second copy). Each was fixed by deleting the program's
copy and calling the library's (the helper became the public `ord_iota` for
that), which is the rule working as designed. Note that `word/` and
`wordcheck/` belong to another wave's work: the two edits there are one
deleted function and one renamed call each, and will conflict with any
change to the same lines. A different collision is a plain name: `trials/jsontool` already had
a function `path_walk`, so a library `path_walk` stopped it building (`function
'path_walk' already defined at idstd/...`); the library's was renamed
`path_files`, because a library name is reserved in every program and the program
is the one that cannot move. Both kinds mean **an `idstd` addition is only safe
after every program in the repository has been built against it**; the result of
doing that for the programs in `trials/`, `idc/tools/` and a few applications is
in section 6.

*Speed traps that the language does not warn about:*

- `opt_get` looks an option up by name by splitting spec lines: 485 ms for the
  `lines` script on a 5 MB file against 36 ms once the lookups were hoisted out
  of the per-line loop (Python 53 ms). The first version was the natural one.
- The lazy JSON reader was 388 ms against Python's 80 ms for 500 users, because
  reading element *i* by path scans from the start. Adding a positional API
  (`json_next`, `json_from`, `json_str`) and walking the array once brought it
  to 5 ms.

### 3. What was added to `idstd`

Everything below is in `idstd` under `core/data/psf/glue/` (and two functions in
`core/data/hmap/`), with at least two cases per function, none of which was left
red; registered in `NAMES.md` section 1.24, section 2.9 (names), section 3
(exports). `idstd` has no free directory slot anywhere above `core/data/psf/`,
so the module hangs from the one slot left there, the same last-resort
placement `re_` uses; fork F6 below.

| area | functions | replaces |
| --- | --- | --- |
| sort by a key | `ord_ints`, `ord_strs` (stable permutation, merge sort), `ord_desc`, `ord_by_ints`, `ord_by_strs`, `ord_iota` | `lst_sort` (insertion sort, ints, no key); `trials/csvq`'s `srt_iota` |
| counting | `hmap_bump`, `hmap_items` (entries sorted by key) | two lines and a loop in every program |
| paths | `path_join`, `path_base`, `path_ext`, `path_last`, `path_glob` (`*` `?`), `path_files` (recursive, sorted, relative) | `trials/httpd`'s `hd_last` |
| text | `str_replace`, `str_lines`, `str_words` | |
| files and processes | `fs_read_bytes`, `fs_temp_text`, `exec_out`, `env_text` | `idrun`'s `dr_bytes`, `dr_envget` |
| options | `opt_parse`, `opt_help`, `opt_get` | |
| JSON (lazy) | `json_find`, `json_text`, `json_count`, `json_from`, `json_str`, `json_len`, `json_next` | |
| HTTP | `http_get`, `http_fetch` (GET, `Connection: close`, no TLS, chunked answered as -2) | |

Of the ones a script reaches for first: `opt_parse` takes a table
(`SHORT|LONG|KIND|ENV|DEFAULT|HELP`) and answers `""`, `"help"` or a message
that names the fix (`option '--count' needs an integer, got 'x'; write digits
only, such as --count 10`).

Library gaps **not** filled: regular-expression use from the scripts (`re_`
exists and was not needed), sorting by two keys in one call (it is two stable
sorts), chunked HTTP bodies, `\uXXXX` in JSON, TLS, a `str_format`/float
formatter, a `sort` that takes a function value for a key (see the closure
point above).

### 4. Forks

Each of these is a design question, left open.

- **F8 (shebang).** `idrun` strips `#!` at the shell line, so scripts run; `idc`
  and every other tool still reject it, so a script that has a `#!` line
  cannot also be compiled with `idc`. Options: (1) the lexer ignores a first
  line starting `#!` (one line in `scan_hashop`, the lexer's `#word` handler;
  a syntax change, so it is yours); (2) every tool that reads a source file strips
  it as `idrun` does (no language change, five places); (3) leave it as the
  `idrun`-only convention. Trade: (1) is the only one under which `idc
  script.id` and `idrun script.id` accept the same file.
- **F1/F3 (script mode).** Measured above: the rules cost a 4 to 9-times
  line count and a 4 to 5 s edit loop through `idstd`, and the cases themselves
  are about a fifth of the lines and none of the loop. Options: keep every rule and make `idrun` fast
  (in-process cases, a prechecked `idstd` image, M3-M4); or waive for
  single-file `#!` scripts. A waiver would not have helped here: every script
  needed `idstd`, a tree, and cases for its parsing.
- **F6 (where `idstd` puts new modules).** A directory slot, not a design, decided
  where `ord_`, `path_`, `opt_`, `json_` and `http_` live. Options: the W0
  restructure ([`WORD.md`](WORD.md) 5.2) gives `core/` and `core/data/` room and
  the modules move (names do not change); or a rule that an `idstd` addition
  names its home before it is written.
- **Closures or a keyed `sort`.** A comparator that cannot carry its keys forced
  an export per sort and a fixture per comparator (`idstd_ord_gt_int`,
  `idstd_ord_ik`). Options: function values that capture a list (a language
  change); keep the export pattern; or give the sort the key list as a
  parameter of the comparator's type (`func(int[], int, int) return int`),
  which fixes ints and not strings.
- **`hmap_` as a struct.** `Zip` shows structs work in `idstd`. Moving the table
  to one would cut about 40 per cent of the parameters in (a), (c) and (e).
  That is an `idstd` API break (NAMES.md section 0 promises none).

### 5. Python and shell that this makes removable, or still needed

No Python or shell tool in the repository was removed: this slice has none.
Functions duplicated by the new `idstd` code were removed: in `idc/tools/idrun`
`dr_bytes`, `dr_fill`, `dr_env`, `dr_envget`; in `trials/httpd` `hd_last`; in
`trials/csvq` `srt_iota` and `sel_row`; in `word` `rbe_iota`; in `wordcheck`
`ofodt_swap`. Still needed:
`idrun` assembles its sources and calls `idlex`/`idparse` through `sh`, with a
`sed` and a `cat` in the line it builds, which is the 250 ms; an `id`-written
driver (M4 of `INTERPRETER.md`) is what removes it.

### 6. Verification, and what was not run

Run, each with its result in this section's tables:

- every one of the six programs built clean through `idc` with its cases, and
  its output compared with Python's on the data above (identical);
- `idc/tools/idrun` rebuilt clean with its cases after each change (including
  the new shebang case and the `$PATH` lookup cases), and run on a three-file
  project, a single file with a shebang through `env`, with and without
  `IDC_CACHE_DIR`;
- `trials/httpd` rebuilt clean after `hd_last` was removed, and served
  `users.json` to (d); (d) was run against it again with the final binaries and
  was still identical to Python (5 ms);
- `idstd/run.sh prefix` passes for the new code. `idstd/run.sh names` fails on
  15 variables and 6 functions of other modules that are not in `NAMES.md` (for
  example `idstd_err_tj`, `idstd_gui_tgl_apply`); none of them is in the new
  modules, and the check reports nothing for these.
- eight mutations of new `idstd` code (merge-sort tie rule, glob backtrack,
  option integer check, JSON unescape, HTTP status offset, `hmap_items` order,
  `path_files` sort, `str_words` filter), each restored by copying the saved file
  back. Seven turned a case red the first time. **`path_files` did not**: its test
  tree was already in sorted order, so removing the sort changed nothing. A
  second fixture tree whose directory sorts before its file (`a/x`, `b`) was
  added, and the same mutation then failed
  `path_files(...) = ["b", "a/x"], expected ["a/x", "b"]` (the function was then
  still called `path_walk`). This is the one case in the new `idstd` code that
  was vacuous as first written.
- six mutations in the scripts and in `idrun`, five red on the first run: the
  size filter in (c) (`df_twice(...) = ["a","b","c"]`), `-m` in (f), the tie
  rule in (e) (`rs_widest(...) = 2, expected 1`), the status test in (d)
  (`jf_why([200, 0]) = "server answered 200"`), and `sed` put back to `cat` in
  `idrun` (the `dr_file` case). The sixth, the unmatched bucket in (b), came
  back green because the mutant was **equivalent**: it swapped one constant for
  another with the same value (0), so no case could tell. It was redone with a
  different value (`cj_o_cust`, 1) and went red: `cj_order(["5", "2", "0.07"])
  then (import cj_sum) = [0, 7], expected [7, 0]`.

- every other program that links `idstd` and was reachable as a project was
  built (`--allow-untested`, so this checks the cross-program rules, not their
  cases) against the final `idstd`: `trials/{csvq, kv, jsontool, jsontool-gen,
  httpget, httpd}`, `idc/tools/{buildrun, ccrun, dupscan, fbtext, idlayout,
  kbuild, mkfont, mkkeymap, mkodt, qmon, idxpack, tmpguard, idrun}`, `editor`,
  `word`, `wordcheck`, `iconcheck`, `uicheck`, `demos/fsdemo`. Six of them did
  not build at first (`csvq` twice, `jsontool`, `qmon`, `word`, `wordcheck`;
  section 2.2) and all build now. It took several rounds, because the
  compiler reports one program's first clash at a time.

Not run: the `idc/tests/run.sh` sections (no compiler change was made);
`tools/mapgen.sh --check`; the other demos, `kernel`, `c2id` (it is a container
of projects, not one, so the plain command was refused and is not a result), the
sibling repositories, and anything under a working copy of another wave. The
duplicate-logic rule means any of them could still fail to build against the new
names.

Reproduce (from the workspace root; `R` is the directory holding `id_development`
and `idstd`):

```sh
export IDSTD_HOME=$R/idstd; cd $R/id_development
idc/bin/idc trials/script/logtop -o logtop        # builds idstd's cases, then the script's
idc/bin/idc idc/tools/idrun -o idc/bin/idrun
printf '#!/usr/bin/env idrun\nmain(int argc, string[] argv) {\n} return int 7;\n(1, ["x"]):(7)\n(2, ["x", "y"]):(7)\n' > hello.id
PATH=$PWD/idc/bin:$PATH ./hello.id; echo $?          # 7
```

## Translating C to id

`c2id/` is a C-to-id compiler written in id. `c2id/tools/c2id.sh prog.c DIR`
preprocesses `prog.c` (`cc -E`, with `c2id/include/` as the only system header
path), translates it, and writes an id project to `DIR`. `idc DIR -o prog`
builds it. `C2ID_CPPFLAGS` carries the program's own `-I` and `-D` flags.

The translation is faithful and slow. C memory becomes one flat bounds-checked
byte store (`alloc`, `peek8..64`, `poke8..64`). Every C function becomes a set
of one-basic-block id functions that return the next block number, driven by a
dispatch tree. Frames live on a software stack. libc comes from `c2id/crt/`
and `c2id/rt/`.

### Corpus

Each program is preprocessed, translated, built with idc and run; stdout and
exit status are compared with the same source built by `gcc -O2`.

| program | C LoC | translated | builds | matches gcc | first failure |
|---|---|---|---|---|---|
| tests/c 010_arith | 13 | yes | yes | yes | - |
| tests/c 020_bitwise | 12 | yes | yes | yes | - |
| tests/c 030_control | 29 | yes | yes | yes | - |
| tests/c 040_pointers | 22 | yes | yes | yes | - |
| tests/c 050_structs | 23 | yes | yes | yes | - |
| tests/c 060_funcptr | 15 | yes | yes | yes | - |
| tests/c 070_recursion | 15 | yes | yes | yes | - |
| mt1 (micro) | 56 | yes | yes | yes | - |
| mt2 (micro) | 32 | yes | yes | yes | - |
| inih | 530 | yes | yes | yes | - |
| libmd md5 | 3433 | yes | yes | yes | - |
| libmd sha1 | 3433 | yes | yes | yes | - |
| libmd sha2 | 3433 | yes | yes | yes | - |
| xxhash | 7345 | yes | yes | yes | - |
| lz4 | 3728 | yes | yes | yes | - |
| miniz tinfl | 2297 | yes | yes | yes | - |
| cJSON | 3512 | yes (385 files) | no | - | float code: `double` arithmetic, `fabs`, `strtod`, `sscanf` need a float model; idc reports 10 errors, the first `unexpected token ')'` |

sqlite3 and a zlib program were not tried. LoC counts the program's own
`.c`/`.h` files, not the preprocessed text.

### What broke in the baseline, and what was fixed

The checked-in c2id no longer built under the current idc. Failure classes, in
the order they appeared:

1. Accessors that differ only in an imported value are rejected by the
   uniqueness rule (36 errors). Inlined; where a case named the accessor it was
   kept.
2. Cases reading an export their function just declared need
   `return void export NAME`, and cases that read a never-written export are
   rejected. Added the clause to the `init_*` family, replaced vacuous checks.
3. A string cannot hold NUL, so `str_of_mem` over padded buffers trapped.
   `slice` now measures with `buf_zlen`.
4. The generated project broke the layout rules: same-name directories,
   numbered siblings, more than 3 entries per directory, more than 3 actions
   per block, duplicate block bodies. The emitter now writes letter-coded
   directories to depth 8, splits long blocks with a chain, and gives each
   chain segment its own tag literal.
5. Initializer lists, constant expressions over casts and `!`, static local
   unsized arrays, parameter names, enums in constant expressions, void
   ternary arms (`assert`) and compiler builtins were unsupported or wrong.
   Fixed in `front/parse`, `front/fold`, `mid/lower`, `back/link`; builtins are
   handled by `__has_builtin` being forced to 0 and by `rt/ext/builtin`.
6. Frame renaming mis-scoped declaration-only blocks and `for` initializers,
   giving wrong results for nested loops.
7. Missing libc: `rt/` adds `printf` family, `fputs`, `sprintf`/`snprintf`,
   `calloc`, `exit`/`abort`, ctype, read-only `fopen`/`fgets`, `fwrite`,
   `bswap`, `ctz`, `clz`.

The seven programs in `c2id/tests/c` all pass.

### Performance against gcc -O2

Wall time, one run each, same input, benchmark drivers in the corpus
(`bench_md5`, `bench_xxh`, `bench_lz4`):

| program | gcc -O2 | translated | ratio |
|---|---|---|---|
| md5 | 0.005 s | 0.377 s | 75x |
| xxhash | 0.002 s | 0.354 s | 177x |
| lz4 | 0.007 s | 1.285 s | 183x |

idc `-O0`, `-O1`, `-O2` and `-O3` give 1.10 to 1.18 s user on the lz4 build:
the optimizer level changes nothing measurable, so the cost is in the shape of
the generated code, not in missed optimizations. (The three runs above are
wall time of different builds from the table; the `-O` comparison is user time
of one build.)

Static shape of the lz4 project: 338 files, 9748 lines; 472 block functions and
435 dispatch-tree nodes; 1891 tag lines against 2027 temporaries; 1249 peek and
631 poke lines; 562 sign/zero-extension lines. Compiling the same project with
`--emit-c` and `-O2 -fno-inline` took 8.2 s against about 2 s with inlining, so
generated code depends on the C compiler inlining one-block functions.

Sources of overhead, ranked by what the generated code contains, not by a
profile (gprof produced no profile, so the ranking is a guess to confirm with
`perf`):

1. One function call per basic block plus a dispatch tree to pick it. A
   C function with 472 blocks pays tree depth in calls per executed block.
2. Flat memory model: every local lives in the software stack frame, so each
   variable read or write is a `peek`/`poke` with a bounds check, not a
   register.
3. Multi-byte peek/poke are byte loops with a bounds check each.
4. 32-bit C `int` semantics are emulated on 64-bit `word`: a sign or zero
   extension after most arithmetic.
5. Per-segment tag literals and `__tmp` temporaries added to satisfy the
   uniqueness and 3-actions rules.

### id blockers

Where id's own rules made faithful translation impossible or costly:

- No float-to-word or word-to-float bit-cast, and no `double` in the flat byte
  store. `double` fields, `strtod`, `sscanf("%lf")` cannot be translated
  faithfully; cJSON stops here. Fixing it needs a design decision (soft-float
  in crt, or a bit-cast builtin).
- Strings cannot contain NUL, so `str_of_mem` and `chr(0)` trap. All C buffers
  stay as byte memory and every string function is reimplemented over it.
- `len(string)` is `strlen` and concatenation never frees: emitted text work
  is quadratic and the translator needs `ulimit -v` guarding.
- At most 3 actions per block and nesting depth 2: every C basic block with
  more than 3 statements is a chain, with a unique tag per segment to dodge the
  duplicate-logic rule. This is the largest source of generated lines.
- A call may not be an argument to a call, and a return clause is a name or a
  literal: every nested C expression is flattened into temporaries.
- One name has one type program-wide, including locals against exports: C
  locals named `l`, `s`, `n` collide with translator variables, and the frame
  pass renames locals to `name__N`.
- At most 3 functions per file and 3 entries per directory: a 3500-line C
  program becomes 385 files in 8 directory levels.
- No `exit` builtin: `exit()` and `abort()` are emulated with a status word
  that unwinds the runner loop.
- Function pointers have no id equivalent that holds a C address: a pointer is
  the function index plus one, called through generated dispatch trees.
- Cases need a `given` that composes setups; a fixture for each new emitter
  function costs more lines than the function.

### Status and gaps

- Cases: every function in `c2id/c2id` now has two, and `idc c2id/c2id` builds
  under the default test requirement. Writing the 213 that were missing found
  three `str_slice` calls written for an older idstd (`c2id/docs/STATUS.md`).
- No wasm or llvm target was tried on generated code.
- The compiler test sections of `idc/tests/run.sh` were not run; no compiler
  source was changed.
