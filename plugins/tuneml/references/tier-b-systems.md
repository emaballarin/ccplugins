# Tier B — systems: less wall-clock per step

Changes that move **`time-per-step`** while computing the same thing, or close to
it. Most carry a `none` or `numeric` blast radius, which means they are verified
by **equality or by a profile**, not by spending runs on a metric.

Read `evidence-grades.md` first. Hardware-conditional material is deliberately
quarantined in `hardware-notes.md`, which is written as microbenchmarks to run
rather than numbers to trust.

---

### B1 — Profile before you _prioritise_. A gate on ranking, not on thinking.

**Grade** `mechanism` · **Moves** which of the other items are real
**Radius** `none` · **Applies to** everything
**Exposure** `neutral` — measuring changes nothing. The only item here with no
cost at all

**Existence and magnitude are graded separately.** A finding whose mechanism is
visible in the source — a Python loop over parameters, a synchronising read in
the hot loop, a decode on the per-step path — is `mechanism`-grade _that it is
happening_ and `analogy`-grade _on how much it costs_. Emit it, label both, and
do not pretend the code has to be profiled before it can be read.

What a profile buys is **ordering and size**, and those are exactly what most
optimisation effort is wasted on. So: without one, say once and clearly that the
Tier-B ranking is a prior rather than a measurement, then rank by prior strength
(§B1.1). With one, rank by the profile and let it overrule every prior below it.

Probe P-1 in `hardware-notes.md` is one substitution, takes minutes, and settles
the most common question outright. Offer it before falling back to priors.

Four bottleneck classes, with completely disjoint remedies:

| Bottleneck        | Signature                                                                                                   | Goes to                 |
| ----------------- | ----------------------------------------------------------------------------------------------------------- | ----------------------- |
| **Input**         | Accelerator idle between steps; step time falls when you feed cached/synthetic batches                      | B2, B3                  |
| **Launch/host**   | Kernel time ≪ step time; thousands of tiny kernels; step time barely moves with batch size                  | B4, B6, B9              |
| **Bandwidth**     | Achieved bytes/s near peak while achieved FLOP/s is far from it; elementwise and normalisation ops dominate | B7, B10                 |
| **Compute**       | Achieved FLOP/s near peak in the big matmuls/convolutions                                                   | A-tier, or shapes (B10) |
| **Communication** | Step time scales badly with worker count; gaps at the reduction                                             | B13                     |

Three measurements, in order, that separate these:

1. **Synthetic-input step time.** Replace the loader with a pre-made batch held on
   device and re-time. The gap is your input-pipeline cost, exactly. This one
   substitution answers the most common question in the list and needs no
   profiler.
2. **Kernel time vs step time.** Sum the device-side kernel durations for one
   step and compare to the wall-clock step. A large gap is host overhead,
   synchronisation, or launch-bound work.
3. **Achieved vs peak.** Compute achieved FLOP/s and achieved bytes/s for the
   dominant op and compare to the device's peak for that dtype. Position on the
   roofline tells you whether to attack arithmetic or traffic.

Also record, separately and always: **one-time cost** (import, compile,
autotune, index build, cache fill) versus **steady-state per-step cost**. They
have different remedies and different amortisation, and conflating them is how a
"20 % speedup" turns out to be a 3-minute regression on a single run.

**Timing hygiene.** Warm up first; synchronise before stopping the clock; use
device events rather than host timestamps for device work; report a median and a
spread, never one number. And time the boundary you actually care about — a
measurement that excludes data loading cannot evaluate a data-loading change.

#### B1.1 — Priors worth acting on before a profile

Some Tier-B trends are strong enough to rank on while the profile is still
pending. **Strength here is about how reliably the symptom predicts a real cost,
not about how large that cost is** — a strong prior with a small payoff is still
worth doing first, because it is cheap and certain.

| Prior strength                     | Symptom, readable from the source                                                                   | Item |
| ---------------------------------- | --------------------------------------------------------------------------------------------------- | ---- |
| **Strong** — act without a profile | Per-example decode, resample, or tokenise on the per-step path                                      | B2   |
| **Strong**                         | A Python `for` over parameters, heads, or experts inside the step                                   | B4   |
| **Strong**                         | A scalar read back to the host (`.item()`, a print, a data-dependent branch) every step             | B9   |
| **Strong**                         | A step-unit hyperparameter unchanged after a schedule, batch, or device-count change                | B11  |
| **Strong**                         | Deterministic per-epoch work recomputed per batch                                                   | B3   |
| **Medium** — likely, size unknown  | Mixed dtypes or mixed memory layouts across the step                                                | B7   |
| **Medium**                         | Evaluation never profiled, or run at training batch size and precision                              | B12  |
| **Medium**                         | Ragged shapes reaching a compiled region with no bucketing                                          | B6   |
| **Medium**                         | A constraint, EMA, or diagnostic applied every step whose result changes slowly                     | B5   |
| **Weak** — profile first           | Shape alignment, layout preference, operator substitution                                           | B10  |
| **Weak**                           | Anything multi-device beyond "overlap communication with computation"                               | B13  |
| **Weak**                           | Compilation, when `k` is unknown — the sign of the answer depends on it (`tier-c-protocol.md` C6.7) | B6   |

A **strong** prior is `mechanism`-grade on existence: the symptom _is_ the cost,
and reading the code is sufficient evidence that it is happening. A **medium**
one names a real cost whose size varies enough that ordering against it is a
guess. A **weak** one is `analogy` until measured, and proposing it ahead of a
profile is how audits lose credibility.

Nothing in this table licenses a _magnitude_ claim. "This is happening and it
costs something" is what a prior supports; "this costs 12 %" needs the probe.

---

### B2 — Get the input pipeline off the critical path

**Grade** `mechanism` · **Moves** `time-per-step` ↓ (up to the whole gap from B1.1)
**Radius** `none` · **Revert** contained · **Applies to** every modality, differently
**Exposure** `neutral` — same data, same order, delivered sooner

Only pursue if B1.1 showed a gap. Then, in rough order of leverage:

- **Move the expensive transform off the per-step path.** Decode, resample,
  tokenise, resize, and featurise **once**, offline, into a compact cached form.
  Doing this per-epoch on the fly is the single most common self-inflicted
  bottleneck across every modality.
- **Send the compact representation, expand on the device.** Transfer is usually
  the constraint, not arithmetic: moving `uint8` and converting on-device beats
  moving pre-converted floats. Same argument for packed integer token IDs, for
  compressed audio frames, and for sparse features expanded on-device.
- **Do augmentation on the accelerator, in batch.** Per-example host-side
  augmentation is both slow and un-parallelisable against the step.
- **If the working set fits in device memory, put it there once.** This is not a
  trick, it is a precondition — it applies to small and medium datasets and
  degrades gracefully to "stage the largest shard you can".
- **Otherwise: memory-map, let the page cache work, and size prefetch depth and
  worker count against the measured gap** — not against a folklore number. More
  workers past the point where the gap closes buys nothing and costs memory.

Per-modality specifics — which transform actually dominates — are in
`modality-map.md`.

**Pitfall.** Caching a transform makes it invisible. If the cache key does not
include every parameter of the transform, a changed preprocessing setting will
silently be ignored for as long as the cache lives (P12).

---

### B3 — Compute epoch-invariants once

**Grade** `mechanism` · **Moves** `time-per-step` ↓ · **Radius** `none`
**Revert** trivial · **Applies to** everything
**Exposure** `neutral` — same values, computed once

Anything deterministic and shared across epochs — normalisation, padding,
positional index tensors, attention masks, bucket boundaries, sort orders,
tokenisation — is computed once and reused. Anything stochastic and per-epoch is
computed **once per epoch over the whole tensor**, then sliced into batches,
rather than per batch: one large kernel instead of `steps_per_epoch` small ones,
and shuffling becomes an index permutation rather than a data movement.

**Pitfall.** "Once per epoch over the whole tensor" needs the whole epoch's
augmented copy to fit alongside the original. Check the memory before assuming
the pattern ports.

---

### B4 — Batch the small operations

**Grade** `mechanism` · effect size `measured-elsewhere` (batching a
per-parameter optimiser's internals was the largest single systems win in the
source: ~5 % of total run time) · **Moves** `time-per-step` ↓
**Radius** `numeric` (reduction order changes) · **Revert** contained
**Applies to** everything, and especially to anything iterating over parameters,
heads, experts, or layers in Python
**Exposure** `bounded` — reduction order moves the last bits; the grouping
granularity is the knob

**A Python loop over parameters is a loop over kernel launches.** Each one is a
launch, a schedule, and a synchronisation opportunity, and on a small model the
launches dominate the arithmetic entirely.

Three levels, increasing in effort:

1. **Fused / multi-tensor elementwise ops.** The `foreach`-style primitives and
   fused optimiser implementations turn `P` tiny elementwise kernels into a
   handful of grouped ones. Usually a one-line change with a real win.
2. **Pad-and-stack for heterogeneous shapes.** The reason people give up on
   batching is that layers have different shapes. Pad each reshaped tensor to a
   common size, stack into one higher-rank tensor, run **one batched** operation,
   slice back. The cost is the padding waste; the benefit is one batched matmul
   instead of `P` small ones. This is the non-obvious move and it is what made
   the source's optimiser fast.
3. **Fusing across the step boundary** — grouping optimiser, gradient clipping,
   and EMA into one pass over the parameters instead of three.

Round padded dimensions up to a hardware-friendly multiple (`hardware-notes.md`),
and check that the padding is genuinely inert — that zeros in the pad region
cannot influence the result through a norm, a reduction, or a division.

**Pitfall.** Grouped reductions change summation order, so results move at the
last bits. That is a `numeric` radius, not `none`: do not assert bit-equality
after this change, assert a tolerance and then check the metric across `n` runs.

---

### B5 — Amortise expensive but slowly-varying work

**Grade** `mechanism` · **Moves** `time-per-step` ↓ · **Radius** `numeric`
**Revert** trivial · **Applies to** everything
**Exposure** `bounded` — the interval is the knob, and a periodically-applied
constraint is a weaker guarantee between applications

Work whose _result_ changes slowly does not need to happen every step:
constraint restoration and re-normalisation, EMA updates, gradient-norm logging,
metric computation, checkpointing, evaluation, and any diagnostic. Apply on an
interval — and let the interval widen as training progresses, since late-training
weights move less than early ones.

The source used an interval that grew from every 2 steps to every 17 across the
run, for a weight-norm constraint, at no measured quality cost.

**Pitfall.** Anything whose _purpose_ is to bound a quantity (a constraint, a
clip) becomes a weaker guarantee when applied periodically. Check that the
quantity stays inside its intended range between applications, rather than
assuming it does.

---

### B6 — Compile the step, and count your recompilations

**Grade** `mechanism` · effect size `measured-elsewhere` (whole-model compilation
~14 % in the source; separately compiling the step function a further ~1 %)
**Moves** `time-per-step` ↓, one-time cost ↑↑ · **Radius** `numeric`
**Revert** trivial · **Applies to** everything with a compiler available
**Exposure** `bounded` — fusion and kernel selection move the arithmetic;
precision flags are the knob

Compiling the model alone leaves the loss, the reduction, the casts, and the
optimiser outside the graph. Compile the **step** — forward, loss, and ideally the
backward and optimiser — and require a full graph so that a graph break fails
loudly instead of silently reverting to eager.

Then measure what you actually got:

- **Count recompilations.** Every distinct shape, dtype, or Python-level branch
  that reaches the compiled region is another compilation. A pipeline with ragged
  sequence lengths and no bucketing can recompile hundreds of times and end up
  slower than eager.
- **Bucket dynamic shapes.** Pad to a small set of sizes rather than to the exact
  length. The padding waste is almost always cheaper than the recompilation.
- **Price the one-time cost against `k` runs.** Aggressive autotuning can cost
  minutes. At `k = 1` this item is a _loss_, and the source is explicit that its
  compiled variant exists for amortising over many runs. See `tier-c-protocol.md`
  C6.

**Pitfall.** A graph break that falls back to eager reports success and delivers
nothing. So does a compiled region that is recompiled every step. Both are
invisible unless you look — which is why "did the mechanism actually happen" is a
standing check in `/tml:review` (P5).

---

### B7 — One dtype, one layout — with the reductions kept wider

**Grade** `mechanism` · **Moves** `time-per-step` ↓, memory ↓
**Radius** `numeric` · **Revert** contained · **Applies to** everything
**Exposure** `bounded` — the storage dtype is the knob. **Exposes tails and
reduction accuracy**; very low precision escalates to `spending`

Mixed dtypes insert casts between kernels; mixed memory layouts insert
transposes. Both are invisible in the code and visible in the profile. Pick one
storage dtype and one layout and carry them end to end.

**Three places need more bits than the storage dtype**, and skimping on any of
them is a silent quality loss rather than a crash:

- **Normalisation statistics.** The source that moved these to half precision
  recorded an accuracy loss for it, in its own release notes.
- **Loss and gradient accumulation** — long reduction chains in low precision
  lose the tail.
- **Optimiser state**, especially second moments and any `1/√v` — the dynamic
  range is the problem, not the resolution.

Prefer a wide-exponent 16-bit format over a wide-mantissa one where the hardware
offers it: it removes the loss-scaling machinery and the overflow class of bugs
outright. Very-low-precision formats are a `distribution`-radius change, not a
`numeric` one, and belong in a plan with a quality floor attached.

**Pitfall.** An epsilon tuned for one precision is wrong in another. A
normalisation `ε` small enough to be harmless in 32-bit can be below the
representable range in 16-bit, turning a guard into a division by zero.

---

### B8 — Separate one-time cost from steady state, and reuse the artifact

**Grade** `mechanism` · **Moves** the _measurement_, and `time-per-step` across
repeated runs · **Radius** `none` · **Applies to** everything
**Exposure** `neutral` — the same artifact, built once

Build the expensive artifact once and reuse it: a compiled graph reused across
runs by re-initialising parameters in place rather than reconstructing the model;
a warmup pass on synthetic data before the clock starts; a cached tokeniser,
index, or autotune result persisted across processes.

This is as much a **measurement** discipline as a speed one. Warming up isolates
steady-state throughput from one-time cost, which is what you want to compare —
_provided_ you then price the one-time cost separately and honestly against your
actual `k`. A benchmark that warms up and a production job that runs once are
measuring different things (P13).

---

### B9 — Remove host↔device synchronisation from the hot loop

**Grade** `mechanism` · **Moves** `time-per-step` ↓, sometimes dramatically
**Radius** `none` · **Revert** trivial · **Applies to** everything
**Exposure** `neutral` — removes waiting, not work

Every one of these serialises the pipeline: reading a scalar back to the host,
printing or logging a tensor value, a Python `if` on a tensor, an early-stop
check on a device-resident loss, dynamic shapes derived from data (`nonzero`,
boolean-mask indexing, variable-length gather), and progress bars that format a
metric every step.

The remedies are mechanical: accumulate metrics **on-device** and read them once
per interval (B5); drive learning rates from Python-side step counters, not from
tensors; replace mask-indexing with a fixed-shape masked arithmetic where the
shape must stay static.

**Pitfall.** A single stray `.item()` inside a logging call that only fires "every
100 steps" still costs a synchronisation every 100 steps — but a `.item()` inside
an `f`-string that is _evaluated_ every step and _emitted_ rarely costs one every
step. Check where the read happens, not where the print happens.

---

### B10 — Structural choices that are pure throughput

**Grade** `mechanism` · **Moves** `time-per-step` ↓ · **Radius** `distribution`
(these change the model) · **Revert** contained-to-structural
**Applies to** everything; this is the architecture-as-cost-lever section
**Exposure** `unknown` — these change the model. Quality effect is
uncharacterised until measured on your task

Architecture decisions that buy time without a principled quality cost:

- **Reduce before you normalise.** Any downsampling — pooling, striding, sequence
  reduction — placed _before_ a normalisation makes that normalisation operate on
  proportionally fewer elements, at no modelling cost.
- **Delete structurally redundant parameters.** A bias immediately preceding a
  normalisation layer is absorbed by that layer's shift. A normalisation scale
  immediately preceding a linear map is absorbed by that map. Both are free to
  remove.
- **Align shapes to the hardware's tile size.** Widths, head dimensions, vocab
  sizes, and padded sequence lengths that sit just above a tile boundary pay for a
  whole extra tile. Rounding _down_ to the boundary is frequently free quality and
  strictly cheaper. See `hardware-notes.md`.
- **Keep the fastest-varying dimension contiguous** for the op that dominates.
- **Prefer the cheaper op where the expensive one is not earning its cost.** This
  is where attention variants, grouped/depthwise convolutions, low-rank
  factorisations, and MoE routing belong — as _priced_ choices with a measured
  quality delta, not as defaults.

**Pitfall.** These are `distribution`-radius: they change the model. Cheap to try,
but they must be verified on the metric, and their quality effect is
`analogy`-grade until you measure it on your task.

---

### B11 — Re-derive every step-unit hyperparameter when the step count changes

**Grade** `mechanism` · **Moves** `steps-to-target`, badly, when neglected
**Radius** `distribution` · **Revert** trivial · **Applies to** everything
**Exposure** `neutral` — a correctness fix; **neglecting** it is what costs
quality

**This is a correctness item filed under systems because it is triggered by a
systems change.** Any hyperparameter whose units are _steps_ is silently wrong
after you change the schedule length, the batch size, or the number of devices:

- normalisation running-statistics momentum — a default tuned for thousands of
  steps never converges in a few hundred, and the evaluation-mode model is then
  measurably worse than the training-mode one;
- adaptive-optimiser `β₂` — an effective averaging window longer than the run;
- warmup length, decay horizon, and any `T_max`;
- EMA decay and its update interval (A6);
- patience, cooldown, and early-stopping windows;
- evaluation and checkpoint intervals.

Rule: express these as **fractions of the run** in configuration and convert to
steps once, at the point where the step count is known. Then a schedule change
propagates automatically instead of silently.

This is the first thing to check when a shortened schedule regresses more than
its length would explain.

---

### B12 — Evaluation is part of the pipeline

**Grade** `mechanism` · effect size `measured-elsewhere` (~2.3 % of a total run
from the evaluation path alone, in an already-fast pipeline)
**Moves** `time-per-step` ↓ amortised · **Radius** `none`-to-`numeric`
**Applies to** everything
**Exposure** `bounded` — evaluation frequency is the knob; coarser evaluation
makes early stopping coarser

Evaluation is routinely 20–50 % of a training job's wall-clock and is almost
never profiled. The levers: evaluate less often but on more data (variance falls
as `1/√n`, so frequent tiny evaluations are the worst of both); batch evaluation
larger than training, since there is no optimiser state; run it in inference
precision; compute metrics on-device; and gate expensive inference-time
augmentation by confidence (A7).

**Pitfall.** Evaluating less often makes early-stopping coarser and can cost more
than it saves. And if evaluation is _inside_ the timed region for your headline
number, changing its frequency changes that number without changing the model —
which is score inflation, however unintentional (P1).

---

### B13 — Multi-device: overlap, and pick the right axis

**Grade** `folklore`-to-`mechanism` depending on the item · **Moves**
`time-per-step` ↓, `steps-to-target` ↑ if the effective batch grows
**Radius** `numeric`-to-`distribution` · **Revert** structural
**Applies to** anything past one device. Decision rules only — this is a boundary
of this plugin's scope.
**Exposure** `unknown` — a larger effective batch changes the optimisation
problem. Dimensions: mean, and every step-unit hyperparameter (B11)

- **Gradient accumulation vs a larger batch are not the same thing.** Both grow
  the effective batch; only the second changes the number of optimiser steps per
  epoch. Both push you into A ∩ B, so price end-to-end.
- **Overlap communication with computation** before considering any exotic
  parallelism. Bucketed reductions launched as gradients become ready is the
  standard and usually sufficient remedy for a communication-bound step.
- **Activation checkpointing is a time-for-memory trade with a known shape** —
  roughly one extra forward pass for a large reduction in activation memory. It
  is a _win_ only when the memory it frees is converted into batch size or a
  larger model; otherwise it is a pure slowdown. State the conversion explicitly.
- **Sharding optimiser state, gradients, and parameters** is an increasing
  memory-for-communication ladder. Climb it only as far as the memory forces you.
- **A larger effective batch changes the optimisation problem.** Re-derive the LR
  and every step-unit hyperparameter (B11), and expect `steps-to-target` to move.
  Scaling to `k` devices and reporting `k×` throughput while time-to-target is
  flat is the canonical version of the throughput fallacy.

Anything beyond these decision rules — topology, placement, custom kernels, and
communication libraries — is out of scope for this plugin and should be handled
by someone reading the profile directly.

---

### B14 — Batch size: chosen once, for time-to-target, not for occupancy

**Grade** `mechanism` for the selection rule · `measured-elsewhere` for the
scaling behaviour (`L-SHALLUE18`) · **Moves** both factors, in opposition
**Radius** `numeric` at fixed hyperparameters, `distribution` in effect — because
changing it invalidates the tuning of everything it interacts with
**Applies to** every pipeline
**Exposure** `bounded` — not a quality knob in itself, but a re-tuning trigger
for knobs that are. Dimensions: mean quality, via the optimiser and
regularisation hyperparameters that must be re-tuned with it

**Batch size is not tuned against validation performance.** Given properly tuned
hyperparameters — the optimiser's and the regulariser's especially — and a
sufficient step budget, the same final quality is reachable at any batch size
(`L-SHALLUE18`). Sweeping it for accuracy measures the staleness of your other
hyperparameters, not the batch size.

What it _does_ govern is time and resource consumption, so choose it for
**time-to-target**:

```
time-to-target = steps-to-target × time-per-step
```

Larger batches reduce `steps-to-target` — perfectly, up to a **critical batch
size**, then with diminishing returns, then not at all. Larger batches also
usually raise `time-per-step` somewhat. The best batch size is the one minimising
the product, and finding it is experimental: there is no way to compute it.

**Do not maximise memory occupancy.** "The largest batch that fits" is a
different objective, and it is frequently not the fast one. Run the sweep
(powers of two, plus near neighbours), measure throughput, and take the argmin of
time-to-target — **the optimum is often interior**, at well under full memory,
and that is a legitimate answer rather than a failure to fill the device. Four
mechanisms produce interior optima, all of them common:

- **Allocator pressure near the ceiling** — fragmentation, allocation retries and
  cache-flush cycles degrade throughput non-linearly as free memory approaches
  zero.
- **Workspace starvation** — many fast kernels need scratch space. With little
  free memory the library silently selects a _slower_ algorithm that fits. Same
  batch size, different kernel, worse step time.
- **Tile and wave quantisation** — kernel efficiency is not monotone in batch
  size. A shape leaving a partial final wave wastes a whole wave, so 96 can beat 100. This alone makes "largest that fits" wrong in principle.
- **Headroom is load-bearing** — evaluation wants a batch at least as large as
  training's (`tier-c-protocol.md`), and at 100% occupancy there is nowhere to
  put it. EMA (D8), checkpointing buffers and communication buffers compete for
  the same space.

The apparent conflict with "utilisation" is not a conflict: **occupancy and
utilisation are the datacenter's objective; time-to-target is the researcher's.**
A configuration that looks wasteful per-device and reaches the target sooner is
correct for the second objective, and saying so plainly avoids an argument that
has nothing to do with the experiment.

**Two things that must accompany the rule.**

_Do this once, early._ Changing batch size later means re-tuning most
hyperparameters — the optimiser's and the regulariser's above all — which is
difficult, slow and expensive once a schedule has been tuned around a value
(B11). It is not a knob to revisit casually.

_An interior optimum is a finding, not just a setting._ Record **why** it is
interior. If the cause is fragmentation or algorithm fallback, fixing the
allocator configuration may buy the large batch _and_ the speed; if it is wave
quantisation, it is a property of the shapes and will not be fixed. Reporting
"50% occupancy was fastest" without the reason hands the next person a number
they cannot act on — this is B1's profiling discipline applied to a shape.

**Gradient accumulation / microbatching is not a speed technique.** It simulates
a larger batch than the hardware supports and therefore buys **no throughput**;
`L-PLAYBOOK` advises avoiding it in applied work, and that is the default
position here. The one retained exception: when the memory-permitted batch size
would otherwise be _crucially_ undersized — single digits — **and** lower
gradient variance is genuinely required. That is a variance argument, not a speed
argument, and it should be made in those words.

---

## Reading order when time is short

1. **B1** — profile if you can; if you cannot, take the strong priors in §B1.1
   and say that the ordering is a prior.
2. Whichever of **B2 / B4 / B9** the profile — or §B1.1 — pointed at.
3. **B11** — the correctness check that every schedule change silently needs.
