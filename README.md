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

The person holding the risk is whoever's name is on the number. An analyst
publishes a revenue figure to a dashboard, a deck, or a board pack. If it is
wrong, it is their credibility, and the decision taken on it was taken wrongly.

**Why this problem is real, stated without embellishment.** I am not an analytics
engineer, and this report makes no claim about my own experience of the
bottleneck. The case rests on something checkable instead: on the twelve cases in
this repository, a current model shown the schema and asked to review a query
declared a 22% overstatement of units sold to be correct — case `B2`, and you can
watch it happen with `python3 -m recount.cli --case B2 --offline --baseline`. The
query runs, returns a plausible figure, and raises nothing. That is the failure
this project addresses, and it is demonstrated rather than asserted.

The warehouse is synthetic and the faults in it are planted, which is a real
limit on how far these results generalise. It is also what makes them
reproducible and the ground truth checkable, and the fault types are the ones any
analytics engineer will recognise: grain, NULL semantics, join degradation,
date boundaries, mixed units.

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

> Everything below is generated from the committed `runs/` by
> [`scripts/render_docs.py`](scripts/render_docs.py) — no number here is typed by
> hand, and `python3 scripts/render_docs.py --check` fails if the README drifts
> from the files.
>
> Replay the same run yourself, with no API key and at no cost:
> `python3 -m recount.evaluate --system both --offline`

<!-- RESULTS:BEGIN -->
Recorded with `gpt-4o-mini` on the 12 bundled cases. Both systems received the same model, temperature, seed, output contract and verdict vocabulary, and were scored by the same code.

| metric | baseline | Recount | change |
|---|---|---|---|
| **Recall on planted faults** | 88% (7/8) | **100%** (8/8) | +12 pt |
| F1 | 93% | 94% | +1 pt |
| Precision | 100% | 89% | -11 pt |
| False alarms on the 4 correct queries (lower is better) | 0/4 | 1/4 | +25 pt |
| Repair accuracy | 6/8 | 6/8 | +0 pt |
| Bug type named correctly | 43% | 25% | -18 pt |
| Cost per case | $0.00019 | $0.00037 | x2.0 |
| Wall clock per case | 1.8s | 2.9s | - |
| Model calls / tool calls | 12 / 0 | 24 / 24 | - |

### Reading this honestly

**Recall is the claim worth defending.** The baseline reported 1 of 8 planted faults as correct. Recount reported none as correct. On the stated problem -- a wrong number reaching a report without anyone noticing -- that is the difference that matters.

**The F1 difference is not.** 93% against 94% is a gap of 1 point on 12 cases, where a single case moves F1 by roughly 8 points and the false alarm rate by 25. It is inside the noise of this sample and is reported rather than leaned on. Twelve cases can show that a mechanism works; they cannot rank two systems that are close.

**Cost is a real trade.** Recount costs x2.0 the baseline and takes about x1.6 the wall clock. At $0.00037 per verified metric that is worth paying, but it is a cost, not a rounding error to hide.

Full per-case tables, including every explanation, are in [`runs/main-gpt-4o-mini/results.md`](runs/main-gpt-4o-mini/results.md). Trajectories for all 24 runs are in [`runs/main-gpt-4o-mini/traces/`](runs/main-gpt-4o-mini/traces/) -- see [TRAJECTORIES.md](TRAJECTORIES.md).
<!-- RESULTS:END -->

## Improvement Changelog

> Each row is a real run, reproducible with the command shown. The ablations
> replay the *same recorded model output* with one stage disabled, which is what
> isolates that stage's contribution rather than asserting it.

<!-- CHANGELOG:BEGIN -->
Each row is a real run. The evidence column is generated from `runs/*/results.json` by [`scripts/render_docs.py`](scripts/render_docs.py), so these numbers cannot drift from the files they came from. Rows for superseded iterations cite the commit that recorded them; recover those with `git show <commit>:runs/<label>/results.json`.

| stage | what was tried and why | evidence | decision / learning |
|---|---|---|---|
| **Baseline** | One prompt: schema, question, SQL. The reasonable first attempt, and a strong one. | F1 93%, recall 88%, 0/4 false alarms, 6/8 repairs, $0.00019/case | Starting point. Note it already scores well -- a 2026 model is good at this task. |
| **Iteration 1**<br>profiler + probes + gate | The original design. Measure the warehouse, let the agent write and run diagnostic probes, then require a bug claim to ship a correction whose effect is checked. | F1 75%, recall 75%, 2/4 false alarms, 6/8 repairs, $0.00063/case (`80020a6`, `runs/ablation-no-recompute-…`) | **Lost to the baseline by 18 points.** Kept the components, questioned the architecture. |
| **Iteration 2**<br>independent recomputation | The gate could only ever downgrade a bug claim, so it was structurally unable to catch a real fault waved through -- and B1 and B4 were. Added a stage that answers the question from scratch, without seeing the query under review, then compares the two numbers. | F1 89%, recall 100%, 2/4 false alarms, 8/8 repairs, $0.00076/case (`80020a6`, `runs/main-…`) | **Kept.** Recall 75% -> 100%. This is the one change that worked. |
| **Iteration 3**<br>profile split by role | Ablations showed the profiler was hurting. The hypothesis was that reviewers need join cardinality while authors need types and formats, so the digest was split. | F1 84%, recall 100%, 3/4 false alarms, 5/8 repairs, $0.00077/case (`2666905`, `runs/main-…`) | **Removed.** It got worse. The trace showed the author writing `WHERE status IS NOT NULL` where the question required `WHERE status = 'completed'` -- the NULL warning displaced the required filter instead of adding to it. |
| **Iteration 4**<br>stored value formats, no hazard framing | If naming a hazard makes an author defend against it, give it no hazards — only how values are stored. This was aimed at the one remaining false alarm, where the author compared against `'2026-01-01T00:00:00Z'` on values stored `'2026-01-01 02:11:00'`. | F1 93%, recall 88%, 0/4 false alarms, 7/8 repairs, $0.00038/case | **Removed.** It did fix that false alarm, and cost a detection doing it: recall fell 100% -> 88%, leaving the system identical to the baseline on every metric. A fix that trades a caught fault for a quieter report is not a fix. |
| **Final**<br>recomputation + gate | Everything that could not be shown to help was deleted: the warehouse profiler, the probe loop, the format hints. What remains is the query under review, an independent derivation of the same question, and a comparison of the two numbers. | F1 94%, recall 100%, 1/4 false alarms, 6/8 repairs, $0.00037/case | **Reported configuration.** Three of the four stages I designed were removed by their own measurements. |

### What each component is worth

Measured against the reported configuration, on the same cases and the same model.

The reported configuration is `--no-profile --no-probes --no-formats`. Reproduce any row offline with `python3 -m recount.evaluate --system recount --offline` plus the flags shown.

| what it changes | flags | result |
|---|---|---|
| Remove the recomputation — the one stage that earned its place | `--no-profile --no-probes --no-formats --no-recompute` | F1 55%, recall 38%, 0/4 false alarms, 3/8 repairs, $0.00021/case |
| Accept the model verdict as-is — what the gate is worth once recomputation exists | `--no-profile --no-probes --no-formats --no-gate` | F1 94%, recall 100%, 1/4 false alarms, 6/8 repairs, $0.00037/case |
| Restore the stored-value-format hints — why they were removed | `--no-profile --no-probes` | F1 93%, recall 88%, 0/4 false alarms, 7/8 repairs, $0.00038/case |
| Restore the warehouse profiler — why it was removed | `--no-probes --no-formats` | F1 84%, recall 100%, 3/4 false alarms, 5/8 repairs, $0.00034/case |
| Restore the probe loop — why it was removed | `--no-profile --no-formats` | F1 94%, recall 100%, 1/4 false alarms, 4/8 repairs, $0.00081/case |

### On the gate, which has no measured contribution

`--no-gate` returns results identical to the reported configuration, on every metric. The gate did not change a single verdict across the twelve cases, and this is the second rewrite of it. Reporting otherwise would be dishonest, so: **its measured contribution here is zero.**

The reason is not that it is broken but that it became redundant. The adjudicator is shown the recomputation, and it follows the evidence — so by the time the gate runs, the verdict already agrees with what the gate would have enforced.

It is kept for one reason: it turns "the model followed the evidence" from an observation into a guarantee. [`tests/test_pipeline.py`](tests/test_pipeline.py) drives it with constructed model output and shows it overruling a verdict in both directions — withdrawing a bug claim that a recomputation contradicts, and escalating a CLEAN verdict that one disagrees with. On this eval set it never had to. On a set where the model ignores the evidence once, it would. That is a defensible reason to keep a component, and it is not the same as a measured improvement.
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

## Repository map

| path | what it is |
|---|---|
| [REPRODUCE.md](REPRODUCE.md) | clean-machine setup, exact commands, runtime, cost |
| [TRAJECTORIES.md](TRAJECTORIES.md) | how to read the agent trajectories |
| [VIDEO.md](VIDEO.md) | script for the solution video |
| `runs/` | results and one trajectory per case per system, for every run reported here |
| `cassettes/` | every recorded model response, so the run replays offline for free |
| `LICENSE` | MIT |

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

### The failure mode: I twice shipped a mechanism that never fired

The verification gate was described, in an earlier version of this README, as
the load-bearing idea. The ablation says otherwise. `--no-gate` came back
**byte-identical** to the full run — same F1, same false alarms, same repairs,
zero escalations — not once but across two rewrites of it.

It was not broken. It was structurally incapable. It could only ever *downgrade*
a bug claim, so it had no way to contradict a CLEAN verdict, which is precisely
the case that costs money: B1's 2.61x overstatement and B4's 93% row loss were
both waved through while the gate watched. Asymmetric verification can only find
the error you already suspect.

The probe loop went the same way. Agent writes hypotheses, runs diagnostic
queries, feeds results back — it reads like good agent design, and once
recomputation existed it contributed *nothing*: identical on every metric at
under half the cost. Deleted.

Three of the four components I built were dead weight or worse. The one that
worked was the dullest: run the query, run an independent derivation, compare the
two numbers. It was in the project's name from day one.

### The hot take

> Don't ask an agent to be careful. Make its claim executable — and give each
> role only the context its own job needs.

Two halves, both learned the hard way.

**Make the claim executable.** Prompting harder does not fix an over-eager
reviewer. "Be conservative", "only flag high-confidence issues" — each produces a
more eloquent version of the same wrong answer, because a model cannot
distinguish its correct reasoning from its incorrect reasoning. Self-reported
confidence is not a signal, it is a fluency artifact. What worked was changing
what counts as a claim: not "explain why this is wrong" but "produce an artifact
whose effect can be measured". Two queries and a diff is not an opinion about
who is right.

**Give each role only what its job needs.** This one surprised me. The
deterministic profiler measures join cardinality exactly and cannot hallucinate,
and it made the system *worse* — removing it took F1 from 84% to 94%.

The facts were correct. They were too loud. Told
`status: NULL in 80 rows -- a predicate on this column must handle NULL
explicitly`, the author wrote:

```sql
WHERE o.status IS NOT NULL          -- what the warning asked for
```

where the question required:

```sql
WHERE o.status = 'completed'        -- what the analyst asked for
```

It did not add a redundant filter. It **replaced the required one**. Given no
profile at all, the same model wrote the correct filter every time.

A hazard named to an author becomes the thing it optimises for, and it competes
with the task. Withholding the facts entirely fails differently — the author then
wrote `'2026-01-01T00:00:00Z'` against values stored `'2026-01-01 02:11:00'`, and
because `T` sorts after a space that silently dropped a day. So the fix was not
*less* context or *more*, but context with no hazard framing at all: how values
are stored, stated as fact, with nothing to defend against.

**What I would do differently next time.** Write the ablation harness before the
second component, not after the fourth. Every wrong turn here was visible in one
run of `--no-X`, and I built three more stages before looking. And treat
"this mechanism is the core of my design" as a hypothesis with a switch attached,
because the two times I was most confident are the two times I was wrong.
