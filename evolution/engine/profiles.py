"""Per-workflow output profiles.

The hard gates are global in intent but not in detail. Every Medical Affairs
deliverable must avoid promotional framing and commercial segmentation — that
is genuinely universal. But requiring an approval-status statement in an
internal field-insight report, or an AE-reporting reminder in a congress
readout, would fail good work for missing something it had no reason to
contain, and a gate that fires on correct output teaches the engine to pad.

So each workflow declares which boundary statements its deliverable owes, and
what its output is shaped like. Everything else stays global.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

import yaml

from .paths import EVALUATORS

ALL_BOUNDARIES = ("approval_status", "offlabel_routing", "ae_reporting")


@dataclass
class Profile:
    workflow: str
    title: str = ""
    sections: list[str] = field(default_factory=list)
    required_boundaries: tuple[str, ...] = ALL_BOUNDARIES
    quotes_efficacy: bool = True

    @property
    def safety_section(self) -> str:
        return "SAFETY AND SPECIAL SITUATIONS"


@lru_cache(maxsize=None)
def load(workflow: str) -> Profile:
    path = EVALUATORS / "workflows" / workflow / "profile.yaml"
    if not path.exists():
        # No profile means no exemptions: every boundary applies.
        return Profile(workflow=workflow)
    spec = yaml.safe_load(path.read_text()) or {}
    artifact = spec.get("artifact", {}) or {}
    declared = spec.get("required_boundaries", list(ALL_BOUNDARIES)) or []
    unknown = [b for b in declared if b not in ALL_BOUNDARIES]
    if unknown:
        raise ValueError(f"{path}: unknown boundary requirement(s) {unknown}")
    return Profile(
        workflow=spec.get("workflow", workflow),
        title=artifact.get("title", workflow),
        sections=list(artifact.get("sections", [])),
        required_boundaries=tuple(declared),
        quotes_efficacy=bool(artifact.get("quotes_efficacy", True)),
    )
