# Starting a project

> **Status: current.** Every command and every error message below was run
> against this tree on the date of the last commit to touch this file. If one
> does not reproduce, that is a bug in this document.

[`TUTORIAL.md`](TUTORIAL.md) teaches the *language* — it writes one program,
`demos/wordcount`, and explains why `id` makes you spread it out. This document
is the other half: the *project*. How a directory becomes a program, where the
binary goes, what a `conf.id` is for, how the standard library gets in, what
happens when you need something the language does not have, and — mostly —
what goes wrong at each of those steps and what the compiler says when it does.

Read `TUTORIAL.md` first if you have never written `id`. Read this when you are
about to start something of your own.

The worked example is a Caesar cipher: text in on stdin, shifted text out.
It is small enough to fit here and large enough to hit six of the traps.

---

## 1. One file

Start with a single file. `idc` takes exactly one path, and a `.id` file is a
valid one.

```
// caesar.id
main(int argc, string[] argv) {
  string text = read_all();
  int i = 0;
  string out = "";
  while(i < len(text)) {
    out = out + shift_one(charat(text, i));
    i = i + 1;
  }
  print(out);
} return int 0;
```

```sh
idc/bin/idc caesar.id --allow-untested -o caesar
```

Every build in this document passes `--allow-untested`. The compiler requires
two test cases per function (§9), and neither this program nor the standard
library it merges has them all yet; the flag is the deprecated way to build
anyway. Each such build prints `idc: warning: --allow-untested is deprecated
and will be removed once every function has its test cases` first, and the
transcripts below leave that line out.

Three errors, and they are worth reading in order:

```
caesar.id:1: error: a block in 'main' performs 5 actions; the limit is 3 (each
  statement, if, else, and while is one action; return is free) -- move some
  statements into a helper function to stay within the limit
caesar.id:6: error: argument 0 of 'shift_one' contains a call; give that value
  a name and pass the name
caesar.id:6: error: no such function 'shift_one'; available builtins: print,
  input, read_all, len, push, pop, to_int, charat, chr, put, flush, getkey,
  sleep_ms, ticks, alloc, store_size, peek8, ...
```

The first is the rule everyone meets first. The third is the last one to fix —
`shift_one` genuinely does not exist yet.

**The second is the one nobody expects.** `shift_one(charat(text, i))` is
rejected: **a call may not appear as an argument to another call.** Not "is
discouraged" — is an error. Every intermediate result gets a name:

```
int c = charat(text, i);
string s = shift_one(c);
```

This is not the 3-action rule in disguise; it is separate, and it is the single
thing that most changes how `id` code looks. Expect roughly one named
temporary per call you would have nested. `demos/fsdemo/end/cleanup.id`
explains the other reason it is a good idea anyway: operands of one expression
are not ordered, so two calls in one expression can run in either order.

> **Pitfall 1.** A call cannot be an argument. Name the value first.

## 2. A directory is a program

Fixing the above means more functions than fit in a file, which means a
directory. A project is a *tree*, every `.id` file in it is compiled together,
and calls resolve across all of them with no imports between your own files.

```
caesar/
├── main.id     main, rotate, rotate_loop
└── shift.id    rotate_step, shift_one, shifted
```

```
// caesar/main.id
main(int argc, string[] argv) {
  string text = read_all();
  string out = rotate(text);
  print(out);
} return int 0;

rotate(string text) {
  string s = "";
  int i = 0;
  s = rotate_loop(text, i, s);
} return string s;

rotate_loop(string text, int i, string s) {
  string r = s;
  while(i < len(text)) {
    r = rotate_step(text, i, r);
    i = i + 1;
  }
} return string r;
```

```
// caesar/shift.id
rotate_step(string text, int i, string r) {
  int c = charat(text, i);
  string out = shift_one(c);
  r = r + out;
} return string r;

shift_one(int c) {
  string out = chr(c);
  if(chr_is_lower(c) == 1) {
    out = shifted(c, 97);
  } else if(chr_is_upper(c) == 1) {
    out = shifted(c, 65);
  }
} return string out;

shifted(int c, int base) {
  int off = c - base + 3;
  int m = off - 26 * (off / 26);
  string out = chr(m + base);
} return string out;
```

```sh
idc/bin/idc caesar --allow-untested
printf 'Attack at dawn!\n' | ./build/caesar
Dwwdfn dw gdzq!
```

Two things happened that were not asked for.

**The binary went to `build/`.** With no `-o`, the output is named after the
project directory and written into `build/`, which is `.gitignore`d — built
binaries never land in the source tree. `-o` overrides both: `-o /tmp/caesar`.
That makes `build/` at a project's root **output, never source**: nothing under
it is compiled and it does not count toward the 3-entry limit, so a tree that
has been built in place compiles exactly as a clean one does. Do not put `.id`
files there.

**`chr_is_lower` and `chr_is_upper` were never defined.** They are `idstd`'s,
and `idstd` is in every build already. See §4.

## 3. The limits, and when they bite

A file holds **at most 3 functions**. A directory holds **at most 3 entries**,
counting `.id` files and subdirectories together. The second is the one that
interrupts you, because it triggers on a directory you were not editing:

```
caesar: error: a project directory may contain at most 3 files and directories
  combined, but this one has 4 (.id files and subdirectories); split it into
  subdirectories
```

The fix is always the same shape — push a pair of files down a level and name
the level after *the stage of work*, not the data type:

```
caesar/
├── conf.id
├── main.id
└── shift/
    ├── shift.id
    └── more/
        └── tail.id
```

Plan for this. A project that will have twelve functions needs three levels,
and deciding what the levels *mean* early is much cheaper than renaming them at
the point the compiler forces the issue. If you find yourself making a
directory called `utils/` you have already lost — it will fill up in a week and
tell you nothing.

> **Pitfall 2.** The entry limit fires on a directory you did not touch, at the
> moment you add one file. Leave room.

**Dead code is still checked.** A function nothing calls is not emitted, but it
still obeys every rule:

```
caesar/dead.id:1: error: a block in 'never_called' performs 4 actions; the
  limit is 3 ...
```

That is deliberate — code that stopped being checked because nothing called it
is how a library rots.

## 4. The standard library is already there

`idstd` is imported by default. You do not name it, and you did not above:
`chr_is_lower` resolved because the library is in every build. It is found
from, in order, `--std DIR`, `$IDSTD_HOME`, then an `idstd` directory beside
this repository.

```sh
idc/bin/idc caesar --allow-untested --no-std      # build without it
idc/bin/idc caesar --allow-untested --std ../idstd
```

The habit to build is: **before writing a small helper, assume `idstd` has
it.** It has about 128 functions — `fx_min`, `fx_max`, `str_split`, `lst_sort`,
`chr_is_digit`, `fmt_int`, `lset`. If you write your own anyway:

```
caesar/mine.id:1: error: function 'chr_is_lower' already defined at
  /home/you/git/idstd/core/text/chr/cls.id:28
caesar/mine.id:4: error: cannot assign a int value to string 'r'
caesar/mine.id:6: error: function 'chr_is_lower' returns int but the expression
  has type string
caesar/mine.id:1: error: variable 'c' is declared twice in function
  'chr_is_lower'
```

**Only the first line is the problem.** The other three are the type checker
reading your function through the library's signature for the same name. This
is the general shape of `id` diagnostics and the most useful habit in this
document: **fix the first error and rebuild.** Do not work down the list.

> **Pitfall 3.** One real error produces a cascade. Read the top line only.

**The other direction is a rule too: a function written in two projects moves
into `idstd`.** Once the same function exists in any two projects, for any
reason — copied, vendored, or written twice independently — it is added to
`idstd` with its cases, and every project deletes its copy and calls the
library's. Two copies drift apart, and a reader can no longer tell which one a
call means. The compiler cannot see across projects, so this is found with
`idc/tools/dupscan.sh`, listing each project root separately:

```sh
idc/tools/dupscan.sh "$PWD/demos/moonbuggy" "$PWD/demos/solitaire" "$PWD/../idstd"
```

Run it whenever a change touches more than one project.

### The trap with no line number of its own

Two `idstd` modules hold state, and state in `id` is an `export` inside a
function body — so the global does not exist until that function has run.
Calling `fx_sin` without calling `fx_trig_init` first used to be a segfault.
It is now caught:

```
idstd/core/math/trig/tab.id:39: error: 'fx_sintab' is exported by
  'fx_trig_init', which nothing calls -- an export is initialised when its
  declaring function runs, so this reads an uninitialised global. Call
  'fx_trig_init' from main's setup chain
```

The fix is one line at the top of `main`:

```
main(int argc, string[] argv) {
  fx_trig_init();
  int v = fx_sin(90000);
  print(v);
} return int 0;
```

```sh
./build/trig
1000
```

(`fx_sin` takes degrees scaled by 1000, so 90 degrees is `90000` and the result
`1000` is 1.0 at the same scale. `idstd` is fixed-point throughout; there is no
float mirror yet.) The same applies to `err_init`. If you write a module of
your own that exports state, it inherits the same obligation.

> **Pitfall 4.** An `export` is a statement, not a declaration. Anything that
> holds state needs its initialiser called from `main`.

## 5. `conf.id`: what the project depends on, and what it holds constant

The shift is hard-coded as `3` above. A project's **root** may carry a
`conf.id` naming the trees it depends on and then the constants it is built
with:

```
// caesar/conf.id
int rot = 3;
```

```
// caesar/shift/...
int off = c - base + (import rot);
```

```sh
idc/bin/idc caesar --allow-untested && printf 'Attack at dawn!\n' | ./build/caesar
Dwwdfn dw gdzq!
```

Change the one line to `int rot = 13;`, rebuild, and nothing else moves:

```
Nggnpx ng qnja!
```

A constant is an ordinary exported global that needs no function to initialise
it — it is emitted at file scope with its value attached, so it holds it before
`main` runs, which is exactly what §4's `export` cannot promise. Two rules
follow from "ordinary exported global":

```
caesar/clash.id:2: error: 'rot' is an exported global (by 'conf.id'); another
  variable cannot reuse that name -- read the global with 'import rot'
```

and imports must come before constants; an `import` after one is an error.

This is also the only place a constant can live. A function whose whole job is
to return one -- `rot() { } return int 3;` -- is rejected with the declaration
to write here instead (`docs/SPEC.md` §7.2).

**Only a root's `conf.id` is a manifest.** The name is reserved everywhere else
rather than silently ignored:

```
caesar/sub/conf.id:1: error: 'conf.id' is the dependency manifest and is only
  read at the root of a project or a dependency. Here it is neither compiled
  nor read, so anything it defines silently does not exist; rename it
```

> **Pitfall 5.** `conf.id` at the root is a manifest. `conf.id` anywhere else
> is an error, not a config file.

### Depending on another tree

```
import "../mylib"
```

The dependency is merged as source, transitively, and its own `conf.id` is
followed. Every rule applies to it — including the 3-entries-per-directory
limit — with one exception that matters: **a name keeps one type within a
compilation unit, and an imported tree is its own unit.** Your `int s` and a
library's `string s` do not collide. Inside your own tree they do, and that is
where it still bites:

```
caesar/shift.id:3: error: argument 'c' of 'shift_one' expects int, got string
caesar/shift.id:8: error: chr expects an int, got string
caesar/shift.id:9: error: argument 'c' of 'chr_is_lower' expects int, got string
```

Every one of those lines is in `shift.id`. The cause was a brand-new file
declaring `noisy(string c)` — and no diagnostic names it. When a type error
appears in a file you did not edit, look for a new declaration of that name
somewhere else in the tree.

> **Pitfall 6.** A name has one type across your whole tree. Breaking that
> reports the error everywhere *except* where you broke it.

### Importing part of a tree

A dependency does not have to be a root. `import "../engine/gfx"` merges that
one directory -- which is how a test gets a renderer without the window backend
the whole engine names. The directory has no `conf.id` of its own, but its code
reads the engine's constants, so it takes them from its **enclosing root: the
nearest directory above it that has a `conf.id`**. A constant keeps one home
however little of its tree you import.

- **Only the constants come along.** The enclosing root's `import` lines are not
  followed: leaving the rest of the tree out is why you imported part of it.
  Whatever the part needs, name in your own `conf.id`.
- **A root's constants are taken once**, however it is reached -- whole, through
  one subdirectory, or through several. Importing `engine/core/util` and
  `engine/gfx` side by side declares nothing twice.
- **A directory with its own `conf.id` is a root**, and reads only that one.
- **One name, two `conf.id`s, is an error** that names both declarations:

  ```
  app/conf.id:2: error: constant 'lib_k' is already declared at
    /home/me/lib/conf.id:2; a constant has one home -- rename one of them
  ```

- **A `conf.id` below the directory you import is still nested**, and still an
  error. Nesting is judged against the tree being built or imported, never
  against the directories above it.
- The rule is for `conf.id` imports. The project you build, a `--backend`
  directory and the standard library read only their own `conf.id`.

## 6. A project with no `main` is a library

```sh
idc/bin/idc lib --allow-untested -o lib.o
file lib.o        # ELF 64-bit LSB relocatable
```

Nothing is pruned — every function is an entry point — and everything is still
checked.

A library that needs code from the program using it takes that code as a
function value ([`SPEC.md`](SPEC.md) §1.1), not as a name the program must
define:

```
run_frame(func(int) return void step, int dt) {
  step(dt);
} return void;
```

A library that calls a name its user defines instead makes every program that
links it define that name, games or not — which is why `idem`'s engine, calling
`g_step` and five siblings, needs `idem/stub/` for everything that is not a
game ([`TODO.md`](TODO.md) 13). A function value is passed or stored where the
reader can see it, and a program that does not need the seam does not supply
one.

## 7. When the language does not have it

`id` has no file I/O. The builtins are stdin and stdout and nothing else, so a
"file program" in `id` is a filter and the caller picks the files with
`< in > out`. When that is not enough, a **native backend** supplies functions
at link time. Name it in the root `conf.id`:

```
// conf.id
import "../../idc/backends/fs"
```

and then `fs_open`, `fs_read`, `fs_write`, `fs_close`, `fs_size`, `fs_exists`,
`fs_list`, `fs_remove` and `fs_error` are ordinary calls. The backend declares
each of them in `id`, as a function whose body is native code:

```
native fs_open(string path, string mode) return int;
```

Its directory is merged into your build like any dependency, so a call into it
is checked like any call: the wrong number or type of arguments, or a
misspelled name, is the same error it would be for a function you wrote.
`demos/fsdemo` is ~40 lines of `id` that never names C. `--backend DIR` does the
same thing from the command line; naming one both ways links it once.

**Which implementation you get is chosen for you.** The build has a target
triple, derived from the machine you are on unless you say otherwise, and the
backend's `backend.json` is indexed by the platform in it. Nothing in your
source changes when the platform does.

```sh
idc/bin/idc demos/fsdemo --allow-untested            # x86_64-unknown-linux-gnu here
```

**A backend costs nothing until you call it.** Attaching one merges its
declarations; it is compiled and linked only when something reachable from
`main` calls one of its natives (and, for the test harness, only when a case
reaches one). A library can name `gfx` in its `conf.id`, and a program that
never draws still links no X11.

`--triple` overrides the platform, and when a native you reach has no
implementation for the platform you asked for, the build stops at the call
that reaches it:

```sh
idc/bin/idc demos/gl3d --allow-untested --backend idc/backends/gl --triple aarch64-apple-darwin
demos/gl3d/loop/frame.id:8: error: native 'glwin_poll', reached from main by
  this call, is implemented by backend 'gl', which has no support for platform
  'darwin' (building for 'aarch64-apple-darwin'); it is implemented for: linux
```

A native declared outside any attached backend is the same kind of error — it
names the call and the platform, and says the declaring file is not in an
attached backend — rather than a linker error about `id_<name>`.

The same applies to `asm` functions, which are selected by exact triple with no
wildcard and no fallback:

```
error: no 'asm' definition of 'dbl' for target 'aarch64-unknown-linux-gnu';
  defined for: x86_64-unknown-linux-gnu
```

**What `--triple` does not do is cross-compile.** It picks sources and asm
overloads; the C target still compiles with your `cc`, so asking for a platform
your compiler does not target is refused rather than faked:

```sh
idc/bin/idc demos/fsdemo --allow-untested --triple aarch64-apple-darwin
idc: cannot build for 'aarch64-apple-darwin' here: the C target compiles with
  the host's cc, which targets 'linux', not 'darwin'.
idc: pass --cc with a cross compiler for 'darwin', or use --target llvm, which
  hands the triple to clang.
```

> **Pitfall 7.** A backend's functions exist in a build only when the backend
> is attached. Call one without it and the error is `no such function` — the
> same error a misspelling gets, because either way nothing in the build
> declares that name. If the spelling is right, attaching the backend is the
> fix. A backend's parameter names are not variables and reserve nothing, so
> no name your program exports or declares can collide with one of them.

## 8. When you do not believe the compiler

```sh
idc/bin/idc caesar --allow-untested --emit-c caesar.c
```

writes the generated C instead of building. It is the fastest way to find out
what a construct actually costs, and the fastest way to confirm that the thing
you think is being called is the thing being called:

```c
char* id_shifted(int c, int base);
...
        out = id_shifted(c, 97);
```

`--keep-c` keeps it *and* builds. `--emit-llvm` and `--target llvm` are the
same idea one layer down.

## 9. Tests

A test case lives beside the function it tests, under its return clause, and
the compiler requires at least two per function on every build. Two for
`shifted`, whose body is in §2:

```
shifted(int c, int base) {
  ...
} return string out;
(97, 97):("d")
(120, 97):("a")
```

A function with fewer is a compile error. `--allow-untested` turns that off
for a build that does not have its cases yet — every build above — and is
deprecated: it warns on every build, and goes once every function has its
cases. While the standard library still lacks some, a build that merges it
needs the flag even when its own functions are all tested. See
[`TESTS.md`](TESTS.md), "Enforcement, and the migration".

---

## The checklist

Seven things, in the order you will meet them.

1. **A call cannot be an argument to a call.** Name every intermediate value.
2. **3 functions per file, 3 entries per directory.** The directory limit fires
   on a directory you were not editing. Plan the levels early.
3. **Read the first error only.** One mistake produces a cascade; the lines
   below the first are consequences.
4. **Anything that exports state needs its initialiser called from `main`** —
   `fx_trig_init`, `err_init`, and anything of yours that does the same.
5. **`conf.id` is a manifest, and only at a root.** Elsewhere it is an error.
   Imports before constants.
6. **A name has one type across your whole tree** — and the errors appear
   everywhere except where you broke it.
7. **A backend is part of the build, not the source.** The platform is chosen
   from the target triple; an unsupported one stops the build by name.

## Where to go next

- [`TUTORIAL.md`](TUTORIAL.md) — the language, through one worked program.
- [`SPEC.md`](SPEC.md) — what is guaranteed, independent of backend.
- [`../README.md`](../README.md) — every builtin and every rule, in one list.
- [`../idc/README.md`](../idc/README.md) — what `idc/bin/idc` does under the hood.
- `demos/` — `hello`, `calc`, `adventure`, `wordcount`, `fsdemo` are the small
  teaching set; `demos/solitaire` is what a real program looks like at scale.
