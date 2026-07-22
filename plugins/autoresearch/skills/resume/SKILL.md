---
name: resume
description: Run the autoresearch experiment loop — propose one change, measure it, keep it only if it beats the noise floor, repeat. Use to resume or continue an autoresearch run, for `/ar:resume`, for "keep iterating", "next experiment", "continue optimising", or whenever `./.ar/ar.jsonl` exists and the loop should advance. Reconstructs everything from disk, so it survives compaction, `/clear`, and a fresh session. Requires `/ar:start` to have run first.
allowed-tools: [Read, Write, Edit, Glob, Grep, Bash]
---

# /ar:resume — advance the loop

Iterate until the target is met, the budget is spent, or the run is stopped.

## First action, always (MANDATORY)

Read state from disk before saying or doing anything else. Context is never the
carrier — this is what makes the loop survive compaction and session resets.

```bash
cat ./.ar/ar.jsonl 2>/dev/null | tail -50; git branch --show-current
```

No `ar.jsonl` means no run exists — say so and point at `/ar:start`. Otherwise
reconstruct best-so-far, run count, plateau streak and budget per
`${CLAUDE_PLUGIN_ROOT}/references/resume-loop.md` §1, then print the status block
before the first iteration.

## Hard rules

1. **Never act on a branch this run did not create.** If the current branch is
   not `config.branch`, do **not** switch onto it — create a fresh branch from
   the present state and open a new segment (`references/protocol.md` §0).
2. **One atomic change per iteration.** No compound edits. Two changes give one
   number and no attribution.
3. **Commit before measuring**, with a `Result: pending` trailer; amend it with
   the real result on keep.
4. **Revert with `git checkout -- . && git clean -fd`** on discard or crash.
   Never `-fdx` — that flag deletes `./.ar/` and the run with it.
5. **Locked harness.** Any diff touching `benchmark.sh`, `checks.sh`,
   `evaluator.py` or the metric-emitting code is rejected and the hypothesis
   abandoned. Optimising a number while free to redefine it is not optimisation.
6. **Keep only above the noise floor.** Improvement must exceed
   `noiseFloor × noiseFloorMultiple`; borderline candidates get a multi-seed
   re-run _before_ the verdict, not after.
7. **Respect the budget** — `maxRuns`, `maxSeconds`, `targetMetric`.
8. **Defer execution.** Print the measurement command; do not launch long jobs.
9. **Do not stop to ask permission.** Once looping, keep going until the target
   is met, the budget is exhausted, `/ar:stop` fires, or interruption.

## The iteration

Pick one hypothesis → apply one change → commit pending → measure → gate on
`checks.sh` → decide keep/discard/crash/checks_failed → amend or revert → append
to `ar.jsonl` and `results.tsv`, update `research.md`, `worklog.md`, `ideas.md` →
next. Three consecutive non-improvements switch strategy family; five propose a
paradigm shift. Full detail in `references/protocol.md` §2–§3.

On any stopping condition, write `./.ar/final_report.md` and print — do not run —
`git switch <originBranch>`.

## Read on demand

| Need                                     | File                                               |
| ---------------------------------------- | -------------------------------------------------- |
| Iteration steps, plateau, stopping       | `${CLAUDE_PLUGIN_ROOT}/references/protocol.md`     |
| Keep threshold, confidence, seed re-runs | `${CLAUDE_PLUGIN_ROOT}/references/statistics.md`   |
| Record formats, metric contracts         | `${CLAUDE_PLUGIN_ROOT}/references/state-schema.md` |
| State reconstruction, overnight runs     | `${CLAUDE_PLUGIN_ROOT}/references/resume-loop.md`  |

Read a reference when the phase that needs it is reached — not up front.

## Completion status

End with a terminal status token as the last line of your reply — `DONE`,
`DONE_WITH_CONCERNS`, `BLOCKED`, or `NEEDS_CONTEXT` — per
`references/completion-status.md`. For `/ar:resume`, `DONE` after the iteration
is measured and kept or reverted (or a stopping condition is hit and the report
written); `DONE_WITH_CONCERNS` if the harness was flaky or a seed disagreed;
`BLOCKED` if `checks.sh` or `benchmark.sh` cannot run; `NEEDS_CONTEXT` if the run
state is missing or `/ar:start` has not run.
