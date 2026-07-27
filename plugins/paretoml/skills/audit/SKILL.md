---
name: audit
description: 'Read a training/evaluation pipeline and emit ranked, evidence-graded, priced findings on its speed↔quality frontier — across the algorithmic (A), systems (B), and protocol (C) tiers. Use for `/parml:audit`, "why is my training slow", "how do I speed up this training without losing accuracy", "review my training loop for efficiency", "what am I leaving on the table here", "is my pipeline input-bound", or before committing to a round of optimisation. Modality-agnostic — vision, text, audio, tabular, graph, time-series. Prices everything in time-to-target-quality, never throughput. Read-first: writes only ./.parml/findings.md and never edits project code. Do NOT use for a one-line "make this loop faster" on non-ML code, for model-quality debugging with no efficiency question, or to run training.'
allowed-tools: [Read, Write, Glob, Grep, Bash]
license: MIT
---

# /parml:audit — price the frontier

Produce a short, ranked, **graded** list of what this pipeline is leaving on the
table, what each item would cost to take, and what it would break. Auditing does
not change anything and does not decide anything — `/parml:plan` decides.

## First action, always

Establish what already exists before reading a line of model code:

```bash
ls -la ./.parml/ 2>/dev/null; git -C . log --oneline -3 2>/dev/null
```

If `findings.md` is already there, read it, say when it was written, and audit as
a **delta** against it — re-confirming what has changed, not re-deriving what has
not. An audit that silently re-proposes what was already rejected is noise.

## Hard rules

1. **Read-first.** Never edit project code. The only path written is
   `./.parml/findings.md`, and only after the findings are shown. No global or
   shared state is touched.
2. **Never launch training.** Print exact commands for anything longer than a
   few seconds and let the operator run it. Short read-only probes — a shape
   check, a version query, a profiler pass on a handful of steps — are fine, and
   should be confirmed before running if the machine is shared.
3. **Every finding carries a grade** from `references/evidence-grades.md`. An
   ungraded claim is not emitted. `folklore` is a respectable grade; silence
   about provenance is not.
4. **`analogy` and `folklore` never outrank `mechanism` or above**, whatever
   effect size they claim. They go in the Hypotheses block, unranked.
5. **Profile before you _prioritise_.** A Tier-B finding whose mechanism is
   visible in the code — a per-parameter Python loop, a synchronising read in the
   hot loop, per-epoch decoding — is `mechanism`-grade _on existence_ and
   `analogy` _on magnitude_: emit it, and label both. What a profile buys is the
   **ordering** and the size, so without one, say once and clearly that the
   Tier-B ranking is a prior rather than a measurement, and rank by
   `tier-b-systems.md` B1's prior-strength table. Probe P-1 in
   `references/hardware-notes.md` is one substitution and usually settles it —
   offer it before falling back to priors.
6. **Radius, exposure and engineering cost are three separate fields**
   (`references/evidence-grades.md` §3) and none predicts the others. Never let
   `distribution` radius stand in for "costs accuracy", or `numeric` for "safe".
   Every finding states all three, and names the quality _dimensions_ exposed.
7. **Exposure against a hard non-negotiable is a veto, not a weight.** If
   `./.parml/frontier.md` records a hard constraint the finding could violate, it
   goes to Not-recommended regardless of effect size. If no constraints are on
   record, say that the exposure column cannot yet be adjudicated.
8. **Price in time-to-target, never in throughput.** Every finding states which
   factor of `steps-to-target × time-per-step` it moves and whether it moves the
   other adversely. A throughput number is never a result (`pitfalls.md` P3).
9. **Consult the modality map before proposing a modality-shaped item.**
   Recommending a vision recipe for a text pipeline is the fastest way to be
   wrong and to be seen to be wrong.
10. **Rank ruthlessly; budget, do not truncate.** Around 7 findings is what an
    operator can act on in one pass, so that is the default — but a pipeline that
    genuinely warrants more gets more. When the list runs long, split it into
    _act now_ and _next pass_ rather than emitting one flat wall, and say why it
    is long. Never silently drop a finding to hit a number: what was cut, and on
    what basis, is stated either way.
11. **The Not-recommended section is not optional.** If nothing was declined, the
    audit almost certainly was not honest — say so explicitly rather than leaving
    the section empty.
12. **Numbers from the catalogues are `measured-elsewhere` on someone else's
    pipeline.** Quote them with their conditions or not at all. Never present a
    borrowed number as a prediction for this codebase.

## Steps

1. **Locate the pipeline.** Entrypoint, training loop, data path, optimiser
   construction site, evaluation path, config. Name the files; everything later
   cites `path:line`.
2. **Classify.** Modality, model family, parameter count and its composition
   (matrix vs vector vs embedding — this decides how much of A3/A4 is reachable),
   dataset size against device memory, precision, framework, and whether a
   compiler is in play. Get the machine from `hardware-notes.md` §1 — from the
   machine, not from a model name.
3. **Establish the operating point.** Current quality, current cost, and — the
   question that decides everything downstream — **is there a noise floor?** If
   not, say so plainly: without it every delta in this report is unfalsifiable
   and the plan must start by measuring it.
   Ask for `k`, the number of runs this will be amortised over. Do not assume it.
4. **Find the bottleneck** (`tier-b-systems.md` B1). Offer the probes; if they
   are declined or impossible, fall back to B1's prior-strength table and declare
   the Tier-B ordering a prior. Either way this is stated once, not repeated on
   every finding. See rule 5.
5. **Walk the tiers in scope.** Default is all three. A tier scope may be given
   (`/parml:audit tier B`, "just the protocol"). The tiers intersect — see
   `evidence-grades.md` §4 — so note any finding that lands in A∩B, A∩C or B∩C
   and price it end to end rather than on one factor.
6. **Grade, price, rank.** Expected value over engineering cost, after the two
   filters: `analogy`/`folklore` to Hypotheses, hard-constraint exposure to
   Not-recommended. Attach pitfalls per finding from `references/pitfalls.md`.
7. **Report.** Show the ranked table and the top findings in the chat. Offer to
   write `./.parml/findings.md` from `templates/findings.md`; write it on
   agreement. Findings are a dated snapshot of one machine and one commit —
   commit them only if the project wants that history; otherwise say so and let
   the operator gitignore `.parml/`. Suggest `/parml:plan` as the next step.

## Scoping the walk

| Signal from step 2–4                                        | Where to spend the audit                       |
| ----------------------------------------------------------- | ---------------------------------------------- |
| No noise floor exists                                       | Tier C first. Everything else is premature     |
| Input-bound                                                 | B2, B3 — usually one change, usually large     |
| Launch-bound, small model                                   | B4, B6, B9                                     |
| Compute-bound at near-peak                                  | Tier A, and shapes (B10). Not more Tier B      |
| Schedule was recently shortened or re-batched               | B11 and `pitfalls.md` P4, before anything else |
| Optimiser built as `Optimizer(model.parameters(), lr=…)`    | A3 — usually the cheapest real win present     |
| Config inherited from a sweep or another project            | `pitfalls.md` P2 and P4 — check for dead knobs |
| Evaluation inside the timed region, or never profiled       | B12 and `pitfalls.md` P1, P13                  |
| A quality constraint exists that is not the headline metric | Tier C C6.4 — this may end the audit           |

## Read on demand

Read a reference when the step that needs it is reached — not up front.

| Need                                                | File                                                     |
| --------------------------------------------------- | -------------------------------------------------------- |
| Grades, pricing, blast radius, the tier algebra     | `${CLAUDE_PLUGIN_ROOT}/references/evidence-grades.md`    |
| Fewer steps to target                               | `${CLAUDE_PLUGIN_ROOT}/references/tier-a-algorithmic.md` |
| Less wall-clock per step, and the profiling gate    | `${CLAUDE_PLUGIN_ROOT}/references/tier-b-systems.md`     |
| Objective, noise floor, when not to optimise        | `${CLAUDE_PLUGIN_ROOT}/references/tier-c-protocol.md`    |
| Whether an item has a form in this modality         | `${CLAUDE_PLUGIN_ROOT}/references/modality-map.md`       |
| Probes to run; how to report a machine-bound number | `${CLAUDE_PLUGIN_ROOT}/references/hardware-notes.md`     |
| What each finding can silently break                | `${CLAUDE_PLUGIN_ROOT}/references/pitfalls.md`           |
| Output shape                                        | `${CLAUDE_PLUGIN_ROOT}/templates/findings.md`            |

## Completion status

End with a terminal status token as the last line of your reply.

- **DONE** — findings ranked, graded and priced, with a bottleneck class backed
  by a probe.
- **DONE_WITH_CONCERNS** — findings produced, but something limits them: no noise
  floor, no profile, a machine that could not be characterised, or a quality
  constraint that may invalidate the whole direction. Name it.
- **BLOCKED** — the pipeline could not be located or read.
- **NEEDS_CONTEXT** — missing exactly one thing and it is load-bearing: the
  quality target, the value of `k`, or which constraints may not move.
