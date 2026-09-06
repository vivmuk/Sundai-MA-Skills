"""Append-only lineage.

Mortality means a candidate stops receiving evolutionary resources. It never
means deletion: a lineage that failed against today's model may succeed
against tomorrow's, and resurrection requires that the record survived.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .paths import LINEAGES, assert_writable


def _path(workflow: str) -> Path:
    return LINEAGES / workflow / "lineage.jsonl"


def record(workflow: str, entry: dict) -> dict:
    entry.setdefault("recorded_at", datetime.now(timezone.utc).isoformat())
    entry.setdefault("resurrectable", True)
    path = assert_writable(_path(workflow))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as fh:
        fh.write(json.dumps(entry, sort_keys=True) + "\n")
    return entry


def read(workflow: str) -> list[dict]:
    path = _path(workflow)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def champion(workflow: str) -> str | None:
    """The most recently recorded champion, or None."""
    for entry in reversed(read(workflow)):
        if entry.get("verdict") == "champion":
            return entry["genome_id"]
    return None


def tree(workflow: str) -> str:
    """An ASCII evolutionary tree of everything recorded so far."""
    entries = read(workflow)
    if not entries:
        return "(no lineage recorded yet)"
    latest: dict[str, dict] = {}
    for e in entries:
        latest[e["genome_id"]] = e
    known = set(latest)
    children: dict[str | None, list[dict]] = {}
    for e in latest.values():
        parent = e.get("parent")
        # An orphan — parent never recorded — roots rather than vanishing.
        children.setdefault(parent if parent in known else None, []).append(e)
    for kids in children.values():
        kids.sort(key=lambda e: e["genome_id"])

    mark = {"champion": "*", "neutral": "~", "quarantined": "!", "extinct": "x"}
    lines: list[str] = []

    def walk(parent: str | None, depth: int) -> None:
        for e in children.get(parent, []):
            gid = e["genome_id"].split("/")[-1]
            rate = e.get("pairwise_win_rate")
            rate_s = f"  win {rate:.2f}" if isinstance(rate, (int, float)) else ""
            reason = e.get("verdict_reason", "")
            lines.append(f"{'  ' * depth}{mark.get(e['verdict'], '?')} {gid}"
                         f"{rate_s}  {reason}")
            walk(e["genome_id"], depth + 1)

    walk(None, 0)
    lines.append("")
    lines.append("* champion   ~ neutral (inside the measured band)   "
                 "! quarantined   x extinct")
    return "\n".join(lines)
