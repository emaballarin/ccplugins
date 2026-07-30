---
name: analyze
description: 'Extract insight from a finished study and return a variance-aware adopt verdict — search-space boundaries, sampling density, infeasible fraction, training-curve pathologies, isolation plots, then adopt or not. Use for `/tml:analyze`, "here are my sweep results", "which config should I pick", "did this change actually help", "why do my runs disagree", "read this wandb export", "is this result real", or after `/tml:round`. Works standalone on results it did not produce — a CSV, a JSONL, or a tracker export is enough, and it names which checks the missing fields disable. Read-first: writes only under ./.tml/ and never edits project code. Do NOT use to design a study (that is /tml:round) or to review a code diff (that is /tml:review).'
allowed-tools: [Read, Write, Glob, Grep, Bash]
license: MIT
---

# /tml:analyze — what the study actually showed

Run the checklist **before** answering the round's question, because several of
its entries can invalidate the round, and nobody wants to hear that after being
told the answer.

## First action, always

```bash
ls -la ./.tml/rounds/ 2>/dev/null | tail -5
```

Then establish which mode you are in:

- **Designed** — a study spec exists in `./.tml/rounds/NNN/`. Read it. The role
  assignment and the fixed-hyperparameter caveats are what make the fairness
  question answerable.
- **Standalone** — results only, no spec. This is a normal mode, not a degraded
  one (`references/regime.md` §4). Ask which hyperparameters the question is
  about; treat the rest as unknown-role; and answer the fairness question
  "cannot be determined" rather than "yes".

## Hard rules

1. **Checklist before conclusion.** In order, and reported even when it passes.
2. **Never invent a role assignment** you were not given. "Cannot be determined"
   is a real finding — it means the comparison's fairness is unverified.
3. **Name the disabled checks.** Missing curves disable overfitting and
   late-variance detection; a missing infeasibility flag disables §4. Silence
   about a check that could not run reads as a check that passed.
4. **Read-first.** Writes only under `./.tml/`. Never edits project code.

## Procedure

### 1. Ingest

The expected shape is `templates/results-example.jsonl`. Coerce a CSV or tracker
export into it. **Required** per trial: an identifier, the hyperparameters, and
the objective. **Optional, and each one gates a check**: the metric-vs-step
series, the best-step, the infeasibility flag and reason, the seed, wall-clock.

Say what was ingested and what was absent before analysing anything.

### 2. The checklist — `references/diagnostics.md` §1

1. **Search-space boundaries** (§2) — plot the objective against each varied
   hyperparameter. Best points hugging a bound means the _space_ decided the
   answer; expand and re-run. If everything above some learning rate is
   infeasible **and** the best trials sit at that edge, stop and go to
   `references/instability.md` — that is a stability defect wearing an
   optimum's clothes.
2. **Sampling density** (§3) — no general answer exists; say so, and show how
   many points landed in the good region.
3. **Infeasible fraction** (§4) — a large fraction means a bad space or a bug.
   Report it as a number with reasons, never as missing rows.
4. **Optimisation failures** → `references/instability.md`.
5. **Training curves** (§5) — problematic overfitting, late step-to-step
   variance, still-improving, saturated-early, or training loss rising (a bug).
   Check the best trial of **every** scientific setting, not just the overall
   best, and look at the whole population: selecting the winner suppresses
   overfitting and quietly rewards configurations that were merely hobbled.
6. **Was the nuisance tuning good enough** to make the comparison fair
   (`references/study-design.md` §4)?

If 1–4 fail, the corrective action is to revise and re-run, not to interpret
harder. Say that plainly rather than producing a hedged answer.

### 3. Answer the round's question

Isolation plots (`diagnostics.md` §6): best trial per scientific value, after
optimising the nuisance dimensions away. Bucket the axis for a continuous
scientific hyperparameter under quasi-random data.

If the question is "include X at all", the no-X baseline must have been tuned
**equally well**. A comparison against an untuned baseline is not evidence.

### 4. The adopt verdict

`diagnostics.md` §7. Name which variance could explain the difference — trial,
study, or data — and be explicit that a significance test on a fixed validation
set does not cover trial variance. Characterise trial variance by re-running the
best trial `n` times where budget allows.

Then one of:

- **adopt** — beats the incumbent accounting for both retrain variances, and the
  improvement outweighs the complexity it adds;
- **adopt provisionally** — plausible but under-measured; record it _as
  provisional_, with the revisit trigger. This is the honest state when budget is
  short, and it is only honest if the provisionality is written down;
- **reject** — within noise, or the complexity is not worth it;
- **cannot determine** — with the specific missing measurement named.

Complexity is a real cost, paid forever, by people who did not run the study.

### 5. Emit

Append the verdict to the round directory, or write `./.tml/analysis-<date>.md`
in standalone mode. Carry forward: the checklist results, the disabled checks,
the caveats inherited from fixed hyperparameters, and what the next round should
ask.

## Handoffs

- Adopted, and the next question is a new comparison → **`/tml:round`**.
- The study exposed instability → **`references/instability.md`**, then re-run.
- The adopted change needs a code-level check → **`/tml:review`**.

## Completion status

`DONE` (checklist run and reported, verdict given with its variance basis),
`DONE_WITH_CONCERNS` (+ which checks could not run), `BLOCKED`, or
`NEEDS_CONTEXT`.
