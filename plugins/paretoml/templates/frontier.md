# Operating point — <project>

<!-- Written by /parml:plan to ./.parml/frontier.md. This is the decision record.
     The technical work is getting onto the frontier; this page is choosing where
     to sit on it, and that choice is the operator's. Delete this comment when
     filling in. -->

**Decided** <ISO date> · **By** <who> · **Supersedes** <previous version, if any>

---

## 1. The objective

Exactly one form (`tier-c-protocol.md` C1). Delete the rest.

- [ ] minimise **<cost>** subject to **<quality> ≥ <Q>**
- [ ] maximise **<quality>** subject to **<cost> ≤ <B>**
- [ ] minimise **variance** at fixed cost and quality
- [ ] minimise **cost per unit of statistical power** — target: detect **δ = <…>**
      at the usual significance level

**Cost is measured in** wall-clock / accelerator-hours / energy / money — pick one
and say so; they conflict (C6.8).
**Quality is** <metric>, measured on <split>, with **n = <…>** runs.
**Target `k`** — how many times will this pipeline be run? <…>
One-time costs are priced as `one-time / k`, so this number decides whether a
whole class of changes is a win or a loss (C6.7).

## 2. What may not move

Named explicitly. Anything left off this list will be spent.

| Constraint                        | Bound | How it is measured | Checked by |
| --------------------------------- | ----- | ------------------ | ---------- |
| Calibration                       |       |                    |            |
| Worst-group / per-segment quality |       |                    |            |
| Robustness under shift            |       |                    |            |
| Determinism / reproducibility     |       |                    |            |
| Comparability with <baseline>     |       |                    |            |
| Tail latency                      |       |                    |            |
| Legibility / maintainability      |       |                    |            |

Mark each **hard** (revert on any violation) or **soft** (negotiable, with a
stated price). A constraint with no measurement next to it is a wish.

## 3. The trade being accepted

State it in one sentence, in the form: _"We accept up to X of <quality> to save Y
of <cost>, and we revert if Z."_

> …

**Not accepted, and why** — the changes that would buy time and are being
declined. Cite the constraint or the C6 case. This section is the point of the
document.

| Declined change | Would buy | Declined because |
| --------------- | --------- | ---------------- |
|                 |           |                  |

## 4. The plan

Ordered. Each row is one atomic change with its own gate. Cheap reverts and
strong grades first; nothing below `mechanism` is banked without being promoted
to `measured-here` first.

| #   | Change | Grade | Moves | Exposure | Expected | Confirm by | Revert trigger | Pitfalls |
| --- | ------ | ----- | ----- | -------- | -------- | ---------- | -------------- | -------- |
| 1   |        |       |       |          |          |            |                |          |
| 2   |        |       |       |          |          |            |                |          |

No row may carry an exposure that violates a **hard** constraint in §2 — those
belong in _Not accepted_ above, not in the plan with a tighter gate.

**Re-measure end to end after every three accepted changes** — additivity is an
assumption with a check, not a law (C5).

## 5. Measurement contract

- **Baseline** — commit `<sha>`, `n = <…>`, centre `<…>`, spread `<…>`.
- **Locked** — the harness, evaluator, metric definition, and data split. Listed
  by path. Any change ends the segment and forces a fresh baseline (C3).
- **Keep threshold** — an improvement counts only if it exceeds the spread. Below
  that it is a re-roll of the same distribution.
- **Both directions** — which changes get the add-to-baseline _and_
  remove-from-final treatment (C4), and which are exempt because their radius is
  `none` and equality settles them.

## 6. Stop rule

Written down **before** starting (C8). Stop when:

- [ ] the objective in §1 is met — the one people forget;
- [ ] the next expected gain is below the noise floor;
- [ ] the next expected gain is below the cost of measuring it;
- [ ] only `analogy`/`folklore` items with `distribution` radius remain;
- [ ] human iteration cost dominates.

## 7. Handoff

- **Many measured iterations under a locked harness** → `/ar:start`, which takes
  this objective, this baseline, and this noise floor directly.
- **A handful of changes** → execute the §4 table directly, `/parml:review` each
  diff before accepting it.
- **Either way** → record the decision in project memory so the next session does
  not re-litigate it.
