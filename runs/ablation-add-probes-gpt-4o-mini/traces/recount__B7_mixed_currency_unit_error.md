# Trajectory — recount — B7_mixed_currency_unit_error

`3` model calls (`1` replayed from cassette) · `7` tool calls · `3619` tokens · `$0.00085`

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

## 2. note · profile_disabled

Warehouse profiling disabled; both roles see the schema only.

## 3. tool · `profiler.format_hints` · value_formats · ok

**request**

```json
{
  "tables": [
    "orders",
    "payments"
  ]
}
```

**response**

```
STORED VALUE FORMATS

  orders.order_ts (TEXT): values are stored like '2026-01-01 02:11:00' through '2026-03-31 21:27:00'
  payments.paid_ts (TEXT): values are stored like '2026-01-01 03:12:00' through '2026-05-30 03:21:00'

Write literals in exactly this format. A differently formatted string compares as text rather than as a time, and silently selects the wrong rows.
```

## 4. model · recompute

`gpt-4o-mini` · replayed · 707 in / 75 out · 0.00s

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
What is the total captured revenue of the Indonesian business (IDR-denominated orders) from completed orders, in cents?

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

STORED VALUE FORMATS

  orders.order_ts (TEXT): values are stored like '2026-01-01 02:11:00' through '2026-03-31 21:27:00'
  payments.paid_ts (TEXT): values are stored like '2026-01-01 03:12:00' through '2026-05-30 03:21:00'

Write literals in exactly this format. A differently formatted string compares as text rather than as a time, and silently selects the wrong rows.

Write a single read-only SQL query that answers this question against this
SQLite warehouse.

Derive it from the question and the measured facts above. Pay attention to the
grain of each measure, to columns that are nullable in practice, and to the
stored format of any value you compare against.

Return exactly these columns, in this order, with these names:
idr_revenue_cents

Reply with one JSON object and nothing else:

{"sql": "a single SELECT, no semicolon", "reasoning": "one sentence on the grain and filters you chose"}
```

**assistant**

```json
{"sql": "SELECT SUM(p.amount_cents) AS idr_revenue_cents FROM payments p JOIN orders o ON p.order_id = o.order_id WHERE o.currency = 'IDR' AND o.status = 'completed'", "reasoning": "The query sums the payment amounts for completed orders in IDR currency, ensuring we only capture the relevant revenue."}
```

## 5. tool · `run_sql` · recompute · ok

**request**

```sql
SELECT SUM(p.amount_cents) AS idr_revenue_cents FROM payments p JOIN orders o ON p.order_id = o.order_id WHERE o.currency = 'IDR' AND o.status = 'completed'
```

**response**

```
idr_revenue_cents
-----------------
4743500000       
```

## 6. model · plan

`gpt-4o-mini` · live call · 821 in / 482 out · 4.11s

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
      "risk": "The query may include payments from orders that are not in IDR currency",
      "bug_type": "missing_filter",
      "probe_sql": "SELECT SUM(p.amount_cents) AS idr_revenue_cents FROM orders o JOIN payments p ON p.order_id = o.order_id WHERE o.status = 'completed' AND o.currency = 'IDR'",
      "settles": "If the result is different from 5468920000, it confirms the issue; if it is the same, the issue is ruled out."
    },
    {
      "risk": "The query may include payments for refunded orders",
      "bug_type": "missing_filter",
      "probe_sql": "SELECT SUM(p.amount_cents) AS idr_revenue_cents FROM orders o JOIN payments p ON p.order_id = o.order_id LEFT JOIN refunds r ON r.order_id = o.order_id WHERE o.status = 'completed' AND r.refund_id IS NULL",
      "settles": "If the result is different from 5468920000, it confirms the issue; if it is the same, the issue is ruled out."
    },
    {
      "risk": "The join between orders and payments may result in duplicate payment amounts due to multiple payments per order",
      "bug_type": "fanout_join",
      "probe_sql": "SELECT COUNT(DISTINCT o.order_id) AS distinct_orders, COUNT(p.payment_id) AS total_payments FROM orders o JOIN payments p ON p.order_id = o.order_id WHERE o.status = 'completed'",
      "settles": "If distinct_orders is less than total_payments, it confirms the issue; if they are equal, the issue is ruled out."
    },
    {
      "risk": "The query may not account for the possibility of orders with no payments",
      "bug_type": "left_join_degraded_to_inner",
      "probe_sql": "SELECT COUNT(*) AS total_orders, COUNT(p.payment_id) AS total_payments FROM orders o LEFT JOIN payments p ON p.order_id = o.order_id WHERE o.status = 'completed'",
      "settles": "If total_orders is greater than total_payments, it confirms the issue; if they are equal, the issue is ruled out."
    }
  ]
}
```

## 7. tool · `run_sql` · probe_1 · ok

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

## 8. tool · `run_sql` · probe_2 · ok

**request**

```sql
SELECT SUM(p.amount_cents) AS idr_revenue_cents FROM orders o JOIN payments p ON p.order_id = o.order_id LEFT JOIN refunds r ON r.order_id = o.order_id WHERE o.status = 'completed' AND r.refund_id IS NULL
```

**response**

```
idr_revenue_cents
-----------------
5382095000       
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
SELECT COUNT(*) AS total_orders, COUNT(p.payment_id) AS total_payments FROM orders o LEFT JOIN payments p ON p.order_id = o.order_id WHERE o.status = 'completed'
```

**response**

```
total_orders | total_payments
-------------+---------------
1250         | 1250          
```

## 11. model · adjudicate

`gpt-4o-mini` · live call · 1409 in / 125 out · 1.90s

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
[1] risk: The query may include payments from orders that are not in IDR currency
    probe: SELECT SUM(p.amount_cents) AS idr_revenue_cents FROM orders o JOIN payments p ON p.order_id = o.order_id WHERE o.status = 'completed' AND o.currency = 'IDR'
    returned:
    idr_revenue_cents
    -----------------
    4743500000       

[2] risk: The query may include payments for refunded orders
    probe: SELECT SUM(p.amount_cents) AS idr_revenue_cents FROM orders o JOIN payments p ON p.order_id = o.order_id LEFT JOIN refunds r ON r.order_id = o.order_id WHERE o.status = 'completed' AND r.refund_id IS NULL
    returned:
    idr_revenue_cents
    -----------------
    5382095000       

[3] risk: The join between orders and payments may result in duplicate payment amounts due to multiple payments per order
    probe: SELECT COUNT(DISTINCT o.order_id) AS distinct_orders, COUNT(p.payment_id) AS total_payments FROM orders o JOIN payments p ON p.order_id = o.order_id WHERE o.status = 'completed'
    returned:
    distinct_orders | total_payments
    ----------------+---------------
    1018            | 1250          

[4] risk: The query may not account for the possibility of orders with no payments
    probe: SELECT COUNT(*) AS total_orders, COUNT(p.payment_id) AS total_payments FROM orders o LEFT JOIN payments p ON p.order_id = o.order_id WHERE o.status = 'completed'
    returned:
    total_orders | total_payments
    -------------+---------------
    1250         | 1250          

An independent recomputation was derived from the business question alone, without seeing the query under review, then executed:

  sql: SELECT SUM(p.amount_cents) AS idr_revenue_cents FROM payments p JOIN orders o ON p.order_id = o.order_id WHERE o.currency = 'IDR' AND o.status = 'completed'
  returned:
    idr_revenue_cents
    -----------------
    4743500000       

  the query under review returned:
    idr_revenue_cents
    -----------------
    5468920000       

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
  "explanation": "The query under review does not filter for orders in IDR currency, leading to an inflated revenue total. The independent recomputation correctly filters for IDR orders and returns a different total, indicating a discrepancy.",
  "corrected_sql": "SELECT SUM(p.amount_cents) AS idr_revenue_cents FROM orders o JOIN payments p ON p.order_id = o.order_id WHERE o.status = 'completed' AND o.currency = 'IDR'"
}
```

## 12. gate · verification_gate

**BUG** — an independently derived query returns a different number, demonstrating the discrepancy

```json
{
  "reported": "idr_revenue_cents\n-----------------\n5468920000       ",
  "recomputed": "idr_revenue_cents\n-----------------\n4743500000       "
}
```
