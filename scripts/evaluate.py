#!/usr/bin/env python3
"""Re-run the gates over an experiment's stored artifacts.

    python3 scripts/evaluate.py 20260906T201735Z-kol-engagement-brief-g1

Gates are deterministic and free, so re-evaluating an old experiment after a
gate has been tightened is cheap — and it is how you find out whether a
champion would still pass today's checks.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "evolution"))

from engine import gates  # noqa: E402
from engine.environment import load_all as load_environments  # noqa: E402
from engine.paths import EXPERIMENTS  # noqa: E402
from engine.phenotype import Phenotype  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("experiment")
    args = ap.parse_args()

    root = EXPERIMENTS / args.experiment
    manifest_path = root / "manifest.json"
    if not manifest_path.exists():
        print(f"  no such experiment: {args.experiment}")
        return 1
    manifest = json.loads(manifest_path.read_text())
    workflow = manifest["genomes"][0].split("/")[0]
    envs = {e.environment_id: e for e in load_environments(workflow)}

    print(f"\n  RE-EVALUATION — {args.experiment}\n  {'-' * 62}")
    changed = 0
    for d in sorted(p for p in root.iterdir() if p.is_dir()):
        phenos = json.loads((d / "phenotypes.json").read_text())
        worst, findings = "pass", []
        for env_id, runs in phenos.items():
            for raw in runs:
                ph = Phenotype(run_id=raw["run_id"], genome_id=raw["genome_id"],
                               environment_id=env_id, seed=raw["seed"],
                               artifact=raw["artifact"], tool_calls=raw["tool_calls"])
                results = gates.run_gates(ph, envs[env_id])
                v = gates.verdict(results)
                findings += [f"[{env_id}] {r.gate}: {f}"
                             for r in results for f in r.findings]
                if v == "extinct":
                    worst = "extinct"
                elif v == "quarantined" and worst != "extinct":
                    worst = "quarantined"
        recorded = next((r["verdict"] for r in manifest["results"]
                         if r["genome_id"].endswith(d.name)), "?")
        drift = "" if (worst == "pass") == (recorded != "extinct") else "  <-- CHANGED"
        if drift:
            changed += 1
        print(f"  {d.name:<8}gates now: {worst:<12}recorded: {recorded:<12}{drift}")
        for f in findings[:3]:
            print(f"           {f[:88]}")
    print(f"  {'-' * 62}")
    print(f"  {changed} verdict(s) would change under today's gates\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
