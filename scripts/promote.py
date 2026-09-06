#!/usr/bin/env python3
"""Propose a champion for promotion into the canonical skill.

    python3 scripts/promote.py kol-engagement-brief
    python3 scripts/promote.py kol-engagement-brief --genome kol-engagement-brief/g1a

Writes a patch and a pull-request body into evolution/experiments/. It does
NOT edit the skill: the engine's write boundary forbids it, and promotion is a
pull request a human merges. That merge is the only approval path.
"""
from __future__ import annotations

import argparse
import difflib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "evolution"))

from engine import lineage  # noqa: E402
from engine.genome import load_all as load_genomes  # noqa: E402
from engine.paths import EXPERIMENTS, assert_writable  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("workflow")
    ap.add_argument("--genome", help="defaults to the recorded champion")
    args = ap.parse_args()
    wf = args.workflow

    genome_id = args.genome or lineage.champion(wf)
    if not genome_id:
        print("  no champion recorded — run an experiment first.")
        return 1
    genomes = load_genomes(wf)
    if genome_id not in genomes:
        print(f"  unknown genome {genome_id}")
        return 1
    genome = genomes[genome_id]
    if not genome.overlays:
        print(f"  {genome_id} is the ancestor; there is nothing to promote.")
        return 1

    entries = [e for e in lineage.read(wf) if e["genome_id"] == genome_id]
    if not entries:
        print(f"  {genome_id} has no lineage record — it has never been evaluated.")
        return 1
    latest = entries[-1]
    if latest["verdict"] != "champion":
        print(f"  {genome_id} is recorded as '{latest['verdict']}', not champion. "
              f"Only a champion may be proposed.")
        return 1

    skill_path = Path(genome.base_skill_path)
    before = (REPO / skill_path).read_text().splitlines(keepends=True)
    after = genome.express().splitlines(keepends=True)
    patch = "".join(difflib.unified_diff(
        before, after, fromfile=f"a/{skill_path}", tofile=f"b/{skill_path}"))

    # Namespaced by workflow: every workflow's first champion is called g1a,
    # so keying on the genome's short id alone makes five proposals collide in
    # one directory and only the last one survive.
    out = assert_writable(EXPERIMENTS / f"promotion-{wf}-{genome.short_id}")
    out.mkdir(parents=True, exist_ok=True)
    (out / "proposal.patch").write_text(patch)

    mutation = latest.get("mutation", {})
    body = f"""## What this changes

Promotes `{genome_id}` into `{skill_path}`. The change was produced by the
Evolution Engine and selected by blinded pairwise comparison against the
previous champion, not by an absolute score.

## The mutation

**Operator:** `{mutation.get('operator')}` · **authored by:** {mutation.get('author')}

{mutation.get('rationale', '').strip()}

## Evidence

| | |
|---|---|
| experiment | `{latest.get('experiment_id')}` |
| win rate vs previous champion | {latest.get('pairwise_win_rate')} |
| inside the measured neutral band | {latest.get('inside_neutral_band')} |
| verdict | {latest.get('verdict')} — {latest.get('verdict_reason')} |
| executor / judge | {latest.get('models', {}).get('executor')} / {latest.get('models', {}).get('judge')} |
| hard gates | all passed (a failure is not promotable at any score) |
| cost | ${latest.get('cost_usd')} |

Artifacts and the full reproducibility manifest: `{latest.get('artifacts_path')}`

## What a reviewer should check

- The diff says what the rationale claims it says.
- The Level 1 purpose and the registry invariants are untouched.
- The mutation is an improvement in method, not a loosening of a boundary.

A win rate outside the neutral band means the change was measurable. It does
not mean it is correct — that judgement is what this pull request is for.

---
_Proposed by the MA Evolution Engine. Generated {datetime.now(timezone.utc).date()}._
"""
    (out / "PR-BODY.md").write_text(body)
    (out / "evidence.json").write_text(json.dumps(latest, indent=2) + "\n")

    print(f"\n  PROMOTION PROPOSAL — {genome_id}\n  {'-' * 58}")
    print(f"  {len([l for l in patch.splitlines() if l.startswith('+') and not l.startswith('+++')])} lines added, "
          f"{len([l for l in patch.splitlines() if l.startswith('-') and not l.startswith('---')])} removed")
    print(f"  patch     {(out / 'proposal.patch').relative_to(REPO)}")
    print(f"  PR body   {(out / 'PR-BODY.md').relative_to(REPO)}")
    print(f"\n  The engine does not apply this. To promote it:\n")
    print(f"    git checkout -b promote/{wf}-{genome.short_id}")
    print(f"    git apply {(out / 'proposal.patch').relative_to(REPO)}")
    print(f"    python3 scripts/validate_skills.py && python3 scripts/build_index.py")
    print(f"    # then open a PR using {(out / 'PR-BODY.md').relative_to(REPO)}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
