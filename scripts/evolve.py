#!/usr/bin/env python3
"""Run the MA Evolution Engine.

    python3 scripts/evolve.py list
    python3 scripts/evolve.py show   kol-engagement-brief
    python3 scripts/evolve.py probe  kol-engagement-brief --runs 5 --yes
    python3 scripts/evolve.py run    kol-engagement-brief --yes
    python3 scripts/evolve.py tree   kol-engagement-brief

Nothing executes until the cost preflight has been shown and confirmed.
The engine writes only under evolution/lineages/ and evolution/experiments/.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "evolution"))

import yaml  # noqa: E402

from engine import adapters, gates, lineage, tournament  # noqa: E402
from engine.cost import BudgetExceeded, Ledger, Preflight  # noqa: E402
from engine.environment import load_all as load_environments  # noqa: E402
from engine.genome import load_all as load_genomes  # noqa: E402
from engine.paths import (EXPERIMENTS, LINEAGES, POLICIES, REGISTRY,  # noqa: E402
                          assert_writable)
from engine.adapters.base import Budget  # noqa: E402


def registry() -> dict:
    return yaml.safe_load(REGISTRY.read_text())["workflows"]


def policy() -> dict:
    return yaml.safe_load((POLICIES / "default-evolution-policy.yaml").read_text())


def band_path(workflow: str) -> Path:
    return LINEAGES / workflow / "neutral-band.json"


def load_band(workflow: str) -> dict | None:
    p = band_path(workflow)
    return json.loads(p.read_text()) if p.exists() else None


def build_runtime(pol: dict, args) -> tuple:
    name = args.adapter or pol["execution"]["adapter"]
    if name == "mock":
        return adapters.MockAdapter(), adapters.MockJudge(), "mock", "mock-judge"
    from engine.adapters.venice import PriceBook, VeniceAdapter, VeniceJudge
    prices = PriceBook()
    ex = pol["execution"]["executor_model"]
    jd = pol["execution"]["judge_model"]
    return VeniceAdapter(ex, prices), VeniceJudge(jd, prices), ex, jd


def execute(adapter, genome, envs, budget, reps, ledger) -> dict:
    """Run one genome across every environment, reps times each."""
    runs: dict[str, list] = {}
    for env in envs:
        runs[env.environment_id] = []
        for seed in range(reps):
            ph = adapter.run(genome, env, budget, seed)
            ledger.charge(ph.usage.cost_usd)
            runs[env.environment_id].append(ph)
    return runs


def gate_report(runs: dict, envs_by_id: dict) -> tuple[str, list[str]]:
    """Worst verdict across every run, with the findings that produced it."""
    worst, findings = "pass", []
    for env_id, phenos in runs.items():
        env = envs_by_id[env_id]
        for ph in phenos:
            results = gates.run_gates(ph, env)
            v = gates.verdict(results)
            for r in results:
                for f in r.findings:
                    findings.append(f"[{env_id}] {r.gate}: {f}")
            if v == "extinct":
                worst = "extinct"
            elif v == "quarantined" and worst != "extinct":
                worst = "quarantined"
    return worst, findings


def cmd_list(args) -> int:
    print("\n  Workflows in the evolution registry\n")
    for name, spec in registry().items():
        status = spec.get("status", "?")
        mark = "*" if status == "active" else " "
        print(f"  {mark} {name:<34} {status}")
    print("\n  * evolvable now; others need environments and a rubric first.\n")
    return 0


def cmd_show(args) -> int:
    wf = args.workflow
    spec = registry()[wf]
    genomes = load_genomes(wf)
    envs = load_environments(wf)
    band = load_band(wf)
    champ = lineage.champion(wf) or "canonical ancestor (g0)"
    print(f"\n  {wf}\n  {'=' * len(wf)}\n")
    print(f"  purpose      {' '.join(spec['purpose']['statement'].split())[:70]}...")
    print(f"  ancestor     {spec['ancestor']['skill']} v{spec['ancestor']['version']}")
    print(f"  requires     {', '.join(spec['requires'])}")
    print(f"  genomes      {len(genomes)}: {', '.join(sorted(g.short_id for g in genomes.values()))}")
    print(f"  environments {len(envs)}: {', '.join(e.environment_id for e in envs)}")
    print(f"  champion     {champ}")
    if band:
        print(f"  neutral band ±{band['value']:.3f} "
              f"(measured from {band['probe_runs']} runs, {band['comparisons']} comparisons)")
    else:
        print("  neutral band NOT MEASURED — run `probe` first; no champion can be "
              "declared until it is")
    print()
    return 0


def cmd_probe(args) -> int:
    """Measure the noise floor by comparing the ancestor against itself."""
    wf = args.workflow
    pol = policy()
    adapter, judge, ex_model, jd_model = build_runtime(pol, args)
    genomes = load_genomes(wf)
    ancestor = genomes[f"{wf}/g0"]
    budget = Budget(**{k: v for k, v in pol["resources"]["per_candidate"].items()})

    envs = load_environments(wf)
    est = adapter.estimate(ancestor, envs[0], budget)
    total_runs = args.runs * len(envs)
    comparisons = 16 * 3 * len(envs)
    pre = Preflight(runs=total_runs, per_run=est, judge_comparisons=comparisons,
                    judge_cost_each=0.019,
                    max_usd=pol["resources"]["per_experiment"]["max_usd"],
                    label=f"noise-floor probe — {wf} "
                          f"({args.runs} ancestor runs x {len(envs)} environments)")
    if not pre.confirm(args.yes):
        print("  aborted before spending anything.")
        return 1

    ledger = Ledger(estimate_usd=pre.total_usd, max_usd=pre.max_usd)
    runs_by_env = {}
    for env in envs:
        runs_by_env[env.environment_id] = []
        for seed in range(args.runs):
            ph = adapter.run(ancestor, env, budget, seed)
            ledger.charge(ph.usage.cost_usd)
            runs_by_env[env.environment_id].append(ph)

    purpose = registry()[wf]["purpose"]["statement"]
    envs_by_id = {e.environment_id: e for e in envs}
    band = tournament.measure_neutral_band(judge, runs_by_env, envs_by_id, purpose)
    band["measured_at"] = datetime.now(timezone.utc).isoformat()
    band["executor_model"] = ex_model
    band["judge_model"] = jd_model
    path = assert_writable(band_path(wf))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(band, indent=2) + "\n")

    print(f"  The ancestor was run {args.runs} times on each of {len(envs)} environments")
    print(f"  and made to compete against itself over {band['replicates']} replicates.\n")
    print(f"  observed win rates   {band['observed_win_rates']}")
    print(f"  NEUTRAL BAND         ±{band['value']:.4f}\n")
    print("  Both sides of every comparison came from the same genome, so every")
    print("  deviation from 0.50 above is noise. A candidate inside this band has")
    print("  not been shown to differ from the champion.\n")
    print(f"  written to {path.relative_to(REPO)}")
    print(f"  actual spend ${ledger.actual_usd:,.2f} (estimated ${pre.total_usd:,.2f})\n")
    return 0


def cmd_run(args) -> int:
    wf = args.workflow
    pol = policy()
    adapter, judge, ex_model, jd_model = build_runtime(pol, args)
    genomes = load_genomes(wf)
    envs = load_environments(wf)
    envs_by_id = {e.environment_id: e for e in envs}
    reps = args.reps or pol["population"]["runs_per_candidate"]
    budget = Budget(**{k: v for k, v in pol["resources"]["per_candidate"].items()})

    ancestor = genomes[f"{wf}/g0"]
    champion_id = lineage.champion(wf) or ancestor.genome_id
    candidates = [g for gid, g in sorted(genomes.items())
                  if g.generation == args.generation]
    if not candidates:
        print(f"  no genomes at generation {args.generation}")
        return 1

    band = load_band(wf)
    if band is None and not args.allow_unmeasured:
        print("\n  REFUSING TO RUN: the neutral band has not been measured.\n"
              "  Without it, any difference between candidates is unattributable.\n"
              "  Run:  python3 scripts/evolve.py probe " + wf + "\n")
        return 2

    total_runs = (len(candidates) + 1) * len(envs) * reps
    comparisons = len(candidates) * len(envs) * pol["selection"]["repetitions"] \
        if "repetitions" in pol["selection"] else len(candidates) * len(envs) * 3
    est = adapter.estimate(ancestor, envs[0], budget)
    pre = Preflight(runs=total_runs, per_run=est, judge_comparisons=comparisons,
                    judge_cost_each=0.019,
                    max_usd=pol["resources"]["per_experiment"]["max_usd"],
                    label=f"generation {args.generation} — {wf} "
                          f"({len(candidates)} candidates x {len(envs)} environments x {reps})")
    if not pre.confirm(args.yes):
        print("  aborted before spending anything.")
        return 1

    # The lineage needs its root. Without a recorded ancestor every candidate
    # is an orphan and the tree cannot be drawn.
    if not any(x["genome_id"] == ancestor.genome_id for x in lineage.read(wf)):
        lineage.record(wf, {
            "genome_id": ancestor.genome_id, "parent": None, "generation": 0,
            "verdict": "champion",
            "verdict_reason": "canonical ancestor — the baseline everything is measured against",
            "mutation": {"operator": None, "rationale": "ancestor (no overlays)",
                         "author": "human"},
            "experiment_id": "baseline", "pairwise_win_rate": None,
            "inside_neutral_band": None, "gates_failed": [],
            "models": {"executor": ex_model, "judge": jd_model}, "cost_usd": 0.0,
            "artifacts_path": ancestor.base_skill_path,
        })

    experiment_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + f"-{wf}-g{args.generation}"
    ledger = Ledger(estimate_usd=pre.total_usd, max_usd=pre.max_usd,
                    fetched_at=est.fetched_at, prices=est.prices or {})
    purpose = registry()[wf]["purpose"]["statement"]
    results = []

    try:
        champion_runs = execute(adapter, genomes[champion_id], envs, budget, reps, ledger)
        for cand in candidates:
            runs = execute(adapter, cand, envs, budget, reps, ledger)
            verdict, findings = gate_report(runs, envs_by_id)
            entry = {"genome_id": cand.genome_id, "parent": cand.parent,
                     "generation": cand.generation, "gates_failed": findings,
                     "mutation": {"operator": cand.overlays[0].operator if cand.overlays else None,
                                  "rationale": cand.overlays[0].rationale if cand.overlays else "",
                                  "author": cand.overlays[0].author if cand.overlays else "human"},
                     "experiment_id": experiment_id,
                     "models": {"executor": ex_model, "judge": jd_model},
                     "cost_usd": round(sum(p.usage.cost_usd for rs in runs.values() for p in rs), 4)}

            if verdict in {"extinct", "quarantined"}:
                entry["verdict"] = verdict
                entry["verdict_reason"] = findings[0] if findings else verdict
                entry["pairwise_win_rate"] = None
                entry["inside_neutral_band"] = None
            else:
                t = tournament.run_tournament(
                    judge, runs, champion_runs, envs_by_id, purpose,
                    cand.genome_id, champion_id, repetitions=3)
                cls = t.classify(band["value"] if band else None)
                entry["pairwise_win_rate"] = round(t.win_rate, 4)
                entry["inside_neutral_band"] = cls == "neutral"
                entry["verdict"] = {"better": "champion", "neutral": "neutral",
                                    "worse": "extinct", "unmeasured": "neutral"}[cls]
                entry["verdict_reason"] = (
                    f"win rate {t.win_rate:.2f} vs {champion_id.split('/')[-1]}, "
                    f"band ±{band['value']:.3f}" if band else "band unmeasured")
            entry["artifacts_path"] = f"evolution/experiments/{experiment_id}/{cand.short_id}/"
            results.append((entry, runs))
    except BudgetExceeded as exc:
        print(f"\n  BUDGET ABORT: {exc}\n")
        return 3

    # Only the best candidate outside the band becomes champion; others revert
    # to neutral. Two champions in one generation is not a result, it is a tie.
    winners = sorted([e for e, _ in results if e["verdict"] == "champion"],
                     key=lambda e: -(e["pairwise_win_rate"] or 0))
    for e in winners[1:]:
        e["verdict"] = "neutral"
        e["verdict_reason"] += " (outperformed by a sibling this generation)"

    out = assert_writable(EXPERIMENTS / experiment_id)
    out.mkdir(parents=True, exist_ok=True)
    for entry, runs in results:
        d = out / entry["genome_id"].split("/")[-1]
        d.mkdir(exist_ok=True)
        for env_id, phenos in runs.items():
            for i, ph in enumerate(phenos):
                (d / f"{env_id}.run{i}.md").write_text(ph.artifact)
        (d / "phenotypes.json").write_text(json.dumps(
            {k: [p.to_dict() for p in v] for k, v in runs.items()}, indent=2, default=str))
        lineage.record(wf, entry)

    manifest = {
        "experiment_id": experiment_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "policy": {"path": "evolution/policies/default-evolution-policy.yaml"},
        "environments": [{"environment_id": e.environment_id, "evidence_mode": "replay",
                          **e.digests()} for e in envs],
        "genomes": [c.genome_id for c in candidates],
        "models": {"executor": {"id": ex_model, "adapter": adapter.name},
                   "judge": {"id": jd_model}},
        "neutral_band": band,
        "cost": {**ledger.to_dict(), "confirmed_by_operator": True, "budget_aborted": False},
        "results": [e for e, _ in results],
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str) + "\n")

    print(f"\n  GENERATION {args.generation} — {wf}")
    print(f"  {'-' * 62}")
    print(f"  {'cand':<6}{'verdict':<13}{'win':<7}{'reason'}")
    for entry, _ in results:
        rate = entry["pairwise_win_rate"]
        rate_s = f"{rate:.2f}" if isinstance(rate, float) else "  — "
        print(f"  {entry['genome_id'].split('/')[-1]:<6}"
              f"{entry['verdict']:<13}{rate_s:<7}{entry['verdict_reason'][:60]}")
    print(f"  {'-' * 62}")
    print(f"  estimated ${pre.total_usd:,.2f}   actual ${ledger.actual_usd:,.2f}   "
          f"runs {ledger.runs}")
    print(f"  manifest  {(out / 'manifest.json').relative_to(REPO)}\n")
    return 0


def cmd_tree(args) -> int:
    print()
    print(lineage.tree(args.workflow))
    print()
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    for name in ("show", "tree"):
        p = sub.add_parser(name)
        p.add_argument("workflow")
    p = sub.add_parser("probe")
    p.add_argument("workflow")
    p.add_argument("--runs", type=int, default=4,
               help="ancestor runs PER ENVIRONMENT; 4 is the minimum "
                    "that allows two independent sides")
    p.add_argument("--adapter")
    p.add_argument("--yes", action="store_true")
    p = sub.add_parser("run")
    p.add_argument("workflow")
    p.add_argument("--generation", type=int, default=1)
    p.add_argument("--reps", type=int)
    p.add_argument("--adapter")
    p.add_argument("--yes", action="store_true")
    p.add_argument("--allow-unmeasured", action="store_true",
                   help="run without a measured neutral band (results are unattributable)")
    args = ap.parse_args()
    return {"list": cmd_list, "show": cmd_show, "probe": cmd_probe,
            "run": cmd_run, "tree": cmd_tree}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
