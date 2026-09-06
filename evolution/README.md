# MA Evolution Engine

A controlled evolutionary layer above the skill library. It takes a
Medical Affairs workflow, runs it against repeatable environments, generates
constrained variants, evaluates them, and proposes the best descendant as a
normal pull request.

The principle it is built around:

> **Keep Medical Affairs purpose and safety boundaries stable. Allow the
> strategies used to achieve that purpose to evolve.**

**Status: specification.** This directory contains the design, the schemas
and the gate definitions. No runner code, and nothing here has executed or
spent anything. Read `DECISIONS.md` for the reasoning behind each choice.

---

## The layers

| Level | What | Who may change it |
|---|---|---|
| 0 | Constitution — scientific accuracy, citation integrity, safety escalation, non-promotional exchange | Humans only. Engine has read-only access, enforced in code. |
| 1 | Workflow purpose — what this workflow is *for* | Humans, via PR against `registry/workflows.yaml` |
| 2 | Goals — how the purpose decomposes | Engine |
| 3 | Methods — instructions, retrieval order, tools, structure, QA, routing | Engine. Most evolution happens here. |

## The loop

```
ancestor ──▶ run against N environments ──▶ phenotype
                                              │
                    ┌─────────────────────────┘
                    ▼
          deterministic gates ──fail──▶ EXTINCT (recorded, never deleted)
                    │ pass
                    ▼
          blinded pairwise vs champion
                    │
        ┌───────────┼───────────┐
        ▼           ▼           ▼
     better      neutral      worse
   (outside     (inside      (outside
     band)       band)        band)
        │           │           │
    reproduce   preserve     extinct
        │
        ▼
  human PR ──merge──▶ canonical skill
```

## Four decisions that carry the design

**Overlays, not copies.** A genome is a base skill commit plus ordered
overlay patches. Candidates never exist as loadable skill directories, are
never listed in `catalog.json` or `SKILLS-INDEX.md`, and live only under
`evolution/`. `validate_skills.py` walks `skills/`, `house-rules/` and
`workshop/data/` — so an unreviewed mutated Medical Affairs skill cannot
become installable by accident. That is a structural property, not a
convention.

**Record evidence once, replay it for every candidate.** If two candidates
query PubMed live on different afternoons they are scored against different
evidence, and no difference between them can be attributed to the mutation.
Replay is what makes the comparison mean anything; it also makes runs free,
offline and rate-limit-free. `--live` exists for the deliberate
"the environment changed" re-test.

**Pairwise, blinded, against the reigning champion.** Absolute 0–100 scores
from a model are noisiest exactly at the margins that decide a tournament.
The judge sees two briefs with identity and metadata stripped, in random
order, and may return a tie. Rubric scores are still produced — to explain
*why* something won, never to decide *that* it won. The judge comes from a
different model family than the executor, because a model scoring its own
output inflates its scores.

**The neutral band is measured, not chosen.** Sampling controls are
unavailable on these models, so runs are irreducibly nondeterministic.
Before any experiment, the ancestor runs five times on one environment; the
observed spread becomes the band. Inside it, a candidate is neutral —
preserved for structural novelty, not promoted (§16). Until the band is
measured the engine refuses to declare a champion, because an unmeasured
band makes every result unattributable.

## Layout

```
evolution/
├── constitution/immutable.yaml        Level 0. Read-only to the engine, CODEOWNERS-protected.
├── registry/workflows.yaml            What may evolve, and the Level 1 purpose it must preserve.
├── policies/                          Population, selection, resources, cost preflight, mutation weights.
├── adapters/CONTRACT.md               The runtime interface. Venice, Claude CLI, mock, Hermes stub.
├── operators/README.md                The mutation library and the G1 candidate set.
├── evaluators/
│   ├── global/                        Five hard gates. Deterministic where it counts.
│   └── workflows/kol-engagement-brief/ pairwise.yaml selects; rubric.yaml explains.
├── environments/kol-engagement-brief/  Inputs + expectations + recorded fixtures.
├── lineages/                          Append-only record. Champions, neutral, extinct.
├── experiments/                       One reproducibility manifest per campaign.
└── schemas/                           Genome, phenotype, expectations, manifest, lineage record.
```

## Gates

| Gate | Kind | Failure |
|---|---|---|
| `citation-integrity` | deterministic | extinct |
| `provenance` | deterministic | extinct |
| `safety` | deterministic, against labelled expectations | extinct |
| `scientific-integrity` | labelled checks deterministic; rest judged | extinct / quarantine |
| `medical-boundaries` | pattern checks deterministic; rest judged | extinct / quarantine |

Deterministic gates cost nothing and are not negotiable. A judged finding
**quarantines** — the candidate stops reproducing and is flagged for a human
— rather than silently ending a lineage on a model's opinion.

## Cost

Prices are fetched live from `GET /models` at run time. A hardcoded price
table goes stale silently, which is the one failure mode a cost preflight
must not have. Every run prints its estimate and **blocks for confirmation**;
actuals are written beside the estimate in the manifest so the estimator
corrects itself against reality.

Observed 2026-09-06, for sanity-checking only: `z-ai-glm-5-3` $1.75/$5.50
per MTok (1M context, function calling, reasoning, Private);
`gemini-3-8-flash` $0.94/$4.69 (1M context, function calling, reasoning,
Anonymized).

| Campaign | Runs | Estimate |
|---|---|---|
| Smoke test (wiring) | 4 | ~$3 |
| Noise-floor probe (G0 × 5) | 5 | ~$4 |
| First campaign: G0 + G1(4) + G2(3), 4 environments, n=2 | 64 | **~$45** (range $30–$80) |
| Full PRD shape: 6 × 10 × 3 × 5 generations | 908 | ~$635 (range $400–$1,100) |

`gemini-3-8-flash` is *Anonymized*, not *Private*. Fine for the synthetic
data in this repository; not automatically fine for a company Twin holding
real interaction notes. Every manifest records the privacy tier of every
model used, so that question can be answered later rather than assumed.

## What is deliberately not here

- No automatic promotion. A champion opens a **draft PR**; a human merging
  it is the approval, and it is the only approval.
- No self-evolving evaluators. The organism must never pass a test by
  rewriting the test.
- No meta-evolution yet — the data format exists, the learning does not
  (see `DECISIONS.md`).
- No Twin state (§38). The public repository holds schemas, synthetic
  examples and public evidence. Company data stays outside it.

## Build order

1. Schemas, lineage store, gates, cost estimator, **mock adapter** — the
   whole engine testable in CI for $0.
2. Four environments with labelled expectations; fixtures recorded once.
3. Venice adapter; three-model bake-off; noise-floor probe.
4. First campaign.
5. Promotion path: branch, evidence pack, draft PR.

Steps 1–2 need no network beyond GitHub. Step 2's recording and everything
after needs egress to `api.venice.ai`, `eutils.ncbi.nlm.nih.gov`,
`clinicaltrials.gov` and `api.fda.gov`.
