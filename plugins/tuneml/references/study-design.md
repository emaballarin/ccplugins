# Designing a round of experiments

Adapted from `L-PLAYBOOK`. Read with `hyperparameter-roles.md` (what the knobs
are for) and `regime.md` (how many trials you can actually run).

---

## 1. One goal per round

A round has **one** clear goal, narrow enough that the experiments can actually
settle it. Adding two features or asking two questions at once means the effects
cannot be disentangled, and the round produces a number instead of an answer.

Legitimate goal shapes:

- Try a candidate pipeline improvement (a regulariser, a preprocessing choice).
- Understand the effect of one hyperparameter.
- Greedily minimise validation error (a legitimate goal, just not an
  informative one — see §5).

**Most rounds should be exploration, not exploitation.** The majority of tuning
time is well spent on understanding the problem rather than on chasing the
validation number, because understanding is what stops you from adopting a
change that was present in a good run by historical accident, tells you which
hyperparameters interact, and tells you when tuning has saturated. Be greedy
deliberately and late, not by default.

---

## 2. Studies and trials

A **study** is a set of hyperparameter configurations to be run and analysed
together; each configuration is a **trial**. Designing a study means choosing
what varies, over what ranges, how many trials, and by what sampling algorithm.

**Default structure: one study per scientific setting**, each tuning over the
nuisance hyperparameters, compared by taking the best trial from each. This
handles conditional hyperparameters naturally and keeps the comparison legible.

**Alternative: one joint study** with scientific and nuisance hyperparameters in
a single search space, when there are too many scientific values for separate
studies. Costs: conditional hyperparameters become awkward-to-impossible to
express, and you must ensure the sampler covers the scientific dimension
uniformly — which is a further argument for quasi-random sampling
(`regime.md` §2).

---

## 3. Search spaces

- **Log scale for anything scale-like.** Learning rate, weight decay, `ε`,
  regularisation strengths. For these, the order of magnitude is what matters,
  and a linear grid wastes almost all its points. Sample log-uniformly.
- **Parameterise so that feasible regions are convex-ish.** If a large fraction
  of trials is infeasible, the space is wrong; sometimes the fix is a
  reparameterisation rather than a narrower range (see `diagnostics.md` §4).
- **Do not put `max_train_steps` in a study.** Fixed per study, refined between
  studies (`step-budget.md` §2).
- **Bounds are hypotheses.** They get checked after the fact
  (`diagnostics.md` §2), and a boundary-hugging optimum means the round is not
  finished.

---

## 4. Allocating the budget — three competing desiderata

A study's budget must serve three things at once, and improving any one of them
costs trials taken from the others:

1. **Enough scientific values compared** — sets how broad the conclusion is.
2. **A wide enough nuisance search space** — sets whether a good nuisance
   setting _exists_ in the space, for **each** scientific value.
3. **Dense enough sampling of that space** — sets whether the search will _find_
   it.

Failures of (2) and (3) are the same failure from the operator's point of view:
an **unfair comparison**, where one scientific value happened to get luckier
nuisance tuning than another. This is the dominant way a well-run-looking study
produces a wrong conclusion, and it is invisible in the final numbers.

There is no general formula for the split; it needs domain knowledge and the
regime (`regime.md` §1). What is not optional is asking, after the study, whether
the nuisance tuning was good enough to justify the comparison at all —
`diagnostics.md` §1 is that question in checklist form.

---

## 5. Exploration and exploitation

Two phases, with different tools and different success criteria:

| Phase            | Goal                                  | Sampling                      | Done when                                                   |
| ---------------- | ------------------------------------- | ----------------------------- | ----------------------------------------------------------- |
| **Exploration**  | Insight: what matters, what interacts | Quasi-random (`regime.md` §2) | The important hyperparameters and sensible ranges are known |
| **Exploitation** | One best configuration                | Bayesian optimisation / TPE   | Budget exhausted, or improvements saturate                  |

**After exploration concludes**, the refined search space should comfortably
contain the region around the best trial and have been sampled adequately. At
that point the advantages of quasi-random sampling no longer apply and a proper
Bayesian optimiser is the right tool — with the caveat that if the space contains
a non-trivial volume of divergent points, the optimiser must handle infeasible
trials properly (`L-GELBART14`; `L-VIZIER` marks them infeasible).

This is also the point at which to consider the **test set** — and the only
circumstance in which folding validation data back into training is defensible is
when there will be no future launch on this workload at all.

---

## 6. Emitting the design

The output of a round design is `templates/study-spec.md`, written to
`./.tml/rounds/NNN/`. It carries the goal, the role assignment, the search
spaces, the sampler and seed, the trial budget, the fixed-hyperparameter caveats,
and — when execution is elsewhere — the **return manifest** listing exactly which
artifacts must come back for `/tml:analyze` to be able to do its job
(`regime.md` §3).

A study spec is worth writing even when the study runs locally five minutes
later. It is the only record of what the round was _for_, and the checklist in
`diagnostics.md` is unanswerable without it.
