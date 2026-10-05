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
