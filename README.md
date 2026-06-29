# The `id` language

`id` is a small C-flavored language. This repo contains its first program
(`demos/hello`) and `idc`, a compiler that transpiles `id` to C and invokes the
system C compiler.

## Quick start

`idc` takes exactly one argument: a single `.id` file, or a **project
directory**.

```sh
./idc.py demos/hello -o hello    # build the hello_world project
./hello                          # usage: ./hello <message>
./hello hi                       # hello world: hi
tests/run.sh                     # regression suite
```

A **project** is a directory *tree*: every directory in it may hold at most 3
entries (counting `.id` files and subdirectories combined), and *all* the `.id`
files in the tree are compiled together as one program, so functions and
exported variables resolve across the whole project. With no `-o`, the output is
named after the project directory:

```sh
./idc.py demos/adventure    # builds ./adventure from the whole project tree
./adventure
```

A single file is handy for tutorials (`./idc.py prog.id`); a project is how real
programs grow. `./idc.py PATH --emit-c prog.c` writes the generated C instead of
building.

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
  different types anywhere in the program is a compile error. A name is one
  variable *within* a function. (This prevents a vague name like `obj` meaning
  different things in different places, while still letting natural names like
  `i` or `src` recur.)
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

## Self-hosting

The `id`-written compiler (`demos/idc_in_id` lexer + `demos/idc_in_id_parse`
parser/codegen) **compiles its own source** to C that is byte-identical to
`idc.py`, and the self-compiled binary reproduces itself exactly (a fixpoint).
`tests/run.sh` checks both. See `demos/idc_in_id_parse/README.md`.

## The compiler

`idc.py` is a self-contained Python program: lexer → recursive-descent parser
→ semantic checks (action limit, function-per-file limit, global name
uniqueness, export/import access, light type checking) → C emission → `cc`.

Generated code details:

- `id` functions are prefixed `id_` in C (so `id` `main` becomes `id_main`,
  wrapped by a real C `main`). Exported variables become C globals.
- A project without a `main` compiles to a `.o` object file (e.g. a library
  like `demos/engine`).
- String concatenation allocates and never frees; fine for now, a real
  runtime would need ownership rules or GC.
