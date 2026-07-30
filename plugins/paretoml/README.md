# parml

> [!WARNING]
> **Superseded by [`tml` (tuneml)](../tuneml/README.md) as of 0.1.1.** Everything
> below is carried forward there, alongside the experimental-method material this
> plugin never covered. Install `tml@ccplugins` and use `/tml:audit`, `/tml:plan`
> and `/tml:review`. No migration is needed — the two never shared state.

**paretoml** — a read-first advisor for the speed↔quality frontier of a training
and evaluation pipeline.

The point of a frontier is that off-frontier configurations are strictly
wasteful, and that _on_ the frontier there is no free choice left — only a
decision about what to spend. This plugin finds the wasteful part, prices it
honestly, and makes the decision explicit instead of accidental.

It is not a max-throughput chaser. Its most useful output is sometimes
_do not do this_.

Modality-agnostic: vision, text, audio, tabular, graphs, time-series.

## Install

```
/plugin marketplace add emaballarin/ccplugins
/plugin install parml@ccplugins
```

## Skills

| Skill           | When                             | What it does                                                                                                                                                                      |
| --------------- | -------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `/parml:audit`  | To find out what is on the table | Reads the pipeline and emits ranked, **evidence-graded**, **priced** findings across the algorithmic (A), systems (B) and protocol (C) tiers. Writes `./.parml/findings.md`.      |
| `/parml:plan`   | To decide                        | Fixes the objective as a constrained optimisation, names what may not move, orders the changes with gates and revert triggers, writes a stop rule. Writes `./.parml/frontier.md`. |
| `/parml:review` | Before merging a change          | Adversarial: did the mechanism engage, is the measurement still valid, what broke silently. Read-only verdicts.                                                                   |

## The two ideas everything else hangs off

**1. The only currency is time-to-target-quality.**

```
time-to-target  =  steps-to-target  ×  time-per-step
                   └─ Tier A ─┘         └─ Tier B ─┘
```

Tier C decides whether _target_ still means what it meant, and whether either
delta is believable. Every finding states which factor it moves **and whether it
moves the other adversely** — because a change that improves throughput 30 % and
loss-per-step 40 % is a regression that every dashboard reports as a win.

**2. Every claim carries a grade.**

`measured-here` › `measured-elsewhere` › `mechanism` › `analogy` › `folklore`

with two hard rules: `analogy` and `folklore` **never outrank** `mechanism` or
above, whatever effect size they claim; and nothing below `mechanism` is banked
without being measured on your pipeline first. A number measured on 50k small
images at n=400 is not evidence about a 7B-parameter language model, and this
plugin will not let itself pretend otherwise. `folklore` is an available,
respectable answer — an ungraded claim is not.

**…and every change is costed on three independent axes.**

| Axis                                                    | Question                                           | Kind                              |
| ------------------------------------------------------- | -------------------------------------------------- | --------------------------------- |
| **Radius** — `none`/`numeric`/`distribution`            | What changed about the computation?                | Mechanical. Sets _how_ to verify. |
| **Exposure** — `neutral`/`bounded`/`spending`/`unknown` | What quality could this cost, on which dimensions? | Policy. A **veto**, not a weight. |
| **Engineering** — effort · revert · legibility          | What does it cost to build, undo, and live with?   | Human. Compounds.                 |

None of the three predicts the others, and collapsing them is how this kind of
advice becomes useless. A `distribution`-radius change can be quality-_positive_
(a derandomised augmentation rewrites the training distribution and improves
quality); a merely `numeric` one can spend real accuracy (normalisation
statistics in half precision). **Radius tells you how to verify. Exposure tells
you whether you are allowed to** — an `unknown` or `spending` exposure against a
_hard_ non-negotiable stops the change regardless of its effect size. No amount
of speed buys a violated constraint.

## A worked shape

```
/parml:audit
```

Reads the pipeline, classifies the modality and the machine, asks whether a noise
floor exists, offers the one-substitution probe that separates input cost from
compute, then walks the tiers in scope. Output defaults to around seven ranked
findings — as many as the pipeline warrants, split into _act now_ and _next pass_
rather than dumped flat — each with a grade, the factor it moves, all three cost
axes, the measurement that would confirm it, and its attached pitfalls. Plus an
unranked _hypotheses_ block and a mandatory _not recommended_ section.

```
/parml:plan
```

Asks the one question the agent cannot answer: which of four objective forms
applies, what the quality floor is, and what may not move — each constraint
marked _hard_ or _soft_. Adjudicates every candidate's exposure against the hard
ones before ordering anything, then sequences what survives cheap-and-certain
first, gates every step, and writes a stop rule _before_ starting. It **offers**
the `/ar:start` handoff with its cost stated — a dedicated branch, a commit, a
frozen harness — and waits for an explicit yes; it never invokes it. And it says
so when the right answer is to change nothing.

```
/parml:review
```

Tries to falsify the claim rather than confirm it — and reports plainly when it
cannot. Five checks run against every diff — score inflation, the throughput
fallacy, whether the mechanism actually engaged, mean-only verification of a
distribution-level change, and the timing boundary — then a trigger table for the
rest. Verdicts are `confirmed`, `unproven`, `regressed`, or
`measurement-invalid`. Adversarial is not pessimistic: `unproven` is the most
common honest first-pass answer and is not softened into `confirmed`, and a clean
`confirmed` is a real outcome that is not hedged into `unproven` for atmosphere.
Manufacturing a concern to look thorough is worse than not reviewing at all.

## Design notes

**Read-first, and it stays that way.** `audit` writes one file, `plan` writes one
file, `review` writes none. Nothing edits project code, nothing launches
training, nothing global is touched. Long jobs get exact commands printed for the
operator to run.

**Profile before you prioritise — a gate on ranking, not on thinking.** A
finding whose mechanism is visible in the source is `mechanism`-grade _that it is
happening_ and `analogy`-grade _on how much it costs_; both get labelled. What a
profile buys is **ordering and size**, which is exactly what optimisation effort
is usually wasted on. Without one, the audit says once and clearly that its
Tier-B ranking is a prior, and ranks by a prior-strength table
(`tier-b-systems.md` §B1.1) that separates "the symptom _is_ the cost" from
"profile first". No prior ever licenses a magnitude claim.

**Hardware specifics are quarantined.** `references/hardware-notes.md` contains
almost no numbers — it is a set of probes to run plus the invariants that survive
hardware generations. This is the file where an agent hallucinates most
confidently, so it is written to make recall structurally unnecessary.

**Tiers are references, not skills.** They are read separately, scoped
individually (`/parml:audit tier B`), and their intersections are named
explicitly — A∩B changes are priced end to end, A∩C asks whether the target
survived, B∩C asks whether the instrument did.

**Speed is not always the objective.** `references/tier-c-protocol.md` §6
enumerates nine cases where it is the wrong one — the deliverable is a
conclusion rather than a model; the claim needs the standard recipe; quality is
not one number; determinism is a requirement; the human iteration cost dominates;
the job runs once so every one-time cost is a loss. An audit that never declines
anything has not been run honestly.

**It composes with the rest of the marketplace.** `parml` advises → `ar` runs the
measured loop under a locked harness → `mf` remembers the decision. The protocol
tier deliberately shares `ar`'s vocabulary — noise floor, keep threshold, locked
harness — so a `/parml:plan` handoff into `/ar:start` needs no translation.

## Scope

**In scope.** The efficiency↔quality frontier of a training and evaluation
pipeline: optimisation and initialisation, augmentation and data streams, the
input pipeline, precision and layout, compilation, evaluation cost, and the
architecture choices that are primarily _cost levers_ (shape and alignment,
redundant parameters, reduction placement, cheaper operator substitutions).

**Adjacent, admissible as the plugin grows.** Architecture selection proper, data
curation strategy, and multi-device topology beyond the decision rules already in
`tier-b-systems.md` B13 — all close in spirit, and each would arrive with its own
graded catalogue rather than as loose advice.

**Out of scope.** Serving and inference deployment, preference-optimisation
pipelines, edge compression, and MLOps. Each is a different literature with
different failure modes; folding them in here would buy surface area and lose the
evidence discipline that makes the rest of it worth reading.

## Attribution

The tier catalogues are original prose; where an entry is graded
`measured-elsewhere`, its measurement is cited. Two MIT-licensed pipelines
supplied most of those citations — see [`NOTICE`](NOTICE). Two corrections to
those sources are carried here as original, numerically re-derived findings: the
Nesterov step-amplification constant, and an inert magnitude schedule in a
machine-tuned optimiser.

MIT — see [`LICENSE`](LICENSE).

## Links

- Marketplace: [emaballarin/ccplugins](https://github.com/emaballarin/ccplugins)
- Changelog: [CHANGELOG.md](CHANGELOG.md)
