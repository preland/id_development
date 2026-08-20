# The `id` language

`id` is a small C-flavored language. This repo contains its first program
(`demos/hello`) and `idc`, a compiler that transpiles `id` to C and invokes the
system C compiler. `idc` is **self-hosted**: its lexer and parser/C-emitter are
themselves written in `id` (`demos/idc_in_id`, `demos/idc_in_id_parse`), and
`bin/idc` is the driver that makes that self-hosted compiler a usable command.

## Quick start

`bin/idc`, the **primary** way to build `id` programs, takes exactly one
argument: a single `.id` file, or a **project directory**.

```sh
bin/idc demos/hello        # build the hello_world project
./build/hello              # usage: ./build/hello <message>
./build/hello hi           # hello world: hi
tests/run.sh               # regression suite
```

A **project** is a directory *tree*: every directory in it may hold at most 3
entries (counting `.id` files and subdirectories combined), and *all* the `.id`
files in the tree are compiled together as one program, so functions and
exported variables resolve across the whole project. With no `-o`, the output is
named after the project directory and written into `build/`, which is
`.gitignore`d — built binaries never land in the source tree:

```sh
bin/idc demos/adventure    # builds ./build/adventure from the whole project tree
./build/adventure
```

`-o` overrides both the name and the directory: `bin/idc demos/hello -o /tmp/hi`.

A single file is handy for tutorials (`bin/idc prog.id`); a project is how real
programs grow. `bin/idc PATH --emit-c prog.c` writes the generated C instead of
building.

### `bin/idc`: the self-hosted driver, and what it actually does

`bin/idc` is a small bash driver around the self-hosted compiler (`id` itself
has no filesystem/dir-walk/subprocess builtins, so — like every self-hosting
compiler — it needs a bootstrap layer living outside the language; the `fs`
backend below adds *files*, but walking a directory tree is still outside the
language, and walking one is exactly what this driver does). On first
use it builds the two self-hosted stages, `idlex` (lexer) and `idparse`
(parser + C emitter), **using `idc.py`** and caches them under `.idc-cache/`
(rebuilt automatically if their `id` source changes). From then on, building
`PATH` means: collect its `.id` file(s) (a single file, or every `.id` under a
project directory, sorted by full path — the same order `idc.py` uses), run
`cat files | idlex | idparse` to get C, then hand that C to `cc` — exactly the
pipeline `tools/parity.sh` differentially tests against `idc.py`. `-o`,
`--emit-c`, `--keep-c`, `--cc`, and `--backend DIR` (reading `backend.json` and
linking a native backend, mirroring `idc.py`'s `resolve_backend`) all work the
same as in `idc.py`.

**Coverage:** there is no fallback — `bin/idc` drives the self-hosted stages
and nothing else. They implement the whole language and all of its rules: the
action-per-block limit, nesting depth, 3-functions-per-file, name-type
consistency, export/import access, duplicate names, function-logic uniqueness,
the type checks, and calls that resolve to nothing. Every case in
`tests/invalid/` is checked against **both** compilers and must produce the
same diagnostic, so a message `idc.py` gives and `bin/idc` does not is a test
failure. `bin/idc` also gates on `cc -fsyntax-only` before trusting its own
output; if that ever fires it means a bug in the compiler, and it says so.

The one rule checked in the driver rather than in `id` is the
3-entries-per-directory limit — it is a property of the filesystem, which `id`
cannot see, which is also why the driver exists.

What only `idc.py` still does: `--target llvm` and `--target wasm`. See
[`docs/GAPS.md`](docs/GAPS.md) for the state of that and everything else.

## Development environment (Nix)

Building the C target needs only a C compiler. The **graphics backends**
(`--backend backends/gfx|gl`) link native system libraries (OpenGL, X11), and
the **`--target llvm|wasm`** paths need `clang`/`llc`/`wat2wasm`/`wasmtime`. On
NixOS these aren't on the default search path, so the repo ships a
[`flake.nix`](flake.nix) providing the whole toolchain in one dev shell:

```sh
nix develop              # drop into a shell with cc, X11/OpenGL, llvm, wasm tools
# or, with direnv (a .envrc is included):
direnv allow             # auto-enters the dev shell on cd into the repo
```

`tools/devshell.sh '<cmd>'` runs a single command in that same shell (it uses
the flake, falling back to `nix-shell -p …`), which is how the graphics/alt-target
builds and `tests/run.sh` are driven:

```sh
tools/devshell.sh 'bin/idc demos/gl3d --backend backends/gl -o gl3d' && ./gl3d
```

On a non-Nix system with the usual dev packages installed (e.g. `libgl-dev`,
`libx11-dev`, `clang`, `wabt`, `wasmtime`), the plain commands work without any
wrapper.

## Language rules (as stated in hello_world.id)

- **`main` is the entrypoint.** `main(int argc, string[] argv)` receives the
  command-line arguments; its `int` return becomes the process exit code.
- **The `return` clause comes after the function's closing brace** and names
  the returned type: `} return int 0;`, `} return string result;`, or
  `} return void;`. It may reference variables declared in the body.
- **3-action limit per block.** *Every* block — the function body and the body
  of each `if`, `else`, and `while` — may perform at most 3 actions. Each
  statement is one action; an `if` is one and each chained `else` is another; a
  `while` is one. The `return` clause is free. (Bodies are **not** free: a
  branch or loop body has its own 3-action budget.)
- **Maximum nesting depth of 2.** Blocks may nest at most two deep; code below
  that must be split into its own function. Together with the 3-action rule this
  keeps every function shallow and small — deep dispatch is expressed as a chain
  of named functions, not a pyramid of nested branches (see `demos/idc_in_id`).
- **A name keeps one type.** A variable name may be reused across functions, but
  every declaration of it (parameters included) must have the *same* type —
  `i` is always an `int`, `src` always a `string`. Declaring one name with two
  different types anywhere in the same source tree is a compile error. A name is
  one variable *within* a function. (This prevents a vague name like `obj`
  meaning different things in different places, while still letting natural
  names like `i` or `src` recur.) The rule stops at the import boundary: your
  tree and each imported tree (the standard library, a library) are separate
  compilation units, so a library's `string s` does not make `int s` an error in
  your program.
- **Variables are function-private unless exported.** `export int value = …;`
  declares and publishes a variable; other functions read it with
  `(import value)`. Touching another function's variable any other way is a
  compile error. An exported name is **reserved program-wide**: no other
  variable may use that name — the only way to reach it is `import`.
- **Maximum of 3 functions per file**, and **at most 3 entries per directory**
  (counting `.id` files and subdirectories). Programs grow not by growing files
  or cluttering folders, but by adding files and nesting subdirectories — a
  project is a tree where every level stays small. The same "rule of 3" as the
  3-action block limit, applied to the file system.
- **Functions must be unique.** Two functions with the same signature (parameter
  types and return type) and the same logic are a compile error, even under
  different names and even if their parameters and locals are spelled
  differently. Bodies are compared up to a consistent renaming of each
  function's own parameters and locals; what carries real meaning — operators,
  literals, and the names of called functions, imported globals, and exported
  variables — must differ for two functions to coexist. This keeps names
  meaningful and stops the same behavior from being written twice; if you need
  it in two places, give it one name and call it.

## Rules the example implies (decisions made by this compiler)

These behaviors are visible in `hello_world.id` but never stated; `idc`
resolves them as follows — revisit as the language evolves:

- **`=` in an expression means equality.** Line 23 compares with
  `(import value) = 0`. Since assignment is only a statement form, a bare `=`
  inside an expression is unambiguous and compiles to `==`. (`==` and `!=`
  also work.)
- **Semicolons are optional.** Line 6 omits one. `idc` treats `;` as an
  optional statement terminator everywhere.
- **Functions link across files implicitly.** `testfn()` calls `otherfn()`,
  defined in a separate file of the same project — and the export/import rule
  is stated only for *variables*. So function calls resolve across every file in
  the project automatically; a call with no definition anywhere in the project
  is a warning and must be satisfied at link time (see `demos/hello`, which
  bundles `otherfn.id`).
- **Array literals**: `["hello_world", "hi"]` builds a `string[]`.
- **`+` on strings concatenates**, and a numeric operand mixed with a string
  is converted (`"lucky " + 7` → `"lucky 7"`).
- **Variables are function-scoped, not block-scoped** — `processresult`'s
  `processed` is assigned inside `if`/`else` branches and returned after the
  brace, so declarations are hoisted to function scope.
- **Types**: `int`, `float`, `string`, `void`, and arrays `T[]`. They map to
  C `int`, `double`, `char*`, `void`, and pointers respectively.
- **`print(x)`** is a builtin that prints any value followed by a newline.
- **`input()`** is a builtin that reads one line from stdin and returns it as a
  `string` (the trailing newline is stripped; end-of-input yields `""`). It
  takes no arguments. Branch on the result with ordinary string comparison —
  see `demos/adventure`, a choose-your-own-adventure that selects paths by the
  index the player types.
- **`while (cond) { ... }`** loops while `cond` (an `int`) is nonzero. The loop
  is one action; its body is free, like a branch body.
- **String/IO builtins:** `len(s)` returns a string's length; `charat(s, i)`
  returns the byte code at index `i` (or `-1` past the end); `chr(n)` builds a
  one-character string from a byte code; `read_all()` reads all of stdin into
  one `string`; `to_int(s)` parses a string to an `int`. Together with `while`
  these make text processing possible — see `demos/idc_in_id`, a lexer for `id`
  **written in `id`**.
- **Growable lists.** A `T[]` is a heap-allocated, growable list with
  **reference semantics** — passing one to a function and mutating it is visible
  to the caller (this is how `id` gets shared mutable state). Operations:
  `[a, b, c]` builds a list and `[]` makes an empty one (in a typed context);
  `xs[i]` reads an element and `xs[i] = v` writes one; `push(xs, v)` appends;
  `len(xs)` is the length. An AST or symbol table is built as a few parallel
  lists indexed by an integer id — see `demos/idc_in_id/BLOCKERS.md`,
  `demos/idc_in_id_calc` (an expression parser + evaluator written in `id`), and
  `demos/idc_in_id_parse` (a parser for `id` functions and statements **plus a C
  emitter** — lex → parse → emit C, all written in `id`, with the emitted C
  compiled by `cc` and run).
- **List ops also include `pop(xs)`** — remove and return the last element (the
  complement of `push`).
- **Real-time terminal I/O.** Beyond `print`/`input`/`read_all`, `id` has the
  builtins a game loop needs: `put(s)` writes without a trailing newline,
  `flush()` flushes stdout, `getkey()` polls one key **without blocking**
  (`-1` if none; raw mode is entered lazily and restored at exit),
  `sleep_ms(n)` sleeps, and `ticks()` returns monotonic milliseconds. On these,
  `demos/engine` is a small full-screen game engine, and `demos/moonbuggy`
  (a real-time side-scroller) and `demos/solitaire` (Klondike) are games
  **written in `id`**.
- **No file I/O among the builtins.** The list above is the whole of it: a
  program gets stdin and stdout, so working on a file means being a filter and
  letting the caller pick them (`./prog < in.txt > out.txt`). Files come from a
  **native backend** instead — [`backends/fs`](backends/fs) links `fs_open`,
  `fs_read`, `fs_write`, `fs_close`, `fs_size`, `fs_exists`, `fs_remove` and
  `fs_error` at link time, and `demos/fsdemo` writes a file, reads it back and
  removes it in ~40 lines of `id` that never name C.

## The standard library (`idstd`)

`idstd` is `id`'s standard library, and it is **imported by default**: a program
calls `fx_max` with no `import.id` line and no flag. It lives in its own
repository, beside this one.

```sh
bin/idc prog.id                  # idstd is already there
bin/idc prog.id --no-std         # build without it
bin/idc prog.id --std ../idstd   # build against a particular one
```

It is resolved from, in order: `--std DIR`, `$IDSTD_HOME`, then an `idstd`
directory beside this repository. A checkout with none of those simply has no
standard library, which is not an error — the compiler has to keep building its
own bootstrap in a tree where the library does not exist. `IDC_NO_STD=1` is
`--no-std` for scripts that cannot pass a flag.

The library is merged exactly like a source dependency named in an `import.id`:
the same 3-entries-per-directory rule applies to it, and its own `import.id` is
followed, so a stdlib module that needs a native backend declares it once
instead of every program naming it.

**Three things must build without it, and do.** `idstd` cannot import itself;
the bootstrap stages (`demos/idc_in_id{,_parse}`) define their own helpers and
any change to their emitted C would break self-hosting, so `bin/idc` bootstraps
them with `--no-std`; and `tests/invalid/`'s diagnostics must not shift because
a library appeared in the program.

**Dead code is not emitted.** Only functions reachable from `main` reach the
generated C — which is what makes a library that is in every program
affordable. Measured on a synthetic 729-function library where the program
calls one function:

| | build | binary |
| --- | --- | --- |
| no stdlib | 0.318 s | 16 408 B |
| 729-function stdlib, before elimination | 0.75 s | 74 584 B |
| 729-function stdlib, after | 0.325 s | 16 448 B |

A project with no `main` is a library, compiles to a `.o`, and keeps every
function — all of them are entry points. And **dead code is still checked**: a
function nothing calls still obeys the action limit, the nesting limit and the
export rules. Code that stopped being checked because nothing called it is how
a library rots, and it would stop checking a user's own dead code too.

See [`docs/IDSTD.md`](docs/IDSTD.md) for what the library contains and what is
still outstanding.

## Native backends

A **backend** is a directory with a `backend.json` and some native source. It
supplies functions no `.id` file defines; `idc` resolves those calls as
link-time symbols and links the backend's objects into the program. Attach one
with a project's `import.id` (preferred) or a `--backend DIR` flag.

**Imports are transitive.** An imported directory's own `import.id` is read too,
so a library can declare the backend it needs and every program that uses it
gets one. Cycles and diamonds terminate — each directory is visited once, keyed
on its resolved path.

| backend | what it adds |
| --- | --- |
| [`backends/fs`](backends/fs) | files: open/read/write/close/size/exists/remove. Needs no system libraries |
| [`backends/gfx`](backends/gfx) | a window and a software framebuffer (X11 / Cocoa) |
| [`backends/gl`](backends/gl) | a hardware-accelerated OpenGL window |

The manifest separates *what* a backend promises from *how* a given compiler
obtains it: `abi` lists the functions in `id`'s own types, and `targets` maps a
code generator (`"c"` today; an LLVM, wasm or interpreter target tomorrow) to
the implementation it should use. Adding a target is a change to the manifest
and the driver that reads it, never to a program's `id` source — see
[`backends/fs/README.md`](backends/fs/README.md), which is written up as the
worked example. `gfx` and `gl` predate `targets` and carry a bare `platforms`
table, which is read as the C target's.

## Self-hosting

The `id`-written compiler (`demos/idc_in_id` lexer + `demos/idc_in_id_parse`
parser/codegen) **compiles its own source** to C that is byte-identical to
`idc.py`, and the self-compiled binary reproduces itself exactly (a fixpoint).
`tests/run.sh` checks both. See `demos/idc_in_id_parse/README.md`. `bin/idc`
is the driver that turns this pair of self-hosted binaries into `id`'s
primary build command — see "`bin/idc`: the self-hosted driver" above.

## The compiler: one implementation, and a bootstrap being retired

**`idc.py` is on its way out, as fast as the work can be done.** It is not a
second supported compiler, not a fallback, and not a place to add anything. The
goal is deleting it. Everything below describes what still holds it here, and
each of those is a task, not a feature —
[`docs/BACKENDS.md`](docs/BACKENDS.md) tracks the order.

Until then it is the original, self-contained Python implementation: lexer →
recursive-descent parser → semantic checks (action limit, function-per-file
limit, project entry-count limit, global name uniqueness, function-logic
uniqueness, export/import access, light type checking) → C/LLVM/WASM emission
→ `cc`/`clang`/`wat2wasm`. It is **stage 0 of the bootstrap**, with two jobs
left:

1. **Bootstrapping** the self-hosted stages (`idlex`, `idparse`) that `bin/idc`
   caches and drives — see above. This happens once, on a cold cache.
2. **The alternative codegen targets**, `--target llvm` and `--target wasm`
   (and their `--emit-llvm`/`--emit-wasm`) — only `idc.py` implements these;
   `bin/idc` only drives the C target.
   [`docs/BACKENDS.md`](docs/BACKENDS.md) is the plan for moving them across.

It is also where the **C runtime prelude** lives, as one string that both
compilers emit verbatim; `tools/gen_runtime_id.py` regenerates the `id`-side
copy from it, so a runtime change is made in one place and parity keeps the two
honest.

**It is not where language features are built**, and a change that grows it is
a change in the wrong direction. "Reference implementation" is what this
section used to call it, and that reading — *the definition of correct, so
define the feature here and port it* — is why work kept landing in Python
instead of in `id`. Stage 0 needs a construct only once the self-hosted
compiler's own source uses that construct. Read
[`docs/HACKING.md`](docs/HACKING.md) before changing the language;
[`demos/idc_in_id_parse/MAP.md`](demos/idc_in_id_parse/MAP.md) is the index
that makes the self-hosted tree navigable, which was the other half of the
problem.

**`bin/idc`** (see "Quick start" above) is the **primary** way to build a
program: it drives the self-hosted `idlex`/`idparse` pair and does not fall
back. It enforces every rule of the language, and its diagnostics are checked
against `idc.py`'s, case by case, by `tests/invalid.sh`.

Generated code details (true of both implementations — the self-hosted
emitter mirrors these byte-for-byte where it's implemented at all):

- `id` functions are prefixed `id_` in C (so `id` `main` becomes `id_main`,
  wrapped by a real C `main`). Exported variables become C globals.
- A project without a `main` compiles to a `.o` object file (e.g. a library
  like `demos/engine`).
- String concatenation allocates and never frees; fine for now, a real
  runtime would need ownership rules or GC.
