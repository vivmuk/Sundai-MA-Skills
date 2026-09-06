# Design decisions

Recorded from the design interview that preceded any code. Each was an open
fork; each is closed. Reopening one is a normal thing to do — but it should
be done deliberately, which is why they are written down.

| # | Question | Decision |
|---|---|---|
| 1 | Demo or infrastructure? | **Honest infrastructure.** Real engine, real gates, small real numbers. |
| 2 | What executes a candidate? | **Adapter interface**, so the runtime is replaceable. Venice primary, Claude Code CLI second, mock for tests. |
| 3 | Who scores? | **AI first, human review available.** Deterministic gates block; judged findings quarantine. |
| 4 | Who authors environments? | **Claude drafts, human reviews the medical content.** Four to start, exercising every hard gate. |
| 5 | Promotion target | Fork `main` for now; upstream once it works. |
| 6 | Budget | No cap set, but **cost shown and confirmed before every execution**. |
| 7 | Who writes mutations? | **Fixed operator library for G1**; LLM mutator behind a flag from G2. |
| 8 | Hermes | **Harness-agnostic.** Adapter contract defined, Hermes left as a stub. |
| 9 | Where is human review optional? | **Both**: optional at scoring, mandatory at promotion. The merged PR is the approval. |
| 10 | Live evidence or replay? | **Record once per environment, replay for every candidate.** Live is a deliberate re-test mode. |
| 11 | Judge design | **Blinded pairwise against the champion**, judge from a different model family than the executor. |
| 12 | Repetitions and significance | **Measure the noise floor first** (G0 × 5); that spread becomes the neutral band. n=2 exploring, n=3 before promotion. |
| 13 | Inference provider | **Venice**, priced live from `GET /models`. Executor `z-ai-glm-5-3`, judge `gemini-3-8-flash`. |
| 14 | Candidate isolation | Overlays under `evolution/`, never a loadable skill path. Satisfied structurally — `validate_skills.py` only walks `skills/`, `house-rules/`, `workshop/data/`. |
| 15 | Human-edit capture | **Schema now, weight `null`** until real data exists. |
| 16 | Where do runs execute? | Network policy to be **widened** so a remote session can run experiments unattended. |
| 17 | Models | `z-ai-glm-5-3` executes, `gemini-3-8-flash` judges. Confirmed against a three-model bake-off before the first campaign. |

## Changed during the build

**Decision 10 (record once, replay) landed differently than specified.** The
spec assumed fixtures would be *recorded* from PubMed and ClinicalTrials.gov,
and that recording would need network egress. It would not have worked: these
experts are fictional, so a live search returns nothing to record. The corpora
are authored instead. The replay guarantee is unchanged and the practical
result is better — every environment runs offline, and an environment change
becomes an edit you can diff rather than an event you absorb.

**The first neutral-band implementation was wrong and the null control caught
it.** Measuring single comparisons gave a band of ±0.5, because one comparison
can only score 0, 0.5 or 1 — a band nothing could ever beat. Worse, once
fixed, rounding the band to four decimal places let a win rate of exactly 5/6
cross a threshold of 0.8333 and crowned `g1d`, the cosmetic null candidate, as
champion. Both are fixed: the probe now measures the same statistic the
tournament reports, by making the ancestor compete against itself. That
`g1d` exists is why either bug was visible at all.

## Changed when the engine went from one workflow to five

**Boundary requirements became per-workflow.** The three required statements —
approval status, off-label routing, AE reporting — were global. Applied to a
field-insight report or a congress readout they failed correct work for
omitting something it had no reason to contain, which would have taught the
engine to pad every deliverable with boilerplate. Each workflow now declares
what its deliverable owes, in `profile.yaml`. The forbidden-content checks and
the design-and-denominator rule stayed global, because those genuinely are.

**A gate false-positived on its own boundary text.** The AE-fabrication check
fired on "Any adverse event identified in this material must be reported" — a
standing obligation, not a claim that one was found. Left alone it would have
rewarded stripping a required statement to get past the safety gate. Fixed,
with a regression test.

**Promotion proposals collided.** Every workflow's first champion is called
`g1a`, so keying the output directory on the genome's short id put five
proposals in one directory and left only the last. Namespaced by workflow now,
with a test. Nothing surfaced this until there was a fifth workflow.

## Two things accepted as consequences, not problems

**"No significant improvement detected" is a legitimate outcome.** With the
neutral band measured from real baseline variance, it is entirely possible
that all four G1 variants land inside it. That is the engine working. A
system that always finds a winner is a system whose evaluator cannot
distinguish signal from noise, and the pressure to produce a champion must
never be allowed to reach the evaluator.

**Meta-evolution (§27) is a data format, not a feature.** Learning which
mutation classes pay off needs on the order of a thousand experiments; the
first campaigns will produce a handful. Every mutation's predicted and
observed effect is recorded from the first run so the data accumulates —
and the mutation weights are not adjusted until there is enough of it to
mean something.
