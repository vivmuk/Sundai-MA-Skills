"""Fixture-backed evidence tools.

These are the function-calling tools a candidate sees. In replay mode they
serve the environment's authored corpus; nothing reaches the network.

Replay is not a caching optimisation. If two candidates query a live service
on different afternoons they are scored against different evidence, and no
difference between them can be attributed to the mutation rather than to the
retrieval.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field


class LiveRetrievalBlocked(RuntimeError):
    """Raised when live mode is requested but not available."""


TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "pubmed_search",
            "description": "Search the literature. Returns records with PMIDs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "author, topic or field-tagged query"},
                    "limit": {"type": "integer", "default": 10},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "trials_search",
            "description": "Search the trial registry by investigator, sponsor or condition.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer", "default": 10},
                },
                "required": ["query"],
            },
        },
    },
]


@dataclass
class EvidenceStore:
    """The authored corpus for one environment."""
    corpus: dict
    mode: str = "replay"
    calls: list[dict] = field(default_factory=list)

    @property
    def publications(self) -> list[dict]:
        return self.corpus.get("publications", [])

    @property
    def trials(self) -> list[dict]:
        return self.corpus.get("trials", [])

    def known_ids(self) -> set[str]:
        """Every identifier a candidate is permitted to cite."""
        ids = {str(p["pmid"]) for p in self.publications if p.get("pmid")}
        ids |= {str(t["nct_id"]) for t in self.trials if t.get("nct_id")}
        ids |= {str(p["doi"]) for p in self.publications if p.get("doi")}
        return ids

    def _match(self, records: list[dict], query: str, limit: int) -> list[dict]:
        terms = [t for t in query.lower().replace('"', " ").split() if len(t) > 2]
        scored = []
        for r in records:
            blob = json.dumps(r).lower()
            score = sum(1 for t in terms if t in blob)
            if score:
                scored.append((score, r))
        scored.sort(key=lambda x: (-x[0], json.dumps(x[1])))
        return [r for _, r in scored[:limit]]

    def call(self, name: str, arguments: dict) -> dict:
        if self.mode != "replay":
            raise LiveRetrievalBlocked(
                "live retrieval is not available for a synthetic environment: "
                "these experts and trials are fictional, so there is nothing "
                "upstream to retrieve. Author the corpus instead."
            )
        query = arguments.get("query", "")
        limit = int(arguments.get("limit", 10))
        if name == "pubmed_search":
            results = self._match(self.publications, query, limit)
        elif name == "trials_search":
            results = self._match(self.trials, query, limit)
        else:
            raise ValueError(f"unknown evidence tool: {name}")
        payload = {"query": query, "count": len(results), "results": results}
        self.calls.append({
            "tool": name,
            "arguments": arguments,
            "result_sha256": hashlib.sha256(
                json.dumps(payload, sort_keys=True).encode()).hexdigest(),
            "source": "fixture",
        })
        return payload
