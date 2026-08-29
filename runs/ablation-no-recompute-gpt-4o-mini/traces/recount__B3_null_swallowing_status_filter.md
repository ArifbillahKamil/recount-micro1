# Trajectory — recount — B3_null_swallowing_status_filter

`2` model calls (`1` replayed from cassette) · `7` tool calls · `2166` tokens · `$0.00055`

## 1. tool · `run_sql` · execute_under_review · ok

**request**

```sql

            SELECT COUNT(*) AS active_orders
            FROM orders
            WHERE status != 'cancelled'
        
```

**response**

```
active_orders
-------------
1277         
```

## 2. tool · `profiler.profile` · profile_warehouse · ok

**request**

```json
{
  "tables": [
    "orders"
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
```

## 3. note · recompute_disabled

Independent recomputation disabled for this run.

## 4. model · plan

`gpt-4o-mini` · replayed · 649 in / 393 out · 0.00s

**system**

```
You are a senior analytics engineer who has been burned by
queries that run cleanly and return the wrong number. You do not speculate: you
design a measurement that would settle each suspicion.
```

**user**

```
Business question the analyst asked:
How many orders are not cancelled? Orders whose status was never stamped by fulfilment are still live business, so count them.

SQL that was produced and executed successfully:
SELECT COUNT(*) AS active_orders
            FROM orders
            WHERE status != 'cancelled'

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

The query returned this result:
active_orders
-------------
1277         

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
      "risk": "The status column in the orders table contains NULL values that are not counted in the active orders",
      "bug_type": "null_swallowing_predicate",
      "probe_sql": "SELECT COUNT(*) AS null_status_count FROM orders WHERE status IS NULL",
      "settles": "If null_status_count is greater than 0, it confirms the risk; if it is 0, it rules it out."
    },
    {
      "risk": "The query does not account for orders that have a status of NULL, which should be considered active",
      "bug_type": "missing_filter",
      "probe_sql": "SELECT COUNT(*) AS total_orders FROM orders WHERE status IS NULL OR status != 'cancelled'",
      "settles": "If total_orders is greater than 1277, it confirms the risk; if it is equal to 1277, it rules it out."
    },
    {
      "risk": "The query may not accurately reflect the number of active orders due to potential duplicates in related tables affecting the count",
      "bug_type": "fanout_join",
      "probe_sql": "SELECT COUNT(DISTINCT order_id) AS distinct_active_orders FROM orders WHERE status != 'cancelled'",
      "settles": "If distinct_active_orders is less than 1277, it confirms the risk; if it is equal to 1277, it rules it out."
    },
    {
      "risk": "The query does not consider the possibility of orders being cancelled after the initial status was set",
      "bug_type": "other",
      "probe_sql": "SELECT COUNT(*) AS cancelled_orders FROM orders WHERE status = 'cancelled'",
      "settles": "If cancelled_orders is greater than 0, it confirms the risk; if it is 0, it rules it out."
    }
  ]
}
```

## 5. tool · `run_sql` · probe_1 · ok

**request**

```sql
SELECT COUNT(*) AS null_status_count FROM orders WHERE status IS NULL
```

**response**

```
null_status_count
-----------------
80               
```

## 6. tool · `run_sql` · probe_2 · ok

**request**

```sql
SELECT COUNT(*) AS total_orders FROM orders WHERE status IS NULL OR status != 'cancelled'
```

**response**

```
total_orders
------------
1357        
```

## 7. tool · `run_sql` · probe_3 · ok

**request**

```sql
SELECT COUNT(DISTINCT order_id) AS distinct_active_orders FROM orders WHERE status != 'cancelled'
```

**response**

```
distinct_active_orders
----------------------
1277                  
```

## 8. tool · `run_sql` · probe_4 · ok

**request**

```sql
SELECT COUNT(*) AS cancelled_orders FROM orders WHERE status = 'cancelled'
```

**response**

```
cancelled_orders
----------------
143             
```

## 9. model · adjudicate

`gpt-4o-mini` · live call · 1010 in / 114 out · 1.74s

**system**

```
You are a senior analytics engineer signing off on
whether a number can go into a business report. You have executed probes and an
independent recomputation, and you now decide based on what they returned.
```

**user**

```
Business question the analyst asked:
How many orders are not cancelled? Orders whose status was never stamped by fulfilment are still live business, so count them.

SQL under review:
SELECT COUNT(*) AS active_orders
            FROM orders
            WHERE status != 'cancelled'

Result it returned:
active_orders
-------------
1277         

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

Probes you designed, and what executing them actually returned:
[1] risk: The status column in the orders table contains NULL values that are not counted in the active orders
    probe: SELECT COUNT(*) AS null_status_count FROM orders WHERE status IS NULL
    returned:
    null_status_count
    -----------------
    80               

[2] risk: The query does not account for orders that have a status of NULL, which should be considered active
    probe: SELECT COUNT(*) AS total_orders FROM orders WHERE status IS NULL OR status != 'cancelled'
    returned:
    total_orders
    ------------
    1357        

[3] risk: The query may not accurately reflect the number of active orders due to potential duplicates in related tables affecting the count
    probe: SELECT COUNT(DISTINCT order_id) AS distinct_active_orders FROM orders WHERE status != 'cancelled'
    returned:
    distinct_active_orders
    ----------------------
    1277                  

[4] risk: The query does not consider the possibility of orders being cancelled after the initial status was set
    probe: SELECT COUNT(*) AS cancelled_orders FROM orders WHERE status = 'cancelled'
    returned:
    cancelled_orders
    ----------------
    143             

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
  "bug_type": "null_swallowing_predicate",
  "confidence": 0.9,
  "explanation": "The query does not account for orders with a NULL status, which should be considered active. The probe confirmed that there are 80 orders with a NULL status that are not included in the count. Therefore, the reported number of active orders is inaccurate.",
  "corrected_sql": "SELECT COUNT(*) AS active_orders FROM orders WHERE status IS NULL OR status != 'cancelled'"
}
```

## 10. tool · `run_sql` · gate_execute_correction · ok

**request**

```sql
SELECT COUNT(*) AS active_orders FROM orders WHERE status IS NULL OR status != 'cancelled'
```

**response**

```
active_orders
-------------
1357         
```

## 11. gate · verification_gate

**BUG** — the correction executes and returns a different result, so the discrepancy is demonstrated

```json
{
  "reported": "active_orders\n-------------\n1277         ",
  "corrected": "active_orders\n-------------\n1357         "
}
```
