"""Execution trace for one verification run.

The hackathon asks for agent trajectories that a reader can follow from the
agent's instructions through to the final result, including how tools responded
and what caused the next step. Rather than bolt reporting on afterwards, every
stage writes into a :class:`Trace`, which renders to JSONL for machines and to
Markdown for humans.

A trace is also the audit trail an analyst needs: every claim Recount makes is
linked to the probe that produced it.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

LLM = "llm"
TOOL = "tool"
GATE = "gate"
NOTE = "note"


@dataclass
class Event:
    seq: int
    kind: str
    step: str
    payload: dict
    duration_s: float = 0.0
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "seq": self.seq,
            "kind": self.kind,
            "step": self.step,
            "duration_s": round(self.duration_s, 3),
            **self.payload,
        }


@dataclass
class Trace:
    case_id: str
    system: str = "recount"
    events: list = field(default_factory=list)
    started: float = field(default_factory=time.time)

    # -- recording ---------------------------------------------------------
    def _add(self, kind: str, step: str, payload: dict, duration_s: float = 0.0) -> Event:
        event = Event(len(self.events) + 1, kind, step, payload, duration_s)
        self.events.append(event)
        return event

    def add_llm(
        self,
        step: str,
        messages: list,
        response_text: str,
        *,
        model: str,
        usage: dict,
        cached: bool,
        duration_s: float,
        cassette_key: Optional[str] = None,
    ) -> Event:
        return self._add(
            LLM,
            step,
            {
                "model": model,
                "cached": cached,
                "cassette_key": cassette_key,
                "usage": usage,
                "messages": messages,
                "response": response_text,
            },
            duration_s,
        )

    def add_tool(
        self,
        step: str,
        tool: str,
        request: Any,
        response: Any,
        *,
        duration_s: float = 0.0,
        ok: bool = True,
    ) -> Event:
        return self._add(
            TOOL,
            step,
            {"tool": tool, "ok": ok, "request": request, "response": response},
            duration_s,
        )

    def add_gate(self, step: str, decision: str, reason: str, detail: Any = None) -> Event:
        return self._add(
            GATE, step, {"decision": decision, "reason": reason, "detail": detail}
        )

    def add_note(self, step: str, text: str, detail: Any = None) -> Event:
        return self._add(NOTE, step, {"text": text, "detail": detail})

    # -- accounting --------------------------------------------------------
    @property
    def llm_calls(self) -> int:
        return sum(1 for e in self.events if e.kind == LLM)

    @property
    def tool_calls(self) -> int:
        return sum(1 for e in self.events if e.kind == TOOL)

    @property
    def usage(self) -> dict:
        prompt = completion = 0
        cost = 0.0
        cached_calls = 0
        for event in self.events:
            if event.kind != LLM:
                continue
            u = event.payload.get("usage") or {}
            prompt += u.get("prompt_tokens", 0)
            completion += u.get("completion_tokens", 0)
            cost += u.get("cost_usd", 0.0)
            if event.payload.get("cached"):
                cached_calls += 1
        return {
            "prompt_tokens": prompt,
            "completion_tokens": completion,
            "total_tokens": prompt + completion,
            "cost_usd": round(cost, 6),
            "llm_calls": self.llm_calls,
            "cached_calls": cached_calls,
            "tool_calls": self.tool_calls,
        }

    # -- rendering ---------------------------------------------------------
    def to_jsonl(self) -> str:
        return "\n".join(json.dumps(e.to_dict(), default=str) for e in self.events)

    def write(self, directory: str | Path) -> dict:
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        stem = f"{self.system}__{self.case_id}"
        jsonl_path = directory / f"{stem}.jsonl"
        md_path = directory / f"{stem}.md"
        jsonl_path.write_text(self.to_jsonl() + "\n", encoding="utf-8")
        md_path.write_text(self.to_markdown(), encoding="utf-8")
        return {"jsonl": str(jsonl_path), "markdown": str(md_path)}

    def to_markdown(self) -> str:
        usage = self.usage
        out = [
            f"# Trajectory — {self.system} — {self.case_id}",
            "",
            f"`{usage['llm_calls']}` model calls "
            f"(`{usage['cached_calls']}` replayed from cassette) · "
            f"`{usage['tool_calls']}` tool calls · "
            f"`{usage['total_tokens']}` tokens · "
            f"`${usage['cost_usd']:.5f}`",
            "",
        ]
        for event in self.events:
            out.extend(_render_event(event))
        return "\n".join(out).rstrip() + "\n"


def _fence(text: str, lang: str = "") -> list:
    body = text if text.endswith("\n") else text + "\n"
    return [f"```{lang}", body.rstrip("\n"), "```", ""]


def _render_event(event: Event) -> list:
    p = event.payload
    head = f"## {event.seq}. "

    if event.kind == LLM:
        cached = " · replayed" if p.get("cached") else " · live call"
        u = p.get("usage") or {}
        out = [
            head + f"model · {event.step}",
            "",
            f"`{p.get('model')}`{cached} · {u.get('prompt_tokens', 0)} in / "
            f"{u.get('completion_tokens', 0)} out · {event.duration_s:.2f}s",
            "",
        ]
        for message in p.get("messages", []):
            role = message.get("role", "?")
            out.append(f"**{role}**")
            out.append("")
            out.extend(_fence(str(message.get("content", ""))))
        out.append("**assistant**")
        out.append("")
        out.extend(_fence(str(p.get("response", "")), "json"))
        return out

    if event.kind == TOOL:
        status = "ok" if p.get("ok") else "FAILED"
        out = [
            head + f"tool · `{p.get('tool')}` · {event.step} · {status}",
            "",
            "**request**",
            "",
        ]
        request = p.get("request")
        out.extend(
            _fence(request if isinstance(request, str) else json.dumps(request, indent=2), "sql" if isinstance(request, str) else "json")
        )
        out.append("**response**")
        out.append("")
        response = p.get("response")
        out.extend(
            _fence(
                response
                if isinstance(response, str)
                else json.dumps(response, indent=2, default=str),
                "" if isinstance(response, str) else "json",
            )
        )
        return out

    if event.kind == GATE:
        out = [
            head + f"gate · {event.step}",
            "",
            f"**{p.get('decision')}** — {p.get('reason')}",
            "",
        ]
        if p.get("detail") is not None:
            out.extend(_fence(json.dumps(p["detail"], indent=2, default=str), "json"))
        return out

    out = [head + f"note · {event.step}", "", str(p.get("text", "")), ""]
    if p.get("detail") is not None:
        out.extend(_fence(json.dumps(p["detail"], indent=2, default=str), "json"))
    return out
