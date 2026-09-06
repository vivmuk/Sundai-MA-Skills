# Environments — kol-engagement-brief

An environment is one repeatable Medical Affairs situation: the source
material an agent is given, plus a label file saying what a competent brief
must do with it. Without the labels there are no automatic gates, and
without automatic gates there is no automatic selection — so the labels are
the most valuable asset here, not the prose.

All material is synthetic. It extends the existing oncology-mm workshop
dataset rather than replacing it, so a candidate sees inputs of the same
shape it would see in `workshop/`.

## The four MVP environments

| id | Situation | Gate it exercises |
|---|---|---|
| `env-01-routine` | Established expert, recent interaction notes, nothing unusual. | Baseline. Specificity and delta detection with everything available. |
| `env-02-buried-ae` | An adverse event is described in passing in historical interaction notes. | `safety` — the failure mode with real-world consequence. |
| `env-03-offlabel-question` | The expert's recorded question concerns an unapproved use. | `medical-boundaries` — routing rather than answering. |
| `env-04-publication-delta` | A publication has appeared since last contact that shifts the expert's position. | `scientific-integrity` + delta detection. Rewards the mutation the PRD predicts will win (§14A). |

These four exercise every hard gate. The remaining six from §8 — no prior
history, ambiguous publication identity, competitor trials, hostile expert,
evidence gap, mid-run evidence update — are added once the engine has run a
full campaign on these.

## Layout

```
env-01-routine/
├── inputs/            # what the agent is given
├── expectations.yaml  # what a competent brief must do — the answer key
└── fixtures/          # recorded PubMed / CT.gov / openFDA responses
```

## expectations.yaml

```yaml
must_surface:     # deterministic scientific-integrity gate
must_not_say:     # deterministic scientific-integrity gate
must_escalate:    # deterministic safety gate; each with its source record id
must_route:       # deterministic boundaries gate (e.g. off-label handling)
known_gaps:       # what genuinely cannot be determined from the material
```

The judge never sees this file. The gates do. A judge holding the answer key
scores the answer key.

## Evidence: replay by default

Each environment records its external evidence **once** and replays it for
every candidate, hashed into the experiment manifest.

This is not a caching optimisation. If candidate A and candidate B query
PubMed live on different afternoons, they are scored against different
evidence, and no fitness difference between them can be attributed to the
mutation rather than to the retrieval. Replay is what makes a comparison
mean anything.

- `--replay` (default): offline, free, reproducible, no rate limits.
- `--live`: deliberate re-recording, used for the §32 "the environment
  changed" re-test — which is a designed experiment, not an accident.

Recording requires network access to `eutils.ncbi.nlm.nih.gov`,
`clinicaltrials.gov` and `api.fda.gov`. Once recorded and committed,
every subsequent run needs only the inference endpoint.
