---
name: plan
description: 'Choose an operating point on the speed↔quality frontier, fix the training-step budget, and turn findings into an ordered, gated change plan — with a quality floor, named non-negotiables, revert triggers, a measurement contract, and a stop rule. Use for `/tml:plan`, "which of these should I actually do", "I have N GPU-hours and need quality Q", "how long should I train for", "how much accuracy can I trade for speed", "what order should I make these changes in", or after `/tml:audit`. Writes ./.tml/frontier.md; hands off to /tml:round for a designed comparison and to /ar:start for many measured iterations under a locked harness. The operating point is the operator''s decision, not the agent''s — this skill frames it and asks. Do NOT use to discover opportunities (that is /tml:audit) or to check a change already made (that is /tml:review).'
allowed-tools: [Read, Write, Glob, Grep, Bash, AskUserQuestion]
license: MIT
---

# /tml:plan — decide where to sit, and how long to train

Two decisions, both the operator's: **where on the frontier** this project sits,
and **how long each run gets**. This skill frames them, prices the options, and
asks. It does not choose.

## First action, always

```bash
ls -la ./.tml/ 2>/dev/null
```

Read `findings.md` if present. If it is absent, say so and either run
`/tml:audit` first or proceed from what the operator states — but never invent
findings to plan against.

## Hard rules

1. **The operating point is not the agent's to choose.** Present the options with
   honest upsides _and_ downsides and ask. Silence is not consent.
2. **A quality floor is mandatory before any `spending` change is ordered.** No
   floor, no spending.
3. **Non-negotiables are vetoes.** A hard constraint touched by an `unknown` or
   `spending` exposure stops that change regardless of effect size.
4. **Every ordered change carries a revert trigger** — the observation that means
   undo it — written before it is made, not after it fails.
5. **Writes only `./.tml/frontier.md`.** No project code.

## Procedure

### 1. Establish the regime

`references/regime.md` §1 and §3: concurrent trials, local or remote execution.
This is not optional and it is not inferable — a plan calling for 60-trial
studies on a machine that runs two at a time is not a plan. Record what was
sacrificed if the regime is low (`study-design.md` §4).

### 2. Fix the step budget

`references/step-budget.md`. Determine compute-bound or not, then:

- **Not compute-bound** — pick `max_train_steps` (§2, including the constant-LR
  sweep procedure and its self-deception failure mode) and fix it across all
  trials. Never tune it inside a study.
- **Compute-bound** — plan rounds of increasing per-trial length (§3), and carry
  the transfer ladder (§4) so it is clear which round-1 conclusions are expected
  to survive: warmup and initialisation very likely, the decay schedule unlikely.

### 3. Name the non-negotiables

Ask for them; do not infer. Each is `hard` or `soft`, and named on a dimension —
mean, calibration, worst-group, robustness under shift, tails, determinism,
latency, memory. A dimension nobody names is a dimension nobody is protecting.

### 4. Frame the operating point

Present two or three concrete points, each with what it buys, what it spends, and
what it forecloses. Then **ask**. Use `AskUserQuestion` when the options are
genuinely comparable; give a recommendation and its reason first.

### 5. Order the work

Ordering rules, in priority:

1. **Defects before optimisations.** Instability (`instability.md`) and invalid
   evaluation come first — everything measured under them is conditioned on them.
2. **Measurement before changes.** If the harness cannot detect the effect, fix
   the harness first (`tier-c-protocol.md`).
3. **`none`-radius before `numeric` before `distribution`.** Verification gets
   more expensive down that list, so bank the cheap-to-verify wins first.
4. **Batch size early or not at all** (`tier-b-systems.md` B14) — it forces
   re-tuning of the optimiser and regularisation hyperparameters, so it is a
   once-early decision, not a mid-project knob.
5. **Cheap reverts before structural ones** at equal expected value.

Each entry gets: the change, the expected effect and its grade, the verification
method implied by its radius, the revert trigger, and the gate that must pass
before the next change starts.

### 6. Measurement contract and stop rule

State once, concretely: what is measured, at what `n`, against what baseline,
with what noise floor, and what counts as a real improvement. Then the **stop
rule** — the condition under which this work ends rather than continuing by
default. Time-boxed, target-based, or diminishing-returns; anything but "keep
going".

### 7. Emit

Write `./.tml/frontier.md` from `templates/frontier.md`, after showing the plan.

## Handoffs

- The next step is a **designed comparison** — a scientific question with
  nuisance parameters to optimise away → **`/tml:round`**.
- The next step is **many measured iterations under a locked harness**, gated on
  a noise floor → **`/ar:start`**. Shared vocabulary, no translation needed; say
  what it will cost before offering it.
- A change was made → **`/tml:review`**.

## Completion status

`DONE` (plan written, operating point chosen **by the operator**, stop rule
stated), `DONE_WITH_CONCERNS`, `BLOCKED`, or `NEEDS_CONTEXT`. If the operator
declined to choose an operating point, that is `NEEDS_CONTEXT`, not a default.
