# The scoreboard

Pure functions from a replayed log and a pack to the five numbers of spec P9/P10. The clock is an
argument (`now`, ms since the epoch); nothing reads a file or a clock.

```
Log_replay replayed = log_replay(path);
Pack book = pack_load(directory);
Score_table table = score_table(replayed.events, book);
Score_figure retention = score_retention(table, score_default_minimum);
```

A `Score_figure` is `(sample, enough, value)`. Below the minimum number of attempts `enough` is 0
and `value` is 0.0: show `score_describe(figure, minimum)`, never the value. A `Score_figures`
(per concept, per week) holds `-1.0` (`score_unknown`) in `numbers` for the same case.

| Metric | Function | Value |
| --- | --- | --- |
| Retention | `score_retention`, `score_retention_concepts`, `score_retention_trend` | accuracy 0.0 to 1.0 |
| Transfer | `score_transfer`, `score_transfer_trend` | accuracy 0.0 to 1.0 |
| Calibration | `score_calibration`, `score_calibration_table`, `score_confident_list` | Brier score; table rows of (count, mean confidence, accuracy) for 50/70/90/99; positions of confident errors, newest first |
| Independence | `score_independence`, `score_independence_trend` | hints plus tap-outs per solved attempt |
| Fluency | `score_fluency`, `score_fluency_concepts` | median seconds |
| Records | `score_record_retention`, `score_record_transfer` | best week with enough attempts |
| Text | `score_define`, `score_describe` | the "what does this mean" line; a figure as a line |

There are no streaks, XP, minutes or completion percentages here; `score_forbidden_count` is the
guard that the shown text contains none.

## The sixth number: synthesis

`score_synthesis(table, minimum)`: accuracy on attempts at `kind: synthesis` items made without a hint and
without a tap-out (an attempt still pending a grade is not in the table at all). The same "not enough data"
rule applies. The pack labels such an attempt with the marker `~synthesis` among its concepts
(`,ca,cb,~synthesis,`), so no struct changed. Its definition is `score_define("synthesis")`.
