# Evidence grades, pricing, and the tier algebra

The shared contract. Every finding this plugin emits carries a **grade**, a
**price**, and a **blast radius**. Read this before the tier catalogues; the
grades are what stop an advisory skill from becoming a folklore dispenser.

---

## 1. The grade ladder

Ordered by how well a claim is supported **for the pipeline in front of you** —
not by how well it is supported in general.

| Grade                | Means                                                                                                                                                 | Bar to claim it                                                                   |
| -------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| `measured-here`      | Measured on this pipeline, this data, this hardware                                                                                                   | You ran it. `n`, the spread, and the harness are recorded.                        |
| `measured-elsewhere` | Measured in a citable source under stated conditions                                                                                                  | Name the source, the `n`, and the conditions. No "papers show that".              |
| `mechanism`          | Follows from an argument that provably holds here — arithmetic, a shape/dtype argument, a profiler trace, a counted kernel launch, a read of the code | You can show the derivation, the trace, or the line of code. It is checkable now. |
| `analogy`            | Generalised from another modality, scale, or architecture                                                                                             | Name the source setting **and** the invariance you are assuming holds.            |
| `folklore`           | Widely repeated; no measurement in hand                                                                                                               | Say so plainly. Do not dress it as `mechanism`.                                   |

**Degradation rule.** `measured-elsewhere` drops to `analogy` when the porting
conditions differ materially from the source's: a different modality, a scale gap
beyond ~10×, a different optimiser family, a different precision, or a target
quality on the other side of a regime change. Apply the drop explicitly and say
which condition triggered it. A number measured on 50k 32×32 images at n=400 is
not evidence about a 7B-parameter language model, and quoting it as though it
were is the single most common way this kind of advice goes wrong.

**Ranking rule.** `analogy` and `folklore` items **never outrank** `mechanism` or
above in a recommendation order, whatever effect size they claim. They are listed
in a separate _hypotheses_ block. A large unmeasured number is not better
evidence than a small measured one; it is a larger unknown.

**Banking rule.** Nothing below `mechanism` is banked — kept, built on, or quoted
downstream — without a `measured-here` promotion first. `analogy` items earn
their place by being measured, not by being plausible.

**When you do not know.** `folklore` is an available, respectable answer. An
ungraded claim is not.

---

## 2. Pricing: the only currency is time-to-target

A finding is priced in **time (or cost) to reach the target quality**. Never in
throughput alone.

```
time-to-target  =  steps-to-target  ×  time-per-step
```

Every change moves one factor, the other, or both — and **the two can move in
opposite directions**. This decomposition is the analytical spine of the whole
plugin:

| Factor            | Moved by                 | Measured as                                                                 |
| ----------------- | ------------------------ | --------------------------------------------------------------------------- |
| `steps-to-target` | **Tier A** (algorithmic) | steps/epochs/tokens until the quality target is first met, at fixed harness |
| `time-per-step`   | **Tier B** (systems)     | steady-state wall-clock per optimiser step, after warmup, at fixed batch    |
| both, or neither  | the intersections (§4)   | end-to-end time-to-target, re-measured                                      |

**Every finding must state which factor it moves and whether it moves the other
adversely.** A change that improves `time-per-step` by 30 % while worsening
`steps-to-target` by 40 % is a regression that a throughput dashboard reports as
a win. This is the most expensive mistake in the field and it is invisible unless
you insist on this decomposition.

Corollaries worth stating to the operator:

- **Throughput is a diagnostic, not an objective.** Samples/sec, tokens/sec, and
  MFU are useful for locating a bottleneck and useless for deciding whether a
  change was good.
- **FLOPs are not time.** Both source pipelines contain changes that cut FLOPs
  without cutting wall-clock, and changes that cut wall-clock without cutting
  FLOPs. Report both when they disagree; decide on time.
- **One-time costs are separate from steady state.** Compilation, autotuning,
  index building, and cache warming are amortised over `k` runs. Price them as
  `one-time / k` and make `k` explicit — at `k = 1` many Tier-B wins are losses.

---

## 3. Three axes, not one

A change has **three independent costs**, and collapsing them is the most common
way this kind of advice becomes useless. They answer different questions, they
are decided by different people, and **none of them predicts the others.**

| Axis                 | Question                                         | Kind                      | Decided by                         |
| -------------------- | ------------------------------------------------ | ------------------------- | ---------------------------------- |
| **Radius**           | What changed about the computation?              | Mechanical — nature-based | The change itself. Not negotiable. |
| **Quality exposure** | What quality could this cost, on what?           | Policy                    | The operator's non-negotiables.    |
| **Engineering cost** | What does it cost to build, undo, and live with? | Human                     | Whoever maintains it.              |

The independence is the point and it is easy to get wrong in both directions: a
`distribution`-radius change can be quality-`neutral` or quality-_positive_ (a
derandomised augmentation rewrites the training distribution and **improves**
quality), while a merely `numeric` change can spend real accuracy (normalisation
statistics moved to half precision). **Radius tells you how to verify. Exposure
tells you whether you are allowed to.**

### 3.1 Radius — mechanical, and it sets the verification method

| Radius         | Meaning                                                                                                      | Verify by                                                                                              |
| -------------- | ------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------ |
| `none`         | Bit-identical or provably equivalent outputs. Pure implementation.                                           | **Equality.** A metric check here wastes runs — and a failed equality is a bug, not a tradeoff.        |
| `numeric`      | Same computation, different arithmetic — precision, kernel, reduction order, fusion.                         | **Metric across `n` runs**, and the tails, not just the mean.                                          |
| `distribution` | Changes what the model sees or optimises — selection, augmentation, schedule, loss, architecture, optimiser. | **Every exposed dimension** (§3.2). You are training a different thing; see `tier-c-protocol.md` C6.2. |

This axis is a fact about the diff. It is read off the change, never negotiated,
and an audit that cannot classify it says `unknown` rather than guessing.

### 3.2 Quality exposure — policy, and it can veto

What the change could cost, **and whether that cost is controllable**:

| Exposure   | Meaning                                                                                                     |
| ---------- | ----------------------------------------------------------------------------------------------------------- |
| `neutral`  | No expected quality cost; often a gain. Still verified — but no trade is being made.                        |
| `bounded`  | An expected cost **with a knob that trades it back** — a gating fraction, a precision, an interval, a size. |
| `spending` | Deliberately spends quality for cost. Legitimate only with headroom and an explicit floor.                  |
| `unknown`  | Could cost quality in a way not yet characterised **here**. Must be measured; never assumed `neutral`.      |

Alongside the level, name the **dimensions exposed** — mean, calibration,
worst-group, robustness under shift, tails, determinism. This is what gets
checked against the non-negotiables in `templates/frontier.md` §2, and the check
is a **veto, not a weight**: an `unknown` or `spending` exposure against a _hard_
non-negotiable stops the change regardless of how large its expected effect is.
No amount of speed buys a violated constraint.

`neutral` is a claim, not a default. An item whose exposure has not been thought
about is `unknown`.

### 3.3 Engineering cost — human, and it compounds

Three parts, reported separately because they trade differently:

- **Effort** — `trivial` (a flag or a line) · `contained` (one module) · `structural`
  (touches the training loop, the data path, or the harness).
- **Revert** — the same scale, for undoing it. Often _not_ the same as effort:
  a one-line precision change is trivial to make and structural to unpick once
  three months of results depend on it.
- **Legibility** — does the pipeline get harder to read, debug, or hand over?
  This is the axis nobody records and it is real: a 2× faster pipeline that only
  one person can modify is frequently net negative (`tier-c-protocol.md` C6.6).

Rank cheap reverts first at equal expected value. The option to undo is worth
real money when the evidence is `analogy`, and worth nothing once you have built
on top of it.

---

## 4. The tier algebra — how A, B, and C intersect

The tiers are separate catalogues and are meant to be read separately. They are
not independent.

```
Δ(time-to-target) ≈ Δ(steps) × time-per-step  +  steps × Δ(time-per-step)
                    └── Tier A ──┘                        └── Tier B ──┘
Tier C decides whether "target" is still the same quantity,
and whether either Δ above is believable.
```

**A ∩ B — changes that move both factors.** Precision and layout, batch size,
compilation, data selection, sequence packing, activation checkpointing. These
must be priced end-to-end, never on one factor. A batch-size increase that halves
`time-per-step` and doubles `steps-to-target` is exactly neutral and is routinely
sold as a 2× speedup.

**A ∩ C — did the target survive the change.** Any `distribution`-radius Tier-A
change alters the training distribution or the objective, so the number you were
targeting may no longer mean what it meant. Data selection, augmentation removal,
schedule shortening, and label smoothing all land here.

**B ∩ C — is the measurement still valid.** Nondeterminism, warmup amortisation,
where the timing boundary sits, whether evaluation is inside or outside the
clock, whether the comparison still shares a harness. A Tier-B change frequently
invalidates the instrument that would have measured it.

**A ∩ B ∩ C — the operating point itself.** Which is not a technical question and
is not the agent's to decide. See `tier-c-protocol.md` §7 and
`templates/frontier.md`.

**Additivity.** Both source pipelines found that independently-measured speedups
accumulate roughly **additively** rather than multiplicatively — measured by
taking each feature's delta twice (added to a weak baseline, removed from the
strong final) and finding them comparable, and separately by six per-change
wall-clock attributions summing to the observed total. Treat additivity as a
**working assumption with a check**, not a law: it is `measured-elsewhere` on two
vision pipelines, it demonstrably failed for one feature (multi-view inference)
in the source that measured it, and it should be re-verified after any three
accepted changes. See `tier-c-protocol.md` §5.

---

## 5. Emitting a finding

The minimum shape. `templates/findings.md` is the full form.

```
[A4] Normalised/orthogonalised updates for matrix parameters
  grade         mechanism (matrix params confirmed at src/model.py:88-140)
                → effect size is `analogy` (source: vision CNN, 2M params)
  moves         steps-to-target ↓ ; time-per-step ↑ ~2-4% (extra matmuls)
  radius        distribution — different optimiser, different trajectory
  exposure      unknown — final quality here is uncharacterised. Dimensions:
                mean, and convergence stability late in the schedule.
                → frontier.md lists no hard constraint this touches: not a veto
  engineering   effort contained (one construction site) · revert contained ·
                legibility: adds a non-standard optimiser others must understand
  price         net unknown until measured; source reports ~20% fewer epochs
  measure       time-to-target at fixed harness, n≥5, both directions (§C5)
  pitfall       does not apply to 1-D params; needs its own LR scale (P9)
```

Three failure modes this shape is designed to prevent:

- A confident number with no grade behind it.
- A grade with no measurement plan behind it — which is how `analogy` items
  quietly get banked.
- A radius standing in for an exposure — "it only changes the arithmetic" is not
  an argument that it costs no accuracy, and "it changes the training
  distribution" is not an argument that it does.
