# Deliverables — constraints, block tables, checks

§4 of the skill: what each review-form field must satisfy, stated to the reviewer _before_ they draft it, and how each draft is checked afterwards. Word budgets assume a four-page workshop paper; scale them by 1.5–2× for a main-track submission and by the venue's own limits when it states them. Examples are synthetic.

## Order

summary → title → review → confidence → (confidential comment, only when the form has one and the reviewer asks). Each is drafted by the reviewer; Claude drafts on "draft it". The order matters: the summary fixes what the paper claims, the title fixes why the score is what it is, and the review then has both to anchor to.

## Summary — 2 to 4 sentences

- Describes the paper in its own framing: what it does, the main result as the authors claim it, the setting, and each experiment named with what it actually compares (which arms, which class). Taking no position.
- The reviewer's translation of the contribution ("this is ridge regression under another name") belongs in the review, not here. The summary is what the authors would recognise.
- Symbols only if the paper's; no new shorthand. Growth rates and bounds are stated in words when the box is plain text.
- A robustness check or an experiment that lives only in the appendix is mentioned factually, with its location; the judgement on that placement is review content.

Check: does every sentence describe something the paper says? Is every experiment named? Is any sentence a verdict?

## Title — one line

- The reason for the score, not the cost of reviewing. Shape: _[one credit], but [score-determining reason 1] and [score-determining reason 2]_.
- Strong reject: the flaw or the triviality. Weak reject: what is known plus what is missing. Weak accept: the contribution plus the one thing to fix. Strong accept: the contribution.
- "Hard to read" is a weak-accept headline; on a reject it invites "we will polish" and leaves chairs wondering why a presentation problem earned the score.
- Long is acceptable when every clause carries a reason; "proper" and "actual" are not clauses.

Check: could chairs reconstruct the score from the title alone? Does every clause name a reason?

## Review — block table by score band

Score-determining items come first, in their own paragraphs, and a reader who stops after them already knows why. Total 400–600 words; past roughly 700 a reject reads as uncertain or vindictive, and an accept as padding.

**Strong reject (flawed or trivial)**

| Block             | Words   | Content                                                                                                                  |
| ----------------- | ------- | ------------------------------------------------------------------------------------------------------------------------ |
| Strengths         | 60–80   | What is right: the question is real; the maths checks (say what was checked, in one sentence); negatives are reported.   |
| Score-determining | 200–250 | At most two items, one paragraph each, each with line reference + phrase + the one-sentence reason it is not a revision. |
| Secondary         | 60–100  | What would matter at a higher score: known results restated, expected findings, thin experiments.                        |
| Judgement         | 40–60   | The score; why neither score-determining item is a revision (the claim is not reached / the evidence is not reported).   |

**Weak reject (major revision)**

| Block                 | Words   | Content                                                                                                                                                                  |
| --------------------- | ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Strengths             | 70–100  | Honest logging, a clean reproduction, a good protocol — the things that survive revision.                                                                                |
| Score-determining (a) | 120–190 | The first reason, with the evidence the paper itself contains for it.                                                                                                    |
| Score-determining (b) | 100–160 | The second reason: the measurement that measures the wrong thing, the comparison announced and not reported.                                                             |
| Secondary             | 100–130 | Untested causal claims, confounds, an uninformative metric column, the missing baseline, the absent literature — each in one clause with a line reference.               |
| Judgement             | 50–80   | Both boundaries in two sentences ("nothing here is wrong; most of it is not new" / "fixable, but every fix is a new experiment"). Then: what the rework is built around. |

**Weak accept (minor revision)**

| Block            | Words   | Content                                                                                                                             |
| ---------------- | ------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| Strengths        | 100–150 | The contribution, stated precisely enough that the authors could quote it.                                                          |
| Required changes | 100–150 | Clarifications and presentation only. If a new experiment or proof appears here, the score is a weak reject and the review says so. |
| Optional         | 50–100  | What would strengthen a camera-ready version.                                                                                       |
| Judgement        | 40–60   | The score and the one thing that keeps it from a strong accept.                                                                     |

**Strong accept**

| Block     | Words   | Content                                               |
| --------- | ------- | ----------------------------------------------------- |
| Strengths | 150–200 | The contribution and why it is one; what was checked. |
| Minor     | 50–100  | Typos, a missing citation, a figure to relabel.       |
| Judgement | 30–50   | The score and, if any, the one reservation.           |

Between bands ("1.5"): use the lower band's table and say in the judgement which side of the line the paper sits on and why.

## Don't-address defaults

The list Claude gives the reviewer before the review is drafted, pruned or extended for the paper at hand:

- Presentation, typos, notation, structure — as a headline. A clause in the secondary block at most, unless the score is a weak accept.
- The stitching: the decomposition is the reviewer's working; the arc line is the deliverable.
- Re-deriving the authors' mathematics — one sentence naming what was checked.
- Private inferences (`inferred` anchors).
- The paper they could have written — one sentence in the judgement, as the reason the fix is a reframing and not a revision.
- Material the paper itself calls "not evidence" or "a pilot" — one clause; its self-scoping is a strength line, not a weakness.
- Related-work gaps beyond the ones that change the score.
- The format (a version log, an elaborate protocol) — neither mocked nor praised beyond the strengths line; it does not move the score.
- An AI-generation suspicion — confidential comment, when the form has one.
- Questions, when there is no rebuttal.

## Error-check protocol

Applied to every draft the reviewer pastes, and to Claude's own drafts when asked to draft:

1. **Substantive**, listed first: a claim the text does not support; a score-determining point missing; a fact wrong (a number, a section, an attribution, a name); two blocks contradicting each other ("well written" in strengths, "working notes" in comments); a question where a statement is needed; a design choice called a bug; an inference stated as a finding; an `unverified` item used without the reviewer's stated decision to keep it; a venue statistic (acceptance rate, score distribution) without its source.
2. **Wording**, listed second: broken LaTeX, tense, hedges that soften a finding, hyphenation, spelling (the reviewer's variety of English), a dangling clause, "proper"/"actual"/"simply".
3. Each item carries its fix. The revised block follows only when the reviewer asks ("output the updated version").
4. The **final pass** is errors only — "No gross mistakes. One word to fix: …" — and adds no new content. A judgement call that changes nothing factual is flagged as optional, in one line.

## Confidence

When the form's confidence scale is known, state it and let the reviewer pick; the level is theirs. When the reviewer has kept an `unverified` item in the review, name it here: the review rests on a check nobody made, and this is where the reviewer's confidence is honestly lower.

## Context dump block

On request, or whenever the conversation is about to be compacted, in this fixed shape so a later session resumes without re-deriving:

```
## State — DD/MM/YYYY, <venue>

Rubric: <scale, one line per band, or "unsourced">. Rebuttal: <yes/no>. Form: <fields>.
Scores: <paper A> N · <paper B> N · … (ordering, if calibrated across siblings)

<paper A> — DONE / IN PROGRESS (<which deliverable is next>).
Kept: <one line per fact the review rests on, each with its line reference and phrase>.
Unverified: <items, or "none">.

Format rules: summary <constraints>; title <shape>; review <band table>; don't: <list>.
```
