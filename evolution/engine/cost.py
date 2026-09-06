"""Cost preflight.

Every experiment prints what it expects to spend and blocks for confirmation
before anything executes. Actuals are written beside the estimate so the
estimator corrects itself against reality instead of drifting.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field

from .adapters.base import CostEstimate


class BudgetExceeded(RuntimeError):
    """Raised mid-experiment when the spend ceiling is reached."""


@dataclass
class Preflight:
    runs: int
    per_run: CostEstimate
    judge_comparisons: int = 0
    judge_cost_each: float = 0.0
    max_usd: float | None = None
    label: str = "experiment"

    @property
    def execution_usd(self) -> float | None:
        return None if self.per_run.cost_usd is None else self.per_run.cost_usd * self.runs

    @property
    def judging_usd(self) -> float:
        return self.judge_comparisons * self.judge_cost_each

    @property
    def total_usd(self) -> float | None:
        ex = self.execution_usd
        return None if ex is None else ex + self.judging_usd

    def render(self) -> str:
        lines = [
            "",
            f"  COST PREFLIGHT — {self.label}",
            f"  {'-' * 54}",
            f"  candidate runs            {self.runs}",
            f"  tokens per run            ~{self.per_run.input_tokens:,} in / "
            f"{self.per_run.output_tokens:,} out",
        ]
        if self.per_run.cost_usd is None:
            lines += [f"  cost                      not dollar-metered "
                      f"({self.per_run.currency_note})"]
        else:
            lines += [
                f"  execution                 ${self.execution_usd:,.2f}",
                f"  judging ({self.judge_comparisons} comparisons)"
                f"{'':<6}${self.judging_usd:,.2f}",
                f"  {'-' * 54}",
                f"  TOTAL                     ${self.total_usd:,.2f}",
            ]
        if self.per_run.fetched_at:
            lines.append(f"  prices fetched            {self.per_run.fetched_at}")
        if self.max_usd is not None:
            lines.append(f"  hard ceiling              ${self.max_usd:,.2f}")
        lines.append("")
        return "\n".join(lines)

    def check_ceiling(self) -> None:
        total = self.total_usd
        if self.max_usd is not None and total is not None and total > self.max_usd:
            raise BudgetExceeded(
                f"estimated ${total:,.2f} exceeds the ceiling of "
                f"${self.max_usd:,.2f}. Raise per_experiment.max_usd in the "
                f"policy, or shrink the experiment.")

    def confirm(self, assume_yes: bool = False, stream=sys.stdin) -> bool:
        print(self.render())
        self.check_ceiling()
        if assume_yes:
            print("  proceeding (--yes)\n")
            return True
        if not stream.isatty():
            print("  refusing to spend without confirmation. Re-run with --yes "
                  "to proceed non-interactively.\n")
            return False
        reply = input("  proceed? [y/N] ").strip().lower()
        return reply in {"y", "yes"}


@dataclass
class Ledger:
    """Actual spend, accumulated as the experiment runs."""
    estimate_usd: float | None = None
    actual_usd: float = 0.0
    max_usd: float | None = None
    runs: int = 0
    prices: dict = field(default_factory=dict)
    fetched_at: str = ""

    def charge(self, amount: float) -> None:
        self.actual_usd += amount
        self.runs += 1
        if self.max_usd is not None and self.actual_usd > self.max_usd:
            raise BudgetExceeded(
                f"spend ceiling reached: ${self.actual_usd:,.2f} of "
                f"${self.max_usd:,.2f} after {self.runs} runs. Aborting.")

    def to_dict(self) -> dict:
        drift = None
        if self.estimate_usd:
            drift = round((self.actual_usd - self.estimate_usd) / self.estimate_usd, 3)
        return {
            "estimate_usd": self.estimate_usd,
            "actual_usd": round(self.actual_usd, 4),
            "estimate_error": drift,
            "prices": self.prices,
            "prices_fetched_at": self.fetched_at,
        }
