"""Genomes and overlays.

A genome is a base skill commit plus ordered overlay patches. It is never a
copy of a skill, and it is never written anywhere a skill loader can find it.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .paths import REPO, LINEAGES


class OverlayError(ValueError):
    """An overlay that cannot be applied exactly as written."""


@dataclass(frozen=True)
class Overlay:
    operator: str
    patch_path: str
    rationale: str
    author: str = "human"
    edits: list[dict] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path, meta: dict) -> "Overlay":
        spec = yaml.safe_load(path.read_text())
        return cls(
            operator=spec.get("operator", meta.get("operator", "")),
            patch_path=str(path.relative_to(REPO)),
            rationale=spec.get("rationale", meta.get("rationale", "")),
            author=spec.get("author", meta.get("author", "human")),
            edits=spec.get("edits", []),
        )

    def apply(self, text: str) -> str:
        """Apply every edit, or raise.

        A missing anchor is an error, never a silent no-op. An overlay that
        quietly did nothing would be scored as a neutral variant, and the
        lineage would record a mutation that never happened.
        """
        for i, edit in enumerate(self.edits):
            op = edit.get("op")
            anchor = edit.get("anchor", "")
            if op in {"replace", "insert_after", "insert_before"}:
                if anchor not in text:
                    raise OverlayError(
                        f"{self.patch_path} edit {i}: anchor not found in the "
                        f"base skill: {anchor[:70]!r}"
                    )
                if text.count(anchor) > 1:
                    raise OverlayError(
                        f"{self.patch_path} edit {i}: anchor is ambiguous "
                        f"({text.count(anchor)} matches): {anchor[:70]!r}"
                    )
            if op == "replace":
                text = text.replace(anchor, edit["with"])
            elif op == "insert_after":
                text = text.replace(anchor, anchor + edit["text"])
            elif op == "insert_before":
                text = text.replace(anchor, edit["text"] + anchor)
            elif op == "append":
                text = text.rstrip("\n") + "\n" + edit["text"]
            else:
                raise OverlayError(f"{self.patch_path} edit {i}: unknown op {op!r}")
        return text


@dataclass
class Genome:
    genome_id: str
    workflow: str
    generation: int
    parent: str | None
    base_skill_path: str
    base_skill_commit: str
    overlays: list[Overlay]
    runtime: dict
    status: str = "candidate"

    @classmethod
    def load(cls, path: Path) -> "Genome":
        spec = yaml.safe_load(Path(path).read_text())
        overlays = []
        for meta in spec.get("overlays", []) or []:
            overlays.append(Overlay.load(REPO / meta["patch_path"], meta))
        return cls(
            genome_id=spec["genome_id"],
            workflow=spec["workflow"],
            generation=spec.get("generation", 0),
            parent=spec.get("parent"),
            base_skill_path=spec["base"]["skill_path"],
            base_skill_commit=spec["base"].get("skill_commit", "working-tree"),
            overlays=overlays,
            runtime=spec.get("runtime", {}),
            status=spec.get("status", "candidate"),
        )

    @property
    def short_id(self) -> str:
        return self.genome_id.split("/")[-1]

    def express(self) -> str:
        """The skill text this genome actually presents to a runtime."""
        text = (REPO / self.base_skill_path).read_text()
        for overlay in self.overlays:
            text = overlay.apply(text)
        return text

    def digest(self) -> str:
        return hashlib.sha256(self.express().encode()).hexdigest()

    def mutation_summary(self) -> str:
        if not self.overlays:
            return "ancestor (no overlays)"
        return "; ".join(f"{o.operator}: {o.rationale}" for o in self.overlays)


def load_all(workflow: str) -> dict[str, Genome]:
    """Every genome defined for a workflow, keyed by genome_id."""
    root = LINEAGES / workflow / "genomes"
    out: dict[str, Genome] = {}
    if not root.exists():
        return out
    for path in sorted(root.glob("*.yaml")):
        g = Genome.load(path)
        out[g.genome_id] = g
    return out
