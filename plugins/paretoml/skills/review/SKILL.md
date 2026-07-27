---
name: review
description: 'Adversarially review a proposed or applied efficiency change to a training/evaluation pipeline: did the claimed mechanism actually engage, is the measurement still valid, what did it silently break. Use for `/parml:review`, "I made this training faster, check it", "review this diff before I merge it", "why did throughput improve but accuracy drop", "did this speedup actually work", or on any diff touching a training loop, data pipeline, optimiser, precision, or evaluation path. Walks a pitfall catalogue — score inflation, dead knobs, the throughput fallacy, optimisations that never engaged, stale step-unit hyperparameters, train/eval mismatch, leakage. Read-only; verdicts, not edits. Do NOT use to find new opportunities (that is /parml:audit) or for general code review of non-ML code (that is /code-review).'
allowed-tools: [Read, Glob, Grep, Bash]
license: MIT
---

# /parml:review — did it work, and what did it cost

A speedup that reports success while doing damage is the default failure mode of
this whole area. So this skill tries to **falsify** the claim rather than confirm
it — and reports plainly when it cannot.

Adversarial is not the same as pessimistic. A change that survives every check is
a real outcome and the correct answer is a clean `confirmed`. Manufacturing a
concern to look thorough is worse than not reviewing at all: it costs the
operator's attention, and it teaches them to discount the next review.

Read-only. It produces a verdict and the specific check that would settle any
open question. It does not edit and it does not run training.

## First action, always

Get the diff and the claim:

```bash
git diff --stat HEAD 2>/dev/null || git status --short
```

Then ask, if not already stated: **what was this change supposed to buy, and how
was that measured?** A review with no claim to test is an audit — redirect to
`/parml:audit`. Read `./.parml/frontier.md` if it exists; a change outside the
recorded plan is itself a finding.

## Hard rules

1. **Read-only.** No edits, no commits, no training runs. Short read-only probes
   are fine.
2. **Test the claim, not the code's plausibility.** "This looks correct" is not a
   verdict. Every conclusion names the check that produced it.
3. **A throughput number is never accepted as evidence** (`pitfalls.md` P3). Ask
   for time-to-target, or for both factors of
   `steps-to-target × time-per-step`. If only throughput exists, the verdict is
   `unproven`, however large the number.
4. **Verify the mechanism engaged** (P5). Separately from whether the number
   moved. These fail independently, and a change whose number improved for an
   unrelated reason is the worst outcome available — it will be built on.
5. **Classify the blast radius from the diff, not from the claim.** If it is
   `distribution`, mean quality alone is not a verification (P6).
6. **Any diff touching the harness, evaluator, metric, split, or evaluation
   frequency ends the comparison** (P1). This is not negotiable and is not a
   matter of intent — say so and require a fresh baseline.
7. **Report what you could not check**, and what would settle it. An unverifiable
   claim is `unproven`, not `confirmed`.
8. **An all-clear is a legitimate result.** If the mechanism engaged, the pricing
   is in time-to-target, the radius was verified appropriately and no pitfall
   fired, say so in one line and stop. Do not pad a clean review with speculative
   concerns, do not downgrade `confirmed` to `unproven` for atmosphere, and do
   not list checks that passed as though they were findings. Report which checks
   ran, that they passed, and what remains untested — that is the whole output.

## The verdicts

| Verdict               | Means                                                                                                                                                                           |
| --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `confirmed`           | Mechanism engaged, priced in time-to-target, radius verified appropriately, exposure checked against §2, no pitfall fired. **A legitimate, expected outcome — do not hedge it** |
| `unproven`            | Plausible and un-refuted, but the evidence does not support the claim yet. Names the missing measurement                                                                        |
| `regressed`           | Something got worse — the other factor, a constraint, or a quality dimension not in the headline                                                                                |
| `measurement-invalid` | The comparison cannot support any verdict: harness moved, `n = 1`, timing boundary wrong, seed not wired                                                                        |

`unproven` is the most common honest verdict on a first pass and should not be
softened into `confirmed`. The converse is equally binding: `confirmed` with an
empty concern list is a real and expected outcome, and must not be hedged into
`unproven` because a clean review feels insufficiently diligent. Both directions
of pressure exist; resist both.

## Steps

1. **Read the diff and state the claim** — what was bought, in what currency,
   measured how, against what baseline, at what `n`.
2. **Classify radius and exposure separately** (`evidence-grades.md` §3), both
   from the diff itself rather than from the claim. **Radius** sets the
   verification method: `none` → equality; `numeric` → metric across `n` runs
   plus the tails; `distribution` → every exposed dimension. **Exposure** sets
   what must have been checked: which quality dimensions this could have cost,
   and whether any of them is a hard non-negotiable in `frontier.md` §2. The two
   do not imply each other — a `numeric` change can spend real accuracy and a
   `distribution` change can be quality-neutral.
3. **Verify the mechanism engaged.** The compiled region did not break or
   recompile per step; the fused path was selected; the frozen prefix has zero
   gradient-enabled parameters; the cached artifact was actually rebuilt; the
   device-resident tensor is not being copied back. Each has a direct check —
   `pitfalls.md` P5.
4. **Walk the standing five** against every diff: **P1** score inflation, **P3**
   throughput fallacy, **P5** mechanism, **P6** mean-only verification, **P13**
   timing boundary. These are where a change _appears_ to have worked.
5. **Walk the diff-triggered rest**, using the trigger table below.
6. **Check the other factor.** A Tier-B change that improved `time-per-step` must
   be shown not to have worsened `steps-to-target`, and vice versa. This is the
   single check that catches the most damage.
7. **Verdict, with the settling check.** Then, if `frontier.md` exists, state
   whether the recorded revert trigger has fired.

## Trigger table

| The diff touches…                         | Also check                                                                                      |
| ----------------------------------------- | ----------------------------------------------------------------------------------------------- |
| Schedule length, batch size, device count | **P4** stale step-unit hyperparameters — the highest-yield check in this table                  |
| Precision, dtype, memory layout           | **P10** precision degradation; **P7** eval-path precision                                       |
| Optimiser construction, parameter groups  | **P9** partition fallthrough; **P8** schedules outliving their parameter                        |
| A compiler, fusion, or a custom kernel    | **P5** mechanism; **P14** determinism now lost                                                  |
| Data loading, caching, preprocessing      | **P12** stale cache; **P11** leakage; **P15** data-order coupling                               |
| Augmentation, selection, curriculum       | **P6** mean-only verification; **P11** leakage; **P15** coupling; **P7** eval-path augmentation |
| Evaluation path, TTA, gating, thresholds  | **P1** score inflation; **P11** threshold tuned on the reported split; **P6** calibration       |
| An inherited or swept configuration       | **P2** dead knobs — set each to two extremes and confirm the output moves                       |
| Freezing, thawing, staged training        | **P8** schedule past the freeze; **P5** did the backward actually shorten                       |
| Nothing but numbers in a config file      | **P2**, **P4**. A config-only diff is not automatically low-risk                                |

## Read on demand

| Need                                         | File                                                     |
| -------------------------------------------- | -------------------------------------------------------- |
| The full pitfall catalogue                   | `${CLAUDE_PLUGIN_ROOT}/references/pitfalls.md`           |
| Radius, grades, the two-factor decomposition | `${CLAUDE_PLUGIN_ROOT}/references/evidence-grades.md`    |
| Whether a measurement is admissible          | `${CLAUDE_PLUGIN_ROOT}/references/tier-c-protocol.md`    |
| What the change was supposed to do           | `${CLAUDE_PLUGIN_ROOT}/references/tier-a-algorithmic.md` |
|                                              | `${CLAUDE_PLUGIN_ROOT}/references/tier-b-systems.md`     |
| Whether a machine-bound number is portable   | `${CLAUDE_PLUGIN_ROOT}/references/hardware-notes.md`     |

## Completion status

End with a terminal status token as the last line of your reply.

- **DONE** — verdict issued per change, with the check behind each one.
- **DONE_WITH_CONCERNS** — verdict issued, but something could not be checked
  without running the pipeline. Name it and name the settling measurement.
- **BLOCKED** — no diff and no claim could be obtained.
- **NEEDS_CONTEXT** — the claim, the baseline, or the `n` behind the reported
  numbers is missing, and no verdict is possible without it.
