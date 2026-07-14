# Changelog

All notable changes to the `ccsci` plugin are documented here.
This project adheres to [Semantic Versioning](https://semver.org/).

## 0.3.0 — 2026-07-07

### `pdf-explore` — tables and embedded figures

Two additive kernel helpers, closing gaps the skill previously conceded in its
own prose (it told you to pay a vision model to transcribe ruled tables, and
could only reach a figure by cropping a downsampled page raster).

- **`pdf_tables`** — deterministic table extraction with **per-table page
  provenance**. No model, no vision, no fan-out: pdfplumber reads the grid off
  the page geometry. The full table is written to a CSV under the cache dir and
  only a capped preview is returned, so a 300-row table never enters the agent's
  context. `min_rows`/`min_cols` (2×2) reject the n×1 "tables" that ruled-line
  detection produces from boxed captions. `table_settings` passes through for
  whitespace-aligned tables. This is the one helper on a second backend —
  PDFium exposes no table API — so **pdfplumber is a new optional dependency**,
  lazily imported and needed only when `pdf_tables` is called.
- **`pdf_images`** — extract embedded raster figures at their **native
  resolution**, via pypdfium2 (**no new dependency**). On a typical paper the
  page-1 figure is embedded at 2372×1359, where a crop from a 100-dpi page
  render yields ~570×326 — roughly 4× the linear detail, for less work.
  Byte-identical images are deduplicated (a per-page logo collapses to one entry
  listing its pages) and sub-`min_px` decoration is dropped. Defaults to
  `render=True`, saving the image as pdfium composites it, because pdfium's raw
  extraction path ignores alpha masks and can silently mis-render a transparent
  figure; `render=False` still offers lossless JPEG/JPEG-2000 passthrough.
  Only raster XObjects are visible to it — vector figures (TikZ, pgfplots,
  matplotlib-PDF) are drawing operations, not images, and still need the
  render-and-crop path, which the skill now documents as the explicit fallback.

Both write into the existing `.cache/pdf-explore/{sha8}-{mtime}/` convention
(`img/`, `tables/`), keyed on mtime — scratch assets for the agent to `Read`,
not a deliverable directory.

`SKILL.md` additionally documents a `uv run --with …` invocation, so the kernel
runs with no install at all.

## 0.2.1 — 2026-07-07

Formatting-only patch. Ran the Markdown/YAML formatter across the plugin
(emphasis-delimiter and table-alignment normalisation, list and YAML
re-indentation). No change to skill or agent behaviour.

## 0.2.0 — initial release

Research and scientific-computing building blocks adapted from Claude Science
for stock Claude Code. Every `host.*` dependency was replaced with a standard
Claude Code tool (`Task` / `Read` / `Write` / `Bash` / env-var) or plain prose.

### Skills

- **literature-review** — retrieve → verify → synthesise scientific literature
  with no fabricated DOIs. Decoupled from the Science host (contact email via
  `LITREVIEW_CONTACT_EMAIL`, OpenAlex via `OPENALEX_API_KEY`); extended from
  bio-leaning to all-STEM (arXiv / DBLP / Semantic Scholar / alphaXiv first-class;
  "superseded / withdrawn / refuted" generalisation; CS/eng evidence calibration);
  added a resolve-published → dedupe → `.bib` → `bibtex-tidy` export step. DOI is
  retained everywhere by default.
- **pdf-explore** — parse a large PDF once, then navigate / scan / map / extract.
  The pure-Python text paths (pypdfium2) are unchanged; the parallel-model helpers
  now fan out via `Task` subagents instead of the in-process host model, and
  figure crops are viewed with `Read`.
- **figure-style** — publication-figure correctness checklist plus a matplotlib
  helper kernel. Ships essentially unchanged; the host image-view call is now
  `Read`.
- **figure-composer** — compose one publication-grade multi-panel figure: outline →
  per-panel `Task` fan-out (each panel loads `figure-style`) → tile + letter →
  adversarial composite review → regen (≤3 rounds). Deterministic tiling kept;
  `host.view_image` → save-crop + `Read`, `save_artifacts` → `Write`.
- **paper-narrative** — judge and reshape the story a paper's figure deck tells (a
  simulated handling-editor review), feeding revised per-figure claims into
  `figure-composer`. The `host.llm` brief-derivation and the review become `Task` steps.
- **canvas-design** — generative poster/art via a design-philosophy manifesto,
  with ~40 bundled typeface families.
- **doc-coauthoring** — three-stage guided doc / spec / proposal co-writing.
- **web-artifacts-builder** — scaffold + bundle a React / Tailwind / shadcn app
  into one self-contained HTML file (requires Node 18+).

### Agents

- **computational-scientist** — a delegatable scientific-computing specialist
  distilled from the Claude Science OPERON persona (produce artifacts, methods
  register, compute-don't-confabulate, read-docs-first), translated to Claude Code
  tools. Pairs with the `deep-researcher` agent — one researches, one computes.
- **deep-researcher** — the research half of the pair, bundled in a
  mindfunnel-optional form: reads `SOUL.md` / `USER.md` / `PROJECT.md` only if
  present, uses the native `memory: user` feature, and references `/mf:dump` merely
  as one optional memory-consolidation cycle.

### Not included / deferred

- `skill-creator` and `product-self-knowledge` are omitted — both are already
  covered by skills shipping upstream in Claude Code.
- The remote-compute skills (`remote-compute-ssh`, `compute-env-setup`) are deferred
  to a later pass.

### External dependencies

- `literature-review`: `bibtex-tidy` (npm) for `.bib` formatting; optional
  `OPENALEX_API_KEY`.
- `pdf-explore`: `pypdfium2`, `pillow` (pip).
- `figure-style` / `figure-composer` / `paper-narrative`: matplotlib + pillow.
- `canvas-design`: a PDF-or-PNG renderer.
- `web-artifacts-builder`: Node 18+ and npm.

### Licensing note

Ships under Apache-2.0 (see `LICENSE`). The `canvas-design` typefaces are under
the SIL Open Font License by their respective authors; each ships with its OFL
license file alongside the font in `skills/canvas-design/canvas-fonts/`.
