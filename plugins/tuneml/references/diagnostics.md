# Extracting insight from a study

Adapted from `L-PLAYBOOK`. Run this checklist **before** answering the round's
original question. Several of its entries can invalidate the round outright, and
answering the original question first tends to make the invalidating answer
unwelcome.

---

## 1. The checklist, in order

1. **Is the search space large enough?** (§2) — a boundary-hugging optimum means
   the space, not the model, decided the answer.
2. **Were enough points sampled?** (§3)
3. **What fraction of trials was infeasible?** (§4)
4. **Does the model show optimisation failures?** → `instability.md`
5. **What do the training curves of the best trials say?** (§5)
6. **Was the nuisance tuning good enough to make the comparison fair?**
   (`study-design.md` §4) — for analysis-only inputs, this is often "cannot be
   determined", and saying so is the correct answer.

Only then: the round's actual question (§6), and the adopt decision (§7).

If any of 1–4 fails, the corrective action is usually to **revise and re-run**,
not to interpret harder.

---

## 2. Search-space boundaries

Plot the objective against each varied hyperparameter, one point per trial — the
**basic hyperparameter axis plot**. Use each trial's best value over training,
not its final value.

A space is **suspicious when the best points cluster near a boundary**: there may
be better points just outside it. Expand and re-run until the best observed point
is not at the edge.

A specific and important pattern: if all trials above some learning rate are
infeasible, **and** the best trials sit right at that edge, the model is not
telling you its optimal learning rate — it is telling you about a stability
problem that is capping the learning rate it can use. Go to `instability.md`
before believing the number.

---

## 3. Sampling density

There is no general way to know when a space has been sampled densely enough —
`L-PLAYBOOK` marks this an open question. In practice: sample what you can
afford, look at the axis plots, and build a sense of how many points landed in
the good region.

The magnitude of the problem is worth stating to an operator, because it is
routinely underestimated: on one worked example, the spread between a lucky and
an unlucky **study** at 20 trials exceeded the run-to-run spread between retrains
at fixed hyperparameters. Study variance is real and is usually invisible
(§7).

---

## 4. Infeasible trials

Count them: diverged, NaN, absurd loss, or failed to run because of an implicit
constraint. Then interpret the fraction:

- **A large fraction** means the search space is sampling regions that cannot
  work. Narrow it, or reparameterise it.
- **A very large fraction** can mean a bug in the training code rather than a bad
  space. Check before tuning the space around it.
- **Any fraction** matters for the choice of exploitation algorithm — a Bayesian
  optimiser that does not model infeasibility will misbehave here
  (`L-GELBART14`).

Record infeasibility as a flag with a reason, not as a missing row. A trial that
vanished is indistinguishable from a trial that was never run, and the two mean
very different things.

---

## 5. Reading training curves

Always look at the curves of at least the best few trials, even when the round's
question only needs one number per trial. Collapsing a trial to a scalar hides
most of what went wrong.

| What you see                                    | What it means                                             | What to do                                                                |
| ----------------------------------------------- | --------------------------------------------------------- | ------------------------------------------------------------------------- |
| Validation error **rising** mid-training        | Problematic overfitting                                   | Add/tune regularisation and re-run **before** comparing scientific values |
| High **step-to-step variance** late in training | Batch variance, small validation set, or LR too high late | Larger batch, more validation data, LR decay, or parameter averaging      |
| Still improving at the end                      | Compute-bound regime                                      | More steps, or a different schedule (`step-budget.md` §3)                 |
| Saturated long before the end                   | Not compute-bound                                         | Fewer steps (`step-budget.md` §2)                                         |
| Training loss **increasing**                    | Almost always a bug                                       | Stop tuning; debug                                                        |

Two subtleties worth carrying:

- **Check overfitting in the best trial of every scientific setting**, not just
  the overall best. If any of them overfits, fix that first — otherwise you are
  comparing a regularised configuration against an unregularised one.
- **Selecting the best trial hides overfitting and rewards accidental
  regularisation.** Anything that makes training worse acts as a regulariser,
  including a learning rate that is simply too small. So the "best" trial for a
  scientific setting may have been selected _because_ it was hobbled — which is
  not the property you were trying to measure. Look at the whole population, not
  only the winner.

---

## 6. Answering the round's question — isolation plots

An **isolation plot** shows, for each value of the scientific hyperparameter, the
performance of the _best_ trial across the nuisance hyperparameters — i.e.
performance after optimising the nuisance dimensions away. That is the
apples-to-apples comparison the whole study was built to produce.

With quasi-random data over a continuous scientific hyperparameter, approximate
it by bucketing the axis and taking the best trial in each vertical slice.

When the question is "should we include X at all", the baseline **without** X
must have had its own nuisance hyperparameters tuned just as well. A comparison
against an untuned baseline is not evidence, and it is the single easiest way to
adopt something useless.

**Automate the plots.** Axis plots for every varied hyperparameter and curves for
every trial, generated without being asked, because the effort of making a plot
is the main reason plots do not get looked at.

---

## 7. The adopt decision, under three kinds of variance

Before adopting anything, be explicit about which variance could explain the
observed difference:

| Source                                  | Is                                                                                                 |
| --------------------------------------- | -------------------------------------------------------------------------------------------------- |
| **Trial / retrain variance**            | Same hyperparameters, different seed — init, shuffling, dropout masks, nondeterministic reductions |
| **Study variance**                      | Same search space, different search seed → a different configuration selected                      |
| **Data collection / sampling variance** | Different train/validation/test split or data generation                                           |

Trial variance alone routinely produces statistically significant differences
between two models with identical hyperparameters, so a significance test against
a fixed validation set is not sufficient. Characterise trial variance by
**running the best trial `n` times** — after major pipeline changes at least, and
accepting that in some settings this is too expensive to be worth it.

Study variance is the one that gets forgotten. It matters whenever the conclusion
is about more than a single point in hyperparameter space, and it has been
observed both larger and smaller than trial variance.

**The decision rule.** Demanding certainty is as wrong as demanding nothing. If a
candidate beats the incumbent taking both of their retrain variances into
account, adopt it as the new baseline — **provided the improvement outweighs the
complexity it adds**. Complexity is a real cost, paid forever, by people who did
not run the study.

**Where the noise floor fits.** This plugin's protocol tier and the `ar` plugin
both gate adoption on beating a measured noise floor; that gate is the
quantitative form of this rule, and it stays. What is legitimately negotiable is
how much budget is spent _characterising_ the floor — buying more certainty has a
price and can be overpaid. Where budget is short, the honest move is to adopt
**provisionally and record it as provisional**, with a revisit trigger. What is
not available is adopting under uncertainty and forgetting that you did, which is
how an unmeasured change becomes load-bearing.
