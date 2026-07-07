---
name: literature-review
description: Find, verify, and synthesize STEM literature across every field — from "what's the seminal paper for X" through full multi-source reviews. Treats journal articles, arXiv/preprints, and conference proceedings as first-class; grounds every claim in a retrieved source, never fabricates DOIs, checks for superseded/withdrawn/refuted work, calibrates confidence to evidence strength (including SOTA/reproduction/ablation caveats for CS and ML), and emits a tidy DOI-pinned BibTeX reference list. Pairs with the deep-researcher agent.
license: Apache-2.0
metadata:
    # Sends the user's query to Crossref (with a polite-pool contact email from
    # LITREVIEW_CONTACT_EMAIL), OpenAlex (with OPENALEX_API_KEY when set — no
    # email is ever sent to OpenAlex), the arXiv API, DBLP, and Semantic Scholar.
    # BibTeX is fetched from doi.org via content negotiation. The alphaXiv MCP
    # (mcp__alphaxiv__*) is the preprint retrieval/reading path when wired in.
    third_party:
        - kind: service
          name: Crossref
          info_url: https://www.crossref.org/documentation/retrieve-metadata/
          privacy_url: https://www.crossref.org/operations-and-sustainability/privacy/
        - kind: service
          name: OpenAlex
          terms_url: https://openalex.org/OpenAlex_termsofservice.pdf
          privacy_url: https://openalex.org/OpenAlex_privacy_policy.pdf
        - kind: service
          name: arXiv
          info_url: https://info.arxiv.org/help/api/index.html
        - kind: service
          name: DBLP
          info_url: https://dblp.org/faq/How+to+use+the+dblp+search+API.html
        - kind: service
          name: Semantic Scholar
          info_url: https://api.semanticscholar.org/api-docs/
        - kind: service
          name: alphaXiv
          info_url: https://www.alphaxiv.org/
---

# Literature review

A literature question has two halves: finding the papers a domain expert would point to, and turning them into something more useful than a reading list — a synthesis that says what's established, what's contested, what's new, and where the holes are. Both halves can fail quietly and look like competent output until someone checks. This covers all of STEM — a machine-learning benchmark result, a distributed-systems protocol, a materials-synthesis route, and a clinical trial are all in scope, and the same discipline applies to each: retrieve before you write, ground every claim in a real record, never invent an identifier.

## Read the request for what it's actually asking

"What's the paper for X" wants one or two specific citations; "what's the evidence on X" wants a synthesis; "compare A and B" wants a comparison, not two adjacent summaries; "where are the gaps" wants the gaps, with the survey as supporting material. A two-word lay query wants you to choose the scope a domain expert would default to and say so up front — "I'll read this as the transformer _architecture_ paper, not the earlier attention mechanism it builds on" or "I'll take this as human RCT evidence; the animal literature is separate." Ask a clarifier only when the answer would genuinely change what you do.

## Load the helpers

`kernel.py` in this skill's directory ships the retrieval and BibTeX helpers. There is no auto-injection: import the file by its path before using it, and the module has zero import-time side effects, so importing it costs nothing. From a Bash `python` invocation (substitute the absolute path to this skill's `kernel.py`):

```bash
python - <<'PY'
import importlib.util, json
spec = importlib.util.spec_from_file_location("litrev_kernel", "/ABSOLUTE/PATH/TO/skills/literature-review/kernel.py")
lr = importlib.util.module_from_spec(spec); spec.loader.exec_module(lr)
print(json.dumps(lr.verify_dois(["10.1145/3292500.3330701"]), indent=2))
PY
```

The public helpers are `verify_dois`, `crossref_lookup`, `search_openalex`, `expand_citations`, `extract_dois`, `style_pass`, `resolve_published` / `resolve_published_all`, `dedupe_records`, `to_bibtex`, and `bibtex_tidy`. Each call is a short `python` run that imports the module and prints JSON you read back. Two optional env vars tune the polite path: `LITREVIEW_CONTACT_EMAIL` (Crossref/doi.org polite pool; defaults to a placeholder — set it to a real address you own) and `OPENALEX_API_KEY` (raises OpenAlex's per-request budget; without it, OpenAlex calls go out unauthenticated and still work, subject to shared rate limits).

## Grounding: retrieve first, then write

For broad-survey, where-are-the-gaps, and compare-methods requests, the first move is a literature sweep, and the answer is built from what comes back. Your recall picks the framing; the retrieval picks the citations. Spread the sweep across the sources that fit the field:

- **`search_openalex` / `crossref_lookup`** from `kernel.py` — the all-field backbone (OpenAlex indexes ~250M works: journals, proceedings, and preprints alike).
- **arXiv, and conference proceedings, as first-class results** — for CS, ML, math, physics, and stats, the version that matters is often an arXiv preprint or a proceedings paper (NeurIPS, ICML, ICLR, CVPR, ACL, STOC, SIGCOMM, …), not a journal article. Treat them as primary literature, not second-class. The arXiv API (`http://export.arxiv.org/api/query`) and **DBLP** (`https://dblp.org/search/publ/api`) are the direct routes to preprints and CS proceedings; **Semantic Scholar** (`https://api.semanticscholar.org/graph/v1`) adds cross-field metadata, `externalIds`, and influential-citation counts.
- **The alphaXiv MCP** — when the alphaXiv tools are available (`mcp__alphaxiv__discover_papers`, `mcp__alphaxiv__get_paper_content`, `mcp__alphaxiv__answer_pdf_queries`, `mcp__alphaxiv__read_files_from_github_repository`), use them as the arXiv/preprint discovery-and-reading path: `discover_papers` to find preprints on a topic, `get_paper_content` / `answer_pdf_queries` to read a specific one closely (methods, ablations, claimed vs. reproduced results). alphaXiv covers CS, math, physics, stats, quant-bio/fin, and EE — not biomedical or clinical literature.
- **PubMed and domain connectors** — for life sciences and clinical work, PubMed and connectors like ClinicalTrials.gov or bioRxiv. Run a scan of the available MCP tools once at the start (the tool list names them, e.g. `mcp__*`) and use whichever literature/data server fits the field.
- **Web search** — for grey literature, very recent work, blog-first results, and disambiguation.

A real survey usually carries on the order of fifteen or more distinct primary-paper DOIs, because each claim is anchored to the paper that established it; a handful of review citations is a reading list, not a synthesis. When the question is after a _specific_ paper — "the original," "the seminal," a named model, trial, or method — find the highly-cited primary publication that the follow-ups all cite, not a review or news piece about it.

That applies even when you know the answer cold. Resolving the DOI for a paper you're certain of — the Transformer paper, ResNet, a textbook constant, a landmark trial — is a one-second tool call, and it's the difference between a citation and a claim about a citation. Verification is something that happens in your tool trace, not a sentence in your reply. **A DOI you emit either resolves to a real paper that says what you claim, or it's a fabrication, and the difference is checkable in five seconds.** When you have author/year/venue but not the DOI, look it up via Crossref, OpenAlex, DBLP, or Semantic Scholar rather than pattern-completing one; when even those details are hazy, that's a search query, not a citation. For recent developments, contested findings, or anything you "remember" from near or after your knowledge cutoff, retrieval isn't optional.

After the first sweep, take the two or three most relevant hits and walk one step in each direction on the citation graph: pull their reference lists (backward) and their cited-by lists (forward), then fold anything new and on-topic into the set before you start writing. The seminal paper a field builds on surfaces in the backward step; the recent work that extends or contests your top hits surfaces in the forward step, and neither reliably appears in a keyword sweep alone. `expand_citations(doi)` in `kernel.py` returns both directions from OpenAlex.

## Resolve, dedupe, and emit BibTeX

After the citation-graph expansion and before you write the reference list, normalize what you've gathered. Preprints and their published versions are the same work wearing two identifiers, and a reference list that carries both — or that cites an arXiv id when a peer-reviewed version of record exists — is a defect. Run this pipeline on the collected records:

1. **Resolve preprints to the version of record.** `resolve_published(record)` (or `resolve_published_all(records)` for a list) takes a record carrying any of `arxiv_id` / `doi` / `title` / `authors` and looks up the published DOI via OpenAlex locations, the arXiv `<arxiv:doi>` / journal-ref field, a Crossref title+author search, and Semantic Scholar `externalIds`, in that order. It returns the record with `doi` set to the **published** DOI when one exists, the arXiv id preserved as a secondary `arxiv_id` field, and `resolved_from` naming the source. When a paper is genuinely preprint-only, the arXiv identifier stays as the record's DOI — flag it as a preprint in the prose.
2. **Collapse duplicates.** `dedupe_records(records)` merges a (preprint, published) pair into one entry keyed by the published DOI, and further dedupes by DOI, normalized title, citation key, and arXiv id. One work, one entry.
3. **Fetch BibTeX.** `to_bibtex(dois)` retrieves a BibTeX entry per DOI via DOI content negotiation (`GET https://doi.org/<DOI>` with `Accept: application/x-bibtex`). Run `verify_dois` first so only real DOIs reach this step. Write the returned entries to a `.bib` file with the `Write` tool.
4. **Tidy.** `bibtex_tidy(bib_path)` runs the `bibtex-tidy` npm CLI in place (`npm i -g bibtex-tidy`; if it is not on PATH the helper leaves the file untidied and returns a note rather than failing). This normalizes braces, sorting, field order, and duplicates.

**DOI policy — keep the DOI everywhere by default.** The DOI is the pin that makes verification, the inline `[Author Year](https://doi.org/…)` links, and dedupe all work, so it is retained throughout: `verify_dois` resolves it, the prose links through it, `to_bibtex` keeps the `doi` field, and the default `bibtex_tidy(bib_path)` omits only `abstract` and `keywords`. Stripping the DOI is an **optional** variant, never the default: call `bibtex_tidy(bib_path, drop_doi=True)` only when a downstream consumer explicitly needs a DOI-free `.bib` (it swaps in `--omit=abstract,keywords,doi`; everything else is identical). Do not strip DOIs from the review itself.

## Superseded, withdrawn, refuted

Sensational or surprising results are findable _because_ they were sensational, and some did not hold up: a retracted paper, a withdrawn preprint, a flawed proof, a benchmark result no one could reproduce, an effect that failed to replicate. The discipline is the same across fields — before you build on a high-profile or surprising finding, check what happened to it. Crossref's `update-to` field flags retractions (and `verify_dois` surfaces a `retraction` flag on Crossref hits); withdrawals, errata, corrigenda, and expressions of concern ride in that same `update-to` field and warrant a direct look. For preprints, check whether a later version withdrew or substantially revised the claim, and whether the published version of record even exists. For computational and theoretical work, "REFUTED" is the operative word: a proof with a known gap, a result later shown incorrect, a method whose headline number was a benchmark artifact. The related trap is the question whose honest answer is "no such paper exists": when someone asks for "the paper showing X" and X fell apart or was never established, name the claim, say what happened to it, and point to what the actual evidence shows — not the closest-matching citation.

## Synthesis is comparison, not summary

A list of papers with one-sentence summaries is a bibliography. The useful layer is on top: this finding replicated, that one didn't; these three agree on the effect but disagree on mechanism; this method wins on ImageNet and that one on long-context; this 2015 result was superseded by this 2022 one. Organize by theme or question, not by paper. For compare-methods requests the deliverable is the trade-off and a recommendation, not two summaries.

## Making the prose carry its weight

A review paragraph earns its place by opening on _your_ synthetic claim and then spending citations to back it, not by opening on a citation and reporting what it found. "Chen 2019 reported a 40% reduction; Park 2020 reported 35%" is two index cards. "The effect is real but modest, with pooled estimates clustering at 35-40% (Chen 2019; Park 2020)" is a review. The diagnostic: read only the first sentence of each paragraph in sequence; if they form your argument, you've written a synthesis; if they form a list of author names, you've written an annotated bibliography in paragraph costume.

## Write prose, not a bulleted bibliography

The artifact should read like a section of a referee-grade review: paragraphs of connected argument, each making one claim and anchoring it with an inline citation, transitioning to the next. A page that is 80% bullet points is a reading list dressed up as a review — it tells the reader _that_ papers exist, not what they collectively show. Reserve bullets for places a list is genuinely the right structure (a reference appendix, a head-to-head comparison table, an enumerated set of named methods); the synthesis itself is prose. If you find yourself starting consecutive lines with `- Author Year showed…`, that's a paragraph that hasn't been written yet.

## Calibrating to evidence

Say which findings are landmark and which are recent; flag preprints as preprints; note when older results were refined or overturned. Match confidence to evidence: a single-cohort finding is "one group reported X," a phase-3 RCT is stated plainly, a contested area gets both sides and an honest "unresolved." When the question contains a contested premise, engage the premise rather than building on it. When the request is about gaps, name specific ones and anchor each to what establishes it as a gap — "more research is needed" means you haven't found the actual hole.

Computational, engineering, and ML work needs its own calibration, because a result can be real and still not mean what the headline says:

- **SOTA on one benchmark is one data point.** A method that tops a single leaderboard may not generalize; ask whether the gain holds across datasets, whether the baselines were tuned as hard as the proposed method, and whether the comparison is compute-matched.
- **Independent reproduction is the bar.** Distinguish "the authors report X" from "others reproduced X." An unreplicated headline number, especially from a preprint with no released code, is a claim, not a result. Released code and third-party reproductions raise confidence; their absence lowers it.
- **Ablations tell you what actually did the work.** A paper without ablations hasn't isolated its own contribution — the gain may come from a confound (more data, longer training, a better tokenizer) rather than the named idea. Note when the ablations are missing or thin.
- **Proof versus empirics.** Keep the distinction explicit: a theorem with stated assumptions and a checked proof is a different kind of evidence than an empirical curve, and a proof is only as strong as its assumptions hold in practice. Flag proofs with known gaps or unrealistic assumptions, and empirical claims dressed up as guarantees.

## Put the answer in the answer — and open on the substance

The review — prose, citations, bottom line — belongs in your response text, where the reader sees it. For anything beyond a one-paper lookup, also save the full review to a Markdown file with the `Write` tool so the reader has a clean, linkable document; the chat reply _is_ the answer, and any pointer to the saved file goes at the end of it, never as a "Report saved:" opener. A reply that is _only_ "I've saved a 14-paper review, all DOIs verified" is not an answer — write the substance in the chat, then mention the file.

The first sentence should be content the reader came for: the finding, the paper, the comparison. "Here's the synthesis," "All DOIs verified against Crossref; no retraction flags," "I've verified every citation," "the report is current as of today" — these are process narration, and they don't belong in the chat reply _or_ the saved file. Verification happens in your tool trace; the reader infers it from citations that resolve and claims that hold up. Do not write a "DOIs verified / no retractions" line anywhere in the output — not as an opener, not as a footer, not as an italic subtitle under the title. The saved file follows exactly the same rule as the chat reply: open on substance, close on substance. The register to aim for is a tight methods paragraph or a referee-grade mini-review: lead with the key result, lay out the supporting evidence with inline DOIs, address the obvious counterpoint or limitation, and close on what's still open. A reader who only gets your first paragraph should already have the answer.

Cite inline as a markdown link — `[Author Year](https://doi.org/10.xxxx/xxxxxx)` — so the rendered prose reads `(Author Year)` and the DOI rides in the href where a reader can click it and a regex can still extract it. Prefer the published version of record's DOI over the arXiv id when both exist (that's what `resolve_published` is for); when a work is genuinely preprint-only, link its arXiv DOI and mark it a preprint. If the DOI itself contains parentheses (some publishers use PII-style suffixes, e.g. `Sxxxx-xxxx(NN)nnnnn-n`), URL-encode them as `%28` and `%29` in the href so the markdown link does not break in simpler renderers. Do not use numbered `[1][2][3]` references (they desync the moment a paragraph is reordered), and reserve the raw `(DOI: 10.xxxx/...)` form for plain-text-only output; a sentence whose visible text is half identifier is not referee-grade prose. The author names in the link text come from the retrieved record, never from recall — keep `authors` riding alongside year and DOI in whatever working notes you draft from (the lookup helpers return it for exactly this reason; only degraded fallback paths go without). A note that carries the DOI but not the names leaves `(Author Year)` to be filled from memory at prose time, and memory supplies plausible names, not the paper's. Section headings are short noun phrases (six words or fewer); when you have five or more topics, group them under two or three parent `##` headings and demote the rest to `###`. The goal is that a domain expert reading your review nods along, finds the papers they'd have named themselves, and doesn't catch you in a single claim you can't back.

## Style pass before saving

Before saving the file, run `style_pass(draft)` once on the full markdown. Fix the issues it lists in a single editing pass, then save; do not call it a second time and do not loop until it returns ok. It is a lint, not a gate, and a clean draft on the first pass is normal. It is shipped in this skill's `kernel.py`; load it the same way as the other helpers (import `kernel.py` by its path — see "Load the helpers") and call `style_pass` on the draft text.
