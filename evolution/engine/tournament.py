"""Blinded pairwise selection and the measured neutral band.

Absolute rubric scores from a model are noisiest exactly at the margins that
decide a tournament, so selection is a comparison, not a score. The judge sees
two briefs with identity and metadata stripped, in randomised order, and may
return a tie.
"""
from __future__ import annotations

import random
import re
import statistics
from dataclasses import dataclass, field

from .environment import Environment
from .phenotype import Phenotype

IDENTITY_PATTERNS = [
    re.compile(r"<!--\s*mock-quality:.*?-->\s*", re.S),   # mock marker: judged blind
    re.compile(r"^\s*genome[_ ]?id\s*:.*$", re.M | re.I),
    re.compile(r"^\s*generation\s*:.*$", re.M | re.I),
    re.compile(r"^\s*mutation\s*:.*$", re.M | re.I),
]


def blind(text: str, keep_marker: bool = False) -> str:
    """Strip anything that identifies which candidate produced this brief."""
    out = text
    for i, pattern in enumerate(IDENTITY_PATTERNS):
        if i == 0 and keep_marker:
            continue
        out = pattern.sub("", out)
    return out.strip()


@dataclass
class Matchup:
    candidate: str
    opponent: str
    environment_id: str
    wins: int = 0
    losses: int = 0
    ties: int = 0

    @property
    def decisive(self) -> int:
        return self.wins + self.losses

    @property
    def win_rate(self) -> float:
        """Ties count as half, so a fully tied matchup reads as 0.5."""
        total = self.wins + self.losses + self.ties
        return 0.5 if total == 0 else (self.wins + 0.5 * self.ties) / total


@dataclass
class TournamentResult:
    candidate: str
    opponent: str
    matchups: list[Matchup] = field(default_factory=list)

    @property
    def win_rate(self) -> float:
        return (statistics.fmean(m.win_rate for m in self.matchups)
                if self.matchups else 0.5)

    def classify(self, band: float | None, epsilon: float = 1e-9) -> str:
        """Outside the band is a result; inside it is noise.

        The comparison carries an epsilon because a win rate and a band
        measured from the same small sample land on identical values often
        enough to matter — 5/6 against a band of 1/3 being the obvious case.
        A tie on the boundary is neutral, never better.
        """
        if band is None:
            return "unmeasured"
        if self.win_rate > 0.5 + band + epsilon:
            return "better"
        if self.win_rate < 0.5 - band - epsilon:
            return "worse"
        return "neutral"


def compare(judge, candidate: Phenotype, opponent: Phenotype,
            env: Environment, purpose: str, seed: int,
            keep_marker: bool = True) -> str:
    """One blinded comparison. Position is randomised and then undone."""
    rng = random.Random(f"{candidate.run_id}:{opponent.run_id}:{seed}")
    candidate_first = rng.random() < 0.5
    a = blind(candidate.artifact, keep_marker) if candidate_first else blind(opponent.artifact, keep_marker)
    b = blind(opponent.artifact, keep_marker) if candidate_first else blind(candidate.artifact, keep_marker)
    verdict = judge.compare(a, b, env, purpose)
    if verdict == "TIE":
        return "TIE"
    picked_a = verdict == "A"
    return "WIN" if picked_a == candidate_first else "LOSS"


def run_tournament(judge, candidate_runs: dict[str, list[Phenotype]],
                   opponent_runs: dict[str, list[Phenotype]],
                   environments: dict[str, Environment], purpose: str,
                   candidate_id: str, opponent_id: str,
                   repetitions: int = 3) -> TournamentResult:
    result = TournamentResult(candidate=candidate_id, opponent=opponent_id)
    for env_id, env in environments.items():
        cands = candidate_runs.get(env_id, [])
        opps = opponent_runs.get(env_id, [])
        if not cands or not opps:
            continue
        m = Matchup(candidate_id, opponent_id, env_id)
        for i in range(repetitions):
            outcome = compare(judge, cands[i % len(cands)], opps[i % len(opps)],
                              env, purpose, seed=i)
            if outcome == "WIN":
                m.wins += 1
            elif outcome == "LOSS":
                m.losses += 1
            else:
                m.ties += 1
        result.matchups.append(m)
    return result


def _rate(judge, cand_runs, opp_runs, environments, purpose, repetitions, salt):
    """The tournament statistic: mean per-environment win rate."""
    rates = []
    for env_id, env in environments.items():
        cands, opps = cand_runs.get(env_id, []), opp_runs.get(env_id, [])
        if not cands or not opps:
            continue
        m = Matchup("a", "b", env_id)
        for i in range(repetitions):
            outcome = compare(judge, cands[i % len(cands)], opps[i % len(opps)],
                              env, purpose, seed=salt * 97 + i)
            if outcome == "WIN":
                m.wins += 1
            elif outcome == "LOSS":
                m.losses += 1
            else:
                m.ties += 1
        rates.append(m.win_rate)
    return statistics.fmean(rates) if rates else 0.5


def measure_neutral_band(judge, runs_by_env: dict, environments: dict,
                         purpose: str, repetitions: int = 3,
                         replicates: int = 16) -> dict:
    """Measure the noise floor of the statistic the tournament actually reports.

    The ancestor is run repeatedly and then made to compete against ITSELF:
    each replicate splits its runs into two disjoint sides and computes a full
    tournament win rate. Both sides came from the same genome, so every
    deviation from 0.5 is noise. The largest deviation observed is the band.

    Measuring single comparisons instead would be useless: one comparison can
    only score 0, 0.5 or 1, so the "noise" would always look like 0.5 and no
    candidate could ever be shown to differ from the champion.
    """
    per_env = min(len(v) for v in runs_by_env.values()) if runs_by_env else 0
    if per_env < 4:
        raise ValueError(
            f"the probe needs at least 4 ancestor runs per environment to split "
            f"into two independent sides; got {per_env}")

    observed = []
    for r in range(replicates):
        side_a, side_b = {}, {}
        for env_id, runs in runs_by_env.items():
            order = list(runs)
            random.Random(f"probe:{env_id}:{r}").shuffle(order)
            half = len(order) // 2
            side_a[env_id], side_b[env_id] = order[:half], order[half:]
        observed.append(_rate(judge, side_a, side_b, environments, purpose,
                              repetitions, salt=r))

    band = max(abs(x - 0.5) for x in observed)
    return {
        # Full precision on purpose. Rounding the band lets a win rate of
        # exactly 5/6 cross a threshold of 0.8333 on a display artifact, which
        # is how a null candidate gets crowned.
        "value": band,
        "value_display": round(band, 4),
        "probe_runs": sum(len(v) for v in runs_by_env.values()),
        "runs_per_environment": per_env,
        "comparisons": replicates * repetitions * len(environments),
        "replicates": replicates,
        "measured_from": "ancestor self-competition across "
                         f"{len(environments)} environments",
        "observed_win_rates": [round(x, 4) for x in observed],
    }
