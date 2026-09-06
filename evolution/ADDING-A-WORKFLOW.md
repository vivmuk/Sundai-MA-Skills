# Adding a workflow

The engine is workflow-agnostic: gates, tournament, band, lineage and
promotion are shared. Wiring a new workflow is data, not code.

Five things, in this order. The last one is the only one that needs judgement.

## 1. Profile — `evaluators/workflows/<workflow>/profile.yaml`

```yaml
workflow: <workflow>
artifact:
  title: <what the deliverable is called>
  quotes_efficacy: true|false     # does it quote numbers that need a design?
  sections: [...]                 # the deliverable's real structure
required_boundaries: [approval_status, offlabel_routing, ae_reporting]
```

Declare only the boundaries this deliverable actually owes. An internal
readout owes none of them; a medical information response owes all three.
Over-declaring is not the safe choice — a gate that fires on correct work
teaches the engine to pad, and padding is how a deliverable stops being read.

## 2. Evaluators — `pairwise.yaml` and `rubric.yaml`

`pairwise.yaml` selects; write the question a real reader would answer, and
anchors describing better and worse in that workflow's own terms.
`rubric.yaml` only explains, and never selects. Any dimension without data
carries `weight: null` — never a default number.

## 3. Environments — `environments/<workflow>/<env-id>/`

```
environment.yaml    id, target, situation, shared_inputs (paths into workshop/data/)
expectations.yaml   the answer key
fixtures/evidence.json   authored corpus, or empty with a note saying why
inputs/             optional workflow-specific material
```

Two minimum. Between them they should be able to trip every gate the workflow
declares — a gate no environment can trip is a gate nobody has tested.

## 4. Genomes and overlays — `lineages/<workflow>/`

An ancestor `g0` with no overlays, and candidates each carrying one overlay.
Overlays are anchored text edits against the real `SKILL.md`; a missing or
ambiguous anchor raises rather than silently doing nothing.

**Include a null control.** One candidate whose overlay is cosmetic, with
"null candidate" in its rationale — the test suite requires it. It is what
tells you the difference between a discovery and the evaluator's own noise,
and it has already caught two real bugs in this engine.

## 5. Registry — `registry/workflows.yaml`

Flip `status: planned` to `active` and add the Level 1 purpose statement and
the invariants. The purpose is what the workflow is *for*: evolution may
change how it is achieved and never what it is. Invariants are the properties
every descendant keeps regardless of fitness.

## Then

```bash
python3 scripts/selftest_evolution.py                      # structural checks, all workflows
python3 scripts/evolve.py probe <workflow> --adapter mock --yes
python3 scripts/evolve.py run   <workflow> --adapter mock --yes
```

The suite checks every active workflow, so a workflow wired up incorrectly
fails there rather than during a campaign that has already spent money.
