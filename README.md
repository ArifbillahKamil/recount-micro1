# Recount

**Your AI analyst just returned a number. Who checks it?**

Recount verifies that a SQL answer actually answers the question that was asked.
It profiles the warehouse, executes differential probes against it, and refuses
to report a bug it cannot demonstrate with a working correction.

```
$ python -m recount.cli --case B1

# `captured_cents` is overstated 2.61x — do not ship it

You asked: How much money did we actually capture from completed orders?

    captured_cents: reported 14,274,325,000 vs corrected 5,468,920,000
    (2.61x, off by +8,805,405,000)

## Why it is wrong
orders is joined to order_items and payments at once. order_items carries
2.16 rows per order, so each payment row is summed once per line item.
```

Built for the micro1 Agentic Workflows Hackathon. Python 3.9+, **zero
third-party dependencies**, and reproducible with no API key.

---

## Who has this problem

Analytics engineers and data analysts at any company that has shipped a
"ask your data a question" feature — which by now is most BI tools, and every
team that has wired an LLM to its warehouse.

The person holding the risk is whoever's name is on the number. A analyst
publishes a revenue figure to a dashboard, a deck, or a board pack. If it is
wrong, it is their credibility, and the decision made on it was made wrong.

## The bottleneck

**A wrong SQL query does not fail. It returns.**

Text-to-SQL agents produce syntactically valid queries that execute cleanly and
return plausible numbers. Nothing errors. Nothing alerts. There is no red mark
anywhere, because from the database's point of view nothing went wrong.

The faults that matter are semantic, and they are invisible at a glance:

| fault | what it looks like | what it does |
|---|---|---|
| fan-out join | joins a coarse measure to a finer-grained table | multiplies revenue by the item count |
| NULL-swallowing predicate | `WHERE status != 'cancelled'` | silently drops every row where status is NULL |
| LEFT JOIN degraded to INNER | a predicate on the right-hand table in `WHERE` | discards the rows the LEFT JOIN existed to keep |
| date range truncation | `BETWEEN '2026-01-01' AND '2026-01-31'` | loses the entire last day |
| timezone day boundary | `date(order_ts)` on UTC data, local reporting | attributes orders to the wrong day |
| mixed-unit aggregation | summing IDR and USD amounts together | adds two different units |

Reviewing these by hand means re-deriving the metric a second way — which is
most of the work of writing the query again. So in practice nobody does it,
and the number ships.

### Why solving it is valuable

The cost is not the debugging time, it is the decision. On the warehouse in
this repository, one plausible-looking revenue query overstates captured
revenue by **2.61x**, and one LEFT JOIN fault silently discards **93% of the
rows** it was written to preserve. Neither raises an error. Both would land in
a report.

Verification is also the last unautomated step. Generation is solved; the
industry shipped it. Checking is not.

---

## Why this is not "ask a model to review my SQL"

Paste a query into a chat assistant and you get a hedged list of things that
*might* be wrong. It cannot know whether `order_items` holds one row per order
or four, because that is a fact about your data, not about your SQL. So it
guesses, confidently, and it is wrong often enough to be untrustworthy — while
being equally confident in both cases.

Recount does not reason about SQL text. It measures the warehouse and executes
queries against it. Every number it reports came from a query you can re-run.

---

## How it works

```
                    ┌─────────────────────────────────────────┐
   question  ─────▶ │  1. execute the query under review      │  no model
   + SQL            └─────────────────────────────────────────┘
                                      │
                    ┌─────────────────────────────────────────┐
                    │  2. profile the warehouse               │  no model
                    │     grain · real NULL counts ·          │
                    │     join cardinality                    │
                    └─────────────────────────────────────────┘
                                      │
                    ┌─────────────────────────────────────────┐
                    │  3. plan falsifiable hypotheses,        │  model
                    │     each with a probe query             │
                    └─────────────────────────────────────────┘
                                      │
                    ┌─────────────────────────────────────────┐
                    │  4. execute the probes read-only        │  no model
                    │     failures fed back once for repair   │
                    └─────────────────────────────────────────┘
                                      │
                    ┌─────────────────────────────────────────┐
                    │  5. adjudicate from probe results       │  model
                    │     CLEAN / BUG / ESCALATE + a fix      │
                    └─────────────────────────────────────────┘
                                      │
                    ┌─────────────────────────────────────────┐
                    │  6. VERIFICATION GATE                   │  no model
                    │     execute the fix. diff it.           │
                    └─────────────────────────────────────────┘
                                      │
                              report to the analyst
```

Four of the six stages involve no model at all. That is deliberate: anything
that can be measured is measured, and the model is used only where judgement is
actually required.

### The design decisions that matter

**1. Measured context instead of inferred context** (`recount/profiler.py`)

Before any model call, plain SQL measures what the model would otherwise have to
guess: row counts, real NULL counts per column, primary-key uniqueness, temporal
ranges, and above all **join cardinality** — rows per parent key, which is
exactly what determines whether a join fans out.

The agent is told, as fact:

```
! order_items.order_id -> orders.order_id: FANS OUT x2.16 avg, up to x4
! payments.order_id    -> orders.order_id: FANS OUT x1.24 avg, up to x3
  refunds.order_id     -> orders.order_id: one row per parent (safe to join)
  orders.status: TEXT, NULL in 80 rows (5.3%)
```

Deterministic, runs in ~0.15s, and cannot hallucinate.

**2. Probes the agent writes and executes** (`recount/agent.py`, `recount/sqlio.py`)

The agent designs a query that would settle each suspicion, then runs it. When a
probe fails, the real SQLite error is fed back once and the probe is rewritten —
so tool output genuinely shapes the next step.

**3. The verification gate — the load-bearing idea** (`recount/agent.py:_gate`)

The dominant failure of a model-based SQL reviewer is not missing bugs. It is
**inventing** them. Asked "is this wrong?", it finds something. Confidence scores
do not help, because it is equally confident when right and when wrong.

So the gate refuses to accept an argument and demands a consequence instead. A
BUG verdict must ship a corrected query, and that correction is executed and
diffed against the original:

| outcome | conclusion |
|---|---|
| correction returns an **identical** result | the "fix" changes nothing, so the original was right → **downgrade to CLEAN** |
| correction returns a **different** result | the fault is real, and the diff is its magnitude → **confirm BUG** |
| correction is **missing or broken** | nothing was demonstrated → **ESCALATE to a human** |

The gate never sees the reference query. It compares the query under review
against *the model's own* proposed correction, so no ground truth leaks into the
system under test.

**4. ESCALATE as a first-class verdict** (`recount/verdict.py`)

A reviewer that must answer CLEAN or BUG will guess. Recount can decline. A
malformed model reply also becomes ESCALATE — never a silent CLEAN.

**5. Cassette record/replay** (`recount/llm.py`)

Every model call is hashed and cached to disk. One mechanism, three payoffs:
a reviewer reproduces the published numbers **with no API key and at zero
cost**; editing one prompt only re-pays for the calls that changed; and the
cassettes are themselves the trajectory evidence.

---

## How it is evaluated

The evaluation is the part most worth scrutinising, so it is built to be
checkable rather than trusted.

**12 cases: 8 with a planted fault, 4 that are correct.** The four correct
queries are the point. A reviewer that answers BUG every time scores perfect
recall and is worthless, because an analyst warned about everything stops
reading warnings. Three of the four are deliberately shaped to *look* wrong.

**The hard case, `C2`.** Surface-identical to the flagship fan-out bug `B1` —
`orders` joined to `order_items`, then aggregated — but the requested metric is
units sold, which genuinely lives at line-item grain. So the join is correct.
Distinguishing `C2` from `B1` is impossible from SQL shape alone; it requires
reading the business question. This case is what proves a pattern-matching
reviewer is not enough.

**Ground truth is machine-verified, not asserted.** Every case ships an
independently written `reference_sql`. `python -m recount.cases` executes both
and **fails the build** if a case labelled BUG returns the same number as its
reference, or a CLEAN case does not. You never have to take a label on trust:

```
$ python -m recount.cases --db data/warehouse.db
12 cases validated: 8 BUG / 4 CLEAN
  B1_fanout_payments_via_line_items
      reported : (14274325000,)
      truth    : (5468920000,)  (2.61x)
  ...
OK - every label is backed by executed data.
```

**A fair baseline.** One direct prompt with the schema, the question and the
SQL — the reasonable first thing anyone would try. It gets the **same model,
temperature, seed, output contract and verdict vocabulary**, including
ESCALATE, and is scored by the same code. The only difference is what is under
test: measured facts, executed probes, and the gate.

### Metrics

| metric | why this one |
|---|---|
| **F1 on bug detection** (primary) | balances catching faults against crying wolf |
| **False alarms on the 4 correct queries** | the failure mode that destroys trust |
| **Repair accuracy** | does the correction return the *true* number? Detection is an opinion; a correction is a work product |
| Bug type named correctly | is the diagnosis right, not just the alarm |
| Escalations | measures calibrated abstention |
| Cost + wall clock per case | what it costs to run |
| Net analyst minutes | **modelled estimate, not a measurement** — coefficients printed in every report and adjustable via CLI |

---

## Results

> **This section is generated from a recorded run.** Reproduce it with
> `python run_all.py --model <model>`, then read
> `runs/main-<model>/results.md`. The committed `cassettes/` let you replay the
> same run offline for free with `python -m recount.evaluate --system both
> --offline`.
>
> _Awaiting the live run — the table below is populated from
> `runs/main-<model>/results.md` and is not yet filled in. No numbers are
> claimed here until they come out of the harness._

<!-- RESULTS:BEGIN -->
<!-- Populated from runs/main-<model>/results.md -->
<!-- RESULTS:END -->

## Improvement Changelog

> Each row is a real run, reproducible with the command shown. The ablations
> replay the *same recorded model output* with one stage disabled, which is what
> isolates that stage's contribution rather than asserting it.

<!-- CHANGELOG:BEGIN -->
| stage | what was tried and why | command | evidence | decision |
|---|---|---|---|---|
| Baseline | One direct prompt: schema + question + SQL, no tools, no execution. The reasonable first attempt. | `--system baseline` | _pending live run_ | Establishes the starting point |
| Iteration 1 | Added the deterministic profiler, because the model was being asked to guess grain and NULL counts it could have been told. | `--system recount --no-probes --no-gate` | _pending_ | _pending_ |
| Iteration 2 | Added agent-authored probes executed against the warehouse, so claims rest on measurements. | `--system recount --no-gate` | _pending_ | _pending_ |
| Iteration 3 | Added the verification gate after observing the model manufacture faults on correct queries. | `--system recount` | _pending_ | _pending_ |
| Final | All three combined. | `python run_all.py` | _pending_ | _pending_ |
<!-- CHANGELOG:END -->

---

## Quick start

```bash
git clone https://github.com/ArifbillahKamil/recount-micro1.git
cd recount-micro1

# verify everything, no API key, no cost
python run_all.py --dry-run
```

Expected: content digest `7e5f85250ade5358`, `12 cases validated: 8 BUG /
4 CLEAN`, and `44 passed, 0 failed` / `31 passed, 0 failed`.

Then supply an API key, either way:

```bash
# A) a .env file in the project root
cp .env.example .env            # PowerShell: Copy-Item .env.example .env
#    then put your key on the OPENAI_API_KEY line

# B) an environment variable
export OPENAI_API_KEY=sk-...    # PowerShell: $env:OPENAI_API_KEY="sk-..."
```

An exported variable takes precedence over `.env`. `.env` is gitignored;
`.env.example` is the template. Then:

```bash
python run_all.py --model gpt-4o-mini
```

Full instructions, expected output, runtime and cost: **[REPRODUCE.md](REPRODUCE.md)**.

## Layout

```
recount/
  warehouse.py   seeded synthetic warehouse with planted grain hazards
  cases.py       the 12 evaluation cases and their self-validating ground truth
  profiler.py    deterministic measurement of grain, NULLs and join cardinality
  sqlio.py       read-only execution gate for every query in the project
  llm.py         zero-dependency OpenAI client with cassette record/replay
  verdict.py     the output contract shared by baseline and Recount
  baseline.py    the single-prompt baseline
  agent.py       the Recount pipeline, including the verification gate
  scoring.py     F1, false alarms, repair accuracy, modelled analyst minutes
  evaluate.py    the harness, plus the three ablations
  report.py      the artifact an analyst receives
  cli.py         verify one query
  env.py         reads .env, without ever overriding the shell
tests/           75 checks, scripted model, no API calls
```

## Safety

The agent writes and executes its own SQL, so that channel is constrained
rather than trusted. Every statement passes `assert_read_only` — single
statement, `SELECT`/`WITH` only, no mutating keywords even when hidden behind a
SQL comment — and runs on a connection opened `mode=ro` with
`PRAGMA query_only`. `tests/test_pipeline.py` feeds the agent a `DROP TABLE`
probe and asserts the warehouse is intact afterwards.

Recount advises; it never rewrites anything. Corrections are printed for a human
to apply.

All data is synthetic and generated from a fixed seed. No credentials are in the
repository.

## Provenance

Everything here was written during the hackathon. There is no pre-existing
codebase, and no third-party packages — the imports are `argparse`,
`dataclasses`, `datetime`, `hashlib`, `json`, `os`, `pathlib`, `random`, `re`,
`sqlite3`, `sys`, `time`, `typing`, `urllib`. The code was written with the
assistance of a coding agent, which the hackathon expects; the architecture,
the evaluation design and the verification-gate mechanism are the contribution.

---

## Main failure mode, and the hot take

**The failure mode.** Before the gate existed, the system's problem was not
missing faults — it was manufacturing them. Given a correct query and asked
whether it was wrong, the model found something wrong, phrased it fluently, and
attached high confidence. The three adversarial CLEAN cases exist because that
behaviour is invisible in any evaluation made only of broken queries. Measure
only recall and this system looks excellent while being unusable.

**The hot take.**

> Don't ask an agent to be careful. Make its claim executable.

Prompting harder does not fix an over-eager reviewer. "Be conservative", "only
flag high-confidence issues", "think step by step" — all of it produces a more
eloquent version of the same wrong answer, because the model cannot tell its
correct reasoning from its incorrect reasoning. Self-reported confidence is
not a signal; it is a fluency artifact.

What worked was changing what counts as a claim. Instead of "explain why this is
wrong", the requirement became "produce an artifact whose effect can be
measured" — a corrected query. Then the system stops arbitrating between
explanations and starts running a diff. An over-eager reviewer's correction
returns the same number as the original, and that is not an opinion about
whether it was over-eager. It is a fact.

The general shape: when an agent's output is an argument, you have to trust it.
When its output is executable, you can check it. Wherever there is a choice,
design the agent's deliverable so that being wrong is *observable* — and put
the check outside the model, where the model's confidence cannot reach it.
