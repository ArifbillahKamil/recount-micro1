# Solution video — script and shot list

Target 4:30, hard ceiling 5:00. Screen recording with voice over. No slides
except the two tables; the terminal is the demo.

Record with the repository freshly cloned and `python run_all.py --dry-run`
already done, so `data/warehouse.db` exists. Everything below runs `--offline`,
so nothing depends on the network mid-recording and nothing costs anything.

Two numbers are marked `[N]`. Fill them from `runs/main-<model>/results.md` and
`runs/changelog-table.md` before recording.

---

## 0:00 – 0:45 · The problem

**On screen:** a terminal, nothing else. Type this and let it run.

```bash
python -m recount.cli --case B1 --offline --baseline
```

While it runs, say:

> Every BI tool now has "ask your data a question". An LLM writes the SQL, the
> query runs, a number comes back. Here's the thing nobody checks: a wrong SQL
> query doesn't fail. It returns.

**On screen:** the baseline's verdict appears. Scroll to the reported figure.

> This query joins orders to order_items and to payments at the same time.
> order_items holds about two rows per order, so every payment gets counted once
> per line item. It reports 14.2 billion. The real figure is 5.4 billion.
> Overstated 2.6 times, no error, no warning. That number goes in a board deck.

## 0:45 – 1:15 · The baseline

> So the obvious thing is to ask a model to review the SQL. That's the baseline:
> the schema, the question, the query, one prompt. It's a reasonable first
> attempt, and on twelve cases it scores 93% F1.

**On screen:** highlight the baseline row of the comparison table.

> It also declared this one correct.

**On screen:**

```bash
python -m recount.cli --case B2 --offline --baseline
```

> Units sold, overstated 22% by a fan-out through payments. Plausible number, no
> error, waved through. That is the failure that matters — not a crash, a
> confident wrong answer.

## 1:15 – 2:45 · One execution, start to finish

**On screen:**

```bash
python -m recount.cli --case B1 --offline
```

Narrate the stages as they scroll past. Then open the trajectory to show the
mechanism:

```bash
python -m recount.cli --case B1 --offline --trace-dir /tmp/t
code /tmp/t/recount__adhoc.md      # or `less`
```

> Recount doesn't reason about the SQL. It measures the warehouse — grain, real
> NULL counts, join cardinality, no model involved. Then it does the thing the
> project is named after: it answers the question from scratch.

**On screen:** scroll to the `model · recompute` event. Pause on it.

> Note what is *missing* from this prompt. It never sees the query under review.
> That's deliberate — a reviewer shown the original reproduces its mistakes.

**On screen:** scroll to the `gate` event.

> Both queries run. The numbers are compared. Disagree, and the reported figure
> is not usable, and the gap is the magnitude. Agree, and two independent
> derivations concur, so a bug claim gets withdrawn.

**On screen:** back to the report output. Point at the corrected query.

> And the analyst gets a runnable fix, not a warning. Every figure in that report
> came from a query you can re-run.

**On screen:** the hard case.

```bash
python -m recount.cli --case C2 --offline
```

> This one is surface-identical to the first — orders joined to order_items, then
> aggregated. But the question asks for units sold, which genuinely lives at line
> item grain, so the query is correct. Four of the twelve cases are correct
> queries, and three of those are shaped to look wrong. Without them you can't
> measure crying wolf, and a reviewer that flags everything scores perfect recall
> while being useless.

## 2:45 – 3:30 · The comparison

**On screen:** `runs/main-<model>/results.md`, headline table.

> Same twelve cases, same model, same temperature, same output contract, scored
> by the same code. The only difference is the measured facts, the recomputation
> and the gate.

Say the honest version:

> Recall goes from 88% to 100% — every planted fault caught, including the one
> the baseline waved through. F1 is [N] against 93%. I'm not going to oversell
> that second number: on twelve cases one case is eight points, so the F1
> difference is inside the noise. The recall difference is the claim I'll defend.

**On screen:**

```bash
python -m recount.evaluate --system both --offline
```

> And this is the part I'd want as a judge. No API key. Every model response is
> committed, so you replay the exact run and get the same table, for nothing.

## 3:30 – 4:30 · The changelog

**On screen:** `runs/changelog-table.md`.

> Four stages, each switched off in turn. That's how you find out what actually
> helped instead of assuming.

> The one that earned its place is the recomputation. Remove it and F1 drops to
> [N]. Everything else I built either did nothing or made things worse.

> The verification gate — the mechanism I described as the load-bearing idea in
> my own README — never fired. The no-gate run was byte-identical to the full
> run. Twice. It could only ever downgrade a bug claim, so it was structurally
> unable to catch the case that matters most: a real fault waved through.

> And the experiment I removed: the probe loop. Agent writes hypotheses, runs
> diagnostic queries. It contributed nothing once recomputation existed —
> identical on every metric at half the cost. Deleted.

## 4:30 – 5:00 · The hot take

**On screen:** the trajectory for `C4`, on the `'2026-01-01T00:00:00Z'` line.

> Last thing, because it changed how I think. My deterministic profiler measures
> fan-out exactly and can't hallucinate. It made the system worse.
>
> Not because the facts were wrong. Because I gave them to the wrong role. Tell a
> model "order_items fans out 2.16x" while it's *judging* a query and it helps.
> Tell it the same thing while it's *writing* one and it turns defensive, adds
> DISTINCTs it doesn't need, and gets the answer wrong. Withhold the profile and
> it breaks differently — here it wrote an ISO timestamp against a column stored
> with a space, dropped a day, and reported a correct query as broken.
>
> So: don't ask an agent to be careful. Make its claim executable, and give each
> role only the context its job needs. Confidence is not a signal. A number you
> can diff is.

---

## Recording notes

- Terminal at 16–18pt. Judges watch this in a small window.
- Pre-run every command once so nothing is cold.
- Don't read the tables aloud line by line. Point, state the one number that
  matters, move on.
- Do not skip the honest framing at 3:00. A reviewer who spots an oversold
  one-case delta stops trusting the rest of the submission.
- `--offline` everywhere: no network, no spend, no surprises mid-take.
