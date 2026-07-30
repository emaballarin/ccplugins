# How long to train

Adapted from `L-PLAYBOOK`. Decided in `/tml:plan`, consumed by `/tml:round`.

---

## 1. Which regime are you in?

| Regime                | Means                                                                                       |
| --------------------- | ------------------------------------------------------------------------------------------- |
| **compute-bound**     | Limited by how long you are willing to wait, not by data or by saturation                   |
| **not compute-bound** | You can afford to train as long as you like; past some point it stops helping (or overfits) |

In the compute-bound regime, _speeding up training is equivalent to improving
it_, and the "optimal" training time is as long as you can afford — though that
does not make training longer the only way to improve results.

Independently of regime: **anything that increases gradient variance across
batches slows progress per step**, and so raises the steps needed to reach a
given loss. Smaller batches, added augmentation, and some regularisers (dropout)
all do this. Budgets set before such a change are invalid after it.

---

## 2. Not compute-bound: picking `max_train_steps`

Goal: long enough to reach the best result, without being wasteful.

- **When in doubt, train longer.** With retrospective optimal checkpoint
  selection and frequent enough checkpoints, performance should never degrade
  from training longer. Keep the `n` best checkpoints seen so far and choose at
  the end; with a pre-specified trial budget, prospective early stopping is
  usually unnecessary.
- **Never tune `max_train_steps` inside a study.** Fix one value for all trials.
  Then look at where retrospective checkpoint selection actually landed:
    - best step consistently in the **first 10%** → the budget is far too high;
    - best step consistently in the **last 25%** → train longer and re-tune the
      decay schedule.
- The right value **changes** when the architecture or the data changes — adding
  augmentation raises it, a better-tuned optimiser or schedule can lower it.

### 2.1 Initial candidate, via a constant-LR sweep

Applicable when the training set can be fit essentially perfectly, using a
constant learning rate:

1. Find any configuration and step count `N` that fits the training set.
2. Run a **constant learning-rate sweep**, no augmentation, no regularisation,
   each trial for `N` steps.
3. The number of steps the **fastest** trial needs to reach perfect training
   performance is the initial `max_train_steps`.

**Its failure mode is self-deception.** If every learning rate in the sweep is
too small, the procedure concludes that a very large `max_train_steps` is
necessary — and it looks like a measurement. Minimum check: confirm the optimal
learning rate is not at the boundary of the swept range (`diagnostics.md` §2).

---

## 3. Compute-bound: rounds of increasing length

Training loss keeps improving and patience is the constraint. Training as long as
possible is not automatically right: shorter runs buy more experiments, and
tuning quality depends on the number of experiments.

The trade is that conclusions from short runs may not hold at full length. So
**tune in rounds of increasing per-trial length** — 1 to 3 rounds is usually
practical:

- **Round 1** — short runs, to find model and optimiser hyperparameters.
- **Round 2** — very few long runs on the best points, to get the final model.

The hard part of `round i → i+1` is the **decay schedule**, and the common
pitfall is spending the extra steps at too small a learning rate. Extend the
high-learning-rate portion rather than stretching the decay: for a linear
schedule, keep the decay length from round 1 and lengthen the initial constant
phase; for cosine, keep the base rate and extend `max_train_steps`.
`source-uncertainty` — `L-PLAYBOOK` marks this specific recommendation
speculative.

---

## 4. What transfers from short runs to long ones

Ordered by decreasing confidence. This ladder is what makes round 1 worth
running at all, and it is `source-uncertainty` throughout — these are the
authors' stated suspicions, and they say more research is needed.

| Confidence      | Transfers                                                           |
| --------------- | ------------------------------------------------------------------- |
| **Very likely** | Warmup length; initialisation — i.e. everything in `instability.md` |
| **Likely**      | Model architecture — a dramatic architectural win usually carries   |
| **Might**       | Optimiser and its hyperparameters; augmentation; regularisation     |
| **Unlikely**    | The learning-rate decay schedule                                    |

Two consequences. **Fix instability in round 1** — it is the surest transfer you
have. And **do not trust a schedule tuned at short horizon**: a decay tuned over
few steps and then extended puts most of the run at an uselessly small learning
rate. Myopic learning-rate selection has a name and a literature; treat a
short-horizon schedule as provisional by default.

A note on regularisation: if the model cannot fit the training set at all, it is
probably in a regime where regularisation will not help much, and tuning it in
round 1 is wasted budget.

---

## 5. Handing off

The step budget is an input to `/tml:round` and an entry in
`templates/frontier.md`. When the plan is many measured iterations under a locked
harness rather than a designed comparison, this is the natural handoff point to
`/ar:start`, which takes a numeric objective, a noise floor, and a locked harness
and runs the accept/reject loop unattended. The vocabulary is deliberately shared
— noise floor, keep threshold, locked harness — so nothing needs restating.
