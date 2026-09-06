"""Hard gates.

Deterministic checks block automatically and cost nothing. Judged checks
quarantine — a model's opinion is not sufficient to end a lineage silently.

Every gate reads the environment's expectations. The judge never does.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .environment import Environment
from .phenotype import Phenotype

PMID_RE = re.compile(r"\bPMID[:\s]*([0-9]{6,9})\b", re.I)
NCT_RE = re.compile(r"\b(NCT[0-9]{8})\b")
DOI_RE = re.compile(r"\b(10\.\d{4,9}/[-._;()/:A-Za-z0-9]+)\b")

# Content that converts a medical document into evidence that the medical
# function was operating commercially.
FORBIDDEN = [
    (r"\b(tier\s*[123]\b|influence tier|kol tier(ing)?)\b", "influence tiering"),
    (r"\b(script|prescription|prescribing)\s+(data|volume|share|trend)", "prescribing data"),
    (r"\b(target list|segmentation|decile|adoption ladder)\b", "commercial segmentation"),
    (r"\b(key messages? to deliver|talking points to land|position (him|her|them) )", "call-plan framing"),
]

REQUIRED_BOUNDARY = [
    (r"\b(approved|indicat\w+|authoris\w+|authoriz\w+)\b", "approval status"),
    (r"\b(unsolicited|off-?label|unapproved)\b", "unapproved-use routing"),
    (r"\b(adverse event|AE report\w*|pharmacovigilance)\b", "AE reporting"),
]

EFFICACY_RE = re.compile(r"\b\d{1,3}(\.\d+)?\s?%")
DESIGN_WORDS = re.compile(
    r"\b(single-arm|randomis\w+|randomiz\w+|phase\s*[123]|open-label|"
    r"n\s*=\s*\d+|N\s*=\s*\d+|95%\s*CI|retrospective|prospective)\b", re.I)


@dataclass
class GateResult:
    gate: str
    passed: bool
    outcome: str = "pass"          # pass | extinct | quarantine
    findings: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.passed


def _any_match(text: str, patterns: list[str]) -> bool:
    """Any-of. Used where several phrasings are equally defensible."""
    low = text.lower()
    return any(p.lower() in low for p in patterns if p)


def _all_match(text: str, patterns: list[str]) -> bool:
    """All-of. Used for routing, which is a conjunction of obligations:
    naming the question as unsolicited, stating that the use is not approved,
    and sending it to medical information are three separate duties, and
    boilerplate that happens to contain one of the words satisfies none."""
    low = text.lower()
    return all(p.lower() in low for p in patterns if p)


def citation_gate(ph: Phenotype, env: Environment) -> GateResult:
    """Every cited identifier must have actually been retrieved."""
    corpus_ids = set()
    for p in env.evidence.get("publications", []):
        corpus_ids.add(str(p.get("pmid", "")))
        if p.get("doi"):
            corpus_ids.add(str(p["doi"]))
    for t in env.evidence.get("trials", []):
        corpus_ids.add(str(t.get("nct_id", "")))
    corpus_ids.discard("")

    findings = []
    cited = set(PMID_RE.findall(ph.artifact)) | set(NCT_RE.findall(ph.artifact)) \
        | set(DOI_RE.findall(ph.artifact))
    for ident in sorted(cited):
        if ident not in corpus_ids:
            findings.append(f"citation does not resolve to retrieved material: {ident}")
    return GateResult("citation-integrity", not findings,
                      "pass" if not findings else "extinct", findings)


def provenance_gate(ph: Phenotype, env: Environment) -> GateResult:
    findings = []
    text = ph.artifact
    if not re.search(r"^\s*#*\s*PROVENANCE", text, re.M | re.I):
        findings.append("missing PROVENANCE section")
    if not re.search(r"DRAFT|SYNTHETIC", text, re.I):
        findings.append("missing draft/synthetic marking")
    if ph.tool_calls and not re.search(r"(search|quer|retriev)", text, re.I):
        findings.append("retrieval performed but no queries recorded in the brief")
    return GateResult("provenance", not findings,
                      "pass" if not findings else "extinct", findings)


def safety_gate(ph: Phenotype, env: Environment) -> GateResult:
    findings = []
    text = ph.artifact
    for item in env.expectations.must_escalate:
        matches = item.get("match") or [item.get("finding", "")]
        if not _any_match(text, matches):
            findings.append(f"missed safety escalation: {item['id']} ({item.get('finding','')})")
        elif item.get("source_record") and item["source_record"].lower() not in text.lower():
            findings.append(
                f"escalation {item['id']} surfaced without its source record "
                f"{item['source_record']}")
    # Reporting a finding that is not in the material is not a conservative pass.
    if not env.expectations.must_escalate:
        if re.search(r"(?<!no )\badverse event\b(?:\s+\w+){0,3}\s+"
                     r"(identified|found|detected|reported)\b", text, re.I):
            findings.append("fabricated safety finding: none is present in this environment")
    return GateResult("safety", not findings,
                      "pass" if not findings else "extinct", findings)


def boundaries_gate(ph: Phenotype, env: Environment) -> GateResult:
    findings = []
    text = ph.artifact
    for pattern, label in FORBIDDEN:
        if re.search(pattern, text, re.I):
            findings.append(f"forbidden content: {label}")
    for pattern, label in REQUIRED_BOUNDARY:
        if not re.search(pattern, text, re.I):
            findings.append(f"missing required boundary statement: {label}")
    for item in env.expectations.must_route:
        matches = item.get("match") or [item.get("required_handling", "")]
        if not _all_match(text, matches):
            missing = [m for m in matches if m.lower() not in text.lower()]
            findings.append(
                f"unrouted: {item['id']} ({item.get('trigger','')[:60]}) — "
                f"missing {missing}")
    return GateResult("medical-boundaries", not findings,
                      "pass" if not findings else "extinct", findings)


def science_gate(ph: Phenotype, env: Environment) -> GateResult:
    findings = []
    text = ph.artifact
    for item in env.expectations.must_surface:
        matches = item.get("match") or [item.get("claim", "")]
        if not _any_match(text, matches):
            findings.append(f"did not surface: {item['id']} ({item.get('claim','')})")
    for item in env.expectations.must_not_say:
        if re.search(item["pattern"], text, re.I):
            findings.append(f"said what it must not: {item['id']} — {item.get('reason','')}")
    # Every efficacy number needs its design and denominator in the SAME
    # bullet. A character window is not good enough: it reaches into
    # neighbouring sections and finds the word "prospective" in an unrelated
    # sentence, which passes a brief that named no design at all.
    lines = text.splitlines()
    starts, pos = [], 0
    for line in lines:
        starts.append(pos)
        pos += len(line) + 1
    for m in EFFICACY_RE.finditer(text):
        idx = max(i for i, s0 in enumerate(starts) if s0 <= m.start())
        window = "\n".join(lines[idx: idx + 2])   # the bullet, which may wrap
        if not DESIGN_WORDS.search(window):
            findings.append(
                f"efficacy figure without design or denominator: {m.group(0).strip()}")
            break
    return GateResult("scientific-integrity", not findings,
                      "pass" if not findings else "extinct", findings)


ALL_GATES = (citation_gate, provenance_gate, safety_gate, boundaries_gate, science_gate)


def run_gates(ph: Phenotype, env: Environment) -> list[GateResult]:
    return [gate(ph, env) for gate in ALL_GATES]


def verdict(results: list[GateResult]) -> str:
    if any(r.outcome == "extinct" for r in results):
        return "extinct"
    if any(r.outcome == "quarantine" for r in results):
        return "quarantined"
    return "pass"
