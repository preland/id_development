# Documentation index

> **Status: describes current practice.** Every document in this directory is
> listed here once, with what it is for, and nothing that is not in this
> directory is listed. `idc/tests/run.sh` (section `core_rest`) fails when a
> `docs/*.md` file is missing from this table or a row names a file that does
> not exist. A document's own first line says whether it describes what is
> built, a plan, or a proposal; this page does not repeat that.

Numbers that change (functions, cases, untested functions, depth, the mutation
score, benchmark ratios) are not written in any document. They are in
[`STATUS.md`](STATUS.md), which `idc/tools/statusgen` writes from the tree, or
come from the command a document names.

## Language and compiler

| doc | what it is for |
| --- | --- |
| [`SPEC.md`](SPEC.md) | what an `id` program means: the language, normative, each claim a case under `idc/tests/conform/` |
| [`STRUCTS.md`](STRUCTS.md) | records (`struct`): the design, its decisions, and what was built |
| [`ASM.md`](ASM.md) | `asm` functions and the platform triples that select among them |
| [`DISPATCH.md`](DISPATCH.md) | calling a function chosen at run time: the proposal and what function values replaced |
| [`MEMORY.md`](MEMORY.md) | freeing memory before exit: the design and the first slice of it |
| [`THREADS.md`](THREADS.md) | threads: the audit of what the runtime shares, the options, and the slices built |
| [`ERRORS.md`](ERRORS.md) | every error code the compiler emits, with the example each is tested against |
| [`DIAGNOSTICS.md`](DIAGNOSTICS.md) | the diagnostic record and its output formats |
| [`HACKING.md`](HACKING.md) | changing the language: where each feature lives in the compiler, the bootstrap rule, the loop |

## Tests

| doc | what it is for |
| --- | --- |
| [`TESTS.md`](TESTS.md) | test cases as part of a function: the case form, the rules, mutation score, how the harness runs |
| [`STATUS.md`](STATUS.md) | generated: per-tree counts, cases per function, shape, test sections, benchmark ratios, mutation score |

## Backends, interop and performance

| doc | what it is for |
| --- | --- |
| [`BACKENDS.md`](BACKENDS.md) | making the self-hosted compiler backend-agnostic: the plan and which steps have landed |
| [`LLVM.md`](LLVM.md) | the LLVM target and the IR it is printed from |
| [`INTEROP.md`](INTEROP.md) | id and JavaScript, id as a library, calling C from id, id instead of Python, and translating C to id |
| [`INTERPRETER.md`](INTERPRETER.md) | an interpreted mode: the scoping and the milestone built |
| [`PERFORMANCE.md`](PERFORMANCE.md) | how far id is from C and Rust, how it is measured, and what the numbers are attributed to |
| [`RELIANCES.md`](RELIANCES.md) | where this project is not written in `id`, with the cost of moving each piece |

## Projects and programs

| doc | what it is for |
| --- | --- |
| [`PROJECT.md`](PROJECT.md) | starting an `id` project: the layout rules, the project model, the standard library, the things that go wrong |
| [`UI.md`](UI.md) | the GUI toolkit, laid out by idml |
| [`EDITOR.md`](EDITOR.md) | the OpenDocument editor |
| [`WORD.md`](WORD.md) | the word processor grown from the editor: plan, seams and work packages |
| [`KERNEL.md`](KERNEL.md) | the kernel and the runtime under it |
| [`RUNNING.md`](RUNNING.md) | running the kernel and the editor |
| [`HYPRLAND.md`](HYPRLAND.md) | running the graphics demos without losing your place, for one compositor |
