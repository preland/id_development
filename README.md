# The `id` language

`id` is a small C-flavored language. Its compiler, `idc`, transpiles `id` to C
and invokes the system C compiler; `idc` is **self-hosted** — its lexer and
parser/C-emitter are themselves written in `id` (`idc/compiler/lex`,
`idc/compiler/parse`), and `idc/bin/idc` is the driver that makes that
self-hosted compiler a usable command.

This is the **umbrella repository**. It holds the docs, the demos, and the
Nix devshell directly; the toolchain and the programs written against it are
git submodules, each its own repository.

## Repository map

| path | what it is |
| --- | --- |
| [`docs/`](docs) | the specification and design docs (18 files — see "Further reading" below) |
| [`demos/`](demos) | example `id` programs |
| `flake.nix`, `.envrc` | the Nix devshell |
| [`idc/`](idc) (submodule) | the toolchain: `bin/idc`, the self-hosted compiler, the bootstrap, `idc.py`, the native backends, the dev tools, and the test suite — see [`idc/README.md`](idc/README.md) |
| [`editor/`](editor) (submodule) | an OpenDocument editor written in `id` |
| [`kernel/`](kernel) (submodule) | a freestanding kernel written in `id` |
| [`vscode/`](vscode) (submodule) | the VS Code extension for `id` |
| [`c2id/`](c2id) (submodule) | a C-to-`id` compiler, written in `id` |

`idstd`, `id`'s standard library, lives in its own repository beside this one
(`~/git/idstd`) — it is not a submodule. See "The standard library" below.

## Working with the submodules

```sh
git clone --recursive <url>          # clone with every submodule checked out
# or, on an existing clone:
git submodule update --init
```

Each of `idc/`, `editor/`, `kernel/`, `vscode/`, and `c2id/` is its own git
repository with its own history and its own remote; this repository only
records which commit of each it currently points at. Committing inside one of
them is a commit in that submodule's repo, and the umbrella notices it moved.

## Quick start

`idc/bin/idc`, the **primary** way to build `id` programs, takes exactly one
argument: a single `.id` file, or a **project directory**.

```sh
idc/bin/idc demos/hello        # build the hello_world project
./build/hello                  # usage: ./build/hello <message>
./build/hello hi               # hello world: hi
idc/tests/run.sh --list        # the regression suite's sections
```

The suite (`idc/tests/run.sh`) is 85s in total and each section is 6-36s, so
it is run in pieces: `--list` shows the sections, a section name or index runs
just that one, and `--resume` continues after the last one that passed.

A **project** is a directory *tree*: every directory in it may hold at most 3
entries (counting `.id` files and subdirectories combined), and *all* the `.id`
files in the tree are compiled together as one program, so functions and
exported variables resolve across the whole project. With no `-o`, the output is
named after the project directory and written into `build/`, which is
`.gitignore`d — built binaries never land in the source tree:

```sh
idc/bin/idc demos/adventure    # builds ./build/adventure from the whole project tree
./build/adventure
```

`-o` overrides both the name and the directory: `idc/bin/idc demos/hello -o /tmp/hi`.

A single file is handy for tutorials (`idc/bin/idc prog.id`); a project is how
real programs grow. `idc/bin/idc PATH --emit-c prog.c` writes the generated C
instead of building. What `idc/bin/idc` actually does under the hood — the
bootstrap, the cache, the pipeline, and the two code generators — is in
[`idc/README.md`](idc/README.md).

### `conf.id`: what a project depends on, and what it holds constant

A project's root may carry a `conf.id`. It names the directories to compile
alongside this one, and then the constants the program should be built with:

```
import "../mylib"
import "../../backends/fs"

int max_depth = 7;
int fanout = 3;
```

Imports come first; a constant is a `TYPE name = value;` line after them, and an
import that follows one is an error. A constant becomes an ordinary exported
global — read it with `(import max_depth)`, and no other variable may take that
name — except that it needs no function to initialise it. It is emitted at file
scope with its value attached, so it holds it before `main` runs, which is
exactly what an `export` inside a function body cannot promise.

Only a *root's* `conf.id` is read as a manifest; the name is reserved and a
file called `conf.id` anywhere else is rejected rather than silently ignored.

### Two programs the language was stretched against

`id` also builds **freestanding**: no libc, no C runtime, nothing linked that
wasn't compiled from `id` source.

**[`kernel/`](kernel) (submodule) is a kernel with a graphical shell.** It
boots under QEMU, sets a framebuffer mode through PCI and the Bochs VBE ports,
draws an 80x30 console with an 8x16 font, reads the PS/2 keyboard, and runs a
shell over an in-memory filesystem — `ls`, `cd`, `cat`, `write`, `uname`. A
fault names itself and stops the machine. [`docs/KERNEL.md`](docs/KERNEL.md).

```sh
idc/tools/devshell.sh 'idc/tools/kbuild.sh'
qemu-system-x86_64 -kernel idc/build/kernel.elf -serial stdio -display none
```

**[`editor/`](editor) (submodule) reads an OpenDocument file and draws it.**
A ZIP holding XML: inflate, parse, resolve the styles, read a TrueType font,
turn glyph outlines into anti-aliased coverage, break lines against a page
width. [`docs/EDITOR.md`](docs/EDITOR.md).

```sh
idc/bin/idc editor -o editor && ./editor doc.odt font.ttf --ppm page.ppm
```

To watch either of them rather than test it -- a window, a shell to type at, a
rendered page -- see [`docs/RUNNING.md`](docs/RUNNING.md).

Both are tested rather than eyeballed. `idc/tools/fbtext.py` reads the
kernel's framebuffer back as text by matching each cell against the kernel's
own font, so a console that wrote to the serial port and drew nothing fails;
the editor's five suites check every module against a reference computed at
test time.

**What they were for** is [`docs/FRICTION.md`](docs/FRICTION.md): twenty-two
places where the language costs more than it should, each naming the code that
hit it — and the four rules that cost something and caught something, which is
the difference worth keeping.

What only `idc.py` still does: `--target wasm`. See
[`docs/GAPS.md`](docs/GAPS.md) for the state of that and everything else, and
[`idc/README.md`](idc/README.md) for `idc.py`'s retirement.

## Development environment (Nix)

Building the C target needs only a C compiler. The **graphics backends**
(`--backend idc/backends/gfx|gl`) link native system libraries (OpenGL, X11),
and the **`--target llvm`** and **`--target wasm`** paths need
`clang`/`llc`/`wat2wasm`/`wasmtime`, and the kernel needs `ld.lld` and
`qemu-system-x86_64`. On
NixOS these aren't on the default search path, so the repo ships a
[`flake.nix`](flake.nix) providing the whole toolchain in one dev shell:

```sh
nix develop              # drop into a shell with cc, X11/OpenGL, llvm, wasm tools
# or, with direnv (a .envrc is included):
direnv allow             # auto-enters the dev shell on cd into the repo
```

`idc/tools/devshell.sh '<cmd>'` runs a single command in that same shell (it
uses the flake, falling back to `nix-shell -p …`), which is how the
graphics/alt-target builds and `idc/tests/run.sh` are driven:

```sh
idc/tools/devshell.sh 'idc/bin/idc demos/gl3d --backend idc/backends/gl -o gl3d' && ./gl3d
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
  of named functions, not a pyramid of nested branches (see `idc/compiler/lex`).
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
  these make text processing possible — see `idc/compiler/lex`, a lexer for
  `id` **written in `id`**.
- **Growable lists.** A `T[]` is a heap-allocated, growable list with
  **reference semantics** — passing one to a function and mutating it is visible
  to the caller (this is how `id` gets shared mutable state). Operations:
  `[a, b, c]` builds a list and `[]` makes an empty one (in a typed context);
  `xs[i]` reads an element and `xs[i] = v` writes one; `push(xs, v)` appends;
  `len(xs)` is the length. An AST or symbol table is built as a few parallel
  lists indexed by an integer id — see `idc/compiler/lex/BLOCKERS.md`,
  `demos/idc_in_id_calc` (an expression parser + evaluator written in `id`), and
  `idc/compiler/parse` (a parser for `id` functions and statements **plus a C
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
  **native backend** instead — [`idc/backends/fs`](idc/backends/fs) links
  `fs_open`, `fs_read`, `fs_write`, `fs_close`, `fs_size`, `fs_exists`,
  `fs_remove` and `fs_error` at link time, and `demos/fsdemo` writes a file,
  reads it back and removes it in ~40 lines of `id` that never name C. See
  [`idc/README.md`](idc/README.md) for how a backend attaches.

## The standard library (`idstd`)

`idstd` is `id`'s standard library, and it is **imported by default**: a program
calls `fx_max` with no `conf.id` line and no flag. It lives in its own
repository, beside this one.

```sh
idc/bin/idc prog.id                  # idstd is already there
idc/bin/idc prog.id --no-std         # build without it
idc/bin/idc prog.id --std ../idstd   # build against a particular one
```

It is resolved from, in order: `--std DIR`, `$IDSTD_HOME`, then an `idstd`
directory beside this repository. A checkout with none of those simply has no
standard library, which is not an error — the compiler has to keep building its
own bootstrap in a tree where the library does not exist. `IDC_NO_STD=1` is
`--no-std` for scripts that cannot pass a flag.

The library is merged exactly like a source dependency named in a `conf.id`:
the same 3-entries-per-directory rule applies to it, and its own `conf.id` is
followed, so a stdlib module that needs a native backend declares it once
instead of every program naming it.

**Three things must build without it, and do.** `idstd` cannot import itself;
the bootstrap stages (`idc/compiler/lex{,_parse}`) define their own helpers and
any change to their emitted C would break self-hosting, so `idc/bin/idc`
bootstraps them with `--no-std`; and `idc/tests/invalid/`'s diagnostics must
not shift because a library appeared in the program.

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

## Further reading

`docs/` holds 18 files. The toolchain internals — native backends, the two
code generators, self-hosting, `idc.py`'s retirement — are in
[`idc/README.md`](idc/README.md) instead of here.

| doc | what it covers |
| --- | --- |
| [`SPEC.md`](docs/SPEC.md) | the language specification — normative and executable |
| [`TUTORIAL.md`](docs/TUTORIAL.md) | writing your first `id` program |
| [`TESTS.md`](docs/TESTS.md) | tests as part of a function's definition |
| [`KERNEL.md`](docs/KERNEL.md) | the kernel and the runtime under it |
| [`EDITOR.md`](docs/EDITOR.md) | the document editor |
| [`LLVM.md`](docs/LLVM.md) | the LLVM target and the IR it is printed from |
| [`BACKENDS.md`](docs/BACKENDS.md) | making the self-hosted compiler backend-agnostic |
| [`IDSTD.md`](docs/IDSTD.md) | the standard library — handoff brief |
| [`GAPS.md`](docs/GAPS.md) | what still stands between `bin/idc` and being the only compiler |
| [`FRICTION.md`](docs/FRICTION.md) | where `id` costs more than it should, with evidence |
| [`HACKING.md`](docs/HACKING.md) | changing the language |
| [`TODO.md`](docs/TODO.md) | the maintained-by-hand list of what's left |
| [`RELIANCES.md`](docs/RELIANCES.md) | where this project is not written in `id` |
| [`RUNNING.md`](docs/RUNNING.md) | running the kernel and the editor |
| [`ASM.md`](docs/ASM.md) | `asm` functions |
| [`DISPATCH.md`](docs/DISPATCH.md) | calling a function chosen at run time (a proposal, unimplemented) |
| [`STRUCTS.md`](docs/STRUCTS.md) | records in `id` (a proposal, unimplemented) |
| [`HYPRLAND.md`](docs/HYPRLAND.md) | running the graphics demos without losing your place, for one compositor |
