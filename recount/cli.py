"""``recount check`` -- verify one query and print a report you can act on.

    # a bundled case, replayed from cassettes at no cost
    python3 -m recount.cli --case B1 --offline

    # your own query
    python3 -m recount.cli \
        --db data/warehouse.db \
        --question "How much did we capture from completed orders?" \
        --sql-file query.sql

    # what the simple baseline says about the same query, for contrast
    python3 -m recount.cli --case B1 --offline --baseline
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional

from . import agent, baseline, cases as case_mod, env, report, warehouse
from .llm import MODE_AUTO, MODE_RECORD, MODE_REPLAY, CassetteMiss, LLMClient, LLMError
from .sqlio import SqlError, run_sql


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="recount",
        description="Verify that a SQL answer actually answers the question.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--db", default="data/warehouse.db")
    p.add_argument("--build", action="store_true", help="rebuild the demo warehouse")
    p.add_argument("--case", help="id or prefix of a bundled evaluation case")
    p.add_argument("--question", help="the business question that was asked")
    p.add_argument("--sql", help="the SQL to verify")
    p.add_argument("--sql-file", help="read the SQL from a file")
    p.add_argument("--model", default="gpt-4o-mini")
    p.add_argument("--offline", action="store_true", help="replay cassettes only")
    p.add_argument("--record", action="store_true", help="force fresh API calls")
    p.add_argument("--cassettes", default="cassettes")
    p.add_argument("--baseline", action="store_true",
                   help="run the single-prompt baseline instead of Recount")
    p.add_argument("--out", help="write the report to this path")
    p.add_argument("--trace-dir", help="write the trajectory here")
    p.add_argument("--json", action="store_true", help="emit the verdict as JSON")
    p.add_argument("--price-in", type=float, default=None)
    p.add_argument("--price-out", type=float, default=None)
    return p


def _resolve_input(args) -> tuple:
    """Return ``(question, sql, title)`` from the flags provided."""
    if args.case:
        matches = [
            c for c in case_mod.CASES
            if c.case_id.lower().startswith(args.case.lower())
        ]
        if not matches:
            raise SystemExit(
                f"no bundled case matches {args.case!r}. Available:\n  "
                + "\n  ".join(c.case_id for c in case_mod.CASES)
            )
        if len(matches) > 1:
            raise SystemExit(
                f"{args.case!r} is ambiguous:\n  "
                + "\n  ".join(c.case_id for c in matches)
            )
        case = matches[0]
        return case.business_question, case.sql, None

    sql = args.sql
    if args.sql_file:
        sql = Path(args.sql_file).read_text(encoding="utf-8")
    if not sql or not args.question:
        raise SystemExit(
            "provide either --case, or both --question and --sql/--sql-file.\n"
            "Run with --help for examples."
        )
    return args.question, sql, None


def main(argv: Optional[list] = None) -> int:
    args = build_parser().parse_args(argv)
    env.load()

    if args.build or not Path(args.db).exists():
        print(f"building demo warehouse at {args.db}", file=sys.stderr)
        warehouse.build(args.db)

    question, sql, title = _resolve_input(args)

    mode = MODE_AUTO
    if args.offline:
        mode = MODE_REPLAY
    elif args.record:
        mode = MODE_RECORD

    if mode != MODE_REPLAY and not os.environ.get("OPENAI_API_KEY"):
        print(
            "OPENAI_API_KEY is not set. Export it, or pass --offline to replay "
            "recorded cassettes at no cost.",
            file=sys.stderr,
        )
        return 2

    try:
        original_result = run_sql(args.db, sql)
    except SqlError as exc:
        print(f"the query does not execute: {exc}", file=sys.stderr)
        return 1

    client = LLMClient(
        model=args.model,
        cassette_dir=args.cassettes,
        mode=mode,
        price_in=args.price_in,
        price_out=args.price_out,
    )

    system = "baseline" if args.baseline else "recount"
    try:
        if args.baseline:
            result, trace = baseline.review(
                args.db, question, sql, client, case_id=args.case or "adhoc"
            )
        else:
            result, trace = agent.review(
                args.db, question, sql, client, case_id=args.case or "adhoc"
            )
    except CassetteMiss as exc:
        print(
            f"{exc}\n\n"
            "Nothing was recorded for this exact request. Drop --offline to call "
            "the API, or pick a bundled --case that was recorded.",
            file=sys.stderr,
        )
        return 3
    except LLMError as exc:
        print(f"model call failed: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(
            {
                "system": system,
                "verdict": result.to_dict(),
                "usage": trace.usage,
            },
            indent=2,
        ))
    else:
        text = report.render(
            question, sql, result, original_result,
            title=title, model=args.model,
        )
        print(text)
        if args.out:
            Path(args.out).parent.mkdir(parents=True, exist_ok=True)
            Path(args.out).write_text(text, encoding="utf-8")
            print(f"\n(report written to {args.out})", file=sys.stderr)

    if args.trace_dir:
        written = trace.write(args.trace_dir)
        print(f"(trajectory written to {written['markdown']})", file=sys.stderr)

    usage = trace.usage
    print(
        f"\n[{system}: {usage['llm_calls']} model call(s), "
        f"{usage['tool_calls']} tool call(s), "
        f"{usage['cached_calls']} replayed, "
        f"${usage['cost_usd']:.5f} at recorded rates]",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
