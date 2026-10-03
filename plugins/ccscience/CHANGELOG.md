# Changelog

All notable changes to the `ccsci` plugin are documented here.
This project adheres to [Semantic Versioning](https://semver.org/).

## 0.10.0 — 2026-10-03

Retires the three skills Anthropic now ships, and moves the rest onto
Claude Code-first mechanics.

Removed:

- **`canvas-design`, `doc-coauthoring`, `web-artifacts-builder`.** Carried here
  while Claude Code lacked them; Anthropic now ships them as `anthropic-skills`.
  The ports differed from the originals only by one Claude Code note each.
  `NOTICE`, `LICENSE`, both READMEs, `plugin.json` and the marketplace entry
  follow. Use `anthropic-skills:canvas-design` and its siblings, which Claude
  Code syncs from a claude.ai sign-in; an install without them can copy the
  three skills from ccsci 0.9.0.

Fixed:

- **`figure-style` says how to load its kernel.** It named
  `apply_figure_style()` and the helpers as if a host had injected them.
- **Kernel imports use `${CLAUDE_SKILL_DIR}/kernel.py`**, which Claude Code
  substitutes, instead of a `/ABSOLUTE/PATH/TO/` placeholder (`bib-audit`,
  `figure-composer`, `figure-style`, `literature-review`, `paper-narrative`,
  `pdf-explore`).
- **`pdf-explore`**: the 1568px / ~1,600-token figures (the image limit before
  Opus 4.7) are gone; fan-out subagents run on Sonnet (`model: "sonnet"`, the
  latest Sonnet), and the 10–30× price claim is dropped.
- **`computational-scientist`**: each Bash `python` run is a fresh process —
  no persistent interpreter, no "cells". A long or heavy job runs when the
  user handed the run over — explicitly, or clearly enough that the dispatcher
  judged so; otherwise the agent returns the launch command. Dispatchers say which in the brief.
- **`paper-narrative` step 4** reads "plus its moved-in panels"; a formatter had
  turned the `+` into a list bullet.

Changed:

- The crop-every-panel self-QA passes (`figure-style` §9.2, `figure-composer`
  §3.5) read the full figure first and crop only where detail is dense; the
  §4 reviewer still crops every panel.
- `literature-review` names `bib-audit`'s DOI-stripping camera-ready preset as
  the different deliverable it is.
- Both agents drop `effort: xhigh` and inherit the session's effort level.
- The subagent tool is named `Agent` throughout, kernel docstrings included
  (`Task` remains an alias).
- Plugin-root references in skill bodies use `${CLAUDE_PLUGIN_ROOT}/…`.

## 0.9.0 — 2026-09-28

### Added — `bib-audit`, an end-to-end audit of an existing `.bib`

A model-invoked skill (also `/ccsci:bib-audit`) whose kernel, `audit(bib, tex)`,
verifies every entry, corrects it from the record it matches, replaces arXiv
preprints with their version of record, merges duplicates losslessly, deletes
garbage, strips non-citation fields (DOIs, abstracts, keywords, tool
bookkeeping, and URLs except where the entry is itself a website, repository or
piece of software), rekeys to `<Surname><Year><FirstContentWord>`, runs the
house `bibtex-tidy` command and validates the result with `bibtex` and
`biber --tool`. What no source settles lands in a review queue; the agent
researches it and records answers with `resolve`, which the next `audit`
applies. `rewrite_tex` migrates `\cite{}` keys through the emitted key map.

- **One routed lookup per entry, batched where the API allows**, instead of
  asking every database about every entry: Crossref by DOI (20 per request),
  arXiv metadata through DataCite (25 per request: latest version, comment,
  published DOI, category), the NeurIPS / PMLR / JMLR proceedings indices and
  the ICLR / NeurIPS / ICML conference-site paper lists (one download per
  year), Crossref bibliographic search, DataCite title search, and OpenReview
  title search last — it allows 20 requests a minute (5 on its older API). The arXiv API itself is asked only for pinned versions and version
  histories. Proceedings indices and past arXiv versions are cached machine-wide
  for good.
- **Never stalled by one slow source.** Lookups for different entries run on a
  thread pool, with request starts still spaced per host. A host that fails
  three attempts in a row is dropped for the rest of the run; the entries it
  would have settled come back `unchecked` and are retried by the next run.
- **Re-runs scale with edits, not with the bibliography.** Each settled entry is
  cached under a hash of its citation content (independent of key, layout,
  escaping, bracing and quote style); a second run over the audited 437-entry
  bibliography served 415 of its 428 entries from the cache, looked up only the
  13 still queued, and rewrote nothing.
- **Identity is strict or soft.** Strict: normalised titles and first authors
  agree. Soft (applied, listed for a glance): a dropped subtitle, a typo or
  spelling variant, a year off by one, a shuffled author order. A DOI or arXiv id
  that resolves to another work is an identity failure, corrected from a title
  search or queued; so is a journal slot (volume and first page, or JMLR paper
  number) that another work occupies — the signature of fabricated metadata.
- **Only the entry's own publication replaces it.** A reprint in an edited
  volume, a later edition, or a review of a book never does (kind and year
  guards), and an entry that names a journal or proceedings is never
  downgraded to its preprint: when no index confirms the venue it is kept as
  written and marked `unconfirmed`.
- **Versions.** A pinned arXiv version is cited exactly; otherwise the latest
  version's metadata with the year of first submission, unless title or authors
  changed across versions. A journal extension of a conference paper is reported,
  never swapped in. OpenReview counts as published only for an accepted paper's
  venue id (an allowlist): submissions under review stay preprints.
- **Venues** from `references/venues.tsv`: the publication's series name without
  edition or year, else `Proceedings of the <conference>`.
- **Outputs.** With `.tex` files the `.bib` is rekeyed in place and the citations
  are migrated, with a hard check that no previously defined key goes
  undefined. Without, the `.bib` keeps its old keys as a drop-in, beside
  `<stem>.rekeyed.bib` and `<stem>.keymap.tsv`. State lives under
  `.ccsci/bibaudit/<bib path>/`: cache, overrides, findings, per-run snapshots,
  and an appended `changes.md` recording every field change with its source.

- **Optional credentials, degrading when refused.** `S2_API_KEY` (Semantic
  Scholar), `OPENALEX_API_KEY`, and `OPENREVIEW_USERNAME` / `OPENREVIEW_PASSWORD`
  (or `OPENREVIEW_TOKEN` for two-factor accounts) are read from the environment.
  Semantic Scholar is asked only with a key (keyless calls answer 429); every
  other source is asked without one. A refused credential is dropped for the
  run, noted in the report, and the request repeated anonymously.
- **DBLP through SPARQL, Semantic Scholar by batch, OpenAlex for names and
  slots.** DBLP issues no API keys and walls dblp.org behind a bot check (probed
  2026-09-27), but `sparql.dblp.org` is open: title search there returns venue,
  year, pages, DOI and ordered authors (it finds the ICLR 2014 publication of an
  arXiv-only entry). Semantic Scholar's record of a preprint names its published
  version. OpenAlex supplies bylines, a journal's name by ISSN, and which work
  sits at a journal's volume and first page.
- **Names as printed on the paper.** The published byline is the reference's.
  Other bylines of the same work (publisher, proceedings and arXiv records;
  never author-registry profiles) only complete it: an initial or abbreviation
  to the name it starts ("G." → "Giovanni", "JF" → "John F."), a name or
  surname to its accented spelling ("Jose" → "José", "Buzsaki" → "Buzsáki"),
  and only where the byline name fits exactly one co-author — the Kendalls,
  Mosers and Leutgebs stay apart. Two written names are two names: "Ben" and
  "Benedict", "Nati" and "Nathan" are never merged. A byline printed surname
  first throughout ("Cavazzoni S., Razzoli L.") is read that way; one such name
  among "First Last" ones is a one-letter surname ("Weinan E."). Records of a
  discussion, reply, erratum or review of the work (Crossref's "[Title]:
  Comment") are neither matched nor used as name evidence. Never reordered,
  never inferred.
  Where bylines disagree with the entry beyond completion, the entry is kept and
  the author listed under `name_conflicts` for review — on every run until
  resolved, since the verdict is cached with the entry.
- **Journal names from one authority.** A journal article's venue is the
  container title Crossref's latest articles of that journal carry — the
  publisher's current name, by the entry's ISSN, else by the ISSN OpenAlex finds
  for the name; `references/journals.tsv` (alias → name) is consulted only when
  Crossref has no answer. The journal-level titles of Crossref and OpenAlex are
  catalogue forms ("Physical review. E", "Machine Learning Science and
  Technology") and are not used. The publisher's styling is taken as it is
  ("PLOS One", "Journal of Neuroscience"); a journal renamed since the article
  appeared keeps the name it appeared under (McCulloch and Pitts stay in "The
  Bulletin of Mathematical Biophysics", not its successor "Bulletin of
  Mathematical Biology"). When Crossref is unreachable the entry is not cached,
  and the next run completes it.
- **Opt-in whole-bibliography passes.** `audit(..., rekey=True)` regenerates
  every key (otherwise a key assigned by an earlier run is kept, recorded in
  `keys.json`, so re-runs never churn citations); `harmonise=True` rewrites each
  author to the unique fullest form the bibliography itself uses for them.
- **Acronyms keep their capitals.** Words with an inner capital or digit
  (`GANs`, `U-Net`, `ResNet50`) are braced in titles so no style lowercases them.
- **Preprints on other servers** (bioRxiv, SSRN, …) are verified from Crossref's
  posted-content records, and upgraded through their `is-preprint-of` link.
- **Fabricated-slot check** covers JMLR and PMLR volumes and, through OpenAlex
  and Crossref, journals; NeurIPS, ICLR and TMLR list no pages to check against.
- **Safe to re-run.** Cached verdicts carry the rules version and are discarded
  when the rules change. Two backups at most: the first original and the state
  before the latest run (`orig.bib` / `prev.bib` in the state directory,
  `<file>.tex.orig.bak` / `.prev.bak` beside rewritten `.tex` files). The
  machine-wide HTTP cache (`$XDG_CACHE_HOME/ccsci/bibaudit/http`) is pruned by
  age and size, 180 days and 200 MB by default (`BIBAUDIT_CACHE_MAX_AGE_DAYS`,
  `BIBAUDIT_CACHE_MAX_MB`).
- **Journal spellings compared by word, abbreviation, contraction and acronym**
  ("Proc. Natl. Acad. Sci.", "PNAS" and "Proceedings of the National Academy of
  Sciences" agree; "Physical Review A" and "E" do not) — for dedupe, the slot
  check and the journal authority alike.
- **Names BibTeX misreads are flagged** under `name_conflicts`, on every run
  until fixed: a middle comma part that is no suffix (Jr., Sr., a Roman numeral,
  an ordinal) or a third comma — as a rule a missing "and" ("Devries, Paul L.
  Hasburn, Javier E." is one person with the suffix "Paul L. Hasburn"). Which
  reading was meant is written nowhere, so none is repaired.
- **Validation in the document's own style**: bibtex compiles every entry with
  the style the `.tex` files name in `\bibliographystyle`, or with
  `audit(..., style=…)` (a name or a `.bst` path); plain otherwise. On the
  437-entry audit plain, plainnat and alpha give 3 warnings, ieeetr 2 (it does
  not sort), IEEEtran 3 others (it also rejects "Third edition" as an edition).
- **A missing `.tex` path or `style` stops the audit before anything is
  written**, so a mistyped path cannot leave the `.bib` rekeyed and the
  citations unmigrated.
- **Drift check reads LaTeX text symbols**: `\textregistered{}` and `®`
  compare equal, so `bibtex-tidy`'s rewrite of one into the other is not
  reported as a changed field.

The key scheme, the all-caps repair and the venue conventions carry over from an
earlier hand-run audit of a 437-entry bibliography; on that audit's accepted
419-entry output the key generator agrees on all 419 keys. Run on the same
original, the skill yields 421 entries, 407 of whose keys match the hand-run
result (the rest: publications that appeared since, name forms as the records
spell them, one title-changed preprint re-dated by the version rule), completes
12 author names from the papers' own bylines, lists no name conflict, and leaves
15 entries for review — among them both fabricated journal slots the hand-run
audit found — with 3 bibtex warnings, all genuine gaps. A 73-entry thesis with
34 `.tex` files, rekeyed in place, recompiles with no undefined citation and no
bibtex warning; a second run changes no key and rewrites no file.

## 0.8.1 — 2026-09-26

Housekeeping — coordinated marketplace version alignment alongside the `ws`
0.2.0 release (the new `test-gate`, `test-audit` and `deslop` skills). Nothing
in this plugin was edited. No skill logic changed.

## 0.8.0 — 2026-09-23

### Added — `paper-review`, a second reader for a human-written review

A user-invoked skill (`/ccsci:paper-review`) that captures a peer-review
workflow in which the reviewer writes the review and Claude supplies what a
sequential reader lacks: the whole paper in view at once. The phases are fixed —
frame (venue, rubric with its boundary words, rebuttal, form fields) → read the
whole paper → test the reviewer's impression against the text → decompose into
an arc line, a claim ledger, line-anchored findings, a missing list and the one
decisive experiment → argue both rubric boundaries for the score → constrain
and error-check the summary, title and review, in that order. Claude drafts
review prose only on "draft it".

Two invariants carry the weight. Every finding is anchored by a line reference
**and** a quoted phrase, because extraction line numbers drift and the phrase is
what finds the passage again. Literature enters the ledger only after its
primary source has been checked; an item that cannot be checked is tagged
`unverified`, kept under its own heading through every recap, and flagged as
substantive by every error check until it is checked (then retagged `derived`,
citing the source), dropped, or kept by the reviewer's stated decision — in
which case the confidence note names it. An unchecked attribution in a signed
review is the reviewer's liability. Venue statistics get the same discipline:
acceptance rates and score distributions are not calibration inputs, are never
volunteered, and when asked for arrive with their source and year or not at
all.

`references/anchors.md` carries the ledger and anchor templates with the tag
vocabulary (`evidenced` · `asserted` · `by construction` · `known from` ·
`announced, not reported` · `confounded`; `stated` · `derived` · `inferred` ·
`unverified`). `references/deliverables.md` carries the per-field constraints,
the review block tables by score band with word budgets, the don't-address
defaults, the error-check protocol (substantive first, wording second, final
pass errors only) and the context-dump block. `scripts/export_notes.py`
renders the notes to an A4 PDF for offline reading (Markdown through `pandoc`
or the `markdown` package, PDF through `wkhtmltopdf` or `weasyprint`); optional,
on request.

The skill ships **user-invoked** (`disable-model-invocation: true`): it changes
how the conversation runs for the whole session, and a review must not start
because a PDF was mentioned. Every example inside it is synthetic — real
submissions are confidential.

## 0.7.0 — 2026-09-02

### Fixed — no more placeholder address in the Crossref polite pool

`litrev_contact()` returned `example@example.com` when `LITREVIEW_CONTACT_EMAIL`
was unset, and all three call sites append the `mailto:` only when it is truthy
— so every unconfigured install identified itself to Crossref and doi.org with a
placeholder. The polite pool exists so an operator can be contacted about their
traffic; an address at a reserved domain (RFC 2606) identifies nobody and is
worse than sending none at all. It now returns `None` when the variable is unset
or blank, and those requests simply go out anonymously. The env var is unchanged
and still the way into the polite pool; the README and SKILL.md now say what
happens without it instead of describing a default that should never have been
one.

### Added — two validators at the model-JSON boundary

The Claude Science originals enforced two invariants in code, inside host calls
that returned parsed model output. The port replaced those calls with prompt
builders, and the invariants degraded into prose asking the model to comply.
Both are back as pure helpers, to be run on the JSON before anything else
touches it:

- **`finalize_outline(outline)`** (`figure-composer`) forces `data_vid=None` on
  every panel. A data ref names a file in the session; pixels cannot encode one,
  so any value a vision model puts there is invented and would send a panel
  subagent to a path that does not exist.
- **`finalize_paper_brief(brief, figure_claims)`** (`paper-narrative`) restores a
  missing `figures` list from the caller's own claims. A model that has just
  written four prose fields routinely drops it, and an empty list makes
  `narrative_review_task` render an empty per-figure table — the handling-editor
  reviewer then grades a deck it was never shown. Absent, `null` and `[]` are all
  treated as missing, which is wider than the original's `setdefault`; a
  non-empty list the model returned is always kept.

Both are pure — they return a new dict and never mutate their input — and both
raise on malformed input rather than silently passing it downstream.

### Added — a behavioural test tier

`tests/test_kernel_behaviour.py` executes the kernel helpers that are pure (no
network, filesystem, or third-party import) and pins their invariants: the two
new validators, `litrev_contact`'s no-address-means-no-`mailto` rule,
`extract_dois`, `dedupe_records`, `pdf_guard_text`'s guarantee that untrusted
page text cannot forge a prompt delimiter, and the panel geometry. The existing
suite stays static-only and is now labelled Tier 1; this is Tier 2 and needs no
skill dependency installed, because the kernels defer every heavy import.

Writing it immediately surfaced a live defect — see below.

### Fixed — `extract_dois` dropped markdown bold before a full stop

`**10.x/y**.` extracted as `10.x/y**`. The trailing-punctuation strip is
anchored at end-of-string and had no `.` in its character class, so on that
input it matched nothing; only afterwards did a separate `removesuffix(".")`
run, by which point the asterisks were stranded with no second pass to catch
them. `**10.x/y**,` was always fine, because a comma _is_ in the class and went
in the same bite. The malformed DOI then failed verification, so the failure was
quiet rather than harmful — a citation simply went missing from a draft that
wrote its DOIs in bold.

`.` is now folded into the character class and the separate period-strip is
gone, which fixes the case and makes the pass order-independent: mixed runs like
`**.`, `..` and `.,` all go in one bite. Interior periods are untouched —
`10.1234/v1.2.3` still extracts whole. Present in the Claude Science original;
found by the new behavioural tier, not by report.

### Changed

- `style_pass(draft)` no longer accepts `model`. The parameter was inherited from
  the original, which never used it either, and it advertised a knob that did
  nothing.
- The `computational-scientist` agent's companion-skills line now names
  `/mf:author` as where a workflow or library gotcha worth keeping gets written
  up as a skill. A pointer only — the agent is not told to volunteer it.
- `NOTICE` added — the plugin was the only one in this marketplace without one.
  It separates what is reproduced verbatim (the three public skills, the fonts,
  the `web-artifacts-builder` scripts) from what is substantially adapted and
  what is original, and records why the per-skill `LICENSE.txt` copies are not
  carried over.

## 0.6.0 — 2026-09-02

### `figure-style` now declares when NOT to load

Upstream Claude Science narrowed this skill's activation scope on 2026-08-31,
and the narrowing is adopted here. Previously both the description and §0 said
to load before _any_ plot, which pulled a long correctness checklist into
context for throwaway EDA scatters and sanity-check histograms — cost with no
deliverable to pay for it.

The trigger is now **final-deliverable figures**: those shipping in a report,
paper, or export, or saved as a file that will be kept. Exploratory and
intermediate plots are drawn plainly, without the skill. A new §0 **Load
trigger** paragraph states this, the frontmatter `description` leads with it so
the decision is made before the body is read, and the two places that asserted
the old rule — the README skill table and the `computational-scientist` agent's
companion-skills line — were corrected to match. No rule inside §1–§9 changed,
and the kernel is untouched.

Upstream's own wording cites a Claude Science system-prompt section that has no
Claude Code counterpart; that reference is dropped rather than ported dead. The
same upstream pass also restyled prose to en-US and stripped explanatory
comments from the kernels — neither is adopted: this repository is en-GB
throughout, and the kernel comments carry the reasoning behind the port's own
adaptations.

## 0.5.4 — 2026-08-06

Declares **Python 3.14+** as the floor for the bundled kernels in the plugin
README. Housekeeping otherwise — coordinated marketplace version alignment
alongside the `mf` guidance update and a repository-wide formatter pass. No
skill logic changed.

## 0.5.3 — 2026-08-06

Housekeeping — coordinated marketplace version alignment, alongside the addition
of the `ws` (whetstone) plugin and the new `/mf:author` skill in `mf` 0.7.0.
Nothing in this plugin was edited. No skill logic changed.

## 0.5.2 - 04-08-2026

Housekeeping — coordinated marketplace version alignment. Nothing in this plugin
was edited. No skill logic changed.

## 0.5.1 — 2026-07-30

Housekeeping — coordinated marketplace version alignment, alongside the addition
of the `tml` (tuneml) plugin and the removal of `parml`. Nothing in this plugin
was edited. No skill logic changed.

## 0.5.0 — 2026-07-27

Coordinated marketplace version bump, alongside a repository-wide formatter pass
and the addition of the `parml` (paretoml) plugin. The formatter normalised the
newly added files only — this plugin's were already conformant from the `e8fd3cd`
pass and are byte-unchanged. No skill logic changed.

## 0.4.0 — 2026-07-27

### Fixed — kernels parse again on Python older than 3.14

`literature-review` and `pdf-explore` each carried `except A, B:` clauses left
behind by a py314-targeted formatter pass: PEP 758 syntax, accepted only on
Python 3.14+. Every earlier interpreter raises `SyntaxError` while parsing, so
both kernels were unloadable on the Python most agent environments actually
provide, and Tier-1 validation failed against CI's 3.12.

The three exception lists now live in named module-level tuples — `_NET_ERRORS`
and `_RESOLVER_ERRORS` in `literature-review`, `_PDF_COERCE_ERRORS` in
`pdf-explore` — instead of an inline `except (A, B):`. A bare name has no
parentheses for a formatter to strip, so the fix survives a repeat
`ruff format --target-version py314 --preview` rather than regressing on the
next reformat. Same exception types caught at the same three sites; no
behaviour change.

## 0.3.1 — 2026-07-23

Housekeeping — coordinated marketplace version alignment. No skill logic changed.

## 0.3.0 — 2026-07-14

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
