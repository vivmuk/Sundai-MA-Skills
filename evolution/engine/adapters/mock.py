"""Mock adapter — the engine's test harness.

It replays a deterministic phenotype built from the environment's own
material. This proves the PLUMBING: that overlays apply, gates fire on the
right things, the tournament ranks, the band is measured, the lineage records
and the promotion path builds a diff. It proves nothing whatsoever about
whether an evolved skill writes a better brief — only a real runtime can say
that. Keeping the two claims apart is the entire point of having this adapter.

The brief carries a hidden `mock-quality` marker that MockJudge reads. No
real judge has anything like it.
"""
from __future__ import annotations

import hashlib
import random
import time
import uuid

from ..environment import Environment
from ..evidence import EvidenceStore
from ..genome import Genome
from ..phenotype import Phenotype, Usage
from .base import Budget, CostEstimate

QUALITY_MARKER = "<!-- mock-quality: {:.4f} -->"


def _latent_quality(genome: Genome, seed: int, noise: float) -> float:
    """Latent quality of this genome on this run: a stable base plus noise.

    The noise is what makes the neutral-band probe meaningful — without it,
    repeated runs would be identical and the band would measure zero, which
    is exactly the false confidence the band exists to prevent.
    """
    declared = genome.runtime.get("mock_quality")
    if declared is None:
        h = hashlib.sha256(genome.genome_id.encode()).digest()
        declared = 0.50 + (h[0] / 255.0) * 0.10
    rng = random.Random(f"{genome.genome_id}:{seed}")
    return max(0.0, min(1.0, float(declared) + rng.uniform(-noise, noise)))


class MockAdapter:
    name = "mock"

    def __init__(self, defects: tuple[str, ...] = (), noise: float = 0.03,
                 price_per_run: float = 0.65):
        self.defects = tuple(defects)
        self.noise = noise
        self.price_per_run = price_per_run

    def estimate(self, genome: Genome, environment: Environment,
                 budget: Budget) -> CostEstimate:
        src = len(environment.source_text()) // 4
        skill = len(genome.express()) // 4
        return CostEstimate(
            input_tokens=(src + skill) * 8,
            output_tokens=6000,
            cost_usd=self.price_per_run,
            prices={"mock": "fixed"},
            fetched_at="n/a (mock adapter)",
        )

    def run(self, genome: Genome, environment: Environment,
            budget: Budget, seed: int) -> Phenotype:
        started = time.perf_counter()
        store = EvidenceStore(environment.evidence)
        store.call("pubmed_search", {"query": environment.target_expert, "limit": 5})
        store.call("trials_search", {"query": environment.target_expert, "limit": 5})

        quality = _latent_quality(genome, seed, self.noise)
        artifact = self._compose(genome, environment, store, quality)

        if len(store.calls) > budget.max_external_queries:
            return Phenotype(
                run_id=uuid.uuid4().hex[:12], genome_id=genome.genome_id,
                environment_id=environment.environment_id, seed=seed,
                artifact=artifact, tool_calls=store.calls, outcome="budget_exceeded",
                budget_breach={"limit": "max_external_queries",
                               "value": len(store.calls)},
                model="mock")

        return Phenotype(
            run_id=uuid.uuid4().hex[:12],
            genome_id=genome.genome_id,
            environment_id=environment.environment_id,
            seed=seed,
            artifact=artifact,
            transcript=[{"role": "system", "content": f"<skill {genome.digest()[:12]}>"},
                        {"role": "assistant", "content": "<brief>"}],
            tool_calls=store.calls,
            usage=Usage(input_tokens=24000, output_tokens=6000, model_calls=4,
                        cost_usd=self.price_per_run,
                        runtime_seconds=time.perf_counter() - started),
            outcome="complete",
            model="mock",
        )

    def _compose(self, genome: Genome, env: Environment,
                 store: EvidenceStore, quality: float) -> str:
        exp = env.expectations
        pubs = store.publications[:3]
        trials = store.trials[:2]
        d = self.defects

        surfaced = [] if "science" in d else [
            (i.get("match") or [i.get("claim", "")])[0] for i in exp.must_surface]
        escalations = [] if "safety" in d else [
            f"- {(i.get('match') or [i.get('finding','')])[0]} "
            f"(source record {i.get('source_record','')}) — simulated workshop "
            f"finding; not submitted to any real system."
            for i in exp.must_escalate]
        routes = [] if "boundaries" in d else [
            f"- {' '.join(i.get('required_handling', '').split())}"
            for i in exp.must_route]

        cites = [f"PMID {p['pmid']}" for p in pubs if p.get("pmid")]
        if "citation" in d:
            cites.append("PMID 99999999")
        trial_ids = [t["nct_id"] for t in trials if t.get("nct_id")]

        blocks = [
            QUALITY_MARKER.format(quality),
            "DRAFT — NOT FOR EXTERNAL USE. REQUIRES QUALIFIED MEDICAL REVIEW.",
            "SYNTHETIC WORKSHOP MATERIAL.",
            "",
            f"# KOL engagement brief — {env.target_expert}",
            "",
            "## WHO THEY ARE",
            f"{env.target_expert}. {env.situation}",
            "",
            "## WHAT THEY CARE ABOUT",
            *[f"- {s}" for s in surfaced],
            *[f"- Publication trajectory: {p['title']} ({p.get('year','')})" for p in pubs],
            "",
            "## WHAT'S CHANGED",
            *([f"- {s}" for s in surfaced] or ["- No change identified since last contact."]),
            "",
            "## ASK THEM",
            f"- What would you need to see before applying that outside a trial setting?",
            f"- Where does the current evidence stop being usable for your patients?",
            "",
            "## THEY MAY ASK",
            "- Durability beyond the reported follow-up. The honest answer is that",
            "  we do not have it; the data are immature.",
            "",
            "## KNOW COLD",
            "- Overall response rate 62.5% (95% CI 54.8-69.8), single-arm,",
            "  open-label phase 1/2, N=168 — no comparative claim available.",
            *([f"- Trial involvement: {t}" for t in trial_ids]),
            "",
            "## BOUNDARIES",
            "- Approved indication only; the product is indicated for adults with",
            "  at least four prior lines of therapy in this jurisdiction.",
            "- Unapproved and off-label uses are discussed only in response to an",
            "  unsolicited question, routed to medical information.",
            "- Any adverse event mentioned in conversation must be reported.",
            *routes,
            "",
            "## SAFETY",
            *(escalations or ["- No safety, PQC or special-situation record identified "
                              "in the supplied material."]),
            "",
            "## PROVENANCE",
            f"- Searches run: pubmed_search, trials_search (query: {env.target_expert}).",
            f"- Sources retrieved: {', '.join(cites) if cites else 'none'}.",
            "- Could not be determined: " + ("; ".join(exp.known_gaps) or "nothing noted"),
        ]
        if "provenance" in d:
            blocks = [b for b in blocks if not b.startswith("## PROVENANCE")
                      and not b.startswith("- Searches run")]
        if "science" in d and exp.must_not_say:
            blocks.append(exp.must_not_say[0].get("example",
                          "This shows superiority over the competitor."))
        return "\n".join(blocks) + "\n"


class MockJudge:
    """Reads the hidden quality marker. A real judge reads the brief."""
    name = "mock-judge"

    def __init__(self, tie_threshold: float = 0.02):
        self.tie_threshold = tie_threshold

    @staticmethod
    def _quality(text: str) -> float:
        for line in text.splitlines():
            if "mock-quality:" in line:
                return float(line.split("mock-quality:")[1].split("-->")[0])
        return 0.5

    def compare(self, brief_a: str, brief_b: str, environment: Environment,
                purpose: str) -> str:
        qa, qb = self._quality(brief_a), self._quality(brief_b)
        if abs(qa - qb) < self.tie_threshold:
            return "TIE"
        return "A" if qa > qb else "B"
