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


def banner(step, total: int, title: str) -> None:
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
    total = 3 if args.dry_run else 10

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

    # The reported configuration. Arrived at by measurement, not design: the
    # warehouse profiler and the probe loop were each measured to cost accuracy
    # or money while contributing nothing, and were removed. What remains is the
    # independent recomputation, the gate, and stored value formats.
    REPORTED = ["--no-profile", "--no-probes"]

    main_label = f"main-{model}"
    variants = [
        # Removing a stage that is in the reported configuration.
        ("no-recompute", REPORTED + ["--no-recompute"],
         "drop the independent recomputation"),
        ("no-gate", REPORTED + ["--no-gate"], "accept the model verdict as-is"),
        ("no-formats", REPORTED + ["--no-formats"],
         "withhold stored value formats from the author"),
        # Putting back a stage that was removed, to show why it was.
        ("add-profile", ["--no-probes"], "restore the warehouse profiler"),
        ("add-probes", ["--no-profile"], "restore the probe loop"),
    ]

    banner(4, total, f"Headline run: baseline vs Recount on {model}")
    run([PY, "-m", "recount.evaluate", "--system", "both", "--model", model,
         "--record", "--label", main_label] + REPORTED + price)

    for index, (name, flags, description) in enumerate(variants, start=5):
        banner(index, total, f"Variant: {name} ({description})")
        run([PY, "-m", "recount.evaluate", "--system", "recount", "--model", model,
             "--label", f"ablation-{name}-{model}"] + flags + price)

    banner(10, total, "Confirm a reviewer with no API key gets the same numbers")
    run([PY, "-m", "recount.evaluate", "--system", "both", "--model", model,
         "--offline", "--label", f"verify-offline-{model}"] + REPORTED + price)

    paths = [f"runs/{main_label}/results.json"] + [
        f"runs/ablation-{name}-{model}/results.json" for name, _, _ in variants
    ]
    table = run([PY, "-m", "recount.evaluate", "--compare"] + paths)
    (HERE / "runs" / "changelog-table.md").write_text(table, encoding="utf-8")

    # Regenerate the README's Results and Improvement Changelog from what was
    # just recorded, so the reported numbers cannot drift from the files behind
    # them and nothing is transcribed by hand.
    banner("+", total, "Regenerate the README from the recorded runs")
    run([PY, "scripts/render_docs.py"])

    print("\n" + "=" * 70)
    print("Done. The README's Results and Improvement Changelog now reflect this run.\n")
    print(f"  runs/{main_label}/results.md       headline table and per-case detail")
    print("  runs/changelog-table.md            every configuration side by side")
    print(f"  runs/{main_label}/traces/          one trajectory per case per system")
    print("\nCommit all of it -- runs/ and cassettes/ are the evidence, and")
    print("cassettes/ is what lets a reviewer replay this for free:\n")
    print("  git add runs cassettes README.md")
    print('  git commit -m "Recorded evaluation run"')
    print("  git push")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
