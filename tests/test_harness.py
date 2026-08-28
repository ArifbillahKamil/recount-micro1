"""End-to-end harness test against the real offline replay path.

Rather than mock the harness, this seeds cassettes by walking the genuine
control flow with a scripted model, then invokes the same
``python3 -m recount.evaluate --offline`` path a reviewer would run. That
exercises cassette keying, replay, scoring, and artifact writing together.

The model is scripted to one specific adversarial behaviour: **always answer
BUG**, on every case, correct or not. That is the real failure mode of a
text-only SQL reviewer, and holding it fixed isolates what the gate contributes,
because both arms replay byte-identical model output.

Nothing here is a reported result. These are fixed inputs chosen to make the
scoring math and the gate's effect assertable. Every number in the submission
comes from a real model run.

    python3 -m tests.test_harness
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from recount import agent, baseline, cases, evaluate, warehouse  # noqa: E402
from recount.llm import MODE_RECORD, LLMClient, LLMResponse  # noqa: E402
from recount.profiler import profile  # noqa: E402

PROMPT_TOKENS = 1000
COMPLETION_TOKENS = 200
MODEL = "gpt-4o-mini"

PASSED, FAILED = [], []


def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        PASSED.append(name)
        print(f"  PASS  {name}")
    else:
        FAILED.append(f"{name}: {detail}")
        print(f"  FAIL  {name} — {detail}")


class Seeder:
    """Duck-types LLMClient, but records a scripted reply into a cassette.

    Keys are computed with the real ``LLMClient`` helpers, so the cassettes are
    indistinguishable from ones a live run would leave behind.
    """

    def __init__(self, cassette_dir: str, script: dict) -> None:
        self._writer = LLMClient(
            model=MODEL, cassette_dir=cassette_dir, mode=MODE_RECORD, api_key="unused"
        )
        self.script = script
        self.model = MODEL

    def chat(self, messages, *, step="chat", max_tokens=1000, json_mode=True, trace=None):
        if step not in self.script:
            raise AssertionError(f"no script for step {step!r}")
        payload = self.script[step]
        text = payload if isinstance(payload, str) else json.dumps(payload)

        body = self._writer._request_body(messages, max_tokens, json_mode)
        key = self._writer.cassette_key(body)
        self._writer._save(
            key,
            body,
            {
                "choices": [{"message": {"content": text}}],
                "usage": {
                    "prompt_tokens": PROMPT_TOKENS,
                    "completion_tokens": COMPLETION_TOKENS,
                },
            },
            step,
        )

        usage = {
            "prompt_tokens": PROMPT_TOKENS,
            "completion_tokens": COMPLETION_TOKENS,
            "total_tokens": PROMPT_TOKENS + COMPLETION_TOKENS,
            "cost_usd": round(
                PROMPT_TOKENS * 0.15 / 1e6 + COMPLETION_TOKENS * 0.60 / 1e6, 8
            ),
            "cost_known": True,
        }
        if trace is not None:
            trace.add_llm(
                step, messages, text, model=MODEL, usage=usage,
                cached=False, duration_s=0.0, cassette_key=key,
            )
        return LLMResponse(text, usage, False, 0.0, key)

    def summary(self) -> dict:
        return {"model": MODEL, "mode": "seeder"}


def seed_all(db: str, cassette_dir: str) -> None:
    """Record cassettes for both systems across all twelve cases.

    The recomputation step is shown the business question and the measured facts
    but never the query under review, so two cases that ask the same question
    produce a byte-identical request and therefore share one cassette. B5 and C4
    are exactly that pair -- the same question, one query correct and one not --
    which is the point of having them.

    A scripted reply must therefore be a function of the question rather than of
    the case, or the second case silently overwrites the first. Real runs get
    this for free (the model sees one prompt and returns one answer, and the
    shared key is a cost saving); only a hand-written script can violate it.
    """
    shared_profile = profile(db)
    recompute_for_question: dict = {}
    for case in cases.CASES:
        recompute_for_question.setdefault(
            case.business_question, " ".join(case.reference_sql.split())
        )

    for case in cases.CASES:
        always_bug = {
            "verdict": "BUG",
            "bug_type": case.bug_type or "fanout_join",
            "confidence": 0.85,
            "explanation": "This query looks like it returns the wrong number.",
            # The model proposes the reference query as its fix. On a genuine bug
            # that changes the number; on a correct query it changes nothing --
            # which is exactly what the gate is built to notice.
            "corrected_sql": " ".join(case.reference_sql.split()),
        }

        # The baseline is scripted to repair only the first four bugs properly and
        # to offer a cosmetic no-op rewrite for the rest, which is how a
        # text-only reviewer typically behaves. Without this mix, repair accuracy
        # would be identical for both arms and the metric untested.
        baseline_reply = dict(always_bug)
        if case.case_id[:2] not in {"B1", "B2", "B3", "B4"}:
            baseline_reply["corrected_sql"] = " ".join(case.sql.split())

        baseline.review(
            db, case.business_question, case.sql,
            Seeder(cassette_dir, {"baseline_review": baseline_reply}),
            case_id=case.case_id,
        )

        agent.review(
            db, case.business_question, case.sql,
            Seeder(
                cassette_dir,
                {
                    # A competent independent derivation: the reference query.
                    # On a planted fault it disagrees with the query under
                    # review; on a correct query it agrees. That asymmetry is
                    # what the gate reads.
                    "recompute": {
                        "sql": recompute_for_question[case.business_question],
                        "reasoning": "derived from the question and the grain",
                    },
                    "plan": {
                        "hypotheses": [
                            {
                                "risk": "the join may change the row count",
                                "bug_type": case.bug_type or "fanout_join",
                                "probe_sql": "SELECT COUNT(*) AS n FROM orders",
                                "settles": "row count",
                            }
                        ]
                    },
                    "adjudicate": always_bug,
                },
            ),
            case_id=case.case_id,
            cached_profile=shared_profile,
        )


def load(out_dir: Path, label: str) -> dict:
    return json.loads((out_dir / label / "results.json").read_text(encoding="utf-8"))


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="recount-harness-"))
    db = str(tmp / "warehouse.db")
    cassette_dir = str(tmp / "cassettes")
    out_dir = tmp / "runs"

    warehouse.build(db)
    print("\nseeding cassettes by walking the real pipeline")
    seed_all(db, cassette_dir)
    n_cassettes = len(list(Path(cassette_dir).glob("*.json")))
    check("cassettes were written", n_cassettes >= 24, f"{n_cassettes} files")

    print("\nrunning the harness in offline replay mode (no API key)")
    code = evaluate.main([
        "--db", db, "--system", "both", "--model", MODEL,
        "--offline", "--cassettes", cassette_dir,
        "--out", str(out_dir), "--label", "gate-on",
    ])
    check("harness exits cleanly", code == 0, f"exit {code}")

    payload = load(out_dir, "gate-on")
    base = payload["systems"]["baseline"]["metrics"]
    rec = payload["systems"]["recount"]["metrics"]

    print("\nscoring math, baseline (always answers BUG)")
    check("baseline TP=8", base["confusion"]["tp"] == 8, str(base["confusion"]))
    check("baseline FP=4", base["confusion"]["fp"] == 4, str(base["confusion"]))
    check("baseline recall=100%", base["recall"] == 1.0, str(base["recall"]))
    check("baseline precision=67%", round(base["precision"], 3) == 0.667, str(base["precision"]))
    check("baseline F1=80%", round(base["f1"], 3) == 0.8, str(base["f1"]))
    check("baseline false alarm rate=100%", base["false_alarm_rate"] == 1.0,
          str(base["false_alarm_rate"]))

    print("\nthe gate, given byte-identical model output")
    check("recount TP=8", rec["confusion"]["tp"] == 8, str(rec["confusion"]))
    check("recount FP=0 (gate absorbed all four)", rec["confusion"]["fp"] == 0,
          str(rec["confusion"]))
    check("recount TN=4", rec["confusion"]["tn"] == 4, str(rec["confusion"]))
    check("recount F1=100%", rec["f1"] == 1.0, str(rec["f1"]))
    check("recount repair accuracy=100% (8/8)", rec["repair_accuracy"] == 1.0,
          str(rec["repair_accuracy"]))
    check(
        "repair credit is capped at the number of planted bugs",
        base["repairs_correct"] <= base["n_bug"]
        and rec["repairs_correct"] <= rec["n_bug"],
        f"baseline {base['repairs_correct']}/{base['n_bug']}, "
        f"recount {rec['repairs_correct']}/{rec['n_bug']}",
    )
    check(
        "a cosmetic no-op rewrite earns no repair credit (baseline 4/8)",
        base["repairs_correct"] == 4 and base["repair_accuracy"] == 0.5,
        f"{base['repairs_correct']}/{base['n_bug']} = {base['repair_accuracy']}",
    )
    check(
        "gate cleared the correction on downgraded cases",
        all(
            not c["repair_attempted"]
            for c in payload["systems"]["recount"]["cases"]
            if c["truth"] == "CLEAN"
        ),
    )

    print("\nablation replays the same cassettes with the gate switched off")
    code = evaluate.main([
        "--db", db, "--system", "recount", "--model", MODEL,
        "--offline", "--cassettes", cassette_dir,
        "--out", str(out_dir), "--label", "gate-off", "--no-gate",
    ])
    check("ablation exits cleanly", code == 0, f"exit {code}")
    ablated = load(out_dir, "gate-off")["systems"]["recount"]["metrics"]
    check("without the gate FP returns to 4", ablated["confusion"]["fp"] == 4,
          str(ablated["confusion"]))
    check("without the gate F1 falls to 80%", round(ablated["f1"], 3) == 0.8,
          str(ablated["f1"]))
    check(
        "the gate is worth +20 F1 points on identical model output",
        round(rec["f1"] - ablated["f1"], 3) == 0.2,
        f"{rec['f1']} vs {ablated['f1']}",
    )

    print("\ncost accounting")
    check("baseline 1 model call per case", base["llm_calls"] == 12, str(base["llm_calls"]))
    check(
        "recount 3 model calls per case (recompute, plan, adjudicate)",
        rec["llm_calls"] == 36,
        str(rec["llm_calls"]),
    )
    check("baseline cost/case is priced from recorded tokens",
          round(base["cost_per_case_usd"], 5) == 0.00027, str(base["cost_per_case_usd"]))
    check("recount cost/case is triple the baseline",
          round(rec["cost_per_case_usd"], 5) == 0.00081, str(rec["cost_per_case_usd"]))

    print("\nartifacts")
    run_dir = out_dir / "gate-on"
    md = (run_dir / "results.md").read_text(encoding="utf-8")
    check("results.md has the headline table", "Headline comparison" in md)
    check("results.md reports the primary metric", "F1 on bug detection" in md)
    traces = list((run_dir / "traces").glob("*.md"))
    check("a trajectory per case per system", len(traces) == 24, str(len(traces)))
    sample = (run_dir / "traces" / "recount__B1_fanout_payments_via_line_items.md").read_text(
        encoding="utf-8"
    )
    check("trajectory shows the gate decision", "verification_gate" in sample)
    check("trajectory shows tool responses", "run_sql" in sample)
    check("trajectory marks replayed calls", "replayed" in sample)

    print("\ndeterminism of replay")
    code = evaluate.main([
        "--db", db, "--system", "both", "--model", MODEL,
        "--offline", "--cassettes", cassette_dir,
        "--out", str(out_dir), "--label", "gate-on-again",
    ])
    again = load(out_dir, "gate-on-again")
    check("replay is deterministic", code == 0 and
          again["systems"]["recount"]["metrics"]["f1"] == rec["f1"] and
          again["systems"]["baseline"]["metrics"]["f1"] == base["f1"])

    print("\n" + "=" * 62)
    print(f"{len(PASSED)} passed, {len(FAILED)} failed")
    for failure in FAILED:
        print(f"  - {failure}")
    print(f"\nartifacts under {out_dir}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
