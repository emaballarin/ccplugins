# Optimisers, and what their hyperparameters actually mean

Load before recommending, tuning, or comparing an optimiser. §1 is not optional
reading: **the same Greek letter denotes different quantities in different
optimisers**, and every downstream recommendation in this file is wrong if the
symbols are read from the wrong algorithm.

The standing position is the playbook's: no optimiser is best across problems,
comparing them fairly is genuinely hard because each carries hyperparameters that
must be tuned before the comparison means anything, and a well-established choice
tuned properly beats an exotic one tuned badly. Everything below is a caveat to
that position, not a replacement for it.

---

## 1. β conventions — read this before writing any β

### 1.1 The two things a β can be

Almost every optimiser hyperparameter written `β` (or `α`, or `momentum`) is one
of two structurally different things:

- **A decay on an exponential moving average.** `a ← β·a + (1−β)·x`. The
  accumulator is a weighted _average_ of past `x`, so its scale matches `x`'s.
  Effective memory is about **1/(1−β)** steps.
- **A decay on a running sum.** `a ← β·a + x`. The accumulator is a _sum_, so at
  steady state it is about **1/(1−β)** times the scale of `x`.

These are not interchangeable, and the difference is exactly a factor of
`1/(1−β)` in the resulting step size. PyTorch's SGD momentum buffer is the
**sum** form; Adam's moments are the **average** form. Confusing the two is how
a "momentum 0.9 → 0.98" change silently becomes a 5× learning-rate change.

### 1.2 What each symbol means, per optimiser

| Optimiser             | Symbol               | Accumulator it decays                       | Form    | Default     | Adam-equivalent role         |
| --------------------- | -------------------- | ------------------------------------------- | ------- | ----------- | ---------------------------- |
| **Adam / AdamW**      | `β₁`                 | EMA of `g`                                  | average | 0.9         | — (is the reference)         |
|                       | `β₂`                 | EMA of `g²`                                 | average | 0.999       | —                            |
| **NAdam**             | `β₁`, `β₂`           | as Adam, unchanged                          | average | 0.9 / 0.999 | identical                    |
|                       | `momentum_decay` (ψ) | schedule rate for `μ_t`, not an accumulator | —       | 4e-3        | no analogue                  |
| **Adan**              | `β₁`                 | EMA of `g`                                  | average | 0.98        | **`β₁`**                     |
|                       | `β₂`                 | EMA of `Δg = g_t − g_{t−1}`                 | average | 0.92        | **no analogue**              |
|                       | `β₃`                 | EMA of `g̃²`                                 | average | 0.99        | **`β₂`**                     |
| **RMSProp** (PyTorch) | `alpha`              | EMA of `g²`                                 | average | 0.99        | **`β₂`**                     |
| **SGD** (PyTorch)     | `momentum`           | running sum of `g`                          | **sum** | —           | loosely `β₁`, different form |

**The collision to watch.** Adan's `β₂` is _not_ Adam's `β₂`. Adan's `β₃` is.
Writing "set β₂ = 0.95" is meaningful for Adam and means something entirely
different for Adan — where the default is 0.92 and the quantity is a gradient
_difference_, not a gradient _square_. Whenever both appear in the same
sentence, qualify them: `Adam-β₂`, `Adan-β₂`. Same for RMSProp's `alpha`, which
plays Adam's `β₂` role under a different name.

**Adan paper vs. implementation.** The reference implementation
(`sail-sg/Adan`) uses the standard EMA convention verified line by line:

```python
exp_avg.mul_(beta1).add_(grad, alpha=1 - beta1)                    # m ← β₁m + (1−β₁)g
exp_avg_diff.mul_(beta2).add_(neg_grad_or_diff, alpha=1 - beta2)   # v ← β₂v + (1−β₂)Δg
neg_grad_or_diff.mul_(beta2).add_(grad)                            # g̃ = g + β₂·Δg
exp_avg_sq.mul_(beta3).addcmul_(…, value=1 - beta3)                # n ← β₃n + (1−β₃)g̃²
```

**The paper uses the complementary convention**, verified against its Algorithm 1:

```
m_k = (1−β₁)m_{k−1} + β₁·g_k                              # paper
v_k = (1−β₂)v_{k−1} + β₂·(g_k − g_{k−1})                  # paper
n_k = (1−β₃)n_{k−1} + β₃·[g_k + (1−β₂)(g_k − g_{k−1})]²   # paper
```

So **`β_paper = 1 − β_code`**, and the two forms agree exactly: the paper's
correction coefficient `(1−β₂)` is the implementation's `β₂`, which is why the
update reads `(m̂ + β₂v̂)` in code and `(m + (1−β₂)v)` in the paper. The
implementation defaults `(0.98, 0.92, 0.99)` are paper-convention
`(0.02, 0.08, 0.01)`.

**Take the implementation as authoritative for the defaults**, and translate
before importing any beta from the paper. Reading paper values as code values —
or the reverse — silently inverts every horizon in §1.3.

### 1.3 Think in horizons, not in betas

`1/(1−β)` steps is the effective memory of an EMA, and it is the only
representation in which betas are comparable across optimisers and across
batch sizes:

| β     | 0.9 | 0.92 | 0.95 | 0.98 | 0.99 | 0.999 |
| ----- | --- | ---- | ---- | ---- | ---- | ----- |
| steps | 10  | 12.5 | 20   | 50   | 100  | 1000  |

Three consequences worth stating to an operator. Adam's default `β₂ = 0.999`
averages the squared gradient over ~1000 steps, which is a **long** time: an EMA
reaches only about 63 % of its asymptotic weight after one horizon
(`1 − (1 − 1/H)^H → 1 − 1/e`), so a run of a few thousand steps never reaches
steady state in that accumulator at all. Bias correction makes the estimate
unbiased from step one, but it is still an average over roughly `min(t, H)`
effective samples, so it stays high-variance early. Second, a genuine change in
gradient scale takes ~1000 steps to be reflected — which is exactly why lowering
`β₂` is the standard response to loss spikes (§4.3). Third, a horizon fixed in
_steps_ is a horizon that shrinks in _examples_ when the batch size grows, which
is one mechanism behind the playbook's rule that changing batch size forces
optimiser hyperparameters to be re-tuned.

---

## 2. Decoupled weight decay is the default, and there is a mechanism

Prefer the decoupled-weight-decay member of any adaptive family: `Adam → AdamW`,
and equivalently for the rest. This is not taste.

With **L2 in the gradient**, the penalty term `λθ` is added to `g` and therefore
passes through the adaptive denominator `√v̂ + ε` along with everything else. The
decay actually applied to a parameter ends up scaled by `1/(√v̂ + ε)` — that is,
**inversely coupled to that parameter's recent gradient magnitude**. Parameters
with large gradients get decayed less; parameters with small gradients get
decayed more. That is not a regulariser anybody designed, and it is why the L2
coefficient in Adam has no stable transferable value.

With **decoupled decay**, `θ ← θ − ηλθ` is applied outside the adaptive step, so
the decay rate is uniform across parameters and independent of gradient history.
`Grade` — `mechanism`; it is visible in four lines of either implementation.

Consequence for tuning: `λ` under AdamW and `λ` under Adam+L2 are different
hyperparameters with different scales. Porting a value across is a bug.

---

## 3. Choosing a family

Playbook first: **use the most popular, well-established optimiser for this
problem type**, and be prepared to attend to _all_ its hyperparameters. An
optimiser with more knobs costs more tuning budget, which is a real price paid
out of the same budget as everything else — early in a project, prefer the
simpler member (SGD with fixed momentum, or Adam with the extra knobs pinned) and
generalise later.

Two things the playbook says that are worth not softening:

- Optimiser advantages are frequently problem- and scale-specific and often fail
  to transfer. `Grade` — `measured-elsewhere`, Choi et al. 2019 (L-CHOI19),
  which finds that optimiser hierarchies largely collapse once each is tuned
  under a comparable budget.
- The _choice_ of optimiser is usually a **scientific** or **fixed**
  hyperparameter, while its internal knobs are **nuisance** hyperparameters —
  see `hyperparameter-roles.md`. Comparing two optimisers means tuning each
  one's nuisance set separately, or the comparison is not a comparison.

### 3.1 The Nesterov branch — NAdam and Adan are not the same idea

Both descend from Adam and both are called "Nesterov"; they Nesterovise
different objects, and their cost/benefit is not close.

|                         | NAdam                              | Adan                                        |
| ----------------------- | ---------------------------------- | ------------------------------------------- |
| Nesterovised quantity   | the momentum accumulator           | the extrapolation point                     |
| New information         | none — a reweighting of `m` vs `g` | curvature, via `Δg = g_t − g_{t−1}`         |
| Denominator             | EMA of `g²`                        | EMA of `g̃²`, `g̃ = g + β₂Δg`                 |
| Optimiser state tensors | 2                                  | 4 (`m`, `v`, `n`, previous gradient)        |
| Optimiser state vs Adam | identical                          | **2×** (see the denominator note below)     |
| Learning rate vs AdamW  | comparable                         | **5–10× larger** (L-ADAN, from its README)  |
| Availability            | `torch.optim.NAdam`                | `pip install adan`, `from adan import Adan` |

**NAdam** buys close to nothing. Its entire content is the numerator reweighting
driven by `μ_t = β₁(1 − ½·0.96^{tψ})`; no new information enters the update, and
under an equal tuning budget it collapses onto Adam — consistent with L-CHOI19.
It is free, so it is not a mistake; it is just not a lever. `Grade` —
`measured-elsewhere`.

**Adan** buys real acceleration — roughly halved epoch budgets reported on ViT /
ConvNeXt / MAE — and charges for it. `Grade` — `measured-elsewhere`, from the
paper's own experiments.

**The `O(ε^{-3.5})` complexity claim, stated with its conditions.** Verified
against the paper. It rests on three assumptions and one algorithmic detail:

|        |                                                              |
| ------ | ------------------------------------------------------------ |
| **A1** | `L`-smoothness of `F` w.r.t. the parameters                  |
| **A2** | Unbiased gradient oracle with bounded magnitude and variance |
| **A3** | **ρ-Lipschitz continuous Hessian** — second-order smoothness |

Under **A1 + A2 only**, Theorem 1 gives `O(c_∞^{2.5}·ε^{-4})`. It is **A3** that
buys the improvement: Theorem 2 gives `O(c_∞^{1.25}·ε^{-3.5})`, which matches the
`Ω(ε^{-3.5})` lower bound for single-query stochastic methods under Lipschitz
gradient _and_ Hessian. Without the Hessian condition the lower bound is
`Θ(ε^{-4})`, so the rate is not better than Adam's in the regime most people are
actually in — it is better _given an extra smoothness assumption nobody
verifies_.

Two further conditions worth not losing: Theorem 2 is stated for Algorithm 1
**with the restart condition**, not the plain optimiser most users run, and at
`λ = 0` — no weight decay. Its parameter scalings (`β₁, β₂ = O(ε²)`,
`β₃ = O(ε⁴)`, paper convention, i.e. code betas → 1) are an asymptotic regime,
not the shipped defaults.

None of this makes the result wrong; it makes it a statement about a specific
algorithm under specific conditions. Cite it that way, or not at all.

Costs, all of which must be stated when recommending it:

- **Mandatory LR and weight-decay re-sweep.** A 5–10× LR shift means every
  schedule, warmup length, and step-unit hyperparameter derived from the old LR
  is invalid. This is not a drop-in swap.
- **2× optimiser state, but "slightly higher" total memory** — the paper's repo
  says the latter and both are true at different denominators. Optimiser state
  is a fraction of a training footprint dominated by activations. Quote whichever
  denominator the operator is actually constrained by, and never the flattering
  one. Same distinction as parameter-EMA's "2× memory" (D8).
- **Noisier in pure bf16.** `Δg = g_t − g_{t−1}` is a difference of near-equal
  quantities; with bf16's 8 mantissa bits this is straightforward catastrophic
  cancellation, and the cancellation lands directly in both the correction term
  and the denominator. `Grade` — `mechanism`. Keep the gradient difference in
  fp32 if the framework allows it.
- **Three betas instead of two.** Its own README reports the optimiser is
  relatively robust to all three, especially `β₂`, and that the tuning order if
  needed is `β₃` first, then `β₁`.

Recommend Adan only where the epoch budget is the binding constraint and there is
budget for the re-sweep. Recommend NAdam only as a free swap nobody should expect
anything from.

---

## 4. The Adam hyperparameter ladder

### 4.1 The standard

The playbook's budget ladder is the default, and it is a statement about where
marginal tuning budget is best spent:

| Trials in the study | Tune                     |
| ------------------- | ------------------------ |
| < 10                | learning rate only       |
| 10–25               | learning rate, `β₁`      |
| 25+                 | learning rate, `β₁`, `ε` |
| substantially more  | additionally `β₂`        |

`Grade` — `measured-elsewhere`, with `source-uncertainty`: the playbook presents
these as rules of thumb and states outright that general claims about search
spaces and sampling density are very difficult to make.

### 4.2 Sweep orders of magnitude; do not pin defaults

**A defensible default is worse than a one-decade sweep.** For the learning rate
and for `ε`, what matters is the order of magnitude, so search log-uniformly and
check the boundary condition afterwards (`diagnostics.md` §2). This is the one
point where the playbook, this plugin's sources, and practice all agree without
qualification.

In particular, **do not pin a numeric learning-rate default**. Beyond being
workload-dependent, it is structurally incompatible with choosing batch size
independently for time-to-target (`tier-b-systems.md`, B14): the optimal LR moves
with the batch size, so an LR fixed as a constant and a batch size chosen as a
free variable cannot both be right. Pick one to fix; the playbook fixes neither
and sweeps.

### 4.3 Two documented departures

Both are conditioned. State the condition or do not state the claim.

**(a) `β₂` over fine LR tuning, in heterogeneous landscapes.** _Once the learning
rate is within a reasonable range_, `β₂` is often the more valuable remaining
knob — and lowering it from `0.999` to around `0.95` (with `β₁ = 0.9`) reduces
loss spikes. Condition: large generative models, LLMs included, or more generally
any objective whose landscape has regions with materially different
characteristics. Mechanism: a shorter second-moment horizon (20 steps at 0.95 vs
1000 at 0.999, §1.3) lets the denominator track an abrupt change in gradient
scale instead of lagging it by a thousand steps, so a gradient spike is damped
rather than passed through. `Grade` — `mechanism` for the horizon argument,
`measured-elsewhere` for the setting, which is standard in published LLM recipes.

This does **not** invert §4.1 in general. It says that at large scale, in this
regime, the ladder's ordering is not the one to follow.

**(b) Tie `β₁ = β₂` and tune them as one.** Orvieto & Gower 2025 (L-ORVIETO25)
find that the constraint `β₁ = β₂` retains Adam's performance across extensive
language-model training experiments, collapsing two hyperparameters into one and
admitting an interpretation of Adam as an online estimator of gradient mean and
variance. `Grade` — `measured-elsewhere`. Attractive precisely when the trial
budget is small, since it moves a two-dimensional search to one dimension —
i.e. it is a cheaper alternative to §4.1's early rungs, not a competitor to (a).

Note this is Adam's `β₁` and Adam's `β₂` (§1.2). It is unrelated to Adan's
`β₁ = β₂` degeneracy, which merely makes Adan reduce to Adam applied to `g̃`.

---

## 5. Learning-rate schedules

Scheduling is not optional for final quality, and the playbook is confident on
two points while explicitly conceding the third:

- Some non-constant schedule is needed, and tuning it matters. `Grade` —
  `measured-elsewhere`.
- **Linear or cosine decay** are the recommended defaults; several other families
  are probably fine. `Grade` — `measured-elsewhere`.
- Which family is _best_ is an open problem. `source-uncertainty` — the playbook
  says so in as many words.

Two things to refuse. **Never copy a complicated piecewise schedule out of a
paper**: those are usually the fossil record of a human watching validation loss
and intervening, they are sensitive to every other hyperparameter in the original
setup, and they are not reproducible. Copy the _algorithm_ that produced a
schedule, or use a simple family. And **never tune `max_train_steps` inside a
study** — it is fixed per study and refined between studies
(`step-budget.md` §2).

Warmup is treated as a stability instrument rather than a schedule choice; its
procedure lives in `instability.md` §3.

**Parameter averaging** — keeping an EMA of the weights and evaluating on the
EMA — is a cheap remedy for late-training step-to-step variance, and is the same
instrument the playbook calls Polyak averaging. Cost is one extra
parameter-sized buffer; see D8 for why that is not "2× memory".
