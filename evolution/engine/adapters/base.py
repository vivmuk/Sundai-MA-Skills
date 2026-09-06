"""The runtime adapter contract.

The engine does not know what runs a candidate. It knows this interface.
The skills are the Medical Affairs knowledge; the harness is replaceable.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ..environment import Environment
from ..genome import Genome
from ..phenotype import Phenotype


@dataclass
class Budget:
    max_model_calls: int = 20
    max_external_queries: int = 15
    max_runtime_minutes: float = 10.0
    max_usd: float | None = None


@dataclass
class CostEstimate:
    input_tokens: int
    output_tokens: int
    cost_usd: float | None          # None when the runtime is not dollar-metered
    currency_note: str = ""
    prices: dict | None = None
    fetched_at: str = ""

    def render(self) -> str:
        if self.cost_usd is None:
            return (f"~{self.input_tokens:,} in / {self.output_tokens:,} out tokens; "
                    f"{self.currency_note}")
        return (f"~{self.input_tokens:,} in / {self.output_tokens:,} out tokens; "
                f"${self.cost_usd:,.2f}")


class Adapter(Protocol):
    name: str

    def estimate(self, genome: Genome, environment: Environment,
                 budget: Budget) -> CostEstimate: ...

    def run(self, genome: Genome, environment: Environment,
            budget: Budget, seed: int) -> Phenotype: ...


class Judge(Protocol):
    name: str

    def compare(self, brief_a: str, brief_b: str, environment: Environment,
                purpose: str) -> str:
        """Return 'A', 'B' or 'TIE'. Never sees the answer key."""
