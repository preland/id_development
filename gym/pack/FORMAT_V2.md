# Pack format, version 2 additions

Everything in `FORMAT.md` still holds. Version 2 adds what a proof-based subject needs, and what lets the
engine choose how to present a concept from how the learner behaves instead of following the source's
order or layout.

## Principle

A pack stores **knowledge in pieces, not in the source's sequence**: each concept carries several
presentations and several kinds of exercise, and the source's chapter order survives only as the
prerequisite graph (`requires`). The engine decides, per learner and per moment, which presentation and
which exercise comes next (confident errors -> a non-example and an error hunt; heavy hint use -> faded
worked examples; fast, correct, confident answers -> proofs and synthesis).

## Concept additions

```
concept: injective
name: Injective function
summary: A function that never sends two different inputs to the same output.
requires: function_definition, implication
part: 7
source: p. 213-215
show_intuition: No two arrows land on the same point of the codomain.
show_definition: f: A -> B is injective when, for all a1, a2 in A, f(a1) = f(a2) implies a1 = a2.
show_example: f(x) = 2x + 1 on the integers: if 2a1 + 1 = 2a2 + 1 then a1 = a2.
show_non_example: f(x) = x^2 on the integers: f(-1) = f(1) but -1 != 1.
show_worked: To prove f(x) = 3x - 5 is injective, assume f(a) = f(b); then 3a - 5 = 3b - 5, so 3a = 3b, so a = b.
misconception: Checking that every input has an output (that is "function", not "injective").
```

| key | needed | meaning |
| --- | --- | --- |
| `part` | yes in v2 packs | the source's part number (used for synthesis across parts) |
| `source` | yes | page references in the source (`p. 213-215`), never long verbatim passages |
| `show_intuition` | yes | one plain-language picture of the idea |
| `show_definition` | yes | the precise statement |
| `show_example`, `show_non_example` | yes, each repeats | concrete instances; a non-example targets a misconception where possible |
| `show_worked` | no, repeats | a short worked proof or computation using the concept |

Presentations are paraphrased in the pack's own words; they are not copied from the source.

## Item additions

New `kind` values: `proof` (write a proof), `synthesis` (combine concepts from at least two different
parts into one argument or construction), `compare` (two problems; name the shared structure),
`counterexample` (give one and say why it works), `negate` (write the negation of a statement).

New `answer_kind` values:

| `answer_kind` | the learner writes | how it is judged |
| --- | --- | --- |
| `free` | prose or a proof | the grader model against `rubric` and `answer` (a model proof); low grader confidence -> the learner self-grades against the reference |
| `set` | a finite set such as `{1, 2, {3}}` | exact set equality (order and repetition ignored), nested sets allowed |
| `truth` | a truth-table column as `TFFT` in the standard row order | exact |
| `choice`, `integer`, `fraction`, ... | as in FORMAT.md | as in FORMAT.md |

Extra keys:

| key | for | meaning |
| --- | --- | --- |
| `bridge` | `synthesis`, `compare` | one line naming the general principle the item makes the learner extract (e.g. "a property preserved by every step is preserved by the whole process: induction, invariants and closure are one idea") |
| `presentation` | any, optional | which concept presentation (`intuition`, `definition`, `example`, `non_example`, `worked`) best explains this item's answer; the engine shows it with the result, only after a committed attempt (P1), and may choose another from the learner's history |

A `synthesis` item lists at least two concepts, from at least two different `part`s. `rubric` lines for
`free` items must be checkable statements ("states the inductive hypothesis explicitly"), never "good proof".
