# Trajectory — baseline — B8_missing_status_filter

`1` model calls (`0` replayed from cassette) · `0` tool calls · `890` tokens · `$0.00018`

## 1. note · context

Baseline context is the schema only: no data profiling, no query execution.

```json
{
  "ddl_chars": 1792
}
```

## 2. model · baseline_review

`gpt-4o-mini` · live call · 776 in / 114 out · 1.92s

**system**

```
You are a senior analytics engineer reviewing SQL before its
result goes into a business report. Decide whether the query correctly answers
the business question that was asked.
```

**user**

```
Database schema:

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

Business question the analyst asked:
What revenue did we capture from completed orders only, in cents?

SQL that was produced and executed successfully:
SELECT SUM(p.amount_cents) AS revenue_cents
            FROM orders o
            JOIN payments p ON p.order_id = o.order_id

The query ran without error and returned a plausible-looking result. Decide
whether the number it returns actually answers the business question.

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
  "explanation": "The query sums the payment amounts from the payments table but does not filter for completed orders. The orders table has a status column that should be checked to ensure only completed orders are included in the revenue calculation.",
  "corrected_sql": "SELECT SUM(p.amount_cents) AS revenue_cents FROM orders o JOIN payments p ON p.order_id = o.order_id WHERE o.status = 'completed'"
}
```

## 3. gate · final

**BUG** — The query sums the payment amounts from the payments table but does not filter for completed orders. The orders table has a status column that should be checked to ensure only completed orders are included in the revenue calculation.

```json
{
  "bug_type": "missing_filter",
  "confidence": 0.9
}
```
