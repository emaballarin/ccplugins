# tuneml findings — <project>

<!-- Written by /tml:audit to ./.tml/findings.md. Read by /tml:plan.
     Every field is load-bearing; an empty field is a finding that is not ready
     to be acted on. Delete this comment block when filling in. -->

**Audited** <ISO date> · **Scope** tiers <A|B|C> · **Modality** <…>
**Pipeline** `<entrypoint path>` · **Machine** `<accelerator, count, driver, framework>`
**Objective on record** <from ./.tml/frontier.md, or "not yet stated">

## Current operating point

| Quantity                               | Value | How it was obtained            |
| -------------------------------------- | ----- | ------------------------------ |
| Quality metric and value               |       | n = ?, spread = ?              |
| Noise floor (spread)                   |       | `measured-here` / not measured |
| `steps-to-target`                      |       |                                |
| `time-per-step` (steady)               |       | after warmup, device events    |
| One-time cost                          |       | compile / autotune / cache     |
| Runs this will be amortised over (`k`) |       | asked, not assumed             |
| End-to-end time-to-target              |       |                                |

If the noise floor row is empty, **every delta below is unfalsifiable** and the
plan must start by measuring it (`tier-c-protocol.md` C2).

## Bottleneck

**Class** input / launch-bound / bandwidth / compute / communication / **unprofiled**
**Evidence** <which probe from `hardware-notes.md`, and what it returned>

If unprofiled, every Tier-B finding below is graded `analogy` and says so.

## Ranked findings

Ranked by expected value over engineering cost, after two filters: `analogy` and
`folklore` items never outrank `mechanism` or above (they go to Hypotheses), and
anything whose **exposure** touches a _hard_ non-negotiable is removed outright
to _Not recommended_ — exposure is a veto, not a term in the score.

Radius, exposure and engineering cost are independent (`evidence-grades.md` §3).
A `distribution`-radius item can be quality-`neutral`; a `numeric` one can spend
real accuracy. Do not let one column stand in for another.

| #   | Item | Moves | Grade | Radius | Exposure | Eng. | Est. effect | Pitfalls |
| --- | ---- | ----- | ----- | ------ | -------- | ---- | ----------- | -------- |
| 1   |      |       |       |        |          |      |             |          |
| 2   |      |       |       |        |          |      |             |          |
| 3   |      |       |       |        |          |      |             |          |

### 1. <title> `[A#/B#/C#]`

**Grade** <grade> — <what makes it that grade, in this codebase, with the file
and line that shows it. If the effect size is a weaker grade than the mechanism,
say both.>
**Moves** `steps-to-target` <↓/↑/–> · `time-per-step` <↓/↑/–> — and whether it
moves the other adversely.
**Radius** `none` / `numeric` / `distribution` — mechanical; sets how this is verified.
**Exposure** `neutral` / `bounded` / `spending` / `unknown` — what quality this
can cost, on which dimensions (mean, calibration, worst-group, robustness, tails,
determinism), and what the knob is if it is `bounded`. **Then: does it touch a
hard non-negotiable in `frontier.md` §2?** If so this is a veto, not a weight,
and the item belongs in _Not recommended_ however large its effect.
**Engineering** effort <trivial/contained/structural> · revert
<trivial/contained/structural> · legibility <no change / harder to read, how>
**Where** `path:line` — the specific site, not the general area.
**Price** <in time-to-target, with the arithmetic. "unknown until measured" is a
valid and preferred answer over an invented number.>
**Measure** <the exact comparison that would confirm it: what runs, what `n`,
against what baseline, and whether both directions are needed (C4).>
**Pitfalls** <P# references from `pitfalls.md`, with the specific check.>

_(repeat per finding — cap at the number the operator can actually act on)_

## Hypotheses — not ranked, not banked

`analogy` and `folklore` items. Listed because they may be worth a measurement,
never because they are worth doing. Each states the invariance it assumes.

| Item | Grade | Assumed invariance | What would settle it |
| ---- | ----- | ------------------ | -------------------- |
|      |       |                    |                      |

## Not recommended

Items that would buy time and should not be taken, with the reason —
a stated non-negotiable, a `tier-c-protocol.md` C6 case, or an unfavourable
risk trade. **An audit with an empty section here has probably not been honest.**

| Item | Would buy | Why not |
| ---- | --------- | ------- |
|      |           |         |

## Already done

Items from the catalogues this pipeline already implements. Recorded so a later
audit does not re-propose them and so the operator can see the ground covered.
