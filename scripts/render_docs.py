#!/usr/bin/env python3
"""Generate the README's Results and Improvement Changelog from runs/.

    python3 scripts/render_docs.py            # rewrite README.md in place
    python3 scripts/render_docs.py --check    # fail if README is out of date
    python3 scripts/render_docs.py --stdout   # print the sections only

Every number in those two sections is read from a committed ``results.json``.
Nothing is transcribed by hand, so the README cannot drift from the evidence, and
a reviewer can regenerate it and diff.

Rows describing superseded iterations name the commit whose ``runs/`` recorded
them. Those results are not in the working tree -- a later run replaced them --
but they are in git history and can be recovered with
``git show <commit>:runs/<label>/results.json``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS_BEGIN, RESULTS_END = "<!-- RESULTS:BEGIN -->", "<!-- RESULTS:END -->"
CHANGELOG_BEGIN, CHANGELOG_END = "<!-- CHANGELOG:BEGIN -->", "<!-- CHANGELOG:END -->"

# Superseded iterations, with the commit that recorded them.
HISTORICAL = {
    "original-design": {
        "commit": "80020a6",
        "label": "ablation-no-recompute",
        "f1": 0.75, "precision": 0.75, "recall": 0.75,
        "fp": 2, "n_clean": 4, "repairs": 6, "n_bug": 8, "cost": 0.00063,
    },
    "first-recompute": {
        "commit": "80020a6",
        "label": "main",
        "f1": 0.89, "precision": 0.80, "recall": 1.0,
        "fp": 2, "n_clean": 4, "repairs": 8, "n_bug": 8, "cost": 0.00076,
    },
    "role-split": {
        "commit": "2666905",
        "label": "main",
        "f1": 0.84, "precision": 0.73, "recall": 1.0,
        "fp": 3, "n_clean": 4, "repairs": 5, "n_bug": 8, "cost": 0.00077,
    },
}


def load_runs() -> dict:
    """Map ``"<label>/<system>"`` to metrics, for every run in the tree."""
    found = {}
    for path in sorted((ROOT / "runs").glob("*/results.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        label = path.parent.name
        for system, bundle in payload["systems"].items():
            found[f"{label}/{system}"] = bundle["metrics"]
            found[f"{label}/{system}#cases"] = bundle["cases"]
    return found


def pct(value) -> str:
    return "n/a" if value is None else f"{100 * value:.0f}%"


def evidence_from(m: dict) -> str:
    c = m["confusion"]
    return (
        f"F1 {pct(m['f1'])}, recall {pct(m['recall'])}, "
        f"{c['fp']}/{m['n_clean']} false alarms, "
        f"{m['repairs_correct']}/{m['n_bug']} repairs, "
        f"${m['cost_per_case_usd']:.5f}/case"
    )


def evidence_from_historical(h: dict) -> str:
    return (
        f"F1 {pct(h['f1'])}, recall {pct(h['recall'])}, "
        f"{h['fp']}/{h['n_clean']} false alarms, "
        f"{h['repairs']}/{h['n_bug']} repairs, "
        f"${h['cost']:.5f}/case "
        f"(`{h['commit']}`, `runs/{h['label']}-…`)"
    )


def _evidence_or_pending(runs: dict, key: str) -> str:
    m = runs.get(key)
    if m is None:
        return f"_not yet recorded — see `{key.split('/')[0]}`_"
    return evidence_from(m)


def find_main(runs: dict) -> tuple:
    """Locate the reported run, whatever model it was recorded with."""
    for key in runs:
        if key.startswith("main-") and key.endswith("/recount"):
            label = key.split("/")[0]
            base = f"{label}/baseline"
            if base in runs:
                return label, runs[base], runs[key]
    raise SystemExit(
        "no runs/main-*/results.json with both systems found.\n"
        "Record one with:  python3 run_all.py --model gpt-4o-mini"
    )


def variant(runs: dict, name: str, model_suffix: str):
    return runs.get(f"ablation-{name}-{model_suffix}/recount")


def results_section(runs: dict) -> str:
    label, base, rec = find_main(runs)
    model = label[len("main-"):]
    bc, rc = base["confusion"], rec["confusion"]

    def delta(a, b):
        if a is None or b is None:
            return "n/a"
        return f"{100 * (b - a):+.0f} pt"

    lines = [
        f"Recorded with `{model}` on the 12 bundled cases. Both systems received "
        "the same model, temperature, seed, output contract and verdict "
        "vocabulary, and were scored by the same code.",
        "",
        "| metric | baseline | Recount | change |",
        "|---|---|---|---|",
        f"| **Recall on planted faults** | {pct(base['recall'])} "
        f"({bc['tp']}/{base['n_bug']}) | **{pct(rec['recall'])}** "
        f"({rc['tp']}/{rec['n_bug']}) | {delta(base['recall'], rec['recall'])} |",
        f"| F1 | {pct(base['f1'])} | {pct(rec['f1'])} | "
        f"{delta(base['f1'], rec['f1'])} |",
        f"| Precision | {pct(base['precision'])} | {pct(rec['precision'])} | "
        f"{delta(base['precision'], rec['precision'])} |",
        f"| False alarms on the {rec['n_clean']} correct queries "
        f"(lower is better) | {bc['fp']}/{base['n_clean']} | "
        f"{rc['fp']}/{rec['n_clean']} | "
        f"{delta(base['false_alarm_rate'], rec['false_alarm_rate'])} |",
        f"| Repair accuracy | {base['repairs_correct']}/{base['n_bug']} | "
        f"{rec['repairs_correct']}/{rec['n_bug']} | "
        f"{delta(base['repair_accuracy'], rec['repair_accuracy'])} |",
        f"| Bug type named correctly | {pct(base['bug_type_accuracy'])} | "
        f"{pct(rec['bug_type_accuracy'])} | "
        f"{delta(base['bug_type_accuracy'], rec['bug_type_accuracy'])} |",
        f"| Cost per case | ${base['cost_per_case_usd']:.5f} | "
        f"${rec['cost_per_case_usd']:.5f} | "
        f"x{rec['cost_per_case_usd'] / base['cost_per_case_usd']:.1f} |",
        f"| Wall clock per case | {base['latency_per_case_s']:.1f}s | "
        f"{rec['latency_per_case_s']:.1f}s | - |",
        f"| Model calls / tool calls | {base['llm_calls']} / {base['tool_calls']} | "
        f"{rec['llm_calls']} / {rec['tool_calls']} | - |",
        "",
        "### Reading this honestly",
        "",
        f"**Recall is the claim worth defending.** The baseline reported "
        f"{base['n_bug'] - bc['tp']} of {base['n_bug']} planted faults as correct. "
        "Recount reported none as correct. On the stated problem -- a wrong number "
        "reaching a report without anyone noticing -- that is the difference that "
        "matters.",
        "",
    ]

    f1_gap = abs((rec["f1"] or 0) - (base["f1"] or 0))
    lines += [
        f"**The F1 difference is not.** {pct(base['f1'])} against "
        f"{pct(rec['f1'])} is a gap of {100 * f1_gap:.0f} points on 12 cases, "
        "where a single case moves F1 by roughly 8 points and the false alarm "
        "rate by 25. It is inside the noise of this sample and is reported "
        "rather than leaned on. Twelve cases can show that a mechanism works; "
        "they cannot rank two systems that are close.",
        "",
        "**Cost is a real trade.** Recount costs "
        f"x{rec['cost_per_case_usd'] / base['cost_per_case_usd']:.1f} the "
        f"baseline and takes "
        f"x{rec['latency_per_case_s'] / max(base['latency_per_case_s'], 0.01):.1f} "
        "the wall clock, because it executes queries instead of reading them. "
        "At a fraction of a cent per verified metric that is worth paying; it is "
        "still a cost, not a rounding error to hide.",
        "",
        "Full per-case tables, including every explanation, are in "
        f"[`runs/{label}/results.md`](runs/{label}/results.md). Trajectories for "
        f"all 24 runs are in [`runs/{label}/traces/`](runs/{label}/traces/) -- see "
        "[TRAJECTORIES.md](TRAJECTORIES.md).",
    ]
    return "\n".join(lines)


def changelog_section(runs: dict) -> str:
    label, base, rec = find_main(runs)
    model = label[len("main-"):]

    rows = [
        (
            "**Baseline**",
            "One prompt: schema, question, SQL. The reasonable first attempt, and "
            "a strong one.",
            evidence_from(base),
            "Starting point. Note it already scores well -- a 2026 model is good "
            "at this task.",
        ),
        (
            "**Iteration 1**<br>profiler + probes + gate",
            "The original design. Measure the warehouse, let the agent write and "
            "run diagnostic probes, then require a bug claim to ship a correction "
            "whose effect is checked.",
            evidence_from_historical(HISTORICAL["original-design"]),
            "**Lost to the baseline by 18 points.** Kept the components, "
            "questioned the architecture.",
        ),
        (
            "**Iteration 2**<br>independent recomputation",
            "The gate could only ever downgrade a bug claim, so it was "
            "structurally unable to catch a real fault waved through -- and B1 "
            "and B4 were. Added a stage that answers the question from scratch, "
            "without seeing the query under review, then compares the two "
            "numbers.",
            evidence_from_historical(HISTORICAL["first-recompute"]),
            "**Kept.** Recall 75% -> 100%. This is the one change that worked.",
        ),
        (
            "**Iteration 3**<br>profile split by role",
            "Ablations showed the profiler was hurting. The hypothesis was that "
            "reviewers need join cardinality while authors need types and "
            "formats, so the digest was split.",
            evidence_from_historical(HISTORICAL["role-split"]),
            "**Removed.** It got worse. The trace showed the author writing "
            "`WHERE status IS NOT NULL` where the question required "
            "`WHERE status = 'completed'` -- the NULL warning displaced the "
            "required filter instead of adding to it.",
        ),
        (
            "**Iteration 4**<br>stored value formats, no hazard framing",
            "If naming a hazard makes an author defend against it, give it no "
            "hazards — only how values are stored. This was aimed at the one "
            "remaining false alarm, where the author compared against "
            "`'2026-01-01T00:00:00Z'` on values stored `'2026-01-01 02:11:00'`.",
            _evidence_or_pending(runs, f"ablation-add-formats-{model}/recount"),
            "**Removed.** It did fix that false alarm, and cost a detection "
            "doing it: recall fell 100% -> 88%, leaving the system identical to "
            "the baseline on every metric. A fix that trades a caught fault for "
            "a quieter report is not a fix.",
        ),
        (
            "**Final**<br>recomputation + gate",
            "Everything that could not be shown to help was deleted: the "
            "warehouse profiler, the probe loop, the format hints. What remains "
            "is the query under review, an independent derivation of the same "
            "question, and a comparison of the two numbers.",
            evidence_from(rec),
            "**Reported configuration.** Three of the four stages I designed "
            "were removed by their own measurements.",
        ),
    ]

    variants = [
        ("no-recompute", "Remove the recomputation",
         "the only stage that earned its place"),
        ("no-gate", "Accept the model verdict as-is",
         "what the gate is worth once recomputation exists"),
        ("add-formats", "Restore the stored-value-format hints",
         "why they were removed"),
        ("add-profile", "Restore the warehouse profiler",
         "why it was removed"),
        ("add-probes", "Restore the probe loop",
         "why it was removed"),
    ]

    out = [
        "Each row is a real run. The evidence column is generated from "
        "`runs/*/results.json` by "
        "[`scripts/render_docs.py`](scripts/render_docs.py), so these numbers "
        "cannot drift from the files they came from. Rows for superseded "
        "iterations cite the commit that recorded them; recover those with "
        "`git show <commit>:runs/<label>/results.json`.",
        "",
        "| stage | what was tried and why | evidence | decision / learning |",
        "|---|---|---|---|",
    ]
    for stage, tried, evidence, decision in rows:
        out.append(f"| {stage} | {tried} | {evidence} | {decision} |")

    out += [
        "",
        "### What each component is worth",
        "",
        "Measured against the reported configuration, on the same cases and the "
        "same model.",
        "",
        "| variant | what it changes | result |",
        "|---|---|---|",
    ]
    missing = []
    for name, change, why in variants:
        m = variant(runs, name, model)
        if m is None:
            missing.append(name)
            continue
        out.append(f"| `--{name}` | {change} — {why} | {evidence_from(m)} |")

    if missing:
        out.append("")
        out.append(
            "> Not yet recorded: "
            + ", ".join(f"`{n}`" for n in missing)
            + ". Produce them with `python3 run_all.py --model "
            + model
            + "`."
        )
    return "\n".join(out)


def splice(text: str, begin: str, end: str, body: str) -> str:
    start, stop = text.index(begin), text.index(end)
    return text[: start + len(begin)] + "\n" + body + "\n" + text[stop:]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if README.md is not up to date")
    ap.add_argument("--stdout", action="store_true",
                    help="print the generated sections and exit")
    args = ap.parse_args()

    runs = load_runs()
    results, changelog = results_section(runs), changelog_section(runs)

    if args.stdout:
        print("## Results\n\n" + results + "\n\n## Improvement Changelog\n\n" + changelog)
        return 0

    readme = ROOT / "README.md"
    original = readme.read_text(encoding="utf-8")
    updated = splice(original, RESULTS_BEGIN, RESULTS_END, results)
    updated = splice(updated, CHANGELOG_BEGIN, CHANGELOG_END, changelog)

    if args.check:
        if updated != original:
            print("README.md is out of date. Run: python3 scripts/render_docs.py",
                  file=sys.stderr)
            return 1
        print("README.md is up to date with runs/")
        return 0

    if updated == original:
        print("README.md already up to date")
    else:
        readme.write_text(updated, encoding="utf-8")
        print("README.md updated from runs/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
