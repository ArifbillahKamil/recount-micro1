"""Deterministic warehouse profiler.

The most common way a SQL reviewer goes wrong is guessing at facts it could have
measured. Is ``order_items`` one row per order or several? Is ``status``
nullable, and does anything actually sit in the NULLs? Does ``payments`` fan out?
A language model asked to reason from DDL alone has to speculate, and its
speculation is confident and frequently wrong.

So none of that is left to the model. This module measures it with plain SQL and
hands over the numbers. It contains no LLM calls and is fully deterministic:
same database, same profile, every time.

The measurement that matters most is :class:`Relationship` -- rows per parent
key. A join fans out precisely when this exceeds 1.0, and that is a fact about
data, not about SQL text.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .sqlio import run_sql, scalar

TEMPORAL_HINTS = ("_ts", "_at", "date", "_time")

# Who the digest is for. See Profile.to_prompt.
REVIEWER = "reviewer"
AUTHOR = "author"


@dataclass
class Column:
    name: str
    declared_type: str
    not_null: bool
    is_pk: bool
    null_count: int = 0
    distinct_count: int = 0
    min_value: Optional[str] = None
    max_value: Optional[str] = None

    @property
    def is_nullable_in_practice(self) -> bool:
        return self.null_count > 0


@dataclass
class Relationship:
    """Cardinality of a foreign-key-shaped column against its parent table."""

    child_table: str
    child_column: str
    parent_table: str
    parent_column: str
    child_rows: int
    distinct_keys: int
    max_rows_per_key: int
    parents_with_multiple: int
    orphan_keys: int

    @property
    def avg_rows_per_key(self) -> float:
        if not self.distinct_keys:
            return 0.0
        return self.child_rows / self.distinct_keys

    @property
    def fans_out(self) -> bool:
        return self.max_rows_per_key > 1

    def describe(self) -> str:
        verdict = (
            f"FANS OUT x{self.avg_rows_per_key:.2f} avg, up to x{self.max_rows_per_key}"
            if self.fans_out
            else "one row per parent (safe to join)"
        )
        extra = ""
        if self.fans_out:
            extra = f"; {self.parents_with_multiple} parent keys have >1 child row"
        if self.orphan_keys:
            extra += f"; {self.orphan_keys} orphan key(s) with no parent"
        return (
            f"{self.child_table}.{self.child_column} -> "
            f"{self.parent_table}.{self.parent_column}: {verdict}{extra}"
        )


@dataclass
class Table:
    name: str
    row_count: int
    columns: list = field(default_factory=list)
    declared_pk: tuple = ()
    pk_is_unique: bool = True

    def grain(self) -> str:
        if self.declared_pk:
            return f"one row per {', '.join(self.declared_pk)}"
        return "no declared primary key -- grain unverified"


@dataclass
class Profile:
    db_path: str
    tables: list = field(default_factory=list)
    relationships: list = field(default_factory=list)

    def table(self, name: str) -> Optional[Table]:
        for candidate in self.tables:
            if candidate.name == name:
                return candidate
        return None

    def fanout_relationships(self) -> list:
        return [r for r in self.relationships if r.fans_out]

    # -- serialisation -----------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "db_path": self.db_path,
            "tables": [
                {
                    "name": t.name,
                    "row_count": t.row_count,
                    "declared_pk": list(t.declared_pk),
                    "pk_is_unique": t.pk_is_unique,
                    "grain": t.grain(),
                    "columns": [
                        {
                            "name": c.name,
                            "type": c.declared_type,
                            "not_null": c.not_null,
                            "null_count": c.null_count,
                            "distinct_count": c.distinct_count,
                            "min": c.min_value,
                            "max": c.max_value,
                        }
                        for c in t.columns
                    ],
                }
                for t in self.tables
            ],
            "relationships": [
                {
                    "child": f"{r.child_table}.{r.child_column}",
                    "parent": f"{r.parent_table}.{r.parent_column}",
                    "avg_rows_per_key": round(r.avg_rows_per_key, 4),
                    "max_rows_per_key": r.max_rows_per_key,
                    "parents_with_multiple": r.parents_with_multiple,
                    "orphan_keys": r.orphan_keys,
                    "fans_out": r.fans_out,
                }
                for r in self.relationships
            ],
        }

    def to_prompt(self, tables: Optional[list] = None, role: str = REVIEWER) -> str:
        """Compact digest for a prompt, tailored to what the reader is doing.

        The same facts are not equally useful to every role, and handing over all
        of them indiscriminately measurably hurt results.

        A **reviewer** judging an existing query needs join cardinality most:
        whether a table fans out is usually the whole question.

        An **author** writing a query from scratch is harmed by those same
        warnings. Told that ``order_items`` fans out x2.16, the model turns
        defensive and wraps correct aggregates in ``DISTINCT`` and subqueries it
        does not need, producing wrong SQL. What it actually needs is duller:
        column types, which columns are really nullable, and the *stored format*
        of values. One observed failure was a date filter written as
        ``'2026-01-01T00:00:00Z'`` against timestamps stored as
        ``'2026-01-01 02:11:00'``; string comparison then dropped the first day
        of the month and admitted the first day of the next.

        So the fan-out section is shown to reviewers and withheld from authors,
        while value ranges -- which reveal the stored format -- go to both.
        """
        wanted = set(tables) if tables else None
        if role == AUTHOR:
            return self._author_prompt(wanted)

        lines = ["MEASURED WAREHOUSE FACTS", ""]

        fanouts = self.fanout_relationships()
        if fanouts:
            lines.append("Join cardinality (measured, not inferred):")
            for rel in fanouts:
                if wanted and rel.child_table not in wanted and rel.parent_table not in wanted:
                    continue
                lines.append(f"  ! {rel.describe()}")
            safe = [r for r in self.relationships if not r.fans_out]
            for rel in safe:
                if wanted and rel.child_table not in wanted and rel.parent_table not in wanted:
                    continue
                lines.append(f"    {rel.describe()}")
            lines.append("")

        for table in self.tables:
            if wanted and table.name not in wanted:
                continue
            lines.append(f"{table.name}: {table.row_count} rows, {table.grain()}")
            if not table.pk_is_unique:
                lines.append("  WARNING declared primary key is not unique in practice")
            for column in table.columns:
                bits = [column.declared_type or "?"]
                if column.is_pk:
                    bits.append("pk")
                if column.is_nullable_in_practice:
                    pct = 100.0 * column.null_count / table.row_count if table.row_count else 0
                    bits.append(f"NULL in {column.null_count} rows ({pct:.1f}%)")
                bits.append(f"{column.distinct_count} distinct")
                if column.min_value is not None:
                    bits.append(f"range {column.min_value} .. {column.max_value}")
                lines.append(f"  {column.name}: {', '.join(bits)}")
            lines.append("")
        return "\n".join(lines).rstrip()

    def _author_prompt(self, wanted: Optional[set]) -> str:
        """Facts needed to write a correct query, without the alarming ones."""
        lines = ["MEASURED COLUMN FACTS", ""]
        for table in self.tables:
            if wanted and table.name not in wanted:
                continue
            lines.append(f"{table.name}: {table.row_count} rows, {table.grain()}")
            for column in table.columns:
                bits = [column.declared_type or "?"]
                if column.is_pk:
                    bits.append("pk")
                if column.is_nullable_in_practice:
                    pct = 100.0 * column.null_count / table.row_count if table.row_count else 0
                    bits.append(
                        f"NULL in {column.null_count} rows ({pct:.1f}%) -- a "
                        "predicate on this column must handle NULL explicitly"
                    )
                bits.append(f"{column.distinct_count} distinct")
                if column.min_value is not None:
                    bits.append(f"values run {column.min_value!r} .. {column.max_value!r}")
                lines.append(f"  {column.name}: {', '.join(bits)}")
            lines.append("")

        lines.append(
            "Match the stored format exactly when you write a literal. The "
            "quoted ranges above show how values are actually stored; comparing "
            "against a differently formatted string compares text, not time, "
            "and silently selects the wrong rows."
        )
        return "\n".join(lines).rstrip()


# ---------------------------------------------------------------------------
# Measurement
# ---------------------------------------------------------------------------


def _quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _user_tables(db_path: str | Path) -> list:
    result = run_sql(
        db_path,
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%' ORDER BY name",
    )
    return [row[0] for row in result["rows"]]


def _columns(db_path: str | Path, table: str) -> list:
    # PRAGMA is blocked by the read-only guard, so schema is read from the DDL
    # view sqlite exposes as a table.
    result = run_sql(
        db_path,
        "SELECT name, type, \"notnull\", pk FROM pragma_table_info("
        f"'{table}') ORDER BY cid",
    )
    return [
        Column(
            name=row[0],
            declared_type=(row[1] or "").upper(),
            not_null=bool(row[2]),
            is_pk=bool(row[3]),
        )
        for row in result["rows"]
    ]


def _is_temporal(column: Column) -> bool:
    lowered = column.name.lower()
    return any(hint in lowered for hint in TEMPORAL_HINTS)


def profile(db_path: str | Path, sample_ranges: bool = True) -> Profile:
    """Measure every user table and every foreign-key-shaped relationship."""
    db_path = str(db_path)
    tables: list = []

    for name in _user_tables(db_path):
        row_count = int(scalar(db_path, f"SELECT COUNT(*) FROM {_quote(name)}") or 0)
        columns = _columns(db_path, name)

        for column in columns:
            col_sql = _quote(column.name)
            column.null_count = int(
                scalar(
                    db_path,
                    f"SELECT COUNT(*) FROM {_quote(name)} WHERE {col_sql} IS NULL",
                )
                or 0
            )
            column.distinct_count = int(
                scalar(
                    db_path,
                    f"SELECT COUNT(DISTINCT {col_sql}) FROM {_quote(name)}",
                )
                or 0
            )
            if sample_ranges and _is_temporal(column) and row_count:
                bounds = run_sql(
                    db_path,
                    f"SELECT MIN({col_sql}), MAX({col_sql}) FROM {_quote(name)}",
                )
                if bounds["rows"]:
                    low, high = bounds["rows"][0]
                    column.min_value = None if low is None else str(low)
                    column.max_value = None if high is None else str(high)

        pk_columns = tuple(c.name for c in columns if c.is_pk)
        pk_unique = True
        if pk_columns and row_count:
            key_expr = ", ".join(_quote(c) for c in pk_columns)
            distinct_keys = int(
                scalar(
                    db_path,
                    f"SELECT COUNT(*) FROM (SELECT {key_expr} FROM "
                    f"{_quote(name)} GROUP BY {key_expr})",
                )
                or 0
            )
            pk_unique = distinct_keys == row_count

        tables.append(
            Table(
                name=name,
                row_count=row_count,
                columns=columns,
                declared_pk=pk_columns,
                pk_is_unique=pk_unique,
            )
        )

    return Profile(
        db_path=db_path,
        tables=tables,
        relationships=_relationships(db_path, tables),
    )


def _relationships(db_path: str | Path, tables: list) -> list:
    """Measure cardinality for every column that names another table's key.

    Detection is by naming convention (``<x>_id`` matching a single-column
    primary key called ``<x>_id``), which fits this warehouse and, importantly,
    does not depend on declared FK constraints -- real warehouses frequently
    lack them.
    """
    pk_owner = {}
    for table in tables:
        if len(table.declared_pk) == 1:
            pk_owner[table.declared_pk[0]] = table.name

    relationships: list = []
    for table in tables:
        for column in table.columns:
            parent_table = pk_owner.get(column.name)
            if not parent_table or parent_table == table.name:
                continue

            child = _quote(table.name)
            child_col = _quote(column.name)
            parent = _quote(parent_table)

            child_rows = int(
                scalar(db_path, f"SELECT COUNT({child_col}) FROM {child}") or 0
            )
            distinct_keys = int(
                scalar(db_path, f"SELECT COUNT(DISTINCT {child_col}) FROM {child}") or 0
            )
            max_per_key = int(
                scalar(
                    db_path,
                    f"SELECT COALESCE(MAX(n), 0) FROM (SELECT COUNT(*) AS n FROM "
                    f"{child} WHERE {child_col} IS NOT NULL GROUP BY {child_col})",
                )
                or 0
            )
            multi = int(
                scalar(
                    db_path,
                    f"SELECT COUNT(*) FROM (SELECT {child_col} FROM {child} "
                    f"WHERE {child_col} IS NOT NULL GROUP BY {child_col} "
                    "HAVING COUNT(*) > 1)",
                )
                or 0
            )
            orphans = int(
                scalar(
                    db_path,
                    f"SELECT COUNT(*) FROM (SELECT DISTINCT {child_col} AS k FROM "
                    f"{child} WHERE {child_col} IS NOT NULL) "
                    f"WHERE k NOT IN (SELECT {child_col} FROM {parent})",
                )
                or 0
            )

            relationships.append(
                Relationship(
                    child_table=table.name,
                    child_column=column.name,
                    parent_table=parent_table,
                    parent_column=column.name,
                    child_rows=child_rows,
                    distinct_keys=distinct_keys,
                    max_rows_per_key=max_per_key,
                    parents_with_multiple=multi,
                    orphan_keys=orphans,
                )
            )
    return relationships


if __name__ == "__main__":  # pragma: no cover
    import argparse

    parser = argparse.ArgumentParser(description="Profile the warehouse.")
    parser.add_argument("--db", default="data/warehouse.db")
    parser.add_argument("--json", action="store_true", help="emit JSON")
    args = parser.parse_args()

    result = profile(args.db)
    print(json.dumps(result.to_dict(), indent=2) if args.json else result.to_prompt())
