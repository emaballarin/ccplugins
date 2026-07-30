# Optimisation failures: identifying and fixing them

Adapted from `L-PLAYBOOK`. Reached from `diagnostics.md` §1 step 4, or whenever a
learning-rate sweep's best value sits at the edge of the feasible region.

**Fix instability before tuning anything else.** An unstable workload reports a
learning-rate ceiling that is an artifact of the instability, and every
conclusion drawn under that ceiling inherits it.

---

## 1. When instability actually matters

Any workload becomes unstable if the learning rate is large enough. That is not a
problem. **Instability is a problem only when it forces a learning rate that is
too small** — i.e. when the model would train better at a rate it cannot reach.

Two kinds worth distinguishing, because they have different fixes:

- **At initialisation / early in training.**
- **Sudden, mid-training.**

---

## 2. Identifying an unstable workload

The systematic procedure:

1. Sweep the learning rate; find the best value `lr*`.
2. Plot **training loss curves for rates just above `lr*`**.
3. If those show loss instability — loss rising rather than falling during
   stretches of training — then fixing the instability will likely improve
   training.

Confirm by training at 5–10× `lr*` and watching for a sudden rise after a steady
decline.

**Log the L2 norm of the full gradient throughout training.** Outlier values are
what produce spurious mid-training instability, and the distribution of this
quantity is what sets a clipping threshold (§4). By default, produce a
gradient-norm-vs-step plot and a histogram over all steps.

**A trap in the evaluation schedule.** Some models show very early instability
followed by a recovery into slow-but-stable training — and a normal evaluation
cadence steps straight over it. To check, run an abbreviated ~500-step run at
`2 × lr*` **evaluating every step**. This is cheap and it is the only way the
pattern is visible.

---

## 3. Learning-rate warmup

Best for early-training instability. The procedure is specific, and skipping its
specifics is why warmup often "does not work":

1. Establish `unstable_base_learning_rate` — the rate at which the model becomes
   unstable (§2).
2. Target a `base_learning_rate` **at least an order of magnitude larger**;
   10× is the default first attempt, and the whole procedure can be repeated for
   100×.
3. The schedule is: ramp `0 → base_learning_rate` over `warmup_steps`, then hold
   constant for `post_warmup_steps`. Setting `post_warmup_steps = 2 ×
warmup_steps` is usually fine.
4. **Sweep `warmup_steps` across orders of magnitude** — e.g.
   `[10, 10³, 10⁴, 10⁵]`. The largest point tried should not exceed 10% of
   `max_train_steps`. The goal is the _shortest_ warmup that unlocks the target
   rate.
5. Apply the winning warmup to the baseline by **prepending** it to the existing
   schedule, and extend the run accordingly: 10,000 steps with 1,000 of warmup
   becomes an 11,000-step run. Compare using retrospective checkpoint selection.
6. If warmup must exceed ~5% of `max_train_steps`, raise `max_train_steps`.

Warmup can be tuned independently of the decay schedule. There is no typical
value across workloads: some models need 100 steps, transformers can need 40k+.

---

## 4. Gradient clipping

Best when the problem is large or outlier gradients, and it addresses **both**
early and mid-training instability — including some bad initialisations that
warmup cannot fix.

- Clip by norm: if `‖g‖ > λ` then `g ← λ · g/‖g‖`.
- **Set `λ` from the measured distribution**: the 90th percentile of observed
  gradient norms is a good starting point. It is workload-dependent and can be
  tuned from there.
- Clip harder if instability persists.

**The stopping condition.** If more than ~50% of updates are being clipped, the
clipping is no longer a safety net — it is an awkward, state-dependent way of
reducing the learning rate. At that point, reduce the learning rate instead and
say so. Extremely aggressive clipping is a smell, not a solution.

---

## 5. The rest of the ladder

In rough order of preference:

1. **Warmup** — early instability.
2. **Gradient clipping** — early or mid, outlier-driven.
3. **A different optimiser** — Adam sometimes tolerates instabilities that plain
   momentum does not. `source-uncertainty`: `L-PLAYBOOK` flags this as an active
   research area.
4. **Architecture and initialisation hygiene** — residual connections and
   normalisation if absent; normalisation **inside** the residual branch
   (`tier-d-architecture.md` D1); residual branches initialised so their outputs
   start near zero (D2).
5. **QK normalisation** — for large transformers specifically, where the failure
   mode is attention-logit growth (D5). `L-OLMO2` reports this combination
   improves both the growth and the spikiness of the gradient norm.
6. **Lower the learning rate** — last resort, and it is a defeat: you are
   accepting the ceiling rather than removing it.

---

## 6. What instability costs you if you leave it

It is worth stating plainly to an operator, because instability is often treated
as a nuisance to be worked around rather than a defect to be fixed:

- The learning-rate sweep returns a ceiling, not an optimum, so every
  learning-rate-dependent conclusion is conditioned on the defect.
- Step-unit hyperparameters derived from that rate — schedule shape, warmup,
  decay length — inherit the same conditioning.
- Search-space boundary diagnosis (`diagnostics.md` §2) will keep reporting a
  boundary problem that is not a boundary problem.
- And per `L-PLAYBOOK`'s own transfer ladder, warmup length and initialisation
  are among the **most** likely hyperparameters to transfer from short runs to
  long ones (`step-budget.md` §4) — so this is cheap to fix early and expensive
  to carry.
