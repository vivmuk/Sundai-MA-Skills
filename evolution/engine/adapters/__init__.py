from .base import Adapter, Budget, CostEstimate, Judge
from .mock import MockAdapter, MockJudge

_REGISTRY = {"mock": MockAdapter}
try:  # optional: only importable where urllib egress exists
    from .venice import VeniceAdapter, VeniceJudge  # noqa: F401
    _REGISTRY["venice"] = VeniceAdapter
except Exception:  # pragma: no cover
    pass


def get(name: str):
    if name not in _REGISTRY:
        raise KeyError(f"unknown adapter {name!r}; available: {sorted(_REGISTRY)}")
    return _REGISTRY[name]


__all__ = ["Adapter", "Budget", "CostEstimate", "Judge",
           "MockAdapter", "MockJudge", "get"]
