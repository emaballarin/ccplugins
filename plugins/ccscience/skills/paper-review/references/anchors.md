# Anchors — templates and tag vocabulary

The decomposition of §2 of the skill, one template per artefact, in the order they are produced. Every example below is synthetic: the form is what matters, and real submissions are confidential.

## Arc

One line. The plainest terms the text supports — the sentence the paper should have opened with. When the paper states it, quote it with its line. When it does not, write it and mark it:

> **Arc (not stated by the paper):** a Kalman filter whose transition matrix is learned by teacher forcing, evaluated on one synthetic system.

A paper whose arc has to be written by the reviewer has a clarity problem the review can state in one verifiable sentence, without adjectives.

## Claim ledger

One row per claim in the abstract and in the contributions list, in the order the paper makes them. Claims made only in the body may be added when they carry the score.

| #   | Claim (paraphrase, ≤ 15 words)                    | Stated at | Evidenced at   | Status                     | Note                                                                      |
| --- | ------------------------------------------------- | --------- | -------------- | -------------------------- | ------------------------------------------------------------------------- |
| 1   | The filter recovers the true transition matrix    | l.12–14   | Table 2, l.156 | `evidenced`                | one system, n = 1 seed                                                    |
| 2   | Training instability is caused by gradient bias   | l.37–39   | —              | `asserted`                 | "which we trace to" with no diagnostic shown                              |
| 3   | The proposed loss selects a different model       | l.77–80   | Fig. 1         | `by construction`          | two losses have two minimisers; a finding only once the gap is measured   |
| 4   | Prop. 1                                           | l.67–76   | App. A.1       | `known from [Author 1999]` | source abstract checked 23/09/2026                                        |
| 5   | Four-way comparison of A, B, C, D at matched size | l.132–133 | —              | `announced, not reported`  | D appears in no table; C only in App. B                                   |
| 6   | Doubling the data degrades the rare class         | l.44      | Table 1, row 9 | `confounded`               | data size and class rebalancing change together; steps vs epochs unstated |

Status vocabulary:

- `evidenced` — a reported result supports it at the stated configuration. Note the configuration and the seed count; "one condition, not a sweep" is a finding.
- `asserted` — stated, with no supporting result or derivation shown.
- `by construction` — true of the setup, not a finding. The tell is a claim that would hold for any data.
- `known from [source]` — in the literature, source checked (abstract at minimum). Write `known from [source] — unverified` when the check could not be made; see below.
- `announced, not reported` — the paper says it will show X and X appears in no table, figure or sentence.
- `confounded` — evidenced, but the comparison changes more than one thing at once.

The mathematics goes through the ledger too: a proposition is `evidenced` when its proof checks, `known from` when it is an identity in a cited paper, `asserted` when the proof is missing or the statement is broader than what is proved (a proposition worded for an algorithm's output when the proof is about the objective).

## Anchor table

Each finding the review might use. The phrase is verbatim, at most a dozen words, enough to find the passage again when line numbers have drifted.

| #   | Where         | Phrase (verbatim)                                   | Reading                                                                                                                                      | Tag          |
| --- | ------------- | --------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- | ------------ |
| 1   | l.26–27       | "chosen for its long-range context"                 | the only motivation given for the architecture; the task's dependence is local                                                               | `stated`     |
| 2   | l.23 + l.58   | "non-overlapping 8-sample windows" · "stride 8"     | windows never overlap, so the model's context is one window; the metric that compares adjacent windows measures an overlap that cannot exist | `derived`    |
| 3   | Table 1       | "0.31 · 0.31 · 0.30 · 0.31"                         | the loss column is flat while the error count moves 5×; a floor set by the loss definition — the paper never says                            | `inferred`   |
| 4   | l.40          | "we do not claim the result beyond bounded domains" | the authors' own disclaimer; the gap at #5 sits upstream of it                                                                               | `stated`     |
| 5   | l.36–39 vs §3 | "assume the worst-case error is below …"            | §3 bounds the average-case error; the hypothesis at l.36 needs the worst case; the first does not imply the second even on bounded domains   | `derived`    |
| 6   | l.107–117     | (reference list)                                    | the direct precedent for the architecture is absent; it is cited by the paper the authors reproduce                                          | `unverified` |

Where: `l.NN–MM` when the venue prints margin line numbers; else `§N p.N`.

Tag vocabulary — what the reading rests on, and therefore where it may go:

- `stated` — the paper says it. May enter the review with its line and phrase.
- `derived` — follows from stated facts, with the derivation shown. The facts are the paper's, or an outside source's once that source has been checked. Cites every fact it rests on (row 2 cites two lines). May enter the review with its derivation.
- `inferred` — explains the data, but the paper never says it. Never reaches the review; it lives here to guide what to ask for or look at.
- `unverified` — rests on an outside source (a precedent, an attribution, a prior result) not yet checked against its primary source. Never in Claude's drafts; flagged by every error check on the reviewer's. See _Unverified items_ for the three ways it is settled.

## Missing

Four headings; any may be empty, and an empty heading is stated as empty so its absence is not mistaken for an oversight.

- **Undefined at first use** — a symbol, acronym or term used before, or without, definition. Give the line of first use.
- **Unstated protocol** — seeds, hyperparameters, dataset composition (size, distribution, split), training density, stopping rule, the trivial baseline (always-predict-majority, copy-input). Each is a sentence the authors could add; each is also a reason a number cannot be interpreted.
- **Announced, not reported** — mirrors the ledger status; listed again here so it is not lost among the claims.
- **Absent literature** — the precedent or the identity the paper reinvents. Each entry carries `verified` (primary source checked, and how: abstract, full text, the paper's own references) or `unverified`.

## Unverified items

A separate heading, kept from the first recap to the last. An item leaves it only by being verified — then retagged `derived`, citing the source and how it was checked (abstract, full text, the paper's own references) — or dropped. The reviewer may keep one in the review regardless; that is their call, but it must be a stated decision, and a kept item stays under this heading and is named in the confidence note. Until an item is verified, dropped or explicitly kept, every error check on a draft that uses it flags it as substantive: an unchecked attribution in a signed review is the failure this heading exists to prevent. When the session is offline, say so once and keep the heading anyway.

## Decisive experiment

One paragraph. The single experiment whose outcome settles the central claim; then each outcome and what it would mean for the paper. Prefer an experiment the paper already half-contains (a model it trained but did not evaluate under the main protocol) over a new one — the burden of the missing comparison is then visibly the paper's.

## Oddities

Coincidences and internal inconsistencies to check, one line each, with a suggested cause when the numbers permit one:

- two unrelated results agreeing to the last digit (copy-paste, or both sitting on a trivial floor — compute the floor);
- a certificate whose sample size cannot deliver the stated confidence (recompute the zero-failure bound);
- a metric that changes definition between rows of one table (a value jumping an order of magnitude across a "bug fix").

An oddity is not a finding until the cause is established; it is a place to look.
