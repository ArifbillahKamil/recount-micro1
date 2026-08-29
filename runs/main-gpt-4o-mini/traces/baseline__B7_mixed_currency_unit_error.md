# Trajectory — baseline — B7_mixed_currency_unit_error

`1` model calls (`0` replayed from cassette) · `0` tool calls · `930` tokens · `$0.00020`

## 1. note · context

Baseline context is the schema only: no data profiling, no query execution.

```json
{
  "ddl_chars": 1792
}
```

## 2. model · baseline_review

`gpt-4o-mini` · live call · 798 in / 132 out · 2.24s

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
What is the total captured revenue of the Indonesian business (IDR-denominated orders) from completed orders, in cents?

SQL that was produced and executed successfully:
SELECT SUM(p.amount_cents) AS idr_revenue_cents
            FROM orders o
            JOIN payments p ON p.order_id = o.order_id
            WHERE o.status = 'completed'

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
  "explanation": "The query does not filter for Indonesian orders, as it lacks a condition to check that the currency of the orders is 'IDR'. This means it could include payments from orders in other currencies, which does not answer the business question accurately.",
  "corrected_sql": "SELECT SUM(p.amount_cents) AS idr_revenue_cents FROM orders o JOIN payments p ON p.order_id = o.order_id WHERE o.status = 'completed' AND o.currency = 'IDR'"
}
```

## 3. gate · final

**BUG** — The query does not filter for Indonesian orders, as it lacks a condition to check that the currency of the orders is 'IDR'. This means it could include payments from orders in other currencies, which does not answer the business question accurately.

```json
{
  "bug_type": "missing_filter",
  "confidence": 0.9
}
```
