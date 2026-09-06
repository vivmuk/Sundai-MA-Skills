"""Venice adapter — the metered runtime.

Executor and judge are different model families by design: a model scoring
its own output inflates its scores, and the effect is largest exactly where
the margins are smallest.

Prices are fetched from GET /models at run time. A hardcoded price table goes
stale silently, which is the one failure mode a cost preflight must not have.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone

from ..environment import Environment
from ..evidence import TOOL_SCHEMAS, EvidenceStore
from ..genome import Genome
from ..phenotype import Phenotype, Usage
from .base import Budget, CostEstimate

BASE_URL = os.environ.get("VENICE_BASE_URL", "https://api.venice.ai/api/v1")
DEFAULT_EXECUTOR = "z-ai-glm-5-3"
DEFAULT_JUDGE = "gemini-3-8-flash"


class VeniceError(RuntimeError):
    pass


def _key() -> str:
    key = os.environ.get("VENICE_API_KEY", "").strip()
    if not key:
        raise VeniceError(
            "VENICE_API_KEY is not set. The engine will not read a key from a "
            "skill file or a committed config — export it in the shell that "
            "runs the experiment.")
    return key


def _request(path: str, payload: dict | None = None, method: str = "GET",
             timeout: int = 300) -> dict:
    url = f"{BASE_URL}{path}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {_key()}")
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raise VeniceError(f"{method} {path} -> HTTP {e.code}: {e.read()[:400]!r}") from e
    except urllib.error.URLError as e:
        raise VeniceError(
            f"{method} {path} unreachable: {e.reason}. If this environment "
            f"blocks egress, api.venice.ai must be allowed by the network policy."
        ) from e


class PriceBook:
    """Live per-million-token prices, fetched once per process."""

    def __init__(self):
        self._prices: dict[str, dict] = {}
        self.fetched_at = ""

    def load(self) -> dict[str, dict]:
        if self._prices:
            return self._prices
        data = _request("/models?type=text")
        for m in data.get("data", data if isinstance(data, list) else []):
            spec = m.get("model_spec", {}) or {}
            pricing = spec.get("pricing", {}) or {}

            def usd(field):
                v = pricing.get(field)
                if isinstance(v, dict):
                    return float(v.get("usd", v.get("USD", 0)) or 0)
                return float(v or 0)

            self._prices[m.get("id", "")] = {
                "input": usd("input"), "output": usd("output"),
                "privacy": spec.get("privacy", ""),
            }
        self.fetched_at = datetime.now(timezone.utc).isoformat()
        return self._prices

    def quote(self, model: str, in_tok: int, out_tok: int) -> float:
        p = self.load().get(model)
        if not p:
            raise VeniceError(
                f"no live price for {model!r}; refusing to guess. "
                f"Known: {sorted(self.load())[:8]}...")
        return in_tok / 1e6 * p["input"] + out_tok / 1e6 * p["output"]


class VeniceAdapter:
    name = "venice"

    def __init__(self, model: str = DEFAULT_EXECUTOR, prices: PriceBook | None = None,
                 max_turns: int = 12):
        self.model = model
        self.prices = prices or PriceBook()
        self.max_turns = max_turns

    def estimate(self, genome: Genome, environment: Environment,
                 budget: Budget) -> CostEstimate:
        skill = len(genome.express()) // 4
        src = len(environment.source_text()) // 4
        turns = min(self.max_turns, budget.max_model_calls)
        # An agentic loop resends its history, so cumulative input is the driver.
        in_tok = int((skill + src) * turns * 0.9)
        out_tok = 1800 * turns
        return CostEstimate(
            input_tokens=in_tok, output_tokens=out_tok,
            cost_usd=self.prices.quote(self.model, in_tok, out_tok),
            prices={self.model: self.prices.load().get(self.model, {})},
            fetched_at=self.prices.fetched_at,
        )

    def run(self, genome: Genome, environment: Environment,
            budget: Budget, seed: int) -> Phenotype:
        started = time.perf_counter()
        store = EvidenceStore(environment.evidence)
        messages = [
            {"role": "system", "content": genome.express()},
            {"role": "user", "content":
                f"Prepare the brief for {environment.target_expert}.\n\n"
                f"Situation: {environment.situation}\n\n"
                f"Source material follows. Use the evidence tools to retrieve "
                f"publications and trials; cite only what you retrieve.\n\n"
                f"{environment.source_text()}"},
        ]
        usage = Usage()
        artifact, outcome, breach = "", "complete", None

        for turn in range(self.max_turns):
            if usage.model_calls >= budget.max_model_calls:
                outcome, breach = "budget_exceeded", {
                    "limit": "max_model_calls", "value": usage.model_calls}
                break
            if (time.perf_counter() - started) / 60 > budget.max_runtime_minutes:
                outcome, breach = "budget_exceeded", {
                    "limit": "max_runtime_minutes"}
                break

            resp = _request("/chat/completions", {
                "model": self.model, "messages": messages,
                "tools": TOOL_SCHEMAS, "tool_choice": "auto",
                "temperature": 0, "seed": seed,
            }, method="POST")
            usage.model_calls += 1
            u = resp.get("usage", {}) or {}
            usage.input_tokens += int(u.get("prompt_tokens", 0))
            usage.output_tokens += int(u.get("completion_tokens", 0))

            choice = (resp.get("choices") or [{}])[0]
            msg = choice.get("message", {}) or {}
            messages.append(msg)
            calls = msg.get("tool_calls") or []
            if not calls:
                artifact = msg.get("content") or ""
                break
            if len(store.calls) + len(calls) > budget.max_external_queries:
                outcome, breach = "budget_exceeded", {
                    "limit": "max_external_queries"}
                break
            for call in calls:
                fn = call.get("function", {}) or {}
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = {}
                try:
                    result = store.call(fn.get("name", ""), args)
                except Exception as exc:  # a bad tool call is data, not a crash
                    result = {"error": str(exc)}
                messages.append({"role": "tool", "tool_call_id": call.get("id", ""),
                                 "content": json.dumps(result)})

        usage.runtime_seconds = time.perf_counter() - started
        try:
            usage.cost_usd = self.prices.quote(
                self.model, usage.input_tokens, usage.output_tokens)
        except VeniceError:
            usage.cost_usd = 0.0

        return Phenotype(
            run_id=uuid.uuid4().hex[:12], genome_id=genome.genome_id,
            environment_id=environment.environment_id, seed=seed,
            artifact=artifact,
            transcript=[{"role": m.get("role", ""),
                         "content": str(m.get("content", ""))[:4000]}
                        for m in messages],
            tool_calls=store.calls, usage=usage, outcome=outcome,
            budget_breach=breach, model=self.model)


class VeniceJudge:
    name = "venice-judge"

    def __init__(self, model: str = DEFAULT_JUDGE, prices: PriceBook | None = None):
        self.model = model
        self.prices = prices or PriceBook()

    def compare(self, brief_a: str, brief_b: str, environment: Environment,
                purpose: str) -> str:
        prompt = (
            f"Purpose of this workflow: {purpose}\n\n"
            "An MSL has ten minutes before a meeting with this expert. Which of "
            "these two briefs better prepares them for that conversation?\n\n"
            "Better: questions only this expert could be asked; correctly "
            "identifies what changed; states uncertainty plainly; prepares the "
            "MSL to listen, not only to talk; readable in ten minutes.\n"
            "Worse: generic questions; comprehensive but unreadable; confident "
            "where evidence is thin; characterisations the expert would resent.\n\n"
            f"SOURCE MATERIAL:\n{environment.source_text()[:12000]}\n\n"
            f"--- BRIEF A ---\n{brief_a[:12000]}\n\n"
            f"--- BRIEF B ---\n{brief_b[:12000]}\n\n"
            "Answer with exactly one of A, B or TIE on the first line, then at "
            "most four sentences of reasoning."
        )
        resp = _request("/chat/completions", {
            "model": self.model, "temperature": 0,
            "messages": [{"role": "user", "content": prompt}],
        }, method="POST")
        text = ((resp.get("choices") or [{}])[0].get("message", {}) or {}).get(
            "content", "") or ""
        head = text.strip().splitlines()[0].strip().upper() if text.strip() else "TIE"
        for token in ("TIE", "A", "B"):
            if head.startswith(token):
                return token
        return "TIE"
