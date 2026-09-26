---
name: id-case-writing
description: Use when an `id` project tree (compiler/parse, editor, c2id, idstd, or similar) has dozens or more functions short of the two test cases docs/TESTS.md requires, and the backlog should be cleared by many parallel cheap (Haiku-tier) agents instead of one agent working through the list serially. Symptoms — `idc/tools/casework.sh list PATH` prints many rows, or `--list-untested` / the adoption table in docs/TESTS.md shows a large "short of two cases" count for one project.
---

# Writing `id` test cases at scale

## The problem this solves

Writing a function's two cases (docs/TESTS.md) is cheap when the case-writer
already knows what to write. It is expensive when they have to first
reconstruct, by hand, what state the function needs and which `given` setup
can build it — and that reconstruction is where almost every failure happens
today. The single dominant failure across every batch measured so far:

```
test failed: is_reach("main") trapped: id: read of an uninitialised export
```

An export exists only once its declaring function has run, and that
declaring function is very often not the function under test, or even
something it calls directly — it is two or three calls deeper. Grepping the
target function's own body for `(import NAME)` (what `casework.sh packet`
does) cannot see that. This skill's whole value is precomputing the
transitive answer once, in a real index, so a cheap agent never has to trace
imports by hand.

## Workflow

**Status: `idxpack.sh PATH TARGET` (below) is built, runs on a real
~3000-function project, and its candidate-`given` search was validated
against a real function (see the validation report). `select`/`pack`/a
multi-function batch mode are designed — the packet shape a Haiku agent
needs is fixed, and `case-writing-prompt.md` already expects it — but not
yet implemented; step 2 below is a manual stand-in until they land. Do not
claim `select`/`pack` work; they do not exist as commands yet.**

1. **Build the index and query one target.** `build` rebuilds `idxpack` and
   runs `idc PATH --calls` — the expensive part, about 8s cold and 2s warm
   for something the size of `compiler/parse` (measured 2026-09-26) — so
   build once and query several targets:

   ```sh
   idc/tools/idxpack.sh build <PROJECT_PATH> <OUTDIR>
   idc/tools/idxpack.sh query <OUTDIR> <TARGET_FUNCTION_NAME>
   ```

   `build` is the expensive step, once per project; `query` is cheap, once
   per target.

   Prints three blank-line-separated lists: `TARGET`'s transitive call
   closure (BFS over `call` edges), the exported names that closure reads
   anywhere (the transitive-import fix over `casework.sh packet`'s
   own-body-only grep), and every zero-parameter `void` function in the
   build whose own closure reaches every one of those exports' declaring
   functions — the legal `given` setups. An empty third list does not
   necessarily mean no setup exists — see "Known limits" below before
   concluding that.

2. **Pick targets, and assemble a packet, by hand for now.**
   `idc/tools/casework.sh list <PROJECT_PATH>` still gives the uncased-function
   list. Do not drop names `idc/tools/chainfind.sh` lists as fold candidates:
   its list is unsound (it cannot count call sites, among other gaps) and rule
   6 is not shipping, so a fold candidate is cased like any other function —
   if it is folded later, its cases are rewritten then. For each target, run step 1, then hand-build a packet section
   combining `idxpack.sh`'s three lists with `casework.sh packet`'s source
   and structural-slot output (it still has both, even though its own
   import-list line is the thing you should ignore in favour of `idxpack`'s).
   Batch 3-5 such sections into one packet for one agent.

3. **Spawn one Haiku agent per packet, in parallel.** Use the Agent tool,
   `model: "haiku"`, one call per packet, all in the same message so they run
   concurrently. Build each prompt from `case-writing-prompt.md` in this
   skill's directory: substitute `{PROJECT_PATH}` and paste your packet in as
   `{PACKET}`. That file states the case syntax and the anti-patterns
   inline — the agent must not need to open docs/TESTS.md.

   **Each agent needs a private workspace.** A PreToolUse hook blocks every
   subagent write under `/home/preland/git`, so an agent pointed at the real
   tree cannot edit anything. Before spawning, copy into a scratch directory
   per agent: `idc/` (with `.idc-cache/`, which holds the built compiler
   stages, but without `.idc-cache/units/` or `build/`), `idstd/`, and the
   project tree if it lives outside `idc/`, keeping the umbrella's relative
   layout. Tell the agent, in an environment note before the packet, its
   workspace path, to `export IDSTD_HOME=<workspace>/idstd`, and to run every
   command from `<workspace>` (where the prompt says "the repo root"). Give
   agents whose targets are in the same directory separate workspaces, and
   merge each one back yourself (`git mv` for any moves, then copy files).

4. **Collect and verify.** Each agent's report says, per function, DONE
   (with the verification and falsification output), or FAILED with a
   reason. For anything reported DONE, spot-check by re-running:

   ```sh
   idc/tools/casework.sh verify <PROJECT_PATH>
   ```

   once per round (not per agent — it rebuilds the whole tree). A round
   where this fails means an agent's report was wrong; find which function
   by the file:line the failure names and re-open that one case.

5. **Refusals are data, not failure.** An agent that refuses a function with
   a stated reason (the state it needs can only be built by a function that
   takes parameters; an honest case would need a program outside the Nix
   devshell, leave files behind, or push the build past 60 seconds) has done
   its job correctly. Collect
   refusals; do not re-assign them to another Haiku agent expecting a
   different answer — escalate to a human or a more capable agent only if
   the reason looks wrong.

## Known limits (read before trusting an empty candidate-`given` list)

- **A name with no declaring function poisons the whole search.** If any one
  of a target's transitive imports has no `export`-inside-a-function-body
  found anywhere in the scanned corpus — the common case is a `conf.id`
  constant, which docs/PROJECT.md says is "readable from `main`'s first
  statement on" and needs no setup at all — `idxpack` cannot find *any*
  candidate `given`, even a perfectly good one for the target's other
  imports, because nothing can "reach" a name with no declarer. When the
  candidate list comes back empty, read the imports list: if one entry says
  no declaring function was found, check by hand whether it is a `conf.id`
  constant (grep the project's root `conf.id`) before concluding no setup
  exists.
- **A declaring function that itself takes parameters** (state set inside a
  function like `arg_flags4(int argc, string[] argv)` rather than a bare
  `export` in a zero-parameter function) can never be reached by a
  zero-parameter `given` no matter what calls it — this is a real instance
  of docs/TESTS.md's "What the case format cannot express," not a bug, and
  `idxpack` returning nothing for it is correct.
- **`select`/`pack`/multi-target batching are not implemented.** Do the
  batch-selection and packet-assembly steps above by hand until they land.

## Common mistakes (from earlier unassisted batches)

- **Treating the packet's candidate lists as the only two options.** They are
  candidates, not a mandate — if none of the listed `given`s actually fits
  the two concrete behaviours being written down, say so and refuse, rather
  than forcing a case onto a setup that technically reaches the import but
  produces a meaningless state for this particular example.
- **Editing a file's function count or a directory's entry count without
  checking the packet's structural-slots line first.** A batch was chosen to
  fit; adding an unplanned helper function of your own can blow the file or
  directory limit for a function later in the same batch.
- **Running `casework.sh verify` per function instead of per round.** It
  rebuilds the whole project tree; running it after every single function in
  a multi-function batch wastes most of the ~2-minute build time N times
  over. Verify once, after the whole batch is written.

See `case-writing-prompt.md` for the literal per-agent prompt (case syntax,
anti-patterns, and the refusal/verification/falsification requirements),
and `docs/TESTS.md` in the repo root for anything this skill's summary of the
syntax leaves out.
