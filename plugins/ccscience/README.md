# ccsci

Research and scientific-computing building blocks from [Claude Science](https://claude.com/product/claude-science),
adapted to run on **stock Claude Code** — every `host.*` runtime dependency swapped for a
standard Claude Code tool (`Task` / `Read` / `Write` / `Bash` / env-var) or plain prose.

Designed for researchers: read the literature without fabricating citations, navigate big PDFs,
draw publication-grade figures, and hand heavy computation to a dedicated specialist agent.

## Install

From any Claude Code session:

```
/plugin marketplace add emaballarin/ccplugins
/plugin install ccsci@ccplugins
```

After installation, eight skills are available under the `ccsci` namespace and two subagents
(`computational-scientist`, `deep-researcher`) become delegatable.

## Setup

Nothing is required to _install_ the plugin. Set what the skills you actually use need:

**Environment variables**

- **`LITREVIEW_CONTACT_EMAIL`** — your email address, sent in the User-Agent for the
  Crossref / doi.org **"polite pool"** (faster, more reliable lookups). Defaults to the
  placeholder `example@example.com`; **set it to a real address you own** before running
  literature reviews. `literature-review` reads it directly.
    ```bash
    export LITREVIEW_CONTACT_EMAIL="you@example.org"
    ```
- **`OPENALEX_API_KEY`** — optional; raises OpenAlex's per-request rate budget. Without it,
  OpenAlex calls still work unauthenticated (subject to shared limits). `literature-review`
  reads it directly.
    ```bash
    export OPENALEX_API_KEY="…"
    ```

Put these in your shell profile (or a per-project `.envrc`) so every session picks them up.

**Python 3.14+ is required** for the bundled kernels — the marketplace's
declared floor, not an incidental version.

**Optional dependencies** (install only what the skills you use need)

| For                                                    | Install                                                                       |
| ------------------------------------------------------ | ----------------------------------------------------------------------------- |
| `literature-review` (`.bib` export)                    | `npm install -g bibtex-tidy`                                                  |
| `pdf-explore`                                          | `pip install pypdfium2 pillow` (plus `pdfplumber` for tables)                 |
| `figure-style` / `figure-composer` / `paper-narrative` | `pip install matplotlib pillow`                                               |
| `canvas-design`                                        | a PDF/PNG renderer — `pip install matplotlib` (or `reportlab` / `weasyprint`) |
| `web-artifacts-builder`                                | Node 18+ and `npm`                                                            |

## Skills

| Skill                     | When                                                             | What it does                                                                                                                                                                                                                                                                                                                                                                                                                                                                 | External deps                                                                                                                          |
| ------------------------- | ---------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| **literature-review**     | "find the seminal paper for X", a full review, grounding a claim | Retrieve → verify → synthesise scientific literature with **no fabricated DOIs**. All-STEM (arXiv / DBLP / Semantic Scholar / alphaXiv first-class, plus OpenAlex / Crossref / PubMed); walks the citation graph; flags superseded / withdrawn / **refuted** work; ends with a resolve-published → dedupe → `.bib` → `bibtex-tidy` export. DOI kept everywhere by default.                                                                                                   | `bibtex-tidy` (npm); optional `OPENALEX_API_KEY`; `LITREVIEW_CONTACT_EMAIL` (Crossref polite pool — set your own, see [Setup](#setup)) |
| **pdf-explore**           | an answer needs content from more than one place in a PDF        | Parse a PDF **once**, then read pages as persistent text (`pdf_pages`), build a TOC (`pdf_outline`), or fan whole-doc relevance scans / per-page maps / structured extraction out over **Task subagents** so the pages never fill your own context. **Tables** via `pdf_tables` (deterministic, page provenance, full table → CSV); **figures** via `pdf_images` (embedded rasters at native resolution) with `pdf_pages(mode="image")` → `pdf_crop` as the vector fallback. | `pypdfium2`, `pillow` (pip); `pdfplumber` for tables                                                                                   |
| **figure-style**          | before drawing any plot                                          | Publication-figure **correctness** checklist (data fidelity, label economy, colour threading, render-then-verify) plus a matplotlib helper kernel (`apply_figure_style`, palettes, panel letters, per-panel crop QA).                                                                                                                                                                                                                                                        | matplotlib                                                                                                                             |
| **figure-composer**       | building one multi-panel figure from a claim + data              | Outline (12-col grid) → one `Task` subagent per panel (each loads `figure-style`) → tile + letter → adversarial composite review → regen, ≤3 rounds.                                                                                                                                                                                                                                                                                                                         | matplotlib, pillow                                                                                                                     |
| **paper-narrative**       | judging / reshaping the story a paper's figures tell             | Handling-editor review of the whole figure deck; converts the verdict into concrete moves and feeds a revised Fig-1 claim into `figure-composer`.                                                                                                                                                                                                                                                                                                                            | matplotlib, pillow                                                                                                                     |
| **canvas-design**         | a poster, artwork, or other static design piece                  | Generative visual art via a design-philosophy manifesto expressed on a `.pdf`/`.png` canvas, with ~40 bundled typeface families.                                                                                                                                                                                                                                                                                                                                             | a renderer (matplotlib / reportlab / Pillow, or HTML→PDF)                                                                              |
| **doc-coauthoring**       | writing a doc, proposal, spec, or decision doc                   | A three-stage guided workflow — context gathering → section-by-section refinement → reader testing (via a `Task` subagent) — to produce a doc that works for its readers.                                                                                                                                                                                                                                                                                                    | —                                                                                                                                      |
| **web-artifacts-builder** | a complex multi-component HTML artifact                          | Scaffold a React + Tailwind + shadcn/ui app and bundle it into one self-contained HTML file.                                                                                                                                                                                                                                                                                                                                                                                 | Node 18+ / npm                                                                                                                         |

## Agents

**computational-scientist** — a delegatable scientific-computing specialist, distilled from the
Claude Science OPERON persona: produce artifacts (not just answers), work in a lab-notebook /
methods register, read the docs before coding, compute-don't-confabulate, and ground capability
claims in what's actually installed. It runs a compute task in its own context, writes real output
files, and returns a structured summary with paths.

It is the **compute half** of a pair with the [`deep-researcher`](https://github.com/emaballarin/ccplugins)
agent — one researches, one computes. `deep-researcher` supplies the DOI-grounded synthesis that
`literature-review` provides the machinery for; `computational-scientist` loads `figure-style` for
any plot and `pdf-explore` when PDFs are in play. The plugin ships **both** agents; `deep-researcher`
is bundled in a **mindfunnel-optional** form — it reads project files (`SOUL.md` / `USER.md` /
`PROJECT.md`) only if present and mentions `/mf:dump` merely as one optional memory-consolidation
cycle, so it works standalone.

## How this relates to what already ships with Claude Code

- **Not re-shipped** — `skill-creator` and `product-self-knowledge` are omitted: both are already
  covered by skills that ship upstream in Claude Code (`skill-creator`, `claude-api`).
- **Adjacent, not duplicate** — `figure-style` complements the upstream `dataviz` skill
  (correctness invariants vs. chart-design system); `literature-review` complements a
  `deep-research`-style agent (DOI-grounded scholarly synthesis vs. general web research);
  `web-artifacts-builder` overlaps `artifact-design` on the design side but adds the React/shadcn
  build toolchain.
- **Deferred** — the remote-compute skills (`remote-compute-ssh`, `compute-env-setup`) are a later pass.

## Provenance & license

Adapted from the Claude Science skills (Apache-2.0, © Anthropic PBC). The adaptations and the new
agents (`computational-scientist`, and the mindfunnel-optional `deep-researcher`) are © Emanuele
Ballarin. Ships under **Apache-2.0** — see [`LICENSE`](LICENSE).

> **Font licensing note:** the `canvas-design` typefaces are under the SIL Open Font License by
> their respective authors, **not** Apache-2.0. Each font ships with its OFL license file in
> `skills/canvas-design/canvas-fonts/`.

## Links

- Marketplace: [emaballarin/ccplugins](https://github.com/emaballarin/ccplugins)
- Changelog: [CHANGELOG.md](CHANGELOG.md)
