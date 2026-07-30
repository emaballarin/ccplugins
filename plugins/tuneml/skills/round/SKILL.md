---
name: round
description: 'Design the next round of experiments — scope one goal, classify every hyperparameter as scientific, nuisance or fixed, build the studies, choose search spaces and a sampler, and allocate the trial budget. Use for `/tml:round`, "what experiment should I run next", "how do I test whether X helps", "design a sweep for this", "is this comparison fair", "set up a hyperparameter search", or after `/tml:plan`. Emits a self-contained study bundle under ./.tml/rounds/NNN/ — config matrix, launch stub and a return manifest — so trials can run on another machine and be analysed here. Read-first: never runs training and never edits project code. Do NOT use to interpret finished results (that is /tml:analyze) or to find opportunities (that is /tml:audit).'
allowed-tools: [Read, Write, Glob, Grep, Bash, AskUserQuestion]
license: MIT
---

# /tml:round — design the next experiment

Turn a question into a study whose answer will actually mean something. The whole
value is in two things: **one goal**, and an honest **scientific / nuisance /
fixed** split. Everything else is bookkeeping.

## First action, always

```bash
ls -la ./.tml/rounds/ 2>/dev/null | tail -5; cat ./.tml/frontier.md 2>/dev/null | head -40
```

Number this round after the highest existing one. If earlier rounds exist, read
the most recent spec and its verdict — a round that repeats a settled question is
wasted budget, and a round that ignores the previous round's caveats inherits
them silently.

## Hard rules

1. **One goal per round.** If the goal needs an "and", it is two rounds. Two
   simultaneous questions cannot be disentangled afterwards.
2. **Write the role assignment down.** A round whose scientific / nuisance / fixed
   split was never recorded cannot be checked for fairness later — and it will
   be, by `/tml:analyze`, possibly in a different session.
3. **Every fixed hyperparameter is a caveat on the conclusion.** Record it as
   one, in those words.
4. **Never put `max_train_steps` in the search space.** Fixed per study.
5. **Read-first.** Writes only under `./.tml/rounds/NNN/`. Never runs training.

## Procedure

### 1. Establish the regime — before designing anything

`references/regime.md`. Three questions: how many trials can run concurrently,
where do they run, and does this plugin get to see the results directly. The
answers change the design, not just its execution. Do not guess the trial
capacity from device count.

### 2. Scope the goal

One sentence. `references/study-design.md` §1. Then state plainly whether this
round is **exploration** (insight — the default and the majority) or
**exploitation** (a best configuration). They use different samplers and have
different success criteria.

### 3. Assign roles

`references/hyperparameter-roles.md`. In order:

1. Name the **scientific** hyperparameters — usually one.
2. Everything else starts **nuisance**.
3. Demote nuisance → **fixed** deliberately, under budget pressure, preferring
   the ones that interact least with the scientific hyperparameters. Record each
   caveat.

Watch for **conditional** hyperparameters — knobs that exist only under some
scientific values. They are why one study per scientific setting is the default
structure, and they carry a specific trap: two conditional hyperparameters
sharing a name are not the same hyperparameter and must not share a search space.
The learning rate under two different optimisers is the standard example; the
beta-symbol collisions in `references/optimisers.md` §1.2 are the same failure in
a different place.

### 4. Build the studies

`references/study-design.md` §2–§3. Default: one study per scientific setting,
each tuning over the nuisance set. Search spaces log-scaled for anything
scale-like. Bounds are hypotheses and will be checked afterwards.

Sampler follows the phase and the regime (`references/regime.md` §2) — quasi-random
for exploration, Bayesian/TPE for exploitation, grid only in one or two
dimensions. If the operator uses Optuna, name the concrete sampler
(`references/regime.md` §2.1).

### 5. Allocate the budget across the three desiderata

Enough scientific values · a wide enough nuisance space · densely enough sampled.
Improving one costs the others (`study-design.md` §4). State which was
sacrificed. In a low or serial regime, sacrifice the number of scientific values
first — a narrow conclusion is still a conclusion, an unfairly-tuned comparison
is not.

### 6. Emit the bundle

Write `./.tml/rounds/NNN/` from `templates/study-spec.md`:

- the spec — goal, phase, role assignment, caveats, search spaces, sampler, seed;
- the **configuration matrix** — one fully-resolved row per trial, with seeds;
- a launch stub for the operator's scheduler;
- the **return manifest** when execution is remote (`regime.md` §3): per trial the
  best metric and its step, the final metric, the metric-vs-step series, an
  infeasibility flag _with its reason_, the resolved hyperparameters, the seed
  and wall-clock. Ask for curves on all trials if storage permits — several
  checks in `/tml:analyze` are impossible without them, and they are small.

The return manifest is the load-bearing part of a remote round: the cost of
discovering an omission afterwards is re-running the whole study.

## Handoffs

- Results are in → **`/tml:analyze`**.
- The design revealed the pipeline is unstable → **stop**, and fix that first
  (`references/instability.md`); a round run on an unstable workload measures the
  instability.

## Completion status

`DONE` (bundle written; role assignment and sacrificed desideratum both stated),
`DONE_WITH_CONCERNS`, `BLOCKED`, or `NEEDS_CONTEXT` — the last one usually
meaning the trial capacity or the goal is still unstated.
