"""Pipeline tests with a scripted model.

The verification gate is the load-bearing idea of this project, so it is tested
against every path it can take, using real SQL executed against the real
warehouse. Only the model is faked.

Run directly (no test framework required):

    python3 -m tests.test_pipeline
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from recount import agent, cases, verdict as V, warehouse  # noqa: E402
from recount.profiler import profile  # noqa: E402
from tests.fake_llm import FakeClient  # noqa: E402

DB = None
PROFILE = None
PASSED = []
FAILED = []


def setup_module_state() -> None:
    global DB, PROFILE
    tmp = Path(tempfile.mkdtemp(prefix="recount-test-"))
    DB = str(tmp / "warehouse.db")
    warehouse.build(DB)
    cases.validate(DB)
    PROFILE = profile(DB)


def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        PASSED.append(name)
        print(f"  PASS  {name}")
    else:
        FAILED.append(f"{name}: {detail}")
        print(f"  FAIL  {name} — {detail}")


def _plan(*hypotheses) -> dict:
    return {"hypotheses": list(hypotheses)}


def _h(risk: str, sql: str, bug_type: str = "fanout_join") -> dict:
    return {"risk": risk, "bug_type": bug_type, "probe_sql": sql, "settles": "x"}


def _recompute_reply(sql: str, reasoning: str = "derived from the question") -> dict:
    return {"sql": " ".join(sql.split()), "reasoning": reasoning}


def run(case_id: str, script: dict, **kwargs):
    """Run the agent on a bundled case with a scripted model.

    Unless the caller scripts it, the recomputation step is given the case's
    reference query -- the "competent independent derivation" scenario, which is
    the realistic default. Tests that need an incompetent or unavailable
    recomputation script it explicitly or pass enable_recompute=False.
    """
    case = cases.by_id(case_id)
    if kwargs.get("enable_recompute", True) and "recompute" not in script:
        script = dict(script)
        script["recompute"] = [_recompute_reply(case.reference_sql)]
    client = FakeClient(script)
    result, trace = agent.review(
        DB,
        case.business_question,
        case.sql,
        client,
        case_id=case_id,
        cached_profile=PROFILE,
        **kwargs,
    )
    return result, trace, client


# ---------------------------------------------------------------------------
# Gate: a real bug with a real fix must be confirmed, with a magnitude.
# ---------------------------------------------------------------------------
def test_true_positive_is_confirmed_with_magnitude() -> None:
    case = cases.by_id("B1_fanout_payments_via_line_items")
    result, trace, _ = run(
        case.case_id,
        {
            "plan": [
                _plan(
                    _h(
                        "order_items fans out relative to orders",
                        "SELECT COUNT(*) AS joined_rows FROM orders o "
                        "JOIN order_items oi ON oi.order_id = o.order_id",
                    )
                )
            ],
            "adjudicate": [
                {
                    "verdict": "BUG",
                    "bug_type": "fanout_join",
                    "confidence": 0.9,
                    "explanation": "order_items duplicates each payment row.",
                    "corrected_sql": case.reference_sql,
                }
            ],
        },
    )
    check("true positive stays BUG", result.verdict == V.BUG, result.verdict)
    delta = " ".join(e.delta or "" for e in result.evidence)
    check("magnitude is reported", "2.61x" in delta, delta)
    check(
        "gate event recorded",
        any(e.kind == "gate" and e.payload.get("decision") == V.BUG for e in trace.events),
    )


# ---------------------------------------------------------------------------
# Gate: the false-positive killer. A "fix" that changes nothing means the
# original was fine. This is the C2 hard case.
# ---------------------------------------------------------------------------
def test_no_op_correction_is_downgraded_to_clean() -> None:
    case = cases.by_id("C2_clean_units_sold_at_line_grain")
    result, _, _ = run(
        case.case_id,
        {
            "plan": [
                _plan(
                    _h(
                        "joining order_items may duplicate rows",
                        "SELECT COUNT(*) FROM orders o JOIN order_items oi "
                        "ON oi.order_id = o.order_id",
                    )
                )
            ],
            "adjudicate": [
                {
                    "verdict": "BUG",
                    "bug_type": "fanout_join",
                    "confidence": 0.85,
                    "explanation": "Looks like a fan-out join.",
                    # Semantically identical to the original: the classic
                    # over-eager "fix" that changes no number.
                    "corrected_sql": case.reference_sql,
                }
            ],
        },
    )
    check(
        "no-op correction downgraded to CLEAN",
        result.verdict == V.CLEAN,
        f"got {result.verdict}",
    )
    check("bug_type cleared on downgrade", result.bug_type is None, str(result.bug_type))
    check(
        "downgrade explains itself without jargon",
        "no discrepancy" in result.explanation.lower(),
        result.explanation,
    )


# ---------------------------------------------------------------------------
# Gate: an unfalsifiable claim is not allowed to reach the analyst as a bug.
# ---------------------------------------------------------------------------
def test_recomputation_overrules_a_clean_verdict_on_a_real_fault() -> None:
    """The capability the first gate lacked: contradicting a CLEAN verdict.

    Measured on gpt-4o-mini, the reviewer waved through B1 and B4 -- a 2.61x
    overstatement and a 93% row loss. A gate that can only downgrade bug claims
    is structurally unable to catch that, which is why it is now symmetric.
    """
    result, trace, _ = run(
        "B1_fanout_payments_via_line_items",
        {
            "plan": [_plan(_h("fan-out", "SELECT COUNT(*) FROM order_items"))],
            "adjudicate": [
                {
                    "verdict": "CLEAN",
                    "confidence": 0.8,
                    "explanation": "The join looks intentional to me.",
                    "corrected_sql": None,
                }
            ],
        },
    )
    check(
        "a CLEAN verdict contradicted by recomputation is escalated, not accepted",
        result.verdict == V.ESCALATE,
        result.verdict,
    )
    check(
        "the conflict is named",
        result.error == "recomputation_conflict",
        str(result.error),
    )
    check(
        "the magnitude reaches the analyst anyway",
        any("2.61x" in (e.delta or "") for e in result.evidence),
        str([e.delta for e in result.evidence]),
    )


def test_bug_without_correction_is_supplied_one_by_recomputation() -> None:
    result, _, _ = run(
        "B3_null_swallowing_status_filter",
        {
            "plan": [_plan(_h("status is nullable", "SELECT COUNT(*) FROM orders"))],
            "adjudicate": [
                {
                    "verdict": "BUG",
                    "bug_type": "null_swallowing_predicate",
                    "confidence": 0.7,
                    "explanation": "The NULL handling drops rows.",
                    "corrected_sql": None,
                }
            ],
        },
    )
    check(
        "the bug stands because the recomputation demonstrates it",
        result.verdict == V.BUG,
        result.verdict,
    )
    check(
        "and the analyst still receives a runnable correction",
        bool(result.corrected_sql),
        str(result.corrected_sql),
    )


def test_reviewer_correction_wins_even_when_the_derivation_disagrees() -> None:
    """The repair the analyst receives should be the more accurate one.

    Measured on gpt-4o-mini: letting the independent derivation override the
    reviewer's correction gave 3/8 correct repairs, against 7/8 for the
    reviewer's own answer. Detection and repair are different jobs, and the
    derivation is only good at the first.
    """
    case = cases.by_id("B3_null_swallowing_status_filter")
    reviewer_fix = (
        "SELECT COUNT(*) AS active_orders FROM orders "
        "WHERE status IS NULL OR status <> 'cancelled'"
    )
    # A derivation that disagrees with both the original and the reviewer.
    poor_derivation = "SELECT COUNT(*) AS active_orders FROM orders WHERE status = 'completed'"

    result, trace, _ = run(
        case.case_id,
        {
            "recompute": [_recompute_reply(poor_derivation)],
            "plan": [_plan(_h("status is nullable", "SELECT COUNT(*) FROM orders"))],
            "adjudicate": [
                {
                    "verdict": "BUG",
                    "bug_type": "null_swallowing_predicate",
                    "confidence": 0.9,
                    "explanation": "NULL status rows are dropped.",
                    "corrected_sql": reviewer_fix,
                }
            ],
        },
    )
    check("verdict is BUG", result.verdict == V.BUG, result.verdict)
    check(
        "the reviewer's correction is what the analyst gets",
        (result.corrected_sql or "").strip() == reviewer_fix,
        str(result.corrected_sql),
    )
    check(
        "the correction is actually right",
        cases.run_sql(DB, result.corrected_sql or "")["rows"]
        == cases.run_sql(DB, case.reference_sql)["rows"],
    )
    check(
        "the competing value is surfaced, not hidden",
        any("second, independently derived" in e.claim for e in result.evidence),
        str([e.claim for e in result.evidence]),
    )


def test_correction_that_repairs_nothing_falls_back_to_the_derivation() -> None:
    case = cases.by_id("B8_missing_status_filter")
    result, _, _ = run(
        case.case_id,
        {
            "plan": [_plan(_h("no status filter", "SELECT COUNT(*) FROM orders"))],
            "adjudicate": [
                {
                    "verdict": "BUG",
                    "bug_type": "missing_filter",
                    "confidence": 0.9,
                    "explanation": "No status predicate.",
                    # Identical to the query under review: repairs nothing.
                    "corrected_sql": " ".join(case.sql.split()),
                }
            ],
        },
    )
    check("verdict is BUG", result.verdict == V.BUG, result.verdict)
    check(
        "a correction returning the original number is not handed over",
        " ".join((result.corrected_sql or "").split()) != " ".join(case.sql.split()),
        str(result.corrected_sql),
    )
    check(
        "the derivation is used instead, and it is right",
        cases.run_sql(DB, result.corrected_sql or "")["rows"]
        == cases.run_sql(DB, case.reference_sql)["rows"],
        str(result.corrected_sql),
    )


def test_reviewer_correction_is_preferred_when_it_corroborates() -> None:
    case = cases.by_id("B5_between_loses_last_day")
    good = "SELECT COUNT(*) AS january_orders FROM orders WHERE order_ts >= '2026-01-01' AND order_ts < '2026-02-01'"
    result, _, _ = run(
        case.case_id,
        {
            "plan": [_plan(_h("BETWEEN drops the last day", "SELECT COUNT(*) FROM orders"))],
            "adjudicate": [
                {
                    "verdict": "BUG",
                    "bug_type": "date_range_truncation",
                    "confidence": 0.9,
                    "explanation": "The upper bound truncates.",
                    "corrected_sql": good,
                }
            ],
        },
    )
    check("verdict is BUG", result.verdict == V.BUG, result.verdict)
    check(
        "two agreeing derivations keep the reviewer's own correction",
        (result.corrected_sql or "").strip() == good,
        str(result.corrected_sql),
    )


# ---------------------------------------------------------------------------
# Fallback: with no recomputation the gate still demands a consequence.
# ---------------------------------------------------------------------------
def test_without_recomputation_bug_without_correction_escalates() -> None:
    result, _, _ = run(
        "B3_null_swallowing_status_filter",
        {
            "plan": [_plan(_h("status is nullable", "SELECT COUNT(*) FROM orders"))],
            "adjudicate": [
                {
                    "verdict": "BUG",
                    "bug_type": "null_swallowing_predicate",
                    "confidence": 0.7,
                    "explanation": "Something feels off about the NULL handling.",
                    "corrected_sql": None,
                }
            ],
        },
        enable_recompute=False,
    )
    check("unproven bug becomes ESCALATE", result.verdict == V.ESCALATE, result.verdict)
    check(
        "reason is machine-readable",
        result.error == "bug_claim_without_correction",
        str(result.error),
    )


def test_without_recomputation_broken_correction_escalates() -> None:
    result, _, _ = run(
        "B5_between_loses_last_day",
        {
            "plan": [_plan(_h("BETWEEN drops the last day", "SELECT COUNT(*) FROM orders"))],
            "adjudicate": [
                {
                    "verdict": "BUG",
                    "bug_type": "date_range_truncation",
                    "confidence": 0.9,
                    "explanation": "The upper bound truncates.",
                    "corrected_sql": "SELECT COUNT(*) FROM ordrs WHERE 1=1",
                }
            ],
        },
        enable_recompute=False,
    )
    check(
        "broken correction becomes ESCALATE",
        result.verdict == V.ESCALATE,
        result.verdict,
    )
    check(
        "failure reason recorded",
        result.error == "correction_failed_to_execute",
        str(result.error),
    )


def test_unrunnable_recomputation_falls_back_gracefully() -> None:
    case = cases.by_id("B1_fanout_payments_via_line_items")
    result, trace, _ = run(
        case.case_id,
        {
            "recompute": [_recompute_reply("SELECT * FROM table_that_is_absent")],
            "plan": [_plan(_h("fan-out", "SELECT COUNT(*) FROM order_items"))],
            "adjudicate": [
                {
                    "verdict": "BUG",
                    "bug_type": "fanout_join",
                    "confidence": 0.9,
                    "explanation": "Fan-out confirmed.",
                    "corrected_sql": case.reference_sql,
                }
            ],
        },
    )
    check(
        "a broken recomputation does not abort the run",
        result.verdict == V.BUG,
        result.verdict,
    )
    check(
        "the fallback is recorded",
        any(
            "no independent recomputation" in str(e.payload.get("text", "")).lower()
            for e in trace.events
            if e.kind == "note"
        ),
    )


# ---------------------------------------------------------------------------
# Probe loop: tool failure must shape the next step, not be swallowed.
# ---------------------------------------------------------------------------
def test_failed_probe_is_repaired_from_tool_feedback() -> None:
    case = cases.by_id("B1_fanout_payments_via_line_items")
    result, trace, client = run(
        case.case_id,
        {
            "plan": [
                _plan(
                    _h("fan-out check", "SELECT COUNT(*) FROM order_itemz"),
                )
            ],
            "probe_repair": [
                {
                    "probes": [
                        {"index": 1, "probe_sql": "SELECT COUNT(*) FROM order_items"}
                    ]
                }
            ],
            "adjudicate": [
                {
                    "verdict": "BUG",
                    "bug_type": "fanout_join",
                    "confidence": 0.9,
                    "explanation": "Confirmed fan-out.",
                    "corrected_sql": case.reference_sql,
                }
            ],
        },
    )
    steps = [c["step"] for c in client.calls]
    check("repair step was invoked", "probe_repair" in steps, str(steps))
    failed_tools = [
        e for e in trace.events if e.kind == "tool" and not e.payload.get("ok", True)
    ]
    check("failed probe is visible in the trace", len(failed_tools) == 1, str(len(failed_tools)))
    repair_prompt = client.prompt_for("probe_repair") or ""
    check(
        "the actual sqlite error is fed back",
        "order_itemz" in repair_prompt and "no such table" in repair_prompt.lower(),
        repair_prompt[:160],
    )
    check("verdict survives the repair", result.verdict == V.BUG, result.verdict)


# ---------------------------------------------------------------------------
# Robustness: malformed model output must never become a silent CLEAN.
# ---------------------------------------------------------------------------
def test_malformed_verdict_fails_safe() -> None:
    result, _, _ = run(
        "B8_missing_status_filter",
        {
            "plan": [_plan(_h("no status filter", "SELECT COUNT(*) FROM orders"))],
            "adjudicate": ['{"verdict": "PROBABLY_FINE", "confidence": 0.5}'],
        },
    )
    check(
        "unknown verdict fails safe to ESCALATE",
        result.verdict == V.ESCALATE,
        result.verdict,
    )
    check(
        "never silently CLEAN",
        result.verdict != V.CLEAN,
        result.verdict,
    )


def test_prose_wrapped_json_is_recovered() -> None:
    case = cases.by_id("B7_mixed_currency_unit_error")
    result, _, _ = run(
        case.case_id,
        {
            "plan": ["Here you go:\n```json\n" + '{"hypotheses": []}' + "\n```"],
            "adjudicate": [
                "Sure — my analysis:\n{"
                '"verdict": "BUG", "bug_type": "mixed_unit_aggregation", '
                '"confidence": 0.8, "explanation": "IDR and USD are summed together.", '
                '"corrected_sql": "' + " ".join(case.reference_sql.split()) + '"}'
            ],
        },
    )
    check(
        "fenced and prose-wrapped JSON is recovered",
        result.verdict == V.BUG,
        f"{result.verdict} / {result.error}",
    )


# ---------------------------------------------------------------------------
# Ablations must actually change behaviour, or the changelog would be fiction.
# ---------------------------------------------------------------------------
def test_gate_ablation_lets_false_positive_through() -> None:
    case = cases.by_id("C2_clean_units_sold_at_line_grain")
    script = {
        "plan": [_plan(_h("fan-out?", "SELECT COUNT(*) FROM order_items"))],
        "adjudicate": [
            {
                "verdict": "BUG",
                "bug_type": "fanout_join",
                "confidence": 0.85,
                "explanation": "Looks like a fan-out join.",
                "corrected_sql": case.reference_sql,
            }
        ],
    }
    without_gate, _, _ = run(case.case_id, script, enable_gate=False)
    check(
        "with the gate disabled the false positive survives",
        without_gate.verdict == V.BUG,
        without_gate.verdict,
    )


def test_profile_is_split_by_role() -> None:
    """Authors and reviewers need different facts, and mixing them costs accuracy.

    Diagnosed from a real false positive: the recomputation for C4 wrote
    `order_ts >= '2026-01-01T00:00:00Z'` against timestamps stored as
    `'2026-01-01 02:11:00'`. Because 'T' sorts after ' ', that dropped the first
    day of January and admitted the first day of February -- 557 rows instead of
    551 -- and the discrepancy was reported as a fault in a correct query.

    With the profile enabled the format was known and C4 passed, but the fan-out
    warnings made the author defensive enough to break C1 and C2. Hence the
    split: authors get types, real NULLs and stored formats; reviewers get join
    cardinality.
    """
    from recount.profiler import AUTHOR, REVIEWER, profile as build

    prof = build(DB)
    author = prof.to_prompt(tables=["orders"], role=AUTHOR)
    reviewer = prof.to_prompt(tables=["orders"], role=REVIEWER)

    check(
        "the author is not shown fan-out warnings",
        "FANS OUT" not in author,
        author[:200],
    )
    check(
        "the reviewer still is",
        "FANS OUT" in reviewer,
        reviewer[:200],
    )
    check(
        "the author is shown the exact stored timestamp format",
        repr("2026-01-01 02:11:00") in author,
        author[:400],
    )
    check(
        "and told to match it",
        "match the stored format exactly" in author.lower(),
        author[-200:],
    )
    check(
        "the author still learns which columns are really nullable",
        "NULL in 80 rows" in author,
        author[:400],
    )

    # The recomputation step must receive the author view, not the reviewer one.
    case = cases.by_id("C4_clean_half_open_date_range")
    _, _, client = run(
        case.case_id,
        {
            "plan": [_plan(_h("range", "SELECT COUNT(*) FROM orders"))],
            "adjudicate": [
                {
                    "verdict": "CLEAN",
                    "confidence": 0.9,
                    "explanation": "Half-open range is correct.",
                    "corrected_sql": None,
                }
            ],
        },
    )
    recompute_prompt = client.prompt_for("recompute") or ""
    adjudicate_prompt = client.prompt_for("adjudicate") or ""
    check(
        "recompute prompt carries the author view",
        "FANS OUT" not in recompute_prompt and "MEASURED COLUMN FACTS" in recompute_prompt,
        recompute_prompt[:200],
    )
    check(
        "adjudicate prompt carries the reviewer view",
        "FANS OUT" in adjudicate_prompt,
        adjudicate_prompt[:200],
    )
    check(
        "the query under review is withheld from the recompute step",
        "BETWEEN" not in recompute_prompt.upper()
        and case.sql.split()[1] not in recompute_prompt,
        recompute_prompt[:200],
    )


def test_format_hints_carry_no_hazard_language() -> None:
    """The author gets how values look, and no warnings.

    Traced from two real failures. Without any measured context the author wrote
    `'2026-01-01T00:00:00Z'` against values stored `'2026-01-01 02:11:00'`, so
    formats are needed. With a fuller profile it wrote `WHERE status IS NOT NULL`
    in place of `WHERE status = 'completed'` -- the NULL warning displaced the
    required filter rather than adding to it. A hazard named to an author becomes
    the thing it optimises for, and it competes with the question.
    """
    from recount.profiler import profile as build

    hints = build(DB).format_hints(tables=["orders"])
    check(
        "the stored timestamp format is shown",
        repr("2026-01-01 02:11:00") in hints,
        hints[:200],
    )
    for phrase in ("FANS OUT", "must handle", "NULL in", "WARNING", "careful"):
        check(
            f"no hazard language: {phrase!r} absent",
            phrase.lower() not in hints.lower(),
            hints[:300],
        )

    case = cases.by_id("C4_clean_half_open_date_range")
    _, _, client = run(
        case.case_id,
        {
            "adjudicate": [
                {"verdict": "CLEAN", "confidence": 0.9,
                 "explanation": "Correct.", "corrected_sql": None}
            ]
        },
        enable_probes=False,
        enable_profile=False,
    )
    prompt = client.prompt_for("recompute") or ""
    check(
        "formats reach the author even with profiling off",
        repr("2026-01-01 02:11:00") in prompt,
        prompt[-300:],
    )
    check(
        "and no fan-out warning rides along",
        "FANS OUT" not in prompt,
        prompt[:200],
    )

    _, trace, client2 = run(
        case.case_id,
        {
            "adjudicate": [
                {"verdict": "CLEAN", "confidence": 0.9,
                 "explanation": "Correct.", "corrected_sql": None}
            ]
        },
        enable_probes=False,
        enable_profile=False,
        enable_formats=False,
    )
    check(
        "--no-formats genuinely withholds them",
        repr("2026-01-01 02:11:00") not in (client2.prompt_for("recompute") or ""),
    )
    check(
        "and says so in the trace",
        any(e.step == "formats_disabled" for e in trace.events),
    )


def test_profile_ablation_falls_back_to_schema_only() -> None:
    case = cases.by_id("B1_fanout_payments_via_line_items")
    script = {
        "plan": [_plan(_h("fan-out", "SELECT COUNT(*) FROM order_items"))],
        "adjudicate": [
            {
                "verdict": "BUG",
                "bug_type": "fanout_join",
                "confidence": 0.9,
                "explanation": "Fan-out.",
                "corrected_sql": case.reference_sql,
            }
        ],
    }
    _, with_profile, client_a = run(case.case_id, script)
    _, without, client_b = run(case.case_id, dict(script), enable_profile=False)

    measured = client_a.prompt_for("plan") or ""
    schema_only = client_b.prompt_for("plan") or ""
    check(
        "with profiling the agent is told the measured fan-out factor",
        "FANS OUT" in measured,
        measured[:120],
    )
    check(
        "without profiling it sees only DDL and must speculate",
        "FANS OUT" not in schema_only and "CREATE TABLE" in schema_only,
        schema_only[:120],
    )
    check(
        "the ablation is recorded in the trace",
        any(e.step == "profile_disabled" for e in without.events),
    )


def test_probe_ablation_skips_planning() -> None:
    result, trace, client = run(
        "B4_left_join_degraded_to_inner",
        {
            "adjudicate": [
                {
                    "verdict": "ESCALATE",
                    "confidence": 0.4,
                    "explanation": "Cannot tell without checking the data.",
                    "corrected_sql": None,
                }
            ]
        },
        enable_probes=False,
    )
    steps = [c["step"] for c in client.calls]
    check("planner is skipped when probes are off", "plan" not in steps, str(steps))
    check("profile is still provided", any(
        e.kind == "tool" and e.payload.get("tool") == "profiler.profile"
        for e in trace.events
    ))


# ---------------------------------------------------------------------------
# Safety: the agent's probe channel must not be able to mutate the warehouse.
# ---------------------------------------------------------------------------
def test_destructive_probe_is_blocked_and_reported() -> None:
    case = cases.by_id("B1_fanout_payments_via_line_items")
    result, trace, _ = run(
        case.case_id,
        {
            "plan": [_plan(_h("suspicious", "DROP TABLE orders"))],
            "probe_repair": [{"probes": []}],
            "adjudicate": [
                {
                    "verdict": "BUG",
                    "bug_type": "fanout_join",
                    "confidence": 0.9,
                    "explanation": "Fan-out confirmed by the profile.",
                    "corrected_sql": case.reference_sql,
                }
            ],
        },
    )
    still_there = cases.run_sql(DB, "SELECT COUNT(*) FROM orders")["rows"][0][0]
    check("warehouse is intact after a destructive probe", still_there == 1500, str(still_there))
    blocked = [
        e for e in trace.events
        if e.kind == "tool" and not e.payload.get("ok", True)
    ]
    check("the blocked probe is recorded in the trace", len(blocked) >= 1, str(len(blocked)))


def test_warehouse_digest_is_content_based_not_file_based() -> None:
    """Two builds must agree on content, and the digest must not read file bytes.

    Regression test for a real defect: the original check hashed the .db file,
    which varies with the SQLite library version, so it reported "your data
    differs" on machines whose data was identical.
    """
    import hashlib
    import tempfile as _tempfile

    tmp = Path(_tempfile.mkdtemp(prefix="recount-digest-"))
    first, second = str(tmp / "one.db"), str(tmp / "two.db")
    warehouse.build(first)
    warehouse.build(second)

    d1 = warehouse.content_digest(first)
    d2 = warehouse.content_digest(second)
    check("content digest is stable across builds", d1 == d2, f"{d1} vs {d2}")
    check(
        "content digest matches the published constant",
        d1 == warehouse.CONTENT_DIGEST,
        f"{d1} vs {warehouse.CONTENT_DIGEST}",
    )

    file_hash = hashlib.sha256(Path(first).read_bytes()).hexdigest()[:16]
    check(
        "the digest is not merely the file hash",
        d1 != file_hash,
        "digest coincides with the file hash, so it may still be layout-dependent",
    )

    # A single changed value must move the digest, or it proves nothing.
    conn = __import__("sqlite3").connect(second)
    conn.execute("UPDATE orders SET status = 'cancelled' WHERE order_id = 1")
    conn.commit()
    conn.close()
    check(
        "digest detects a single altered row",
        warehouse.content_digest(second) != d2,
    )


def test_empty_response_from_reasoning_model_is_recovered() -> None:
    """A reasoning model can spend the whole ceiling thinking and return nothing.

    Observed live on gpt-5.6-luna: max_tokens is renamed to
    max_completion_tokens, that ceiling covers reasoning, and a value sized for a
    chat model is consumed before any content is written. The response is a
    valid 200 with empty content, so it must be detected and retried rather than
    surfaced as a parse failure.
    """
    import tempfile as _tempfile

    from recount.llm import MODE_RECORD, LLMClient
    from recount.trace import Trace as _Trace

    class ReasoningHeavy(LLMClient):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.budgets: list = []

        def _post(self, body):
            budget = body.get("max_completion_tokens") or body.get("max_tokens")
            self.budgets.append(budget)
            if budget < 5000:
                return {
                    "choices": [{"message": {"content": ""}, "finish_reason": "length"}],
                    "usage": {
                        "prompt_tokens": 900,
                        "completion_tokens": budget,
                        "completion_tokens_details": {"reasoning_tokens": budget},
                    },
                }
            return {
                "choices": [
                    {
                        "message": {"content": '{"verdict": "BUG"}'},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 900,
                    "completion_tokens": 240,
                    "prompt_tokens_details": {"cached_tokens": 700},
                },
            }

    client = ReasoningHeavy(
        model="gpt-5.6-luna",
        cassette_dir=_tempfile.mkdtemp(prefix="recount-empty-"),
        mode=MODE_RECORD,
        api_key="unused",
    )
    trace = _Trace(case_id="empty-response")
    response = client.chat(
        [{"role": "user", "content": "plan"}], step="plan", max_tokens=1600, trace=trace
    )

    check("empty response is retried at a larger ceiling", len(client.budgets) == 2,
          str(client.budgets))
    check("the retry succeeds", response.json() == {"verdict": "BUG"}, response.text)
    check(
        "the raised ceiling is remembered for later calls",
        client._token_scale > 1,
        str(client._token_scale),
    )
    check(
        "the retry is visible in the trajectory",
        any(e.step == "token_budget" for e in trace.events),
    )

    client.budgets.clear()
    client.chat([{"role": "user", "content": "adjudicate"}], step="adjudicate",
                max_tokens=1200)
    check(
        "a later call starts at the learned ceiling, wasting no request",
        len(client.budgets) == 1,
        str(client.budgets),
    )


def test_cached_prompt_tokens_are_priced_at_the_cached_rate() -> None:
    """Charging cached prompt tokens at full rate overstates cost substantially."""
    import tempfile as _tempfile

    from recount.llm import MODE_RECORD, LLMClient

    client = LLMClient(
        model="gpt-5.6-luna",
        cassette_dir=_tempfile.mkdtemp(prefix="recount-price-"),
        mode=MODE_RECORD,
        api_key="unused",
    )
    usage = client._usage_from(
        {
            "usage": {
                "prompt_tokens": 900,
                "completion_tokens": 240,
                "prompt_tokens_details": {"cached_tokens": 700},
            }
        }
    )
    expected = 200 * 0.20 / 1e6 + 700 * 0.02 / 1e6 + 240 * 1.20 / 1e6
    check(
        "cached tokens billed at the cached rate",
        abs(usage["cost_usd"] - expected) < 1e-9,
        f"{usage['cost_usd']} vs {expected}",
    )
    naive = 900 * 0.20 / 1e6 + 240 * 1.20 / 1e6
    check(
        "and that materially differs from ignoring the cache",
        naive > usage["cost_usd"] * 1.2,
        f"naive {naive} vs {usage['cost_usd']}",
    )

    unknown = LLMClient(
        model="a-model-with-no-published-price",
        cassette_dir=_tempfile.mkdtemp(prefix="recount-price2-"),
        mode=MODE_RECORD,
        api_key="unused",
    )
    unknown_usage = unknown._usage_from(
        {"usage": {"prompt_tokens": 100, "completion_tokens": 10}}
    )
    check(
        "an unpriced model reports cost as unknown rather than guessing",
        unknown_usage["cost_known"] is False,
        str(unknown_usage),
    )


def test_dotenv_parsing_and_precedence() -> None:
    """`.env` must work, must never override the shell, and must not leak values."""
    import io
    import os
    import tempfile as _tempfile
    from contextlib import redirect_stdout

    from recount import env as env_mod

    parsed = env_mod.parse(
        "\n".join(
            [
                "# comment",
                "PLAIN=sk-plain",
                'export QUOTED="sk with space"',
                "SINGLE='sk-single'",
                "TRAILING=sk-abc # note",
                'HASHED="sk-a#b"',
                "EMPTY=",
                "no equals sign here",
            ]
        )
    )
    check("plain value parsed", parsed.get("PLAIN") == "sk-plain", str(parsed))
    check("export prefix stripped", parsed.get("QUOTED") == "sk with space", str(parsed))
    check("single quotes stripped", parsed.get("SINGLE") == "sk-single", str(parsed))
    check("inline comment removed", parsed.get("TRAILING") == "sk-abc", str(parsed))
    check("hash inside quotes preserved", parsed.get("HASHED") == "sk-a#b", str(parsed))
    check("malformed line ignored", "no equals sign here" not in parsed, str(parsed))

    tmp = Path(_tempfile.mkdtemp(prefix="recount-env-"))
    (tmp / "recount").mkdir()
    (tmp / "run_all.py").write_text("", encoding="utf-8")
    (tmp / ".env").write_text("RECOUNT_TEST_SECRET=sk-from-file\n", encoding="utf-8")

    original = os.environ.pop("RECOUNT_TEST_SECRET", None)
    try:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            env_mod.load(tmp)
        check(
            "value from .env is applied",
            os.environ.get("RECOUNT_TEST_SECRET") == "sk-from-file",
            str(os.environ.get("RECOUNT_TEST_SECRET")),
        )
        printed = buffer.getvalue()
        check(
            "the secret is never printed",
            "sk-from-file" not in printed,
            printed.strip(),
        )
        check("only the key name is reported", "RECOUNT_TEST_SECRET" in printed, printed)

        # An exported variable must survive a second load.
        os.environ["RECOUNT_TEST_SECRET"] = "sk-from-shell"
        with redirect_stdout(io.StringIO()):
            env_mod.load(tmp)
        check(
            "the shell environment wins over .env",
            os.environ["RECOUNT_TEST_SECRET"] == "sk-from-shell",
            os.environ["RECOUNT_TEST_SECRET"],
        )
    finally:
        os.environ.pop("RECOUNT_TEST_SECRET", None)
        if original is not None:
            os.environ["RECOUNT_TEST_SECRET"] = original


def test_dotenv_is_gitignored() -> None:
    """A supported credential file that is not ignored is a leak waiting to happen."""
    ignore = (Path(__file__).resolve().parents[1] / ".gitignore").read_text(
        encoding="utf-8"
    )
    entries = {line.strip() for line in ignore.splitlines()}
    check(".env is gitignored", ".env" in entries, sorted(entries))
    check(
        ".env.example is NOT ignored, so the template ships",
        ".env.example" not in entries,
        sorted(entries),
    )


def test_trace_renders_markdown() -> None:
    case = cases.by_id("B1_fanout_payments_via_line_items")
    _, trace, _ = run(
        case.case_id,
        {
            "plan": [_plan(_h("fan-out", "SELECT COUNT(*) FROM order_items"))],
            "adjudicate": [
                {
                    "verdict": "BUG",
                    "bug_type": "fanout_join",
                    "confidence": 0.9,
                    "explanation": "Fan-out.",
                    "corrected_sql": case.reference_sql,
                }
            ],
        },
    )
    md = trace.to_markdown()
    check("trace markdown includes tool responses", "run_sql" in md, "")
    check("trace markdown includes the gate", "gate" in md.lower(), "")
    check("trace jsonl is line-per-event", len(trace.to_jsonl().splitlines()) == len(trace.events))


TESTS = [
    test_true_positive_is_confirmed_with_magnitude,
    test_no_op_correction_is_downgraded_to_clean,
    test_recomputation_overrules_a_clean_verdict_on_a_real_fault,
    test_bug_without_correction_is_supplied_one_by_recomputation,
    test_reviewer_correction_wins_even_when_the_derivation_disagrees,
    test_correction_that_repairs_nothing_falls_back_to_the_derivation,
    test_reviewer_correction_is_preferred_when_it_corroborates,
    test_without_recomputation_bug_without_correction_escalates,
    test_without_recomputation_broken_correction_escalates,
    test_unrunnable_recomputation_falls_back_gracefully,
    test_failed_probe_is_repaired_from_tool_feedback,
    test_malformed_verdict_fails_safe,
    test_prose_wrapped_json_is_recovered,
    test_gate_ablation_lets_false_positive_through,
    test_format_hints_carry_no_hazard_language,
    test_profile_is_split_by_role,
    test_profile_ablation_falls_back_to_schema_only,
    test_probe_ablation_skips_planning,
    test_destructive_probe_is_blocked_and_reported,
    test_warehouse_digest_is_content_based_not_file_based,
    test_empty_response_from_reasoning_model_is_recovered,
    test_cached_prompt_tokens_are_priced_at_the_cached_rate,
    test_dotenv_parsing_and_precedence,
    test_dotenv_is_gitignored,
    test_trace_renders_markdown,
]


def main() -> int:
    setup_module_state()
    for test in TESTS:
        print(f"\n{test.__name__}")
        test()
    print("\n" + "=" * 62)
    print(f"{len(PASSED)} passed, {len(FAILED)} failed")
    for failure in FAILED:
        print(f"  - {failure}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
