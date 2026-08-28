"""Read-only SQL execution: the single gate every query in this project passes.

The agent writes and runs its own probe SQL, which is a consequential action on
a database. Everything funnels through :func:`run_sql`, which opens the file in
read-only URI mode, sets ``PRAGMA query_only``, rejects statements that are not
a single read, caps returned rows, and normalises errors to one exception type.

Defence is layered on purpose: even if prompt text is ignored or the model is
adversarial, the connection itself cannot write.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

MAX_ROWS = 200

_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|replace|truncate|attach|detach|"
    r"vacuum|reindex|pragma|begin|commit|rollback)\b",
    re.IGNORECASE,
)


class SqlError(RuntimeError):
    """Any failure to execute a read query, with sqlite internals stripped."""


def _strip_sql_comments(sql: str) -> str:
    sql = re.sub(r"--[^\n]*", " ", sql)
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    return sql


def assert_read_only(sql: str) -> None:
    """Reject anything that is not a single read statement.

    Raises :class:`SqlError` with a message the agent can act on, since this
    doubles as tool feedback during the probe loop.
    """
    body = _strip_sql_comments(sql).strip().rstrip(";").strip()
    if not body:
        raise SqlError("empty statement")
    if ";" in body:
        raise SqlError("only one statement per probe is allowed")
    lowered = body.lower()
    if not (lowered.startswith("select") or lowered.startswith("with")):
        raise SqlError("probes must start with SELECT or WITH")
    match = _FORBIDDEN.search(body)
    if match:
        raise SqlError(f"forbidden keyword in a read-only probe: {match.group(0)!r}")


def run_sql(db_path: str | Path, sql: str, limit: int = MAX_ROWS) -> dict:
    """Execute a single read statement and return columns, rows, truncation."""
    assert_read_only(sql)
    uri = f"file:{Path(db_path).as_posix()}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True, timeout=10.0)
    except sqlite3.Error as exc:
        raise SqlError(f"cannot open database: {exc}") from exc
    try:
        conn.execute("PRAGMA query_only = ON")
        cur = conn.execute(sql)
        columns = [d[0] for d in cur.description or []]
        rows = [tuple(r) for r in cur.fetchmany(limit)]
        truncated = len(cur.fetchmany(1)) > 0
    except sqlite3.Error as exc:
        raise SqlError(str(exc)) from exc
    finally:
        conn.close()
    return {"columns": columns, "rows": rows, "truncated": truncated}


def scalar(db_path: str | Path, sql: str):
    """Run a query expected to yield one value."""
    result = run_sql(db_path, sql, limit=1)
    if not result["rows"]:
        return None
    return result["rows"][0][0]


def result_signature(result: dict) -> tuple:
    """Comparable signature of a result set, used for ground-truth diffing."""
    return (tuple(result["columns"]), tuple(result["rows"]))


def render_result(result: dict, max_rows: int = 12) -> str:
    """Render a result set as a compact text table for prompts and reports."""
    columns = result["columns"]
    rows = result["rows"]
    if not columns:
        return "(no columns)"
    shown = rows[:max_rows]
    widths = [len(str(c)) for c in columns]
    for row in shown:
        for i, value in enumerate(row):
            widths[i] = max(widths[i], len(_fmt(value)))
    line = " | ".join(str(c).ljust(widths[i]) for i, c in enumerate(columns))
    out = [line, "-+-".join("-" * w for w in widths)]
    for row in shown:
        out.append(" | ".join(_fmt(v).ljust(widths[i]) for i, v in enumerate(row)))
    if not shown:
        out.append("(0 rows)")
    hidden = len(rows) - len(shown)
    if hidden > 0:
        out.append(f"... {hidden} more row(s)")
    if result.get("truncated"):
        out.append(f"... truncated at {MAX_ROWS} rows")
    return "\n".join(out)


def _fmt(value) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, float):
        return f"{value:.4f}".rstrip("0").rstrip(".")
    return str(value)



def schema_ddl(db_path: str | Path) -> str:
    """The CREATE TABLE statements, as an analyst would be shown the schema.

    Read from the live database rather than a constant, so both systems are
    described by the same source of truth and neither can drift from it.
    """
    result = run_sql(
        db_path,
        "SELECT sql FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%' ORDER BY name",
    )
    statements = [row[0].strip() for row in result["rows"] if row[0]]
    return ";\n\n".join(statements) + ";"



def values_match(left: dict, right: dict) -> bool:
    """Compare two result sets by value, ignoring column names.

    An independently derived query answers the same question but need not label
    its output identically. Comparing signatures including column names would
    report a disagreement over an alias, so only shape and values are compared.
    """
    left_rows, right_rows = left.get("rows") or [], right.get("rows") or []
    if len(left_rows) != len(right_rows):
        return False
    for a, b in zip(left_rows, right_rows):
        if len(a) != len(b):
            return False
        for x, y in zip(a, b):
            if x is None or y is None:
                if x is not y:
                    return False
                continue
            if isinstance(x, bool) != isinstance(y, bool):
                return False
            if isinstance(x, (int, float)) and isinstance(y, (int, float)):
                # Tolerate float noise; integers still compare exactly.
                if isinstance(x, int) and isinstance(y, int):
                    if x != y:
                        return False
                elif abs(float(x) - float(y)) > 1e-9 * max(1.0, abs(float(x))):
                    return False
            elif str(x) != str(y):
                return False
    return True
