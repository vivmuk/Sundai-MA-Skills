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

## Evidence: an authored corpus, replayed

Each environment carries its evidence in `fixtures/evidence.json`, hashed into
the experiment manifest and replayed identically for every candidate.

The corpus is **authored, not recorded**. Every expert, trial and journal here
is fictional, so there is nothing upstream to record: a live PubMed search for
Dr Adaeze Okafor returns nothing, and a fixture captured from one would be an
empty file. Live mode therefore raises rather than silently returning nothing.
The practical consequence is good — these environments run entirely offline,
with no API key, no rate limit and no network.

This is not a caching optimisation. If candidate A and candidate B query
PubMed live on different afternoons, they are scored against different
evidence, and no fitness difference between them can be attributed to the
mutation rather than to the retrieval. Replay is what makes a comparison
mean anything.

An "environment change" (§32) is therefore made by **editing the corpus** —
which is exactly what `env-04` is: `env-01` plus one new publication that
shifts the expert's position. That makes environmental change a variable you
control and can diff, rather than something that happens to you between runs.

Real evidence enters only when a workflow is evolved against real experts.
That is a different kind of environment, it needs egress to
`eutils.ncbi.nlm.nih.gov` and `clinicaltrials.gov`, and it carries data-
protection consequences the synthetic set does not.
