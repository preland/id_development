# The `id` language

`id` is a small C-flavored language. This repo contains its first program
(`hello_world.id`) and `idc`, a compiler that transpiles `id` to C and invokes
the system C compiler.

## Quick start

```sh
./idc.py hello_world.id examples/otherfn.id -o hello_world
./hello_world          # usage: ./hello_world <message>
./hello_world hi       # hello world: hi
tests/run.sh           # regression suite
```

`./idc.py prog.id --emit-c prog.c` writes the generated C instead of building.
All input files are compiled together as one program.

## Language rules (as stated in hello_world.id)

- **`main` is the entrypoint.** `main(int argc, string[] argv)` receives the
  command-line arguments; its `int` return becomes the process exit code.
- **The `return` clause comes after the function's closing brace** and names
  the returned type: `} return int 0;`, `} return string result;`, or
  `} return void;`. It may reference variables declared in the body.
- **3-action limit per function.** Each top-level statement is one action; an
  `if` is one action and each `else` is another. Statements nested inside
  branches are free, and the `return` clause is free. Exceeding the limit is a
  compile error.
- **Variable names are unique and global.** Declaring the same variable name
  in two functions (parameters included) is a compile error, program-wide.
- **Variables are function-private unless exported.** `export int value = …;`
  declares and publishes a variable; other functions read it with
  `(import value)`. Touching another function's variable any other way is a
  compile error.
- **Maximum of 3 functions per file.** Programs grow by adding files, not by
  growing files.

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
  which no file in the original program defines — and the export/import rule
  is stated only for *variables*. So function calls resolve across all input
  files automatically; a call with no definition anywhere is a warning and
  must be satisfied at link time (see `examples/otherfn.id`).
- **Array literals**: `["hello_world", "hi"]` builds a `string[]`.
- **`+` on strings concatenates**, and a numeric operand mixed with a string
  is converted (`"lucky " + 7` → `"lucky 7"`).
- **Variables are function-scoped, not block-scoped** — `processresult`'s
  `processed` is assigned inside `if`/`else` branches and returned after the
  brace, so declarations are hoisted to function scope.
- **Types**: `int`, `float`, `string`, `void`, and arrays `T[]`. They map to
  C `int`, `double`, `char*`, `void`, and pointers respectively.
- **`print(x)`** is a builtin that prints any value followed by a newline.

## The compiler

`idc.py` is a self-contained Python program: lexer → recursive-descent parser
→ semantic checks (action limit, function-per-file limit, global name
uniqueness, export/import access, light type checking) → C emission → `cc`.

Generated code details:

- `id` functions are prefixed `id_` in C (so `id` `main` becomes `id_main`,
  wrapped by a real C `main`). Exported variables become C globals.
- A file set without a `main` compiles to a `.o` object file for later linking.
- String concatenation allocates and never frees; fine for now, a real
  runtime would need ownership rules or GC.
