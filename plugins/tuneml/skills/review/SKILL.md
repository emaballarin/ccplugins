---
name: review
description: 'Adversarially review a proposed or applied change to a training/evaluation pipeline: did the claimed mechanism actually engage, is the measurement still valid, what did it silently break. Use for `/tml:review`, "I made training faster, check it", "review this diff before I merge", "why did throughput improve but accuracy drop", "did this speedup actually work", "check my optimiser swap", or on any diff touching a training loop, data pipeline, optimiser, precision, architecture or evaluation path. Walks a pitfall catalogue — score inflation, dead knobs, the throughput fallacy, changes that never engaged, stale step-unit hyperparameters, train/eval mismatch, leakage, beta-convention errors across optimisers. Read-only; verdicts, not edits. Do NOT use to find new opportunities (that is /tml:audit), to interpret a sweep (that is /tml:analyze), or for general code review of non-ML code (that is /code-review).'
allowed-tools: [Read, Glob, Grep, Bash]
license: MIT
---

# /tml:review — did it work, and what did it cost

Adversarial by construction. The default posture is that the change **did not do
what it claims**, and the review's job is to find out whether that default
survives contact with the diff.

## Hard rules

1. **Read-only.** No edits, no writes, not even to `./.tml/`. Verdicts only.
2. **Three questions, always, in order**: did the mechanism engage, is the
   measurement still valid, what did it silently break.
3. **"Improved throughput" is not an answer** to any of them.
4. **A verdict without a check behind it is an opinion.** Name the file, the
   line, the trace, or the number.

## Procedure

### 1. What is claimed, and what would falsify it

State the claim in one sentence, then its **radius**
(`references/evidence-grades.md` §3.1) read mechanically off the diff, then what
observation would show it false. If nothing would, say so — an unfalsifiable
claim is the finding.

### 2. Did the mechanism engage

The most common failure is a change that is present in the source and inert at
runtime:

- A flag set after the object it configures was constructed.
- A fast path guarded by a condition that never holds — dtype, shape, contiguity,
  device, or a version check.
- A compiled path recompiling every step (count the recompilations; a
  recompilation per step is worse than no compilation).
- A kernel that silently fell back because its workspace did not fit — which is
  also why an interior batch-size optimum can appear (`tier-b-systems.md` B14).
- An optimiser change where the **beta convention differs between algorithms**:
  Adan's `β₂` is not Adam's `β₂`, Adan's `β₃` is, RMSProp's `alpha` is, and
  PyTorch's SGD `momentum` decays a _sum_ rather than an average
  (`references/optimisers.md` §1). A ported beta value is a silent
  learning-rate change. Check this whenever an optimiser was swapped or its
  hyperparameters were copied from elsewhere.
- Weight decay carried across an `Adam → AdamW` boundary unchanged — different
  hyperparameter, different scale (`optimisers.md` §2).

### 3. Is the measurement still valid

`references/tier-c-protocol.md` and `references/pitfalls.md`:

- **Score inflation** — did the change alter what is being measured, not just how
  fast it is computed? Evaluation set, metric definition, checkpoint selection
  rule, or the harness itself.
- **Stale step-unit hyperparameters** — anything expressed in steps (schedules,
  warmup, decay length, EMA horizons, eval cadence) after a batch-size or
  throughput change. `references/optimisers.md` §1.3: a horizon fixed in steps
  shrinks in examples when the batch grows.
- **Timing boundary** — is evaluation inside or outside the clock? Warmup
  amortised or included? One-time costs priced at the real `k`?
- **Baseline drift** — is the comparison still against the same baseline, run on
  the same harness, on the same hardware?

### 4. What did it silently break

- **Quality dimensions other than the mean** — calibration, worst-group, tails,
  robustness under shift, determinism. A mean that held while calibration moved
  is a real regression and a common one.
- **Train/eval mismatch** — a transform, a precision, or a normalisation applied
  on one path and not the other.
- **Leakage** — validation data touching training, directly or through
  statistics.
- **Numerics** — reductions moved to lower precision; fp16 without loss scaling
  where it is needed; catastrophic cancellation in a difference of near-equal
  quantities (`optimisers.md` §3.1 for the Adan case in bf16).
- **Legibility** — the axis nobody records. A pipeline only one person can now
  modify is frequently a net loss (`tier-c-protocol.md`).

### 5. Verdict

One of:

- **holds** — mechanism engaged, measurement valid, no unpriced breakage. Say
  what evidence supports each of the three.
- **holds with caveats** — plus the specific caveats.
- **does not hold** — with the specific reason and the check that shows it.
- **cannot determine** — with the specific missing measurement, and what to run.

Then the residue: what remains unverified and would need a measurement to close.

## Handoffs

- The change is fine but the sweep behind it is questionable → **`/tml:analyze`**.
- The review found instability rather than a bad change →
  **`references/instability.md`**.

## Completion status

`DONE` (all three questions answered with evidence), `DONE_WITH_CONCERNS`,
`BLOCKED`, or `NEEDS_CONTEXT`.
