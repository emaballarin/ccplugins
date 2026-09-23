---
name: paper-review
description: Human-driven peer review of a scientific manuscript with Claude as the second reader. Claude reads the whole paper at once, tests the reviewer's impression against the text, builds a line-anchored ledger of claims and gaps, calibrates the score against the rubric's boundaries, and constrains and error-checks the summary, title and review the reviewer writes. For conference, workshop and journal reviews once the PDF and the review form are in hand.
disable-model-invocation: true
license: Apache-2.0
---

# /ccsci:paper-review — second reader for a human-written review

The review is the reviewer's. What Claude adds is the one thing a sequential human reader does not have: the whole paper in view at once, so a claim in the abstract can be held against the table meant to support it, a disclaimer on one line against the hypothesis three lines above it, an announced four-way comparison against the numbers actually reported. The chief tools are recap tables, schematic decompositions, reminders of what is missing, and error checks on the reviewer's drafts. Prose for the review form comes from Claude only when the reviewer says "draft it".

Everything stays in the conversation. Files are written on request only (§5).

**Pacing.** The phases are turns, not one message. Stop after §0 for the PDF and the impression; after §3 for the score, because the block table of §4 depends on the band; and after each deliverable's constraints for the reviewer's draft. Run end to end, §0–§4 is five thousand words — right, and unreadable; paced, each turn is one thing the reviewer can act on.

## 0. Frame

Fix the frame before opening the PDF, because it decides the shape of every deliverable:

| Field                   | Why it matters                                                                                                                                                                                                                                                                                                                                                 |
| ----------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Venue and track         | Norms differ: a four-page workshop paper is not judged as a main-track submission.                                                                                                                                                                                                                                                                             |
| Rubric                  | The score scale _with its boundary definitions_. Ask the reviewer to paste the official text; when only the venue is named, search for its current reviewer guidelines and quote what is found, with the source. A rubric that cannot be sourced is labelled `unsourced` and stays labelled at every calibration step — an invented rubric calibrates nothing. |
| Rebuttal                | No rebuttal ⇒ a declarative review: every question becomes a statement of what the paper does not say.                                                                                                                                                                                                                                                         |
| Page limit and appendix | Decides whether appendix-only evidence counts toward a main-text claim.                                                                                                                                                                                                                                                                                        |
| Form fields             | Which boxes exist — summary, one-line title, strengths/weaknesses, questions, confidence, confidential comment — so nothing is written for a box that is not there.                                                                                                                                                                                            |
| Siblings                | Other papers in the same batch, for calibration on request (§3).                                                                                                                                                                                                                                                                                               |

Done when the frame is echoed back as a table with every field filled or marked `unknown — decide later`. Then ask for the PDF and the reviewer's **impression**: a few sentences on what the paper is, where it lands, and what they doubt. The impression comes before Claude's reading so the reading can be held against it rather than shaped by it.

## 1. Read, then test the impression

Read the whole paper — main text, appendix, references — before writing a word about it. A paper that fits one `Read` (≤ 20 pages) is read in full with `pages`; for a longer one, load `pdf-explore` so the pages persist. Keep the margin line numbers when the venue prints them; otherwise anchor by section and page.

Treat each sentence of the impression as a hypothesis and test it against the text. Report where Claude lands relative to the reviewer, in the reviewer's own units — "a notch below you", "half-agree: split the two claims" — with the passages that decide it. Agreement the text does not earn is worth nothing to the reviewer; a disagreement anchored to a line is what they asked for.

## 2. Decompose and stitch

Produce, in this order (templates and tag vocabulary in `references/anchors.md`):

1. **Arc** — one line stating what the paper does, in the plainest terms the text supports. When the paper never states its own arc, this line is the clarity evidence for the review: quote it there and let the gap speak.
2. **Claim ledger** — every claim in the abstract and the contributions list, with where it is stated, where it is evidenced, and a status: `evidenced` · `asserted` · `by construction` · `known from [source]` · `announced, not reported` · `confounded`. Check the mathematics claim by claim — each proposition against its proof, each constant against a recomputation — and record the outcome here; the review will cite it in one sentence.
3. **Anchors** — each finding as line reference + quoted phrase + reading + tag. The tag says what the reading rests on, and so where it may go: `stated` (the paper says it) and `derived` (follows from stated facts — the paper's, or a checked primary source's — with the derivation shown) may enter the review; `inferred` (explains the data but the paper never says it) stays in the notes; `unverified` (rests on an outside source not yet checked) stays out until the paragraph below lets it in.
4. **Missing** — terms undefined at first use; unstated protocol (seeds, hyperparameters, dataset composition, trivial baseline); announced-not-reported comparisons; absent literature.
5. **Decisive experiment** — the one experiment whose outcome settles the central claim, and what each outcome would mean.
6. **Oddities** — coincidences and internal inconsistencies worth a check: two unrelated numbers that agree exactly; a certificate the sample size cannot deliver; a metric column that never moves.

Literature enters the ledger only after its primary source has been checked — the abstract at minimum. A memory-matched attribution in a signed review is the reviewer's liability. When checking is impossible (offline, paywalled), tag the item `unverified`, list it under its own heading, and repeat that heading in every later recap. It leaves the heading only by being checked — then retagged `derived`, citing the source and how it was checked — or dropped. The reviewer may keep one in the review regardless, but only as a stated decision: until it is checked, dropped or explicitly kept, every error check flags it as substantive, and a kept item stays on the heading and is named in the confidence note.

Done when every abstract claim has a ledger row and every anchor carries a line reference _and_ a phrase. Extraction line numbers drift across tools and versions; the phrase is what finds the passage again.

## 3. Calibrate

Argue both boundaries of the score the reviewer leans toward — why not the band above, why not the band below — using the rubric's own boundary words as the test ("viable after major revision" against "fundamentally flawed or trivial"). A paper on a boundary is called so, with which way it leans and what would tip it. The reviewer sets the score.

Venue statistics — acceptance rates, score distributions — are not calibration inputs: the rubric's boundary words place this paper, and a rate says nothing about it. Claude never volunteers one. When the reviewer asks, the figure comes with its source and year, or not at all; a number recalled from memory is not stated, labelled or not.

On request only, calibrate across siblings: an ordering table with the largest gap named, so that three borderline scores are not filed for three papers that are not comparable.

## 4. Deliverables

Order: summary → title → review → confidence. A confidential comment to chairs only when the form has one and the reviewer asks; an AI-generation suspicion goes there, never into the review, where the content does the work.

For each deliverable, state its constraints (`references/deliverables.md`), then the reviewer drafts. Claude drafts on "draft it", in the block structure the constraints prescribe. Every draft gets an error check split into _substantive_ (a claim the text does not support, a score-determining point missing, a fact wrong, two blocks contradicting each other) and _wording_; the final pass is errors only.

For the review, the reviewer's draft is preceded by the block table — blocks, word budget, content of each — for the score band, and by the don't-address list for this paper. A reader who stops after the first two blocks already knows why the score is what it is.

## 5. Persist

On request only: a context dump in the fixed block of `references/deliverables.md` (rubric, scores, per-paper facts kept, format rules), so a later or compacted session resumes without re-deriving; or the notes exported to an A4 PDF for offline reading with `scripts/export_notes.py` (Markdown through `pandoc` or the `markdown` package; PDF through `wkhtmltopdf` or `weasyprint` — `uv run --with weasyprint` avoids installing it).

## Rules the corrections taught

Each was a correction made mid-review; the reason travels with it so it generalises.

- **Show derivations, keep inferences private.** A claim about the paper enters the review with its derivation from stated facts shown — "the window is 8 samples (l.23) and the stride is 8 (l.58), so consecutive windows never overlap and the 'context' the method sees is one window". An inference that explains the data but the paper never states (curves saturating at the same epoch in every run, consistent with a scheduler event) is the reviewer's private explanation: it shapes the questions and stays out of the review.
- **Credit the disclaimer, then locate the gap.** When the authors scope a claim themselves, say so, then place the gap _upstream_ or _downstream_ of their disclaimer. A gap upstream of a disclaimer is untouched by it; "the claim fails" alone invites the reply "we said so at line 40".
- **The summary describes the paper in its own framing.** The reviewer's translation of the contribution is review content; the summary says what the authors say they did, names each experiment and what it compares, and takes no position.
- **The title states the reason for the score.** "Hard to read and review" is the cost of reviewing and reads as a presentation complaint; "the central theorem's hypothesis is never established" is the reason. Presentation is a weak-accept headline, never a reject's.
- **Declarative when there is no rebuttal.** "Is the test set deduplicated against training?" becomes "the paper does not state whether the test set is deduplicated against training; as written, the reported gain is consistent with leakage."
- **Confirm the maths in one sentence** — say what was checked. Re-deriving it in the review spends words vindicating the paper.
- **Design choices are design choices.** Call something a bug only when the paper does; call an expected result expected; ask only for what the authors could have known.
- **The paper they could have written gets one sentence**, in the judgement, as the reason the fix is a reframing and not a revision.
- **A huge effect size on a by-construction comparison is not a strength.** It confirms determinism, not a finding.
- **Announced but not reported is a finding, not a question.** "Baseline D appears in no table" beats "was D evaluated?".
- **Nothing wrong and nothing new are separate verdicts.** State both; together they place a paper between the reject bands more precisely than either alone.

## Done when

- The frame table, the impression verdict, the arc, the ledger, the anchors and the missing list have all been shown, in that order, and each anchor has a line reference and a phrase.
- Every `unverified` item was checked, dropped, or kept by the reviewer's stated decision; a kept one is still listed at the last recap and named in the confidence note.
- Both boundaries of the score were argued and the reviewer set it.
- Summary, title and review each passed a final errors-only check, in that order.
