# tml

**tuneml** — a read-first advisor for training and evaluating neural networks
well.

Two things practitioners need that are usually kept apart: **how to run
experiments whose answers mean something**, and **where to sit on the
speed↔quality frontier**. Doing the second without the first gets you a fast
pipeline optimising a number you can no longer trust. Doing the first without the
second gets you a rigorous study you cannot afford to run.

It is not a max-throughput chaser and not an autotuner. Its most useful output is
sometimes _do not do this_, and its second most useful is _this comparison was
not fair_.

Modality-agnostic: vision, text, audio, tabular, graphs, time-series.

> **Replaces `parml` (paretoml)**, which was removed from this marketplace at
> its final 0.1.1 release. Its tier catalogues, evidence grades and templates are
> carried forward here unchanged in substance. No migration is needed — `parml`
> wrote to `./.parml/`, this writes to `./.tml/`, and the two never shared
> state; the `audit` / `plan` / `review` skill contracts are unchanged.

## Install

```
/plugin marketplace add emaballarin/ccplugins
/plugin install tml@ccplugins
```

## Skills

| Skill          | When                             | What it does                                                                                                                                                                                                |
| -------------- | -------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `/tml:audit`   | To find out what is on the table | Reads the pipeline and emits ranked, **evidence-graded**, **priced** findings across the algorithmic (A), systems (B), protocol (C) and architecture (D) tiers. Writes `./.tml/findings.md`.                |
| `/tml:plan`    | To decide                        | Fixes the operating point and the step budget under an explicit quality floor, names what may not move, orders the changes with gates and revert triggers, writes a stop rule. Writes `./.tml/frontier.md`. |
| `/tml:round`   | To design the next experiment    | Scopes one goal, splits hyperparameters into **scientific / nuisance / fixed**, builds the studies and search spaces, emits a portable study bundle with a return manifest.                                 |
| `/tml:analyze` | When results are in              | Runs the diagnostic checklist **before** the conclusion, draws isolation plots, and returns a variance-aware adopt verdict. Works on results it did not produce.                                            |
| `/tml:review`  | Before merging a change          | Adversarial: did the mechanism engage, is the measurement still valid, what broke silently. Read-only verdicts.                                                                                             |

Read → decide → design → interpret → guard. Nothing edits project code; all
state lives in `./.tml/`.

## The four ideas everything else hangs off

**1. The only currency is time-to-target-quality.**

```
time-to-target  =  steps-to-target  ×  time-per-step
                   └─ Tier A ─┘         └─ Tier B ─┘
```

Every finding states which factor it moves **and whether it moves the other
adversely** — because a change that improves throughput 30% and loss-per-step 40%
is a regression that every dashboard reports as a win.

**2. Every hyperparameter has a role, and the role comes from the question.**

Scientific (what you are measuring), nuisance (what must be optimised away to
compare fairly), fixed (what you are holding still, and therefore a caveat on the
conclusion). The same knob is all three in different rounds. Get this wrong and
the study answers a question nobody asked.

**3. Every claim carries a grade — and sometimes a flag.**

`measured-here` › `measured-elsewhere` › `mechanism` › `analogy` › `folklore`.
An ungraded claim is not emitted. Orthogonally, a **source-uncertainty** flag
marks claims whose cited source itself declines to settle the question — the
tuning playbook's open-research markers, why gated activations work, pre-norm
versus post-norm on final quality. A well-cited open question is still open.

**4. The regime is established, not assumed.**

How many trials can you actually run at once? Where do they run? Did this plugin
design the study? Guidance calibrated for a hundred parallel trials prescribes
experiments you cannot run; the regime is asked for, and the procedure branches
on it.

## What it will not do

- **Choose your operating point.** It frames the trade and asks.
- **Invent a role assignment** it was not given. "Cannot be determined" is a real
  verdict about a study's fairness.
- **Report throughput as a result.**
- **Fabricate an identifier.** A citation in `references/literature.md` is either
  verified or has no identifier at all.
- **Run your training.** Read-first, always.

## Handoff to `/ar:*`

When the work is many measured iterations under a locked harness rather than a
designed comparison, `/tml:plan` offers the handoff to `/ar:start` with its cost
stated. The two share protocol vocabulary deliberately — noise floor, keep
threshold, locked harness — so nothing needs restating across the boundary.

## Attribution

The experimental-method material is adapted from the **Deep Learning Tuning
Playbook** (Godbole, Dahl, Gilmer, Shallue, Nado, 2023), used under **CC BY
4.0**, with changes listed in [`NOTICE`](NOTICE). The tier catalogues carried
forward from `parml` credit their own sources there too. This plugin is MIT
licensed; see [`LICENSE`](LICENSE).
