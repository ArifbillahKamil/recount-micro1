# Reproduction guide

Written for someone starting from a clean machine with nothing installed.

## Requirements

- **Python 3.9 or newer.** Nothing else. No pip install, no virtualenv, no
  database server. The warehouse is SQLite via the standard library and the API
  client is `urllib`.
- **An OpenAI API key**, only if you want to re-record model responses. To
  reproduce the published numbers you do not need one — see *Offline* below.

Verify your interpreter:

```bash
python3 --version        # 3.9+
python3 -c "import sqlite3; print(sqlite3.sqlite_version)"
```

## 1. Build the warehouse

```bash
cd recount
python3 -m recount.warehouse --db data/warehouse.db
```

Expected output:

```json
{
  "customers": 400,
  "products": 60,
  "orders": 1500,
  "order_items": 3244,
  "payments": 1683,
  "refunds": 103,
  "marketing_spend": 360,
  "sessions": 6000,
  "orders_with_null_status": 80,
  "orders_with_multiple_payments": 252,
  "orders_with_multiple_items": 1005
}
```

The build prints a content digest and checks it for you:

```
content digest: 7e5f85250ade5358
matches the published digest -- your data is identical
```

You can re-check an existing warehouse at any time:

```bash
python3 -m recount.warehouse --db data/warehouse.db --digest-only
# 7e5f85250ade5358
```

If that digest differs, stop — every downstream number depends on it.

**Why a content digest and not a hash of the `.db` file.** Hashing the file was
the first thing this guide did, and it was wrong. SQLite's on-disk layout depends
on the library version, so two machines that generate byte-for-byte identical
*data* still produce different *files*. The file hash therefore failed for anyone
whose SQLite differed from the author's, while reporting that their data was
different — which was untrue and alarming. The digest reads every row of every
table in a determined order and hashes the values, so it depends on the data
alone.

## 2. Confirm the ground truth is real

The evaluation labels are not asserted by hand. Each case ships a `sql` and an
independently written `reference_sql`; this executes both and fails if a case
labelled BUG returns the same number as its reference, or a case labelled CLEAN
does not.

```bash
python3 -m recount.cases --db data/warehouse.db
```

Expected: `12 cases validated: 8 BUG / 4 CLEAN`, then a per-case listing of the
reported value against the true value, ending in
`OK - every label is backed by executed data.`

## 3. Inspect what the agent is given

Recount's context is measured, not inferred. This is the deterministic profiler,
which uses no model at all:

```bash
python3 -m recount.profiler --db data/warehouse.db
```

Runs in well under a second. Note these measured facts, which several cases turn
on:

```
! order_items.order_id -> orders.order_id: FANS OUT x2.16 avg, up to x4
! payments.order_id    -> orders.order_id: FANS OUT x1.24 avg, up to x3
  refunds.order_id     -> orders.order_id: one row per parent (safe to join)
  orders.status: TEXT, NULL in 80 rows (5.3%)
```

## 4. Run the tests

No API key and no network needed. The model is scripted, so every gate path is
checked deterministically.

```bash
python3 -m tests.test_pipeline    # 25 checks — gate paths, probe repair, safety
python3 -m tests.test_harness     # 31 checks — replay, scoring math, artifacts
```

Both should end in `N passed, 0 failed`.

## 5. Offline: reproduce the published result at zero cost

Every model response from the recorded run is committed under `cassettes/`. This
replays them, needs no API key, and makes no network call:

```bash
python3 -m recount.evaluate --system both --offline
```

Writes `results.md`, `results.json`, and one trajectory per case per system
under `traces/`, in a directory named after the run — for example
`runs/both-gpt-4o-mini-replay/`. The headline table in `results.md` is the
comparison reported in the README.

> **Windows note.** Every command in this guide uses concrete values rather than
> `<placeholders>`, because `<` is a redirection operator in PowerShell and a
> pasted placeholder fails to parse before Python ever runs. Substitute your own
> values directly.

Runtime: a few seconds. Cost: $0.00.

## 6. Verify a single query, the way an analyst would

```bash
# a query with a planted fault
python3 -m recount.cli --case B1 --offline

# the adversarial correct query that looks wrong
python3 -m recount.cli --case C2 --offline

# what the simple baseline says about the same query
python3 -m recount.cli --case B1 --offline --baseline
```

Your own query:

```bash
python3 -m recount.cli \
  --db data/warehouse.db \
  --question "How much did we capture from completed orders?" \
  --sql-file my_query.sql
```

## 7. Re-record against a live model

Only needed to reproduce from scratch rather than from cassettes.

### Supplying the API key

Two options. Both are read by every entry point.

**A. A `.env` file in the project root** — the same directory as `run_all.py`:

```bash
cp .env.example .env            # Windows PowerShell: Copy-Item .env.example .env
```

Then edit it:

```
OPENAI_API_KEY=sk-your-key-here
```

**B. An environment variable:**

```bash
export OPENAI_API_KEY=sk-...              # macOS / Linux
$env:OPENAI_API_KEY="sk-..."              # Windows PowerShell
```

An exported variable always wins over `.env`, so a one-off
`OPENAI_API_KEY=... python3 -m recount.evaluate ...` behaves as expected.

`.env` is listed in `.gitignore` and must never be committed; a test asserts
this. When a `.env` is loaded, only the *names* of the variables it set are
printed, never the values.

```bash
# see which models your key can reach
python3 -m recount.llm --list-models

python3 -m recount.evaluate \
  --system both \
  --model gpt-4o-mini \
  --record \
  --label live-run
```

**Pin the price you were actually billed.** The built-in table is a convenience
and is marked unverified; a model missing from it reports cost as `unpriced`
rather than guessing:

```bash
python3 -m recount.evaluate --system both --model gpt-5.4-mini \
  --price-in 0.75 --price-out 4.50 --label live-run
```

### Measured size and cost of one full run

Prompt sizes are measured from the recorded requests; token counts use 4
characters per token as a proxy.

| | input | output |
|---|---|---|
| baseline, per case | ~890 tok | ~250 tok |
| Recount plan, per case | ~774 tok | ~500 tok |
| Recount adjudicate, per case | ~1,039 tok | ~300 tok |
| **full run, 12 cases, both systems** | **~32,500 tok** | **~12,600 tok** |

| model | cost per full run |
|---|---|
| gpt-4o-mini | ~$0.012 |
| gpt-5.4-mini | ~$0.081 |
| gpt-5.4 | ~$0.270 |

Wall clock for a live run is dominated by API latency: roughly 2–5 minutes for
all 12 cases across both systems, sequentially.

Because cassettes are keyed by the full request, re-running after editing one
prompt only pays for the calls that actually changed.

## 8. Ablations — reproducing the changelog

Each row of the Improvement Changelog is a real run. These replay the same
recorded model output with one stage switched off, which is what isolates that
stage's contribution:

```bash
# no verification gate: the model's verdict is accepted as-is
python3 -m recount.evaluate --system recount --offline --no-gate --label no-gate

# no probing: adjudicate from measured facts alone
python3 -m recount.evaluate --system recount --offline --no-probes --label no-probes

# put any set of runs side by side
python3 -m recount.evaluate --compare \
  runs/both-gpt-4o-mini-replay/results.json \
  runs/no-gate/results.json \
  runs/no-probes/results.json
```

## What the numbers mean

- **F1 on bug detection** is the headline. It is not recall, because a reviewer
  that flags everything has perfect recall and no value.
- **False alarms** counts BUG verdicts on the 4 queries that are actually
  correct. Three of those are deliberately shaped to look wrong.
- **Repair accuracy** executes the proposed correction and checks it returns the
  reference number. Detection is an opinion; a correction is a work product.
- **Net analyst minutes** is an explicitly modelled estimate, not a measurement.
  The coefficients are printed in every `results.md` and are adjustable with
  `--minutes-saved`, `--minutes-false-alarm`, `--minutes-escalation`.

## Safety

The agent writes and executes its own probe SQL. Every statement passes
`recount/sqlio.py:assert_read_only` and runs on a connection opened
`mode=ro` with `PRAGMA query_only`. Non-SELECT statements, multiple statements,
and keywords hidden behind SQL comments are all rejected.
`tests/test_pipeline.py` asserts the warehouse is intact after the agent is fed
a `DROP TABLE` probe.
