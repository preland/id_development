# gym/plan: the session planner

Pure: the clock (`now`, milliseconds since the epoch) and the randomness (`seed`)
are arguments, so a plan for a fixed pack, log, time and seed is always the same.

## Calling it

```
Pack book = pack_load(directory);                    // gym/pack
Log_replay log = log_replay(path);                   // gym/log
Plan_session plan = plan_for_log(book, log.events, now, seed);
```

| function | what it answers |
| --- | --- |
| `plan_for_log(Pack, Log_events, word now, int seed) -> Plan_session` | the whole plan from a pack and a replayed log |
| `plan_build_book(Pack) -> Plan_book` | the numeric index of a pack (ids, item ratings, item-to-concept links, prerequisites) |
| `plan_replay(Plan_book, Log_events) -> Plan_learner` | the learner a log replays into: FSRS state and Elo rating per concept, item ratings and attempts |
| `plan_build_session(Plan_book, Plan_learner, word now, int seed) -> Plan_session` | the plan, when the caller already holds the book and learner |
| `plan_why(Plan_session, string item_id) -> string` | the reason line of one item in the plan, `""` if it is not there |
| `plan_hints_allowed(string phase) -> int` | 0 for `"warmup"` (cold), 1 for any other phase |
| `plan_due_count(Plan_learner, word at) -> int` | concepts whose predicted recall is at or under 0.90 at time `at`; the cooldown shows it for `now + 86400000` after replaying the finished session's log |
| `plan_recall(Plan_learner, int concept, word at) -> float` | predicted recall of one concept (0.0 if never attempted) |

A `Plan_session` is three parallel lists: `ids` (item ids), `phases` and `reasons`.
Phases, in the order a session runs them: `"warmup"`, `"main"`, `"transfer"`; the
2-minute cooldown has no items.

## The plan

| phase | time | rows |
| --- | --- | --- |
| warmup | 5 min | up to 5 concepts whose recall is at or under 0.90, lowest first, one item each, hints unavailable |
| main | 13 min | up to 9 weak concepts (recall under 0.95, not in the warm-up), then new concepts to fill 13 rows in all: at most 3 new concepts, 3 rounds, unlocked only when every prerequisite has an attempt in the log; interleaved round by round, the seed ordering ties |
| transfer | 5 min | up to 2 held-out items whose concepts were all attempted in the log, never attempted ones first |

An item is never in a plan twice. An item is chosen for a concept by its cost
(`fit_of.id`): how far its expected first-try success falls outside 75 to 85 percent,
10 per earlier attempt (a fresh variant is preferred), 400 when its latest attempt
was an again (a failure or a tap-out).

## Reasons ("why am I seeing this?")

```
due: recall predicted 0.71 at 4.2 days; expected first-try success 78%
weak: recall predicted 0.92 at 9.0 days; expected first-try success 79%
new: prerequisites done; expected first-try success 64%
new: no prerequisites; expected first-try success 50%
transfer probe for odds, dice
```

## Knobs (conf.id, all `plan_*`)

Slots: `plan_warm_up_slots` 5, `plan_main_slots` 13, `plan_review_slots` 9,
`plan_transfer_slots` 2, `plan_new_limit` 3, `plan_depth` 3. Band:
`plan_band_low` 750, `plan_band_high` 850 (thousandths). Scores:
`plan_due_score` 900, `plan_mastery_score` 950. Elo: `plan_start_float` 1000.0,
`plan_factor` 32.0. Costs: `plan_attempt_cost` 10, `plan_again_cost` 400. The
attempt-to-grade mapping is documented at the top of `grade.id`.

## Decisions to know about

- Events are replayed in file order, not sorted by time; an append-only log is in time order.
- `unparseable` counts as incorrect; the learner's own self-grade field is not used.
- Elo score of an attempt: 1.0 for grades 3 and 4, 0.5 for grade 2, 0.0 for grade 1.
- Every concept an item lists is reviewed and rated by that attempt.
- Transfer probes use only concepts attempted in the log, not those planned for the same session.
- A prerequisite the pack does not define blocks its concept forever (the safe reading of a broken pack).

## Tests

Cases use a built-in world (`plan_world_packs`, `plan_world_logs` in conf.id) through
the setups in `fixture.id`; scene 0 is an empty log, 1 a failed coin history, 2 coin
and dice practised, 3 adds odds and a seen transfer item, 4 everything mastered,
5 a tapped-out item. "Now" in the cases is day 10, 864000000 ms.

## Version 2 packs: kinds, presentations and synthesis

Everything below applies only to a pack with a `part:` line on some concept (`pack_has_parts`); a version 1 pack
is planned exactly as above. `plan_for_log` runs two steps after `plan_build_session`:

1. **`plan_adjust`** (`retarget.id`, `row.id`, `order.id`, `order_put.id`). For each concept it reads the
   learner's history (`tally.id`: attempts, misses, clean answers, sure errors, whether the latest answer was
   fluent) and sets a level (`kinds.id`): *novice* (fewer than 2 attempts, or more misses than hits), *strong*
   (at least 2 clean answers and at most a third missed) or *learning*. A main-set item may be swapped for
   another practice item of the same concept that is not in the plan, when its kind ranks higher for the level
   and its difficulty is within 400 of the original, raised by 100 when the latest answer was fluent. Then the
   items of a concept that has two or more main rows are re-ordered by kind rank (novices: error hunt, choice,
   recall, solve, ..., proof last; strong learners: proof, counterexample, compare, ... first), easiest first
   within a kind. Ids and reasons move together, and every moved row says so in its reason.
2. **`plan_with_synthesis`**. A synthesis item (`kind: synthesis`; the book gives it link flag 2, so it is
   neither practice nor transfer) is offered only when every concept it lists has predicted recall of at least
   0.85 at the planning time *and* at least one clean answer (right, no hint, no tap-out). The unlocked item
   attempted least often is chosen; it replaces the last new-concept row of the main set, or is added at the
   end of the main set when there is room (fewer than 13 rows). At most one per plan.

### Presentation policy (`present.id`, `present_text.id`, `match.id`, `fade.id`)

After a committed attempt (and, for a free answer, once graded) the engine chooses what to show from the attempt
and the concept's earlier misses. Nothing is stored: `gym why ITEM` rebuilds the choice from the log.

| attempt | shown | reason line |
| --- | --- | --- |
| wrong, confidence 90 or 99 | `show_non_example` (aimed at the written misconception the answer resembles, if any), then `show_definition` | `confident error (99% sure, and wrong): ...` |
| wrong, lower confidence, first miss on the concept | `show_worked` in full | `wrong with low confidence (70%): the worked example in full ...` |
| wrong, lower confidence, missed before | `show_worked` faded: the first half of its steps, the rest left to the learner | `... after 2 earlier miss(es) on the concept: the worked example faded ...` |
| right, but with hints or slower than 90 s | `show_example` | `right, but with 2 hint(s): another example of the idea` |
| right, no hints, 30 s or less, confidence 90 or more | nothing; item difficulty for the concept goes up (the next plan prefers items 100 harder) | `right, fast and confident (...): nothing to add; move on, ...` |
| right otherwise | nothing | `right and unassisted: nothing to add` |

The misconception is the concept's `misconception:` line sharing the most content words (5 letters or more)
with the item's prompt and the learner's answer, at least two. When several `show_example`, `show_non_example`
or `show_worked` lines exist, the one sharing most words with that belief (or the answer) is shown, else they
rotate with the number of earlier misses. A presentation the concept lacks is replaced by the one the item's
`presentation:` names. Thresholds: `plan_slow_seconds` 90, `plan_fast_seconds` 30, `score_confident_level` 90.

Knobs (conf.id): `plan_kind_slack` 400, `plan_kind_weight` 200, `plan_difficulty_step` 100,
`plan_solid_attempts` 2, `plan_synthesis_recall` 850, `plan_order_novice`, `plan_order_learning`,
`plan_order_strong`.
