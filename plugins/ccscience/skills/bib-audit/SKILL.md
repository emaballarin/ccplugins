---
name: bib-audit
description: Audit an existing BibTeX bibliography end to end — verify every entry against Crossref, arXiv (via DataCite), DBLP, Semantic Scholar, OpenAlex, the NeurIPS/PMLR/JMLR proceedings indices, the ICLR/NeurIPS/ICML paper lists and OpenReview, correct wrong or fabricated metadata, replace arXiv preprints with their published version of record, merge duplicates, strip non-citation fields, rekey to `<Surname><Year><FirstContentWord>`, tidy and validate — then research only the entries no source settles. Use when asked to audit, check, clean or fix a `.bib` / references file, to upgrade arXiv citations to published versions, or to canonicalise citation keys (and migrate the `\cite{}` keys in `.tex` files). Writing a new literature review or finding papers to cite is `literature-review`.
license: Apache-2.0
metadata:
    # Sends each entry's title, first author and identifiers to Crossref (with a
    # polite-pool contact email from LITREVIEW_CONTACT_EMAIL when set), DataCite,
    # DBLP's SPARQL endpoint, Semantic Scholar, OpenAlex, the arXiv API and
    # OpenReview (each with the user's own key or sign-in when set); downloads the
    # public NeurIPS, PMLR and JMLR indices and the ICLR/NeurIPS/ICML paper lists.
    third_party:
        - kind: service
          name: Crossref
          info_url: https://www.crossref.org/documentation/retrieve-metadata/
          privacy_url: https://www.crossref.org/operations-and-sustainability/privacy/
        - kind: service
          name: DataCite
          info_url: https://support.datacite.org/docs/api
        - kind: service
          name: DBLP (SPARQL)
          info_url: https://sparql.dblp.org/
        - kind: service
          name: Semantic Scholar
          info_url: https://api.semanticscholar.org/api-docs/
        - kind: service
          name: OpenAlex
          info_url: https://docs.openalex.org/
        - kind: service
          name: arXiv
          info_url: https://info.arxiv.org/help/api/index.html
        - kind: service
          name: OpenReview
          info_url: https://docs.openreview.net/reference/api-v2
        - kind: service
          name: NeurIPS Proceedings
          info_url: https://papers.nips.cc/
        - kind: service
          name: PMLR
          info_url: https://proceedings.mlr.press/
        - kind: service
          name: JMLR
          info_url: https://jmlr.org/papers/
---

# Bibliography audit

The kernel does every mechanical part of the audit in one call and leaves a **review queue**: the few entries no source could settle. Your job is that queue — the bibliographic research the maintainer finds slow — and then a report. Trust the kernel's corrections; spend your effort on the queue and the soft matches.

## Load the kernel

`kernel.py` sits next to this file; import it by absolute path in a Bash `python` heredoc (zero import-time side effects, standard library only). Each `python` run is a fresh process, so re-import every time:

```bash
python3 - <<'PY'
import importlib.util, json
spec = importlib.util.spec_from_file_location("bibaudit", "/ABSOLUTE/PATH/TO/skills/bib-audit/kernel.py")
k = importlib.util.module_from_spec(spec); spec.loader.exec_module(k)
s = k.audit("paper/references.bib", tex=["paper/main.tex", "paper/appendix.tex"])
print(json.dumps({x: s[x] for x in ("entries_in", "entries_out", "status", "queue", "soft", "notices", "validation")}, indent=1, default=str))
PY
```

Needs `bibtex-tidy` on PATH (`npm i -g bibtex-tidy`); `bibtex` and `biber` enable validation and are reported as skipped when absent. Every credential is optional, read from the environment, and dropped with a note if refused — the source is then asked anonymously:

| variable                                      | effect                                                                                                                                                               |
| --------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `S2_API_KEY`                                  | Semantic Scholar at 1 request/s; without it Semantic Scholar is not asked (its keyless pool answers 429)                                                             |
| `OPENREVIEW_USERNAME` + `OPENREVIEW_PASSWORD` | OpenReview sign-in (searches go out signed in; the bulk ICLR 2018/2019 listing it would unlock is not built yet); `OPENREVIEW_TOKEN` instead for two-factor accounts |
| `OPENALEX_API_KEY`                            | OpenAlex's larger daily budget                                                                                                                                       |
| `LITREVIEW_CONTACT_EMAIL`                     | Crossref's polite pool (a real address)                                                                                                                              |

The summary's `credentials` and `credential_notes` say which were used and what happened to them.

## 1. Run the audit

Call `audit(bib, tex=[...])`, passing every `.tex` file that cites the bibliography when there are any. It writes in place and snapshots the original first:

- **With `.tex` files:** the `.bib` gets the canonical keys and each `.tex` has its `\cite{}` keys migrated (each keeps its original as `.orig.bak` and the version before the latest rewrite as `.prev.bak` — never more; a file whose migration would leave a previously defined key undefined is left untouched and listed under `tex.skipped`).
- **Without:** the `.bib` keeps its old keys, so the document still builds as is (a merged duplicate stays as an identical copy under its old key). Beside it: `<stem>.rekeyed.bib` with the canonical keys and `<stem>.keymap.tsv`; `rewrite_tex(tex_files, "<stem>.keymap.tsv")` migrates the `.tex` later.

A re-run looks up only entries that are new or edited since the last audit, so run it again freely after every change; an update to the audit's rules (`RULES_VERSION`) re-audits everything once. Keys, once assigned, stay put across runs even when a later correction changes the metadata they came from; `audit(..., rekey=True)` recomputes them all (and migrates the `.tex`). `audit(..., harmonise=True)` gives each person one spelling across the whole bibliography — the fuller form other entries use, when that is unambiguous; it goes beyond what each paper prints, so use it only when asked. A source that keeps failing is dropped for the rest of the run (`hosts_down`); the entries it would have settled come back `unchecked` and are retried by the next run. An entry that names a journal or proceedings no index confirms, while the work itself exists on arXiv, is kept as written and marked `unconfirmed`, with a notice. Validation compiles every entry with the BibTeX style the `.tex` files name in `\bibliographystyle` (plain without them); pass `style="plainnat"` (or a path to a `.bst`) to validate with another, e.g. for a biblatex document. The style used is `validation_style` in the summary. Done when the summary prints with no exception; read `status`, `queue`, `soft`, `notices` and `validation` from it.

## 2. Work the review queue

`findings.json` in the state directory (`summary["state"]`) holds each queued entry with its problem, the entry as it stands, and the nearest candidates. For every item, find what the entry really is — web search, the arXiv listing, the publisher's page, Google Scholar, alphaXiv — then record the answer with `resolve`:

| what you found                                              | call                                                                  |
| ----------------------------------------------------------- | --------------------------------------------------------------------- |
| the real work has a DOI                                     | `k.resolve(bib, key, doi="10.…", note="<where you found it>")`        |
| the real work is on arXiv                                   | `k.resolve(bib, key, arxiv="2301.12345", note=…)`                     |
| a real work no index holds (book, thesis, report, web page) | `k.resolve(bib, key, fields={"publisher": "…", "year": "…"}, note=…)` |
| the entry is right and simply unindexed                     | `k.resolve(bib, key, accept=True, note=…)`                            |

An identifier passed to `resolve` replaces the entry's title and authors with the real work's, so it also repairs an entry whose metadata was fabricated. When an entry has **no** real counterpart — a hallucinated reference, an irrecoverable fragment — stop and show the maintainer the entry and your evidence; `resolve(..., delete=True)` only on their word.

Then read `unconfirmed` (in `findings.json`): entries whose claimed journal or proceedings no index confirms — each notice names what the indices do hold (another edition, a reprint, a review, the arXiv version); correct a wrong claim with `resolve`. Read `name_conflicts`: authors whose bylines spell the given names incompatibly were left as they are, and names BibTeX misreads — usually a missing "and" (`Devries, Paul L. Hasburn, Javier E.` reads as one person with the suffix "Paul L. Hasburn"); both are listed on every run until resolved; decide from the papers and record it with `resolve(bib, key, fields={"author": "…"})`. Then glance down the `unverifiable` entries in `changes.md` — books, chapters, theses, reports and web pages no index holds — and spot-check any that looks unfamiliar; `resolve(..., accept=True)` records one you confirmed, so it is not raised again. Then check the `soft` list: each pairs the entry's title with the record it was matched to, and a wrong pairing is fixed with `resolve` and the right identifier. Look at `possible_duplicates` the same way.

Re-run `audit` to apply the answers. Done when the queue is empty, or every remaining item is with the maintainer together with its evidence.

## 3. Report

Lead with the headline counts (entries in → out, corrected, upgraded, merged, deleted, queued), then the items a human should see first: identity corrections (an entry that described another work), anything still with the maintainer, journal versions reported but not swapped in, and validation warnings. Give the paths — the `.bib` (and the rekeyed copy and key map, when there were no `.tex` files) and `changes.md` in the state directory, which carries the full per-field log with the source of every change.

## Policy

What the kernel does, so you can explain it and extend it without second-guessing it.

- **Identity.** A record matches strictly when the normalised titles agree (case, accents, LaTeX, math, punctuation, hyphens, articles and prepositions in five languages all ignored) and the first authors agree (particles, given/family swaps and missing accents tolerated). A **soft match** — a dropped subtitle, a typo or spelling variant, a year off by one, a shuffled author order — is applied and listed for a glance. An identifier (DOI, arXiv id) that resolves to a different work is an identity failure: the kernel searches by title for the real one and corrects the entry, or queues it. So is a journal slot (volume and first page, or JMLR paper number) that belongs to another work — the signature of fabricated metadata.
- **Version of record.** A preprint is replaced by the published version of the same work (conference, journal, or a Crossref preprint's `is-preprint-of` link). A later journal extension of a conference paper is a different work: reported in `notices`, never swapped in. Neither is a reprint in an edited volume, a later edition of a book, or a review, discussion, reply or erratum about it: a record of another kind, a title marking a piece about the work (Crossref's "[Title]: Comment"), or more than a year away without the same journal (or, for books, publisher), never replaces the entry. An entry that names a publication is never downgraded to its preprint. OpenReview counts as published only for an accepted paper's venue id; submissions under review, rejected and withdrawn papers stay preprints.
- **Preprint-only entries** are `@misc` with `eprint`, `archiveprefix = {arXiv}` and `primaryclass`. A version pinned in the entry (`2301.12345v2`) is cited exactly. Otherwise the metadata is the latest version's and the year that of first submission — unless title or authors changed across versions, when the year is that of the first version carrying the final title and authors. Preprints are re-checked for publication after 30 days (`preprint_ttl_days`).
- **Venues** come from `references/venues.tsv`: the publication's own series name with edition and year removed (`Advances in Neural Information Processing Systems`), or `Proceedings of the <conference>` where the publication has no series name of its own. `year` is the conference's year; no edition number is stored. Journals take their current name from one authority: the container title Crossref's latest articles of the journal carry (by the entry's ISSN, else by the ISSN OpenAlex finds for the name), with `references/journals.tsv` only where Crossref knows nothing. The publisher's current styling is accepted wholesale ("PLOS One", "Journal of Neuroscience"), for one consistent name per journal; a journal renamed since the article appeared keeps the name it appeared under ("The Bulletin of Mathematical Biophysics", not "Bulletin of Mathematical Biology"). The journal-level titles of Crossref and OpenAlex are catalogue forms ("Physical review. E", colons dropped) and are never used. A journal whose authority was unreachable keeps its name and the entry is re-audited next run. Add a venue by adding a row there.
- **Stripped:** DOIs, abstracts, keywords, tool bookkeeping (`biburl`, `timestamp`, `file`, …) and URLs — except where the entry _is_ a website, repository or piece of software, whose URL is the citation. `publisher` goes from `@article` (invalid in biblatex's data model).
- **Deleted:** duplicates (merged losslessly: the better-verified entry survives, a field only a duplicate has is carried over) and garbage — entries with no title and no author, placeholder titles, unparseable fragments. The raw text of every deletion is kept in `changes.md`. A plausible entry no source knows is never garbage; it goes to the queue.
- **Keys:** `<Surname><Year><FirstContentWord>`, PascalCase, ASCII: particles joined (`VonNeumann`), accents folded (`Buzsaki`), stopwords in five languages, numbers and math skipped, hyphenated words joined (`FashionMNIST`), corporate authors condensed (`TorchVision`). A collision takes the venue acronym, then a letter.
- **Formatting:** the house `bibtex-tidy` command (`TIDY_ARGS`), after which values it wrongly title-cases (`PLOS ONE` → `Plos One`) are restored and any other value it changed is listed under `drift`. A `\url{}` containing a character it would escape moves to `url`.
- **State** lives in `<repo>/.ccsci/bibaudit/<bib path>/`: `cache.json` (every settled entry, keyed by a hash of its citation content — and the only place the stripped DOIs survive), `overrides.json` (your `resolve` answers), `findings.json`, `keys.json` (the keys assigned so far), `changes.md` (one dated section per run), `orig.bib` (the bibliography as first seen) and `prev.bib` (as it was before the latest run). Upstream data is cached machine-wide under `~/.cache/ccsci/bibaudit/`, pruned to 180 days since last use and 200 MB (`BIBAUDIT_CACHE_MAX_AGE_DAYS`, `BIBAUDIT_CACHE_MAX_MB`).
- **Names** are completed to the fullest form the paper's own byline spells — Crossref's publisher metadata, the arXiv submission, the proceedings' listings, OpenAlex's as-printed names — completing only initials, abbreviations and accents: "G." → "Giovanni", "JF" → "John F.", "Buzsaki" → "Buzsáki". Two written given names are two names ("Ben" and "Benedict" never merge): the published byline's is kept and the disagreement listed in `name_conflicts`. Registries and profiles (OpenAlex's person names, DBLP, Semantic Scholar, OpenReview) never complete or rewrite a name; they only repair a missing or truncated author list. Authors are never reordered. Titles the audit writes have acronyms and inner capitals braced (`{LLMs}`, `{U-Net}`) so styles do not lowercase them.
- **Sources** were chosen by probing, 2026-09-27. DBLP issues no API keys and answers scripted clients with a bot-check page, but its SPARQL endpoint is open, so DBLP is read there (title search: venue, year, pages, DOI, authors in order). Semantic Scholar refuses unauthenticated batch requests (HTTP 429 on the first call), so it is asked only with `S2_API_KEY`; its record of a preprint then names the published version in one batched call. OpenAlex supplies byline names, a journal's ISSN when the entry has none, and which work sits at a journal's volume and first page, for the slot check. OpenReview mirrors DBLP records too, but its search allows 20 requests a minute (5 on the older API, asked only about work from 2019 or earlier) and its bulk listings demand a bot challenge; accepted ICLR papers (from 2020) and the NeurIPS/ICML years not yet in their proceedings come instead from each conference site's own paper list, one download per year. Where no index covers the venue-year the authors name in their arXiv comment (ICLR 2015, say), that statement upgrades the entry as a soft match. The arXiv API throttles under sustained use (429/503, each answered only after 30–60 s), so arXiv metadata — latest version, comment, published DOI, category — comes from DataCite, which registers every arXiv DOI and answers 25 ids per request in well under a second; the arXiv API is asked only for a pinned version or a version history. Re-probe before changing any of this.
