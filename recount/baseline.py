"""The baseline: one direct prompt with basic instructions.

This is the "reasonable basic way to handle the task" the rules ask for, and it
is what most teams would reach for first: show a capable model the schema, the
business question and the SQL, and ask whether the query is right.

Fairness is deliberate and worth stating plainly, because an unfair baseline
makes the whole comparison worthless:

* Same model, same temperature, same seed as Recount.
* Same output contract and the same three verdicts, including ESCALATE -- the
  baseline is never scored down for lacking vocabulary Recount has.
* Same schema text, read from the same database.
* Same scoring code.

The one thing it does not get is the thing under test: measured facts about the
data, and the ability to execute a probe. It must reason from SQL text alone.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from . import verdict as V
from .llm import CassetteMiss, LLMClient, LLMError
from .sqlio import schema_ddl
from .trace import Trace

SYSTEM_PROMPT = """You are a senior analytics engineer reviewing SQL before its
result goes into a business report. Decide whether the query correctly answers
the business question that was asked."""

USER_TEMPLATE = """Database schema:

{ddl}

Business question the analyst asked:
{question}

SQL that was produced and executed successfully:
{sql}

The query ran without error and returned a plausible-looking result. Decide
whether the number it returns actually answers the business question.

{contract}"""


def build_messages(ddl: str, question: str, sql: str) -> list:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": USER_TEMPLATE.format(
                ddl=ddl.strip(),
                question=question.strip(),
                sql=sql.strip(),
                contract=V.OUTPUT_CONTRACT,
            ),
        },
    ]


def review(
    db_path: str | Path,
    question: str,
    sql: str,
    client: LLMClient,
    *,
    case_id: str = "adhoc",
    trace: Optional[Trace] = None,
) -> tuple:
    """Review one query. Returns ``(Verdict, Trace)``."""
    trace = trace or Trace(case_id=case_id, system="baseline")
    ddl = schema_ddl(db_path)
    trace.add_note(
        "context",
        "Baseline context is the schema only: no data profiling, no query execution.",
        {"ddl_chars": len(ddl)},
    )

    messages = build_messages(ddl, question, sql)
    try:
        response = client.chat(
            messages, step="baseline_review", max_tokens=900, trace=trace
        )
        result = V.parse(response.json())
    except CassetteMiss:
        # Never degrade a missing recording into a verdict. Doing so would let a
        # reviewer believe they reproduced a run that never replayed.
        raise
    except LLMError as exc:
        result = V.failed(str(exc))
        trace.add_note("failure", f"model call failed: {exc}")

    trace.add_gate(
        "final",
        result.verdict,
        result.explanation or "no explanation given",
        {"bug_type": result.bug_type, "confidence": result.confidence},
    )
    return result, trace
