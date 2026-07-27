---
name: plan
description: 'Choose an operating point on the speed↔quality frontier and turn findings into an ordered, gated change plan — with a quality floor, named non-negotiables, revert triggers, a measurement contract, and a stop rule. Use for `/parml:plan`, "which of these should I actually do", "I have N GPU-hours and need quality Q", "how much accuracy can I trade for speed here", "what order should I make these changes in", or after `/parml:audit`. Writes ./.parml/frontier.md and hands off to /ar:start when the work is many measured iterations under a locked harness. The operating point is the operator''s decision, not the agent''s — this skill frames it and asks. Do NOT use to discover opportunities (that is /parml:audit) or to check a change already made (that is /parml:review).'
allowed-tools: [Read, Write, Glob, Grep, Bash, AskUserQuestion]
license: MIT
---

# /parml:plan — decide where to sit on the frontier

Getting _onto_ the frontier is technical. Choosing _where on it_ to sit is not,
and it is not the agent's decision. This skill frames the choice, asks it once,
records the answer, and orders the work around it.

## First action, always

```bash
ls -la ./.parml/ 2>/dev/null
```

Read `findings.md` if present. If it is absent, ask whether to run
`/parml:audit` first — planning against unenumerated options produces a plan for
the wrong problem. Planning without an audit is legitimate when the operator
already knows the candidate changes; say which case you are in.

If `frontier.md` exists, this is a **revision**. Read it, restate the recorded
decision, and change it deliberately with a `Supersedes` line — never silently.

## Hard rules

1. **The operating point is asked, not assumed.** The objective form, the quality
   floor, and the non-negotiables are the operator's to state. Use
   `AskUserQuestion` once, with real options and honest downsides — not a
   questionnaire, and not a menu of six unranked choices.
2. **Present a decision as a brief.** One recommendation with its reason first,
   then each alternative with an honest upside _and_ downside. An agent that
   lists options without ranking them has moved the work, not done it.
3. **Never bank anything below `mechanism`.** `analogy` and `folklore` items may
   enter the plan only as _measurements to run_, never as changes to make.
4. **No plan without a noise floor.** If none exists, step 1 of the plan is
   measuring it. Every gate downstream is defined against it, so a plan that
   skips it is a plan whose every verdict is unfalsifiable.
5. **Every step carries a revert trigger.** A change with no stated condition for
   undoing it is not gated, and gates are the entire mechanism by which this
   stays conscious rather than opportunistic.
6. **The Not-accepted section is mandatory.** Name what would buy time and is
   being declined, and why. A plan that declines nothing has not made a choice.
7. **Order by cheap-and-certain first.** At equal expected value, prefer `none`
   radius over `numeric` over `distribution`, `neutral` exposure over `bounded`
   over `unknown`, and trivial reverts over structural. Early certainty
   compounds; early ambiguity poisons everything measured after it.
8. **Exposure against a hard constraint is a veto.** A change whose quality
   exposure could violate a §2 **hard** non-negotiable does not go into the plan
   with a tighter gate — it goes into _Not accepted_, whatever its effect size.
   Gates manage risk; they do not buy permission.
9. **Do not run the plan.** This skill writes it. Execution is the operator's, or
   `/ar:resume`'s.
10. **The `/ar:start` handoff is proposed, never taken.** Name it as an option,
    state its cost plainly — it creates a git branch and a commit on first use,
    and it wants a locked harness — and wait for an explicit yes. Do not invoke
    it as part of planning, and do not present it as the obvious next step when a
    three-item checklist executed by hand would do.
11. **Be willing to output "do not do this."** If `tier-c-protocol.md` C6 applies —
    the deliverable is a conclusion, the claim needs the standard recipe, `k = 1`,
    a hard constraint is at risk — say so as the recommendation, not as a caveat.

## Steps

1. **Read the findings**, or take the candidate changes as stated.
2. **Frame the objective** (`tier-c-protocol.md` C1). One of four forms:
   minimise cost subject to a quality floor; maximise quality subject to a
   budget; minimise variance; minimise cost per unit of statistical power. Ask
   which, with a recommendation. The fourth form is the right answer more often
   than people expect and is almost never volunteered — if the deliverable is a
   _conclusion_ rather than a model, say so.
3. **Ask for the non-negotiables**, and mark each **hard** or **soft**. That
   distinction is what makes rule 8 operable: hard vetoes, soft is negotiable at
   a stated price. Calibration, worst-group quality, robustness, determinism,
   comparability with a baseline, tail latency, legibility. Anything left unnamed
   here will be spent. Get `k` if the audit did not.
4. **Adjudicate exposure against §2**, before ordering anything. Each candidate's
   quality exposure (`evidence-grades.md` §3.2) either clears the hard
   constraints or leaves the plan. Do this first: it is cheaper to remove a
   candidate than to order it and then discover it was never admissible.
5. **Order what survives.** Rule 7. Fold in the intersections: any A∩B item is
   priced end to end, never on one factor (`evidence-grades.md` §4).
6. **Attach a gate to each step** — the confirming measurement, the `n` it needs,
   whether both directions are required (C4), the revert trigger, and the
   pitfalls to watch.
7. **Write the stop rule** (C8), before starting rather than after. Deciding to
   stop while looking at a tantalising unexplored item is a decision made under
   the worst possible conditions.
8. **Write `./.parml/frontier.md`** from `templates/frontier.md`. Unlike
   `findings.md`, this one is a **decision record** and is usually worth
   committing — it is what stops the same trade being re-argued in three weeks
   with nobody remembering what was agreed. Recommend it; do not commit it
   yourself.
9. **Offer a handoff; do not take one.** Present the two routes with their costs
   and a recommendation, then stop:
    - **Execute the table by hand** — right for a handful of changes. Run
      `/parml:review` on each diff before accepting it. No new branch, no new
      state, and the default when in doubt.
    - **`/ar:start`** — right only when the work is genuinely many measured
      iterations under a locked harness. Say plainly what it costs: it creates a
      dedicated git branch and a commit on first use, and it will want the harness
      frozen for the whole run. It takes this objective, baseline and noise floor
      directly, so nothing needs restating — but **wait for an explicit yes and
      let the operator invoke it.** Never invoke it from here.

    Either way, suggest recording the decision in project memory so the next
    session does not re-litigate it.

## The four objective forms, and when each is right

| Form                                      | Right when                                       | Watch                                                             |
| ----------------------------------------- | ------------------------------------------------ | ----------------------------------------------------------------- |
| minimise cost s.t. quality ≥ Q            | Q is externally fixed — baseline, SLA, threshold | Q must be a _measured_ floor with an `n`, not a hope              |
| maximise quality s.t. cost ≤ B            | The budget is hard — deadline, grant, device     | Spend the budget on steps, not on a bigger model, unless measured |
| minimise variance at fixed cost & quality | The deliverable is a comparison                  | Some speedups _raise_ variance; that is a regression here         |
| minimise cost per unit statistical power  | The deliverable is a conclusion                  | Optimise `time × runs-needed`; required `n` grows as `σ²` (C6.1)  |

## Read on demand

| Need                                        | File                                                     |
| ------------------------------------------- | -------------------------------------------------------- |
| Objective forms, noise floor, stop rule, C6 | `${CLAUDE_PLUGIN_ROOT}/references/tier-c-protocol.md`    |
| Grades, pricing, radius, the tier algebra   | `${CLAUDE_PLUGIN_ROOT}/references/evidence-grades.md`    |
| What a candidate change actually does       | `${CLAUDE_PLUGIN_ROOT}/references/tier-a-algorithmic.md` |
|                                             | `${CLAUDE_PLUGIN_ROOT}/references/tier-b-systems.md`     |
| What each accepted change could break       | `${CLAUDE_PLUGIN_ROOT}/references/pitfalls.md`           |
| Output shape                                | `${CLAUDE_PLUGIN_ROOT}/templates/frontier.md`            |

## Completion status

End with a terminal status token as the last line of your reply.

- **DONE** — operating point recorded, plan ordered and gated, stop rule written,
  handoff named.
- **DONE_WITH_CONCERNS** — plan written with a stated weakness: no noise floor
  yet, a constraint that cannot currently be measured, or a dependence on an
  `analogy`-grade estimate. Name it.
- **BLOCKED** — the objective cannot be stated because the quality floor is not
  measurable with the harness in place.
- **NEEDS_CONTEXT** — waiting on the operator for the objective form, the quality
  floor, `k`, or the non-negotiables. This is the expected outcome of step 3 when
  the answer has not been given.
