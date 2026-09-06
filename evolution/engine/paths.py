"""Repository paths and the engine's write boundary."""
from __future__ import annotations
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
EVOLUTION = REPO / "evolution"
CONSTITUTION = EVOLUTION / "constitution" / "immutable.yaml"
REGISTRY = EVOLUTION / "registry" / "workflows.yaml"
POLICIES = EVOLUTION / "policies"
ENVIRONMENTS = EVOLUTION / "environments"
LINEAGES = EVOLUTION / "lineages"
EXPERIMENTS = EVOLUTION / "experiments"
EVALUATORS = EVOLUTION / "evaluators"

# The only two trees the engine may write to. Enforced, not documented.
WRITABLE = (LINEAGES, EXPERIMENTS)


class WriteBoundaryError(PermissionError):
    """Raised when the engine is asked to write outside its allowed roots."""


def assert_writable(path: Path) -> Path:
    """Refuse any write outside evolution/lineages/ or evolution/experiments/.

    The constitution says the engine cannot edit skills, house rules, gates or
    itself. This is where that stops being a promise and starts being code.
    """
    resolved = Path(path).resolve()
    for root in WRITABLE:
        try:
            resolved.relative_to(root.resolve())
            return resolved
        except ValueError:
            continue
    raise WriteBoundaryError(
        f"refusing to write outside the engine's boundary: {resolved}\n"
        f"allowed roots: {', '.join(str(r) for r in WRITABLE)}"
    )
