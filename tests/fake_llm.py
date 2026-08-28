"""A scripted stand-in for the model, used only by the test suite.

This exists to test the parts of Recount that must be correct regardless of
which model is behind it: probe execution, the repair path, and above all the
verification gate. Scripting the model responses makes those tests deterministic
and free.

It is a test double and never produces reported results. Every number in the
submission comes from a real model run recorded in cassettes/.
"""

from __future__ import annotations

import json
from typing import Optional

from recount.llm import LLMResponse, parse_json_object


class FakeClient:
    """Returns queued responses keyed by pipeline step.

    ``script`` maps a step name to a list of payloads, consumed in order. A
    payload may be a dict (serialised to JSON) or a raw string, so malformed
    output can be simulated too.
    """

    def __init__(self, script: dict, model: str = "fake-model") -> None:
        self.script = {k: list(v) for k, v in script.items()}
        self.model = model
        self.calls: list = []
        self.stats = {"hits": 0, "misses": 0, "live_calls": 0, "cost_usd": 0.0}

    def chat(
        self,
        messages: list,
        *,
        step: str = "chat",
        max_tokens: int = 1000,
        json_mode: bool = True,
        trace=None,
    ) -> LLMResponse:
        queue = self.script.get(step)
        if not queue:
            raise AssertionError(
                f"FakeClient has no scripted response for step {step!r} "
                f"(scripted: {sorted(self.script)})"
            )
        payload = queue.pop(0)
        text = payload if isinstance(payload, str) else json.dumps(payload)
        self.calls.append({"step": step, "messages": messages, "response": text})

        usage = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "cost_usd": 0.0,
            "cost_known": False,
        }
        if trace is not None:
            trace.add_llm(
                step,
                messages,
                text,
                model=self.model,
                usage=usage,
                cached=False,
                duration_s=0.0,
                cassette_key="fake",
            )
        return LLMResponse(
            text=text, usage=usage, cached=False, latency_s=0.0, cassette_key="fake"
        )

    def summary(self) -> dict:
        return {"model": self.model, "mode": "fake", "live_calls": 0}

    def prompt_for(self, step: str) -> Optional[str]:
        """The user-message text sent for a step, for asserting on prompts."""
        for call in self.calls:
            if call["step"] == step:
                return call["messages"][-1]["content"]
        return None
