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
