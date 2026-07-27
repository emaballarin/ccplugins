# Tier C — protocol: deciding what to optimise, and believing the answer

Tier A and Tier B change the pipeline. Tier C decides **whether the target is
still the right target** and **whether either tier's measured delta is real**.

It is the tier that most often changes the answer, and the only one where the
correct recommendation is sometimes _do not make it faster_.

Vocabulary here is deliberately shared with the `ar` (autoresearch) plugin —
noise floor, keep threshold, locked harness — so a plan can hand off without
translation.

---

### C1 — State the objective as a constrained optimisation

**Grade** `mechanism` · **Governs** everything downstream · **Cost** one sentence

"Make it faster" is not an objective; it has no stopping condition and no way to
be wrong. Every engagement starts by writing one of these down:

| Form                                            | When it is right                                                  |
| ----------------------------------------------- | ----------------------------------------------------------------- |
| minimise **cost** subject to **quality ≥ Q**    | Q is externally fixed — a published baseline, an SLA, a threshold |
| maximise **quality** subject to **cost ≤ B**    | The budget is fixed — a deadline, a grant, a device               |
| minimise **variance** at fixed cost and quality | The deliverable is a comparison, not a model                      |
| minimise **cost per unit of statistical power** | The deliverable is a _conclusion_ — see C6.1                      |

Then name, explicitly, what is **not** allowed to move: calibration, worst-group
accuracy, robustness, determinism, comparability with a baseline, licence to
report the number as "the standard recipe". Anything left unnamed here will be
spent, because every real speedup spends something.

Record the answer in `templates/frontier.md`. It is one page and it prevents the
most expensive class of mistake in this whole plugin.

---

### C2 — Know the noise floor before believing anything

**Grade** `mechanism` · **Governs** every keep/revert decision · **Cost** `n` baseline runs

Run the **unmodified** pipeline `n` times (5 is a working minimum) and record the
centre and the spread. The spread is the bar: a change that buys less than it is
not an improvement, it is a re-roll of the same distribution.

- Centre: the **median**, so one pathological run cannot move the reference.
- Spread: the standard deviation, or the median absolute deviation when `n` is
  small or the sample is visibly skewed. MAD is the safer default at `n = 5`.
- Fix both **once** per segment and never recompute mid-segment. A floor that
  drifts with the run is not a floor.
- If the spread is exactly zero — a fully deterministic harness — keep on any
  strict improvement, but record confidence as undefined rather than infinite.

**The arithmetic that makes this concrete.** With a between-run standard
deviation `σ` on the quality metric, detecting a mean improvement `δ` at the
usual significance level takes on the order of `n ≈ 2(1.96 + 0.84)²σ²/δ²`, i.e.
roughly `16 σ²/δ²`, runs — the source pipeline's worked case is `σ = 0.14 %`,
`δ = 0.02 %` → ≈ 133 runs. Two consequences:

- **Any claimed improvement below about `σ/3` from a handful of seeds is
  unfalsified noise**, no matter how good the mechanism sounds.
- **This is the argument for speed that survives contact with rigour.** A faster
  run is not an end in itself; it is what converts an 11-hour significance test
  into a 7-minute one. That is the honest reason to care about Tier A and B.

---

### C3 — Lock the harness

**Grade** `mechanism` · **Governs** whether the score means anything
**Cost** discipline

The benchmark script, the evaluator, the metric definition, the data split, and
the code emitting the number are off-limits for the whole comparison. The reason
is direct and does not depend on anyone acting in bad faith: **an agent (or a
person) optimising a number it is also allowed to define will eventually improve
the number by weakening the measurement.** Loosening a tolerance, dropping a hard
case, widening an early-stopping window, or shortening the eval set all read as
progress and are all pure score inflation.

Enforce mechanically — reject any diff touching a locked path — not by intent.
If the harness genuinely must change, that **ends the segment**: change it
deliberately, re-measure the baseline and the floor, and start a new one. Numbers
either side of a harness change are not comparable and must never share a table.

---

### C4 — Measure each change in both directions

**Grade** `measured-elsewhere` (the protocol, and its finding, come from the
source pipeline's own ablation) · **Governs** whether you can reason about
changes independently · **Cost** two runs per feature instead of one

For each feature, measure both:

1. the cost saved by **adding** it to the weak baseline, and
2. the cost added by **removing** it from the strong final configuration.

If the two agree, the feature's interactions are additive and you may reason
about it independently — which is what licenses a ranked list at all. If they
diverge, you have found a real interaction and must say so rather than quoting
one of the two numbers.

The source found agreement for every feature it tested **except one** — its
inference-time augmentation, whose value depended strongly on what else was
present. Expect the exception, do not assume it away.

---

### C5 — Additivity is a working assumption with a check

**Grade** `measured-elsewhere` on two vision pipelines · **Governs** how you
combine estimates · **Cost** one end-to-end re-measurement per few changes

Independently-measured speedups tend to accumulate **additively** rather than
multiplicatively. Two independent observations support this: the both-directions
protocol in C4 agreeing across a 2× change in baseline strength, and a separate
pipeline's six per-change wall-clock attributions summing to within a percent of
the observed total.

Use it to plan — a ranked list of independently-priced items is only meaningful
under something like additivity — but **re-measure end to end after every three
accepted changes**. Drift compounds silently, and the one documented exception
was a feature whose value depended on its neighbours.

---

### C6 — When speed is the wrong objective

**Grade** `mechanism` throughout · **Governs** whether to recommend anything at all

The cases where the correct output of this plugin is "do not do this". An audit
that never produces one of these is not being run honestly.

**C6.1 — The deliverable is a conclusion, not a model.** If you need `n` runs for
significance, per-run speed is a means and `time × runs-needed` is the objective.
A change that cuts run time 30 % while raising between-run variance 30 % _loses_
net power, because required `n` grows as `σ²`. Always report the variance
alongside the speedup; a speedup quoted without it is half a measurement.

**C6.2 — Fidelity to the claim you are making.** Any `distribution`-radius change
means you are training a different thing. If the claim is about _the standard
recipe_, a faster non-standard recipe does not support it. This is not pedantry:
data selection, augmentation removal, schedule shortening, and precision
reduction all change what the number is about.

**C6.3 — Comparability.** Ablations, baselines, and prior work must share a
harness (C3). A pipeline tuned for speed that only you run makes your numbers
incomparable with everything published — sometimes an acceptable price, never an
invisible one.

**C6.4 — Quality is not one number.** Mean accuracy can hold while calibration,
worst-group accuracy, robustness under shift, or tail latency degrade. The
measured example is in `tier-a-algorithmic.md` A7: inference-time augmentation
_reduced_ test-set variance and _worsened_ class-wise calibration in every
configuration tested, at n = 10 000 per cell. Data selection, distillation,
quantisation, early exit, and aggressive precision reduction all have this shape.
If the model faces people or a threshold, these are constraints, not metrics.

**C6.5 — Determinism.** Reduced precision, non-deterministic kernels,
asynchronous reductions, atomics, fused operations, and autotuning all trade
bitwise reproducibility for speed. Sometimes reproducibility is a hard
requirement — regulated settings, debugging a rare failure, or any comparison
whose whole point is that only one thing changed.

**C6.6 — Human iteration cost.** A pipeline that runs 2× faster and takes a week
to understand, breaks on every change, and only one person can modify is often
net negative. The relevant clock is time-to-answer, and it includes the human.
State this when a proposed change trades legibility for wall-clock; it is real,
routinely ignored, and the operator is the only one who can price it.

**C6.7 — One-shot runs.** Compilation, autotuning, cache building, and index
construction are amortised over `k` runs. At `k = 1` a substantial fraction of
Tier B is a net loss. Ask for `k` before recommending anything with a one-time
cost, and price it as `one-time / k`.

**C6.8 — Cost is not wall-clock.** Wall-clock, accelerator-hours, energy, and
money are four different objectives that routinely conflict — scaling to more
devices usually improves the first and worsens the second. Say which one is being
optimised.

**C6.9 — Risk.** In a production or regulated path, the expected cost of a silent
regression can exceed any plausible speedup. `pitfalls.md` is the list of ways
these changes fail silently; weigh it, do not just append it.

---

### C7 — Choose the operating point explicitly, and write it down

**Grade** `mechanism` · **Governs** the whole engagement · **Cost** one page

The point of a frontier is that off-frontier configurations are strictly
wasteful — and that _on_ the frontier there is no free choice left, only a
decision about what to spend. Getting onto the frontier is the technical part;
choosing where to sit on it is not, and is **not the agent's decision**.

Fill `templates/frontier.md`: the objective from C1, the quality floor with its
metric and its `n`, the non-negotiables, the accepted trade with its price, the
revert trigger for each accepted change, and the stop rule (C8). Then a decision
survives the session, the person, and the argument three weeks later about why
the number changed.

**Present a decision as a brief, not a menu.** One recommendation with its
reason, each alternative with an honest upside and downside. An agent that lists
six options without ranking them has moved the work, not done it.

---

### C8 — Have a stop rule

**Grade** `mechanism` · **Governs** when to stop · **Cost** one line

Stop optimising when any of these is true:

- the next expected gain is **below the noise floor** (C2) — it cannot be
  demonstrated, so it cannot be banked;
- the next expected gain is **below the cost of measuring it** — including your
  time and the runs it would take;
- the remaining candidates are all `analogy`/`folklore` **and** carry
  `distribution` radius — an unfavourable expected-value trade;
- **human iteration cost now dominates** (C6.6);
- the objective from C1 is **met**. This is the one people forget.

Write the rule down before starting. Deciding to stop while looking at a
tantalising unexplored item is a decision made under the worst possible
conditions.

---

### C9 — Report honestly

**Grade** `mechanism` · **Governs** whether the work is usable by anyone else
**Cost** a paragraph

Every reported speedup carries: the baseline it is against, `n` and the spread
for both arms, the harness identity, what moved in `steps-to-target` versus
`time-per-step`, the one-time cost and the `k` it was amortised over, and every
quality dimension checked _including the ones that moved the wrong way_.

Two specific disciplines:

- **Convert quality deltas into effective speedup** through a fitted cost-vs-error
  curve, so that gains in different currencies are comparable. Prefer a
  conservative fit — the source notes that a power-law fit reported a 27 %
  effective speedup where linear interpolation between the same two points
  reported 52 %. Say which you used.
- **Report the dose-response, not a verdict.** A monotone sweep that stopped at
  its largest value is _under-tested_, not _failed_. "Best so far, still short of
  target" is a valid and useful result; state it in those words rather than
  rounding it to success or failure.

---

## The three-line version

1. Write the objective as a constraint, and name what may not move (C1).
2. Measure the floor before believing any delta; lock the harness (C2, C3).
3. Know which of C6.1–C6.9 applies, and be willing to output "do not do this".
