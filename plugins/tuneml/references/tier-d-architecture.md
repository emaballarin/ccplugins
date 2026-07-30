# Tier D — architecture and numerics: what the model is made of

Changes to the model itself and to the arithmetic it runs in. Distinct from Tier
A (which changes the optimisation trajectory over a fixed model) and Tier B
(which changes the cost of a step without changing what is computed): a Tier-D
change usually moves **both** factors and frequently changes what "the model" even
denotes, so it is priced end to end and never on one factor.

`L-PLAYBOOK` deliberately scopes this out — its advice is to reuse an
architecture that already works and spend the budget on tuning. That advice is
correct as a default and this tier does not overturn it: **most projects should
take a well-established architecture and stop**. What follows is for when the
architecture is genuinely in play, or when it is the thing that is broken.

Read `evidence-grades.md` first.

---

### D1 — Normalisation placement: pre-norm by default

**Grade** `mechanism` for the gradient argument · `measured-elsewhere` for the
scaling evidence · **Moves** `steps-to-target`, and whether training completes at all
**Radius** `distribution` · **Applies to** any residual stack, transformers especially
**Exposure** `bounded` — placement changes the function class; the knob is the
placement itself, and both options are trainable under the right conditions.
Dimensions: mean quality, training stability, late-training gradient behaviour

**Pre-norm** puts the normalisation _inside_ the residual branch:
`x' = x + Sublayer(Norm(x))`. **Post-norm** puts it on the sum:
`x' = Norm(x + Sublayer(x))`.

The difference is not aesthetic. In pre-norm the block Jacobian contains an
**identity term** — the residual stream passes through additions only, so a
full-strength gradient path reaches every earlier layer regardless of what the
sublayer does. In post-norm the LayerNorm Jacobian gates **every** path including
the residual one, and those per-layer factors compound multiplicatively with
depth. That is the whole argument, it is `mechanism`-grade, and it is why
pre-norm tolerates larger learning rates and can drop warmup entirely
(`L-XIONG20`).

**Default to pre-norm.** It is what made frontier-scale stacks trainable
(`L-VASWANI17` was post-norm at 6+6 layers; the transition happened as depth
grew).

Its costs, which are real and must be stated:

- The block output is **not** normalised, so the residual stream grows in
  magnitude with depth. A **final normalisation before the output head** is
  therefore mandatory, not optional.
- That growth makes numerical precision matter more in very deep stacks (D7).
- Residual output projections should be initialised down by a depth-dependent
  factor — `1/√(2n)` for `n` blocks with two sublayers each is the standard
  choice — or the accumulated sum starts too large (D2).

**Post-norm is not untrainable, and the quality question is open.**
`source-uncertainty`, deliberately:

- `L-DEEPNET` trains **1000-layer** post-norm transformers via depth-scaled
  residuals (DeepNorm) plus a derived initialisation, explicitly to get
  "good performance of Post-LN and stable training of Pre-LN".
- `L-OLMO2` reorders the norm to the sublayer **outputs** and reports improved
  gradient-norm growth and spikiness, combined with QK-norm (D5).
- `L-PERILN` revisits the placement question directly.

So the honest statement is: pre-norm is the default because it is stable and
cheap to get right; post-norm variants remain competitive on final quality when
their stabilisation is done properly, and that is an active area. Anyone claiming
the question is settled in either direction is overstating.

**What to refuse.** Do not accept simulated evidence for this item. Illustrative
code that hard-codes a divergence threshold and then plots divergence above it
demonstrates nothing; several widely-read explainers do exactly that. Grade such
material `mechanism` at most, never `measured-here`.

---

### D2 — Residual connections, and starting the branch near zero

**Grade** `measured-elsewhere` (`L-HE16`) · **Moves** `steps-to-target`
**Radius** `distribution` · **Applies to** depth ≳ 10
**Exposure** `neutral` — this is close to a free win and among the best
effort-to-effect changes available. Dimensions: none expected

`y = F(x) + x` every few same-shaped blocks. Ensures gradient flow, and lets
depth be added incrementally rather than all at once.

Two ways to keep the sum well-scaled at initialisation, either of which works:

- **Normalise the addition by `√2`** — variance-preserving when the two branches
  are independent and unit-variance.
- **Initialise the residual branch so its output is ≈ 0**, making each block start
  as an identity map.

The second generalises: a block that begins near-identity is a block that cannot
destabilise the stack before it has learned anything, and it is the same
principle as the depth-scaled initialisation in D1 and the near-identity
initialisation in `tier-a-algorithmic.md`.

---

### D3 — Activation units: scalar criteria, and the gated families

**Grade** `mechanism` for the criteria · `measured-elsewhere` for which variant
wins (`L-SHAZEER20`) · **Moves** `steps-to-target`, and `time-per-step` slightly
**Radius** `distribution` · **Applies to** any architecture
**Exposure** `bounded` — the knob is the choice itself, and matched-capacity
comparison keeps it honest. Dimensions: mean quality

Two levels, because the modern default is not a pointwise function at all and
criteria written for a scalar `f` do not type-check against it.

**Level 1 — the scalar nonlinearity `σ`**, used pointwise _or_ as a gate:

- `σ` continuous;
- `σ'` bounded and **mostly non-zero** — this is what rules out a dead half-domain;
- `lim_{x→−∞} σ(x) = c`, finite;
- `lim_{x→+∞} σ(x) ~ x` **when `σ` acts pointwise**. A `σ` used _as a gate_ may
  instead saturate to a finite constant.

The last clause is the necessary relaxation: the original GLU gates with a
**sigmoid**, which fails the pointwise criterion and is perfectly correct as a
gate, because the parallel _linear_ branch carries the magnitude. SiLU/Swish,
GELU and Mish satisfy the pointwise form; SwiGLU and GEGLU inherit it through
their gates.

**Level 2 — the unit `U`**, whatever sits between two linear maps:

- `U` admits a **near-linear regime**. This is the real content of `σ(x) ~ x`,
  and it generalises: a GLU with a saturated gate degenerates to a linear map.
  Same property as near-identity residual init (D2).
- `U`'s Jacobian is **bounded** over the operating range — for a gated unit,
  checked on the _product_, not on `σ` alone.
- **Multiplicative interaction is a capability, not a defect.** The product of
  two learned projections expresses a degree-2 interaction no pointwise map can.
- **Compare at matched parameters and FLOPs.** GLU variants use three projections
  where a standard FFN uses two, so `L-SHAZEER20` states verbatim that "to make
  the parameter count and FLOP counts match the baseline, we reduce the hidden
  dimension `d_ff` by a factor of 2/3". Swapping FFN→SwiGLU **without** shrinking
  changes capacity and activation simultaneously, which is precisely the unfair
  comparison `hyperparameter-roles.md` exists to prevent.

`source-uncertainty` on _why_ gating helps: `L-SHAZEER20` offers no mechanism and
closes by hoping the results encourage future work on gating. Its advantage is
`measured-elsewhere` and has never been promoted to `mechanism`.

---

### D4 — Normalisation family: prefer stateless

**Grade** `mechanism` for the state argument · **Moves** `time-per-step`, and
`steps-to-target` indirectly
**Radius** `distribution` · **Applies to** anything currently using BatchNorm
**Exposure** `bounded` — BatchNorm sometimes regularises, and removing it can
cost that. Dimensions: mean quality, and train/eval consistency

General form `y = a · (x − μ)/σ + b`, differing in what the statistics are
reduced over:

| Layer            | Reduces over                                      |
| ---------------- | ------------------------------------------------- |
| **BatchNorm**    | the batch **and** spatial dimensions, per channel |
| **LayerNorm**    | all features of one example                       |
| **GroupNorm**    | a group of channels, per example                  |
| **InstanceNorm** | spatial dimensions, per channel per example       |
| **RMSNorm**      | as LayerNorm with `μ = 0` — no mean-centring      |

**FiLM is not on this list as "learnable `a` and `b`".** `a` and `b` are already
learnable in every entry above. FiLM (`L-PEREZ18`) is the case where they are
**predicted from a conditioning input** — it is a conditioning mechanism, not a
normalisation variant, and filing it as the latter loses the only thing that
distinguishes it.

**Prefer stateless normalisation**, i.e. avoid BatchNorm where a choice exists:
it introduces a dependency between examples in a batch, and it carries extra
state that must be maintained and synchronised at test time. `L-PLAYBOOK` agrees
that batch norm can often be replaced by LayerNorm, and separately documents the
traps if it cannot be — decoupling the statistics batch from the gradient batch,
ghost-batch-norm implementations mishandling per-device batch > virtual batch,
and EMAs that are never synchronised across hosts before checkpointing.

---

### D5 — QK normalisation for large-model stability

**Grade** `measured-elsewhere` (`L-DEHGHANI23`, `L-OLMO2`) · **Moves** whether
training survives at the learning rate you want
**Radius** `distribution` · **Applies to** large transformers
**Exposure** `neutral` — reported as stabilising with no quality cost.
Dimensions: none reported; not independently characterised here

Normalising queries and keys before the attention product bounds the attention
logits, which removes a specific and common failure mode: unbounded logit growth
producing loss spikes and divergence. `L-OLMO2` reports it as part of the
combination that improves both the growth and the spikiness of the gradient norm,
and identifies attention-logit explosion as the mechanism behind post-norm's
instability specifically.

Reached from `instability.md` §5 when the workload is a large transformer.

---

### D6 — Match the inductive bias to the structure in the data

**Grade** `mechanism` · **Moves** `steps-to-target`
**Radius** `distribution` · **Applies to** data with known structure
**Exposure** `neutral` — usually a gain. Dimensions: generalisation under the
assumed symmetry, if the symmetry assumption is wrong

Use the model class whose bias matches the data — convolutional for images,
graph models for graph-structured data — and where a symmetry is genuinely
present, build it in:

- **Invariance**: `F(Gx) = F(x)`.
- **Equivariance**: `F(Gx) = G'F(x)` — e.g. group convolutions (`L-COHEN16`).

Transformers are **topologically unbiased**: they are set models over tokens, and
any structure comes from the embeddings (positional encodings among them). That
is a strength when the structure is unknown and a cost when it is known and
cheap to encode.

---

### D7 — Reduced-precision arithmetic

**Grade** `mechanism` · **Moves** `time-per-step` primarily, memory secondarily
**Radius** `numeric` · **Applies to** any accelerator with reduced-precision units
**Exposure** `bounded` — the knob is which operations stay in high precision.
Dimensions: numerical stability, reduction accuracy, determinism

**The dominant benefit is speed, not memory.** Reduced-precision matmul
throughput on tensor-core-class hardware is a multiple of fp32, and framing this
as a memory-saving measure understates it badly enough to mis-price it. Memory is
a real second benefit, and it is what buys larger batches (B14).

**fp16 and bf16 are not interchangeable.** bf16 carries fp32's exponent range and
generally needs **no loss scaling**; fp16 has a much narrower exponent range and
generally does, because small gradients underflow. Prescribing loss scaling
generically prescribes a workaround for a problem half the cases do not have.

Compensations, applied to the cases that need them: loss scaling / rescaling,
stochastic rounding, and automatic mixed precision as the packaged form. Some
reductions need the extra bits regardless — see `tier-b-systems.md` on the
specific accumulations that must stay wide.

Integer quantisation (int8, int4) is mostly an inference technique, and its open
problem is **activation outliers**; `L-BONDARENKO23` traces these to attention
heads that need a way to attend to nothing and produce extreme activations
instead.

---

### D8 — Parameter averaging, and what it actually costs

**Grade** `measured-elsewhere` · **Moves** `steps-to-target` at fixed quality
**Radius** `none` at training time — the EMA is evaluated, not trained
**Exposure** `neutral` — a separate set of weights is evaluated; the trained
weights are untouched. Dimensions: none

Keep an exponential moving average of the parameters, optimise as usual, and
**evaluate on the EMA**. This is the same instrument `L-PLAYBOOK` reaches for as
Polyak averaging when late-training step-to-step variance is the problem
(`diagnostics.md` §5).

**The cost is one extra parameter-sized buffer** — which is _not_ "2× memory".
Stated as 2× it reads as doubling the training footprint; it doubles **parameter
storage in isolation**. Under Adam the parameter-related buffers are already
roughly four (parameters, gradients, two moments), so an EMA adds about 25% to
_those_, and less again as a fraction of a total footprint usually dominated by
activations. Always name the denominator. The same distinction applies to Adan's
"2× optimiser state" versus its repository's "slightly higher" total
(`optimisers.md` §3.1).

---

### D9 — Spectral bias: making high-frequency structure learnable

**Grade** `measured-elsewhere` (`L-RAHAMAN19`, `L-TANCIK20`, `L-SITZMANN20`)
**Moves** `steps-to-target`, and what is representable at all
**Radius** `distribution` · **Applies to** low-dimensional coordinate inputs especially
**Exposure** `neutral` — expands the representable function class.
Dimensions: none expected; can increase sensitivity to input noise

Networks preferentially fit **low-frequency** functions (`L-RAHAMAN19`), which is
why a plain MLP on raw coordinates learns a blurry approximation and stops. The
remedies all work by giving the network high-frequency structure it cannot
manufacture:

- **Positional encodings / random Fourier features** on the input
  (`L-TANCIK20`).
- **Periodic activations** — SIREN (`L-SITZMANN20`).

**Spectral normalisation belongs to a different problem.** `L-MIYATO18`
_constrains_ the Lipschitz constant; it is a stabilisation and robustness
instrument (with `L-CISSE17`), not an expressivity one. Filing it here inverts
its effect. Note also that a Lipschitz bound constrains a function's _rate of
change_, not its "amount of nonlinearity" — a low-Lipschitz function can be
highly nonlinear, so that reasoning does not license the remedies above; spectral
bias does.

---

### D10 — Numerical hygiene

**Grade** `mechanism` · **Moves** whether the run survives
**Radius** `numeric` · **Applies to** everywhere a division or a root appears
**Exposure** `neutral` — changes values by `ε`. Dimensions: none at sane `ε`

- `1/x → 1/(x+ε)` avoids division by zero — **valid only for `x ≥ 0`**. Where `x`
  can be negative, `ε` does not save you and can move a pole rather than remove
  it; use `x/(x²+ε)` or an explicit guard.
- `√x → √(x+ε)`, and **mind the derivative**: this is the point of it. `d/dx √x`
  diverges at 0, while `d/dx √(x+ε) = 1/(2√(x+ε))` is finite. The forward value
  barely moves; the backward value stops being infinite.
- Choose `ε` by order of magnitude, and treat it as a tunable when it sits inside
  an optimiser (`optimisers.md` §4.1).
