# Solution video — read this and record

You do not need to know anything about video. One terminal window, a screen
recorder, and `demo.py` doing the work. Target 4:40, hard ceiling 5:00.

Everything runs offline against committed cassettes: no network, no spending, no
chance of a failed command mid-take.

---

## Before you record

**1. Warm it up.** Run once so nothing is cold and you know every beat works:

```powershell
python demo.py --check
```

Ends with `All beats ran. Safe to record.` If it does not, stop and say so.

**2. Make the terminal readable.** Judges watch in a small window.

- Font size **18pt or larger**
- Maximise the window, close other tabs
- Light-on-dark is fine; just be consistent

**3. Pick a recorder.**

| tool | notes |
|---|---|
| **OBS Studio** | free, records screen + mic, works everywhere |
| **Windows Game Bar** | already installed — `Win + G`, then record. Simplest option |
| ScreenPal / Loom | browser-based, records and hosts in one step |

**4. Choose how you narrate.** Two honest options — pick whichever you will
actually finish.

- **Path A — speak.** Read the lines below. Short sentences, written to be said
  out loud, not read.
- **Path B — no voice.** Record silently and put a text card between beats. The
  card text is given for each beat. This is a legitimate format and it removes
  all the speaking pressure. Slightly weaker than narration, far better than no
  video.

---

## Recording it

**Get the lines.** The script lives in `demo.py`, so it cannot drift from the
beats:

```powershell
python demo.py --script     # every line, all nine beats, ~4:32
python demo.py --cue 3      # one beat, while you rehearse it
```

Put that on a phone or a second screen, off camera. Then run this and leave it
open:

```powershell
python demo.py
```

It prints a numbered banner, runs one command, then waits for **Enter**. So the
loop is: read the line → press Enter → read the next line. If you stumble, pause,
breathe, and say the sentence again — you will cut the bad take out, or just leave
it. Judges are watching for the work, not for polish.

---

### Beat 1 — The problem · ~50s

**Say:**

> Every BI tool now has "ask your data a question". A model writes the SQL, the
> query runs, a number comes back.
>
> Here is the thing nobody checks. A wrong SQL query does not fail. It returns.
>
> This is the obvious defence: show a model the schema and the query, and ask if
> it is right.

*(press Enter — the baseline verdict appears)*

> It says the number holds. Three thousand six hundred and forty-eight units.
>
> The real answer is two thousand nine hundred and ninety-three. This query joins
> through the payments table, and installment orders have several payment rows, so
> every line item gets counted more than once. Overstated twenty-two percent.
>
> No error. No warning. And read that explanation — it is fluent, specific, and
> completely wrong. That is the failure that matters.

**Card (Path B):** `A wrong SQL query does not fail. It returns.` then
`Reviewer: "the number holds" — 3,648 units. Truth: 2,993. Overstated 22%.`

---

### Beat 2 — The same query, verified · ~45s

**Say:**

> Same query, through Recount.

*(Enter)*

> It reports the overstatement, the true figure, and the size of the gap. Then it
> hands over a corrected query you can run.
>
> Not a warning. A fix. And every number in that report came from SQL that was
> actually executed.

**Card:** `Recount: overstated 1.22x, +655 units — with a runnable fix.`

---

### Beat 3 — How it works · ~55s

**Say:**

> Recount does not read the SQL and form an opinion. It answers the question
> again, from scratch.
>
> This is the entire prompt that step receives.

*(Enter)*

> Look at what is missing. The query being checked is not in there. That is
> deliberate — a reviewer shown a faulty query tends to repeat its mistake.
>
> So it derives its own answer, that query gets executed too, and the two numbers
> are compared. Different numbers mean the reported figure cannot be used, and the
> gap is the magnitude. Same numbers mean two independent derivations agree.
>
> The decision is a diff between two executed queries. Not a judgement about
> which explanation sounds better.

**Card:** `The recomputation never sees the query it is checking.` then
`Two derivations. Both executed. Compare the numbers.`

---

### Beat 4 — The hard case · ~40s

**Say:**

> Now the case that makes this hard.

*(Enter — two queries appear side by side)*

> Both join orders to order items and then aggregate. Same shape. One is broken,
> one is perfectly correct — because this one asks for units sold, and units
> really do live at line-item grain.
>
> You cannot tell them apart from the SQL. Only the question separates them.

*(Enter — C2 runs)*

> Recount clears it. Four of my twelve cases are correct queries, and three are
> shaped to look wrong. Without those you cannot measure crying wolf, and a
> reviewer that flags everything scores perfect recall while being useless.

**Card:** `Same SQL shape. One broken, one correct.` then
`4 of 12 cases are correct queries. 3 are shaped to look wrong.`

---

### Beat 5 — Where it fails · ~25s

**Say:**

> And here is where Recount is wrong.

*(Enter)*

> This query is correct and it flags it anyway. One false alarm in four correct
> queries. The baseline has none. That is a real cost and I am not hiding it.

**Card:** `Recount's own false alarm: 1 of 4 correct queries. The baseline: 0.`

---

### Beat 6 — The comparison · ~45s

**Say:**

> Twelve cases. Same model, same temperature, same output contract, scored by the
> same code. The only difference is the recomputation.

*(Enter)*

> Recall goes from eighty-eight percent to one hundred. Every planted fault
> caught, including the one the reviewer waved through.
>
> F1 is ninety-four against ninety-three. I am not going to oversell that. One
> point on twelve cases is a single case — that is inside the noise. Recall is the
> claim I will defend. And it costs twice as much, and raises that false alarm.

**Card:** `Recall 88% → 100%. F1 93% → 94% — one case, inside the noise.`
then `Cost: 2x. False alarms: +1.`

---

### Beat 7 — Reproducible · ~25s

**Say:**

> This part I would want as a judge. No API key in this shell. No network call.

*(Enter)*

> Every model response is committed, so you replay the exact run and get the same
> table, for nothing. Verified from a clean clone in three different timezones.

**Card:** `No API key. No network. Same numbers.`

---

### Beat 8 — What each component was worth · ~45s

**Say:**

> Last thing, and it is the part I would want to be asked about.

*(Enter)*

> Four stages. Each one switched off in turn. Three of them I deleted, because
> their own numbers said to.
>
> The verification gate — which an earlier version of my own README called the
> load-bearing idea — returns results identical to the final configuration. Twice,
> across two rewrites. Its measured contribution is zero.
>
> The probe loop: identical results at more than double the cost. Deleted.
>
> And my deterministic profiler, the component I was proudest of. It made things
> worse. Not because the facts were wrong — because I gave them to the wrong role.

**Card:** `Three of four stages deleted by their own measurements.` then
`Remove the recomputation: F1 94% → 55%.`

---

### Closing — the hot take · ~30s

Nothing to run. Just say it.

> Told "status must handle NULL explicitly", the author wrote
> `WHERE status IS NOT NULL` where the question required
> `WHERE status = 'completed'`. It did not add a filter. It replaced the required
> one. A hazard you name to an agent becomes the thing it optimises for, and it
> competes with the task.
>
> So: don't ask an agent to be careful. Make its claim executable, and give each
> role only the context its own job needs. Confidence is not a signal. A number
> you can diff is.

**Card:** `Don't ask an agent to be careful. Make its claim executable.`

---

## After recording

1. **Upload and get a URL.** YouTube unlisted is safest. Google Drive works if you
   set sharing to **Anyone with the link** — otherwise judges get a 403.
2. **Open the URL in an incognito window.** If it asks for a login, fix it. A
   video nobody can open is a deliverable you did not submit.
3. Paste the URL into the HackerEarth form. Title, description and the source
   zip are in [SUBMISSION.md](SUBMISSION.md).

## If it runs long

Cut in this order — beat 5, then beat 7, then trim beat 4. Never cut the honest
framing in beat 6; a reviewer who notices an oversold number stops trusting
everything else.
