"""The artifact an analyst receives.

Design constraints, all learned from what reviewers actually ignore:

* **Lead with the number.** Someone who asked a question and got a figure wants
  to know first whether they can use it. Not a summary of the methodology.
* **Say the magnitude.** "Possible fan-out issue" prompts nothing. "Overstated
  2.61x, should be 5,468,920,000" prompts an immediate fix.
* **Every claim carries its probe.** The reader can re-run any line of evidence.
* **Ship a runnable correction**, not advice about what to consider.
* **Be short when the answer is fine.** A clean verdict that takes two pages
  trains people to stop reading. Clean reports are a few lines.

Deliberately absent: emoji section markers, an executive summary above a
one-line finding, hedged phrasing that commits to nothing, and any sentence that
would read the same for a different query.
"""

from __future__ import annotations

from typing import Optional

from . import verdict as V
from .sqlio import render_result

DIVIDER = "-" * 68


def _fmt_number(value, column: str = "") -> str:
    if isinstance(value, bool) or value is None:
        return str(value)
    if isinstance(value, int):
        text = f"{value:,}"
        if "cents" in column.lower() and abs(value) >= 100:
            text += f" ({value / 100:,.2f} in major units)"
        return text
    if isinstance(value, float):
        return f"{value:,.4f}".rstrip("0").rstrip(".")
    return str(value)


def _headline_values(result: dict) -> list:
    """The scalar values a single-row result reports, with their column names."""
    rows = result.get("rows") or []
    columns = result.get("columns") or []
    if len(rows) != 1:
        return []
    return [(columns[i] if i < len(columns) else f"col{i+1}", v)
            for i, v in enumerate(rows[0])]


def _sql_block(sql: str) -> str:
    return "```sql\n" + _tidy_sql(sql) + "\n```"


def _tidy_sql(sql: str) -> str:
    lines = [ln.rstrip() for ln in (sql or "").strip().splitlines()]
    if not lines:
        return ""
    indents = [len(ln) - len(ln.lstrip()) for ln in lines if ln.strip()]
    shift = min(indents) if indents else 0
    return "\n".join(ln[shift:] if len(ln) >= shift else ln for ln in lines)


def _bug_title(delta: "Optional[V.Evidence]") -> str:
    """Name the metric and the size of the error in the heading.

    "Do not ship this number" says nothing a reader can act on.
    "`captured_cents` is overstated 2.61x" is the whole finding at a glance.
    """
    detail = (delta.detail if delta else None) or {}
    column = detail.get("column")
    ratio = detail.get("ratio")
    direction = detail.get("direction")
    if column and ratio and direction in {"overstated", "understated"}:
        return f"`{column}` is {direction} {ratio:.2f}x — do not ship it"
    if column:
        return f"`{column}` does not match the question asked"
    return "This number does not answer the question asked"


def _corrected_evidence(result: V.Verdict) -> Optional[V.Evidence]:
    for evidence in result.evidence:
        if evidence.delta and evidence.delta != "no difference":
            return evidence
    return None


def _probe_evidence(result: V.Verdict) -> list:
    return [e for e in result.evidence if not e.delta]


def render(
    question: str,
    sql: str,
    result: V.Verdict,
    original_result: dict,
    *,
    title: Optional[str] = None,
    model: Optional[str] = None,
) -> str:
    if result.verdict == V.BUG:
        body = _render_bug(question, sql, result, original_result, title)
    elif result.verdict == V.CLEAN:
        body = _render_clean(question, result, original_result, title)
    else:
        body = _render_escalate(question, sql, result, original_result, title)

    footer = ["", DIVIDER, ""]
    provenance = "Checked by Recount against the live warehouse."
    if model:
        provenance += f" Adjudicated with {model}."
    footer.append(
        provenance + " Every figure above came from a query you can re-run."
    )
    return "\n".join(body + footer)


# ---------------------------------------------------------------------------


def _render_bug(
    question: str,
    sql: str,
    result: V.Verdict,
    original_result: dict,
    title: Optional[str],
) -> list:
    delta = _corrected_evidence(result)
    out = [f"# {title or _bug_title(delta)}", ""]
    out.append(f"**You asked:** {question.strip()}")
    out.append("")

    reported = _headline_values(original_result)
    if reported and delta:
        out.append("The query returns a number that does not answer that question.")
        out.append("")
        out.append(f"    {delta.delta}")
        out.append("")
    elif reported:
        for column, value in reported:
            out.append(f"Reported `{column}`: **{_fmt_number(value, column)}**")
        out.append("")

    if result.explanation:
        out.append("## Why it is wrong")
        out.append("")
        out.append(result.explanation.strip())
        out.append("")

    probes = _probe_evidence(result)
    if probes:
        out.append("## Evidence")
        out.append("")
        out.append("Measured against your data, not inferred from the SQL:")
        out.append("")
        for evidence in probes:
            out.append(f"**{evidence.claim}**")
            out.append("")
            out.append(_sql_block(evidence.sql))
            out.append("")
            out.append("```")
            out.append(evidence.result_text)
            out.append("```")
            out.append("")

    if result.corrected_sql:
        out.append("## Corrected query")
        out.append("")
        out.append(_sql_block(result.corrected_sql))
        out.append("")
        if delta:
            out.append("Returns:")
            out.append("")
            out.append("```")
            out.append(delta.result_text)
            out.append("```")
            out.append("")
        out.append(
            "This correction was executed against the same warehouse before "
            "this report was written. It is the reason the discrepancy above is "
            "stated as a fact rather than a suspicion."
        )
        out.append("")

    out.append("## Before you ship")
    out.append("")
    out.append("- Re-run the corrected query and replace the figure at source.")
    out.append(
        "- Check whether anything downstream already consumed the old number: "
        "a dashboard tile, a scheduled export, a deck."
    )
    if result.bug_type:
        out.append(
            f"- This is a `{result.bug_type}` fault. If the same pattern appears "
            "in sibling queries, they carry it too."
        )
    return out


def _render_clean(
    question: str,
    result: V.Verdict,
    original_result: dict,
    title: Optional[str],
) -> list:
    out = [f"# {title or 'Checked — the number holds'}", ""]
    out.append(f"**You asked:** {question.strip()}")
    out.append("")
    for column, value in _headline_values(original_result):
        out.append(f"`{column}`: **{_fmt_number(value, column)}**")
    out.append("")
    out.append(result.explanation.strip() or "No discrepancy found.")
    out.append("")

    probes = _probe_evidence(result)
    if probes:
        out.append("## What was checked")
        out.append("")
        for evidence in probes:
            out.append(f"{evidence.claim}:")
            out.append("")
            out.append("```")
            out.append((evidence.result_text or "").rstrip())
            out.append("```")
            out.append("")
        out.append(
            "The reported figure survived each of these, so it is safe to use."
        )
    return out


def _render_escalate(
    question: str,
    sql: str,
    result: V.Verdict,
    original_result: dict,
    title: Optional[str],
) -> list:
    out = [f"# {title or 'Needs a human decision'}", ""]
    out.append(f"**You asked:** {question.strip()}")
    out.append("")
    for column, value in _headline_values(original_result):
        out.append(f"Reported `{column}`: **{_fmt_number(value, column)}**")
    out.append("")
    out.append(
        result.explanation.strip()
        or "This query could not be settled from the schema and data alone."
    )
    out.append("")
    out.append(
        "Recount will not label a query wrong unless it can produce a corrected "
        "query that returns a different number. It could not do that here, so "
        "this is being handed to you rather than guessed at."
    )
    out.append("")

    probes = _probe_evidence(result)
    if probes:
        out.append("## What was measured")
        out.append("")
        for evidence in probes:
            out.append(f"**{evidence.claim}**")
            out.append("")
            out.append(_sql_block(evidence.sql))
            out.append("")
            out.append("```")
            out.append(evidence.result_text)
            out.append("```")
            out.append("")

    out.append("## The question to settle")
    out.append("")
    out.append(
        "- Decide the intended grain of the metric, then confirm the join "
        "matches it."
    )
    out.append("- If the definition is genuinely ambiguous, write it down "
               "before this query is used again.")
    return out


def render_from_run(
    question: str,
    sql: str,
    result: V.Verdict,
    original_result: dict,
    **kwargs,
) -> str:
    """Convenience wrapper mirroring :func:`render`, kept for callers."""
    return render(question, sql, result, original_result, **kwargs)
