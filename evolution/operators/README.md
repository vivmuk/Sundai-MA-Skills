# Mutation operators

Generation 1 uses hand-authored variants. This is deliberate: if a model
writes the candidate *and* a model scores it, a bad result is
unattributable — you cannot tell whether the mutation was poor, the
evaluation was poor, or both. The fixed library establishes that the
evaluation works before the mutator is allowed to write anything.

Every operator produces an **overlay patch** against the ancestor, never a
rewritten skill file. The overlay is the unit of inheritance: a child
inherits its parent's overlays and adds one.

## The library (§14)

| Operator | Changes | Constraint |
|---|---|---|
| `skill_instruction` | Wording and instruction of a workflow stage | Level 1 purpose and registry invariants untouched |
| `retrieval_order` | The sequence of Stage 2 retrieval | Same sources, different order |
| `tool_selection` | Which evidence tools are consulted | Only tools declared in the skill's `network` frontmatter |
| `context_allocation` | How much context each input class receives | Total budget unchanged |
| `model_routing` | Which model handles which stage | Models available on the configured adapter |
| `output_structure` | Stage 5 section order and shape | Required sections retained |
| `examples` | Adds or replaces a worked example | Synthetic only |
| `qa_loop` | The Stage 4 challenge process | May add passes, never remove the challenge |
| `recombination` | Merges overlays from two parents | From G3; child re-runs the full suite |

## Generation 1 for kol-engagement-brief

Four candidates, chosen because each tests a different hypothesis about
where the value in this workflow actually sits:

- **G1a — `skill_instruction`.** Classify recent publications into
  continuity, shift, or new direction *before* generating questions.
  Hypothesis: question specificity comes from trajectory analysis, not from
  publication volume.
- **G1b — `retrieval_order`.** Analyse prior-interaction deltas before
  retrieving publications, and let the unresolved questions drive the
  search. Hypothesis: the delta is the brief's most-used section, so it
  should shape retrieval rather than be assembled after it.
- **G1c — `qa_loop`.** Replace draft→review with claim extraction →
  citation validation → specificity check → red-team → revision.
  Hypothesis: most of the quality gap is caught, not written.
- **G1d — neutral control.** A cosmetic reordering with no substantive
  change. Hypothesis: none. Its purpose is to show what the measurement
  system reports when nothing has actually changed — if G1d "wins", the
  evaluator is broken and every other result this generation is void.

G1d is not padding. An evolutionary system without a null candidate cannot
distinguish a discovery from its own noise.
