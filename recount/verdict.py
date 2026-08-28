"""The output contract shared by the baseline and by Recount.

Both systems emit the same structure, accept the same three verdicts, and are
scored by the same code. Keeping the contract identical is what makes the
comparison fair: any difference in results comes from tools and orchestration,
not from one system being allowed a richer answer than the other.

``corrected_sql`` is the field that turns this from an opinion into a work
product. A reviewer does not want to be told a number is wrong; they want the
right number. Because a correction is executable, it is also gradable -- run it
and compare against the reference result. That yields *repair accuracy*, a much
harder bar than detection, and one a system cannot bluff.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

CLEAN = "CLEAN"
BUG = "BUG"
ESCALATE = "ESCALATE"
VERDICTS = (CLEAN, BUG, ESCALATE)

BUG_TYPES = (
    "fanout_join",
    "null_swallowing_predicate",
    "left_join_degraded_to_inner",
    "date_range_truncation",
    "timezone_day_boundary",
    "mixed_unit_aggregation",
    "missing_filter",
    "wrong_aggregation_grain",
    "other",
)

OUTPUT_CONTRACT = """Reply with one JSON object and nothing else:

{
  "verdict": "CLEAN" | "BUG" | "ESCALATE",
  "bug_type": one of [%s] or null,
  "confidence": number between 0 and 1,
  "explanation": "at most 3 sentences, concrete, naming the tables involved",
  "corrected_sql": "a single SELECT that answers the business question, or null"
}

Verdict meanings:
  CLEAN     - the query correctly answers the business question.
  BUG       - the query runs but returns a number that does not answer the
              business question. Set bug_type and corrected_sql.
  ESCALATE  - answering needs a business decision you cannot make from the
              schema and data alone. Use this instead of guessing.

Judge the query against the business question, not against style. A join to a
finer grain is a bug when the metric is coarser, and correct when the metric
actually lives at that finer grain.""" % (", ".join(f'"{b}"' for b in BUG_TYPES))


@dataclass
class Evidence:
    """One executed probe backing a claim."""

    claim: str
    sql: str
    result_text: str
    delta: Optional[str] = None
    detail: Optional[dict] = None

    def to_dict(self) -> dict:
        return {
            "claim": self.claim,
            "sql": " ".join(self.sql.split()),
            "result": self.result_text,
            "delta": self.delta,
            "detail": self.detail,
        }


@dataclass
class Verdict:
    verdict: str
    bug_type: Optional[str] = None
    confidence: float = 0.0
    explanation: str = ""
    corrected_sql: Optional[str] = None
    evidence: list = field(default_factory=list)
    error: Optional[str] = None

    @property
    def flags_bug(self) -> bool:
        return self.verdict == BUG

    def to_dict(self) -> dict:
        return {
            "verdict": self.verdict,
            "bug_type": self.bug_type,
            "confidence": self.confidence,
            "explanation": self.explanation,
            "corrected_sql": self.corrected_sql,
            "evidence": [e.to_dict() for e in self.evidence],
            "error": self.error,
        }


def _clean_str(value) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"null", "none", "n/a"}:
        return None
    return text


def parse(payload: dict) -> Verdict:
    """Coerce a model's JSON into a :class:`Verdict`.

    Unknown verdicts become ESCALATE rather than an exception. A malformed reply
    is a real failure mode, and treating it as "needs a human" is both the
    honest reading and the safe default -- it never silently becomes a CLEAN.
    """
    raw_verdict = str(payload.get("verdict", "")).strip().upper()
    if raw_verdict not in VERDICTS:
        return Verdict(
            verdict=ESCALATE,
            explanation=(
                f"unrecognised verdict {raw_verdict!r}; treated as needing review"
            ),
            error="unparseable_verdict",
        )

    bug_type = _clean_str(payload.get("bug_type"))
    if bug_type is not None and bug_type not in BUG_TYPES:
        bug_type = "other"

    try:
        confidence = float(payload.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = min(max(confidence, 0.0), 1.0)

    return Verdict(
        verdict=raw_verdict,
        bug_type=bug_type if raw_verdict == BUG else None,
        confidence=confidence,
        explanation=_clean_str(payload.get("explanation")) or "",
        corrected_sql=_clean_str(payload.get("corrected_sql")),
    )


def failed(reason: str) -> Verdict:
    """A verdict representing a system failure, scored as ESCALATE."""
    return Verdict(
        verdict=ESCALATE,
        explanation=f"verification could not complete: {reason}",
        error=reason,
    )
