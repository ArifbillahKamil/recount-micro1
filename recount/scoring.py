"""Metrics for a verification run.

Choosing the metric carefully matters more here than the model does.

The obvious metric, "how many planted bugs did it find", rewards exactly the
wrong behaviour. A reviewer that answers BUG every single time scores perfect
recall and is worthless, because an analyst who is warned about everything stops
reading warnings. So the headline metric is **F1 on bug detection**, and it is
reported next to the **false alarm rate on queries that are actually correct**.
Four of the twelve cases are correct queries, three of them deliberately shaped
to look wrong, precisely so this failure mode is measurable rather than
invisible.

The harder metric is **repair accuracy**: of the planted bugs, how often did the
system produce a correction that returns the true number? Detection is an
opinion. A correction is a work product, and it either reproduces the reference
result or it does not.

Analyst minutes are reported as an explicitly modelled estimate, never as a
measurement. The coefficients are stated, defensible and adjustable, so a
reviewer who disagrees can recompute rather than having to trust them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .verdict import BUG, CLEAN, ESCALATE


@dataclass
class TimeModel:
    """Analyst minutes attributed to each outcome. Assumptions, not measurements.

    Rationale for the defaults:

    * ``confirmed_bug_saved`` -- finding a silent grain or NULL bug by hand means
      re-deriving the metric a second way. Conservatively 12 minutes.
    * ``false_alarm_cost`` -- a wrong warning still has to be investigated and
      dismissed. 8 minutes.
    * ``escalation_cost`` -- triaging a flagged-but-undecided query. 4 minutes.
    * a missed bug costs nothing at review time, so it scores zero here. Its
      real cost lands downstream and is reported as recall, not as minutes.
    """

    confirmed_bug_saved: float = 12.0
    false_alarm_cost: float = 8.0
    escalation_cost: float = 4.0

    def describe(self) -> str:
        return (
            f"confirmed bug +{self.confirmed_bug_saved:g} min, "
            f"false alarm -{self.false_alarm_cost:g} min, "
            f"escalation -{self.escalation_cost:g} min, "
            "missed bug 0 min (counted as recall, not time)"
        )


@dataclass
class Outcome:
    """One case, one system."""

    case_id: str
    is_bug: bool
    expected_bug_type: Optional[str]
    verdict: str
    bug_type: Optional[str]
    confidence: float
    repair_correct: bool = False
    repair_attempted: bool = False
    latency_s: float = 0.0
    cost_usd: float = 0.0
    cost_known: bool = True
    llm_calls: int = 0
    tool_calls: int = 0
    error: Optional[str] = None
    tags: tuple = ()
    explanation: str = ""

    @property
    def flagged(self) -> bool:
        return self.verdict == BUG

    @property
    def outcome_class(self) -> str:
        if self.is_bug:
            return "TP" if self.flagged else "FN"
        return "FP" if self.flagged else "TN"

    @property
    def bug_type_correct(self) -> bool:
        return (
            self.is_bug
            and self.flagged
            and self.bug_type is not None
            and self.bug_type == self.expected_bug_type
        )


@dataclass
class Metrics:
    system: str
    n_cases: int
    n_bug: int
    n_clean: int
    tp: int
    fp: int
    fn: int
    tn: int
    escalations_on_bug: int
    escalations_on_clean: int
    repairs_correct: int
    repairs_attempted: int
    bug_types_correct: int
    errors: int
    total_cost_usd: float
    cost_known: bool
    total_latency_s: float
    llm_calls: int
    tool_calls: int
    time_model: TimeModel = field(default_factory=TimeModel)

    # -- detection ---------------------------------------------------------
    @property
    def precision(self) -> Optional[float]:
        denom = self.tp + self.fp
        return self.tp / denom if denom else None

    @property
    def recall(self) -> Optional[float]:
        denom = self.tp + self.fn
        return self.tp / denom if denom else None

    @property
    def f1(self) -> Optional[float]:
        p, r = self.precision, self.recall
        if p is None or r is None or (p + r) == 0:
            return 0.0 if (p is not None and r is not None) else None
        return 2 * p * r / (p + r)

    @property
    def false_alarm_rate(self) -> Optional[float]:
        return self.fp / self.n_clean if self.n_clean else None

    @property
    def repair_accuracy(self) -> Optional[float]:
        return self.repairs_correct / self.n_bug if self.n_bug else None

    @property
    def bug_type_accuracy(self) -> Optional[float]:
        return self.bug_types_correct / self.tp if self.tp else None

    # -- derived -----------------------------------------------------------
    @property
    def net_analyst_minutes(self) -> float:
        m = self.time_model
        return (
            self.tp * m.confirmed_bug_saved
            - self.fp * m.false_alarm_cost
            - (self.escalations_on_bug + self.escalations_on_clean) * m.escalation_cost
        )

    @property
    def cost_per_case(self) -> float:
        return self.total_cost_usd / self.n_cases if self.n_cases else 0.0

    @property
    def latency_per_case(self) -> float:
        return self.total_latency_s / self.n_cases if self.n_cases else 0.0

    def to_dict(self) -> dict:
        return {
            "system": self.system,
            "n_cases": self.n_cases,
            "n_bug": self.n_bug,
            "n_clean": self.n_clean,
            "confusion": {"tp": self.tp, "fp": self.fp, "fn": self.fn, "tn": self.tn},
            "precision": _round(self.precision),
            "recall": _round(self.recall),
            "f1": _round(self.f1),
            "false_alarm_rate": _round(self.false_alarm_rate),
            "repair_accuracy": _round(self.repair_accuracy),
            "repairs_correct": self.repairs_correct,
            "repairs_attempted": self.repairs_attempted,
            "bug_type_accuracy": _round(self.bug_type_accuracy),
            "escalations_on_bug": self.escalations_on_bug,
            "escalations_on_clean": self.escalations_on_clean,
            "errors": self.errors,
            "net_analyst_minutes_modelled": round(self.net_analyst_minutes, 1),
            "time_model": self.time_model.describe(),
            "total_cost_usd": round(self.total_cost_usd, 6),
            "cost_per_case_usd": round(self.cost_per_case, 6),
            "cost_known": self.cost_known,
            "total_latency_s": round(self.total_latency_s, 2),
            "latency_per_case_s": round(self.latency_per_case, 2),
            "llm_calls": self.llm_calls,
            "tool_calls": self.tool_calls,
        }


def _round(value: Optional[float], digits: int = 4) -> Optional[float]:
    return None if value is None else round(value, digits)


def score(
    system: str, outcomes: list, time_model: Optional[TimeModel] = None
) -> Metrics:
    time_model = time_model or TimeModel()
    return Metrics(
        system=system,
        n_cases=len(outcomes),
        n_bug=sum(1 for o in outcomes if o.is_bug),
        n_clean=sum(1 for o in outcomes if not o.is_bug),
        tp=sum(1 for o in outcomes if o.outcome_class == "TP"),
        fp=sum(1 for o in outcomes if o.outcome_class == "FP"),
        fn=sum(1 for o in outcomes if o.outcome_class == "FN"),
        tn=sum(1 for o in outcomes if o.outcome_class == "TN"),
        escalations_on_bug=sum(
            1 for o in outcomes if o.is_bug and o.verdict == ESCALATE
        ),
        escalations_on_clean=sum(
            1 for o in outcomes if not o.is_bug and o.verdict == ESCALATE
        ),
        # Only planted bugs can earn repair credit. A correction offered on a
        # query that was already correct is not a repair, and counting it would
        # let a system score above 100% against a bug-only denominator.
        repairs_correct=sum(1 for o in outcomes if o.is_bug and o.repair_correct),
        repairs_attempted=sum(1 for o in outcomes if o.is_bug and o.repair_attempted),
        bug_types_correct=sum(1 for o in outcomes if o.bug_type_correct),
        errors=sum(1 for o in outcomes if o.error),
        total_cost_usd=sum(o.cost_usd for o in outcomes),
        cost_known=all(o.cost_known for o in outcomes),
        total_latency_s=sum(o.latency_s for o in outcomes),
        llm_calls=sum(o.llm_calls for o in outcomes),
        tool_calls=sum(o.tool_calls for o in outcomes),
    )


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _pct(value: Optional[float]) -> str:
    return "n/a" if value is None else f"{100 * value:.0f}%"


def _num(value: Optional[float]) -> str:
    return "n/a" if value is None else f"{value:.2f}"


def _delta(new: Optional[float], old: Optional[float], as_pct: bool = True) -> str:
    if new is None or old is None:
        return "n/a"
    diff = new - old
    if as_pct:
        return f"{100 * diff:+.0f} pt"
    return f"{diff:+.2f}"


def per_case_table(outcomes: list) -> str:
    header = (
        "| case | truth | verdict | class | bug type | repair | "
        "note |\n|---|---|---|---|---|---|---|"
    )
    rows = []
    for o in outcomes:
        truth = "BUG" if o.is_bug else "CLEAN"
        repair = "-"
        if o.repair_attempted:
            repair = "correct" if o.repair_correct else "wrong"
        note = o.error or (o.explanation[:70] + ("..." if len(o.explanation) > 70 else ""))
        rows.append(
            f"| `{o.case_id}` | {truth} | {o.verdict} | {o.outcome_class} | "
            f"{o.bug_type or '-'} | {repair} | {note.replace('|', '/')} |"
        )
    return "\n".join([header] + rows)


def comparison_table(baseline: Metrics, solution: Metrics) -> str:
    """The headline table: same cases, same model, same contract."""
    rows = [
        (
            "**F1 on bug detection** (primary)",
            _pct(baseline.f1),
            _pct(solution.f1),
            _delta(solution.f1, baseline.f1),
        ),
        ("Precision", _pct(baseline.precision), _pct(solution.precision),
         _delta(solution.precision, baseline.precision)),
        ("Recall", _pct(baseline.recall), _pct(solution.recall),
         _delta(solution.recall, baseline.recall)),
        (
            f"**False alarms** on the {solution.n_clean} correct queries "
            "(lower is better)",
            f"{baseline.fp}/{baseline.n_clean} ({_pct(baseline.false_alarm_rate)})",
            f"{solution.fp}/{solution.n_clean} ({_pct(solution.false_alarm_rate)})",
            _delta(solution.false_alarm_rate, baseline.false_alarm_rate),
        ),
        (
            "**Repair accuracy** (correction returns the true number)",
            f"{baseline.repairs_correct}/{baseline.n_bug} ({_pct(baseline.repair_accuracy)})",
            f"{solution.repairs_correct}/{solution.n_bug} ({_pct(solution.repair_accuracy)})",
            _delta(solution.repair_accuracy, baseline.repair_accuracy),
        ),
        ("Bug type named correctly", _pct(baseline.bug_type_accuracy),
         _pct(solution.bug_type_accuracy),
         _delta(solution.bug_type_accuracy, baseline.bug_type_accuracy)),
        (
            "Escalations (bug / clean)",
            f"{baseline.escalations_on_bug} / {baseline.escalations_on_clean}",
            f"{solution.escalations_on_bug} / {solution.escalations_on_clean}",
            "-",
        ),
        (
            "Net analyst minutes (modelled)",
            f"{baseline.net_analyst_minutes:+.0f}",
            f"{solution.net_analyst_minutes:+.0f}",
            f"{solution.net_analyst_minutes - baseline.net_analyst_minutes:+.0f}",
        ),
        (
            "Cost per case",
            _cost(baseline),
            _cost(solution),
            "-",
        ),
        (
            "Wall clock per case",
            f"{baseline.latency_per_case:.1f}s",
            f"{solution.latency_per_case:.1f}s",
            "-",
        ),
        (
            "Model calls / tool calls",
            f"{baseline.llm_calls} / {baseline.tool_calls}",
            f"{solution.llm_calls} / {solution.tool_calls}",
            "-",
        ),
    ]
    out = ["| metric | baseline | Recount | change |", "|---|---|---|---|"]
    for label, a, b, d in rows:
        out.append(f"| {label} | {a} | {b} | {d} |")
    return "\n".join(out)


def _cost(metrics: Metrics) -> str:
    if not metrics.cost_known:
        return "unpriced"
    return f"${metrics.cost_per_case:.5f}"


def summary_line(metrics: Metrics) -> str:
    return (
        f"{metrics.system}: F1 {_pct(metrics.f1)} "
        f"(P {_pct(metrics.precision)} / R {_pct(metrics.recall)}), "
        f"false alarms {metrics.fp}/{metrics.n_clean}, "
        f"repairs {metrics.repairs_correct}/{metrics.n_bug}, "
        f"escalations {metrics.escalations_on_bug + metrics.escalations_on_clean}, "
        f"cost {_cost(metrics)}/case"
    )
