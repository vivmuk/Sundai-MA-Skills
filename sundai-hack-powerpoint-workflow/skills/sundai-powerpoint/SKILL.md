---
name: sundai-powerpoint
description: >-
  Sundai PowerPoint skill — base PowerPoint skill for the Sundai Hack Medical
  Affairs workflow. Use whenever a .pptx or .potx is created, edited, read, or
  validated — especially PDF → medical-to-medical (M2M) decks. Combines Anthropic
  pptx mechanics (pptxgenjs, OOXML edit/validate) with Open Medical Affairs slide
  rules: non-promotional standards, citation on every data slide, fair balance,
  draft marking, and consulting-grade design. Load after analysis is done; do not
  start slides from a raw PDF until document-ingestion and evidence-appraisal
  have finished.
license: >-
  Scripts and base pptx mechanics: Anthropic skills (see LICENSE.txt).
  Medical Affairs rules layer: Apache-2.0 (Open-Medical-Affairs).
metadata:
  version: "1.0.0-sundai"
  tier: content
  maturity: hack
  role: base-skill
  requires:
    - medical-affairs-foundations
    - citation-integrity
    - capability-detection
  suggests:
    - evidence-appraisal
    - data-visualization-for-medical
    - consulting-grade-design
    - deliverable-quality-review
    - document-ingestion
    - medical-slide-deck
    - mlr-review-readiness
  produces: Non-promotional medical slide deck (.pptx)
---

# Sundai PowerPoint skill

Base slide skill for the Sundai Hack PowerPoint workflow.

Mechanics: [anthropics/skills pptx](https://github.com/anthropics/skills/tree/main/skills/pptx).
**Content and compliance:** Open Medical Affairs (`medical-slide-deck`, `consulting-grade-design`, `medical-affairs-foundations`).

When they conflict, **Medical Affairs rules win** for what appears on a slide;
Anthropic guidance wins for packing a valid `.pptx`.

## House rules (required)

Before finishing any deck, read the overrides in **`house-rules/` inside this skill**:

- `house-rules/medical-slide-deck.md`
- `house-rules/medical-affairs-foundations.md`
- and other matching files in `house-rules/`

**House-rules override defaults** in this SKILL.md and in sibling MA skills.

## Before you touch PowerPoint

**Do not start here.** Build the deck only after analysis is done.

Typical PDF → M2M path:

1. `medical-affairs-foundations` (always)
2. `document-ingestion` on the PDF
3. `evidence-appraisal` + `citation-integrity`
4. `capability-detection`
5. **This skill (`sundai-powerpoint`)** + `consulting-grade-design` / `data-visualization-for-medical`
6. `deliverable-quality-review` then `mlr-review-readiness`

Hard requires: `medical-affairs-foundations`, `citation-integrity`, `capability-detection`.
Suggested: `evidence-appraisal`, `data-visualization-for-medical`, `consulting-grade-design`, `deliverable-quality-review`.

Output is **draft material for qualified medical review**. Keep DRAFT on the title slide.

---

# Medical Affairs rules (govern content)

## Medical slide ≠ commercial slide

| | Commercial | Medical (required here) |
|---|---|---|
| Headline | The message | What the data show |
| Data | Selected to support | Design + limits visible |
| Comparison | Favourable framing | Only with head-to-head evidence |
| Safety | Elsewhere | Alongside efficacy, comparable prominence |
| Citation | Sometimes | **Every data slide** |
| Approval status | Assumed | Stated |

**Headline test.** Titles state findings, not conclusions.
Good: `ORR 63% in triple-class-exposed patients (single-arm, n=165)`.
Bad: `Substantial activity in heavily pretreated patients`.

## Non-negotiables on every data slide

1. Citation footnote (author, journal, year, identifier) — footer preferred
2. Design named with the number (single-arm / randomised / etc.)
3. N and population — no percentage without denominator
4. Confidence intervals on estimates
5. Evidence tier if not peer-reviewed — `[abstract]`, `[preprint]`, `[data on file]`
6. Never invent citations (`citation-integrity`)

## M2M / MSL scientific structure

```
Disease context
Unmet need            evidence-based
The evidence          design, population, results with CIs, limitations
Safety                same prominence (oxblood reserved for safety)
What remains unknown
References
Backup                anticipated questions
```

## Consulting-grade palette (use these hex values without `#` in pptxgenjs)

| Role | Hex | Use |
|---|---|---|
| Ink | `12283A` | Titles, primary series |
| Slate | `5B6B79` | Secondary text, axes |
| Teal | `0E7C7B` | Single accent / finding |
| Gold | `C89B3C` | Sparse callouts |
| Oxblood | `8C2F39` | Safety only |
| Cloud | `E8ECEF` | Gridlines, banding |
| White | `FFFFFF` | Content backgrounds |

One idea per slide. 0.5 inch margins. Left-align body. No decorative title underlines or sidebar stripes.

## Challenge before handoff

Run `deliverable-quality-review`, then `mlr-review-readiness`. Check citations, safety prominence, finding-titles, approval status, DRAFT marking.

---

# PPTX mechanics (Anthropic)

A `.pptx` is a ZIP of XML.

| Task | Approach |
|---|---|
| Create | `pptxgenjs` script |
| Edit / template | unzip → edit slide XML → zip |
| Read | `markitdown deck.pptx`; `python scripts/thumbnail.py deck.pptx` |

## Scripts (relative to this skill)

| Script | Purpose |
|---|---|
| `scripts/thumbnail.py` | Labeled slide grid |
| `scripts/add_slide.py` | Duplicate slide with bookkeeping |
| `scripts/clean.py` | Remove orphaned parts |
| `scripts/office/validate.py` | Schema / structural checks |
| `scripts/office/soffice.py` | LibreOffice convert |

## pptxgenjs gotchas

- Set `pres.layout` before slides. Default 16:9 = 10 x 5.625 inches.
- Hex: never `#`, never 8-digit. Example `color: "12283A"`.
- Do not reuse mutated option/shadow objects across `add*` calls.
- Shadow `offset` >= 0. Use `charSpacing` not `letterSpacing`.
- Bullets: `bullet: true`; `breakLine: true` except last item.
- One `new pptxgen()` per file.
- Prefer native `addChart()`; stacked bar labels: `ctr` / `inEnd` / `inBase` only.
- After write: `python scripts/office/validate.py deck.pptx`.
- Speaker notes: `slide.addNotes("...")`.

## QA

- Medical: citations, no promo headlines, safety, DRAFT, `markitdown`
- File: `python scripts/office/validate.py output.pptx`
- Visual: soffice to PDF, then `pdftoppm`

## Provenance

- Anthropic pptx base + LICENSE.txt
- Open-Medical-Affairs Medical-Affairs-Skills rules
- Bundle: `sundai-hack-powerpoint-workflow` in vivmuk/Sundai-MA-Skills
