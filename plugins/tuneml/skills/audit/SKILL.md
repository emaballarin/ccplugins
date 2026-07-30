---
name: audit
description: 'Read a training/evaluation pipeline and emit ranked, evidence-graded, priced findings across the algorithmic (A), systems (B), protocol (C) and architecture (D) tiers. Use for `/tml:audit`, "why is my training slow", "how do I speed this up without losing accuracy", "review my training loop", "what am I leaving on the table", "is my pipeline input-bound", "is my eval setup sound", or before committing to a round of optimisation. Modality-agnostic — vision, text, audio, tabular, graph, time-series. Prices everything in time-to-target-quality, never throughput. Read-first: writes only ./.tml/findings.md and never edits project code. Do NOT use to design an experiment (that is /tml:round), to interpret results (that is /tml:analyze), or to run training.'
allowed-tools: [Read, Write, Glob, Grep, Bash]
license: MIT
---

# /tml:audit — what is this pipeline leaving on the table

Produce a short, ranked, **graded** list of what could be improved, what each item
would cost to take, and what it would silently break. Auditing changes nothing and
decides nothing — `/tml:plan` decides.

## First action, always

Establish what already exists before reading a line of model code:

```bash
ls -la ./.tml/ 2>/dev/null; git -C . log --oneline -3 2>/dev/null
```

If `findings.md` is already there, read it, say when it was written, and audit as
a **delta** — re-confirming what changed, not re-deriving what did not. An audit
that silently re-proposes what was already rejected is noise.

## Hard rules

1. **Read-first.** Never edit project code. The only path written is
   `./.tml/findings.md`, and only after the findings have been shown. No global
   or shared state is touched.
2. **Every finding carries a grade.** From the ladder in
   `references/evidence-grades.md` §1. An ungraded claim is not emitted;
   `folklore` is a respectable answer.
3. **Every finding is priced in time-to-target**, decomposed into
   `steps-to-target × time-per-step`, and states whether it moves the other
   factor adversely. Throughput is a diagnostic, never a result.
4. **Every tier-A/B/D item declares a quality exposure**, separately from its
   radius. Radius says how to verify; exposure says whether you are allowed to.
5. **Recommending nothing is a valid outcome.** A pipeline with no worthwhile
   changes should be told so, in one paragraph.

## Procedure

### 1. Scope, and the two questions that change the answer

Find the training entry point, the data path, the eval path, and the harness.
Then establish, by asking rather than inferring:

- **The target.** What quality, on what metric, measured how? Without it nothing
  can be priced, because "time-to-target" has no target.
- **The constraint.** Wall-clock, device-hours, memory, or deadline?

If the pipeline is already instrumented, read `references/regime.md` §1 and note
the parallelism regime — it changes what `/tml:plan` can propose next.

### 2. Read the pipeline against the catalogues

Load only the tiers the pipeline can actually exercise:

| Tier                                | Covers                                                 |
| ----------------------------------- | ------------------------------------------------------ |
| `references/tier-a-algorithmic.md`  | Fewer steps to target                                  |
| `references/tier-b-systems.md`      | Less wall-clock per step                               |
| `references/tier-c-protocol.md`     | Whether the measurement means anything                 |
| `references/tier-d-architecture.md` | The model and its arithmetic                           |
| `references/optimisers.md`          | Optimiser choice and its hyperparameters               |
| `references/modality-map.md`        | Per-modality instantiation of modality-sensitive items |

Two things to check that are not "opportunities" but defects, and which outrank
every optimisation in the list:

- **Optimisation failures** (`references/instability.md` §2). A workload whose
  learning-rate sweep tops out at an instability is reporting a ceiling, not an
  optimum, and every tuning conclusion under it is conditioned on the defect.
- **Evaluation validity** (`references/tier-c-protocol.md`). Periodic evaluation
  at regular **step** intervals rather than time intervals; eval batch at least
  as large as training's; partial batches correctly weighted (padded examples
  usually weight zero); retrospective checkpoint selection keeping the `n` best;
  enough saved per evaluation to support offline analysis. Periodicity in
  validation metrics on a shuffled split is a bug signature — usually
  train/test overlap or unshuffled data.

### 3. Grade honestly, then rank

Apply the degradation rule when porting a number across modality or scale. Rank
by expected time saved per unit of engineering cost, subject to:

- `analogy` and `folklore` items never outrank `mechanism` or above, whatever
  effect size they claim — they go in a separate **hypotheses** block.
- Cheap reverts first at equal expected value.
- A `spending` or `unknown` exposure against a stated hard constraint is a veto,
  not a weight.

### 4. Emit

Show the findings, then write `./.tml/findings.md` from
`templates/findings.md`. Lead with the ranked list; put the reasoning under it.

State explicitly if the ranking is a **prior rather than a measurement** — which
it is whenever no profile was available (`tier-b-systems.md` B1). And log
anything deliberately dropped: a truncated audit that does not say it truncated
reads as complete coverage.

## Handoffs

- Decide which findings to take, in what order → **`/tml:plan`**.
- The next question is an experiment rather than a change → **`/tml:round`**.
- A change has already been made and needs checking → **`/tml:review`**.

## Completion status

End with `DONE` (findings emitted, with the grade distribution stated),
`DONE_WITH_CONCERNS` (+ what could not be assessed and why), `BLOCKED` (+ the
blocker), or `NEEDS_CONTEXT` (+ exactly what is missing — usually the target
metric).
