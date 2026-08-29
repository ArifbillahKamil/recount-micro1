# Trajectory — recount — B8_missing_status_filter

`3` model calls (`1` replayed from cassette) · `6` tool calls · `3479` tokens · `$0.00083`

## 1. tool · `run_sql` · execute_under_review · ok

**request**

```sql

            SELECT SUM(p.amount_cents) AS revenue_cents
            FROM orders o
            JOIN payments p ON p.order_id = o.order_id
        
```

**response**

```
revenue_cents
-------------
7301960000   
```

## 2. note · profile_disabled

Warehouse profiling disabled; both roles see the schema only.

## 3. note · formats_disabled

Stored value formats withheld from the author for this run.

## 4. model · recompute

`gpt-4o-mini` · replayed · 627 in / 83 out · 0.00s

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
What revenue did we capture from completed orders only, in cents?

SCHEMA

CREATE TABLE customers (
    customer_id   INTEGER PRIMARY KEY,
    name          TEXT    NOT NULL,
    country       TEXT    NOT NULL,
    signup_ts     TEXT    NOT NULL   -- ISO-8601 UTC
);

CREATE TABLE marketing_spend (
    spend_date  TEXT    NOT NULL,
    channel     TEXT    NOT NULL,
    spend_cents INTEGER NOT NULL,
    PRIMARY KEY (spend_date, channel)
);

CREATE TABLE order_items (
    order_item_id    INTEGER PRIMARY KEY,
    order_id         INTEGER NOT NULL REFERENCES orders(order_id),
    product_id       INTEGER NOT NULL REFERENCES products(product_id),
    quantity         INTEGER NOT NULL,
    unit_price_cents INTEGER NOT NULL
);

CREATE TABLE orders (
    order_id    INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(customer_id),
    order_ts    TEXT    NOT NULL,   -- ISO-8601 UTC
    status      TEXT,               -- nullable on purpose
    currency    TEXT    NOT NULL    -- 'IDR' or 'USD'
);

CREATE TABLE payments (
    payment_id   INTEGER PRIMARY KEY,
    order_id     INTEGER NOT NULL REFERENCES orders(order_id),
    amount_cents INTEGER NOT NULL,
    paid_ts      TEXT    NOT NULL,
    method       TEXT    NOT NULL
);

CREATE TABLE products (
    product_id       INTEGER PRIMARY KEY,
    name             TEXT    NOT NULL,
    category         TEXT    NOT NULL,
    list_price_cents INTEGER NOT NULL
);

CREATE TABLE refunds (
    refund_id    INTEGER PRIMARY KEY,
    order_id     INTEGER NOT NULL REFERENCES orders(order_id),
    amount_cents INTEGER NOT NULL,
    refund_ts    TEXT    NOT NULL,
    reason       TEXT    NOT NULL
);

CREATE TABLE sessions (
    session_id  INTEGER PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(customer_id),
    session_ts  TEXT    NOT NULL,
    channel     TEXT    NOT NULL
);

Write a single read-only SQL query that answers this question against this
SQLite warehouse.

Derive it from the question and the measured facts above. Pay attention to the
grain of each measure, to columns that are nullable in practice, and to the
stored format of any value you compare against.

The result must not depend on where or when the query runs. Do not use
'localtime', 'now', CURRENT_DATE or random(): use an explicit offset such as
date(col, '+7 hours') and literal dates.

Return exactly these columns, in this order, with these names:
revenue_cents

Reply with one JSON object and nothing else:

{"sql": "a single SELECT, no semicolon", "reasoning": "one sentence on the grain and filters you chose"}
```

**assistant**

```json
{"sql": "SELECT SUM(oi.quantity * oi.unit_price_cents) AS revenue_cents FROM orders o JOIN order_items oi ON o.order_id = oi.order_id WHERE o.status = 'completed'", "reasoning": "The query calculates the total revenue from completed orders by summing the product of quantity and unit price for each order item associated with orders that have a status of 'completed'."}
```

## 5. tool · `run_sql` · recompute · ok

**request**

```sql
SELECT SUM(oi.quantity * oi.unit_price_cents) AS revenue_cents FROM orders o JOIN order_items oi ON o.order_id = oi.order_id WHERE o.status = 'completed'
```

**response**

```
revenue_cents
-------------
5468920000   
```

## 6. model · plan

`gpt-4o-mini` · live call · 797 in / 460 out · 3.55s

**system**

```
You are a senior analytics engineer who has been burned by
queries that run cleanly and return the wrong number. You do not speculate: you
design a measurement that would settle each suspicion.
```

**user**

```
Business question the analyst asked:
What revenue did we capture from completed orders only, in cents?

SQL that was produced and executed successfully:
SELECT SUM(p.amount_cents) AS revenue_cents
            FROM orders o
            JOIN payments p ON p.order_id = o.order_id

SCHEMA

CREATE TABLE customers (
    customer_id   INTEGER PRIMARY KEY,
    name          TEXT    NOT NULL,
    country       TEXT    NOT NULL,
    signup_ts     TEXT    NOT NULL   -- ISO-8601 UTC
);

CREATE TABLE marketing_spend (
    spend_date  TEXT    NOT NULL,
    channel     TEXT    NOT NULL,
    spend_cents INTEGER NOT NULL,
    PRIMARY KEY (spend_date, channel)
);

CREATE TABLE order_items (
    order_item_id    INTEGER PRIMARY KEY,
    order_id         INTEGER NOT NULL REFERENCES orders(order_id),
    product_id       INTEGER NOT NULL REFERENCES products(product_id),
    quantity         INTEGER NOT NULL,
    unit_price_cents INTEGER NOT NULL
);

CREATE TABLE orders (
    order_id    INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(customer_id),
    order_ts    TEXT    NOT NULL,   -- ISO-8601 UTC
    status      TEXT,               -- nullable on purpose
    currency    TEXT    NOT NULL    -- 'IDR' or 'USD'
);

CREATE TABLE payments (
    payment_id   INTEGER PRIMARY KEY,
    order_id     INTEGER NOT NULL REFERENCES orders(order_id),
    amount_cents INTEGER NOT NULL,
    paid_ts      TEXT    NOT NULL,
    method       TEXT    NOT NULL
);

CREATE TABLE products (
    product_id       INTEGER PRIMARY KEY,
    name             TEXT    NOT NULL,
    category         TEXT    NOT NULL,
    list_price_cents INTEGER NOT NULL
);

CREATE TABLE refunds (
    refund_id    INTEGER PRIMARY KEY,
    order_id     INTEGER NOT NULL REFERENCES orders(order_id),
    amount_cents INTEGER NOT NULL,
    refund_ts    TEXT    NOT NULL,
    reason       TEXT    NOT NULL
);

CREATE TABLE sessions (
    session_id  INTEGER PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(customer_id),
    session_ts  TEXT    NOT NULL,
    channel     TEXT    NOT NULL
);

The query returned this result:
revenue_cents
-------------
7301960000   

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
      "risk": "The query may include payments for orders that are not completed due to missing a filter on the orders table.",
      "bug_type": "missing_filter",
      "probe_sql": "SELECT COUNT(*) FROM orders WHERE status IS NULL OR status != 'completed'",
      "settles": "A non-zero count would confirm this, indicating there are orders not marked as completed. A count of zero would rule it out."
    },
    {
      "risk": "The query may include payments for orders that have been refunded, leading to inflated revenue figures.",
      "bug_type": "wrong_aggregation_grain",
      "probe_sql": "SELECT SUM(p.amount_cents) - COALESCE(SUM(r.amount_cents), 0) AS net_revenue_cents FROM orders o JOIN payments p ON p.order_id = o.order_id LEFT JOIN refunds r ON r.order_id = o.order_id WHERE o.status = 'completed'",
      "settles": "If this net revenue is less than the original revenue_cents, it confirms the issue. If they are equal, it rules it out."
    },
    {
      "risk": "The query may double count payments if there are multiple payments for a single order.",
      "bug_type": "fanout_join",
      "probe_sql": "SELECT COUNT(DISTINCT o.order_id) AS distinct_orders, COUNT(p.payment_id) AS total_payments FROM orders o JOIN payments p ON p.order_id = o.order_id WHERE o.status = 'completed'",
      "settles": "If distinct_orders is less than total_payments, it confirms the issue. If they are equal, it rules it out."
    },
    {
      "risk": "The query may not account for currency differences if orders are in different currencies.",
      "bug_type": "mixed_unit_aggregation",
      "probe_sql": "SELECT currency, SUM(amount_cents) AS total_revenue_cents FROM payments p JOIN orders o ON p.order_id = o.order_id GROUP BY currency",
      "settles": "If there are multiple currencies returned, it confirms the issue. If only one currency is returned, it rules it out."
    }
  ]
}
```

## 7. tool · `run_sql` · probe_1 · ok

**request**

```sql
SELECT COUNT(*) FROM orders WHERE status IS NULL OR status != 'completed'
```

**response**

```
COUNT(*)
--------
482     
```

## 8. tool · `run_sql` · probe_2 · ok

**request**

```sql
SELECT SUM(p.amount_cents) - COALESCE(SUM(r.amount_cents), 0) AS net_revenue_cents FROM orders o JOIN payments p ON p.order_id = o.order_id LEFT JOIN refunds r ON r.order_id = o.order_id WHERE o.status = 'completed'
```

**response**

```
net_revenue_cents
-----------------
5416250000       
```

## 9. tool · `run_sql` · probe_3 · ok

**request**

```sql
SELECT COUNT(DISTINCT o.order_id) AS distinct_orders, COUNT(p.payment_id) AS total_payments FROM orders o JOIN payments p ON p.order_id = o.order_id WHERE o.status = 'completed'
```

**response**

```
distinct_orders | total_payments
----------------+---------------
1018            | 1250          
```

## 10. tool · `run_sql` · probe_4 · ok

**request**

```sql
SELECT currency, SUM(amount_cents) AS total_revenue_cents FROM payments p JOIN orders o ON p.order_id = o.order_id GROUP BY currency
```

**response**

```
currency | total_revenue_cents
---------+--------------------
IDR      | 6363960000         
USD      | 938000000          
```

## 11. model · adjudicate

`gpt-4o-mini` · live call · 1362 in / 150 out · 1.90s

**system**

```
You are a senior analytics engineer signing off on
whether a number can go into a business report. You have executed probes and an
independent recomputation, and you now decide based on what they returned.
```

**user**

```
Business question the analyst asked:
What revenue did we capture from completed orders only, in cents?

SQL under review:
SELECT SUM(p.amount_cents) AS revenue_cents
            FROM orders o
            JOIN payments p ON p.order_id = o.order_id

Result it returned:
revenue_cents
-------------
7301960000   

SCHEMA

CREATE TABLE customers (
    customer_id   INTEGER PRIMARY KEY,
    name          TEXT    NOT NULL,
    country       TEXT    NOT NULL,
    signup_ts     TEXT    NOT NULL   -- ISO-8601 UTC
);

CREATE TABLE marketing_spend (
    spend_date  TEXT    NOT NULL,
    channel     TEXT    NOT NULL,
    spend_cents INTEGER NOT NULL,
    PRIMARY KEY (spend_date, channel)
);

CREATE TABLE order_items (
    order_item_id    INTEGER PRIMARY KEY,
    order_id         INTEGER NOT NULL REFERENCES orders(order_id),
    product_id       INTEGER NOT NULL REFERENCES products(product_id),
    quantity         INTEGER NOT NULL,
    unit_price_cents INTEGER NOT NULL
);

CREATE TABLE orders (
    order_id    INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(customer_id),
    order_ts    TEXT    NOT NULL,   -- ISO-8601 UTC
    status      TEXT,               -- nullable on purpose
    currency    TEXT    NOT NULL    -- 'IDR' or 'USD'
);

CREATE TABLE payments (
    payment_id   INTEGER PRIMARY KEY,
    order_id     INTEGER NOT NULL REFERENCES orders(order_id),
    amount_cents INTEGER NOT NULL,
    paid_ts      TEXT    NOT NULL,
    method       TEXT    NOT NULL
);

CREATE TABLE products (
    product_id       INTEGER PRIMARY KEY,
    name             TEXT    NOT NULL,
    category         TEXT    NOT NULL,
    list_price_cents INTEGER NOT NULL
);

CREATE TABLE refunds (
    refund_id    INTEGER PRIMARY KEY,
    order_id     INTEGER NOT NULL REFERENCES orders(order_id),
    amount_cents INTEGER NOT NULL,
    refund_ts    TEXT    NOT NULL,
    reason       TEXT    NOT NULL
);

CREATE TABLE sessions (
    session_id  INTEGER PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(customer_id),
    session_ts  TEXT    NOT NULL,
    channel     TEXT    NOT NULL
);

Probes you designed, and what executing them actually returned:
[1] risk: The query may include payments for orders that are not completed due to missing a filter on the orders table.
    probe: SELECT COUNT(*) FROM orders WHERE status IS NULL OR status != 'completed'
    returned:
    COUNT(*)
    --------
    482     

[2] risk: The query may include payments for orders that have been refunded, leading to inflated revenue figures.
    probe: SELECT SUM(p.amount_cents) - COALESCE(SUM(r.amount_cents), 0) AS net_revenue_cents FROM orders o JOIN payments p ON p.order_id = o.order_id LEFT JOIN refunds r ON r.order_id = o.order_id WHERE o.status = 'completed'
    returned:
    net_revenue_cents
    -----------------
    5416250000       

[3] risk: The query may double count payments if there are multiple payments for a single order.
    probe: SELECT COUNT(DISTINCT o.order_id) AS distinct_orders, COUNT(p.payment_id) AS total_payments FROM orders o JOIN payments p ON p.order_id = o.order_id WHERE o.status = 'completed'
    returned:
    distinct_orders | total_payments
    ----------------+---------------
    1018            | 1250          

[4] risk: The query may not account for currency differences if orders are in different currencies.
    probe: SELECT currency, SUM(amount_cents) AS total_revenue_cents FROM payments p JOIN orders o ON p.order_id = o.order_id GROUP BY currency
    returned:
    currency | total_revenue_cents
    ---------+--------------------
    IDR      | 6363960000         
    USD      | 938000000          

An independent recomputation was derived from the business question alone, without seeing the query under review, then executed:

  sql: SELECT SUM(oi.quantity * oi.unit_price_cents) AS revenue_cents FROM orders o JOIN order_items oi ON o.order_id = oi.order_id WHERE o.status = 'completed'
  returned:
    revenue_cents
    -------------
    5468920000   

  the query under review returned:
    revenue_cents
    -------------
    7301960000   

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
  "bug_type": "missing_filter",
  "confidence": 0.9,
  "explanation": "The query does not filter for completed orders, which leads to including payments from orders that are not completed. Additionally, the independent recomputation from the order_items table shows a significantly different revenue figure, indicating the original query's result cannot be trusted.",
  "corrected_sql": "SELECT SUM(p.amount_cents) - COALESCE(SUM(r.amount_cents), 0) AS net_revenue_cents FROM orders o JOIN payments p ON p.order_id = o.order_id LEFT JOIN refunds r ON r.order_id = o.order_id WHERE o.status = 'completed'"
}
```

## 12. note · correction

The reviewer's correction and the independent derivation disagree on the corrected value; both are reported.

## 13. gate · verification_gate

**BUG** — an independently derived query returns a different number, demonstrating the discrepancy

```json
{
  "reported": "revenue_cents\n-------------\n7301960000   ",
  "recomputed": "revenue_cents\n-------------\n5468920000   "
}
```
