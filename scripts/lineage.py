#!/usr/bin/env python3
"""Inspect the evolutionary record.

    python3 scripts/lineage.py tree   kol-engagement-brief
    python3 scripts/lineage.py list   kol-engagement-brief
    python3 scripts/lineage.py show   kol-engagement-brief --genome kol-engagement-brief/g1a

Nothing here deletes. Mortality means a candidate stops receiving resources;
an extinct lineage keeps its genome, its scores and its failures so that it
can be resurrected when the models or the environment change.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "evolution"))

from engine import lineage  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("tree", "list"):
        p = sub.add_parser(name)
        p.add_argument("workflow")
    p = sub.add_parser("show")
    p.add_argument("workflow")
    p.add_argument("--genome", required=True)
    args = ap.parse_args()

    if args.cmd == "tree":
        print()
        print(lineage.tree(args.workflow))
        print()
        return 0

    entries = lineage.read(args.workflow)
    if args.cmd == "list":
        print(f"\n  {'genome':<10}{'gen':<5}{'verdict':<13}{'win':<7}{'experiment'}")
        for e in entries:
            rate = e.get("pairwise_win_rate")
            rate_s = f"{rate:.2f}" if isinstance(rate, float) else "  — "
            print(f"  {e['genome_id'].split('/')[-1]:<10}{e.get('generation',0):<5}"
                  f"{e['verdict']:<13}{rate_s:<7}{e.get('experiment_id','')}")
        print(f"\n  {len(entries)} records\n")
        return 0

    matches = [e for e in entries if e["genome_id"] == args.genome]
    if not matches:
        print(f"  no record for {args.genome}")
        return 1
    print(json.dumps(matches[-1], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
