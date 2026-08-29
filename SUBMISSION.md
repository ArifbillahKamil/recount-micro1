# HackerEarth submission — copy/paste

## Title

```
Recount — verify a text-to-SQL answer by re-deriving it and diffing the numbers
```

## Video URL

Upload the recording (YouTube unlisted, Google Drive with link sharing, or Loom)
and paste the URL. Script: [VIDEO.md](VIDEO.md).

## Source Code

Upload `recount-submission.zip` (3.2 MB). It contains the code, the recorded
evaluation runs, all 224 trajectory files, every model cassette, and the git
history — so the commits cited in the changelog can be checked from the zip alone
with `git show 80020a6:runs/changelog-table.md`.

## Description

Paste everything below.

---

**A wrong SQL query does not fail. It returns.**

Every BI tool now has "ask your data a question". A model writes the SQL, it
executes, a number comes back. Nothing checks it. The faults that matter are
semantic and invisible: a join to a finer grain that multiplies revenue,
`status != 'cancelled'` silently dropping every NULL, a `LEFT JOIN` degraded to
`INNER` by a `WHERE` predicate. No error, no warning, and the figure goes into a
dashboard or a board pack.

On the 12 cases in this repository, a current model shown the schema and asked to
review a query declared a **22% overstatement of units sold to be correct**. You
can watch it happen in one command:
`python3 -m recount.cli --case B2 --offline --baseline`

### What Recount does

It does not reason about the SQL. It executes the query under review, then
**derives an answer to the same business question from scratch — without being
shown the query** — runs that too, and compares the two numbers. Withholding the
original is deliberate: a reviewer shown a faulty query tends to reproduce its
mistakes. Disagreement means the reported figure is not usable, and the gap is the
magnitude. Agreement means two independent derivations concur.

The analyst receives a runnable corrected query, not a warning.

### Results

`gpt-4o-mini`, 12 cases, same model / temperature / seed / output contract for
both systems, scored by the same code.

| metric | baseline | Recount |
|---|---|---|
| **Recall on planted faults** | 88% (7/8) | **100% (8/8)** |
| F1 | 93% | 94% |
| Precision | 100% | 89% |
| False alarms on the 4 correct queries | 0/4 | 1/4 |
| Cost per case | $0.00019 | $0.00037 |

**Recall is the claim I defend.** The baseline reported one of eight planted
faults as correct; Recount reported none. **The F1 difference is not** — one point
on twelve cases is a single case, inside the noise, and it is reported rather than
leaned on. Recount also raises one false alarm the baseline does not, and costs
twice as much.

### The evaluation is built to be checked, not trusted

- **Ground truth is machine-verified.** Every case ships an independently written
  reference query. `python3 -m recount.cases` executes both and **fails the
  build** if a case labelled BUG returns the same number as its reference.
- **Four of the twelve cases are correct queries**, three shaped to look wrong. A
  reviewer that flags everything scores perfect recall and is useless; without
  these you cannot measure crying wolf.
- **Reproducible with no API key and at no cost.** Every model response is
  committed. Verified from a fresh clone under UTC, Asia/Jakarta and
  America/New_York — identical numbers in all three.

### Improvement changelog: three of my four stages were deleted by their own numbers

| stage | result | decision |
|---|---|---|
| profiler + probes + gate (original design) | F1 75% | **lost to the baseline** |
| + independent recomputation | F1 89% | **kept — the one change that worked** |
| + profile split by role | F1 84% | removed |
| + stored-value-format hints | F1 93%, recall 88% | removed |
| **recomputation + gate** | **F1 94%, recall 100%** | **reported** |

Remove the recomputation and F1 falls to 55% with recall halving to 38%. The
verification gate — which an earlier version of my own README called the
load-bearing idea — returns results **identical** to the reported configuration
across two rewrites. Its measured contribution is zero, and the report says so.

### Hot take

> Don't ask an agent to be careful. Make its claim executable — and give each
> role only the context its own job needs.

Prompting harder does not fix an over-eager reviewer; self-reported confidence is
a fluency artifact, not a signal. Two queries and a diff is not an opinion about
who is right.

The second half cost more to learn. My deterministic profiler measures join
cardinality exactly and cannot hallucinate, and it made the system **worse**. Told
`status: NULL in 80 rows — a predicate on this column must handle NULL
explicitly`, the author wrote `WHERE status IS NOT NULL` where the question
required `WHERE status = 'completed'`. It did not add a redundant filter, it
**replaced the required one**. A hazard named to an author becomes the thing it
optimises for, and it competes with the task.

And the sharpest example came from inside the project. Cloning the repo fresh and
replaying failed, because an agent-authored query carried
`DATE(order_ts, 'localtime', '+7 hours')` — 17 rows on a machine set to
Asia/Jakarta, 19 on UTC. A query that runs, returns a plausible number, and is
wrong for reasons invisible in the SQL: exactly the failure this project exists to
catch, produced by the project. Host-dependent SQL is now rejected outright.

### Run it

```bash
git clone https://github.com/ArifbillahKamil/recount-micro1.git
cd recount-micro1
python run_all.py --dry-run                              # no API key, no cost
python -m recount.evaluate --system both --offline        # reproduces the table above
python -m recount.cli --case B1 --offline                 # verify one query
```

Python 3.9+, **zero third-party dependencies**, 133 tests. Full setup, runtime and
cost in `REPRODUCE.md`; trajectory guide in `TRAJECTORIES.md`.

Repository: https://github.com/ArifbillahKamil/recount-micro1
