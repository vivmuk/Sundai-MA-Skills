"""The observable behaviour of one genome in one environment on one run."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, asdict


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0
    model_calls: int = 0
    cost_usd: float = 0.0
    runtime_seconds: float = 0.0


@dataclass
class Phenotype:
    run_id: str
    genome_id: str
    environment_id: str
    seed: int
    artifact: str                       # the brief itself
    transcript: list[dict] = field(default_factory=list)
    tool_calls: list[dict] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)
    outcome: str = "complete"           # complete|budget_exceeded|adapter_error|refused
    budget_breach: dict | None = None
    model: str = ""

    @property
    def artifact_sha256(self) -> str:
        return hashlib.sha256(self.artifact.encode()).hexdigest()

    def to_dict(self) -> dict:
        d = asdict(self)
        d["artifact_sha256"] = self.artifact_sha256
        return d
