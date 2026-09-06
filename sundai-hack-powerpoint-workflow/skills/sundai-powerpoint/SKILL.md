---
name: sundai-powerpoint
description: >-
  Sundai PowerPoint skill — the single Sundai Hack skill for turning one PDF
  (or study package) into a non-promotional medical-to-medical (M2M) PowerPoint
  deck. Encompasses foundations, document ingestion, evidence appraisal,
  citation integrity, capability detection, consulting-grade design, medical
  slide rules, pptxgenjs/OOXML mechanics, quality review, and MLR readiness.
  Use for any hackathon ask like "make an M2M deck from this PDF", "build
  slides from this paper", or anytime a .pptx must be created or edited in
  this workflow. Do not load sibling MA skills — this skill is the whole path.
license: >-
  Anthropic pptx mechanics: see LICENSE.txt in this skill.
  Medical Affairs rules: Apache-2.0 (Open-Medical-Affairs).
metadata:
  version: "2.0.0-sundai-hack"
  tier: workflow
  maturity: hack
  role: single-hackathon-skill
  produces: Non-promotional M2M medical slide deck (.pptx) + provenance notes
---

# Sundai PowerPoint skill

**One skill for the hackathon.** PDF (or paper) in → appraised M2M deck out.

Do not load `medical-affairs-foundations`, `document-ingestion`, `medical-slide-deck`,
etc. as separate skills — their rules are **inlined below**. Optional: read
`house-rules/*.md` in this folder if present; those override this file.

Provenance: Anthropic [pptx](https://github.com/anthropics/skills/tree/main/skills/pptx)
mechanics + Open Medical Affairs content rules. On conflict: **MA rules win for
content**; Anthropic wins for packing a valid `.pptx`.

Output is always **draft material for qualified medical review**. Keep **DRAFT**
on the title slide. Never call the deck compliant, approved, or ready to submit.

---

## End-to-end pipeline (run in order)

### Stage 0 — Orient (foundations)

1. Job + audience (MSL M2M / scientific exchange — not promotional).
2. Data class (published PDF vs internal vs synthetic).
3. Evidence status (peer-reviewed, abstract, preprint, data on file, label).
4. Approval status of every use/population discussed; jurisdiction if it matters.
5. Name what is missing — do not invent it.

**Safety:** If the PDF or notes are human-sourced field/KOL/MI text, scan for AE / PQC /
special situations before analysis. Literature safety tables are literature, not cases.
You are a detection aid, not a PV control. Surface verbatim quotes if anything hits.

### Stage 1 — Ingest the PDF

- Extract text/tables/structure (pypdf / pdfplumber / `markitdown` as available).
- **Never guess unread content.** Scanned PDFs without OCR → say so and stop or offer a path.
- PDF tables mis-align columns — verify critical numbers against the rendered page; note which were eye-checked.
- Figures as images are invisible to text extractors — say what you could not read.

### Stage 2 — Appraise + cite

For every result you will put on a slide:

- Name design (RCT, single-arm, RWE, …), N, population, endpoints, CIs/HRs as reported.
- State what the result supports and what it does **not** support.
- No comparative claim without head-to-head evidence.
- Citations must be retrieved/verified — never invented. Unresolved IDs are removed, not caveated.

### Stage 3 — Capability check

Before promising `.pptx`: confirm `pptxgenjs` and/or `python-pptx`, write access,
and (for QA) LibreOffice/`pdftoppm` if available. If binaries are missing, still
deliver a complete markdown/HTML slide outline with citations and DRAFT marking,
and name the command that would render `.pptx`.

### Stage 4 — Build the M2M deck

**Structure (MSL / M2M scientific presentation):**

```
Title (DRAFT) + indication / audience
Disease context
Unmet need              evidence-based, not assertion
The evidence            design, population, results + CIs, limitations
Safety                  same prominence as efficacy
What remains unknown
References
Backup                  anticipated questions (not leftover slides)
```

**Medical ≠ commercial**

| | Commercial | Medical (required) |
|---|---|---|
| Headline | Message | What the data show |
| Safety | Buried | Alongside efficacy |
| Citation | Optional | Every data slide |
| Approval | Assumed | Stated |

**Headline test:** finding titles, not conclusions.
Good: `ORR 63% (single-arm, n=165)`. Bad: `Substantial activity`.

**Every data slide must have:** citation footer; design named; N + population; CIs;
evidence tier if not peer-reviewed (`[abstract]` / `[preprint]` / `[data on file]`).

**Palette (pptxgenjs: no `#`):**

| Role | Hex | Use |
|---|---|---|
| Ink | `12283A` | Titles, primary series |
| Slate | `5B6B79` | Secondary / axes |
| Teal | `0E7C7B` | One accent / the finding |
| Gold | `C89B3C` | Sparse callouts |
| Oxblood | `8C2F39` | Safety only |
| Cloud | `E8ECEF` | Banding / grids |
| White | `FFFFFF` | Content backgrounds |

One idea per slide. ≥0.5" margins. Left-align body. No title underlines, no decorative
sidebars, no cream backgrounds. Prefer native `addChart()`; clinical figures may be
PNGs. Keep decorative imagery off data slides.

### Stage 5 — Challenge (quality review)

Walk the deck:

- Citation + N + design on every data slide?
- Safety prominence comparable to efficacy?
- Any promotional / conclusion titles?
- Comparative claim without H2H?
- Approval status stated?
- Would it read the same if the product were a competitor's?
- DRAFT still on title?

### Stage 6 — MLR readiness + deliver

Hand off with: `.pptx` (or fallback outline), provenance (PDF name, what was / was not
readable, eye-checked numbers, citation list), open gaps, DRAFT marking. Flag items
reviewers must check before use.

---

## PPTX mechanics (create / edit / QA)

| Task | Approach |
|---|---|
| Create | `pptxgenjs` script (preferred) |
| Edit / template | unzip → edit `ppt/slides/slideN.xml` → zip |
| Read | `markitdown deck.pptx` |
| Thumbnails | `python scripts/thumbnail.py deck.pptx [prefix]` |
| Validate | `python scripts/office/validate.py deck.pptx` |
| Visual QA | `scripts/office/soffice.py --headless --convert-to pdf` then `pdftoppm -jpeg -r 150` |

### pptxgenjs gotchas

- Set `pres.layout` before slides (default 16:9 = 10" × 5.625").
- Hex without `#` or alpha digits. Use `transparency` 0–100 for fills.
- Fresh options object per `add*` call (library mutates in place).
- Shadow `offset` ≥ 0. `charSpacing` not `letterSpacing`.
- Bullets: `bullet: true`; `breakLine: true` except last.
- One `new pptxgen()` per file.
- Stacked-bar `dataLabelPosition`: only `ctr` / `inEnd` / `inBase`.
- Secondary-axis combos need both `valAxes` and `catAxes` (two entries each).
- Validate after `writeFile()`. Speaker notes: `slide.addNotes(...)`.

### Edit tips

Use `scripts/add_slide.py` / `scripts/clean.py` — do not hand-copy slide parts.
Structural add/delete/reorder before content edits. Prefer `defusedxml.minidom`
for OOXML transforms.

Scripts live under `scripts/` in this skill (from Anthropic pptx). If schemas or
LibreOffice are missing, still ship content-complete slides and note the gap.

---

## House rules

If `house-rules/` exists beside this file, those org overrides win. Seeded intent:
finding titles, citation in footer on each data slide, corporate template when named.

---

## Hackathon success criteria

- Single PDF ingested without hallucinated unread pages
- Appraised evidence on slides with real citations
- M2M structure + fair balance + DRAFT
- Valid `.pptx` (or explicit degraded delivery)
- Challenge pass documented
