# Changelog

All notable changes to the `tml` (tuneml) plugin are documented here.
This project adheres to [Semantic Versioning](https://semver.org/).

## 0.1.1 — 2026-07-30

Documentation-integrity patch from a full re-read of the plugin. No skill logic
changed, and no guidance was altered in substance.

- **Three cross-references into the protocol tier were unresolvable.**
  `evidence-grades.md` pointed at `tier-c-protocol.md` "§7" and "§5", and
  `tier-b-systems.md` at "§6", but that catalogue is organised as `C1`…`C9`
  items and has no numbered sections — so none of the three resolved. Corrected
  to `C7` (operating point), `C5` (additivity) and `C6` (when speed is the wrong
  objective), which is what each meant. Inherited from `parml`, where the same
  three were already broken. As item references they are now covered by Tier-1
  validation and cannot silently break again.
- **One ambiguous section reference.** `/tml:round` ended a sentence with a bare
  "(§2.1)" that meant `references/regime.md` §2.1, not its own §2.1 — which does
  not exist. Made explicit.
- **A corrected arithmetic claim.** `optimisers.md` §1.3 asserted that a
  2000-step run "spends a quarter of its life with a poorly-warmed denominator"
  at `β₂ = 0.999`. The fraction was unsupported and the framing ignored Adam's
  bias correction. Replaced with the checkable statement: an EMA reaches ~63 % of
  its asymptotic weight after one horizon (`1 − (1 − 1/H)^H → 1 − 1/e`, verified
  numerically at 0.632), bias correction makes the estimate unbiased from step
  one but it remains an average over ~`min(t, H)` effective samples, so a run of
  a few thousand steps never reaches steady state in that accumulator.

## 0.1.0 — 2026-07-30

Initial release. An umbrella advisor for training and evaluating neural networks
well: **the scientific method for tuning** and **the speed↔quality frontier**, in
one plugin. Supersedes `parml` (paretoml), whose tier catalogues, evidence
grades and templates it carries forward.

### Five skills

`/tml:audit` reads a pipeline and emits ranked, evidence-graded, priced findings;
`/tml:plan` fixes an operating point and a step budget under an explicit quality
floor; `/tml:round` designs the next round of experiments; `/tml:analyze`
extracts insight from results and returns a variance-aware adopt verdict;
`/tml:review` adversarially checks a proposed or applied change. Read → decide →
design → interpret → guard. Nothing edits project code; state lives in `./.tml/`.

### The experimental method

Adapted from the Deep Learning Tuning Playbook (CC BY 4.0 — see `NOTICE`):

- **Scientific / nuisance / fixed** hyperparameter roles, with conditional
  hyperparameters and the rule that two conditional knobs sharing a name are not
  the same knob. The role is a property of the goal, not of the hyperparameter.
- **Study design** — one goal per round, one study per scientific setting,
  nuisance dimensions optimised away before comparison, and the three competing
  desiderata that a trial budget must split between.
- **A diagnostic checklist run before the conclusion** — search-space boundaries,
  sampling density, infeasible fraction, optimisation failures, training-curve
  pathologies — several of which can invalidate a round outright.
- **Isolation plots**, and the requirement that an "include X at all" comparison
  tunes the no-X baseline equally well.
- **Three kinds of variance** — trial, study, data — with study variance named
  explicitly because it is the one that gets forgotten.
- **Step budgets** — compute-bound versus not, the constant-LR sweep for an
  initial `max_train_steps` and its self-deception failure mode, rounds of
  increasing length, and the transfer ladder from short runs to long ones.
- **Optimisation-failure triage** — identifying an unstable workload, the warmup
  procedure with its order-of-magnitude sweep, gradient clipping from the
  measured 90th percentile, and the ~50%-clipped stopping condition.

### Explicit execution regime

`L-PLAYBOOK` assumes a study service running tens to hundreds of concurrent
trials. That assumption is made explicit and branched on rather than inherited:

- **Parallelism** — `high` / `low` / `serial`, established by asking, with the
  playbook's own documented fallbacks in the lower regimes and a requirement to
  state which desideratum was sacrificed.
- **Sampler by phase** — quasi-random for exploration (five named reasons),
  Bayesian/TPE for exploitation, grid only in one or two dimensions. Mapped onto
  concrete Optuna samplers: `QMCSampler` then `TPESampler`.
- **Local or remote** — `/tml:round` emits a self-contained bundle with a
  configuration matrix and a **return manifest** naming exactly which artifacts
  must come back, so trials can run anywhere.
- **Analysis-only** — `/tml:analyze` works on results it did not produce, states
  which checks the missing fields disable, and refuses to invent a role
  assignment it was not given.

### Tier D — architecture and numerics

A fourth catalogue, covering ground both sources scope out: normalisation
placement (pre-norm by default, with the gradient-highway argument, its
mandatory final norm and depth-scaled init, and the open final-quality question
against DeepNorm / OLMo-2 / Peri-LN); residual connections and near-identity
initialisation; activation units at two levels, so the criteria cover both
pointwise nonlinearities and the gated GLU family with its 2/3 parameter-matching
convention; the normalisation-layer taxonomy, with FiLM correctly filed as
conditioning rather than "learnable scale and shift"; QK normalisation; inductive
bias and equivariance; reduced precision framed speed-first with fp16 and bf16
distinguished; parameter EMA with an honest memory denominator; spectral bias and
its remedies; and numerical hygiene.

### Optimisers, and the β conventions

A dedicated reference, because **the same symbol denotes different quantities in
different optimisers** and every recommendation downstream is wrong if they are
read from the wrong algorithm. Adan's `β₂` is a gradient-_difference_ EMA rate;
Adam's `β₂` is a squared-gradient rate; Adan's `β₃` plays Adam's `β₂` role;
RMSProp calls it `alpha`; and PyTorch's SGD `momentum` decays a running _sum_
rather than an average, which is a factor of `1/(1−β)` in the step. Betas are
additionally given in **horizon** form (`1/(1−β)` steps), the only representation
comparable across optimisers.

Also: decoupled weight decay with its mechanism rather than as a preference; the
Adam budget ladder as the standard, with two conditioned departures (`β₂` over
fine LR tuning in heterogeneous landscapes, and `β₁ = β₂` tying per Orvieto &
Gower 2025); no pinned numeric learning-rate default, because one is structurally
incompatible with choosing batch size independently; and NAdam versus Adan as two
different Nesterovisations with very different cost/benefit.

### Batch size (B14)

Not a quality knob — but not a memory-occupancy contest either. Chosen once,
early, by minimising `steps-to-target × time-per-step`, with the optimum
frequently **interior**: allocator pressure, workspace starvation forcing slower
kernel selection, tile/wave quantisation, and the headroom that evaluation and
parameter EMA need. Occupancy is the datacenter's objective; time-to-target is
the researcher's. An interior optimum is recorded as a **finding**, with its
cause, because a fixable cause may buy both. Gradient accumulation is retained
only for a crucially undersized batch where lower gradient variance is genuinely
required — a variance argument, never a speed one.

### Evidence grades, and a source-uncertainty flag

The grade ladder, the three cost axes and the tier algebra are carried forward
unchanged. Added: an explicit **source-uncertainty** flag, orthogonal to the
grade, marking claims whose _cited source itself_ declines to settle the question
— the playbook's 🤖 sections, `L-SHAZEER20`'s conclusion, the pre-norm versus
post-norm final-quality comparison. A well-cited open question is still open.

### Pinned literature index

`references/literature.md` resolves every citation by key, and states its
identifier policy outright: an identifier is either **verified** or **absent**.
Fabricating one to fill a gap is worse than omitting it.
