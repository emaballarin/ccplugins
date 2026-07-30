# Modality map

Which tier items have a form in your modality, what that form is, and which input
transform dominates the pipeline cost. Consult before proposing any item marked
modality-sensitive — most of the algorithmic tier's _mechanisms_ are universal
while their _instantiations_ are not, and proposing a vision recipe for a text
pipeline is the fastest way to lose an operator's trust.

Everything here is `analogy`-grade for effect size unless your own measurement
says otherwise. The mechanism transfers; the number does not.

---

## A-tier applicability at a glance

`✓` has a direct form · `~` has a weaker or conditional form · `✗` does not apply
· `!` applies but is contraindicated by default

| Item                               | Vision | Text/tokens | Audio | Tabular | Graph | Time-series | RL  |
| ---------------------------------- | :----: | :---------: | :---: | :-----: | :---: | :---------: | :-: |
| A1 frozen data-derived input layer |   ✓    |   ✗ → A1b   |   ✓   |    ✓    |   ✓   |      ✓      |  ~  |
| A2 near-identity init              |   ✓    |      ✓      |   ✓   |    ✓    |   ✓   |      ✓      |  ✓  |
| A3 parameter-group update scales   |   ✓    |      ✓      |   ✓   |    ✓    |   ✓   |      ✓      |  ✓  |
| A4 normalised (matrix) updates     |   ✓    |      ✓      |   ✓   |    ~    |   ✓   |      ✓      |  ~  |
| A5 derandomised augmentation       |   ✓    |      ~      |   ✓   |    ~    |   ~   |      ~      |  ✗  |
| A6 iterate averaging               |   ✓    |      ✓      |   ✓   |    ✓    |   ✓   |      ✓      |  !  |
| A7 confidence-gated inference      |   ✓    |      ✓      |   ✓   |    ✓    |   ✓   |      ✓      |  ~  |
| A8 freeze converged prefixes       |   ✓    |      ✓      |   ✓   |    ✓    |   ✓   |      ✓      |  ✓  |
| A9 output scale / loss temperature |   ✓    |      ✓      |   ✓   |    ✓    |   ✓   |      ✓      |  ✓  |
| A10 decoupled hyperparameters      |   ✓    |      ✓      |   ✓   |    ✓    |   ✓   |      ✓      |  ✓  |
| A11 hard-example selection         |   ~    |      ~      |   ~   |    !    |   ~   |      ~      |  ~  |
| A12 decay to zero / warmup rule    |   ✓    |      ✓      |   ✓   |    ✓    |   ✓   |      ✓      |  ~  |
| A13 complete, reproducible stream  |   ✓    |      ✓      |   ✓   |    ✓    |   ✓   |      ✓      |  ~  |
| A14 input-size ramp                |   ✓    |      ✓      |   ✓   |    ✗    |   ~   |      ✓      |  ~  |

Two `!` entries are deliberate. A11 on tabular data is contraindicated by
default: tabular datasets are the ones most likely to carry label noise and
protected subgroups, which is exactly the combination hard-example mining
damages. A6 in RL is contraindicated because the data distribution is
non-stationary by construction, so averaging across a policy change averages
across different problems.

---

## Per modality

### Vision — images, video

- **A1** — whiten local patches at the first layer's receptive field; the
  covariance is small (channels × patch size, squared). Concatenate the basis with
  its negation before any ReLU-family activation. Video adds a temporal axis to
  the patch; the argument is unchanged.
- **A5 orbit** — horizontal flip is the classic small orbit. Also: the four/eight
  element rotation-reflection group where the task is orientation-invariant,
  discrete crop positions, and channel permutations where physically meaningful.
- **A14** — progressive resizing. Cost is roughly quadratic in side length.
- **Input cost dominated by** decode (JPEG/PNG) and resize, usually by a wide
  margin over everything else. Pre-decode to a fixed-size raw or compact tensor
  format and the input bottleneck typically disappears. Augment on-device.
- **Watch** — normalisation statistics computed over train+test; resize
  interpolation differing between train and eval; augmentation left active at
  evaluation.

### Text, code, token sequences

- **A1 does not apply** in its covariance form: the input is discrete and the
  embedding is the first layer. Use **A1b** — tie input/output embeddings,
  initialise the output bias from empirical token log-frequency so the model
  starts at the unigram optimum, and start from pretrained embeddings when the
  inventory allows.
- **A5 orbit** — the strong case is _masking_: an MLM-style mask sampled i.i.d.
  per epoch has exactly the redundancy A5 describes, and a deterministic sweep
  that guarantees each position is masked once per `1/p` epochs is the direct
  analogue. Weaker cases: dropout mask antithesis, span-corruption offsets,
  negative-sample scheduling. Token-level "augmentation" (synonym swap, back
  translation) is usually not a small orbit.
- **A14** — sequence-length curriculum. Cost is quadratic in length for dense
  attention, so the early saving is large. Positional encodings must handle the
  change (A14's pitfall applies hard here).
- **Input cost dominated by** tokenisation, and by padding waste. Pre-tokenise
  offline; **pack** sequences to a fixed length rather than padding each to the
  batch maximum — this is frequently a larger win than anything in B4, and it is
  an input-pipeline change, not a modelling one.
- **Watch** — packing changes what "one example" means, so loss reduction and
  metric denominators must be re-derived; and length bucketing interacts with
  compilation (B6).

### Audio, speech

- **A1** — a fixed filterbank or learned-then-frozen front end; per-band
  normalisation over the training distribution. The whitening argument applies to
  spectrogram patches exactly as to image patches.
- **A5 orbit** — small discrete sets only: channel swap for true stereo, a fixed
  set of time shifts, a fixed set of speed/pitch factors. Time reversal is a real
  orbit for some tasks and destroys others; check before assuming.
- **A14** — duration and sample-rate curriculum.
- **Input cost dominated by** decode and resample, then featurisation. Pre-resample
  offline; featurise on-device in batch if the features are cheap, offline if not.
- **Watch** — silence padding entering normalisation statistics; augmentation that
  changes duration interacting with a length-bucketed batcher.

### Tabular

- **A1** — this is where whitening is most literal and most under-used: per-feature
  standardisation plus a full-covariance whitening of the numeric block, computed
  on the training split, frozen. Cheap, closed-form, and often worth more than an
  architecture change.
- **A5 orbit** — weak. Most tabular augmentation is continuous (noise, mixup) and
  has no small orbit. Categorical dropout patterns are the exception.
- **A11 contraindicated by default** — see above.
- **Input cost dominated by** row-wise access patterns. Columnar storage, whole-
  tensor residency, and integer-encoded categoricals; the entire dataset usually
  fits in device memory, which makes B2's strongest form available.
- **Watch** — target leakage through any statistic computed over the full dataset
  (encodings, imputation, scaling); subgroup performance under any selection.

### Graphs

- **A1** — frozen spectral or structural positional encodings, computed once.
  Degree/feature normalisation is the local-whitening analogue.
- **A5 orbit** — node permutations are not a small orbit; discrete edge-dropout
  patterns and canonical-orientation choices sometimes are.
- **A14** — neighbourhood radius / sampled-fanout curriculum.
- **Input cost dominated by** neighbourhood sampling and gather. Precompute
  sampled neighbourhoods; sort by degree to reduce ragged work; this is a heavy
  B9 case (dynamic shapes everywhere).
- **Watch** — transductive leakage through encodings computed over the whole graph
  including test nodes.

### Time series, sensors

- **A1** — a fixed basis (Fourier, wavelet) or per-channel whitening as a frozen
  stem; per-channel standardisation using **causal, training-window** statistics.
- **A5 orbit** — discrete lag offsets, channel permutation where channels are
  exchangeable, sign flip where the signal is sign-symmetric.
- **A14** — context-window length curriculum.
- **Input cost dominated by** windowing and stride materialisation. Materialise
  windows as strided views rather than copies wherever the framework allows.
- **Watch** — any statistic computed across the forecast boundary is leakage;
  shuffling that breaks a temporal split.

### Reinforcement learning and other non-stationary settings

Most of this plugin assumes a fixed data distribution and a fixed objective.
Under a moving distribution:

- **A6 iterate averaging is contraindicated** by default — averaging across a
  policy shift averages across different problems.
- **C2's noise floor is much larger** and much more skewed; expect to need
  substantially more seeds, and prefer robust centre statistics.
- **Throughput matters more than usual** because the environment step can be the
  bottleneck and is often CPU-bound — but the throughput fallacy still applies:
  measure return at fixed environment-interaction budget, not steps/second.
- **B1's synthetic-input substitution** still works and is still the fastest way
  to separate environment cost from learner cost.

---

## Multimodal and retrieval pipelines

Treat each tower separately for Tier A — they have different input statistics,
different natural learning rates (A3), and different frozen-prefix opportunities
(A8, often a wholly frozen encoder). Treat the _joint_ objective's temperature as
a single A9 decision. For Tier B, the binding constraint is usually the slowest
tower's input pipeline plus any cross-tower synchronisation; profile the towers
separately before the whole (B1).

---

## When the modality is not listed

Answer four questions, and the map follows:

1. **Is the input continuous with stable second-order structure?** If yes, A1
   applies in some form. If it is discrete, go to A1b.
2. **Does any augmentation or masking have a small discrete orbit?** If yes, A5
   applies. If the randomness is continuous, it does not.
3. **Is there a natural notion of input size that can be ramped?** If yes, A14.
4. **What is the single most expensive per-example transform?** That is your B2
   target, and it is almost always worth moving offline.

Items A2, A3, A6–A10, A12 and A13 apply everywhere. They are the portable core.
