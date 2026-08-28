"""The evaluation set: 12 analyst questions with machine-verified ground truth.

Each case carries three things:

``business_question``
    What the analyst actually asked. Correctness is undefined without it -- a
    join to line-item grain is a bug when the metric is order-level revenue and
    correct when the metric is units sold. Any verifier that reasons only about
    SQL shape must therefore produce false positives.

``sql``
    What a text-to-SQL agent returned. Every one of these executes without
    error and returns a plausible number.

``reference_sql``
    An independently written query for the same intent, used as ground truth.

Labels are not asserted by hand. ``validate`` executes ``sql`` and
``reference_sql`` and checks that BUG cases genuinely disagree and CLEAN cases
genuinely agree. A mislabelled case fails the build, so a reviewer never has to
take the labels on trust.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .sqlio import SqlError, result_signature, run_sql  # noqa: F401  (re-exported)

CLEAN = "CLEAN"
BUG = "BUG"


@dataclass(frozen=True)
class Case:
    case_id: str
    business_question: str
    sql: str
    reference_sql: str
    label: str
    bug_type: Optional[str] = None
    hazard: str = ""
    tags: tuple = field(default_factory=tuple)

    @property
    def is_bug(self) -> bool:
        return self.label == BUG


CASES: tuple = (
    # ------------------------------------------------------------------ bugs
    Case(
        case_id="B1_fanout_payments_via_line_items",
        business_question=(
            "How much money did we actually capture from completed orders? "
            "Return a single total in cents."
        ),
        sql="""
            SELECT SUM(p.amount_cents) AS captured_cents
            FROM orders o
            JOIN order_items oi ON oi.order_id = o.order_id
            JOIN payments    p  ON p.order_id  = o.order_id
            WHERE o.status = 'completed'
        """,
        reference_sql="""
            SELECT SUM(p.amount_cents) AS captured_cents
            FROM orders o
            JOIN payments p ON p.order_id = o.order_id
            WHERE o.status = 'completed'
        """,
        label=BUG,
        bug_type="fanout_join",
        hazard=(
            "order_items is at line-item grain. Joining it alongside payments "
            "repeats every payment row once per line item, so an order-level "
            "measure is multiplied by its item count."
        ),
        tags=("grain", "flagship"),
    ),
    Case(
        case_id="B2_fanout_units_via_payments",
        business_question=(
            "How many units did we sell on completed orders? Return a single total."
        ),
        sql="""
            SELECT SUM(oi.quantity) AS units_sold
            FROM orders o
            JOIN order_items oi ON oi.order_id = o.order_id
            JOIN payments    p  ON p.order_id  = o.order_id
            WHERE o.status = 'completed'
        """,
        reference_sql="""
            SELECT SUM(oi.quantity) AS units_sold
            FROM orders o
            JOIN order_items oi ON oi.order_id = o.order_id
            WHERE o.status = 'completed'
        """,
        label=BUG,
        bug_type="fanout_join",
        hazard=(
            "payments carries several rows for installment orders, duplicating "
            "line items. The fan-out runs in the opposite direction from B1, so "
            "a verifier that only knows the 'order_items is dangerous' rule "
            "will miss it."
        ),
        tags=("grain",),
    ),
    Case(
        case_id="B3_null_swallowing_status_filter",
        business_question=(
            "How many orders are not cancelled? Orders whose status was never "
            "stamped by fulfilment are still live business, so count them."
        ),
        sql="""
            SELECT COUNT(*) AS active_orders
            FROM orders
            WHERE status != 'cancelled'
        """,
        reference_sql="""
            SELECT COUNT(*) AS active_orders
            FROM orders
            WHERE status IS NULL OR status != 'cancelled'
        """,
        label=BUG,
        bug_type="null_swallowing_predicate",
        hazard=(
            "status is nullable. NULL != 'cancelled' evaluates to NULL, not "
            "true, so every unstamped order is dropped without warning."
        ),
        tags=("three_valued_logic",),
    ),
    Case(
        case_id="B4_left_join_degraded_to_inner",
        business_question=(
            "Across all orders, how many orders are there and what is the total "
            "refunded amount? Orders that were never refunded count as zero."
        ),
        sql="""
            SELECT COUNT(*) AS orders_seen,
                   COALESCE(SUM(r.amount_cents), 0) AS refunded_cents
            FROM orders o
            LEFT JOIN refunds r ON r.order_id = o.order_id
            WHERE r.amount_cents >= 0
        """,
        reference_sql="""
            SELECT COUNT(*) AS orders_seen,
                   COALESCE(SUM(r.amount_cents), 0) AS refunded_cents
            FROM orders o
            LEFT JOIN refunds r ON r.order_id = o.order_id
        """,
        label=BUG,
        bug_type="left_join_degraded_to_inner",
        hazard=(
            "The WHERE predicate on the right-hand table discards the "
            "NULL-extended rows the LEFT JOIN was written to preserve, "
            "collapsing the result to refunded orders only."
        ),
        tags=("join_semantics", "catastrophic"),
    ),
    Case(
        case_id="B5_between_loses_last_day",
        business_question=(
            "How many orders were placed during January 2026, in UTC?"
        ),
        sql="""
            SELECT COUNT(*) AS january_orders
            FROM orders
            WHERE order_ts BETWEEN '2026-01-01' AND '2026-01-31'
        """,
        reference_sql="""
            SELECT COUNT(*) AS january_orders
            FROM orders
            WHERE order_ts >= '2026-01-01' AND order_ts < '2026-02-01'
        """,
        label=BUG,
        bug_type="date_range_truncation",
        hazard=(
            "order_ts is a timestamp, so BETWEEN's inclusive upper bound "
            "'2026-01-31' matches only the instant at midnight and drops the "
            "whole final day."
        ),
        tags=("temporal",),
    ),
    Case(
        case_id="B6_timezone_day_misattribution",
        business_question=(
            "How many orders were placed on 31 January 2026 on the "
            "Asia/Jakarta calendar (UTC+7)? Finance reports on local days."
        ),
        sql="""
            SELECT COUNT(*) AS orders_on_day
            FROM orders
            WHERE date(order_ts) = '2026-01-31'
        """,
        reference_sql="""
            SELECT COUNT(*) AS orders_on_day
            FROM orders
            WHERE date(order_ts, '+7 hours') = '2026-01-31'
        """,
        label=BUG,
        bug_type="timezone_day_boundary",
        hazard=(
            "order_ts is UTC but the business day is UTC+7. Orders placed "
            "after 17:00 UTC belong to the next Jakarta day, so a naive "
            "date() truncation attributes them to the wrong day."
        ),
        tags=("temporal",),
    ),
    Case(
        case_id="B7_mixed_currency_unit_error",
        business_question=(
            "What is the total captured revenue of the Indonesian business "
            "(IDR-denominated orders) from completed orders, in cents?"
        ),
        sql="""
            SELECT SUM(p.amount_cents) AS idr_revenue_cents
            FROM orders o
            JOIN payments p ON p.order_id = o.order_id
            WHERE o.status = 'completed'
        """,
        reference_sql="""
            SELECT SUM(p.amount_cents) AS idr_revenue_cents
            FROM orders o
            JOIN payments p ON p.order_id = o.order_id
            WHERE o.status = 'completed' AND o.currency = 'IDR'
        """,
        label=BUG,
        bug_type="mixed_unit_aggregation",
        hazard=(
            "orders.currency mixes IDR and USD. Summing amount_cents across "
            "both adds two different units and silently inflates the IDR total."
        ),
        tags=("units",),
    ),
    Case(
        case_id="B8_missing_status_filter",
        business_question=(
            "What revenue did we capture from completed orders only, in cents?"
        ),
        sql="""
            SELECT SUM(p.amount_cents) AS revenue_cents
            FROM orders o
            JOIN payments p ON p.order_id = o.order_id
        """,
        reference_sql="""
            SELECT SUM(p.amount_cents) AS revenue_cents
            FROM orders o
            JOIN payments p ON p.order_id = o.order_id
            WHERE o.status = 'completed'
        """,
        label=BUG,
        bug_type="missing_filter",
        hazard=(
            "No status predicate, so pending and refunded orders are counted "
            "as captured completed revenue."
        ),
        tags=("filter",),
    ),
    # ----------------------------------------------------------------- clean
    Case(
        case_id="C1_clean_distinct_order_count_with_payments",
        business_question=(
            "For completed orders, how many orders are there and how much did "
            "we capture in total?"
        ),
        sql="""
            SELECT COUNT(DISTINCT o.order_id) AS orders_seen,
                   SUM(p.amount_cents)        AS captured_cents
            FROM orders o
            JOIN payments p ON p.order_id = o.order_id
            WHERE o.status = 'completed'
        """,
        reference_sql="""
            SELECT COUNT(*) AS orders_seen, SUM(t.paid) AS captured_cents
            FROM (
                SELECT order_id, SUM(amount_cents) AS paid
                FROM payments GROUP BY order_id
            ) t
            JOIN orders o ON o.order_id = t.order_id
            WHERE o.status = 'completed'
        """,
        label=CLEAN,
        hazard=(
            "payments does fan out relative to orders, but COUNT(DISTINCT) "
            "handles the count and SUM over payments is the intended measure, "
            "so the result is correct."
        ),
        tags=("grain",),
    ),
    Case(
        case_id="C2_clean_units_sold_at_line_grain",
        business_question=(
            "How many units did we sell across completed orders?"
        ),
        sql="""
            SELECT SUM(oi.quantity) AS units_sold
            FROM orders o
            JOIN order_items oi ON oi.order_id = o.order_id
            WHERE o.status = 'completed'
        """,
        reference_sql="""
            SELECT SUM(t.units) AS units_sold
            FROM (
                SELECT order_id, SUM(quantity) AS units
                FROM order_items GROUP BY order_id
            ) t
            JOIN orders o ON o.order_id = t.order_id
            WHERE o.status = 'completed'
        """,
        label=CLEAN,
        hazard=(
            "THE HARD CASE. Surface-identical to B1 -- orders joined to "
            "order_items, then aggregated -- but the requested metric lives at "
            "line-item grain, so the join is exactly right. Distinguishing this "
            "from B1 requires reading the business question, not the SQL shape."
        ),
        tags=("grain", "adversarial", "hard"),
    ),
    Case(
        case_id="C3_clean_null_safe_active_orders",
        business_question=(
            "How many orders are not cancelled? Orders with an unset status "
            "count as not cancelled."
        ),
        sql="""
            SELECT COUNT(*) AS active_orders
            FROM orders
            WHERE COALESCE(status, 'unknown') <> 'cancelled'
        """,
        reference_sql="""
            SELECT COUNT(*) AS active_orders
            FROM orders
            WHERE status IS NULL OR status <> 'cancelled'
        """,
        label=CLEAN,
        hazard=(
            "Same question as B3, handled correctly with COALESCE. A verifier "
            "that pattern-matches on 'nullable column in a predicate' will "
            "false-positive here."
        ),
        tags=("three_valued_logic", "adversarial"),
    ),
    Case(
        case_id="C4_clean_half_open_date_range",
        business_question=(
            "How many orders were placed during January 2026, in UTC?"
        ),
        sql="""
            SELECT COUNT(*) AS january_orders
            FROM orders
            WHERE order_ts >= '2026-01-01' AND order_ts < '2026-02-01'
        """,
        reference_sql="""
            SELECT COUNT(*) AS january_orders
            FROM orders
            WHERE strftime('%Y-%m', order_ts) = '2026-01'
        """,
        label=CLEAN,
        hazard=(
            "Same question as B5, handled correctly with a half-open interval."
        ),
        tags=("temporal", "adversarial"),
    ),
)


# ---------------------------------------------------------------------------
# Execution + self-validation
# ---------------------------------------------------------------------------


@dataclass
class CaseTruth:
    case: Case
    reported: dict
    truth: dict
    differs: bool
    label_consistent: bool

    def summary(self) -> str:
        rep = self.reported["rows"][0] if self.reported["rows"] else ()
        tru = self.truth["rows"][0] if self.truth["rows"] else ()
        return f"reported={rep} truth={tru}"


def resolve_truth(db_path: str | Path, case: Case) -> CaseTruth:
    reported = run_sql(db_path, case.sql)
    truth = run_sql(db_path, case.reference_sql)
    differs = result_signature(reported) != result_signature(truth)
    return CaseTruth(
        case=case,
        reported=reported,
        truth=truth,
        differs=differs,
        label_consistent=(differs == case.is_bug),
    )


def validate(db_path: str | Path, cases: tuple = CASES) -> list:
    """Resolve every case and raise if any label contradicts the data."""
    resolved = [resolve_truth(db_path, c) for c in cases]
    broken = [r for r in resolved if not r.label_consistent]
    if broken:
        lines = [
            f"  {r.case.case_id}: label={r.case.label} but differs={r.differs} "
            f"({r.summary()})"
            for r in broken
        ]
        raise AssertionError(
            "eval set is mislabelled -- ground truth contradicts the label:\n"
            + "\n".join(lines)
        )
    return resolved


def by_id(case_id: str) -> Case:
    for case in CASES:
        if case.case_id == case_id:
            return case
    raise KeyError(case_id)


if __name__ == "__main__":  # pragma: no cover
    import argparse

    parser = argparse.ArgumentParser(
        description="Validate the eval set against the warehouse."
    )
    parser.add_argument("--db", default="data/warehouse.db")
    args = parser.parse_args()

    resolved = validate(args.db)
    n_bug = sum(1 for r in resolved if r.case.is_bug)
    print(f"{len(resolved)} cases validated: {n_bug} BUG / {len(resolved) - n_bug} CLEAN\n")
    for r in resolved:
        rep = r.reported["rows"][0] if r.reported["rows"] else ()
        tru = r.truth["rows"][0] if r.truth["rows"] else ()
        if r.case.is_bug:
            try:
                ratio = f"  ({rep[0] / tru[0]:.2f}x)" if tru and tru[0] else ""
            except (TypeError, ZeroDivisionError):
                ratio = ""
            print(f"  {r.case.case_id}")
            print(f"      bug_type : {r.case.bug_type}")
            print(f"      reported : {rep}")
            print(f"      truth    : {tru}{ratio}")
        else:
            print(f"  {r.case.case_id}")
            print(f"      agrees   : {rep}")
    print("\nOK - every label is backed by executed data.")
