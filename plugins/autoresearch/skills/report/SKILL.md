---
name: report
description: Write the final summary of an autoresearch run to `./.ar/final_report.md` — trajectory, best commit and its diff, what worked, what failed, and what to try next. Use for `/ar:report`, "write up the autoresearch results", or "summarise the experiment loop". Reads `./.ar/ar.jsonl` from disk, so it works in a fresh session. Writes only the report; never iterates, commits, or reverts, and leaves the loop able to continue.
allowed-tools: [Read, Write, Glob, Grep, Bash]
---

# /ar:report — write the run up

Turn the record into something a person can read. Do not iterate.

## Steps

1. Read state (`cat ./.ar/ar.jsonl | tail -50`, plus `worklog.md` and
   `results.tsv` if present). No `ar.jsonl` means nothing to report — say so and
   stop.
2. Reconstruct the run per `${CLAUDE_PLUGIN_ROOT}/references/resume-loop.md` §1,
   across **all** segments, not just the last: a segment boundary marks a harness
   or baseline change, so metrics either side of it are not comparable and the
   report must say where the boundaries fell rather than plotting through them.
3. Pull the winner chain from git — it is an independent record of the same run:

    ```bash
    git log --format='%h %s' --grep='"status":"keep"' <config.branch>
    git diff <config.snapshotCommit>..<bestCommit> --stat
    ```

4. Write `./.ar/final_report.md`:
    - **Goal and setup** — objective, metric, direction, harness, budget.
    - **Result** — baseline → best, absolute and relative, with the confidence
      tier. State plainly whether the total gain clears the noise floor; a run
      that ended inside its own scatter did not find anything, and the report
      says so rather than dressing it up.
    - **Trajectory** — the keep chain, each with commit, metric, delta and the
      one-line description of the change.
    - **What worked** — the winning changes and, where the record supports it,
      why they worked. Distinguish an explanation from a guess.
    - **What failed** — discarded families of hypotheses. This is the part with
      the most reuse value; a future run should not re-derive these.
    - **Caveats** — crashes, `checks_failed` iterations, seeds that disagreed,
      segment boundaries.
    - **Next** — the strongest untried ideas, from `ideas.md` and the plateau
      history.
5. Report the path. `.gitignore` carries `!.ar/final_report.md`, so the report is
   trackable if it should be committed — offer, do not commit unasked.

## Hard rules

1. **Write `final_report.md` and nothing else.** No iterating, no commits, no
   branch switches, no reverts.
2. Every number comes from `ar.jsonl` or git. Never recompute or estimate one.
3. Report failures and null results as prominently as wins. A loop that banked
   noise is a finding; concealing it wastes the next run.

## Completion status

End with a terminal status token as the last line of your reply — `DONE`,
`DONE_WITH_CONCERNS`, `BLOCKED`, or `NEEDS_CONTEXT` — per
`references/completion-status.md`. For `/ar:report`, `DONE` once
`final_report.md` is written and its path reported; `NEEDS_CONTEXT` if `ar.jsonl`
is absent or empty (nothing to summarise).
