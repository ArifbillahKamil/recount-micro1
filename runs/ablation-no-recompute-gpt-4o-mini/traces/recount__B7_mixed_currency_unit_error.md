# Trajectory — recount — B7_mixed_currency_unit_error

`2` model calls (`1` replayed from cassette) · `7` tool calls · `2577` tokens · `$0.00063`

## 1. tool · `run_sql` · execute_under_review · ok

**request**

```sql

            SELECT SUM(p.amount_cents) AS idr_revenue_cents
            FROM orders o
            JOIN payments p ON p.order_id = o.order_id
            WHERE o.status = 'completed'
        
```

**response**

```
idr_revenue_cents
-----------------
5468920000       
```

## 2. tool · `profiler.profile` · profile_warehouse · ok

**request**

```json
{
  "tables": [
    "orders",
    "payments"
  ],
  "views": [
    "reviewer",
    "author"
  ]
}
```

**response**

```
MEASURED WAREHOUSE FACTS

Join cardinality (measured, not inferred):
  ! order_items.order_id -> orders.order_id: FANS OUT x2.16 avg, up to x4; 1005 parent keys have >1 child row
  ! orders.customer_id -> customers.customer_id: FANS OUT x3.86 avg, up to x12; 352 parent keys have >1 child row
  ! payments.order_id -> orders.order_id: FANS OUT x1.24 avg, up to x3; 252 parent keys have >1 child row
    refunds.order_id -> orders.order_id: one row per parent (safe to join)

orders: 1500 rows, one row per order_id
  order_id: INTEGER, pk, 1500 distinct
  customer_id: INTEGER, 389 distinct
  order_ts: TEXT, 1493 distinct, range 2026-01-01 02:11:00 .. 2026-03-31 21:27:00
  status: TEXT, NULL in 80 rows (5.3%), 4 distinct
  currency: TEXT, 2 distinct

payments: 1683 rows, one row per payment_id
  payment_id: INTEGER, pk, 1683 distinct
  order_id: INTEGER, 1357 distinct
  amount_cents: INTEGER, 941 distinct
  paid_ts: TEXT, 1672 distinct, range 2026-01-01 03:12:00 .. 2026-05-30 03:21:00
  method: TEXT, 4 distinct
```

## 3. note · recompute_disabled

Independent recomputation disabled for this run.

## 4. model · plan

`gpt-4o-mini` · replayed · 772 in / 397 out · 0.00s

**system**

```
You are a senior analytics engineer who has been burned by
queries that run cleanly and return the wrong number. You do not speculate: you
design a measurement that would settle each suspicion.
```

**user**

```
Business question the analyst asked:
What is the total captured revenue of the Indonesian business (IDR-denominated orders) from completed orders, in cents?

SQL that was produced and executed successfully:
SELECT SUM(p.amount_cents) AS idr_revenue_cents
            FROM orders o
            JOIN payments p ON p.order_id = o.order_id
            WHERE o.status = 'completed'

MEASURED WAREHOUSE FACTS

Join cardinality (measured, not inferred):
  ! order_items.order_id -> orders.order_id: FANS OUT x2.16 avg, up to x4; 1005 parent keys have >1 child row
  ! orders.customer_id -> customers.customer_id: FANS OUT x3.86 avg, up to x12; 352 parent keys have >1 child row
  ! payments.order_id -> orders.order_id: FANS OUT x1.24 avg, up to x3; 252 parent keys have >1 child row
    refunds.order_id -> orders.order_id: one row per parent (safe to join)

orders: 1500 rows, one row per order_id
  order_id: INTEGER, pk, 1500 distinct
  customer_id: INTEGER, 389 distinct
  order_ts: TEXT, 1493 distinct, range 2026-01-01 02:11:00 .. 2026-03-31 21:27:00
  status: TEXT, NULL in 80 rows (5.3%), 4 distinct
  currency: TEXT, 2 distinct

payments: 1683 rows, one row per payment_id
  payment_id: INTEGER, pk, 1683 distinct
  order_id: INTEGER, 1357 distinct
  amount_cents: INTEGER, 941 distinct
  paid_ts: TEXT, 1672 distinct, range 2026-01-01 03:12:00 .. 2026-05-30 03:21:00
  method: TEXT, 4 distinct

The query returned this result:
idr_revenue_cents
-----------------
5468920000       

List the specific ways this query could fail to answer the business question.
For each one, write a probe: a single read-only SELECT whose output would settle
whether that failure is actually happening in this data.

A good probe measures a consequence. Compare a row count before and after a
join, compare COUNT(*) against COUNT(DISTINCT key), count rows excluded by a
predicate, or compute the requested metric by an independent route and show both
numbers. A probe that merely re-runs the original query settles nothing.

Reply with one JSON object and nothing else:

{
  "hypotheses": [
    {
      "risk": "one sentence, naming the tables or columns involved",
      "bug_type": one of ["fanout_join", "null_swallowing_predicate", "left_join_degraded_to_inner", "date_range_truncation", "timezone_day_boundary", "mixed_unit_aggregation", "missing_filter", "wrong_aggregation_grain", "other"],
      "probe_sql": "a single SELECT, no semicolon",
      "settles": "what result would confirm this, and what would rule it out"
    }
  ]
}

At most 4 hypotheses, ordered by how likely they are given the
measured facts above. If the measured facts already show a table does not fan
out, do not propose a fan-out hypothesis about it.
```

**assistant**

```json
{
  "hypotheses": [
    {
      "risk": "The payments table may contain payments for orders that are not completed.",
      "bug_type": "missing_filter",
      "probe_sql": "SELECT COUNT(*) FROM payments p JOIN orders o ON p.order_id = o.order_id WHERE o.status != 'completed'",
      "settles": "If the count is greater than 0, it confirms the issue; if 0, it rules it out."
    },
    {
      "risk": "The orders table may have completed orders that do not have corresponding payments.",
      "bug_type": "fanout_join",
      "probe_sql": "SELECT COUNT(*) FROM orders o LEFT JOIN payments p ON p.order_id = o.order_id WHERE o.status = 'completed' AND p.order_id IS NULL",
      "settles": "If the count is greater than 0, it confirms the issue; if 0, it rules it out."
    },
    {
      "risk": "The query may be aggregating payments in different currencies without filtering for IDR.",
      "bug_type": "missing_filter",
      "probe_sql": "SELECT SUM(p.amount_cents) AS total_revenue_cents FROM payments p JOIN orders o ON p.order_id = o.order_id WHERE o.status = 'completed' AND o.currency != 'IDR'",
      "settles": "If the total revenue is greater than 0, it confirms the issue; if 0, it rules it out."
    },
    {
      "risk": "The payments table may contain duplicate entries for the same order.",
      "bug_type": "wrong_aggregation_grain",
      "probe_sql": "SELECT order_id, COUNT(*) FROM payments GROUP BY order_id HAVING COUNT(*) > 1",
      "settles": "If any rows are returned, it confirms the issue; if none, it rules it out."
    }
  ]
}
```

## 5. tool · `run_sql` · probe_1 · ok

**request**

```sql
SELECT COUNT(*) FROM payments p JOIN orders o ON p.order_id = o.order_id WHERE o.status != 'completed'
```

**response**

```
COUNT(*)
--------
327     
```

## 6. tool · `run_sql` · probe_2 · ok

**request**

```sql
SELECT COUNT(*) FROM orders o LEFT JOIN payments p ON p.order_id = o.order_id WHERE o.status = 'completed' AND p.order_id IS NULL
```

**response**

```
COUNT(*)
--------
0       
```

## 7. tool · `run_sql` · probe_3 · ok

**request**

```sql
SELECT SUM(p.amount_cents) AS total_revenue_cents FROM payments p JOIN orders o ON p.order_id = o.order_id WHERE o.status = 'completed' AND o.currency != 'IDR'
```

**response**

```
total_revenue_cents
-------------------
725420000          
```

## 8. tool · `run_sql` · probe_4 · ok

**request**

```sql
SELECT order_id, COUNT(*) FROM payments GROUP BY order_id HAVING COUNT(*) > 1
```

**response**

```
order_id | COUNT(*)
---------+---------
2        | 2       
3        | 3       
9        | 2       
11       | 2       
14       | 2       
19       | 3       
24       | 2       
25       | 2       
28       | 3       
32       | 2       
33       | 2       
40       | 3       
... 188 more row(s)
... truncated at 200 rows
```

## 9. model · adjudicate

`gpt-4o-mini` · live call · 1270 in / 138 out · 1.29s

**system**

```
You are a senior analytics engineer signing off on
whether a number can go into a business report. You have executed probes and an
independent recomputation, and you now decide based on what they returned.
```

**user**

```
Business question the analyst asked:
What is the total captured revenue of the Indonesian business (IDR-denominated orders) from completed orders, in cents?

SQL under review:
SELECT SUM(p.amount_cents) AS idr_revenue_cents
            FROM orders o
            JOIN payments p ON p.order_id = o.order_id
            WHERE o.status = 'completed'

Result it returned:
idr_revenue_cents
-----------------
5468920000       

MEASURED WAREHOUSE FACTS

Join cardinality (measured, not inferred):
  ! order_items.order_id -> orders.order_id: FANS OUT x2.16 avg, up to x4; 1005 parent keys have >1 child row
  ! orders.customer_id -> customers.customer_id: FANS OUT x3.86 avg, up to x12; 352 parent keys have >1 child row
  ! payments.order_id -> orders.order_id: FANS OUT x1.24 avg, up to x3; 252 parent keys have >1 child row
    refunds.order_id -> orders.order_id: one row per parent (safe to join)

orders: 1500 rows, one row per order_id
  order_id: INTEGER, pk, 1500 distinct
  customer_id: INTEGER, 389 distinct
  order_ts: TEXT, 1493 distinct, range 2026-01-01 02:11:00 .. 2026-03-31 21:27:00
  status: TEXT, NULL in 80 rows (5.3%), 4 distinct
  currency: TEXT, 2 distinct

payments: 1683 rows, one row per payment_id
  payment_id: INTEGER, pk, 1683 distinct
  order_id: INTEGER, 1357 distinct
  amount_cents: INTEGER, 941 distinct
  paid_ts: TEXT, 1672 distinct, range 2026-01-01 03:12:00 .. 2026-05-30 03:21:00
  method: TEXT, 4 distinct

Probes you designed, and what executing them actually returned:
[1] risk: The payments table may contain payments for orders that are not completed.
    probe: SELECT COUNT(*) FROM payments p JOIN orders o ON p.order_id = o.order_id WHERE o.status != 'completed'
    returned:
    COUNT(*)
    --------
    327     

[2] risk: The orders table may have completed orders that do not have corresponding payments.
    probe: SELECT COUNT(*) FROM orders o LEFT JOIN payments p ON p.order_id = o.order_id WHERE o.status = 'completed' AND p.order_id IS NULL
    returned:
    COUNT(*)
    --------
    0       

[3] risk: The query may be aggregating payments in different currencies without filtering for IDR.
    probe: SELECT SUM(p.amount_cents) AS total_revenue_cents FROM payments p JOIN orders o ON p.order_id = o.order_id WHERE o.status = 'completed' AND o.currency != 'IDR'
    returned:
    total_revenue_cents
    -------------------
    725420000          

[4] risk: The payments table may contain duplicate entries for the same order.
    probe: SELECT order_id, COUNT(*) FROM payments GROUP BY order_id HAVING COUNT(*) > 1
    returned:
    order_id | COUNT(*)
    ---------+---------
    2        | 2       
    3        | 3       
    9        | 2       
    11       | 2       
    14       | 2       
    19       | 3       
    24       | 2       
    25       | 2       
    28       | 3       
    32       | 2       
    33       | 2       
    40       | 3       
    ... 188 more row(s)
    ... truncated at 200 rows

Independent recomputation: not attempted.

Decide the verdict from what was executed, not from how the SQL looks.

* The recomputation above is the strongest evidence available. If it returns a
  different number from the query under review, the two disagree and the
  reported number cannot be trusted. If it returns the same number, two
  independent derivations agree.
* Judge against the business question. Joining to a finer grain is a bug when
  the requested metric is coarser, and correct when the metric genuinely lives
  at that finer grain.
* If you answer BUG, corrected_sql is mandatory and will be executed.

Reply with one JSON object and nothing else:

{
  "verdict": "CLEAN" | "BUG" | "ESCALATE",
  "bug_type": one of ["fanout_join", "null_swallowing_predicate", "left_join_degraded_to_inner", "date_range_truncation", "timezone_day_boundary", "mixed_unit_aggregation", "missing_filter", "wrong_aggregation_grain", "other"] or null,
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
actually lives at that finer grain.
```

**assistant**

```json
{
  "verdict": "BUG",
  "bug_type": "mixed_unit_aggregation",
  "confidence": 0.8,
  "explanation": "The query aggregates payments without filtering for the IDR currency, as evidenced by probe [3] which shows significant revenue in other currencies. Additionally, probe [1] indicates that there are payments for orders that are not completed, which could further skew the results.",
  "corrected_sql": "SELECT SUM(p.amount_cents) AS idr_revenue_cents FROM orders o JOIN payments p ON p.order_id = o.order_id WHERE o.status = 'completed' AND o.currency = 'IDR'"
}
```

## 10. tool · `run_sql` · gate_execute_correction · ok

**request**

```sql
SELECT SUM(p.amount_cents) AS idr_revenue_cents FROM orders o JOIN payments p ON p.order_id = o.order_id WHERE o.status = 'completed' AND o.currency = 'IDR'
```

**response**

```
idr_revenue_cents
-----------------
4743500000       
```

## 11. gate · verification_gate

**BUG** — the correction executes and returns a different result, so the discrepancy is demonstrated

```json
{
  "reported": "idr_revenue_cents\n-----------------\n5468920000       ",
  "corrected": "idr_revenue_cents\n-----------------\n4743500000       "
}
```
