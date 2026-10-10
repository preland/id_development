# Mental Gym in id: build plan

The product spec is `../Mental Gym — Design Principles.md`. This file records how the MVP is built in id
and idml, and the defaults chosen where the spec leaves a choice open. It is also a trial of id in a real
product: anything id or idstd makes awkward is written down in `TRIAL.md` as it happens.

## Defaults chosen for the MVP (each is one module or one setting)

| Choice | Default | Why |
| --- | --- | --- |
| MVP domain | Probability fundamentals: answers are numbers, fractions or short exact forms | Tool-checkable answers (spec, "MVP domain"); one exact checker, no CAS |
| Storage | Plain files: a pack directory per subject, an append-only event log per learner | Pure id (no SQLite binding in idstd); replaying the log rebuilds every number, so nothing is lost or silently overwritten |
| Memory model | FSRS-6 with its published default weights | Spec, "Two models" |
| Skill model | Elo per (learner, concept) against item ratings | Spec, "Two models" |
| Calibration | Brier score over confidence (50/70/90/99%) | Spec, scoreboard |
| Interface | Native window through idstd's idml kit, plus a scriptable CLI for every action | Native first (user decision 2026-10-08); the CLI makes every flow testable headless |
| Models (phase 2) | Grader and coach on the small local model (Qwen3-4B, `serve-small`, port 8183) | Spec: grading must answer in a second or two |

## Modules

| Path | Job |
| --- | --- |
| `idstd/core/learn/` (prefixes `fsrs_`, `elo_`, `brier_`) | Pure math, reusable by any app: FSRS-6 stability/difficulty/retrievability and next interval; Elo update and expected score; Brier score and calibration bins |
| `gym/pack/` | Read a subject pack (concepts, items, hint ladders, misconceptions, transfer items) from text files and validate it |
| `gym/check/` | Decide whether an answer matches a reference: exact integer, fraction, decimal with tolerance, percent, short normalised text, a choice |
| `gym/log/` | Append events (attempt, hint, tap-out, self-grade) to the learner's log; replay the log into state |
| `gym/plan/` | Build a session: warm-up (due reviews, no hints), main set (new or weak, success band 75-85%), transfer finisher (held-out items), cooldown |
| `gym/score/` | Retention, transfer, calibration, independence, fluency from the replayed log |
| `gym/cli/` | `gym` command: `session`, `answer`, `hint`, `tapout`, `score`, `why`, `pack check`; every command scriptable with a fixed clock |
| `gym/ui/` | The window: rep screen (prompt, answer, confidence, hint ladder, tap-out), session progress, scoreboard, concept map |
| `gym/ai/` (phase 2) | Grader and coach through the local model; the reference answer is never sent before an attempt is logged; hint leak check; structured feedback with required fields |

## Rules every module keeps

- The clock is an argument (milliseconds since the epoch), never read inside the logic, so every flow has
  deterministic cases.
- Nothing the learner sees comes from a source that is not in the pack or the log.
- No XP, streaks, minutes or completion percentages anywhere (spec P9).

## Format v2 (proof-based subjects)

`pack/FORMAT_V2.md` is implemented across the same modules: `gym/pack/rules/parts.id`, `synthesis.id`, `free.id`
(the version 2 rules), `gym/check/` (`set`, `truth`, `free` answers: `brackets.id`, `atom.id`, `members.id`,
`collection.id`, `pending.id`), `gym/log/` (the `graded` line and the replay-time settling of pending attempts:
`graded.id`, `settle.id`), `gym/session/` (`grade.id`, `take.id`, `marks.id`, `present.id`, `show.id`: free
answers, self-grading, what to show with a result), `gym/plan/` (`present*.id`, `match.id`, `fade.id`,
`tally.id`, `kinds.id`, `retarget.id`, `row.id`, `order*.id`, `synthesis*.id`: the presentation policy, kind
ordering and synthesis) and `gym/score/synthesis.id` (the sixth number). Every choice the engine makes from
behaviour carries a reason line that `gym why` prints.
