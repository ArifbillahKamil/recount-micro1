"""Evaluation harness: run the baseline and Recount over the same cases.

Both systems get the same warehouse, the same twelve cases, the same model, the
same temperature and seed, and the same output contract. They are scored by the
same code. The only difference is the one under test: measured facts, executed
probes, and the verification gate.

Typical use::

    # once
    python3 -m recount.warehouse --db data/warehouse.db

    # the headline comparison
    python3 -m recount.evaluate --system both --model gpt-4o-mini

    # reproduce it later, or on a machine with no API key, for free
    python3 -m recount.evaluate --system both --offline

    # measure what a single stage contributes, for the changelog
    python3 -m recount.evaluate --system recount --no-gate --label no-gate
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from . import agent, baseline, cases as case_mod, env, scoring, verdict as V, warehouse
from .llm import MODE_AUTO, MODE_RECORD, MODE_REPLAY, CassetteMiss, LLMClient
from .profiler import profile as build_profile
from .scoring import Outcome, TimeModel
from .sqlio import SqlError, result_signature, run_sql
from .trace import Trace

BASELINE = "baseline"
RECOUNT = "recount"


@dataclass
class RunConfig:
    db: str
    model: str
    mode: str
    cassette_dir: str
    out_dir: str
    label: str
    enable_gate: bool = True
    enable_probes: bool = True
    enable_profile: bool = True
    max_probes: int = agent.MAX_PROBES
    price_in: Optional[float] = None
    price_out: Optional[float] = None
    write_traces: bool = True

    def describe(self) -> dict:
        return {
            "model": self.model,
            "mode": self.mode,
            "gate_enabled": self.enable_gate,
            "probes_enabled": self.enable_probes,
            "profile_enabled": self.enable_profile,
            "max_probes": self.max_probes,
            "db": self.db,
        }


def _check_repair(db: str, case: case_mod.Case, result: V.Verdict) -> tuple:
    """Did the proposed correction actually return the true number?

    Ground truth is touched here and nowhere else. The system under test never
    sees ``reference_sql``; it is used only to grade the answer after the fact.
    """
    if not result.corrected_sql:
        return False, False
    try:
        corrected = run_sql(db, result.corrected_sql)
        expected = run_sql(db, case.reference_sql)
    except SqlError:
        return True, False
    return True, result_signature(corrected) == result_signature(expected)


def run_system(
    system: str,
    selected: list,
    config: RunConfig,
    time_model: TimeModel,
) -> tuple:
    """Run one system over the selected cases. Returns (Metrics, outcomes, meta)."""
    client = LLMClient(
        model=config.model,
        cassette_dir=config.cassette_dir,
        mode=config.mode,
        price_in=config.price_in,
        price_out=config.price_out,
    )
    shared_profile = build_profile(config.db) if system == RECOUNT else None

    outcomes: list = []
    traces: list = []

    for index, case in enumerate(selected, start=1):
        print(f"  [{index:>2}/{len(selected)}] {case.case_id} ... ", end="", flush=True)
        started = time.time()
        trace = Trace(case_id=case.case_id, system=system)

        if system == BASELINE:
            result, trace = baseline.review(
                config.db,
                case.business_question,
                case.sql,
                client,
                case_id=case.case_id,
                trace=trace,
            )
        else:
            result, trace = agent.review(
                config.db,
                case.business_question,
                case.sql,
                client,
                case_id=case.case_id,
                trace=trace,
                cached_profile=shared_profile,
                max_probes=config.max_probes,
                enable_gate=config.enable_gate,
                enable_probes=config.enable_probes,
                enable_profile=config.enable_profile,
            )

        elapsed = time.time() - started
        attempted, correct = _check_repair(config.db, case, result)
        usage = trace.usage

        outcomes.append(
            Outcome(
                case_id=case.case_id,
                is_bug=case.is_bug,
                expected_bug_type=case.bug_type,
                verdict=result.verdict,
                bug_type=result.bug_type,
                confidence=result.confidence,
                repair_attempted=attempted,
                repair_correct=correct,
                latency_s=elapsed,
                cost_usd=usage["cost_usd"],
                cost_known=True,
                llm_calls=usage["llm_calls"],
                tool_calls=usage["tool_calls"],
                error=result.error,
                tags=case.tags,
                explanation=result.explanation,
            )
        )
        traces.append(trace)

        mark = outcomes[-1].outcome_class
        print(f"{result.verdict:<9} {mark}  ({elapsed:.1f}s)")

    metrics = scoring.score(system, outcomes, time_model)

    if config.write_traces:
        trace_dir = Path(config.out_dir) / config.label / "traces"
        for trace in traces:
            trace.write(trace_dir)

    return metrics, outcomes, {"client": client.summary()}


def write_results(
    config: RunConfig,
    results: dict,
    time_model: TimeModel,
) -> Path:
    out = Path(config.out_dir) / config.label
    out.mkdir(parents=True, exist_ok=True)

    payload = {
        "label": config.label,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "config": config.describe(),
        "time_model": time_model.describe(),
        "systems": {
            name: {
                "metrics": bundle["metrics"].to_dict(),
                "client": bundle["meta"]["client"],
                "cases": [
                    {
                        "case_id": o.case_id,
                        "truth": "BUG" if o.is_bug else "CLEAN",
                        "expected_bug_type": o.expected_bug_type,
                        "verdict": o.verdict,
                        "bug_type": o.bug_type,
                        "class": o.outcome_class,
                        "confidence": o.confidence,
                        "repair_attempted": o.repair_attempted,
                        "repair_correct": o.repair_correct,
                        "latency_s": round(o.latency_s, 2),
                        "cost_usd": round(o.cost_usd, 6),
                        "llm_calls": o.llm_calls,
                        "tool_calls": o.tool_calls,
                        "error": o.error,
                        "explanation": o.explanation,
                    }
                    for o in bundle["outcomes"]
                ],
            }
            for name, bundle in results.items()
        },
    }
    (out / "results.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        f"# Evaluation — {config.label}",
        "",
        f"Model `{config.model}` · mode `{config.mode}` · "
        f"profile {'on' if config.enable_profile else 'OFF'} · "
        f"probes {'on' if config.enable_probes else 'OFF'} · "
        f"gate {'on' if config.enable_gate else 'OFF'}",
        "",
        f"Analyst-minute model: {time_model.describe()}",
        "",
    ]

    if BASELINE in results and RECOUNT in results:
        lines += [
            "## Headline comparison",
            "",
            scoring.comparison_table(
                results[BASELINE]["metrics"], results[RECOUNT]["metrics"]
            ),
            "",
        ]

    for name, bundle in results.items():
        lines += [
            f"## {name} — per case",
            "",
            scoring.per_case_table(bundle["outcomes"]),
            "",
            "```json",
            json.dumps(bundle["metrics"].to_dict(), indent=2),
            "```",
            "",
        ]

    (out / "results.md").write_text("\n".join(lines), encoding="utf-8")
    return out


def compare_files(paths: list) -> str:
    """Render a metric table across several results.json files, for the changelog."""
    loaded = []
    for path in paths:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        for system, bundle in payload["systems"].items():
            loaded.append((f"{payload['label']}/{system}", bundle["metrics"]))

    header = "| run | F1 | precision | recall | false alarms | repairs | escalations | cost/case |"
    out = [header, "|---|---|---|---|---|---|---|---|"]
    for label, m in loaded:
        fa = f"{m['confusion']['fp']}/{m['n_clean']}"
        rp = f"{m['repairs_correct']}/{m['n_bug']}"
        esc = m["escalations_on_bug"] + m["escalations_on_clean"]
        cost = f"${m['cost_per_case_usd']:.5f}" if m["cost_known"] else "unpriced"
        out.append(
            f"| `{label}` | {_p(m['f1'])} | {_p(m['precision'])} | {_p(m['recall'])} "
            f"| {fa} | {rp} | {esc} | {cost} |"
        )
    return "\n".join(out)


def _p(value) -> str:
    return "n/a" if value is None else f"{100 * value:.0f}%"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Evaluate the baseline and Recount on the same cases.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--db", default="data/warehouse.db")
    p.add_argument("--build", action="store_true", help="rebuild the warehouse first")
    p.add_argument(
        "--system", choices=[BASELINE, RECOUNT, "both"], default="both"
    )
    p.add_argument("--model", default="gpt-4o-mini")
    p.add_argument(
        "--offline",
        action="store_true",
        help="replay recorded cassettes only; needs no API key and costs nothing",
    )
    p.add_argument(
        "--record",
        action="store_true",
        help="always call the API and overwrite cassettes",
    )
    p.add_argument("--cassettes", default="cassettes")
    p.add_argument("--out", default="runs")
    p.add_argument("--label", default=None, help="run directory name")
    p.add_argument("--cases", default=None, help="comma-separated case id prefixes")
    p.add_argument("--list-cases", action="store_true")
    p.add_argument("--no-gate", action="store_true", help="ablation: skip the gate")
    p.add_argument("--no-probes", action="store_true", help="ablation: skip probing")
    p.add_argument(
        "--no-profile",
        action="store_true",
        help="ablation: schema only, no measured data facts",
    )
    p.add_argument("--max-probes", type=int, default=agent.MAX_PROBES)
    p.add_argument("--price-in", type=float, default=None, help="USD per 1M input tokens")
    p.add_argument("--price-out", type=float, default=None, help="USD per 1M output tokens")
    p.add_argument("--minutes-saved", type=float, default=12.0)
    p.add_argument("--minutes-false-alarm", type=float, default=8.0)
    p.add_argument("--minutes-escalation", type=float, default=4.0)
    p.add_argument("--compare", nargs="+", default=None, help="results.json paths")
    return p


def main(argv: Optional[list] = None) -> int:
    args = build_parser().parse_args(argv)
    env.load()

    if args.compare:
        print(compare_files(args.compare))
        return 0

    if args.list_cases:
        for case in case_mod.CASES:
            kind = "BUG  " if case.is_bug else "CLEAN"
            print(f"  {kind} {case.case_id}  ({case.bug_type or 'correct'})")
        return 0

    # Credentials are checked before any work, so a missing key fails in a
    # second rather than after building and validating.
    mode = MODE_AUTO
    if args.offline:
        mode = MODE_REPLAY
    elif args.record:
        mode = MODE_RECORD

    if mode != MODE_REPLAY and not os.environ.get("OPENAI_API_KEY"):
        print(
            "OPENAI_API_KEY is not set.\n"
            "Either export it, or run with --offline to replay recorded cassettes.",
            file=sys.stderr,
        )
        return 2

    if args.build or not Path(args.db).exists():
        print(f"building warehouse at {args.db}")
        stats = warehouse.build(args.db)
        print(f"  {stats.orders} orders, {stats.order_items} line items, "
              f"{stats.payments} payments, {stats.orders_with_null_status} null-status\n")

    print("validating the eval set against the data ...")
    case_mod.validate(args.db)
    print(f"  ok: {len(case_mod.CASES)} cases, every label backed by executed SQL\n")

    selected = list(case_mod.CASES)
    if args.cases:
        wanted = [c.strip().lower() for c in args.cases.split(",") if c.strip()]
        selected = [
            c for c in selected if any(c.case_id.lower().startswith(w) for w in wanted)
        ]
        if not selected:
            print(f"no cases matched {args.cases!r}", file=sys.stderr)
            return 2

    systems = [BASELINE, RECOUNT] if args.system == "both" else [args.system]
    label = args.label or _default_label(args, mode)

    config = RunConfig(
        db=args.db,
        model=args.model,
        mode=mode,
        cassette_dir=args.cassettes,
        out_dir=args.out,
        label=label,
        enable_gate=not args.no_gate,
        enable_probes=not args.no_probes,
        enable_profile=not args.no_profile,
        max_probes=args.max_probes,
        price_in=args.price_in,
        price_out=args.price_out,
    )
    time_model = TimeModel(
        confirmed_bug_saved=args.minutes_saved,
        false_alarm_cost=args.minutes_false_alarm,
        escalation_cost=args.minutes_escalation,
    )

    results: dict = {}
    for system in systems:
        print(f"running {system} on {len(selected)} cases "
              f"(model {config.model}, mode {mode})")
        try:
            metrics, outcomes, meta = run_system(system, selected, config, time_model)
        except CassetteMiss as exc:
            print(
                f"\nreplay failed for {system}: {exc}\n\n"
                "This run is NOT a reproduction and no results were written.\n"
                "Either the cassettes for this configuration were never recorded, "
                "or a prompt changed since they were.\n"
                f"Record them with:  python3 -m recount.evaluate --system {system} "
                f"--model {config.model} --record",
                file=sys.stderr,
            )
            return 3
        results[system] = {"metrics": metrics, "outcomes": outcomes, "meta": meta}
        print(f"  -> {scoring.summary_line(metrics)}\n")

    out = write_results(config, results, time_model)

    if BASELINE in results and RECOUNT in results:
        print(scoring.comparison_table(
            results[BASELINE]["metrics"], results[RECOUNT]["metrics"]
        ))
        print()
    print(f"written: {out}/results.md, {out}/results.json, {out}/traces/")
    return 0


def _default_label(args, mode: str) -> str:
    bits = [args.system, args.model.replace("/", "-")]
    if args.no_gate:
        bits.append("no-gate")
    if args.no_probes:
        bits.append("no-probes")
    if args.no_profile:
        bits.append("no-profile")
    if mode == MODE_REPLAY:
        bits.append("replay")
    return "-".join(bits)


if __name__ == "__main__":
    raise SystemExit(main())
