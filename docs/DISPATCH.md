# Calling a function chosen at run time

> **Status: a proposal. Nothing here is implemented.** No `select` exists in
> either compiler, in `docs/SPEC.md`, or in `idc/tests/conform/`. It is written up
> because four separate pieces of work are blocked on it and each invented the
> same workaround; it is not a description of the language.

`id` cannot express "call whichever function this is". Four separate pieces of
work are blocked on it, and all four have independently invented the same
workaround:

- **`idstd`** cannot write a sort that takes a comparator, so `lst_sort` is
  int-only and there is no `string[]` sort at all.
- **`c2id`** (`../c2id`) needs C function pointers, and its plan is a
  `crt_callN` helper dispatching on an integer id — listed as "planned: needs
  the emitter" since the front end was finished.
- **`docs/BACKENDS.md`** proposes selecting a code-generation target with
  `if(target() == "py")` chains, explicitly *because* "`id` has no function
  pointers, so a target cannot be a table of closures".
- **Every event loop** in `demos/` hand-writes a branch chain over a state
  integer.

Three of those four are chains of `if` on a value, written by hand, under a
3-action budget that makes each chain several files long. The language should
write them.

## Not function pointers

The obvious answer is a first-class function value. It is the wrong one here,
for reasons that are specific to this language rather than general:

- **It would be the first unchecked call in `id`.** Every call today resolves
  to a named function the compiler has seen, which is what lets it check
  arity, argument types and return type at the call site, and what makes the
  reachability analysis behind dead-code elimination exact. A value of
  function type defeats all of that at once.
- **It has no portable lowering.** C wants a function pointer, WASM wants a
  `funcref` in a table plus a `call_indirect` type index, LLVM wants a
  pointer with a signature, and an interpreter wants a closure object. That
  is four different ABIs for one feature — precisely the shape of thing
  `docs/SPEC.md` exists to prevent.
- **It invites closures**, which need captured environments, which need
  lifetimes, which `id` does not have (`docs/SPEC.md` §6).

## The proposal: a `select` set

A `select` declares a **named, closed set of functions that share one
signature**, and gives each member an index. Calling through the set with an
index calls that member.

```
select shape_area(int id) returns float {
  circle_area;
  square_area;
  tri_area;
}
```

- Every member must already exist and must have **identical parameter types
  and return type** — checked at compile time, like an `asm` overload set.
- The set is **closed**: its members are listed at the declaration. There is
  no way to add one at run time.
- `shape_area(1, ...)` calls `square_area(...)`. An index outside the set
  **traps**, with the same shape of message as an out-of-bounds list index.
- The index is an ordinary `int`, so it can be stored in a list, returned
  from a function, or read from input — which is the whole point.

## Why this fits

**It stays checkable.** The compiler knows every function the call can reach,
so arity and types are checked exactly as they are for a direct call, and
reachability stays exact — a `select` marks its members reachable, and nothing
else becomes reachable by accident. Dead-code elimination keeps working, which
matters because it is what makes an always-imported `idstd` affordable.

**It lowers to the same thing everywhere, with no new ABI.** Every target
already has the construct:

| target | lowering |
| --- | --- |
| C | `switch` on the index, or an array of function pointers — the emitter's choice, not the language's |
| LLVM | `switch` terminator over blocks that `call` directly |
| WASM | `br_table`, no `funcref` table and no `call_indirect` needed |
| interpreter | an index into a vector of function bodies |

None of those is a pointer crossing a boundary, so `docs/SPEC.md` needs one
new sentence (the trap on a bad index) rather than a new type.

**It is honest about what it is.** A `select` is a jump table with a name. The
programs that need it are writing a jump table by hand today; this one is
checked, is one declaration instead of a chain of files, and cannot silently
fall through to a wrong default — which the hand-written chains can and,
twice, have (`cs3` and `unbox3`, recorded in `docs/BACKENDS.md`).

## What it does not solve

- **No captured state.** A member is an ordinary function; anything it needs
  is a parameter or an import. A comparator that closes over a sort key must
  take it as an argument. This is a real limitation and it is deliberate —
  captured state is the part that needs lifetimes.
- **No open extension.** A library cannot let a user add a case to its own
  `select`. For `idstd`'s sort this is fine (the comparator is the user's
  whole set); for a plugin system it is not. If that is ever needed, it is a
  second feature and should be argued separately.

## Order of work

1. `docs/SPEC.md` gains the trap and the index rule.
2. `idc/tests/conform/select/` cases first, so all three targets are held to the
   same behaviour from the beginning rather than after the fact.
3. `idc/idc.py`: parse, check the signature agreement, emit for C. Byte-parity is
   not a gate here — the construct is new, so there is nothing to be identical
   to; the gate is the conformance suite.
4. The self-hosted compiler, with `idc/tools/parity.sh` back as the gate once
   both emit it.
5. LLVM and WASM.
6. Then `idstd` gets a real sort, and `docs/BACKENDS.md`'s dispatch layer
   stops being a chain of `if`.
