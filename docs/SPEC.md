# What an `id` program means

> **Status: normative, and executable.** Every claim here is a case under
> `idc/tests/conform/`, run on every target by `idc/tests/conform.sh`. §10 records
> where the targets do not meet it yet.

This document says what `id` code *does*, independently of how it is compiled.
Everything here is a promise every code-generation target must keep.

## Why it exists

Until now the answer to "what does this program do" was "whatever the C the
compiler emitted does". That was workable while there was one target. There is
not: the original compiler emitted LLVM IR and WebAssembly from `f229d52` on, and the
three have **already drifted**. A shift wider than the type gives three
different answers today — the C target defines it through a runtime helper,
the LLVM target emits a raw instruction whose result is poison, and the WASM
target masks the shift count. Nothing reports this, because nothing was
looking.

Nothing *could* have been looking. `idc/tools/parity.sh`, which has caught almost
every bug in this compiler, compares the **text** two compilers emit. That is
only a question that exists while both of them emit C, and it says nothing
about a target that emits something else. It stays exactly as useful as it has
always been for the two C-emitting compilers, and it is structurally incapable
of growing into the cross-target gate.

`idc/tests/conform.sh` is that gate: it builds each case in `idc/tests/conform/` every
way the toolchain allows, runs it, and requires the same stdout, exit code and
stderr from each. This document is what those cases are checking, written down
so that a disagreement has a right answer instead of a majority vote.

**The C target is the reference.** Where this document merely records existing
behaviour it says so; where it *chooses*, it says that too, and names what has
to change.

---

## 1. Types

Five scalar types and two type constructors. `T[]` is a list of `T`, and
nests. `func(T1, T2) return R` is a function type (§1.1).

| type | width | representation |
| --- | ---: | --- |
| `int` | 32 | two's complement, signed |
| `word` | 64 | two's complement; the type of an address in the flat store |
| `float` | 64 | IEEE-754 binary64 |
| `string` | — | an immutable sequence of bytes |
| `void` | 0 | no value |

A list is a heap-allocated growable sequence with **reference semantics**:
passing one to a function and mutating it is visible to the caller. This is
how `id` gets shared mutable state, and it is the one place in the language
where assignment does not copy.

Width is a promise, not an implementation note: `int` is 32 bits on every
target, including targets whose natural word is wider.

**A narrowing conversion is written down.** A declaration or an assignment may
narrow -- `int n = a;` where `a` is a `word` -- because the type it narrows to
is named on the line that does it. An **argument may not**: the parameter's
type is in another file, so `take(a)` would read as if nothing happened while
dropping half of a `word`. Declare a local of the parameter's type and pass
that. **Nor may a return clause**: `} return int w;` hands a `word` across the
function's boundary exactly as an argument does, so declare an `int` local,
assign it, and return that. Widening is exact and needs no ceremony in any of
these places. This is the
same strictness `xs[a]` has always had, which used to look inconsistent with
both of the others.

**A variable name has one type across the whole program.** Every parameter and
local of that name, in every function and every imported tree, has the same
type, and so does the standard library's: a program's `string n` is an error
when the library declares an `int n` anywhere, loaded or not (E0303, at the
program's declaration, with the library's as the related location). Exports are
outside the rule, being one global each.

### 1.1 Function values

A library sometimes needs code from its user: an engine runs a frame by calling
the game's step. `id` says that with a value whose type is a function type,
rather than by having the library call a name every user must define.

```
tick(int n) {
  print("tick " + n);
} return void;

run_frame(func(int) return void step, int dt) {
  step(dt);
} return void;

main(int argc, string[] argv) {
  run_frame(tick, 16);
} return int 0;
```

**The type.** `func(T1, T2) return R` lists parameter types only, with no
names; `R` may be `void`, and `func() return void` takes nothing. A parameter
type may itself be a function type. Brackets after the return type belong to
the return type: `func(int) return int[]` returns a list. `func` is a keyword
and cannot be a name. However it is spaced, a function type is one type: two
spellings are the same type exactly when they list the same types in the same
order, and a name that is a function type in one place has that same type
everywhere in the program, as every name does (§1).

**The values.** A value of a function type is a named top-level function
written in `id` -- one of the program's, the standard library's, or a `native`
declaration -- or a closure that `bind` makes from one (§1.1.1). Nothing else
is: there are no lambdas, and a builtin (`print`, `len`, ...) or an `asm`
function is not a value. A function's name where a value is expected denotes
that function, and
its signature must be the type exactly: the same parameter types in the same
order and the same return type. There is no conversion between function types;
`func(int) return void` does not accept a function taking a `word`.

**Where one may be.** A parameter, a local, and an export read with
`(import NAME)` -- which is how a library stores a value its user hands it:

```
eng_setup() {
  export func(int) return void eng_step = tock;
} return void;

frame() {
  func(int) return void g = (import eng_step);
  g(16);
} return void;
```

Nowhere else. Not an element of a list, and so not in a list type (there is no
way to spell one); not a function's return type; not an operand of any
operator, comparisons included; not an argument to a builtin; not a condition.
A test case passes one by naming the function where the argument goes --
`(tick, 16):(tick, 16)` -- or through `(import NAME)` after a `given` setup has
stored it (docs/TESTS.md).

**Calling one.** `step(dt)`, where `step` is a parameter, local or export of a
function type. The arguments are checked against the type -- how many, and each
against its parameter type, with the narrowing rule above -- and every rule of
§7.1 applies unchanged: calls nest at most one level inside an argument, and a
return clause is a name or a literal.

**Why this much and no more.** A call through a value hides which function
runs, which is the one thing `id`'s rules otherwise never hide. What stays
visible is the type: it is written on the declaration of the name being called,
in the same function or in the export, and every diagnostic about a call
through one names it. Values that could be built at run time, returned, or kept
in a list would let a call's function come from anywhere the value travelled;
a named function stored or passed at a line the reader can find cannot.

**What the compiler says.** Where a function type is expected, the message
names both signatures; where no function value may be at all, it names the
value's type.

| written | error |
| --- | --- |
| `func(int) return void f = pair;` where `pair` takes two ints | `cannot initialize func(int) return void 'f' with a func(int, int) return void value` |
| `f = twice;` where `twice` returns int | `cannot assign a func(int) return int value to func(int) return void 'f'` |
| `run_frame(shout, 16)` where `shout` takes a string | `argument 'step' of 'run_frame' expects func(int) return void, got func(string) return void` |
| `step(dt, dt)` | `'step' is a func(int) return void, which takes 1 argument(s), got 2` |
| `step(label)` with a string | `argument 0 of 'step' (a func(int) return void) expects int, got string` |
| `step(w)` with a word | `argument 0 of 'step' (a func(int) return void) narrows word to int; declare a int local and pass that` |
| `int[] xs = [tick];` | `a function value cannot be an element of a list: element 0 is func(int) return void` |
| `func(int) return void[] fs` | `'func(int) return void[]': brackets after a function type's return type belong to the return type, and void[] is not a type; a function value cannot be an element of a list` |
| `} return func(int) return void f;` | `'pick' returns func(int) return void; a function value cannot be a function's return type -- store it in an export, or pass it to the function that calls it` |
| `func(int) return func(int) return void` | `a function type cannot return a function value; pass the function, or store it in a local or an export` |
| `func(int dt) return void` | `a function type lists parameter types only: write 'int', not 'int dt'` |
| `tick + 1` | `'+' cannot take a function value: its left operand is func(int) return void; a function value can only be passed, stored or called` |
| `print(tick)` | `'print' cannot take a function value: argument 0 is func(int) return void; a function value can only be passed to a function written in id, stored or called` |
| `if(step)` | `a condition cannot be a function value (func(int) return void); call it, and test what it returns` |
| `func(string) return void f = print;` | `'print' is a builtin, not a function defined in id; only a function written in id can be a value -- write one that calls 'print' and pass that` |
| `int func = 1;` | `'func' is a keyword (it begins a function type, see docs/SPEC.md) and cannot be used as a name` |
| `int thing = 1; thing();` | `'thing' is a variable, not a function` -- unchanged: only a variable of a function type can be called |

`-tick`, `!tick` and `tick[0]` draw the existing unary and index messages,
which name the type.

**Uniqueness and reachability.** A function named as a value keeps its name in
the fingerprint the duplicate-logic rule compares (docs/HACKING.md), as a
called function does, so two functions that differ only in which function they
pass are different logic. A call through a parameter or local is that
variable's position, like any other use of it, so renaming the parameter does
not make a second function. A function named as a value is reachable exactly as
a called one is: it is emitted, and an export it declares is live.

**On the targets.** A function value of either kind is a pointer to an object
(§1.1.1 says what is in it). The C target spells every function type `IdFn*`,
names the object of a plain function `ID_FNV(tick__0)`, and calls through the
variable by casting the object's `fn` to the function's signature, with the
object first, so each argument converts to the parameter type the function type
spells -- `((void (*)(IdFn*, int))step->fn)(step, 16)`. The LLVM target,
`--freestanding` included, spells it `ptr`, gets the object of a plain function
from the runtime (`call ptr @id_fn_plain(ptr @idfn_a_tick__0, ptr @id_tick)`) and
calls through the adapter the runtime reads from the object (`%f = call ptr
@id_clo_fn(ptr %v5)`, then `call void %f(ptr %v5, i32 16)`), converting each
argument likewise. `--target wasm` is the C target's C, so it is the same.

### 1.1.1 Closures: `bind`

A function value carries no state, so "sort these rows by column `n`", with `n`
known only at run time, used to need an export for `n` and a fixture in every
case of every function that touched it. `bind` makes a function value that
carries values.

```
cmp_col(int n, int[] a, int[] b) {
  int c = a[n] < b[n];
} return int c;

sorted_by(int[][] rows, int n) {
  func(int[], int[]) return int lt = bind(cmp_col, n);
  int[][] out = sort_rows(rows, lt);
} return int[][] out;
```

**The form.** `bind(NAME, v1, ..., vk)`, with `k >= 1`. `NAME` is the name of a
function written in `id` (a function of the program, of the standard library, or
a `native` declaration): the same names §1.1 lets stand as a value. It is
partial application: the values fix the function's **leading** `k` parameters,
and the result is a value that takes the rest. If `NAME` is `func(P1, ..., Pn)
return R`, then `bind(NAME, v1, ..., vk)` has the type `func(Pk+1, ..., Pn)
return R`; with `k = n` it takes nothing, `func() return R`. A value `vi` must
fit `Pi` exactly as an argument fits a parameter, narrowing rule included (§1).
`bind` is a builtin name, so a function cannot be called `bind`. It is an
expression, so the calling rules of §7.1 apply to it as to any call: it nests
one level inside an argument and its own values are names, literals and
operators, not further calls.

**Why a named function and not a lambda.** Both were weighed. An anonymous
function would put a function inside a function: its body would be a block
counted against the enclosing function's three actions or exempt from them; it
would have no name, so the two cases every function owes and the
duplicate-logic rule would have nothing to be attached to; and it would capture
whatever variables it happened to mention, so what a closure holds would be
read off its body rather than off the line that creates it. Partial application
has none of those problems. The function stays a top-level, named, tested,
uniqueness-checked unit (`cmp_col` above has its two cases and is callable on
its own: `(0, [1], [2]):(1)`); what is captured is the list of values written on
the `bind` line, in the order of the leading parameters; and the rules need no
new exception. The price is that the captured values must be the function's
leading parameters, so a function meant to be bound declares them first.

**What is captured.** The values are evaluated once, left to right, when the
`bind` runs, and what the closure holds is fixed from then on. Nothing the
closure holds changes when the variables it was made from do, and a closure has
no way to change what it holds.

| a value of type | what the closure holds | immutable because |
| --- | --- | --- |
| `int`, `word`, `float` | the value | it is a value |
| `string` | the same string | a string is immutable (§4) |
| `int[]`, `word[]`, `float[]`, `string[]` | **a copy**: a new list of the same elements, made when `bind` runs and then locked | locking is the §8 constant-list lock: a `push`, `pop` or index assignment on it, anywhere, is the trap `id: cannot mutate a constant list`. The caller's own list is untouched, so later writes to it are not seen by the closure and the closure's calls cannot write to it |
| `func(...)`, a plain function or another closure | the same value | a function value is immutable |

A list is copied one level, so the copy of a `string[]` shares its strings
(immutable) and nothing else. A **list of lists, a list of function values, and
a struct** cannot be captured: an element that is itself a list or a struct is a
reference, so a copy would share it with its owner and the closure would be
neither a copy nor immutable. `bind(f, rows)` for a `int[][]` is the error `'bind' cannot capture ... a list of lists`; the fix is to capture the one
row, or to flatten the rows into one list and capture that. (A deep copy was
the other option and was refused: it makes `bind` cost the size of the data
every time, which is the thing a comparator closure made once per sort and
called n log n times must not do.) A function whose captured parameter is a
list may read it freely: `a[i]`, `len(a)` and passing it to a function that
only reads it all work, and writing it traps as above.

**Freeing.** A closure is a block of the same kind as a string or a list, made
by the runtime allocator, and so is each list copy it holds. In this slice they
are released with the rest of the program's blocks at exit (§6 and
docs/MEMORY.md): the escape analysis does not yet prove a closure local dead,
and the free of a list is never based on a closure. What `bind` does not do is
keep a reference to the caller's lists: a list handed to `bind` is **copied**,
so the analysis treats the position as one that does not keep it, and the caller
may still free its own list when it can prove it dead.

**The type.** A closure has the type `func(...) return R` of §1.1, not a new
one: `bind(cmp_col, n)` and a plain function `by_first(int[], int[]) return
int` are both `func(int[], int[]) return int`, so everything that accepts one
accepts the other, and a call through either is `f(a, b)`. Where a function
value may be, a closure may be (a parameter, a local, an export read with
`(import NAME)`), and where it may not (an operand, a list element, a return
type, a builtin's argument) it may not be either. Nothing in the type says
whether a value is plain or closed over: that is what lets a library take a
callback and leaves the caller free to choose.

**What the compiler says.**

| written | error |
| --- | --- |
| `bind(inc)` | `'bind' takes the name of a function and at least one value to capture: write bind(NAME, value, ...); with no value to capture, NAME alone is already a function value` |
| `bind(3, 4)` | `'bind' takes the name of a function written in id as its first argument, but it is a int; write bind(NAME, value, ...)` |
| `bind(step, 4)` where `step` is a `func(int) return void` variable | `'bind' takes the name of a function written in id, but 'step' is a variable of type func(int) return void; bind the function by its own name where it is known, or pass 'step' on unchanged` |
| `bind(len, xs)` | `'bind' cannot bind 'len': it is a builtin, not a function defined in id; write a function that calls 'len' and bind that` |
| `bind(inc, 1, 2)` where `inc` has one parameter | `'bind' gives 2 values to 'inc', which takes 1 parameter(s); bind fixes the leading parameters, so give at most 1` |
| `bind(inc, "x")` | `'bind' value 0 for 'inc' expects int, got string` |
| `bind(inc, w)` with a `word` | `'bind' value 0 for 'inc' narrows word to int; declare a int local and pass that` |
| `bind(f, rows)` with `rows` an `int[][]` | `'bind' value 0 for 'f' cannot be captured: it is a int[][], a list whose elements are themselves lists or structs, so a copy would still share them; capture a list of ints, words, floats or strings (one row, or the rows flattened into one list)` |
| `bind(f, p)` with `p` a `Point` | `'bind' value 0 for 'f' cannot be captured: it is a Point, a struct, which is a reference the closure would share with its owner; capture the fields it needs as separate values` |
| a closure where a function value may not be | the messages of §1.1, unchanged: they name the type |

**Uniqueness and reachability.** `bind(NAME, ...)` names `NAME` as a called
function is named: it is in the fingerprint the duplicate-logic rule compares
and it makes `NAME` reachable. Two functions that differ only in which function
they bind are different logic; the values bound are positions like any other
argument, so renaming a local does not make a second function.

**In a test case.** A closure is built where a function value is, and a case
can give one in two ways. Through a setup, as for any function value:
`given mk() (cl)`, where `mk` stores `bind(...)` in an export and the case
passes `(import cl)`. Or directly, anywhere a position of a function type
takes a function's name (docs/TESTS.md): `(bind(cmp_col, 1), ...)`, whose
values are case literals. A closure compares by what it holds: two are equal
when they are the same function with the same number of captured cells and the
cells hold the same bits; a captured string is the same pointer only when it is
the same literal, and a captured list is always a fresh copy, so a case that
restates a closure capturing a list or string on an `EXPECTED` side
cannot match -- write the case on the function's return value instead (the
expected tuple may stop before the closure's parameter).

**Across a boundary.** A closure is an `id` object, so it does not cross into
code that is not `id`:

- `--lib` and a library's C header refuse a `func(...)` parameter already
  (docs/INTEROP.md); that is unchanged, and there is no way for C to hold a
  closure.
- A `native`'s `func(...)` parameter is a C function pointer. A **plain**
  function passed there still is one. A **closure** has no function pointer to
  give, so passing one traps (§8): `id: a closure cannot be passed to a native:
  it takes a plain function pointer; pass the function by name, or give the
  native the values another way`. The check is at the call, on the value, so
  it is a trap and not a compile error: the compiler cannot see, through a
  parameter of function type, which kind arrived.
- `thr_map` is such a native: **a closure to `thr_map` traps in this slice.**
  The reason is not the data: a closure's captured values are immutable and
  copied, which is exactly what a pure function run on several threads may
  read. The native is a C function that would have to call `f` with the closure
  as its first argument, and that is a change to `thr_run`'s C ABI, which
  docs/INTEROP.md documents as a plain pointer. It is recorded as a fork in
  docs/THREADS.md.
- `--target wasm` is the C target's output compiled for wasm32-wasi, so closures
  are the same there; the JavaScript and WASM exports (`jsbind`, `wlgen`) take
  scalars, strings and lists only and are unchanged.

**On the targets.** Every function value is a pointer to an object of one
layout, whether it is plain or a closure: a code pointer `fn` (a function that
takes the object first, then the closure's remaining parameters), a pointer
`raw` to the function itself (null for a closure), a count `n` of captured
cells, and the cells, 8 bytes each, as a list cell is. A plain function used as
a value is a constant object with `n = 0` that the translation unit defines once
(`idfn_o_NAME__0`); `bind` allocates a new object and copies `n` and `fn` from
the constant template of its (function, number of values) pair
(`idfn_o_NAME__K`), then fills the cells. Calling `f(a, b)` loads `f->fn` and
calls it with `f` and the arguments. `fn` is a small generated function per
(function, number of values) that unpacks the cells and calls the real function
with them in front, so the real function is an ordinary function with ordinary
parameters and nothing in it knows it was bound. The unit defines these at its
end, for exactly the pairs its code used. The LLVM target holds an object as
`ptr` and never looks inside one: its module defines only the adapters, and the
runtime makes objects and reads their cells (`id_fn_plain`, `id_clo_make`,
`id_clo_set`, `id_clo_cell`, `id_clo_fn`), so the layout above is the C
runtime's and `tools/idrun`, which runs the same module, keeps an object as one
of its own lists.

### 1.2 Structs

A struct is a named record of one to three fields, with **reference
semantics**, like a list: passing one to a function and writing a field is
visible to the caller, and two names for one struct see each other's writes.
(docs/STRUCTS.md has the reasoning and the decisions behind each rule here.)

```
// geo/point.id -- a struct has a file of its own
struct Point {
  int x;
  int y;
}

// anywhere else
shift(Point p, int dx) {
  p.x = p.x + dx;
} return void;

main(int argc, string[] argv) {
  Point p = Point(1, 2);
  shift(p, 3);
  print(p.x);
} return int 0;
```

**Declaring.** `struct NAME { TYPE field; ... }` at the top level, in a file
that holds that declaration and nothing else: no function and no second
struct. A field is an `int`, `word`, `float` or `string`, another struct, or a
list of any of those (`Point[]`, `int[]`); not `void`, and not a function value
(§1.1). A struct has **one to three fields** -- the same three every limit in
the language is -- so a bigger record is two records, one inside the other. A
struct may not contain itself, directly or through the structs in its fields
(it could never be built); a **list** of itself is the way to say "any number
of these".

**Naming.** A struct is a program-wide type: a struct in an imported tree and
the same declaration in the program are one struct declared twice, and the
second is an error. Two structs with the same field names *and* types, in the
same order, are one struct (`{x, y}` and `{w, h}` are two; `{x, y}` twice is
one); the rule is the one two functions with the same body obey. A struct
cannot be named like a function or a builtin, because `Point(1, 2)` and
`point(1, 2)` are told apart by looking the name up. Field names live in the
struct's own namespace: `p.x` and `s.x` may have different types, and a field
may share a name with a variable or an export. Variables keep the rule of §1:
a name has one type across the program, so `Point c` in one function and `Conn c` in
another is an error.

**Constructing.** `Point(1, 2)` builds a struct, one value per field, in
declaration order, each checked against its field the way an argument is
checked against a parameter (a `word` is not squeezed into an `int` field).
It is an **initialiser and nothing else**: `Point p = Point(1, 2);` and
`export Point p = Point(1, 2);`. It is not an assignment's value, a list
element, an argument or a return -- declare the struct, then use the name --
so a struct is built on a line of its own, where the next line can see what it
is. There is no empty struct and no default; a struct has the value it was
built with. An empty list literal is not a constructor's argument any more than
it is a function's (§5): declare the list with its type (`int[] xs = [];`) and
pass the name.

**Fields.** `p.x` reads, `p.x = v;` writes, where `p` is any expression of
struct type: `s.t.keys`, `xs[i].x` and `(import g).x` read, and the write
`NAME.f = v;` or `xs[i].f = v;` goes through a name or an index like a list
element's (a write through `(import g)` is rejected, as for a list, §5). A
write is checked against the field's type like a declaration is. A struct is
indexed by name, never by number: `p[0]` is an error that lists the fields.

**What a struct cannot do (v1).** `==`, `!=`, `<`, arithmetic, `+`, a condition
and `print` do not take a struct; compare and print its fields (`a.x == b.x`).
`push(ps, p)` and `ps[i]` work on a list of structs, which is a list of
references. A struct has **no defined layout** and cannot be read with `peek`
or written with `poke`: it is not bytes, and nothing about how it is stored is
a promise. There are no struct constants in `conf.id` (a constructor is an
initialiser, and a function that only assigns literals into one would be the
constant-wrapper §7.2 rejects); a struct-typed `export` is initialised by its
owner like a list, and a read before the owner ran traps in a test case.

**In a test case.** A struct is written as the constructor, as an argument, an
expected value or a `then` check's value: `(Point(1, 2), 7):(Point(3, 2))`
(docs/TESTS.md). Its arguments are case literals in turn, so a field that is a
list, a struct or `(import NAME)` is written as it would be anywhere else.

**What the compiler says.**

| written | error |
| --- | --- |
| `p.z` | `struct 'Point' has no field 'z'; its fields are x, y` |
| `n.x` where `n` is an `int` | `cannot read field 'x' of a int; only a struct has fields (a list's length is len(list))` |
| `p[0]` | `cannot index a Point; a struct's fields are read by name, as in p.x (its fields are x, y)` |
| `Point(1)` | `struct 'Point' takes 2 field(s) (x, y), got 1; pass one value per field, in order` |
| `Point(1, "s")` | `argument 'y' of 'Point' expects int, got string` |
| `p = Point(3, 4);` | `'Point(...)' builds a struct and can only initialise a declaration, as in 'Point p = Point(...);' -- ...` |
| `p.x = "s";` | `cannot store a string into field 'x' (int) of struct 'Point'` |
| `p == q`, `p + 1` | `'==' cannot take a struct: its left operand is Point; a struct is compared and combined by field, as in a.x == b.x` |
| `print(p)` | `'print' cannot take a struct: argument 0 is Point; use its fields, as in print(p.x)` |
| `if(p)` | `a condition cannot be a struct (Point); test one of its fields, as in x > 0` |
| `Pnt p = ...` | `unknown type 'Pnt'; a type is int, word, float, string, a struct declared in a file of its own (structs: Point), or a list of one of those, as in 'int[]'` |
| a struct with four fields | `struct 'Wide' has 4 fields; the limit is 3 -- group related fields into a second struct and nest it, as in 'struct Wide { Part p; int a; int b; }'` |
| a struct beside a function | `struct 'A' shares its file with function 'f'; a struct is declared in a file of its own -- move the function to another file` |
| a second `{int a; int b;}` | `struct 'B' has the same fields as struct 'A' (declared at a.id:1); two structs with the same field names and types are one struct -- use 'A', or give 'B' a field of another name or type` |
| `struct N { N next; }` | `struct 'N' contains itself, directly or through another struct, so no value of it could ever be built; hold a list of it instead ('N[] items')` |
| a case writing `Size(1, 2)` for a `Point` | `this case builds a Size where a Point is required` |

**Memory.** A struct is a reference, so the rule of §6 applies to what it
holds: a list or string stored in a field -- by the constructor or by
`p.f = xs;` -- is **kept**, never freed when the function that made it ends,
because the compiler does not follow a value into a field (docs/MEMORY.md).
A struct is not itself freed yet: only lists are.

**On the targets.** A struct is the list it is stored as: the C target spells
it `IdList*`, one 64-bit cell per field in declaration order, with a field read
as the list read at the field's constant position and unboxed to the field's
type; the LLVM target spells it `ptr` and lowers the constructor, a read and a
write to the same list operations. Both produce the same output
(`idc/tests/conform/struct/`). The WASM target compiles the C target's own C
(`idc/bin/idc --target wasm`), so a struct needs nothing of its own there --
untested in the workspace this was written in, which has no WASI toolchain --
while `idc/idc.py`, frozen, does not parse the syntax and builds nothing that
merges one.

### 1.3 Pure functions

`pure` is a marker the compiler proves. A function written with it promises
that its result depends on its arguments alone and that calling it changes
nothing the rest of the program can see, which is what lets it run on another
thread (`docs/THREADS.md`) or be called in any order. The marker is written
before the name, in the same place `native` is, and the rest of the header is
unchanged:

```
pure sq(int x) {
  int r = x * x;
} return int r;

pure native thr_run(pure func(int) return int f, int n, int threads, int[] out) return int;

run_all(pure func(int) return int step, int n) {
  int i = 0;
  while(i < n) {
    step(i);
    i = i + 1;
  }
} return void;
```

`pure` is a keyword, so it is not a name. It is not part of a type: `sq` and an
unmarked function with the same signature have the same `func(int) return int`
type, and a pure function may be passed wherever that type is expected.

**What the compiler proves of `pure f`.** Each violation is an error that names
the offending write or call and the fix (`docs/ERRORS.md`, `E0801`-`E0806`):

- **`f` writes no export** (`E0801`). An `export` declaration is the only way
  a function assigns an export, so a pure function has none.
- **`f` does no I/O** (`E0802`). It may call only the builtins `len`, `push`,
  `pop`, `to_int`, `charat`, `chr`, `str_sub`, `udiv`, `umod`, `ult`, `ushr`, `fail`, `bind` and the four float bit-cast builtins (the list
  is the `pure_builtins` constant of `idc/compiler/parse/conf.id`). `print`,
  `put`, `flush`, `eprint`, `input`, `read_all`, `getkey`, `sleep_ms` and `ticks`
  do I/O or read the clock, and `alloc`, `store_size`, `peek*`, `poke*`,
  `str_of_mem` and `mem_of_str` read or write the flat store, whose contents are
  not an argument. A builtin that is added later is refused until it is listed.
- **`f` calls only pure functions** (`E0803`): functions marked `pure`, and
  natives declared `pure native`. A native is impure unless its declaration says
  otherwise, because the compiler cannot see its C; writing `pure native` is the
  author's promise that the C writes no global and does no I/O, and it is the
  one part of this rule that is believed rather than proved. An `asm` function
  is never pure. A struct constructor and an allocation are fine: a pure
  function may build lists and strings and mutate its own.
- **`f` reads no mutable export** (`E0804`). An `(import NAME)` is allowed only
  when `NAME` is a constant of `conf.id`, which is built before `main` and never
  assigned again (a list constant is also locked, so it cannot be written
  through an alias). Any other export is assigned by some function, and a read
  of it makes the result depend on when the read ran. An export that is
  assigned once during start-up is *not* accepted: that the assignment has
  finished before a parallel region starts is an ordering fact the compiler does
  not know. Pass the value as a parameter, or move it to `conf.id`.
- **`f` calls a function value only through a pure parameter** (`E0805`).

**A pure parameter.** `pure func(T) return R name`, written in a parameter list
(and only there: `E0807` otherwise), says that the function a caller passes is
pure. At every call, in a pure function or not, the argument written for a pure
parameter has to be the name of a pure function, or a pure parameter of the
caller (`E0806`); a local or an export that holds a function value is refused,
because what it holds is decided where it is assigned. **A closure counts when the
function it binds is pure**: `bind(f, v, ...)` (§1.1.1) is accepted for a pure
parameter when `f` is a pure function or a pure parameter, because the values it
captures are copies that nothing can write (a captured list is locked), so the
closure does what `f` does and nothing more. `bind` is therefore on the list of
builtins a pure function may call. Inside the callee, a call
through the parameter counts as a call to a pure function. This is how idstd's
`thr_map` accepts only pure functions at compile time (`docs/THREADS.md`).

**What it does not prove.** A pure function may still trap (an index out of
range, a division by zero), which is a result like any other, and may build
lists and strings, so it may allocate and run out of memory. It does not prove
that a pure function terminates. It does not yet prove that a pure function
leaves a *list argument* unmodified: `push(xs, v)` on a parameter is accepted,
and becomes an error when a parallel map takes a list as input
(`docs/THREADS.md`, section 5).

## 2. Integer arithmetic

### 2.0 How an integer is written

Three spellings, all producing the same kind of value — the base is a way of
writing a number, not a property the number keeps:

```
255      decimal
0xff     hexadecimal, 0x or 0X
0b1010   binary, 0b or 0B    (== 10)
```

A literal too large for `int` is a `word`. There is no digit separator, no
octal, and no exponent form for integers: a literal with an exponent is a
`float`, never an `int` (§3).

### 2.1 Overflow wraps

`int` and `word` arithmetic that exceeds the type's range **wraps**, modulo
2³² and 2⁶⁴ respectively.

```
2147483647 + 1   ==  -2147483648
100000 * 100000  ==   1410065408
```

This is a **choice**, and it is deliberately stronger than C, where signed
overflow is undefined and an optimiser is entitled to assume it cannot happen.
Every C compile, the wasm one included, passes `-fwrapv` so the emitted C
means what `id` means (§10, S1).

Wrapping was chosen over trapping because `id` compiles to code that runs at C
speed and a check on every arithmetic operation is the one cost that would
change that; and over promotion (Python's answer) because a language with a
flat store and a 64-bit machine word has already committed to fixed-width
integers. If a trapping or arbitrary-precision integer is wanted later, it
belongs as a *different type*, not as a change to this one.

### 2.2 Division truncates toward zero

`/` truncates toward zero and `%` takes the sign of the dividend, which is C's
rule and the one most readers expect.

```
(0 - 7) / 2  == -3      (0 - 7) % 2  == -1
7 / (0 - 2)  == -3      7 % (0 - 2)  ==  1
(0 - 7) / (0 - 2) ==  3
```

Division and remainder by zero **trap** (§8). So does the one division that
overflows, `MIN / -1`; `MIN % -1` is `0` rather than a trap, because the
answer is representable even though the quotient is not.

### 2.3 Shifts are defined for every count

For a value of width `W` (32 for `int`, 64 for `word`):

| count | `a << n` | `a >> n` | `ushr(a, n)` |
| --- | --- | --- | --- |
| `n < 0` | trap | trap | trap |
| `0 <= n < W` | shift, wrapping within `W` | arithmetic (sign-filling) | logical (zero-filling) |
| `n >= W` | `0` | `0`, or `-1` if `a < 0` | `0` |

```
1 << 31  == -2147483648      (0 - 1) >> 35 == -1
1 << 32  ==  0                       4 >> 35 ==  0
1 << 35  ==  0                (0 - 8) >> 1  == -4
```

`>>` is the arithmetic shift; the logical one is spelled `ushr`, so which is
meant is visible where it happens rather than implied by a declaration
elsewhere.

This matches the C target today, which routes both `int` and `word` shifts
through `id_shl`/`id_sar`. It does **not** match the other two targets — see
§10.

### 2.4 Bitwise and logical operators

`& | ^ ~ << >>` require integral operands (`int` or `word`); `float` is
rejected at compile time. `&& || !` likewise take integral operands and yield
`int` `0` or `1`. `&&` and `||` short-circuit: the right operand is evaluated
only when the left one does not already decide the result, so
`i < len(xs) && xs[i] == 2` never reads past the end of `xs`.

Mixing `int` and `word` in one operation widens to `word`.

**A comparison and a bitwise operator in one expression must be grouped with
parentheses.** The bitwise operators bind tighter than the comparisons in `id`
and looser in C, so an expression that relies on either table can only be read
by someone who knows which one applies. A comparison (`== != < <= > >=`, and
the bare `=` that means equality inside an expression) whose left or right
operand is an unparenthesized bitwise operation (`& | ^ << >>`) is a compile
error, and so is a bitwise operation whose operand is an unparenthesized
comparison. The diagnostic shows how the current precedence groups it:

```
flags & 4 == 4       error: 'flags & 4 == 4' mixes a bitwise '&' with a comparison '==';
                     parenthesize it as the current precedence reads it: '(flags & 4) == 4'
(flags & 4) == 4     ok
flags & (4 == 4)     ok
```

The second form cannot be written without parentheses today, because a
comparison binds looser and only reaches a bitwise operand through them; the
rule names it anyway, since it is about the reader and not about this table.
The parentheses are grouping only: they change neither the emitted code nor a
function's fingerprint for the uniqueness rule. Unary `~` is out of scope -- it
binds tighter than every binary operator and cannot be misread -- and so are
`&&` and `||` next to a bitwise operator. The original `idc.py`, now deleted, never had this rule.

## 3. Floats

`float` is IEEE-754 binary64 with the usual arithmetic. `%` on a float is a
compile error. Mixing `int` or `word` with `float` in an arithmetic or
comparison operator widens to `float`.

**Printing is lossy, and this is recorded rather than chosen.** A float reaches
text through C's `%g`: six significant digits, trailing zeros dropped,
exponent form beyond that range.

```
print(2.0)          →  2
print(1.0 / 3.0)    →  0.333333
print(0.1 + 0.2)    →  0.3
print(123456789.5)  →  1.23457e+08
```

`0.1 + 0.2` is not `0.3`, and a float does not survive a round trip through
`print`. A shortest-round-tripping representation (what Python, JavaScript and
Rust print) would be the better answer, but changing it would move the output
of every program in the tree and every golden file in `idstd`, so it is a
separate piece of work. It is written down here so that the WASM target — which
does not implement float printing at all — implements *this* and not something
of its own.

**A float literal is digits, then a point and digits or an exponent or both.**
The exponent is `e` or `E`, an optional `+` or `-`, and at least one digit:

```
1.5        0.8        6.02e23      1.5E+3      1e-30      2e10
```

*What makes a literal a float* is a point or an exponent. Without either it is an
integer (§2.0), so `2e10` is a **float**, not the integer 20000000000: an integer
has no exponent form, `2e10` does not fit an `int` and would otherwise silently be
a `word`, and one rule ("an exponent or a point means float") is easier to hold
than a rule that depends on the value. A literal is still never signed (`-1e-30`
is the unary `-` applied to a literal), and the point must have a digit on each
side (`.5`, `5.` and `.e5` are errors).

**A literal's value is what C's `strtod` gives for the same text, on every
target**, including subnormals (`4.9e-324` is the smallest one, `2^-1074`;
`2.4703282292062327e-324`, just under half of it, is `0.0`) and every rounding
tie (`conform/float/12-exponent-exact`). The compiler does not convert the
digits: each backend hands the text to its own correctly-rounding reader. The
only spelling it changes is a missing point before the exponent (`2e10` is passed
on as `2.0e10`), because LLVM's text form requires one.

**Two literals are errors, and both name the fix.** An exponent with no digits
(`1e`, `1e+`) is E0103: it is not read as `1` followed by a variable `e`. A
literal that rounds to infinity (`1e999`, or anything at or above
`2^1024 - 2^970`, which is where round-to-nearest-even leaves `DBL_MAX` =
`1.7976931348623157e308`) is E0104. A literal too small to represent rounds to
zero, as it does in C, and is accepted.

`idrun` (docs/INTERPRETER.md) reads the compiler's IR text itself and is exact
only up to 15 digits and a net power of ten of 22; past that its last bit can
differ from the compiled targets.

**Floats and their bits.** Four builtins move between a `float` and the bits
that encode it, because a float in a list or a file is a bit pattern and the
arithmetic that would rebuild one by hand is both long and wrong at the edges
(subnormals, infinities, NaN).

| call | meaning |
| --- | --- |
| `bits_of_float(f)` | the 64 bits of the binary64 `f`, as a `word` |
| `float_of_bits(w)` | the `float` whose binary64 bits are the `word` `w` |
| `bits32_of_float(f)` | `f` rounded to binary32 (round to nearest, ties to even), its 32 bits as a non-negative `word` |
| `float_of_bits32(w)` | the `float` equal to the binary32 whose bits are the low 32 bits of `w` |

The binary64 pair is exact in both directions, NaN payloads included.
`bits32_of_float` of a value too large for binary32 is an infinity, and of a
NaN a NaN, as C's `(float)` conversion gives. `bits_of_float` takes a `float`
exactly: an `int` is made one by adding `0.0`. `float_of_bits` and
`float_of_bits32` take an `int` or a `word`. A `float` stored in a list is
already `bits_of_float` of itself (§5).

## 4. Strings

A `string` is an immutable byte sequence. There is no mutation operator; `+`
builds a new string.

- `+` with a `string` on either side concatenates, converting the other operand
  (`"lucky " + 7` is `"lucky 7"`).
- `==` and `!=` compare contents, not identity.
- `len(s)` is the length in **bytes**. `id` has no notion of a character; a
  multi-byte UTF-8 sequence is that many bytes.
- `charat(s, i)` is the byte at `i`, or `-1` if `i` is outside the string.
  Reading past the end is a value, not a trap — it is how a scanner detects
  end-of-input.
- `chr(n)` builds a one-byte string; `chr(0)` traps (below).
- `str_sub(s, i, n)` is the `n` bytes of `s` from byte `i`, as a new string: one allocation, one copy. A span that is not inside `s` -- a negative `i` or `n`, or `i + n` past `len(s)` -- traps (§8). An empty span (`n` of 0) reads nothing, so it answers `""` for any `i >= 0`, past the end included. idstd's `str_slice` is this builtin with the same trap message.
- `to_int(s)` parses a leading integer.

**A string cannot contain a NUL byte.** This is a consequence of the C
representation that has already cost something real: `idstd` abandoned a
planned function over it. It is recorded as a limitation rather than a design
decision, and a target is not free to lift it, because a program that works on
one target and not another is the thing this document exists to prevent.

Bytes that may hold a NUL belong in the flat store (§6), not in a string: idstd's
`stdio_slurp`, `stdio_read_mem`, `stdio_read_some_mem` and `stdio_write_mem` move
stdin and stdout/stderr bytes through it without a string in between.

**A NUL byte that would reach a string traps; it never truncates silently.**
Every way bytes become a string checks for it: `read_all()` and `input()` on
stdin that contains a NUL, `str_of_mem(addr, n)` over `n` bytes that contain
one, and `chr(0)` (or any `n` whose low byte is 0). The trap names the fix: use
idstd's `stdio_slurp` / `stdio_read_mem`, or the store (`fs_read_mem`), for
binary data (§8). A fixed-size buffer padded with NULs must be read with the
length of its text, not its capacity.

**A `\0` escape in a string literal is a compile error**, at the literal: a
string never holds a NUL byte, so the diagnostic sends binary data to
`stdio_read_mem`, `fs_read_mem` or the store (`tests/invalid/nul_in_string.id`).

## 5. Lists

- `[a, b, c]` builds a list. **A list literal has no type of its own**: it
  takes the type of the slot it is going into -- the declared type, the
  parameter's type, or the function's return type -- and every element is
  checked against that type's element type, the first no differently from the
  rest. So `word[] xs = [0, 0, 0]` is a `word[]` literal, and
  `int[] xs = ["a"]` names element 0. `[]` is the same rule with no elements
  to check.
- `xs[i]` reads, `xs[i] = v` writes; both **trap** on an index outside
  `0 <= i < len(xs)`. There is no silent drop and no growth by assignment.
- `push(xs, v)` appends; `pop(xs)` removes and returns the last element and
  **traps** on an empty list; `len(xs)` is the count.
- Lists have **reference semantics** (§1). Two names for one list see each
  other's writes.
- A `float` stored in a list survives unchanged: cells are uniform 64-bit and
  a float is stored by bit pattern, not by conversion.
- `(import xs)[i] = v` is rejected at compile time. Index-assignment is only
  recognised through a plain identifier, so writing through an imported global
  directly used to compile to a discarded comparison and do nothing; pass the
  list to a helper that takes it as a parameter.
- A list constant from `conf.id` (`docs/PROJECT.md` §5) is locked once built.
  `push`, `pop` or an index-assignment against it **traps**, whether reached
  directly or through an alias that took it from `(import name)` first; a
  direct `push`/`pop` on `(import name)` is instead rejected at compile time,
  naming the constant.

## 6. `word` and the flat store

One flat, byte-addressed memory, shared by the whole program. An address is an
ordinary `word`, so a record is an offset, an array is a stride, and taking an
address is arithmetic — none of which needs syntax.

- `alloc(n)` reserves `n` bytes and returns their address. **Address 0 is never
  returned**, so it can mean null. Allocations are 8-byte aligned.
- `store_size()` is the high-water mark.
- `peek8/16/32/64(addr)` and `poke8/16/32/64(addr, v)` load and store, **little
  endian**.
- **A peek returns a `word`, and which word is spelled in the name.**
  `peek8`, `peek16` and `peek32` read their bytes **zero-extended**: `peek32`
  of `0xBF000000` is `3204448256`, in every expression. `peek8u`, `peek16u` and
  `peek32u` are those same reads under a name that says so. `peek8s`,
  `peek16s` and `peek32s` **sign-extend** instead: the same four bytes read
  with `peek32s` are `-1090519040`. `peek64` has one reading. A `word` stored
  into an `int` wraps (§1), so `int x = peek32(p);` holds `-1090519040` while
  `peek32(p) + 0` is `3204448256` -- not two answers for one call but a
  `word` and its narrowing. Write `peek32s` where a signed 32-bit field is
  meant: `int x = peek32s(p);` and `peek32s(p) + 0` agree.
- Every access is bounds-checked against the high-water mark and **traps**
  outside it. This is the entire reason the store is a primitive rather than a
  library: the mistake that silently corrupts memory in C is a clean abort
  here.
- `str_of_mem(addr, n)` and `mem_of_str(s)` bridge bytes and strings;
  `str_of_mem` traps if any of the `n` bytes is a NUL (§4).
- `udiv`, `umod`, `ult`, `ushr` are the unsigned readings of `/ % < >>`. The
  plain operators keep their signed meaning. An `int` argument to `udiv`,
  `umod` or `ushr` is read as its 32 unsigned bits (§2.3's width `W`), not
  sign-extended: `ushr(0 - 1, 28)` is `15` and `ushr(0 - 1, 32)` is `0`. Pass
  a `word` to read 64 bits.

**Memory is meant to be freed before exit, and only part of it is.** `alloc` is
a bump pointer, and the arena behind strings is freed only at process exit — a
gap in the implementation, not a property of the language: a program that
allocates in a loop grows until it exits or runs out. The rule (decided
2026-09-26) is that the compiler frees a list or string it can prove never
escapes — never returned, exported, stored in another list, or kept by a callee
— when the scope that made it ends, and keeps anything it cannot prove, so
freeing can never cause a use-after-free. No syntax marks it. It frees a local
list, struct or string that nothing keeps, the string temporaries of an
expression, and a block a function returns fresh, by whoever receives it
(docs/MEMORY.md says how each is proved). A list is freed with its
elements (decided 2026-10-02: deep) when it also **owns** them: every element
that goes into it is a list literal written for it, and no element is read out
into a position that keeps it -- a store, a return, an alias, or an argument
the callee keeps. Only the elements that are themselves lists are freed, and
only one level down: the lists in a `string[][]` are freed and its strings are
not, and an `int[][][]` frees its middle lists and keeps the innermost. A list
that fails any of these is freed shallowly (header and cells) if it is a local
nothing keeps, and not at all otherwise; none of this is visible to a program
except as memory use.

**Every target frees the same allocations, unless a target is systemically
unable to** (decided 2026-09-30): a program whose memory is reclaimed on one
target and not another has no portable memory behaviour at all. The C target,
the LLVM target, `--target wasm` (the C target's output recompiled for
wasm32-wasi) and the freestanding runtime all free the same lists, elements
included, and `tests/conform/free/` runs programs on C, LLVM and wasm and
requires the same count. The exceptions, and why:

- **The freestanding runtime** frees but cannot check: a kernel has no stderr
  to trap to, so the use-after-free guard (`ID_FREE_GUARD`) is hosted-only, and
  a wrong proof there corrupts memory where it would trap elsewhere. It also
  frees no string: its strings are bump-allocated, so there is nothing to give
  a string back to.

No target is systemically unable to free a list. docs/MEMORY.md is the design,
the open decisions, and what each target frees today.

## 7. Evaluation order

**The operands of an operator, and the arguments of a call, are evaluated left
to right.** So are the elements of a list literal, and the two sides of an
index assignment: the list, then the index, then the value.

```
"a=" + bump(c) + " b=" + bump(c)      the first bump runs first
"pop=" + pop(xs) + " len=" + len(xs)  len sees the shorter list
f(step(c), step(c))                   the first argument is the first step
```

Most expressions give the same answer whichever order they are evaluated in,
which is why this was unwritten for a long time. It stops being true the moment
two operands share state -- and the two programs that found it are the two that
would: a DEFLATE bit reader, where every read advances the stream so the order
*is* the format, and a line of a document that pops a list and then measures
it.

This is a **choice**, made here rather than left to each target, and it is the
one the majority of languages a reader will have used make. The alternative --
declaring the order unspecified and requiring programmers to avoid the
situation -- was rejected for a specific reason: `id` has no way to *say* that
an expression has an effect, so a rule the programmer must obey is a rule
nothing can check. An order everything obeys needs no checking.

It is deliberately a property of the language and not of a flag. If it ever
needs to be configurable, the thing to configure is the target, not the
program: a program that reads differently depending on a build setting is
worse than either order.

### 7.1 The shape of an expression

Two rules, and one idea behind both: **a value that takes a step to compute is
given a name, and the name is what the reader of the line sees.**

**A call's argument may hold at most one level of call nesting.** Counted by
call depth, not by expression depth: an operator or an index wrapped around a
call adds no depth of its own. A call inside a call is fine; a call inside a
call inside a call is not.

```
int n = lm_len(s2w(s));        fine -- one call, one level down
int n = f(g(x) + 1);           fine -- the operator adds no depth

int n = lm_len(w2n(s2w(s)));   rejected -- two levels
word a = s2w(s);               the same thing, said in two steps
int n = lm_len(w2n(a));

int n = f(x) + g(y);           fine -- neither call is inside the other's
                               argument list
```

This was "no call inside an argument at all" until 2026-09-22. It existed to
stop call chains ten deep on one line, and one level of nesting does not
produce those. Arguments are evaluated left to right on every target (§7;
§11, S11).

**A return clause is a name or a literal.** Nothing else: no call, no
operator, no index, no list literal.

```
} return int n;                a name
} return int 0;                a literal
} return string "";            a literal
} return void;                 nothing

} return int i + 1;            rejected -- name it
} return int lm_len(a);        rejected
} return int xs[0];            rejected
} return int[][] [tab, row];   rejected, and it never parsed anyway: the `[`
                               after the type reads as another dimension of it
```

Neither rule buys the compiler anything. Both are about the reader. `id` fixes
the order operands are evaluated in (§7) precisely because two operands can
share state — and the expression that most easily hides shared state from a
reader is the one with a call buried inside another call's arguments, where
neither the order nor the fact that there are two steps is visible. Naming the
intermediate makes both visible, in the order they happen.

The cost is real and is not hidden here: **the action limit is unchanged**, so
a block that gains a name may have to give up a statement, and a function that
gains a statement may have to continue into a `chain` or become two. Across
this repository the two rules
cost about 1600 new names and several hundred new functions. That is the trade,
made deliberately: `docs/FRICTION.md` (retired; `git show 479234a^:docs/FRICTION.md`) §14 and §15 are what the other side of it
was costing.

Two places cannot be repaired by naming, so nesting beyond one level there
becomes a function instead:

* a `while` condition — a name bound before the loop is computed once where the
  loop needs it every iteration;
* the right of `&&` or `||` — a name bound before the `if` is computed even when
  the operator skips it.

```
while(is_alnum(charat(src, i))) {          fine -- one level
while(ok(is_alnum(charat(src, i)))) {      rejected -- two levels

while(ok(is_alnum_at(src, i))) {           the composition, as a function
```

### 7.3 Leaving a loop or a function early

**`break;` leaves the innermost enclosing `while`.** Outside every `while` it is
rejected where it is written. Nesting is limited to two levels, so a `break`
inside a `while` inside a `while` leaves only the inner one.

**`return NAME;`, `return LITERAL;` and `return;` leave the function.** An early
return takes the same shape as the return clause (§7.1) — a name or a literal —
and is checked against the function's declared type the same way: a value in a
`void` function, or `return;` in a function that returns one, is rejected. From
inside a `chain` segment it leaves the whole function, not just the segment.

```
first_even(int[] xs) {
  int i = 0;
  int none = 0 - 1;
  while(i < len(xs)) {
    if(xs[i] % 2 == 0) {
      int found = xs[i];
      return found;
    }
    i = i + 1;
  }
} return int none;
```

**Neither costs an action.** They end work rather than doing it, so the action
limit counts neither; a block may hold three actions and a `break` or `return`.

### 7.2 A function is not a constant

**A function that only returns one scalar constant is rejected.** Such a
function is a constant under a function's name: every caller has to open it to
learn that it never changes. A value that never changes is declared as one, in
the project's `conf.id` (`docs/PROJECT.md` §5), and read with `(import name)`.
A directory imported on its own, with no `conf.id` of its own, reads the
constants of its enclosing root -- the nearest directory above it that has a
`conf.id` -- and none of that root's imports, so the constant has one home
however much of its tree a program imports.

```
ch_nl() {                      rejected
} return int 10;

funcs_per_file() {             rejected -- a local initialised to a literal
  int n = 3;
} return int n;

zero(int a) {                  rejected -- the parameter is never used
} return int 0;

k() {                          rejected -- 2 * 1000 folds to 2000
  int n = 2 * 1000;
} return int n;

names() {                      rejected -- 1, 2 and 3 are literals
  int[] out = [1, 2, 3];
} return int[] out;
```

```
p.id:1: error: 'ch_nl' only returns the constant 10; declare it in conf.id as
  'int ch_nl = 10;' and read it with (import ch_nl)

p.id:1: error: 'names' only returns the constant [1, 2, 3]; declare it in
  conf.id as 'int[] names = [1, 2, 3];' and read it with (import names)
```

Precisely, a function is rejected when it is not `main`, not a `native`
declaration, and returns `int`, `word`, `float`, `string`, or one of their list
types; when every statement of its body declares a local of its own (not an
`export`) or assigns one, each time to a value that is a literal, a non-empty
list literal of nothing but literal elements, or an operator over literals the
compiler folds; and when its return clause is such a literal or one of those
locals. A call, an `import`, a parameter, a loop, a branch or a write through
an index anywhere in the body makes it a function. So do these, deliberately:

- **A list, built from anything but literals.** `names() { int[] out =
  [(import x), "b"]; } return int[] out;` depends on something other than a
  literal, so it is a function, not a constant wrapper — the fold this rule
  relies on (below) does not look inside a list literal's elements for
  anything but a literal read straight off it.
- **`[]`.** `new_bucket() { int[] b = []; } return int[] b;` is not a
  constant wrapper even though it is vacuously "nothing but literals": an
  empty list carries no values a conf.id constant could hold instead of it,
  and every caller needs its *own* fresh list -- the reason a list return type
  was excluded from this rule in the first place. A conf.id constant would
  give every caller the same list.
- **Assigning a parameter.** `reset(int a) { a = 5; } return int a;` uses its
  parameter; a parameter is not one of the function's own locals.

Folding is the compiler's existing constant fold for integers, and only it: a
value it does not reduce -- `-1` written with the unary operator, a float
expression, a local initialised from another local -- is not recognised as a
constant, and such a function is accepted. A negative result is spelled in the
diagnostic as the subtraction that folds (`int n = 0 - 1;`).

## 8. Traps

A trap writes one line to **stderr** and exits with status **1**. It is not
catchable; `id` has no exceptions.

| condition | message |
| --- | --- |
| `fail(MSG)` | `id: MSG` |
| `/` or `%` by zero | `id: division by zero` / `id: remainder by zero` |
| `MIN / -1` | `id: division overflow` |
| shift by a negative count | `id: shift by a negative amount` |
| list index outside the list | `id: index N out of bounds (len M)` |
| `pop` of an empty list | `id: pop from empty list` |
| mutating a conf.id list constant (`push`, `pop`, index-assignment) | `id: cannot mutate a constant list` |
| a closure (§1.1.1) passed to a `native`'s `func(...)` parameter | `id: a closure cannot be passed to a native: it takes a plain function pointer; pass the function by name, or give the native the values another way` |
| flat-store access outside the store | `id: store address N out of range (size M)` |
| a list grown past its capacity limit | `id: list capacity overflow` |
| a size computation that overflows | `id: allocation size overflow (WHAT)` |
| allocation refused by the host | `id: out of memory (N bytes)` |
| a NUL byte reaching a string through `read_all`, `input`, `str_of_mem` | `id: a NUL byte reached a string (WHICH): use idstd stdio_slurp or stdio_read_mem, or the store (fs_read_mem), for binary data` |
| `chr` of a code whose low byte is 0 | `id: a NUL byte reached a string (chr(0)): a string cannot hold NUL; use the store (poke8) for binary data` |
| `str_sub(s, i, n)` with a span outside `s` | `id: str span out of bounds: i=I n=N in a string of length M; clamp i and n first (fx_min, fx_max)` |
| a `native` returning a list or struct whose `IdList` has a negative length (every other such result is copied into a list the runtime owns, so `push` works on it) | `id: a native returned a malformed list (len N): fill len cells at data, or size the list from id and return a count` |
| reading an export whose declaring function has not run: a list anywhere; any type in a test case | `id: read of an uninitialised export (its declaring function has not run)` |

`fail(msg)` is the program's own trap: `msg` is a `string`, the line is `id: `
followed by it, and it returns nothing because it does not come back. It
behaves as every trap does -- a case's `then traps:("TEXT")` matches it, a
`--lib` call returns status 1 and `NAME_error()` holds the line, a wasm module
raises `IdTrap` carrying it, and a trap in a worker thread ends the process.
It is for a state the caller should not have reached; a condition the caller
can recover from is a return value.

The exact text is part of the specification, not an implementation detail:
these messages are what a user sees when their program fails, and a target
that words them differently makes the language feel different.

## 9. Program structure and I/O

- **A first line that begins exactly `#!` is skipped**, so that a file can be run
  as `./script.id` under `#!/usr/bin/env idrun`. It is the lexer's rule (and
  every tool that tokenizes `id`, because they all use the lexer): it applies to
  line 1 of a source file only, the line is not a token, and line 2 is still line
  2 in every diagnostic. A `#!` anywhere else, or a `#` that does not begin
  `#!`, is an error.
- `main(int argc, string[] argv)` is the entry point. Its `int` return is the
  process exit status. `argv[0]` is the program name, whose spelling depends on
  how the program was launched and is therefore **not** specified.
- A function may **continue into a `chain`** rather than split: `} chain (the
  same parameters, restated) {`, followed by up to three more actions, and the
  `return` clause at the end belongs to the whole function. A chain is a literal
  continuation — the parameters, the imports, and the locals declared by earlier
  segments are all still in scope. The restated parameter list must match the
  original exactly, in both type and name, and each segment is held to the
  three-action limit on its own rather than the segments being counted together.
  A chain may only follow a segment that spent all three of its actions: a
  segment that still had room should have kept writing rather than starting a
  new one, so there is one way to continue a function rather than two.
- `blank` is a statement that costs one action and does nothing. It exists to
  pad a segment up to three actions when, and only when, a chain follows and
  the chain's first statement costs more actions than the segment had room for.
  Only an `if` with an `else` costs more than one action, so that is the only
  statement a `blank` can stand in for; anywhere else the segment had room to
  keep writing, and the padding is rejected. A `blank` is invisible to the
  duplicate rule: a function padded with one is the same function as the one
  written without it, because it performs the same work.
  A function and its chains are one function: they do not count separately
  toward the three-functions-per-file limit, and one pair of test cases covers
  them all, because the segments execute as a unit. The duplicate rule (§7.2's
  neighbour: two functions with the same signature and the same logic are one
  function written twice) compares a chain function whole, like any other:
  the signature and every segment, in order, must match for two functions to
  be duplicates. A later segment depends on what the earlier ones computed, so
  it is not a unit of logic on its own.
- `print(x)` writes a value and a newline to stdout; `put(s)` writes a string
  without one -- an int or a float is an error, as in `put("" + x)`; `flush()`
  flushes.
- `eprint(x)` writes to stderr exactly what `print(x)` writes to stdout: it
  takes the same argument, spells the value the same way and ends it with a
  newline. **It flushes stdout first**, so when both streams reach the same
  place the lines appear in the order the program wrote them, a `put` line
  left unfinished included. Inside a test case it writes where the case's
  `print` does, never into the channel the harness reports through
  (`docs/TESTS.md`, "How it runs"). A `--freestanding` build has one output,
  and `eprint` writes there as `print` does: the `id` runtime's serial port.
- `input()` reads one line from stdin, without its newline, and returns `""` at
  end of input. `read_all()` reads the whole of stdin.
- An exported variable is initialised when its declaring function runs, not
  before. Reading one earlier is rejected at compile time when the exporting
  function is unreachable from `main`, and is otherwise the programmer's
  responsibility.
- **`} return void export NAME;`** says that a function exists to initialize
  the exported variable `NAME`. The function is still void and returns
  nothing; the clause only states its purpose, and it changes nothing in what
  is emitted, on any target. `NAME` must be exported in the function's own
  body (`export TYPE NAME = ...;`), not in a function it calls, and exactly one
  name is allowed; each of these is an error that says how to fix it, as is
  `export NAME` after a return type that is not `void`. Its one effect is on
  the function's own test cases: they may read `NAME` in every form of
  `(import NAME)`, which a case otherwise may not do for a variable the
  function under test only declares (`docs/TESTS.md`, "A case never reads back
  what its own call made"). The cases of a function that calls it are still
  held to that rule for `NAME`.
- An exported variable whose declaring function is unreachable from `main` is
  not emitted at all, in a build that has a `main` and is not
  `--freestanding` -- the original `idc.py`, now deleted, did not prune
  (docs/HACKING.md). Safe for the reason above: nothing reachable can read an
  export a check has already rejected reading. A no-main library, a
  `--freestanding` build, and the test harness's own unit each keep exactly
  what they already keep nothing else from (docs/HACKING.md, "the exported-
  global block").
- A variable exists from its declaration to the end of the block that declares
  it; a function's return clause sees the body's top-level declarations. A use
  anywhere else, including before the declaration, is rejected at compile time.

## 10. Deliberately unspecified

Naming these keeps them from being discovered as bugs later:

- `argv[0]`'s exact spelling.
- The printed spelling of a NaN. `0.0 / 0.0` prints `-nan` under glibc and
  `nan` through LLVM, because the two disagree about the sign bit of the NaN
  they produce, not about anything `id` decides. The infinities *are*
  specified: `1.0 / 0.0` is `inf` and `-1.0 / 0.0` is `-inf`.
- The address `alloc` returns, beyond "nonzero, 8-aligned, and distinct from
  every other live allocation".
- The order in which unrelated top-level definitions are emitted.
- Timing: `ticks()` is monotonic milliseconds from an unspecified origin.
- Nothing about the order operands are evaluated in: §7 chooses it.
- Anything reached through a native backend, which is by definition
  platform-specific — but see the `native` declarations in idstd's
  `host/io/fs/`, `host/dev/win/gfx/`, and `host/dev/win/gl/`, which are the contract in
  `id`'s own types.

## 11. Where the targets have diverged from this specification

Found by writing this document and running the conformance suite
(`idc/tests/conform.sh` today). Each is a bug against the spec, not a permitted
variation. Which of them still apply is not recorded here: the conformance
suite prints every remaining divergence under "gaps", so run it and read that.
The rows below say what each one was and why it happened.

| # | what | affected |
| --- | --- | --- |
| **S1** | Overflow wrapped only because the compiler chose to; C calls it undefined. nixpkgs' gcc wrapper adds `-fno-strict-overflow`, which hid it, while the unwrapped clang of the wasm target folded `x + 1 > x` to `1` at `INT_MAX`. Every C compile now passes `-fwrapv`, and `conform/int/18-overflow-not-assumed` is what fails without it. | C, WASM |
| **S2** | Shifts with a count outside `0..W` gave three different answers: `(0 - 8) >> 32` was `-1` (§2.3) on C, `0` on LLVM, and `-8` on WASM, which masks the count to 5 bits. Both now route through helpers that give §2.3's answer. | LLVM, WASM |
| **S3** | `str_of_int` was wrong for `INT_MIN`: `2147483647 + 1` printed `-./,),(-*,(`, because the digit loop negated a negative value, which overflows, and every digit then came out as `'0' - d`. It now folds into the negative half of the range, which is always representable. | WASM |
| **S4** | `int` division and remainder by zero did not trap: LLVM raised SIGFPE (exit 136) and WASM aborted (exit 134) where C prints a line and exits 1. The checked-division fix recorded as C2 in `docs/GAPS.md` (retired; `git show 479234a^:docs/GAPS.md`) had been applied to the C runtime only. | LLVM, WASM |
| **S5** | Float-to-string is not implemented, so printing or concatenating a float fails to compile — the 10 remaining gaps, and now the only one left. | WASM |
| **S6** | `word`, the flat store and the unsigned builtins were rejected — 21 of 30 builtins, making §6 unimplementable. LLVM now calls the C runtime's helpers (which it already links); WASM implements the store in its own WAT over linear memory, which is its natural home. Only the real-time I/O builtins remain C-only, and those are genuinely platform-bound. | LLVM, WASM |
| **S7** | Because of S6, `idstd` did not build — `core/data/buf/buf.id` uses `word`. Fixed with S6. | LLVM, WASM |
| **S8** | Calls resolved at link time were refused, so no program using a native backend built. LLVM links the same backends as C (`idc/tests/backends.sh` compares the two). **WASM now serves a backend that declares `wasm_wasi_sources` (its C, compiled for wasm32-wasi) or `wasm_js` (a JS module; the native stays an import, `env.id_NAME`, answered by the generated `<name>.mjs`), reached-only as for C.** idstd's `fs` and `env` have both; `sock`, `proc`, `gfx` and `gl` have neither and are refused at the call that reaches them. WASI's preopened file system is deliberately not used: a path would not mean what it means on the C target. See `docs/INTEROP.md`, "id and JavaScript". | WASM (sock, proc, gfx, gl) |
| **S9** | The LLVM and WASM targets were once reachable only from `idc/idc.py`. `idc/bin/idc` now has all three: `--target c`, `llvm` and `wasm`, where wasm recompiles the C target's C for wasm32-wasi. | — |
| **S10** | The flat store sits at a fixed 1 MiB offset in the same linear memory the string/list heap grows through, so **the heap is capped at 1 MiB**. Passing it used to overwrite the store and read back garbage with nothing reported — a 400 000-element list made `peek64` return `71772820526333952` where C returned `123456789`. The heap now aborts with `id: out of memory` instead, which is §7-legal, but the cap is real and the other two targets do not have it. The proper fix is to place the store above the heap and grow it with `memory.grow`, checking the heap against its actual base rather than a constant. | WASM |

| **S11** | **The C target does not evaluate operands left to right**, which §7 now requires. It emits one C expression per `id` expression, and C does not sequence the arguments of a call: gcc evaluates them right to left, so `"pop=" + pop(xs) + " len=" + len(xs)` prints the length *before* the pop. The LLVM and WASM targets both conform, because both emit instructions in the order they walk the tree. Found by `idc/tests/kernel.sh`, which runs the same source on both runtimes and requires them to agree. | C |

**How S11 was fixed.** An expression in which two operands each contain a
*unit* -- a call, an index read, an `import`, a division that can trap, or an
`&&`/`||` -- binds the units to temporaries left to right, children before
parents, with the comma operator: `int idsq_8;` on the line before the
statement, then `(idsq_8 = id_bump(c), id_pair(idsq_8, id_bump(c)))`. For an
`if` / `else if` chain every temporary is declared before the first `if`.
Everything else is pure, so only the order of units is observable. A `while`
or `else if` condition stays where it was written, so it is still evaluated on
every iteration and only when reached; `&&` and `||` keep C's own
short-circuit. The emitter is `back/tgt/c/emit/prog/code/expr/atom/order/`.

The output is C11 plus one GNU extension, the statement expression `({ ... })`,
which gcc and clang both accept: the runtime's `ID_S` and `ID_FNV` macros use
it, and so does freeing a fresh call result passed straight to another call
(`g(f(x))`, docs/MEMORY.md). That matters because the compiler's own C is the
stage-0 bootstrap, so a compiler without the extension cannot build it. Names beginning `idsq_` are reserved for these temporaries
and rejected in source. Byte-parity with the original `idc.py` was lost for every
statement that needed sequencing.

`idc/tests/conform/order/` holds the cases, now passing on all three targets.

| **S12** | **Function values (§1.1) on WASM.** This row said they were missing because the WASM target was then built by the deleted `idc.py`. `idc/bin/idc` now builds wasm from the C target's C, which has them; `idc/tests/conform.sh` prints any remaining `wasm:fn` gap under "gaps". | WASM |

| **S13** | **Closures (§1.1.1) on `--freestanding`.** The runtime written in `id` has the calls a module makes (`clo_make`, `clo_set`, `clo_cell`, `clo_fn`, `fn_plain`, `fn_raw`, `clo_copy`; `idc/runtime/mem/clo/`), and a program that binds builds and links. Two things differ from the hosted runtimes, both for want of a place to trap to: the list a closure captures is not locked, so a write to it is unchecked (as it is for every list constant there, §8), and a closure given to a native's function-pointer parameter reaches it as a null rather than stopping the program. A `float` captured needs `id_box_f`, which that runtime does not define for a list either. | freestanding |

`docs/BACKENDS.md` is the plan for the compiler restructuring these imply.
