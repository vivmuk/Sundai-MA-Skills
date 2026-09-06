"""Environments: the source material, the answer key, and the evidence corpus.

Every environment in this repository is synthetic. The experts, the product
and the trials are fictional, so the evidence corpus is **authored**, not
recorded from a live service — a real PubMed search for Dr Adaeze Okafor
returns nothing, and a fixture recorded from one would be empty. That is why
these environments run entirely offline.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .paths import REPO, ENVIRONMENTS


def sha256_of(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sha256_of_tree(root: Path) -> str:
    """Order-independent digest of a directory, for the manifest."""
    h = hashlib.sha256()
    for p in sorted(Path(root).rglob("*")):
        if p.is_file():
            h.update(str(p.relative_to(root)).encode())
            h.update(p.read_bytes())
    return h.hexdigest()


@dataclass
class Expectations:
    """The answer key. Read by the deterministic gates, never shown to a judge."""
    environment_id: str
    must_surface: list[dict] = field(default_factory=list)
    must_not_say: list[dict] = field(default_factory=list)
    must_escalate: list[dict] = field(default_factory=list)
    must_route: list[dict] = field(default_factory=list)
    known_gaps: list[str] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path) -> "Expectations":
        spec = yaml.safe_load(Path(path).read_text())
        cls._validate(path, spec)
        return cls(
            environment_id=spec["environment_id"],
            must_surface=spec.get("must_surface", []) or [],
            must_not_say=spec.get("must_not_say", []) or [],
            must_escalate=spec.get("must_escalate", []) or [],
            must_route=spec.get("must_route", []) or [],
            known_gaps=spec.get("known_gaps", []) or [],
        )

    @staticmethod
    def _validate(path: Path, spec: dict) -> None:
        """Fail loudly, here, naming the file.

        An unquoted "Label: value" in a YAML list silently becomes a mapping,
        and the answer key is the one artifact where a silent malformation is
        expensive: the gates would score against something nobody wrote.
        """
        for gap in spec.get("known_gaps") or []:
            if not isinstance(gap, str):
                raise ValueError(
                    f"{path}: known_gaps entries must be strings, got "
                    f"{type(gap).__name__} ({gap!r}). A colon followed by a "
                    f"space makes YAML read the line as a mapping — quote it.")
        for group in ("must_surface", "must_not_say", "must_escalate", "must_route"):
            for item in spec.get(group) or []:
                if not isinstance(item, dict) or "id" not in item:
                    raise ValueError(f"{path}: every {group} entry needs an 'id'; "
                                     f"got {item!r}")
                for key, value in item.items():
                    if key == "match" and not isinstance(value, list):
                        raise ValueError(
                            f"{path}: {group}/{item['id']} 'match' must be a list")


@dataclass
class Environment:
    environment_id: str
    workflow: str
    situation: str
    target_expert: str
    root: Path
    input_paths: list[Path]
    expectations: Expectations
    evidence: dict

    @classmethod
    def load(cls, workflow: str, environment_id: str) -> "Environment":
        root = ENVIRONMENTS / workflow / environment_id
        spec = yaml.safe_load((root / "environment.yaml").read_text())
        inputs = [REPO / p for p in spec.get("shared_inputs", [])]
        inputs += sorted((root / "inputs").glob("*.md")) if (root / "inputs").exists() else []
        missing = [str(p) for p in inputs if not p.exists()]
        if missing:
            raise FileNotFoundError(f"{environment_id}: missing inputs {missing}")
        evidence_path = root / "fixtures" / "evidence.json"
        evidence = json.loads(evidence_path.read_text()) if evidence_path.exists() else {}
        return cls(
            environment_id=spec["environment_id"],
            workflow=spec.get("workflow", workflow),
            situation=spec.get("situation", ""),
            target_expert=spec.get("target_expert", ""),
            root=root,
            input_paths=inputs,
            expectations=Expectations.load(root / "expectations.yaml"),
            evidence=evidence,
        )

    def source_text(self) -> str:
        """Everything the agent is given, concatenated with provenance headers."""
        parts = []
        for p in self.input_paths:
            rel = p.relative_to(REPO)
            parts.append(f"<!-- source: {rel} -->\n{p.read_text()}")
        return "\n\n".join(parts)

    def digests(self) -> dict:
        return {
            "inputs_sha256": hashlib.sha256(self.source_text().encode()).hexdigest(),
            "expectations_sha256": sha256_of(self.root / "expectations.yaml"),
            "fixtures_sha256": (sha256_of_tree(self.root / "fixtures")
                                if (self.root / "fixtures").exists() else ""),
        }


def load_all(workflow: str) -> list[Environment]:
    root = ENVIRONMENTS / workflow
    ids = sorted(p.name for p in root.iterdir()
                 if p.is_dir() and (p / "environment.yaml").exists())
    return [Environment.load(workflow, i) for i in ids]
