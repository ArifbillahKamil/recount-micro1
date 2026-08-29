"""Recount: verify a text-to-SQL answer by executing evidence for it.

Pipeline, and the reason each stage exists:

1. **Profile** (no model). Measure grain, real NULL counts and join cardinality.
   Removes the need to speculate about the data.
2. **Plan** (model). Turn the business question, the SQL and the measured facts
   into specific, falsifiable hypotheses, each paired with a probe query.
3. **Probe** (no model). Execute the probes read-only. A failed probe is fed
   back once for repair, so tool output genuinely shapes the next step rather
   than being decoration.
4. **Adjudicate** (model). Decide CLEAN / BUG / ESCALATE from probe results,
   and when claiming a bug, produce a corrected query.
5. **Gate** (no model). The stage that does the real work.

About the gate. The dominant failure of a language-model SQL reviewer is not
missing bugs, it is inventing them: given any query and asked "is this wrong?",
it finds something. Confidence scores do not help, because it is equally
confident when right and wrong.

So the gate refuses to accept an argument and demands a consequence instead. A
BUG verdict must come with a correction, and that correction is executed and
diffed against the original query:

* identical result -> the "fix" changes nothing, so the original was already
  right. Downgrade to CLEAN.
* different result -> the bug is real, and the diff is the magnitude, in the
  units the analyst cares about.
* correction missing or broken -> nothing was proven. Downgrade to ESCALATE.

The gate never sees ``reference_sql``. It compares the original query against
the model's own proposed correction, so nothing about the ground truth leaks
into the system under test.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from . import verdict as V
from .llm import CassetteMiss, LLMClient, LLMError
from .profiler import Profile, profile as build_profile
from .sqlio import (
    SqlError,
    render_result,
    result_signature,
    run_sql,
    schema_ddl,
    values_match,
)
from .trace import Trace

MAX_PROBES = 4
MAX_PROBE_REPAIRS = 1

PLANNER_SYSTEM = """You are a senior analytics engineer who has been burned by
queries that run cleanly and return the wrong number. You do not speculate: you
design a measurement that would settle each suspicion."""

PLANNER_TEMPLATE = """Business question the analyst asked:
{question}

SQL that was produced and executed successfully:
{sql}

{profile}

The query returned this result:
{result}

List the specific ways this query could fail to answer the business question.
For each one, write a probe: a single read-only SELECT whose output would settle
whether that failure is actually happening in this data.

A good probe measures a consequence. Compare a row count before and after a
join, compare COUNT(*) against COUNT(DISTINCT key), count rows excluded by a
predicate, or compute the requested metric by an independent route and show both
numbers. A probe that merely re-runs the original query settles nothing.

Reply with one JSON object and nothing else:

{{
  "hypotheses": [
    {{
      "risk": "one sentence, naming the tables or columns involved",
      "bug_type": one of [{bug_types}],
      "probe_sql": "a single SELECT, no semicolon",
      "settles": "what result would confirm this, and what would rule it out"
    }}
  ]
}}

At most {max_probes} hypotheses, ordered by how likely they are given the
measured facts above. If the measured facts already show a table does not fan
out, do not propose a fan-out hypothesis about it."""

REPAIR_TEMPLATE = """Some probes failed to execute. Rewrite only those, keeping
the same intent. This database is SQLite.

{failures}

Reply with one JSON object and nothing else:

{{"probes": [{{"index": <original index>, "probe_sql": "a single SELECT"}}]}}"""

RECOMPUTE_SYSTEM = """You are a senior analytics engineer. You are handed a
business question and the measured facts about a warehouse, and you write the
query that answers it. You are not reviewing anyone's work: you are deriving the
answer independently."""

RECOMPUTE_TEMPLATE = """Business question:
{question}

{profile}

Write a single read-only SQL query that answers this question against this
SQLite warehouse.

Derive it from the question and the measured facts above. Pay attention to the
grain of each measure, to columns that are nullable in practice, and to whether
a join fans out.

Return exactly these columns, in this order, with these names:
{columns}

Reply with one JSON object and nothing else:

{{"sql": "a single SELECT, no semicolon", "reasoning": "one sentence on the grain and filters you chose"}}"""

ADJUDICATOR_SYSTEM = """You are a senior analytics engineer signing off on
whether a number can go into a business report. You have executed probes and an
independent recomputation, and you now decide based on what they returned."""

ADJUDICATOR_TEMPLATE = """Business question the analyst asked:
{question}

SQL under review:
{sql}

Result it returned:
{result}

{profile}

Probes you designed, and what executing them actually returned:
{probes}

{recompute}

Decide the verdict from what was executed, not from how the SQL looks.

* The recomputation above is the strongest evidence available. If it returns a
  different number from the query under review, the two disagree and the
  reported number cannot be trusted. If it returns the same number, two
  independent derivations agree.
* Judge against the business question. Joining to a finer grain is a bug when
  the requested metric is coarser, and correct when the metric genuinely lives
  at that finer grain.
* If you answer BUG, corrected_sql is mandatory and will be executed.

{contract}"""


@dataclass
class Hypothesis:
    index: int
    risk: str
    bug_type: str
    probe_sql: str
    settles: str = ""
    result_text: Optional[str] = None
    error: Optional[str] = None

    @property
    def executed(self) -> bool:
        return self.result_text is not None


def _referenced_tables(sql: str, profile: Profile) -> list:
    """Tables the query mentions, so the profile digest stays small."""
    tokens = set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", sql.lower()))
    named = [t.name for t in profile.tables if t.name.lower() in tokens]
    return named or [t.name for t in profile.tables]


def _render_hypotheses(hypotheses: list) -> str:
    if not hypotheses:
        return "(no probes were executed)"
    blocks = []
    for h in hypotheses:
        block = [f"[{h.index}] risk: {h.risk}", f"    probe: {' '.join(h.probe_sql.split())}"]
        if h.error:
            block.append(f"    FAILED TO EXECUTE: {h.error}")
        else:
            indented = "\n".join(
                f"    {line}" for line in (h.result_text or "").splitlines()
            )
            block.append("    returned:")
            block.append(indented)
        blocks.append("\n".join(block))
    return "\n\n".join(blocks)


@dataclass
class Recompute:
    """An independent derivation of the requested metric, and what it returned."""

    sql: Optional[str] = None
    reasoning: str = ""
    result: Optional[dict] = None
    result_text: str = ""
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.result is not None

    def render(self, original_text: str) -> str:
        if self.error:
            return (
                "Independent recomputation: FAILED to produce a runnable query "
                f"({self.error}). No second opinion is available."
            )
        if not self.ok:
            return "Independent recomputation: not attempted."
        return (
            "An independent recomputation was derived from the business question "
            "alone, without seeing the query under review, then executed:\n\n"
            f"  sql: {' '.join((self.sql or '').split())}\n"
            f"  returned:\n{_indent(self.result_text, 4)}\n\n"
            f"  the query under review returned:\n{_indent(original_text, 4)}"
        )


def _indent(text: str, spaces: int) -> str:
    pad = " " * spaces
    return "\n".join(pad + line for line in (text or "").splitlines())


def _recompute(
    client: LLMClient,
    trace: Trace,
    db_path: str | Path,
    question: str,
    profile_text: str,
    original_result: dict,
) -> Recompute:
    """Derive the answer from scratch, then run it.

    The query under review is deliberately withheld. A reviewer shown the
    original tends to reproduce its mistakes, and the value of a second opinion
    lies precisely in it being arrived at independently. Only the expected output
    columns are disclosed, so the two results can be compared at all.
    """
    columns = ", ".join(original_result.get("columns") or []) or "(a single value)"
    messages = [
        {"role": "system", "content": RECOMPUTE_SYSTEM},
        {
            "role": "user",
            "content": RECOMPUTE_TEMPLATE.format(
                question=question.strip(),
                profile=profile_text,
                columns=columns,
            ),
        },
    ]

    try:
        response = client.chat(messages, step="recompute", max_tokens=1200, trace=trace)
        payload = response.json()
    except LLMError as exc:
        if isinstance(exc, CassetteMiss):
            raise
        trace.add_note("recompute", f"model call failed: {exc}")
        return Recompute(error=str(exc))

    sql = str(payload.get("sql") or "").strip()
    reasoning = str(payload.get("reasoning") or "").strip()
    if not sql:
        trace.add_note("recompute", "no query was produced")
        return Recompute(reasoning=reasoning, error="no query produced")

    try:
        result = run_sql(db_path, sql)
    except SqlError as exc:
        trace.add_tool("recompute", "run_sql", sql, str(exc), ok=False)
        return Recompute(sql=sql, reasoning=reasoning, error=str(exc))

    rendered = render_result(result)
    trace.add_tool("recompute", "run_sql", sql, rendered)
    return Recompute(sql=sql, reasoning=reasoning, result=result, result_text=rendered)


def _plan(
    client: LLMClient,
    trace: Trace,
    question: str,
    sql: str,
    profile_text: str,
    result_text: str,
    max_probes: int,
) -> list:
    messages = [
        {"role": "system", "content": PLANNER_SYSTEM},
        {
            "role": "user",
            "content": PLANNER_TEMPLATE.format(
                question=question.strip(),
                sql=sql.strip(),
                profile=profile_text,
                result=result_text,
                bug_types=", ".join(f'"{b}"' for b in V.BUG_TYPES),
                max_probes=max_probes,
            ),
        },
    ]
    response = client.chat(messages, step="plan", max_tokens=1600, trace=trace)
    payload = response.json()

    hypotheses = []
    for raw in (payload.get("hypotheses") or [])[:max_probes]:
        probe_sql = str(raw.get("probe_sql") or "").strip()
        if not probe_sql:
            continue
        hypotheses.append(
            Hypothesis(
                index=len(hypotheses) + 1,
                risk=str(raw.get("risk") or "").strip() or "(unstated)",
                bug_type=str(raw.get("bug_type") or "other").strip(),
                probe_sql=probe_sql,
                settles=str(raw.get("settles") or "").strip(),
            )
        )
    return hypotheses


def _execute_probes(db_path: str | Path, trace: Trace, hypotheses: list) -> None:
    for h in hypotheses:
        try:
            result = run_sql(db_path, h.probe_sql)
        except SqlError as exc:
            h.error = str(exc)
            h.result_text = None
            trace.add_tool(
                f"probe_{h.index}", "run_sql", h.probe_sql, str(exc), ok=False
            )
            continue
        h.error = None
        h.result_text = render_result(result)
        trace.add_tool(f"probe_{h.index}", "run_sql", h.probe_sql, h.result_text)


def _repair_probes(
    client: LLMClient,
    trace: Trace,
    db_path: str | Path,
    hypotheses: list,
) -> None:
    broken = [h for h in hypotheses if h.error]
    if not broken:
        return

    failures = "\n\n".join(
        f"[{h.index}] intent: {h.risk}\n"
        f"    sql: {' '.join(h.probe_sql.split())}\n"
        f"    error: {h.error}"
        for h in broken
    )
    trace.add_note(
        "probe_repair",
        f"{len(broken)} probe(s) failed to execute; asking for a rewrite.",
        {"failed_indices": [h.index for h in broken]},
    )

    messages = [
        {"role": "system", "content": PLANNER_SYSTEM},
        {"role": "user", "content": REPAIR_TEMPLATE.format(failures=failures)},
    ]
    try:
        response = client.chat(messages, step="probe_repair", max_tokens=900, trace=trace)
        rewrites = response.json().get("probes") or []
    except CassetteMiss:
        # In replay the control flow is deterministic, so a miss here means the
        # run genuinely diverged from what was recorded. Surface it.
        raise
    except LLMError as exc:
        trace.add_note("probe_repair", f"repair call failed: {exc}")
        return

    by_index = {h.index: h for h in hypotheses}
    repaired = []
    for raw in rewrites:
        try:
            index = int(raw.get("index"))
        except (TypeError, ValueError):
            continue
        target = by_index.get(index)
        new_sql = str(raw.get("probe_sql") or "").strip()
        if target is None or not new_sql:
            continue
        target.probe_sql = new_sql
        repaired.append(target)

    if repaired:
        _execute_probes(db_path, trace, repaired)


def _adjudicate(
    client: LLMClient,
    trace: Trace,
    question: str,
    sql: str,
    profile_text: str,
    result_text: str,
    hypotheses: list,
    recompute: Recompute,
) -> V.Verdict:
    messages = [
        {"role": "system", "content": ADJUDICATOR_SYSTEM},
        {
            "role": "user",
            "content": ADJUDICATOR_TEMPLATE.format(
                question=question.strip(),
                sql=sql.strip(),
                result=result_text,
                profile=profile_text,
                probes=_render_hypotheses(hypotheses),
                recompute=recompute.render(result_text),
                contract=V.OUTPUT_CONTRACT,
            ),
        },
    ]
    response = client.chat(messages, step="adjudicate", max_tokens=1200, trace=trace)
    return V.parse(response.json())


def _gate(
    db_path: str | Path,
    trace: Trace,
    result: V.Verdict,
    original_sql: str,
    original_result: dict,
    recompute: Optional[Recompute] = None,
) -> V.Verdict:
    """Decide from executed numbers rather than from the model's confidence.

    When an independent recomputation is available it is decisive, because it is
    symmetric: it can contradict a CLEAN verdict as readily as a BUG one. The
    first version of this gate could only downgrade a bug claim, which left it
    unable to catch the case that matters most -- a real fault waved through.
    """
    if recompute is not None and recompute.ok:
        return _gate_by_recomputation(
            db_path, trace, result, original_result, recompute
        )

    if recompute is not None and recompute.error:
        trace.add_note(
            "verification_gate",
            "No independent recomputation was available "
            f"({recompute.error}); falling back to checking the proposed "
            "correction on its own.",
        )

    if result.verdict != V.BUG:
        trace.add_gate(
            "verification_gate",
            result.verdict,
            "no bug claimed, so no correction is required",
        )
        return result

    if not result.corrected_sql:
        trace.add_gate(
            "verification_gate",
            V.ESCALATE,
            "a bug was claimed but no corrected query was produced, so nothing "
            "was demonstrated",
        )
        result.verdict = V.ESCALATE
        result.bug_type = None
        result.explanation = (
            "A possible problem was raised but could not be demonstrated: "
            + (result.explanation or "no correction was offered.")
        )
        result.error = "bug_claim_without_correction"
        return result

    try:
        corrected = run_sql(db_path, result.corrected_sql)
    except SqlError as exc:
        trace.add_tool(
            "gate_execute_correction",
            "run_sql",
            result.corrected_sql,
            str(exc),
            ok=False,
        )
        trace.add_gate(
            "verification_gate",
            V.ESCALATE,
            f"the proposed correction does not execute ({exc}), so the bug "
            "claim is unproven",
        )
        result.verdict = V.ESCALATE
        result.bug_type = None
        result.explanation = (
            "A possible problem was raised, but the proposed correction failed "
            f"to run ({exc}). A human should look at this."
        )
        result.error = "correction_failed_to_execute"
        return result

    corrected_text = render_result(corrected)
    trace.add_tool(
        "gate_execute_correction", "run_sql", result.corrected_sql, corrected_text
    )

    original_text = render_result(original_result)
    if result_signature(corrected) == result_signature(original_result):
        trace.add_gate(
            "verification_gate",
            V.CLEAN,
            "the proposed correction returns exactly the original result, so the "
            "original query already answers the question",
            {"result": original_text},
        )
        result.verdict = V.CLEAN
        result.bug_type = None
        result.corrected_sql = None
        result.explanation = (
            "Checked and no discrepancy found: a rewritten version of this query "
            "returns an identical result, so the reported number stands."
        )
        # Append rather than replace: the probes that were run are the reason the
        # analyst can trust this, so they belong in the report.
        result.evidence.append(
            V.Evidence(
                claim="an independent rewrite reproduces the reported number",
                sql=original_sql,
                result_text=original_text,
                delta="no difference",
            )
        )
        return result

    trace.add_gate(
        "verification_gate",
        V.BUG,
        "the correction executes and returns a different result, so the "
        "discrepancy is demonstrated",
        {"reported": original_text, "corrected": corrected_text},
    )
    delta_text, delta_detail = _describe_delta(original_result, corrected)
    result.evidence.append(
        V.Evidence(
            claim="the corrected query returns a different number",
            sql=result.corrected_sql,
            result_text=corrected_text,
            delta=delta_text,
            detail=delta_detail,
        )
    )
    return result


def _gate_by_recomputation(
    db_path: str | Path,
    trace: Trace,
    result: V.Verdict,
    original_result: dict,
    recompute: Recompute,
) -> V.Verdict:
    """Compare two independent derivations of the same question."""
    original_text = render_result(original_result)
    agree = values_match(original_result, recompute.result)

    if agree:
        if result.verdict == V.BUG:
            trace.add_gate(
                "verification_gate",
                V.CLEAN,
                "a query derived independently from the question returns exactly "
                "the reported number, so the bug claim is not supported",
                {"both_returned": original_text},
            )
            result.verdict = V.CLEAN
            result.bug_type = None
            result.corrected_sql = None
            result.explanation = (
                "Checked and no discrepancy found. A query written independently "
                "from the question, without reference to this one, returns the "
                "same number."
            )
        else:
            trace.add_gate(
                "verification_gate",
                result.verdict,
                "an independently derived query returns the same number, "
                "corroborating the reported result",
                {"both_returned": original_text},
            )
        result.evidence.append(
            V.Evidence(
                claim="a query derived independently returns the same number",
                sql=recompute.sql or "",
                result_text=recompute.result_text,
                delta="no difference",
            )
        )
        return result

    # The two derivations disagree, so the reported number is not reliable.
    delta_text, delta_detail = _describe_delta(original_result, recompute.result)

    if result.verdict == V.BUG:
        corrected = _best_correction(
            db_path, trace, result, original_result, recompute
        )
        trace.add_gate(
            "verification_gate",
            V.BUG,
            "an independently derived query returns a different number, "
            "demonstrating the discrepancy",
            {"reported": original_text, "recomputed": recompute.result_text},
        )
        result.corrected_sql = corrected
        result.evidence.append(
            V.Evidence(
                claim="an independent derivation of this metric disagrees",
                sql=recompute.sql or "",
                result_text=recompute.result_text,
                delta=delta_text,
                detail=delta_detail,
            )
        )
        return result

    # A conflict: the reviewer sees no fault, but the recomputation disagrees.
    # Neither can be trusted over the other, so a human decides.
    trace.add_gate(
        "verification_gate",
        V.ESCALATE,
        "the reviewer found no fault, but an independently derived query returns "
        "a different number; the conflict cannot be settled automatically",
        {"reported": original_text, "recomputed": recompute.result_text},
    )
    result.verdict = V.ESCALATE
    result.bug_type = None
    result.error = "recomputation_conflict"
    result.explanation = (
        "Two independent derivations of this metric disagree, so the reported "
        f"number should not be used until someone decides which is right. {delta_text}."
    )
    result.evidence.append(
        V.Evidence(
            claim="an independent derivation of this metric disagrees",
            sql=recompute.sql or "",
            result_text=recompute.result_text,
            delta=delta_text,
            detail=delta_detail,
        )
    )
    return result


def _best_correction(
    db_path: str | Path,
    trace: Trace,
    result: V.Verdict,
    original_result: dict,
    recompute: Recompute,
) -> Optional[str]:
    """Choose which corrected query the analyst is handed.

    This preference was originally the other way round -- the independent
    derivation won unless the reviewer's correction happened to match it -- and
    it cost real accuracy. Measured on gpt-4o-mini over the eight planted faults,
    that rule produced 3/8 correct corrections where taking the reviewer's own
    answer produced 7/8. The independent derivation is a good detector, because
    disagreeing with the original is enough to prove a discrepancy. It is a
    weaker repair, because being right requires it to get the whole query right.

    So the reviewer's correction wins whenever it runs and actually changes the
    number. The derivation is the fallback, and where the two disagree both
    values are surfaced rather than one being quietly chosen.
    """
    candidate = result.corrected_sql
    if candidate:
        try:
            produced = run_sql(db_path, candidate)
        except SqlError as exc:
            trace.add_note(
                "correction",
                f"The reviewer's correction does not run ({exc}); using the "
                "independently derived query instead.",
            )
            return recompute.sql or None

        if not values_match(produced, original_result):
            if not values_match(produced, recompute.result):
                # Two candidate fixes that disagree. Neither is provably right,
                # so the analyst is told rather than shown only one.
                result.evidence.append(
                    V.Evidence(
                        claim=(
                            "a second, independently derived query returns a "
                            "different corrected value -- treat both as "
                            "candidates until one is confirmed"
                        ),
                        sql=recompute.sql or "",
                        result_text=recompute.result_text,
                    )
                )
                trace.add_note(
                    "correction",
                    "The reviewer's correction and the independent derivation "
                    "disagree on the corrected value; both are reported.",
                )
            return candidate

        trace.add_note(
            "correction",
            "The reviewer's correction returns the original number, so it "
            "repairs nothing; using the independently derived query instead.",
        )
    return recompute.sql or candidate


def _describe_delta(original: dict, corrected: dict) -> tuple:
    """Express the discrepancy in the analyst's units where possible.

    Returns ``(text, detail)``. ``detail`` is structured so the report can build
    a specific headline without re-parsing prose.
    """
    o_rows, c_rows = original.get("rows") or [], corrected.get("rows") or []
    if len(o_rows) == 1 and len(c_rows) == 1 and len(o_rows[0]) == len(c_rows[0]):
        parts = []
        detail = None
        columns = original.get("columns") or []
        for i, (o_val, c_val) in enumerate(zip(o_rows[0], c_rows[0])):
            label = columns[i] if i < len(columns) else f"col{i + 1}"
            if o_val == c_val:
                continue
            numeric = (
                isinstance(o_val, (int, float))
                and isinstance(c_val, (int, float))
                and not isinstance(o_val, bool)
                and c_val
            )
            if numeric:
                ratio = o_val / c_val
                parts.append(
                    f"{label}: reported {o_val:,} vs corrected {c_val:,} "
                    f"({ratio:.2f}x, off by {o_val - c_val:+,})"
                )
                if detail is None:
                    detail = {
                        "column": label,
                        "reported": o_val,
                        "corrected": c_val,
                        "ratio": ratio,
                        "direction": "overstated" if ratio > 1 else "understated",
                    }
            else:
                parts.append(f"{label}: reported {o_val} vs corrected {c_val}")
        if parts:
            return "; ".join(parts), detail
    return (
        f"{len(o_rows)} row(s) reported vs {len(c_rows)} row(s) corrected",
        {
            "column": "row count",
            "reported": len(o_rows),
            "corrected": len(c_rows),
            "ratio": None,
            "direction": "differs",
        },
    )


def review(
    db_path: str | Path,
    question: str,
    sql: str,
    client: LLMClient,
    *,
    case_id: str = "adhoc",
    trace: Optional[Trace] = None,
    cached_profile: Optional[Profile] = None,
    max_probes: int = MAX_PROBES,
    enable_gate: bool = True,
    enable_probes: bool = True,
    enable_profile: bool = True,
    enable_recompute: bool = True,
) -> tuple:
    """Verify one query. Returns ``(Verdict, Trace)``.

    The three ``enable_*`` switches map one-to-one onto the three design choices
    under test -- measured context, executed tools, and verification -- so the
    changelog can measure what each contributes on identical cases instead of
    asserting it.
    """
    trace = trace or Trace(case_id=case_id, system="recount")

    # 1. Execute the query under review, so every later stage argues about a
    #    real number rather than an imagined one.
    try:
        original_result = run_sql(db_path, sql)
    except SqlError as exc:
        trace.add_tool("execute_under_review", "run_sql", sql, str(exc), ok=False)
        return V.failed(f"the query under review does not execute: {exc}"), trace

    original_text = render_result(original_result)
    trace.add_tool("execute_under_review", "run_sql", sql, original_text)

    # 2. Measured facts, no model involved.
    profile = cached_profile or build_profile(db_path)
    tables = _referenced_tables(sql, profile)
    if enable_profile:
        profile_text = profile.to_prompt(tables=tables)
        trace.add_tool(
            "profile_warehouse",
            "profiler.profile",
            {"tables": tables},
            profile_text,
        )
    else:
        # Ablation: same pipeline, but the agent sees only the DDL and must
        # speculate about grain, NULLs and cardinality instead of knowing them.
        profile_text = "SCHEMA (no data profiling available)\n\n" + schema_ddl(db_path)
        trace.add_note(
            "profile_disabled",
            "Profiling disabled for this run; the agent sees the schema only.",
        )

    hypotheses: list = []
    recompute = Recompute()
    try:
        if enable_recompute:
            recompute = _recompute(
                client, trace, db_path, question, profile_text, original_result
            )
        else:
            trace.add_note(
                "recompute_disabled",
                "Independent recomputation disabled for this run.",
            )

        if enable_probes:
            hypotheses = _plan(
                client, trace, question, sql, profile_text, original_text, max_probes
            )
            _execute_probes(db_path, trace, hypotheses)
            for _ in range(MAX_PROBE_REPAIRS):
                if not any(h.error for h in hypotheses):
                    break
                _repair_probes(client, trace, db_path, hypotheses)
        else:
            trace.add_note(
                "probes_disabled",
                "Probe stage disabled for this run; adjudicating from measured "
                "facts alone.",
            )

        result = _adjudicate(
            client, trace, question, sql, profile_text, original_text,
            hypotheses, recompute,
        )
    except CassetteMiss:
        # A missing recording is a reproducibility failure, not a verdict.
        raise
    except LLMError as exc:
        trace.add_note("failure", f"model call failed: {exc}")
        return V.failed(str(exc)), trace

    # Attach the probes that were actually executed as supporting evidence.
    for h in hypotheses:
        if h.executed:
            result.evidence.append(
                V.Evidence(claim=h.risk, sql=h.probe_sql, result_text=h.result_text)
            )

    if enable_gate:
        result = _gate(db_path, trace, result, sql, original_result, recompute)
    else:
        trace.add_gate(
            "verification_gate",
            result.verdict,
            "gate disabled for this run; the model's verdict is accepted as-is",
        )

    return result, trace
