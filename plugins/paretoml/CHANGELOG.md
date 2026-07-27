# Changelog

All notable changes to the `parml` (paretoml) plugin are documented here.
This project adheres to [Semantic Versioning](https://semver.org/).

## 0.1.0 — 2026-07-27

Initial release. A read-first advisor for the speed↔quality frontier of a
training and evaluation pipeline — not a max-throughput chaser, and willing to
recommend changing nothing.

### Three skills

`/parml:audit` reads a pipeline and emits ranked, evidence-graded, priced
findings; `/parml:plan` fixes an operating point under an explicit quality floor
and orders the work with gates and a stop rule; `/parml:review` adversarially
checks a proposed or applied change. One analysis, one decision, one guard — no
verb sprawl. Nothing edits project code; `audit` and `plan` each write exactly
one file under `./.parml/`, and `review` writes none.

### The two-factor currency

Everything is priced in **time-to-target-quality**, decomposed as
`steps-to-target × time-per-step`. Tier A moves the first factor, Tier B the
second, and every finding must state which it moves _and whether it moves the
other adversely_. Throughput is treated as a diagnostic and is never accepted as
a result — a change that improves samples/sec 30 % while worsening loss-per-step
40 % is a regression that a dashboard reports as a win.

### Evidence grades

`measured-here` › `measured-elsewhere` › `mechanism` › `analogy` › `folklore`,
with a degradation rule for cross-modality and cross-scale porting. Two hard
constraints: `analogy`/`folklore` items never outrank `mechanism` or above
whatever effect size they claim, and nothing below `mechanism` is banked without
a `measured-here` promotion. An ungraded claim is not emitted; `folklore` is a
respectable answer.

### Three independent cost axes

Every change is costed on three axes that do not predict each other, because
collapsing them is how this kind of advice becomes useless:

- **Radius** — `none` / `numeric` / `distribution`. Mechanical, read off the
  diff, never negotiated. Sets _how_ the change is verified.
- **Quality exposure** — `neutral` / `bounded` / `spending` / `unknown`, plus the
  dimensions exposed (mean, calibration, worst-group, robustness, tails,
  determinism). A policy question answered by the operator's non-negotiables, and
  a **veto rather than a weight**: an `unknown` or `spending` exposure against a
  _hard_ constraint stops the change whatever its effect size.
- **Engineering cost** — effort, revert cost, and legibility, reported
  separately because they trade differently. A one-line precision change is
  trivial to make and structural to unpick once results depend on it.

A `distribution`-radius change can be quality-positive; a `numeric` one can spend
real accuracy. Every catalogue item in tiers A and B carries an explicit
`**Exposure**` line, enforced by Tier-1 validation.

### Three tier catalogues, separately readable

- **Tier A — algorithmic** (15 items): frozen data-derived input transforms and
  their discrete-input analogue, near-identity initialisation, parameter-group
  update scales, normalised updates, derandomised augmentation with its measured
  boundary condition, iterate averaging, confidence-gated inference, freezing,
  output-scale control, decoupled hyperparameters, example selection with its
  contraindications, schedule shape, stream completeness, and input-size ramping.
- **Tier B — systems** (13 items): a profiling gate on _prioritisation_ — a
  code-visible mechanism is emittable unprofiled, graded separately on existence
  and magnitude, and ranked by a prior-strength table — input-pipeline removal
  from the critical path, invariant caching, small-op batching including
  pad-and-stack for heterogeneous shapes, periodic amortisation, step compilation
  with recompilation counting, precision and layout with the three reductions
  that need extra bits, one-time-vs-steady-state separation, synchronisation
  removal, architecture as a cost lever, step-unit hyperparameter re-derivation,
  evaluation cost, and multi-device decision rules.
- **Tier C — protocol** (9 items): objective as a constrained optimisation, noise
  floor with the runs-for-significance arithmetic, locked harness, both-direction
  ablation, additivity as an assumption with a check, **nine cases where speed is
  the wrong objective**, the operating-point decision record, a stop rule, and
  honest reporting.

The tiers intersect explicitly: A∩B changes are priced end to end, A∩C asks
whether the target survived the change, B∩C asks whether the instrument did.

### Modality map and quarantined hardware notes

`modality-map.md` gives per-modality instantiation for every modality-sensitive
item across vision, text, audio, tabular, graphs, time-series and non-stationary
settings, plus a four-question procedure for a modality not listed.
`hardware-notes.md` deliberately contains almost no numbers: seven probes to run
and the invariants that survive hardware generations, because recalled hardware
specifics are indistinguishable from measured ones until they cost a week.

### Pitfall catalogue

Fifteen entries in symptom → mechanism → detection form, covering the ways a
speedup reports success while doing damage: score inflation through a moved
measurement, dead knobs in tuned configurations, the throughput fallacy, stale
step-unit hyperparameters, optimisations that never engaged, mean-only
verification of distribution-level changes, train/eval mismatch, schedules
outliving their parameter, parameter-partition fallthrough, precision
degradation, leakage, stale caches, timing boundaries, nondeterminism read as
improvement, and data-order coupling. `/parml:review` walks five of them against
every diff.

### Composition

Shares `ar`'s protocol vocabulary — noise floor, keep threshold, locked harness —
so `/parml:plan` can hand off to `/ar:start` without translation. The handoff is
**offered with its cost stated and never taken**: `/ar:start` creates a git
branch and a commit on first use, so it waits for an explicit yes, and executing
a short table by hand is the default when in doubt.

### Two corrections carried as original findings

Both re-derived numerically rather than taken on trust from the sources they
correct: the steady-state Nesterov step amplification is `1/(1−m)`, not
`1 + 1/(1−m)`; and a magnitude-target schedule immediately followed by an
unconditional renormalisation is inert, with a measured total effect of ~10⁻⁴
relative across a whole run.
