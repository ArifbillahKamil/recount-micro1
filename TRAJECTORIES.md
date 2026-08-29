# Agent trajectories — how to read them

Every evaluated case writes a full trajectory. Nothing is summarised or
reconstructed afterwards: each stage records into the trace as it runs, so what
you read is what happened.

```
runs/<run-label>/traces/
  baseline__B1_fanout_payments_via_line_items.md      human-readable
  baseline__B1_fanout_payments_via_line_items.jsonl   one JSON object per event
  recount__B1_fanout_payments_via_line_items.md
  recount__B1_fanout_payments_via_line_items.jsonl
  ...                                                 2 files x 2 systems x 12 cases
```

Start with the `.md` files. Use the `.jsonl` if you want to grep or aggregate.

## What a trajectory contains

The header states the cost of the case:

```
# Trajectory — recount — B1_fanout_payments_via_line_items
`3` model calls (`0` replayed from cassette) · `7` tool calls · `3448` tokens · `$0.00078`
```

Then every event in order, numbered. Four kinds:

| kind | meaning |
|---|---|
| `tool` | a real call: SQL executed, or the profiler run. Shows the request and the actual response, including errors |
| `model` | a model call. Shows **every message sent**, verbatim, and the reply. Notes whether it was a live call or replayed from a cassette |
| `gate` | a verification decision, with the reason and the numbers behind it |
| `note` | something that shaped the next step — a retry, a raised token ceiling, a disabled stage |

## Following one Recount case

Read `recount__B1_fanout_payments_via_line_items.md` in order:

1. **`tool · run_sql · execute_under_review`** — the query being checked is
   executed first, so every later stage argues about a real number.
2. **`tool · profiler.profile`** — measured facts. No model involved.
3. **`model · recompute`** — the question is answered from scratch. Note what is
   *absent* from this prompt: the query under review. A reviewer shown the
   original tends to reproduce its mistakes.
4. **`tool · run_sql · recompute`** — the independent query is executed.
5. **`model · plan`** — hypotheses, each with a probe query.
6. **`tool · run_sql · probe_N`** — probes executed. A failure here is followed by
   a `note` and a `model · probe_repair` carrying the real SQLite error.
7. **`model · adjudicate`** — the verdict, decided from what the probes and the
   recomputation returned.
8. **`gate · verification_gate`** — the decision that can overrule the model, in
   either direction, and the two numbers it compared.

The baseline trajectories are deliberately short: one `note` recording that its
context is the schema alone, one model call, one gate event that changes nothing.
That contrast is the point of including them.

## Cases worth reading first

| file | why |
|---|---|
| `recount__B1_...` | the flagship fault: a 2.61x overstatement, caught and quantified |
| `recount__B4_left_join_degraded_to_inner` | 93% of rows silently discarded |
| `recount__C2_clean_units_sold_at_line_grain` | a **correct** query that looks like B1. Watch the recomputation agree with it and the gate withdraw a bug claim |
| `recount__C4_clean_half_open_date_range` | see below — a real failure, kept on purpose |
| `baseline__B2_fanout_units_via_payments` | the baseline declaring a 1.22x overstatement correct |

## A failure left in place

In the run where the profile was withheld from the recomputation step, the
recomputation for `C4` wrote:

```sql
order_ts >= '2026-01-01T00:00:00Z'
```

against timestamps stored as `2026-01-01 02:11:00`. Because `T` sorts after a
space, that dropped 1 January and admitted 1 February: 557 rows where the correct
answer is 551. A correct query was reported as faulty on the strength of it.

The trajectory shows this end to end, and it is the evidence behind splitting the
profile by role — see the Improvement Changelog in the README. It is left in the
repository rather than tidied away, because a trajectory that only shows the
system succeeding is not evidence of anything.

## Replaying instead of reading

Every model response is committed under `cassettes/`. To watch a case run:

```bash
python3 -m recount.cli --case B1 --offline --trace-dir /tmp/traces
python3 -m recount.cli --case C2 --offline --trace-dir /tmp/traces
python3 -m recount.cli --case B1 --offline --baseline
```

No API key, no cost, and the same numbers.
