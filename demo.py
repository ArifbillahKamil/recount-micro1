#!/usr/bin/env python3
"""Guided demo for the solution video. Press Enter, talk, press Enter.

    python3 demo.py             step through all eight beats
    python3 demo.py --script    print every line you have to say
    python3 demo.py --cue 3     the lines for one beat only
    python3 demo.py --list      show the beats without running anything
    python3 demo.py --step 3    run one beat on its own
    python3 demo.py --check     verify every beat runs, then exit

Everything runs offline against the committed cassettes, so there is no network
call, nothing to spend, and no chance of a surprise mid-take.

Keep VIDEO.md open somewhere off-camera. This script puts only clean output on
screen; the words are in there.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = sys.executable or "python3"
WIDTH = 74

OFFLINE = ["--offline"]
REPORTED = ["--no-profile", "--no-probes", "--no-formats"]


def rule(char: str = "─") -> str:
    return char * WIDTH


def banner(number: int, total: int, title: str, subtitle: str = "") -> None:
    print("\n" * 2 + rule("━"))
    print(f"  {number}/{total}   {title}")
    if subtitle:
        print(f"         {subtitle}")
    print(rule("━") + "\n")


def shell(args: list, echo: bool = True) -> str:
    if echo:
        printable = " ".join(["python"] + [a for a in args[1:]])
        print(f"$ {printable}\n")
    proc = subprocess.run(args, cwd=HERE, capture_output=True, text=True)
    out = (proc.stdout or "") + (proc.stderr or "")
    print(out.rstrip())
    return out


_INTERACTIVE = True


def pause(prompt: str = "Enter to continue") -> None:
    if not _INTERACTIVE:
        return
    try:
        input(f"\n{rule()}\n[{prompt}] ")
    except EOFError:
        pass


# ---------------------------------------------------------------------------
# The eight beats
# ---------------------------------------------------------------------------


def beat_1() -> None:
    """A wrong query that reports itself as correct."""
    shell([PY, "-m", "recount.cli", "--case", "B2", *OFFLINE, "--baseline"])


def beat_2() -> None:
    """The same query, verified."""
    shell([PY, "-m", "recount.cli", "--case", "B2", *OFFLINE])


def beat_3() -> None:
    """What the recomputation step is and is not shown."""
    trace = HERE / "runs" / "main-gpt-4o-mini" / "traces"
    path = trace / "recount__B2_fanout_units_via_payments.md"
    if not path.exists():
        print(f"(missing {path} — run: python run_all.py --model gpt-4o-mini)")
        return

    import json

    jsonl = path.with_suffix(".jsonl")
    events = [json.loads(line) for line in jsonl.read_text(encoding="utf-8").splitlines()]

    for event in events:
        if event["kind"] == "llm" and event["step"] == "recompute":
            prompt = event["messages"][-1]["content"]
            print("The entire prompt the recomputation step receives:\n")
            print(rule("·"))
            print(prompt.strip())
            print(rule("·"))
            print("\nNote what is absent: the query under review.")
            print("It is deriving the answer, not reviewing anyone's work.\n")
            print("Its reply:\n")
            print("  " + " ".join(event["response"].split())[:400])
            break

    for event in events:
        if event["kind"] == "gate":
            print(f"\nThe gate compared the two numbers → {event['decision']}")
            print(f"  {event['reason']}")
            break


def beat_4() -> None:
    """A correct query that looks exactly like the broken one."""
    from recount import cases

    b1 = cases.by_id("B1_fanout_payments_via_line_items")
    c2 = cases.by_id("C2_clean_units_sold_at_line_grain")
    print("Two queries. Both join orders to order_items, then aggregate.\n")
    for label, case in (("B1  — a real fault", b1), ("C2  — entirely correct", c2)):
        print(f"  {label}")
        print(f"    asked:  {case.business_question.strip()}")
        print("    " + " ".join(case.sql.split()))
        print()
    print("The shape is identical. Only the question tells them apart:")
    print("C2 asks for units sold, which really does live at line-item grain.\n")
    pause("Enter to run C2 through Recount")
    shell([PY, "-m", "recount.cli", "--case", "C2", *OFFLINE])


def beat_5() -> None:
    """The one case Recount gets wrong."""
    print("Recount is not clean. This is its false alarm.\n")
    shell([PY, "-m", "recount.cli", "--case", "C4", *OFFLINE])


def beat_6() -> None:
    """The comparison."""
    shell([PY, "-m", "recount.evaluate", "--system", "both", *OFFLINE,
           *REPORTED, "--label", "demo"])


def beat_7() -> None:
    """Reproducibility."""
    print("No API key is set for this shell, and no network call is made.")
    print("Every model response is committed under cassettes/.\n")
    shell([PY, "-c",
           "import os;print('OPENAI_API_KEY set:', bool(os.environ.get('OPENAI_API_KEY')))"],
          echo=False)
    print()
    shell([PY, "-m", "recount.evaluate", "--system", "both", *OFFLINE,
           *REPORTED, "--label", "demo-again"])
    print("\nSame numbers, twice, for nothing.")


def beat_8() -> None:
    """What each component was actually worth."""
    table = HERE / "runs" / "changelog-table.md"
    if table.exists():
        print(table.read_text(encoding="utf-8").rstrip())
    print("\nRemove the recomputation and F1 falls to 55%.")
    print("Everything else I built either changed nothing or made it worse.")


BEATS = [
    (beat_1, "The problem",
     "a reviewer calls a 22% overstatement correct"),
    (beat_2, "The same query, verified",
     "reported 3,648 units against 2,993 — and a runnable fix"),
    (beat_3, "How it works",
     "the recomputation never sees the query it is checking"),
    (beat_4, "The hard case",
     "a correct query shaped exactly like the broken one"),
    (beat_5, "Where it fails",
     "Recount's own false alarm, shown rather than hidden"),
    (beat_6, "The comparison",
     "same cases, same model, same contract"),
    (beat_7, "Reproducible with no API key",
     "replayed from committed cassettes, at no cost"),
    (beat_8, "What each component was worth",
     "three of four stages were deleted by their own numbers"),
]

# What to say, per beat. Short sentences on purpose: these are meant to be
# spoken, and a line you stumble over costs more than a line that is plain.
#
# "BEFORE" is said with the banner on screen, before pressing Enter.
# "AFTER" is said once the output has appeared.
NARRATION = {
    1: {
        "seconds": 42,
        "before": [
            "Every BI tool now has 'ask your data a question'.",
            "A model writes the SQL. The query runs. A number comes back.",
            "Here is what nobody checks.",
            "A wrong SQL query does not fail. It returns.",
            "So here is the obvious defence: show a model the query, and ask if"
            " it is right.",
        ],
        "after": [
            "It says the number holds. Three thousand six hundred and forty-eight units.",
            "The real answer is two thousand nine hundred and ninety-three.",
            "This query joins through payments. Installment orders have several"
            " payment rows, so every line item gets counted twice. Overstated"
            " twenty-two percent.",
            "No error. No warning.",
            "And that explanation is fluent, specific, and wrong. That is the"
            " failure that matters.",
        ],
    },
    2: {
        "seconds": 22,
        "before": ["Same query. Now through Recount."],
        "after": [
            "It reports the overstatement, the true figure, and the size of the gap.",
            "Then it gives you a corrected query you can run. Not a warning, a fix.",
            "Every number there came from SQL that was actually executed.",
        ],
    },
    3: {
        "seconds": 42,
        "before": [
            "Recount does not read the SQL and form an opinion.",
            "It answers the question again, from scratch.",
            "This is the whole prompt that step receives.",
        ],
        "after": [
            "Look at what is missing. The query being checked is not in there.",
            "That is deliberate. A reviewer who sees a broken query tends to"
            " repeat its mistake.",
            "So it writes its own answer, that query gets executed, and the two"
            " numbers are compared.",
            "Different numbers mean the reported figure cannot be used, and the"
            " gap is the size of the error.",
            "The decision is a diff between two executed queries. Not a judgement"
            " about which explanation sounds better.",
        ],
    },
    4: {
        "seconds": 34,
        "before": ["Now the case that makes this hard."],
        "after": [
            "Both join orders to order items, then aggregate. Same shape.",
            "One is broken. One is completely correct, because this one asks for"
            " units sold, and units really do live at line-item grain.",
            "You cannot tell them apart from the SQL. Only the question separates them.",
            "[ press Enter ]",
            "Recount clears it.",
            "Four of my twelve cases are correct queries, and three are shaped to"
            " look wrong. Without those you cannot measure crying wolf.",
        ],
    },
    5: {
        "seconds": 18,
        "before": ["And here is where Recount is wrong."],
        "after": [
            "This query is correct, and it flags it anyway.",
            "One false alarm out of four. The baseline has none. That is a real"
            " cost, and I am not hiding it.",
        ],
    },
    6: {
        "seconds": 34,
        "before": [
            "Twelve cases. Same model, same settings, scored by the same code.",
            "The only difference is the recomputation.",
        ],
        "after": [
            "Recall goes from eighty-eight percent to one hundred. Every planted"
            " fault caught, including the one the reviewer waved through.",
            "F1 is ninety-four against ninety-three.",
            "I am not going to oversell that. One point on twelve cases is a"
            " single case. That is inside the noise.",
            "Recall is the claim I will defend. And it costs twice as much.",
        ],
    },
    7: {
        "seconds": 20,
        "before": [
            "This part I would want as a judge. No API key here. No network call.",
        ],
        "after": [
            "Every model response is committed, so you replay the exact run and"
            " get the same table, for nothing.",
            "Verified from a clean clone, in three different timezones.",
        ],
    },
    8: {
        "seconds": 32,
        "before": ["Last thing, and it is the part I would want to be asked about."],
        "after": [
            "Four stages, each switched off in turn. Three of them I deleted,"
            " because their own numbers told me to.",
            "The verification gate. An earlier version of my own README called it"
            " the load-bearing idea.",
            "It gives results identical to the final configuration. Twice, across"
            " two rewrites. Its measured contribution is zero.",
            "The probe loop: identical results at double the cost. Deleted.",
            "And my profiler, the component I was proudest of, made things worse.",
        ],
    },
    9: {
        "seconds": 28,
        "before": [
            "[ nothing left to run — just say this to close ]",
            "I told the agent that status has NULLs and a predicate must handle them.",
            "So it wrote WHERE status IS NOT NULL. The question needed WHERE"
            " status equals completed.",
            "It did not add a filter. It replaced the one that mattered.",
            "A hazard you name to an agent becomes the thing it optimises for,"
            " and it competes with the task.",
            "So: don't ask an agent to be careful. Make its claim executable, and"
            " give each role only the context its own job needs.",
            "Confidence is not a signal. A number you can diff is.",
        ],
        "after": [],
    },
}


def print_script(only: int = None) -> None:
    total = sum(n["seconds"] for n in NARRATION.values())
    print(f"\n{rule('━')}\n  NARRATION SCRIPT — about {total // 60}:{total % 60:02d}"
          f"\n{rule('━')}")
    print("\n  Read the BEFORE lines, press Enter, then read the AFTER lines.")
    print("  Keep this on a phone or a second screen, off camera.\n")

    titles = {i: BEATS[i - 1][1] for i in range(1, len(BEATS) + 1)}
    titles[9] = "Closing — the hot take"

    for number, block in NARRATION.items():
        if only and number != only:
            continue
        print(rule())
        print(f"  BEAT {number} — {titles.get(number, '')}   (~{block['seconds']}s)")
        print(rule())
        if block["before"]:
            print("\n  ── say this first ──")
            for line in block["before"]:
                print(f"    {line}")
        if block["after"]:
            print("\n  ── press Enter, then say this ──")
            for line in block["after"]:
                print(f"    {line}")
        print()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--step", type=int)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--script", action="store_true",
                    help="print the lines to say, for every beat")
    ap.add_argument("--cue", type=int, metavar="N",
                    help="print the lines to say for beat N only")
    args = ap.parse_args()

    global _INTERACTIVE
    _INTERACTIVE = not args.check

    if args.script or args.cue:
        print_script(args.cue)
        return 0

    if args.list:
        for i, (_, title, sub) in enumerate(BEATS, 1):
            print(f"  {i}. {title:<34} {sub}")
        return 0

    if not (HERE / "data" / "warehouse.db").exists():
        print("Building the warehouse first (one-off) ...")
        shell([PY, "-m", "recount.warehouse", "--db", "data/warehouse.db"], echo=False)

    chosen = [BEATS[args.step - 1]] if args.step else BEATS
    offset = (args.step - 1) if args.step else 0

    for index, (fn, title, sub) in enumerate(chosen, start=offset + 1):
        banner(index, len(BEATS), title, sub)
        fn()
        if args.check:
            continue
        if index < len(BEATS) or args.step:
            pause()

    if args.check:
        print("\n" + rule("━"))
        print("  All beats ran. Safe to record.")
        return 0

    print("\n" + rule("━"))
    print("  That's the demo. Closing line is in VIDEO.md.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
