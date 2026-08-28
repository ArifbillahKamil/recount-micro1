"""OpenAI chat client with cassette record/replay. No third-party packages.

Why cassettes carry so much weight here:

* **Reproducibility.** A reviewer with no API key runs ``--offline`` and gets
  byte-identical results, because every model response is replayed from disk.
* **Cost.** Re-running the evaluation after a prompt change only pays for the
  calls that actually changed; everything else is a cache hit.
* **Trajectories.** A cassette is a verbatim record of what was sent and what
  came back, which is exactly the trajectory evidence the rules ask for.

The cassette key is a hash of everything that can change a response (model,
messages, temperature, response format, token ceiling, seed). Change a prompt
and you get a new key, so a stale response can never be silently reused.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

API_URL = "https://api.openai.com/v1/chat/completions"

# USD per 1M tokens, (input, output).
#
# Model pricing moves, and a cost figure in a submission is only as good as the
# rate behind it. This table is therefore treated as a convenience, never as
# authority:
#
# * If the model is absent from the table, cost is reported as "unpriced"
#   rather than guessed. A missing number is honest; a wrong number is not.
# * --price-in / --price-out always win, so a reviewer can pin the exact rate
#   they were billed.
#
# Run `python -m recount.llm --list-models` to see what your key can reach, and
# confirm rates at https://openai.com/api/pricing before quoting a cost.
PRICING = {
    # Verify before use. Sourced from openai.com/api/pricing listings and a
    # report of the 2026-07-30 price change; treated as unconfirmed.
    "gpt-5.4": (2.50, 15.00),
    "gpt-5.4-mini": (0.75, 4.50),
    # Older generations, kept for anyone still pinned to them.
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1-nano": (0.10, 0.40),
    "gpt-4.1": (2.00, 8.00),
}

MODE_AUTO = "auto"
MODE_RECORD = "record"
MODE_REPLAY = "replay"

RETRY_STATUS = {408, 409, 429, 500, 502, 503, 504}


class LLMError(RuntimeError):
    pass


class CassetteMiss(LLMError):
    """Raised in replay mode when no recording exists for a request."""


@dataclass
class LLMResponse:
    text: str
    usage: dict
    cached: bool
    latency_s: float
    cassette_key: str

    def json(self) -> dict:
        """Parse the response as JSON, tolerating prose or fences around it."""
        return parse_json_object(self.text)


def parse_json_object(text: str) -> dict:
    """Extract the first JSON object from ``text``.

    Models occasionally wrap JSON in fences or a sentence even when asked not
    to. Recovering here keeps a formatting slip from being scored as a
    reasoning failure, which would make the evaluation measure the wrong thing.
    """
    text = (text or "").strip()
    if text.startswith("```"):
        lines = [ln for ln in text.splitlines() if not ln.strip().startswith("```")]
        text = "\n".join(lines).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    if start == -1:
        raise LLMError(f"no JSON object in response: {text[:200]!r}")
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        ch = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start : index + 1])
                except json.JSONDecodeError as exc:
                    raise LLMError(f"malformed JSON object: {exc}") from exc
    raise LLMError(f"unterminated JSON object in response: {text[:200]!r}")


def _canonical(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


class LLMClient:
    def __init__(
        self,
        model: str = "gpt-4o-mini",
        cassette_dir: str | Path = "cassettes",
        mode: str = MODE_AUTO,
        api_key: Optional[str] = None,
        *,
        temperature: float = 0.0,
        seed: int = 7,
        max_retries: int = 4,
        timeout_s: float = 90.0,
        price_in: Optional[float] = None,
        price_out: Optional[float] = None,
    ) -> None:
        if mode not in (MODE_AUTO, MODE_RECORD, MODE_REPLAY):
            raise ValueError(f"unknown mode: {mode}")
        self.model = model
        self.cassette_dir = Path(cassette_dir)
        self.mode = mode
        self.temperature = temperature
        self.seed = seed
        self.max_retries = max_retries
        self.timeout_s = timeout_s
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")

        table_in, table_out = PRICING.get(model, (None, None))
        self.price_in = price_in if price_in is not None else table_in
        self.price_out = price_out if price_out is not None else table_out
        self.pricing_known = self.price_in is not None and self.price_out is not None

        self.cassette_dir.mkdir(parents=True, exist_ok=True)
        self.stats = {"hits": 0, "misses": 0, "live_calls": 0, "cost_usd": 0.0}
        self._compat: set = set()

    # -- keys and storage --------------------------------------------------
    def _request_body(
        self,
        messages: list,
        max_tokens: int,
        json_mode: bool,
    ) -> dict:
        body = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": max_tokens,
            "seed": self.seed,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        return body

    @staticmethod
    def cassette_key(body: dict) -> str:
        return hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest()[:32]

    def _cassette_path(self, key: str) -> Path:
        return self.cassette_dir / f"{key}.json"

    def _load(self, key: str) -> Optional[dict]:
        path = self._cassette_path(key)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def _save(self, key: str, body: dict, response: dict, step: str) -> None:
        record = {
            "cassette_key": key,
            "step": step,
            "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "request": body,
            "response": response,
        }
        self._cassette_path(key).write_text(
            json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    # -- cost --------------------------------------------------------------
    def _cost(self, prompt_tokens: int, completion_tokens: int) -> Optional[float]:
        if not self.pricing_known:
            return None
        return (
            prompt_tokens * self.price_in / 1_000_000.0
            + completion_tokens * self.price_out / 1_000_000.0
        )

    def _usage_from(self, response: dict) -> dict:
        raw = response.get("usage") or {}
        prompt_tokens = int(raw.get("prompt_tokens", 0))
        completion_tokens = int(raw.get("completion_tokens", 0))
        cost = self._cost(prompt_tokens, completion_tokens)
        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "cost_usd": round(cost, 8) if cost is not None else 0.0,
            "cost_known": cost is not None,
        }

    # -- parameter compatibility ------------------------------------------
    #
    # Model families disagree about request parameters: some want
    # max_completion_tokens instead of max_tokens, some reject a temperature or
    # a seed outright. Rather than hardcode a per-model matrix that will be stale
    # within weeks, the client learns from the API's own 400 response and retries.
    #
    # The cassette key is always computed from the *logical* body, so acquiring a
    # compatibility quirk never invalidates recordings.
    def _wire_body(self, logical: dict) -> dict:
        body = dict(logical)
        if "rename_max_tokens" in self._compat:
            if "max_tokens" in body:
                body["max_completion_tokens"] = body.pop("max_tokens")
        if "drop_temperature" in self._compat:
            body.pop("temperature", None)
        if "drop_seed" in self._compat:
            body.pop("seed", None)
        if "drop_response_format" in self._compat:
            body.pop("response_format", None)
        return body

    @staticmethod
    def _detect_compat(message: str) -> Optional[str]:
        m = message.lower()
        unsupported = any(
            phrase in m
            for phrase in ("unsupported", "not supported", "unrecognized", "invalid")
        )
        if "max_completion_tokens" in m and "max_tokens" in m:
            return "rename_max_tokens"
        if not unsupported:
            return None
        if "temperature" in m:
            return "drop_temperature"
        if "response_format" in m:
            return "drop_response_format"
        if "seed" in m:
            return "drop_seed"
        return None

    # -- transport ---------------------------------------------------------
    def _post(self, logical_body: dict) -> dict:
        if not self._api_key:
            raise LLMError(
                "OPENAI_API_KEY is not set. Export the key, or run with "
                "--offline to replay recorded cassettes."
            )
        last_error: Optional[str] = None
        attempt = 0
        compat_retries = 0

        while attempt < self.max_retries:
            data = json.dumps(self._wire_body(logical_body)).encode("utf-8")
            request = urllib.request.Request(
                API_URL,
                data=data,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(request, timeout=self.timeout_s) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", "replace")[:400]
                last_error = f"HTTP {exc.code}: {detail}"

                if exc.code == 400 and compat_retries < 4:
                    quirk = self._detect_compat(detail)
                    if quirk and quirk not in self._compat:
                        self._compat.add(quirk)
                        compat_retries += 1
                        continue  # retry immediately, not counted as a failure

                if exc.code not in RETRY_STATUS:
                    raise LLMError(last_error) from exc
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                last_error = f"{type(exc).__name__}: {exc}"

            time.sleep(min(2.0 ** attempt, 16.0))
            attempt += 1

        raise LLMError(f"request failed after {self.max_retries} attempts: {last_error}")

    # -- public API --------------------------------------------------------
    def chat(
        self,
        messages: list,
        *,
        step: str = "chat",
        max_tokens: int = 1400,
        json_mode: bool = True,
        trace=None,
    ) -> LLMResponse:
        body = self._request_body(messages, max_tokens, json_mode)
        key = self.cassette_key(body)

        started = time.time()
        cached = False
        record = None

        if self.mode in (MODE_AUTO, MODE_REPLAY):
            record = self._load(key)

        if record is not None:
            cached = True
            self.stats["hits"] += 1
            response = record["response"]
        else:
            self.stats["misses"] += 1
            if self.mode == MODE_REPLAY:
                raise CassetteMiss(
                    f"no cassette for step '{step}' (key {key}).\n"
                    "Offline replay cannot invent a response. Re-record with "
                    "an API key, or check that prompts match the recorded run."
                )
            response = self._post(body)
            self.stats["live_calls"] += 1
            self._save(key, body, response, step)

        latency = time.time() - started
        try:
            text = response["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"unexpected response shape: {str(response)[:300]}") from exc

        usage = self._usage_from(response)
        self.stats["cost_usd"] += 0.0 if cached else usage["cost_usd"]

        if trace is not None:
            trace.add_llm(
                step,
                messages,
                text,
                model=self.model,
                usage=usage,
                cached=cached,
                duration_s=latency,
                cassette_key=key,
            )

        return LLMResponse(
            text=text,
            usage=usage,
            cached=cached,
            latency_s=latency,
            cassette_key=key,
        )

    def summary(self) -> dict:
        return {
            "model": self.model,
            "mode": self.mode,
            "cassette_hits": self.stats["hits"],
            "cassette_misses": self.stats["misses"],
            "live_calls": self.stats["live_calls"],
            "billed_cost_usd": round(self.stats["cost_usd"], 6),
            "pricing_known": self.pricing_known,
            "parameter_quirks_applied": sorted(self._compat),
        }



def list_models(api_key: Optional[str] = None, timeout_s: float = 30.0) -> list:
    """Return model ids the key can reach, newest-looking first.

    Useful before an evaluation run: pick a model you actually have access to,
    then pin its price with --price-in/--price-out.
    """
    key = api_key or os.environ.get("OPENAI_API_KEY")
    if not key:
        raise LLMError("OPENAI_API_KEY is not set")
    request = urllib.request.Request(
        "https://api.openai.com/v1/models",
        headers={"Authorization": f"Bearer {key}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise LLMError(f"HTTP {exc.code}: {exc.read().decode('utf-8', 'replace')[:300]}") from exc
    except urllib.error.URLError as exc:
        raise LLMError(f"cannot reach the API: {exc}") from exc
    ids = sorted(m.get("id", "") for m in payload.get("data", []))
    return [i for i in ids if i]


if __name__ == "__main__":  # pragma: no cover
    import argparse

    parser = argparse.ArgumentParser(description="Inspect model access and pricing.")
    parser.add_argument("--list-models", action="store_true")
    args = parser.parse_args()

    if args.list_models:
        for model_id in list_models():
            price = PRICING.get(model_id)
            note = (
                f"${price[0]}/${price[1]} per 1M (unconfirmed)"
                if price
                else "not in pricing table -- pass --price-in/--price-out"
            )
            print(f"  {model_id:<40} {note}")
    else:
        parser.print_help()
