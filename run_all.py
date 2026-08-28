#!/usr/bin/env python3
"""Produce every number the submission reports. Works on Windows, macOS, Linux.

    # Windows PowerShell
    $env:OPENAI_API_KEY="sk-..."
    python run_all.py --model gpt-4o-mini

    # macOS / Linux
    export OPENAI_API_KEY=sk-...
    python3 run_all.py --model gpt-4o-mini

Pin the rate you were actually billed so the reported cost is honest:

    python run_all.py --model gpt-5.4-mini --price-in 0.75 --price-out 4.50

Roughly 4x one full run: about $0.05 on gpt-4o-mini, about $1.10 on gpt-5.4.
Runtime is dominated by API latency, roughly 10-20 minutes.

Use --dry-run to check everything works before spending anything.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = sys.executable or "python3"


def banner(step: str, total: int, title: str) -> None:
    print(f"\n{'=' * 70}\n  {step}/{total}  {title}\n{'=' * 70}", flush=True)


def run(args: list, tail: int = 0) -> str:
    """Run a subcommand, stream or tail its output, abort on failure."""
    printable = " ".join(["python"] + args[1:])
    print(f"$ {printable}\n", flush=True)
    proc = subprocess.run(args, cwd=HERE, capture_output=True, text=True)
    output = (proc.stdout or "") + (proc.stderr or "")
    lines = output.rstrip().splitlines()
    shown = lines[-tail:] if tail and len(lines) > tail else lines
    for line in shown:
        print("  " + line)
    if proc.returncode != 0:
        print(f"\nFAILED (exit {proc.returncode}). Stopping.", file=sys.stderr)
        raise SystemExit(proc.returncode)
    print()
    return output


def check_warehouse() -> None:
    """Confirm the generated data matches, by content rather than by file bytes.

    Deliberately not a hash of the .db file: SQLite's on-disk layout varies with
    the library version, so that check fails across machines whose data is in
    fact identical.
    """
    sys.path.insert(0, str(HERE))
    from recount import warehouse

    digest = warehouse.content_digest(HERE / "data" / "warehouse.db")
    print(f"  content digest = {digest}")
    if digest != warehouse.CONTENT_DIGEST:
        raise SystemExit(
            f"  MISMATCH: expected {warehouse.CONTENT_DIGEST}\n\n"
            "  The generated data differs, so results would not be comparable.\n"
            "  This should not happen with an unmodified checkout. Check that:\n"
            "    - recount/warehouse.py is unmodified (git status)\n"
            "    - you did not pass a custom --seed\n"
            "  Then report the digest above along with your Python version."
        )
    print("  matches the published digest -- your data is identical\n")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--model", default="gpt-4o-mini")
    p.add_argument("--price-in", type=float, default=None,
                   help="USD per 1M input tokens, as billed to you")
    p.add_argument("--price-out", type=float, default=None,
                   help="USD per 1M output tokens, as billed to you")
    p.add_argument("--dry-run", action="store_true",
                   help="setup and tests only; makes no API calls and costs nothing")
    args = p.parse_args()

    price: list = []
    if args.price_in is not None and args.price_out is not None:
        price = ["--price-in", str(args.price_in), "--price-out", str(args.price_out)]

    model = args.model
    total = 3 if args.dry_run else 8

    banner(1, total, "Build the warehouse (deterministic, seeded)")
    run([PY, "-m", "recount.warehouse", "--db", "data/warehouse.db"])
    check_warehouse()

    banner(2, total, "Validate the eval set against the data")
    run([PY, "-m", "recount.cases", "--db", "data/warehouse.db"], tail=4)

    banner(3, total, "Test suites (scripted model, no API calls, no cost)")
    run([PY, "-m", "tests.test_pipeline"], tail=3)
    run([PY, "-m", "tests.test_harness"], tail=3)

    if args.dry_run:
        print("\nDry run complete. Everything works and nothing was spent.")
        print("When ready, set OPENAI_API_KEY and run again without --dry-run.")
        return 0

    sys.path.insert(0, str(HERE))
    from recount import env as _env

    _env.load(HERE)

    if not os.environ.get("OPENAI_API_KEY"):
        print("OPENAI_API_KEY is not set.\n", file=sys.stderr)
        print("Pick either one:\n", file=sys.stderr)
        print(f"  A) a .env file at {HERE}", file=sys.stderr)
        print("       cp .env.example .env          # macOS / Linux", file=sys.stderr)
        print("       Copy-Item .env.example .env   # Windows PowerShell", file=sys.stderr)
        print("     then edit it and put your key on the OPENAI_API_KEY line\n",
              file=sys.stderr)
        print("  B) an environment variable in this shell", file=sys.stderr)
        print("       $env:OPENAI_API_KEY=\"sk-...\"   # Windows PowerShell",
              file=sys.stderr)
        print("       export OPENAI_API_KEY=sk-...   # macOS / Linux\n",
              file=sys.stderr)
        print("Or use --dry-run to verify the project without a key.", file=sys.stderr)
        return 2

    main_label = f"main-{model}"
    ablations = [
        ("no-profile", ["--no-profile"], "schema only, no measured data facts"),
        ("no-probes", ["--no-probes"], "no executed probes"),
        ("no-gate", ["--no-gate"], "model verdict accepted as-is"),
    ]

    banner(4, total, f"Headline run: baseline vs Recount on {model}")
    run([PY, "-m", "recount.evaluate", "--system", "both", "--model", model,
         "--record", "--label", main_label] + price)

    for index, (name, flags, description) in enumerate(ablations, start=5):
        banner(index, total, f"Ablation: {name} ({description})")
        run([PY, "-m", "recount.evaluate", "--system", "recount", "--model", model,
             "--label", f"ablation-{name}-{model}"] + flags + price)

    banner(8, total, "Confirm a reviewer with no API key gets the same numbers")
    run([PY, "-m", "recount.evaluate", "--system", "both", "--model", model,
         "--offline", "--label", f"verify-offline-{model}"] + price)

    paths = [f"runs/{main_label}/results.json"] + [
        f"runs/ablation-{name}-{model}/results.json" for name, _, _ in ablations
    ]
    table = run([PY, "-m", "recount.evaluate", "--compare"] + paths)
    (HERE / "runs" / "changelog-table.md").write_text(table, encoding="utf-8")

    print("\n" + "=" * 70)
    print("Done. Send these back so the changelog is written from real numbers:\n")
    print(f"  runs/{main_label}/results.md          <- the headline table")
    print("  runs/changelog-table.md               <- the ablation comparison")
    print("\nPasting the contents of those two files into the chat is enough.\n")
    print("Also commit cassettes/ -- that is what lets judges reproduce for free,")
    print("and it doubles as the agent trajectory evidence.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
