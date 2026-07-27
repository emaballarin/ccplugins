# Pitfalls — how a speedup breaks something silently

Every entry has the same shape: **symptom** (what you see), **mechanism** (why),
**detection** (the specific check that settles it). None of these announce
themselves; each one reports success while doing damage.

`/parml:review` walks this list against a diff. `/parml:audit` attaches the
relevant entries to each finding. If you read only one, read **P3** — it is the
most expensive mistake in the field and the one a dashboard actively encourages.

---

### P1 — Score inflation: the measurement moved, not the model

**Symptom.** The number improved and nothing about the model explains it.
**Mechanism.** The thing being optimised was also allowed to be edited. A
loosened tolerance, a dropped hard case, a shorter evaluation set, a widened
early-stopping window, a changed metric denominator, a re-drawn split — all read
as progress. This needs no bad intent; it is the default outcome of optimising a
number you can also define.
**Detection.** Diff the harness, the metric, the split, and the evaluation code
between the two arms. Any change there ends the comparison: re-baseline and open
a new segment (`tier-c-protocol.md` C3). If evaluation sits inside your timed
region, changing its _frequency_ is also this pitfall.

---

### P2 — Dead knobs in a tuned or auto-generated configuration

**Symptom.** A configuration contains a carefully-named parameter, schedule, or
annealing curve that does nothing.
**Mechanism.** A later operation erases the earlier one. The concrete measured
case: a magnitude target annealed from `0.50` to `0.079` over training, applied
by scaling a tensor to that norm — and then immediately followed on the next line
by an unconditional renormalisation to unit norm. The schedule's total effect on
what the downstream computation receives is a swing of about `1×10⁻⁴` relative
across the entire run, invariant to the input magnitude. It is a no-op wearing
the clothes of a hyperparameter.
**Detection.** For every knob you inherit, **set it to two extreme values and
check the output changes**. Sweeps and searches produce dead knobs routinely, and
they survive because nobody tests that the parameter is load-bearing. Do this
before porting a tuned config and before spending any sweep budget on a knob.

---

### P3 — The throughput fallacy

**Symptom.** Samples/sec, tokens/sec, or MFU improved; time-to-target did not, or
got worse.
**Mechanism.** `time-to-target = steps-to-target × time-per-step`, and a change
can move the two in opposite directions. Larger batches, reduced precision,
aggressive packing, dropped augmentation, and more devices all raise throughput
while potentially raising the number of steps needed. A 30 % throughput gain
alongside a 40 % loss-per-step regression is a regression that every dashboard
reports as a win.
**Detection.** **Never accept a throughput number as a result.** Measure
time-to-target-quality, or measure both factors and show the product. Throughput
is a diagnostic for locating a bottleneck and nothing else. Same for FLOPs: both
source pipelines contain changes that cut FLOPs without cutting wall-clock.

---

### P4 — Step-unit hyperparameters left stale after a schedule change

**Symptom.** A shortened, lengthened, or re-batched run regresses by more than
its length explains. Often: evaluation-mode quality is far below training-mode
quality.
**Mechanism.** Anything with units of _steps_ is now wrong — normalisation
running-statistics momentum, adaptive `β₂`, warmup length, decay horizon, EMA
decay and interval, patience, cooldown, evaluation and checkpoint intervals. A
running-statistics momentum tuned for thousands of steps never converges in a few
hundred, so the buffers used at evaluation are near their initial values.
**Detection.** Grep the config for every step-valued parameter and re-derive each
against the new step count. Symptom-level check: if train-mode and eval-mode
quality diverge sharply, suspect the normalisation buffers first. Express these
as fractions of the run in configuration (`tier-b-systems.md` B11) and the class
of bug disappears.

---

### P5 — The optimisation that never happened

**Symptom.** The change is in, the code is correct, and nothing got faster — or it
got slower.
**Mechanism.** The mechanism silently did not engage. A compiled region fell back
to eager on a graph break; it recompiled on every step because a shape or a
Python-level branch varied; a fused path rejected the dtype and took the generic
one; a "device-resident" tensor was being copied back each step; a frozen prefix
still had one trainable parameter, so the backward pass still traversed it.
**Detection.** Verify the mechanism directly, never by the end-to-end number
alone: require a full graph and let a break raise; count recompilations; confirm
the fused kernel was actually selected; assert the frozen prefix has zero
parameters with gradients enabled. `/parml:review` treats "did the claimed
mechanism happen" as a standing check for exactly this reason.

---

### P6 — A distribution-radius change verified only on the mean

**Symptom.** Mean quality held, so the change was accepted. Something else moved.
**Mechanism.** A change that alters what is trained or predicted can hold the
mean while moving calibration, worst-group accuracy, robustness under shift, tail
latency, or the error _distribution_. The measured example: inference-time
augmentation reduced test-set variance while worsening class-wise calibration in
every configuration tested, at n = 10 000 per cell. Data selection, distillation,
quantisation, early exit and aggressive precision reduction share this shape.
**Detection.** Decide _before_ the run which quality dimensions are constraints
(`tier-c-protocol.md` C1) and measure those, not just the headline. At minimum,
alongside the mean: the spread, a calibration measure if you ship probabilities,
and per-group accuracy if you have group labels.

---

### P7 — Train/eval mismatch introduced by the optimisation

**Symptom.** Training metrics look fine; evaluation is inexplicably worse, or
suspiciously better.
**Mechanism.** An optimisation touched one path and not the other. Augmentation
left enabled at evaluation; dropout or normalisation left in the wrong mode
because a compiled or refactored path bypassed the mode switch; different padding,
resizing, or tokenisation between the two paths; evaluation running at a
precision or input size the model never trained at; an averaged-weights copy used
for one path and not the other.
**Detection.** Run the _evaluation_ path on a slice of _training_ data and compare
with the training-time metric on the same slice. They should agree closely. This
one check catches most of the class and takes a minute.

---

### P8 — A schedule that outlives its parameter

**Symptom.** Nothing — until a refactor makes it visible, and then something
diverges.
**Mechanism.** A parameter is frozen partway through training, but its learning
rate schedule is written against the full run and keeps evaluating past the
freeze point — going to zero and then negative. In both source pipelines this is
harmless _only_ because the detached parameter's gradient is `None` and the
optimiser skips it. Change how the freeze is expressed, or reorder the loop, and
a negative learning rate becomes live.
**Detection.** Assert every group's learning rate is non-negative every step —
one line, no cost. Any schedule attached to a parameter that stops training must
terminate where the parameter does.

---

### P9 — Parameter partition fallthrough

**Symptom.** A parameter-group change (A3) produced no effect, or an unexpected
one.
**Mechanism.** Groups are usually selected by a name substring, so a renamed
module silently falls into the default group; or a parameter lands in two groups;
or a group is empty; or the scheduler updates a captured learning rate instead of
iterating `param_groups`, so the new groups never see a schedule. Related: an
optimiser designed for matrix parameters silently receiving 1-D ones.
**Detection.** Assert the group sizes sum to the total parameter count, that the
intersection of any two groups is empty, that no group is empty, and that every
group's learning rate actually changes across steps. Print the partition once at
startup — it is four lines and it makes the whole class visible.

---

### P10 — Precision-induced silent degradation

**Symptom.** No crash, no `NaN`, slightly worse quality that never recovers.
**Mechanism.** A reduction, a statistic, or an optimiser state lost its tail in
low precision. Long accumulation chains, normalisation statistics, and second
moments are the three usual sites. Separately: an epsilon tuned for one precision
can fall below the representable range in another, turning a guard into a
division by zero; and a narrow-exponent format silently saturates where a
wide-exponent one would not.
**Detection.** Keep reductions, normalisation statistics, and optimiser state
wider than the storage dtype (`tier-b-systems.md` B7), and diff quality over `n`
runs rather than one — this pitfall is usually within one run's noise and only
visible in the mean. Check the loss _tails_, not just the final number.

---

### P11 — Leakage through a statistic or a threshold

**Symptom.** Results that do not reproduce on genuinely held-out data.
**Mechanism.** Something was fitted on data it should not have seen. Normalisation
or whitening statistics computed over the whole dataset rather than the training
split (A1's own pitfall); encodings or imputation fitted before the split; a
confidence threshold or gating fraction (A7) tuned on the test set; an
early-stopping point selected on the reported set; a data-selection criterion
(A11) derived from test predictions; transductive features computed over a whole
graph including test nodes.
**Detection.** Every fitted quantity — statistic, encoding, threshold, stopping
point, selection rule — names the split it was fitted on. Anything tuned must be
tuned on a split you are not reporting. This is the pitfall most likely to
invalidate a result completely rather than partially.

---

### P12 — A stale cache makes a change invisible

**Symptom.** A preprocessing or augmentation change has no effect at all.
**Mechanism.** The transform was cached (B2, B3) and the cache key does not
include the parameter that changed, so the old artifact is served indefinitely.
Amplified when the cache is shared across experiments or machines.
**Detection.** Hash every parameter of the transform into the cache key, and
record the key in the run's metadata. Sanity check: change a parameter to an
absurd value and confirm the output changes.

---

### P13 — The timing boundary excludes what you optimised

**Symptom.** A large measured speedup that does not show up in the job's actual
duration.
**Mechanism.** The clock did not cover the whole pipeline. Kernel time measured
instead of step time; data loading outside the region; evaluation, checkpointing,
or compilation excluded; the warmup pass absorbing a cost that a real single run
would pay. Warming up before timing is legitimate and necessary for comparing
steady state — it is _not_ legitimate to then quote the warmed number as the cost
of a one-shot job (`tier-c-protocol.md` C6.7).
**Detection.** Time end to end — from first data access to final output — at least
once, and reconcile it against the sum of your components. Report one-time cost
and steady-state cost separately, with the `k` you amortised over.

---

### P14 — Nondeterminism read as improvement

**Symptom.** A change looked good once and evaporates on repetition.
**Mechanism.** A single run compared against a single baseline run, with a
between-run spread larger than the effect. Detecting a `δ` improvement at usual
significance needs on the order of `16σ²/δ²` runs; below about `σ/3`, one run
cannot distinguish anything (`tier-c-protocol.md` C2). Worse, seeded runs that
_look_ deterministic can be identical for the wrong reason — a seed that is
ignored manufactures false confidence by returning the same number every time.
**Detection.** Never decide on `n = 1`. Measure the floor first. Verify the seed
actually varies the result before trusting a seed sweep — if three seeds return
identical values, the seed is not wired up, and that is a broken harness rather
than a stable one.

---

### P15 — Data-order coupling

**Symptom.** A selection, curriculum, or replay mechanism degrades after an
unrelated upstream change.
**Mechanism.** The mechanism depends on the exact data stream being reproducible —
a proxy model's per-example decisions replayed against the main model (A11), a
derandomised augmentation keyed to the epoch and example index (A5), a cached
mask sequence. Any change to sampling, sharding, worker count, batch size, or
device count silently desynchronises it, and the mechanism keeps running against
the wrong examples.
**Detection.** Assert the coupling rather than assuming it: record a checksum of
the example-index sequence and compare it between the two runs that are supposed
to share it. Make the stream complete and subsettable in a commuting way
(`tier-a-algorithmic.md` A13) so that the property is structural rather than
incidental.

---

## Using this list

- **In an audit** — attach the relevant entries to each finding, and let a
  finding's pitfall count feed its risk, not just its effort.
- **In a review** — walk P1, P3, P5, P6 and P13 against every diff, then whichever
  others the diff touches. Those five cover the cases where the change _appears_
  to have worked.
- **Before porting a tuned configuration** — P2 and P4, always. Inherited configs
  carry dead knobs and stale step-units as a matter of course.
