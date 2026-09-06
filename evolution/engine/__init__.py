"""MA Evolution Engine.

Runtime-agnostic evolution of Medical Affairs workflow skills. The engine
never writes outside evolution/lineages/ and evolution/experiments/, and
never touches a canonical skill: promotion is a pull request a human merges.
"""
__all__ = ["genome", "environment", "phenotype", "evidence", "gates",
           "tournament", "lineage", "cost", "adapters"]
