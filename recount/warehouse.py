"""Synthetic e-commerce warehouse with grain hazards built in.

Zero dependencies: stdlib ``sqlite3`` only.

The warehouse is deterministic given a seed, so every reviewer materialises
byte-identical data and therefore byte-identical ground-truth numbers.

Hazards are deliberately planted so that plausible-looking SQL can be wrong
without raising an error:

* ``order_items`` is at line-item grain -> joining it to ``orders`` fans out
  any order-level measure.
* ``payments`` allows several rows per order (installments, retries) -> a
  second, independent fan-out path.
* ``orders.status`` is nullable -> ``status != 'cancelled'`` silently drops
  those rows because ``NULL != 'cancelled'`` is ``NULL``, not true.
* ``refunds`` is sparse -> a predicate on a LEFT JOINed refund column
  quietly degrades the join to an INNER JOIN.
* ``orders.order_ts`` is stored as a UTC timestamp, while the business
  reports on ``Asia/Jakarta`` calendar days -> naive ``date()`` truncation
  misattributes orders placed late in the local day.
* ``orders.currency`` mixes IDR and USD -> summing raw amounts is meaningless
  without conversion.
"""

from __future__ import annotations

import random
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE customers (
    customer_id   INTEGER PRIMARY KEY,
    name          TEXT    NOT NULL,
    country       TEXT    NOT NULL,
    signup_ts     TEXT    NOT NULL   -- ISO-8601 UTC
);

CREATE TABLE products (
    product_id       INTEGER PRIMARY KEY,
    name             TEXT    NOT NULL,
    category         TEXT    NOT NULL,
    list_price_cents INTEGER NOT NULL
);

-- One row per order. Order-level measures live here.
CREATE TABLE orders (
    order_id    INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(customer_id),
    order_ts    TEXT    NOT NULL,   -- ISO-8601 UTC
    status      TEXT,               -- nullable on purpose
    currency    TEXT    NOT NULL    -- 'IDR' or 'USD'
);

-- One row per line item. NOT order grain.
CREATE TABLE order_items (
    order_item_id    INTEGER PRIMARY KEY,
    order_id         INTEGER NOT NULL REFERENCES orders(order_id),
    product_id       INTEGER NOT NULL REFERENCES products(product_id),
    quantity         INTEGER NOT NULL,
    unit_price_cents INTEGER NOT NULL
);

-- One or more rows per order (installments / retried captures).
CREATE TABLE payments (
    payment_id   INTEGER PRIMARY KEY,
    order_id     INTEGER NOT NULL REFERENCES orders(order_id),
    amount_cents INTEGER NOT NULL,
    paid_ts      TEXT    NOT NULL,
    method       TEXT    NOT NULL
);

-- Sparse: most orders have no refund.
CREATE TABLE refunds (
    refund_id    INTEGER PRIMARY KEY,
    order_id     INTEGER NOT NULL REFERENCES orders(order_id),
    amount_cents INTEGER NOT NULL,
    refund_ts    TEXT    NOT NULL,
    reason       TEXT    NOT NULL
);

-- Daily grain, one row per (spend_date, channel).
CREATE TABLE marketing_spend (
    spend_date  TEXT    NOT NULL,
    channel     TEXT    NOT NULL,
    spend_cents INTEGER NOT NULL,
    PRIMARY KEY (spend_date, channel)
);

CREATE TABLE sessions (
    session_id  INTEGER PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(customer_id),
    session_ts  TEXT    NOT NULL,
    channel     TEXT    NOT NULL
);
"""

# ---------------------------------------------------------------------------
# Generation parameters. Changing these changes ground truth, so they are
# pinned here rather than passed around.
# ---------------------------------------------------------------------------

WINDOW_START = datetime(2026, 1, 1, tzinfo=timezone.utc)
WINDOW_DAYS = 90

N_CUSTOMERS = 400
N_PRODUCTS = 60
N_ORDERS = 1500

COUNTRIES = ["ID", "ID", "ID", "SG", "MY", "US", "AU"]
CATEGORIES = ["audio", "wearables", "home", "accessories", "lighting"]
CHANNELS = ["organic", "paid_search", "paid_social", "email", "referral"]
PAY_METHODS = ["card", "va_transfer", "ewallet", "installment"]
REFUND_REASONS = ["damaged", "late_delivery", "wrong_item", "changed_mind"]

# Status mix. `None` is the nullable trap: rows that are effectively active but
# were never stamped by the fulfilment service.
STATUS_WEIGHTS = [
    ("completed", 0.68),
    ("cancelled", 0.09),
    ("refunded", 0.06),
    ("pending", 0.11),
    (None, 0.06),
]

JAKARTA_OFFSET = timedelta(hours=7)


@dataclass(frozen=True)
class WarehouseStats:
    """Counts a reviewer can assert against to confirm a clean build."""

    customers: int
    products: int
    orders: int
    order_items: int
    payments: int
    refunds: int
    marketing_spend: int
    sessions: int
    orders_with_null_status: int
    orders_with_multiple_payments: int
    orders_with_multiple_items: int

    def as_dict(self) -> dict:
        return dict(self.__dict__)


def _weighted_choice(rng: random.Random, weighted: list) -> object:
    roll = rng.random()
    cumulative = 0.0
    for value, weight in weighted:
        cumulative += weight
        if roll < cumulative:
            return value
    return weighted[-1][0]


def build(db_path: str | Path, seed: int = 20260828) -> WarehouseStats:
    """Materialise the warehouse at ``db_path``, replacing any existing file."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    rng = random.Random(seed)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.executescript(SCHEMA)
        _seed_customers(conn, rng)
        _seed_products(conn, rng)
        counts = _seed_orders(conn, rng)
        _seed_marketing(conn, rng)
        _seed_sessions(conn, rng)
        conn.commit()
        stats = _collect_stats(conn, counts)
    finally:
        conn.close()
    return stats


def _seed_customers(conn: sqlite3.Connection, rng: random.Random) -> None:
    rows = []
    for customer_id in range(1, N_CUSTOMERS + 1):
        signup = WINDOW_START - timedelta(
            days=rng.randint(0, 500), seconds=rng.randint(0, 86399)
        )
        rows.append(
            (
                customer_id,
                f"customer_{customer_id:04d}",
                rng.choice(COUNTRIES),
                signup.isoformat(sep=" ", timespec="seconds").replace("+00:00", ""),
            )
        )
    conn.executemany("INSERT INTO customers VALUES (?, ?, ?, ?)", rows)


def _seed_products(conn: sqlite3.Connection, rng: random.Random) -> None:
    rows = []
    for product_id in range(1, N_PRODUCTS + 1):
        rows.append(
            (
                product_id,
                f"product_{product_id:03d}",
                rng.choice(CATEGORIES),
                rng.randrange(45_000, 3_500_000, 5_000),
            )
        )
    conn.executemany("INSERT INTO products VALUES (?, ?, ?, ?)", rows)


def _seed_orders(conn: sqlite3.Connection, rng: random.Random) -> dict:
    prices = dict(
        conn.execute("SELECT product_id, list_price_cents FROM products").fetchall()
    )

    order_rows: list[tuple] = []
    item_rows: list[tuple] = []
    payment_rows: list[tuple] = []
    refund_rows: list[tuple] = []

    item_id = 0
    payment_id = 0
    refund_id = 0

    for order_id in range(1, N_ORDERS + 1):
        # Bias a slice of orders into the last local-day hours so the UTC vs
        # Asia/Jakarta boundary has real mass to detect.
        day_offset = rng.randint(0, WINDOW_DAYS - 1)
        if rng.random() < 0.22:
            hour = rng.randint(17, 23)  # 00:00-06:59 next day in Jakarta
        else:
            hour = rng.randint(0, 16)
        order_ts = WINDOW_START + timedelta(
            days=day_offset, hours=hour, minutes=rng.randint(0, 59)
        )

        status = _weighted_choice(rng, STATUS_WEIGHTS)
        currency = "USD" if rng.random() < 0.12 else "IDR"
        customer_id = rng.randint(1, N_CUSTOMERS)

        order_rows.append(
            (
                order_id,
                customer_id,
                order_ts.isoformat(sep=" ", timespec="seconds").replace("+00:00", ""),
                status,
                currency,
            )
        )

        # 1-4 line items. Multi-item orders are the fan-out mass.
        n_items = _weighted_choice(
            rng, [(1, 0.34), (2, 0.31), (3, 0.22), (4, 0.13)]
        )
        order_total = 0
        for _ in range(n_items):
            item_id += 1
            product_id = rng.randint(1, N_PRODUCTS)
            quantity = _weighted_choice(rng, [(1, 0.72), (2, 0.19), (3, 0.09)])
            unit_price = prices[product_id]
            order_total += unit_price * quantity
            item_rows.append((item_id, order_id, product_id, quantity, unit_price))

        # Payments: cancelled orders are never captured. Installment orders
        # split into 2-3 rows, creating the second fan-out path.
        if status != "cancelled":
            if rng.random() < 0.18:
                n_payments = _weighted_choice(rng, [(2, 0.7), (3, 0.3)])
                base = order_total // n_payments
                for part in range(n_payments):
                    payment_id += 1
                    amount = (
                        order_total - base * (n_payments - 1)
                        if part == n_payments - 1
                        else base
                    )
                    paid = order_ts + timedelta(days=30 * part, minutes=rng.randint(1, 90))
                    payment_rows.append(
                        (
                            payment_id,
                            order_id,
                            amount,
                            paid.isoformat(sep=" ", timespec="seconds").replace("+00:00", ""),
                            "installment",
                        )
                    )
            else:
                payment_id += 1
                paid = order_ts + timedelta(minutes=rng.randint(1, 240))
                payment_rows.append(
                    (
                        payment_id,
                        order_id,
                        order_total,
                        paid.isoformat(sep=" ", timespec="seconds").replace("+00:00", ""),
                        rng.choice(PAY_METHODS[:3]),
                    )
                )

        # Refunds are sparse and mostly attached to refunded orders.
        refund_chance = 0.92 if status == "refunded" else 0.015
        if rng.random() < refund_chance:
            refund_id += 1
            portion = rng.choice([0.25, 0.5, 1.0])
            refunded = order_ts + timedelta(days=rng.randint(1, 21))
            refund_rows.append(
                (
                    refund_id,
                    order_id,
                    int(order_total * portion),
                    refunded.isoformat(sep=" ", timespec="seconds").replace("+00:00", ""),
                    rng.choice(REFUND_REASONS),
                )
            )

    conn.executemany("INSERT INTO orders VALUES (?, ?, ?, ?, ?)", order_rows)
    conn.executemany("INSERT INTO order_items VALUES (?, ?, ?, ?, ?)", item_rows)
    conn.executemany("INSERT INTO payments VALUES (?, ?, ?, ?, ?)", payment_rows)
    conn.executemany("INSERT INTO refunds VALUES (?, ?, ?, ?, ?)", refund_rows)

    return {
        "order_items": len(item_rows),
        "payments": len(payment_rows),
        "refunds": len(refund_rows),
    }


def _seed_marketing(conn: sqlite3.Connection, rng: random.Random) -> None:
    rows = []
    for day_offset in range(WINDOW_DAYS):
        day = (WINDOW_START + timedelta(days=day_offset)).date().isoformat()
        for channel in CHANNELS:
            if channel == "organic":
                continue  # organic has no spend; a LEFT JOIN target
            rows.append((day, channel, rng.randrange(1_500_000, 40_000_000, 50_000)))
    conn.executemany("INSERT INTO marketing_spend VALUES (?, ?, ?)", rows)


def _seed_sessions(conn: sqlite3.Connection, rng: random.Random) -> None:
    rows = []
    session_id = 0
    for _ in range(6000):
        session_id += 1
        ts = WINDOW_START + timedelta(
            days=rng.randint(0, WINDOW_DAYS - 1),
            hours=rng.randint(0, 23),
            minutes=rng.randint(0, 59),
        )
        # ~15% anonymous sessions -> nullable FK.
        customer_id = None if rng.random() < 0.15 else rng.randint(1, N_CUSTOMERS)
        rows.append(
            (
                session_id,
                customer_id,
                ts.isoformat(sep=" ", timespec="seconds").replace("+00:00", ""),
                rng.choice(CHANNELS),
            )
        )
    conn.executemany("INSERT INTO sessions VALUES (?, ?, ?, ?)", rows)


def _scalar(conn: sqlite3.Connection, sql: str) -> int:
    return int(conn.execute(sql).fetchone()[0])


def _collect_stats(conn: sqlite3.Connection, counts: dict) -> WarehouseStats:
    return WarehouseStats(
        customers=_scalar(conn, "SELECT COUNT(*) FROM customers"),
        products=_scalar(conn, "SELECT COUNT(*) FROM products"),
        orders=_scalar(conn, "SELECT COUNT(*) FROM orders"),
        order_items=counts["order_items"],
        payments=counts["payments"],
        refunds=counts["refunds"],
        marketing_spend=_scalar(conn, "SELECT COUNT(*) FROM marketing_spend"),
        sessions=_scalar(conn, "SELECT COUNT(*) FROM sessions"),
        orders_with_null_status=_scalar(
            conn, "SELECT COUNT(*) FROM orders WHERE status IS NULL"
        ),
        orders_with_multiple_payments=_scalar(
            conn,
            "SELECT COUNT(*) FROM (SELECT order_id FROM payments "
            "GROUP BY order_id HAVING COUNT(*) > 1)",
        ),
        orders_with_multiple_items=_scalar(
            conn,
            "SELECT COUNT(*) FROM (SELECT order_id FROM order_items "
            "GROUP BY order_id HAVING COUNT(*) > 1)",
        ),
    )


def ddl() -> str:
    """The schema as an analyst (or an LLM) would be shown it."""
    return SCHEMA.strip()


if __name__ == "__main__":  # pragma: no cover
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Build the synthetic warehouse.")
    parser.add_argument("--db", default="data/warehouse.db")
    parser.add_argument("--seed", type=int, default=20260828)
    args = parser.parse_args()

    stats = build(args.db, seed=args.seed)
    print(json.dumps(stats.as_dict(), indent=2))
