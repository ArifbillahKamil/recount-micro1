# Trajectory — recount — C2_clean_units_sold_at_line_grain

`3` model calls (`3` replayed from cassette) · `7` tool calls · `3180` tokens · `$0.00078`

## 1. tool · `run_sql` · execute_under_review · ok

**request**

```sql

            SELECT SUM(oi.quantity) AS units_sold
            FROM orders o
            JOIN order_items oi ON oi.order_id = o.order_id
            WHERE o.status = 'completed'
        
```

**response**

```
units_sold
----------
2993      
```

## 2. tool · `profiler.profile` · profile_warehouse · ok

**request**

```json
{
  "tables": [
    "order_items",
    "orders"
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
  ! order_items.product_id -> products.product_id: FANS OUT x54.07 avg, up to x73; 60 parent keys have >1 child row
  ! orders.customer_id -> customers.customer_id: FANS OUT x3.86 avg, up to x12; 352 parent keys have >1 child row
  ! payments.order_id -> orders.order_id: FANS OUT x1.24 avg, up to x3; 252 parent keys have >1 child row
    refunds.order_id -> orders.order_id: one row per parent (safe to join)

order_items: 3244 rows, one row per order_item_id
  order_item_id: INTEGER, pk, 3244 distinct
  order_id: INTEGER, 1500 distinct
  product_id: INTEGER, 60 distinct
  quantity: INTEGER, 3 distinct
  unit_price_cents: INTEGER, 57 distinct

orders: 1500 rows, one row per order_id
  order_id: INTEGER, pk, 1500 distinct
  customer_id: INTEGER, 389 distinct
  order_ts: TEXT, 1493 distinct, range 2026-01-01 02:11:00 .. 2026-03-31 21:27:00
  status: TEXT, NULL in 80 rows (5.3%), 4 distinct
  currency: TEXT, 2 distinct
```

## 3. model · recompute

`gpt-4o-mini` · replayed · 421 in / 62 out · 0.00s

**system**

```
You are a senior analytics engineer. You are handed a
business question and the measured facts about a warehouse, and you write the
query that answers it. You are not reviewing anyone's work: you are deriving the
answer independently.
```

**user**

```
Business question:
How many units did we sell across completed orders?

MEASURED COLUMN FACTS

order_items: 3244 rows, one row per order_item_id
  order_item_id: INTEGER, pk, 3244 distinct
  order_id: INTEGER, 1500 distinct
  product_id: INTEGER, 60 distinct
  quantity: INTEGER, 3 distinct
  unit_price_cents: INTEGER, 57 distinct

orders: 1500 rows, one row per order_id
  order_id: INTEGER, pk, 1500 distinct
  customer_id: INTEGER, 389 distinct
  order_ts: TEXT, 1493 distinct, values run '2026-01-01 02:11:00' .. '2026-03-31 21:27:00'
  status: TEXT, NULL in 80 rows (5.3%) -- a predicate on this column must handle NULL explicitly, 4 distinct
  currency: TEXT, 2 distinct

Match the stored format exactly when you write a literal. The quoted ranges above show how values are actually stored; comparing against a differently formatted string compares text, not time, and silently selects the wrong rows.

Write a single read-only SQL query that answers this question against this
SQLite warehouse.

Derive it from the question and the measured facts above. Pay attention to the
grain of each measure, to columns that are nullable in practice, and to the
stored format of any value you compare against.

Return exactly these columns, in this order, with these names:
units_sold

Reply with one JSON object and nothing else:

{"sql": "a single SELECT, no semicolon", "reasoning": "one sentence on the grain and filters you chose"}
```

**assistant**

```json
{"sql": "SELECT SUM(quantity) AS units_sold FROM order_items oi JOIN orders o ON oi.order_id = o.order_id WHERE o.status IS NOT NULL", "reasoning": "I summed the quantity from order_items where the corresponding orders have a non-null status to count only completed orders."}
```

## 4. tool · `run_sql` · recompute · ok

**request**

```sql
SELECT SUM(quantity) AS units_sold FROM order_items oi JOIN orders o ON oi.order_id = o.order_id WHERE o.status IS NOT NULL
```

**response**

```
units_sold
----------
4212      
```

## 5. model · plan

`gpt-4o-mini` · replayed · 759 in / 492 out · 0.00s

**system**

```
You are a senior analytics engineer who has been burned by
queries that run cleanly and return the wrong number. You do not speculate: you
design a measurement that would settle each suspicion.
```

**user**

```
Business question the analyst asked:
How many units did we sell across completed orders?

SQL that was produced and executed successfully:
SELECT SUM(oi.quantity) AS units_sold
            FROM orders o
            JOIN order_items oi ON oi.order_id = o.order_id
            WHERE o.status = 'completed'

MEASURED WAREHOUSE FACTS

Join cardinality (measured, not inferred):
  ! order_items.order_id -> orders.order_id: FANS OUT x2.16 avg, up to x4; 1005 parent keys have >1 child row
  ! order_items.product_id -> products.product_id: FANS OUT x54.07 avg, up to x73; 60 parent keys have >1 child row
  ! orders.customer_id -> customers.customer_id: FANS OUT x3.86 avg, up to x12; 352 parent keys have >1 child row
  ! payments.order_id -> orders.order_id: FANS OUT x1.24 avg, up to x3; 252 parent keys have >1 child row
    refunds.order_id -> orders.order_id: one row per parent (safe to join)

order_items: 3244 rows, one row per order_item_id
  order_item_id: INTEGER, pk, 3244 distinct
  order_id: INTEGER, 1500 distinct
  product_id: INTEGER, 60 distinct
  quantity: INTEGER, 3 distinct
  unit_price_cents: INTEGER, 57 distinct

orders: 1500 rows, one row per order_id
  order_id: INTEGER, pk, 1500 distinct
  customer_id: INTEGER, 389 distinct
  order_ts: TEXT, 1493 distinct, range 2026-01-01 02:11:00 .. 2026-03-31 21:27:00
  status: TEXT, NULL in 80 rows (5.3%), 4 distinct
  currency: TEXT, 2 distinct

The query returned this result:
units_sold
----------
2993      

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
      "risk": "The join between orders and order_items may be causing a fanout issue due to multiple order_items per order.",
      "bug_type": "fanout_join",
      "probe_sql": "SELECT COUNT(DISTINCT o.order_id) AS distinct_orders, COUNT(oi.order_id) AS total_order_items FROM orders o JOIN order_items oi ON oi.order_id = o.order_id WHERE o.status = 'completed'",
      "settles": "If distinct_orders is significantly less than total_order_items, it confirms a fanout issue. If they are close, it rules it out."
    },
    {
      "risk": "Some completed orders may have NULL values in the order_items table, leading to an undercount of units sold.",
      "bug_type": "null_swallowing_predicate",
      "probe_sql": "SELECT COUNT(*) AS total_completed_orders, COUNT(oi.order_id) AS total_order_items FROM orders o LEFT JOIN order_items oi ON oi.order_id = o.order_id WHERE o.status = 'completed'",
      "settles": "If total_completed_orders is greater than total_order_items, it confirms that some completed orders have no associated order_items. If they are equal, it rules it out."
    },
    {
      "risk": "The query may be missing orders that were completed but have been excluded due to a status filter.",
      "bug_type": "missing_filter",
      "probe_sql": "SELECT COUNT(*) AS total_orders FROM orders WHERE status = 'completed'",
      "settles": "If total_orders matches the expected number of completed orders, it rules out missing orders. If it is higher than expected, it confirms the issue."
    },
    {
      "risk": "The aggregation of quantities may be incorrect due to the presence of multiple order_items for the same order.",
      "bug_type": "wrong_aggregation_grain",
      "probe_sql": "SELECT SUM(oi.quantity) AS total_units_sold, COUNT(DISTINCT o.order_id) AS distinct_orders FROM orders o JOIN order_items oi ON oi.order_id = o.order_id WHERE o.status = 'completed'",
      "settles": "If total_units_sold divided by distinct_orders is greater than the average quantity per order, it confirms a wrong aggregation grain. If it is consistent, it rules it out."
    }
  ]
}
```

## 6. tool · `run_sql` · probe_1 · ok

**request**

```sql
SELECT COUNT(DISTINCT o.order_id) AS distinct_orders, COUNT(oi.order_id) AS total_order_items FROM orders o JOIN order_items oi ON oi.order_id = o.order_id WHERE o.status = 'completed'
```

**response**

```
distinct_orders | total_order_items
----------------+------------------
1018            | 2169             
```

## 7. tool · `run_sql` · probe_2 · ok

**request**

```sql
SELECT COUNT(*) AS total_completed_orders, COUNT(oi.order_id) AS total_order_items FROM orders o LEFT JOIN order_items oi ON oi.order_id = o.order_id WHERE o.status = 'completed'
```

**response**

```
total_completed_orders | total_order_items
-----------------------+------------------
2169                   | 2169             
```

## 8. tool · `run_sql` · probe_3 · ok

**request**

```sql
SELECT COUNT(*) AS total_orders FROM orders WHERE status = 'completed'
```

**response**

```
total_orders
------------
1018        
```

## 9. tool · `run_sql` · probe_4 · ok

**request**

```sql
SELECT SUM(oi.quantity) AS total_units_sold, COUNT(DISTINCT o.order_id) AS distinct_orders FROM orders o JOIN order_items oi ON oi.order_id = o.order_id WHERE o.status = 'completed'
```

**response**

```
total_units_sold | distinct_orders
-----------------+----------------
2993             | 1018           
```

## 10. model · adjudicate

`gpt-4o-mini` · replayed · 1319 in / 127 out · 0.00s

**system**

```
You are a senior analytics engineer signing off on
whether a number can go into a business report. You have executed probes and an
independent recomputation, and you now decide based on what they returned.
```

**user**

```
Business question the analyst asked:
How many units did we sell across completed orders?

SQL under review:
SELECT SUM(oi.quantity) AS units_sold
            FROM orders o
            JOIN order_items oi ON oi.order_id = o.order_id
            WHERE o.status = 'completed'

Result it returned:
units_sold
----------
2993      

MEASURED WAREHOUSE FACTS

Join cardinality (measured, not inferred):
  ! order_items.order_id -> orders.order_id: FANS OUT x2.16 avg, up to x4; 1005 parent keys have >1 child row
  ! order_items.product_id -> products.product_id: FANS OUT x54.07 avg, up to x73; 60 parent keys have >1 child row
  ! orders.customer_id -> customers.customer_id: FANS OUT x3.86 avg, up to x12; 352 parent keys have >1 child row
  ! payments.order_id -> orders.order_id: FANS OUT x1.24 avg, up to x3; 252 parent keys have >1 child row
    refunds.order_id -> orders.order_id: one row per parent (safe to join)

order_items: 3244 rows, one row per order_item_id
  order_item_id: INTEGER, pk, 3244 distinct
  order_id: INTEGER, 1500 distinct
  product_id: INTEGER, 60 distinct
  quantity: INTEGER, 3 distinct
  unit_price_cents: INTEGER, 57 distinct

orders: 1500 rows, one row per order_id
  order_id: INTEGER, pk, 1500 distinct
  customer_id: INTEGER, 389 distinct
  order_ts: TEXT, 1493 distinct, range 2026-01-01 02:11:00 .. 2026-03-31 21:27:00
  status: TEXT, NULL in 80 rows (5.3%), 4 distinct
  currency: TEXT, 2 distinct

Probes you designed, and what executing them actually returned:
[1] risk: The join between orders and order_items may be causing a fanout issue due to multiple order_items per order.
    probe: SELECT COUNT(DISTINCT o.order_id) AS distinct_orders, COUNT(oi.order_id) AS total_order_items FROM orders o JOIN order_items oi ON oi.order_id = o.order_id WHERE o.status = 'completed'
    returned:
    distinct_orders | total_order_items
    ----------------+------------------
    1018            | 2169             

[2] risk: Some completed orders may have NULL values in the order_items table, leading to an undercount of units sold.
    probe: SELECT COUNT(*) AS total_completed_orders, COUNT(oi.order_id) AS total_order_items FROM orders o LEFT JOIN order_items oi ON oi.order_id = o.order_id WHERE o.status = 'completed'
    returned:
    total_completed_orders | total_order_items
    -----------------------+------------------
    2169                   | 2169             

[3] risk: The query may be missing orders that were completed but have been excluded due to a status filter.
    probe: SELECT COUNT(*) AS total_orders FROM orders WHERE status = 'completed'
    returned:
    total_orders
    ------------
    1018        

[4] risk: The aggregation of quantities may be incorrect due to the presence of multiple order_items for the same order.
    probe: SELECT SUM(oi.quantity) AS total_units_sold, COUNT(DISTINCT o.order_id) AS distinct_orders FROM orders o JOIN order_items oi ON oi.order_id = o.order_id WHERE o.status = 'completed'
    returned:
    total_units_sold | distinct_orders
    -----------------+----------------
    2993             | 1018           

An independent recomputation was derived from the business question alone, without seeing the query under review, then executed:

  sql: SELECT SUM(quantity) AS units_sold FROM order_items oi JOIN orders o ON oi.order_id = o.order_id WHERE o.status IS NOT NULL
  returned:
    units_sold
    ----------
    4212      

  the query under review returned:
    units_sold
    ----------
    2993      

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
  "bug_type": "wrong_aggregation_grain",
  "confidence": 0.9,
  "explanation": "The query under review aggregates units sold from the order_items table based on completed orders, but the independent recomputation indicates a higher total of units sold. This suggests that the query may be missing some completed orders or order items, leading to an undercount.",
  "corrected_sql": "SELECT SUM(oi.quantity) AS units_sold FROM order_items oi JOIN orders o ON oi.order_id = o.order_id WHERE o.status = 'completed'"
}
```

## 11. note · correction

The reviewer's correction returns the original number, so it repairs nothing; using the independently derived query instead.

## 12. gate · verification_gate

**BUG** — an independently derived query returns a different number, demonstrating the discrepancy

```json
{
  "reported": "units_sold\n----------\n2993      ",
  "recomputed": "units_sold\n----------\n4212      "
}
```
