# Trajectory — recount — C2_clean_units_sold_at_line_grain

`3` model calls (`1` replayed from cassette) · `6` tool calls · `3273` tokens · `$0.00075`

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

## 2. note · profile_disabled

Warehouse profiling disabled; both roles see the schema only.

## 3. note · formats_disabled

Stored value formats withheld from the author for this run.

## 4. model · recompute

`gpt-4o-mini` · replayed · 623 in / 71 out · 0.00s

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
units_sold

Reply with one JSON object and nothing else:

{"sql": "a single SELECT, no semicolon", "reasoning": "one sentence on the grain and filters you chose"}
```

**assistant**

```json
{"sql": "SELECT SUM(oi.quantity) AS units_sold FROM order_items oi JOIN orders o ON oi.order_id = o.order_id WHERE o.status = 'completed'", "reasoning": "The query sums the quantity of items sold from order_items where the corresponding orders have a status of 'completed', ensuring we only count completed orders."}
```

## 5. tool · `run_sql` · recompute · ok

**request**

```sql
SELECT SUM(oi.quantity) AS units_sold FROM order_items oi JOIN orders o ON oi.order_id = o.order_id WHERE o.status = 'completed'
```

**response**

```
units_sold
----------
2993      
```

## 6. model · plan

`gpt-4o-mini` · live call · 799 in / 403 out · 3.35s

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
      "risk": "The query may be counting order items from orders that are not actually completed due to incorrect status filtering.",
      "bug_type": "missing_filter",
      "probe_sql": "SELECT COUNT(*) FROM orders WHERE status != 'completed'",
      "settles": "A non-zero result would confirm this, indicating there are orders not filtered out, while a zero result would rule it out."
    },
    {
      "risk": "The query may be counting order items that are associated with orders that have been refunded, leading to inflated unit sales.",
      "bug_type": "other",
      "probe_sql": "SELECT SUM(oi.quantity) FROM order_items oi JOIN orders o ON oi.order_id = o.order_id JOIN refunds r ON o.order_id = r.order_id WHERE o.status = 'completed'",
      "settles": "A non-zero result would confirm this, indicating refunded items are included, while a zero result would rule it out."
    },
    {
      "risk": "The query may be counting duplicate order items due to multiple entries in the order_items table for the same order.",
      "bug_type": "fanout_join",
      "probe_sql": "SELECT COUNT(DISTINCT oi.order_item_id) FROM order_items oi JOIN orders o ON oi.order_id = o.order_id WHERE o.status = 'completed'",
      "settles": "If this count is less than the original units_sold, it would confirm duplicates, while equality would rule it out."
    },
    {
      "risk": "The query may be aggregating quantities without considering different currencies, leading to incorrect totals.",
      "bug_type": "mixed_unit_aggregation",
      "probe_sql": "SELECT COUNT(DISTINCT currency) FROM orders WHERE status = 'completed'",
      "settles": "More than one distinct currency would confirm this risk, while a single currency would rule it out."
    }
  ]
}
```

## 7. tool · `run_sql` · probe_1 · ok

**request**

```sql
SELECT COUNT(*) FROM orders WHERE status != 'completed'
```

**response**

```
COUNT(*)
--------
402     
```

## 8. tool · `run_sql` · probe_2 · ok

**request**

```sql
SELECT SUM(oi.quantity) FROM order_items oi JOIN orders o ON oi.order_id = o.order_id JOIN refunds r ON o.order_id = r.order_id WHERE o.status = 'completed'
```

**response**

```
SUM(oi.quantity)
----------------
48              
```

## 9. tool · `run_sql` · probe_3 · ok

**request**

```sql
SELECT COUNT(DISTINCT oi.order_item_id) FROM order_items oi JOIN orders o ON oi.order_id = o.order_id WHERE o.status = 'completed'
```

**response**

```
COUNT(DISTINCT oi.order_item_id)
--------------------------------
2169                            
```

## 10. tool · `run_sql` · probe_4 · ok

**request**

```sql
SELECT COUNT(DISTINCT currency) FROM orders WHERE status = 'completed'
```

**response**

```
COUNT(DISTINCT currency)
------------------------
2                       
```

## 11. model · adjudicate

`gpt-4o-mini` · live call · 1283 in / 94 out · 1.32s

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
[1] risk: The query may be counting order items from orders that are not actually completed due to incorrect status filtering.
    probe: SELECT COUNT(*) FROM orders WHERE status != 'completed'
    returned:
    COUNT(*)
    --------
    402     

[2] risk: The query may be counting order items that are associated with orders that have been refunded, leading to inflated unit sales.
    probe: SELECT SUM(oi.quantity) FROM order_items oi JOIN orders o ON oi.order_id = o.order_id JOIN refunds r ON o.order_id = r.order_id WHERE o.status = 'completed'
    returned:
    SUM(oi.quantity)
    ----------------
    48              

[3] risk: The query may be counting duplicate order items due to multiple entries in the order_items table for the same order.
    probe: SELECT COUNT(DISTINCT oi.order_item_id) FROM order_items oi JOIN orders o ON oi.order_id = o.order_id WHERE o.status = 'completed'
    returned:
    COUNT(DISTINCT oi.order_item_id)
    --------------------------------
    2169                            

[4] risk: The query may be aggregating quantities without considering different currencies, leading to incorrect totals.
    probe: SELECT COUNT(DISTINCT currency) FROM orders WHERE status = 'completed'
    returned:
    COUNT(DISTINCT currency)
    ------------------------
    2                       

An independent recomputation was derived from the business question alone, without seeing the query under review, then executed:

  sql: SELECT SUM(oi.quantity) AS units_sold FROM order_items oi JOIN orders o ON oi.order_id = o.order_id WHERE o.status = 'completed'
  returned:
    units_sold
    ----------
    2993      

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
  "verdict": "CLEAN",
  "bug_type": null,
  "confidence": 1,
  "explanation": "The query correctly sums the quantities of order items from completed orders, as confirmed by the independent recomputation. Both the original query and the recomputation returned the same result of 2993 units sold. There are no issues with the filtering or aggregation based on the provided schema.",
  "corrected_sql": null
}
```

## 12. gate · verification_gate

**CLEAN** — an independently derived query returns the same number, corroborating the reported result

```json
{
  "both_returned": "units_sold\n----------\n2993      "
}
```
