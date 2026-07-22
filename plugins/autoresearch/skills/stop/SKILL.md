---
name: stop
description: End the current autoresearch run — append a `status:stopped` sentinel to `./.ar/ar.jsonl`, which is also what halts the external `ar-loop.sh` driver. Use for `/ar:stop`, "stop the loop", "halt autoresearch", or "that's enough iterations". Writes the sentinel and the final report, then prints (does not run) the command to return to the original branch. Never reverts or discards work — every kept commit stays on the experiment branch.
allowed-tools: [Read, Write, Glob, Grep, Bash]
---

# /ar:stop — end the run

Halt cleanly, leaving everything recoverable.

## Steps

1. Read state (`cat ./.ar/ar.jsonl | tail -50`). No `ar.jsonl` means no run to
   stop — say so and stop.
2. If `HEAD` carries a `Result: pending` trailer, an iteration was interrupted
   mid-measurement. Leave the commit alone, and record it in the sentinel's
   `reason` so a later `/ar:resume` re-measures rather than reverting it.
3. Append the sentinel — the last line of the file, and what `ar-loop.sh` greps
   for:

    ```json
    { "run": <n>, "status": "stopped", "segment": <s>, "reason": "<why>" }
    ```

4. Write `./.ar/final_report.md` (see the `/ar:report` skill for its shape).
5. Print the final status block, the best commit, and — as text, not as a command
   to run — how to get back:

    ```
    git switch <config.originBranch>          # return to where the run started
    git log --format='%h %s' --grep='"status":"keep"' <config.branch>
    ```

## Hard rules

1. **Destroy nothing.** No reverts, no branch deletion, no `git clean`. Stopping
   is not discarding: the experiment branch and every kept commit stay exactly as
   they are, and the operator decides later what to merge or bin.
2. **Do not switch branches.** Print the command and leave the experiment branch
   checked out for inspection.
3. Stopping is reversible — a later `/ar:resume` opens a new segment and carries
   on from the same state. Say so.
