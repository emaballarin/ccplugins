# Tier A — algorithmic: fewer steps to the same quality

Changes that move **`steps-to-target`**. They alter what is computed, so almost
all of them carry a `numeric` or `distribution` blast radius and must be verified
by metric, not by equality.

Read `evidence-grades.md` first. Every item below carries a grade; the grade is
about the _mechanism_, and each item states separately where its **effect size**
is only `analogy` for your setting. Per-modality instantiation lives in
`modality-map.md` — an item's "Applies to" line names which modalities have a
form of it, not that the same code works everywhere.

Ordered by expected payoff per unit of effort, as observed across the two source
pipelines. Your ordering will differ; re-rank against your own profile.

---

### A1 — Put the derivable structure of the input into a frozen first layer

**Grade** `mechanism` (the transform is computed in closed form; freezing is
checkable) · effect size `measured-elsewhere` on vision, `analogy` elsewhere
**Moves** `steps-to-target` ↓↓, and `time-per-step` ↓ if the freeze is complete
**Radius** `distribution` · **Revert** contained
**Applies to** vision, audio, tabular, time-series, graphs · _not_ discrete-token
text in this form (see A1b)
**Exposure** `neutral` — replaces learned work with derivable work; expected
gain, not a trade

The first layer of most networks spends thousands of steps learning the
second-order statistics of its own input — statistics you can compute in closed
form from a small sample, in one pass, and never touch again. Doing so was the
single largest lever in the source pipeline: it more than halved the epoch count
on its own, more than every other feature combined.

Three separable sub-ideas, portable independently:

1. **Whiten locally, at the granularity the first layer sees.** The covariance is
   over one receptive field, not the whole input, so it is tiny — a `k`-element
   patch over `C` channels gives a `(C·k)²` matrix. Estimating it is cheap and
   massively over-determined from a small sample; do not spend a full pass on it.
2. **Preserve sign information across a half-wave nonlinearity.** If the layer is
   followed by a ReLU-family activation, concatenate the basis with its own
   negation. Otherwise the activation discards half of what you just carefully
   constructed.
3. **Freeze it, completely.** A prefix with no trainable parameter lets autograd
   stop before it — see A8. Partial freezing does not buy this.

Add a small learnable bias to the frozen layer, train it briefly, then freeze
that too. Use a symmetric eigendecomposition (`eigh`), not an SVD: the matrix is
symmetric positive semi-definite by construction. The regulariser added to the
eigenvalues before the inverse square root is the only real knob — it caps how
much near-null directions get amplified.

**Check first.** Is the first layer's input already normalised to something close
to identity covariance? If a data pipeline upstream already whitens, this is a
no-op. Does the input have stable second-order structure at all? For inputs whose
statistics shift across the dataset, a fixed transform is a liability.

**Pitfall.** The statistics must come from the training split only. Computing
them over the full dataset is a real, subtle leak (P11).

---

### A1b — The discrete-input analogue

**Grade** `analogy` · **Moves** `steps-to-target` ↓ · **Radius** `distribution`
**Applies to** text, code, categorical/ID features, retrieval
**Exposure** `neutral` — starts the model at a known optimum of a sub-problem

For discrete token inputs there is no covariance to whiten — the embedding _is_
the first layer, and it is learned. The structurally analogous moves are: tying
input and output embeddings; initialising the unembedding bias from the empirical
token log-frequency, so the model starts by predicting the unigram distribution
instead of learning it; and starting from pretrained embeddings when the token
inventory allows. All three remove work the model would otherwise do with
gradient steps.

The unigram-bias initialisation is `mechanism`-grade in its motivation — the
optimal constant predictor is exactly the unigram distribution, so you are
starting the model at a known optimum of a sub-problem — but its **effect size on
your run is unmeasured** and shrinks as the schedule lengthens.

---

### A2 — Initialise near identity so gradients reach depth on step 1

**Grade** `mechanism` · effect size `measured-elsewhere` (vision CNN)
**Moves** `steps-to-target` ↓ · **Radius** `distribution` · **Revert** trivial
**Applies to** every deep stack, every modality
**Exposure** `neutral` — a starting point, not a constraint on the solution

A deep stack initialised at random must first learn to _transmit_ before it can
learn to compute. Initialising each layer as a partial identity — the first
`min(fan_in, fan_out)` output units as an identity map on the input, the rest at
the default — starts the network as a near-identity function and gets useful
gradient to every depth immediately.

Per family: partial-identity (Dirac) kernels for convolutions; zero-initialised
residual-branch output projections for transformers and ResNets (the family
containing Fixup, ReZero, DeepNet and the standard "zero-init the last norm
gamma" trick); orthogonal or identity-plus-noise for recurrent stacks.

Explicit residual connections are **complementary, not redundant** — the source
pipeline measured a further gain from adding residuals on top of identity init at
its higher quality target. If you have both, keep both.

**Pitfall.** Identity init interacts with weight decay: decaying an identity
initialisation toward zero undoes it during exactly the phase it was meant to
help. Check that your decay excludes, or is small relative to, the identity
component.

---

### A3 — Give each parameter kind an update scale that matches it

**Grade** `mechanism` · effect size `measured-elsewhere` (a 64× bias LR was worth
a quarter of the source pipeline's remaining epochs)
**Moves** `steps-to-target` ↓ · **Radius** `distribution` · **Revert** contained
**Applies to** everything, every modality. **The most transferable item here.**
**Exposure** `neutral` — expected gain; the risk here is a partition bug (P9),
not a trade

Biases, normalisation parameters, embeddings, matrix weights, and the output head
have gradients with different natural magnitudes and different curvature. A
single global learning rate is a compromise across all of them and is optimal for
none. Split them into groups and scale each.

The split that generalises:

| Group                                  | Typical treatment                                                         |
| -------------------------------------- | ------------------------------------------------------------------------- |
| Normalisation biases / shifts          | Substantially higher LR; usually no weight decay                          |
| Normalisation scales                   | Often freezable at 1 entirely (A8) — check redundancy with the next layer |
| Matrix parameters (2-D and reshapable) | The main group; the natural home for a normalised optimiser (A4)          |
| Embeddings / sparse rows               | Their own LR; usually no decay; sparse-aware update if large              |
| Output head / final projection         | Its own LR; interacts strongly with output scale (A9)                     |
| Anything frozen-then-thawed            | Its own schedule, ending where it freezes                                 |

**Check first.** Read the optimiser construction site. If it is
`Optimizer(model.parameters(), lr=...)` with no groups, this item applies and is
usually the cheapest real win in the file.

**Pitfall.** Group membership is usually decided by a name substring. Silently
falling through to the default group is a common and invisible bug — assert that
the group sizes sum to `len(list(model.parameters()))` and that no group is
empty. Also: adding a group changes _nothing_ unless the schedule updates every
group; check the scheduler iterates `param_groups`, not a captured single LR.

---

### A4 — Normalise the update, not just the gradient

**Grade** `mechanism` (the update's spectral scale becomes dimension-free by
construction) · effect size `analogy` outside the settings where it is published
**Moves** `steps-to-target` ↓, `time-per-step` ↑ slightly · **Radius** `distribution`
**Revert** contained · **Applies to** any model with substantial matrix parameters
**Exposure** `unknown` — final quality under a different optimiser family is
uncharacterised here. Dimensions: mean, late-schedule stability

Optimisers in the Muon family replace the raw (momentum) gradient for matrix
parameters with an approximate orthogonalisation of it, computed with a few
matmuls. Two consequences that matter more than the loss curve:

- The update has a **known spectral scale**, so the learning rate stops depending
  on layer dimension — which is why LR warmup can often be removed entirely (A12)
  and why transferring an LR across widths becomes plausible.
- A separate weight-norm constraint becomes a distinct, useful lever: fixing
  `‖W‖` while the update size is fixed keeps the _effective_ step stable.

The approximation deliberately does not converge to an exact orthogonalisation —
in the source, singular values land in a broad band around 1 — and this costs
nothing in quality while saving iterations. Do not "fix" it.

**Check first.** How much of your parameter count is matrix-shaped? For a model
dominated by embeddings or by 1-D parameters, the reachable fraction is small and
so is the win.

**Pitfall.** It does not apply to 1-D parameters, and applying it to embeddings
is its own research question, not a default. Keep those on the vector optimiser
(A3). The orthogonalisation is per-parameter, so a naive implementation launches
one small matmul chain per layer — see B4 before concluding it is too slow.

---

### A5 — Derandomise small-orbit stochastic choices

**Grade** `measured-elsewhere` (a derandomised horizontal flip, measured at n=400
per cell across 16 configurations, was worth an effective 4–38 % speedup — with a
stated boundary condition, below) · mechanism is `mechanism`-grade
**Moves** `steps-to-target` ↓ · **Radius** `distribution` · **Revert** trivial
**Applies to** any augmentation or masking with a small discrete orbit
**Exposure** `neutral` — improves where it applies and is a no-op where it does
not; the boundary condition costs nothing

Sampling an augmentation independently and identically each epoch wastes the same
way with-replacement sampling wastes: over two consecutive epochs, a binary
augmentation applied i.i.d. leaves each example in the same state half the time,
so only `1.5N` of the `2N` reachable inputs are seen. Enumerating the orbit
deterministically instead — random on the first epoch, then strictly alternating —
makes it `2N` at zero cost.

The general principle: **if a stochastic choice has a small discrete orbit,
schedule a deterministic sweep of the orbit rather than sampling it i.i.d.** The
same reasoning already justifies random reshuffling over with-replacement
sampling, which everyone accepts; this is the same argument applied one level
down, inside the augmentation.

**Boundary condition, stated by the source that measured it.** It helps in every
setting where the augmentation itself helps over not applying it at all — **and
nowhere else**. Where an aggressive augmentation policy already saturates input
diversity, derandomising one component of it buys nothing. Two other measured
regularities: adding other augmentation narrows the gain, and inference-time
augmentation narrows it further.

**Check first.** Does the augmentation you are considering actually help? Run the
ablation _off_ before spending effort on derandomising it. This is a two-run
check that frequently deletes the item.

**Pitfall.** Derandomisation couples the augmentation state to the epoch index
and often to the example index, which breaks if your sampler reshuffles across
epoch boundaries or if examples are duplicated within a batch. It also makes runs
correlated across seeds in a way that can _shrink_ apparent seed variance —
do not let that read as improved stability.

---

### A6 — Average the iterates

**Grade** `measured-elsewhere` · **Moves** `steps-to-target` ↓
**Radius** `numeric` at eval time, `none` for training · **Revert** trivial
**Applies to** everything, every modality. Cheapest accuracy per unit compute here.
**Exposure** `neutral` — expected gain. Contraindicated under a non-stationary
distribution (see `modality-map.md`)

Keep an exponential moving average of the weights and evaluate that. Two details
that separate a working implementation from a decorative one:

- **Ramp the averaging.** Near-zero averaging early, when the weights are still
  moving fast; strong averaging late. A schedule of the form `(step/total)^p`
  with `p ≈ 3` is what the source used; a linear ramp works. A constant decay set
  for late training actively hurts early.
- **Average the whole state, including normalisation running statistics**, not
  just the parameters. Averaging weights while leaving stale buffers behind is a
  common half-implementation that produces a worse model than either endpoint.

Update every `k` steps rather than every step (B5), and do one full merge at the
end.

**Conflict, and how to resolve it.** The source _dropped_ iterate averaging when
it moved to a normalised optimiser (A4) with a learning rate decaying to exactly
zero — which is itself a form of averaging. The two are partially redundant.
This is an inference from two configurations, **not a published ablation**: treat
"drop the EMA once you have A4 + decay-to-zero" as `analogy`, and make it your
first measured experiment rather than a default.

---

### A7 — Spend inference compute only where the model is uncertain

**Grade** `measured-elsewhere` (confidence-gated multi-view inference recovered
~2.3 % of a total run's wall-clock at equal accuracy) · `mechanism` for the
gating argument · **Moves** evaluation cost ↓, quality ↑ per unit inference cost
**Radius** `distribution` at the prediction level · **Revert** trivial
**Applies to** everything. Under-exploited in most pipelines.
**Exposure** `bounded` — the gating fraction `q` is the knob. **Exposes
calibration**, measurably and in every configuration tested

Averaging a model's predictions over several augmented or sampled views buys
accuracy at a multiple of inference cost. But confident predictions almost never
change under this treatment, so most of that multiple is spent on inputs whose
answer was already settled. Gate it:

```
1. one cheap forward pass over everything
2. rank by a confidence signal (max prob, margin, entropy, agreement)
3. spend the expensive treatment on the least-confident fraction q only
4. splice the results back
```

Cost drops from `V×` to roughly `1 + q·V×`, and `q` becomes a clean
accuracy/latency dial rather than a binary. The same shape covers every
"spend more compute on hard inputs" mechanism: multi-view test-time augmentation,
multi-sample decoding and self-consistency, MC-dropout, deep ensembles, cascades,
and early-exit networks. All of them gate the same way.

**Pitfall — measured, not speculative.** In the source's own experiment
(n = 10 000 per cell), test-time augmentation **reduced test-set variance but
worsened class-wise calibration** in every configuration tested. If you ship
probabilities, or if a downstream threshold depends on them, this is not free.
Measure calibration alongside accuracy, not after.

**Pitfall.** The confidence threshold and the fraction `q` are hyperparameters.
Tuning them on the test set is the most common leak in this item (P11). Tune on a
held-out split you are not reporting.

---

### A8 — Freeze what has stopped learning, and make the freeze free

**Grade** `mechanism` · **Moves** `time-per-step` ↓, `steps-to-target` neutral-to-↑
**Radius** `distribution` · **Revert** trivial · **Applies to** everything
**Exposure** `bounded` — the freeze point is the knob; freezing too early or
too broadly costs quality

Two distinct wins, often confused:

- **Backward-pass truncation.** If a _contiguous prefix_ of the model has no
  trainable parameter, autograd need not compute input gradients through it at
  all. This is a real, large saving, and it requires the prefix to be _entirely_
  frozen — one trainable bias in the stem forfeits all of it.
- **Optimiser-state elimination.** Frozen parameters need no momentum, no second
  moment, no EMA copy. On a large model this is a memory win that converts into a
  batch-size win.

**Express a freeze as a `detach` in the forward path, not as a mutation of
`requires_grad`.** Mutating a parameter's `requires_grad` mid-run invalidates a
compiled graph and silently changes the optimiser's view of its own state; a
boolean argument that switches a `detach` specialises into two compiled graphs
and then stops.

Also freeze what is _structurally_ redundant rather than merely converged: a
normalisation layer's scale parameter immediately preceding a linear map is
absorbable into that map, so training it adds a degree of freedom that buys
nothing.

**Pitfall.** A schedule attached to a parameter that is about to be frozen must
end at the freeze point. In both source pipelines the frozen parameter's LR
schedule continues past the freeze and goes **negative**; it is harmless only
because the detached parameter's gradient is `None` and the optimiser skips it.
Copy the pattern and you inherit a landmine (P8).

---

### A9 — Set the output scale and loss temperature deliberately at init

**Grade** `mechanism` · **Moves** `steps-to-target` ↓ · **Radius** `distribution`
**Revert** trivial · **Applies to** every softmax head, contrastive temperature,
and regression output
**Exposure** `neutral` — sets a starting condition analytically instead of
spending steps on it

A head initialised without regard to its output magnitude starts the loss either
saturated or flat, and the first hundreds of steps are spent fixing that rather
than learning. Fix it analytically: normalise the head's weights to a known
scale, then divide the logits by a constant chosen so the initial predictive
distribution is close to uniform (classification) or close to the target's
empirical mean and variance (regression).

This interacts tightly with **label smoothing** and with the **loss reduction
convention**. Sum-reduction makes the gradient magnitude proportional to batch
size, which is what makes a "learning rate per N examples" parametrisation (A10)
exact; mean-reduction hides the batch-size dependence inside the LR. Pick one
convention and make the LR parametrisation match it.

**Pitfall.** Output scale, label smoothing, and head learning rate are three
knobs for approximately two degrees of freedom. Tuning them independently wastes
sweep budget; tune the scale first analytically, then the other two.

---

### A10 — Reparametrise hyperparameters so each can be tuned alone

**Grade** `mechanism` (derivable, and re-derived numerically — see below)
**Moves** your _sweep_ cost, not the run · **Radius** `none` when done correctly
**Revert** trivial · **Applies to** everything
**Exposure** `neutral` — a reparametrisation; done correctly it changes no run
at all

Raw optimiser hyperparameters are coupled: raising momentum scales up the
effective step, so the learning rate must be re-tuned; raising the learning rate
scales up a coupled weight decay; changing batch size moves both. Under coupling,
a sweep is an exponential grid. Under a decoupled parametrisation it is a set of
independent one-dimensional scans.

Express the learning rate **per N examples** and the weight decay **per N
examples, decoupled from the learning rate**, dividing both by the optimiser's
own step-amplification factor:

```
amplification A = 1 / (1 - momentum)          # Nesterov or heavy-ball, steady state
lr_impl        = LR_per_N / (N * A)
wd_impl        = WD_per_N * batch / (N * A)   # then wd_impl / lr_impl if the
                                              # optimiser couples decay to lr
```

With sum-reduction, the per-step displacement is then `LR_per_N × (batch/N) × ḡ`
and the per-step decay is `WD_per_N × (batch/N) × w`, both independent of
momentum. That is the whole point.

> **Correction to a widely-copied source.** The source pipelines use
> `A = 1 + 1/(1−m)`. Simulated against the exact update rule at
> `m ∈ {0, 0.5, 0.6, 0.655, 0.825, 0.85, 0.9}` for 20 000 steps with a constant
> gradient, the steady-state amplification is exactly `1/(1−m)` at every value.
> The error is internally harmless — the same constant divides both `lr` and
> `wd`, so it cancels — but the momentum↔LR decoupling it advertises is only
> partial, with residual coupling `1/(2−m)`: moving `m` from 0.6 to 0.9 still
> changes the effective step by 1.27×. **Use `1/(1−m)`.**

**Pitfall.** Adaptive optimisers have a different amplification and their own
coupling between LR, `β₂`, and `ε`. Do not transplant this constant; derive the
one for your optimiser, or measure it with the same ten-line simulation.

---

### A11 — Spend the steps on the examples that carry signal

**Grade** `measured-elsewhere` on clean, curated, balanced data · degrades to
`analogy` — often to _contraindicated_ — elsewhere. Read the pitfalls.
**Moves** `steps-to-target` ↓ · **Radius** `distribution` (maximally)
**Revert** structural · **Applies to** everything, with the largest caveats here
**Exposure** `spending` — **deliberately trades quality for cost.** Exposes
worst-group accuracy and amplifies label noise. Only with headroom and an
explicit floor

Not every example teaches equally at every point in training. Two mechanisms, of
increasing ambition:

- **Within-batch selection.** Forward the full batch, backward only the
  highest-loss or least-confident fraction. Costs one forward, saves most of a
  backward.
- **Proxy-model selection.** Train a much smaller model on the _identical_ seeded
  data stream, record which examples it found hard, and train the full model only
  on those. A cheap model deciding what an expensive model should look at.

**This is the item most likely to be a mistake in your setting.** The failure
modes are severe and none of them show up in mean accuracy on clean data:

- **Label noise amplification.** The highest-loss examples in a real dataset are
  disproportionately _mislabelled_. Hard-example mining is, on noisy data, a
  mislabelled-example amplifier.
- **Worst-group collapse.** Selection reshapes the effective training
  distribution. Mean accuracy can hold while a minority subgroup's accuracy
  falls off a cliff. If you have group labels, this is not optional to check.
- **Data-order coupling.** Proxy selection only replays correctly if augmentation
  and ordering are seeded and reproduced exactly. That coupling is fragile and
  breaks silently when anything upstream changes.
- **Distribution shift at eval.** You trained on a re-weighted distribution and
  are evaluating on the original one.

The source reached for this only at its _higher_ quality target, where it had
accuracy headroom to trade. That is the right posture: **an accuracy-spending
move, not a free speedup.**

---

### A12 — Decay to zero; warm up only if the update is not scale-normalised

**Grade** `mechanism` for the warmup argument, `folklore`-to-`measured-elsewhere`
for schedule-shape preferences · **Moves** `steps-to-target` ↓
**Radius** `distribution` · **Revert** trivial · **Applies to** everything
**Exposure** `bounded` — schedule shape is the knob; removing warmup without
normalised updates costs stability

Ending the learning rate at exactly zero at the last step is near-universal and
close to free. The warmup question is more interesting: warmup exists to survive
early updates whose magnitude is not yet controlled. An optimiser that normalises
its update's scale by construction (A4) removes that failure mode, which is why
the normalised-optimiser configurations in both sources delete warmup entirely
while the plain-SGD configurations keep it.

Rule: **keep a short warmup unless your update magnitude is bounded by
construction, and then measure removing it.** Where a parameter has its own
schedule (a briefly-trained bias, a thawing layer), that schedule ends where the
parameter's training ends — not where the run ends.

---

### A13 — Keep the data stream complete and reproducible under subsetting

**Grade** `mechanism` · **Moves** correctness of every comparison; `steps-to-target`
marginally · **Radius** `none`-to-`distribution` · **Applies to** everything
**Exposure** `neutral` — a correctness property; neglecting it corrupts
comparisons rather than models

Dropping the last partial batch each epoch silently discards up to a batch of
data per epoch and makes the effective dataset depend on batch size — which
corrupts any comparison across batch sizes. Building batches _across_ the epoch
boundary removes the special case entirely.

The stronger property, and the reason this is Tier A rather than housekeeping:
**subsetting should commute with shuffling.** If a subset mask is applied to the
_ordering_ rather than the ordering being recomputed on the subset, then a
subsetted run sees a subsequence of the full run's stream, and the two are
directly comparable. Ablations on data fraction, curriculum, and selection (A11)
are only interpretable when this holds.

---

### A14 — Ramp the input size, not just the learning rate

**Grade** `analogy` (widely used; not measured in the source pipelines, which are
single-resolution) · **Moves** `time-per-step` ↓ early, `steps-to-target` ~flat
**Radius** `distribution` · **Revert** contained
**Applies to** vision (resolution), text (sequence length), audio (duration /
sample rate), video (frames), graphs (neighbourhood radius)
**Exposure** `bounded` — the length of the final full-size phase is the knob.
Exposes anything with a size-dependent inductive bias

Most of the early phase of training does not need full input fidelity. Start
short/small, finish at the deployment size, and spend the saved compute on more
steps. Because cost is typically superlinear in input size — quadratic in
sequence length for attention, quadratic in side length for images — the saving
is concentrated exactly where the model is least able to use the detail.

Two non-negotiables: **finish at the target size** for long enough that the model
adapts, and **evaluate at the target size throughout**, or your curve is
measuring the schedule rather than the model.

**Pitfall.** Anything with a size-dependent inductive bias — positional
encodings, resolution-dependent normalisation statistics, bucketed attention —
has to be told the size is changing. A train/test size discrepancy is a real,
documented effect, not a rounding error.

---

## Reading order when time is short

If you can only act on three items, and you have no profile yet:

1. **A3** — parameter groups. Almost always applicable, cheap, contained.
2. **A6** — iterate averaging. Cheapest quality per unit compute in the list.
3. **A10** — decoupled hyperparameters. Does not speed up the run; speeds up
   every subsequent decision about the run, which is usually the binding cost.

**A1** dominates the source's own ablation but is the most modality-shaped item
here; check `modality-map.md` before spending effort on it.
