# Hardware notes — measure, do not recall

> **This file deliberately contains almost no numbers.**
>
> Hardware specifics are the single most likely thing for an agent to state
> confidently and wrongly: peak throughputs, tile sizes, dtype support and kernel
> behaviour change with every architecture, driver, and library version, and a
> plausible-sounding number recalled from training data is indistinguishable from
> a measured one until it costs someone a week.
>
> So this file is a set of **probes to run** and **invariants that survive
> hardware generations**. Anything you want a number for, measure — the probes
> below take seconds. Any number quoted from memory is `folklore` grade
> (`evidence-grades.md`) and must be labelled as such.

---

## 1. Establish the machine first

Before any Tier-B reasoning, get the ground truth from the machine itself, not
from a model name:

- accelerator model, count, and interconnect topology;
- driver, runtime, and framework versions;
- which reduced-precision formats are **supported** and which are **fast** — these
  are different sets, and the gap is where most precision disappointment lives;
- the memory-bandwidth-to-peak-arithmetic ratio, which determines whether
  elementwise and normalisation work is free or dominant;
- whether the device is shared, throttled, or power-capped — a capped device
  makes every timing comparison you are about to run unreliable.

Report these alongside any Tier-B finding. A finding without the machine it was
measured on is not portable and should not be written down as though it were.

---

## 2. Probes

Each answers one question the rest of Tier B depends on. Run them on the target
machine, in the target environment, at the shapes your model actually uses.

**P-1 — Is the input pipeline the bottleneck?**
Replace the loader with one pre-made batch resident on the device and re-time the
step. The delta _is_ the input cost. No profiler required, no interpretation
needed, and it is the highest-information single measurement available.

**P-2 — Is the step launch-bound?**
Sum device-side kernel durations for one step; compare to wall-clock step time. A
wide gap means host overhead, synchronisation, or too many small kernels — B4,
B6, B9. A narrow gap means the device is genuinely busy and you should be looking
at Tier A or at shapes.

**P-3 — Where on the roofline is the dominant op?**
For the largest matmul or convolution in the step, at your real shapes and dtype,
compute achieved FLOP/s and achieved bytes/s and compare each to the device's
measured peak. Near-arithmetic-peak means only fewer or cheaper operations help.
Near-bandwidth-peak means fusion, precision, and layout help.

**P-4 — What is the tile-alignment cliff on this machine?**
Sweep one matmul dimension across a range spanning several plausible tile
boundaries — e.g. every value from `k` to `2k` for a candidate `k` — and plot time
against size. The sawtooth is the alignment penalty, and its period is your
machine's effective tile size for that dtype. **Read the period off the plot;
never assume it.** Then round widths, head dimensions, vocabulary sizes and
padded lengths to it (B10).

**P-5 — Does the layout choice actually help here?**
Time the dominant op in both candidate memory layouts, at your shapes and dtype.
Layout preferences are kernel- and version-specific and reverse across
generations. If the difference is inside the noise, pick the one that avoids
transposes elsewhere.

**P-6 — What does compilation actually cost and buy?**
Record: cold compile time, warm start time, steady-state step time, and the
**recompilation count** over a few hundred real steps. Then compute the break-even
run count. This is the input to `tier-c-protocol.md` C6.7 and it is frequently
the difference between a recommendation and a warning.

**P-7 — Is the device thermally or power limited during a long run?**
Sample clocks, power draw, and temperature across a full-length run. A device that
throttles at minute three makes every short benchmark optimistic and every A/B
comparison order-dependent. If it throttles, interleave the arms rather than
running them back to back, and insert a fixed idle gap between runs.

---

## 3. Invariants that do survive hardware generations

These are `mechanism`-grade and safe to reason from without re-measuring — though
their _magnitude_ still needs P-1 to P-7.

- **Transfer is usually more expensive than conversion.** Move the compact
  representation and expand on-device, rather than converting on the host and
  moving the wide one.
- **Kernel launches have a fixed cost that does not shrink with problem size.**
  Small tensors are therefore launch-bound, and batching them (B4) is a
  structurally sound move on every accelerator.
- **Reductions and elementwise ops are bandwidth-bound; large matmuls are
  arithmetic-bound.** Fusing the former into the latter's neighbourhood is
  always directionally right.
- **Synchronisation costs a pipeline drain**, whatever the hardware (B9).
- **Padding to an alignment boundary is cheaper than the alternative it avoids**
  — a recompilation, a ragged kernel, or a fallback path — far more often than
  the wasted arithmetic suggests.
- **Wide-exponent 16-bit formats remove the loss-scaling machinery**; narrow-
  exponent ones do not. Which is _available and fast_ is a P-1-to-P-7 question;
  that the exponent range is what matters is not.
- **Memory freed is only a speedup once it is converted** into batch size, model
  size, or fewer shards. Activation checkpointing that frees memory nobody
  spends is a pure slowdown (B13).

---

## 4. Non-accelerator and non-standard targets

The tier catalogues assume a single accelerator with host-device transfer. Where
that is not the setting:

- **CPU-only** — Tier B's shape is different: thread count and affinity, memory
  layout, and vectorisation dominate; launch overhead largely disappears; B2's
  device-residency argument becomes an ordinary cache-locality argument. Most of
  Tier A is unaffected.
- **Graph-compiled / ahead-of-time targets** — recompilation (B6) is not a
  runtime tax but a hard shape constraint; dynamic shapes may be prohibited
  outright, which promotes bucketing and packing from optimisation to
  prerequisite.
- **Multi-tenant or shared devices** — C2's noise floor is dominated by the
  neighbours, not by the run. Measure it in the environment you will actually
  run in, and expect it to be several times larger than on a quiet machine.
- **Consumer or memory-constrained devices** — the binding constraint is usually
  memory, not time, which reorders the whole of Tier B and makes B13's
  time-for-memory trades favourable where they would otherwise be losses.

State which of these applies before quoting anything from Tier B; several of its
items invert.

---

## 5. How to report a hardware-conditional finding

```
[B4] Batch the per-parameter optimiser internals
  grade    mechanism (P-2: 412 kernels/step, 38% of step time outside kernels)
  machine  <accelerator, count, driver, framework version> — measured 2026-07-27
  probe    P-2 before/after; P-4 gave tile period 8 for this dtype
  caveat   re-measure on a different accelerator or framework major version
```

The `machine` and the date are not decoration. A Tier-B number without them is
`folklore` the moment it leaves the machine it was measured on.
