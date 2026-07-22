---
name: status
description: Print the current autoresearch run's state — goal, baseline, noise floor, best-so-far, run tallies, budget, branch, and the last few iterations. Use for `/ar:status`, "how is the loop doing", "what's the best so far", or any read-only check on an autoresearch experiment. Reconstructs everything from `./.ar/ar.jsonl` on disk, so it works in a fresh session with no prior history. Strictly read-only — never iterates, edits, commits, or reverts.
allowed-tools: [Read, Glob, Grep, Bash]
---

# /ar:status — read-only state

Report where the run stands. Change nothing.

## Steps

1. Read state:

    ```bash
    cat ./.ar/ar.jsonl 2>/dev/null | tail -50; git branch --show-current
    ```

    No `ar.jsonl` means no run in this repo — say so, point at `/ar:start`, stop.

2. Reconstruct from the **last** config header and its segment's result lines:
   run count, keep/discard/crash tallies, best-so-far and its commit, plateau
   streak, elapsed budget. Method in
   `${CLAUDE_PLUGIN_ROOT}/references/resume-loop.md` §1.

3. Print the status block:

    ```
    AR ACTIVE — <goal>
      direction   minimize (val_bpb)
      baseline    0.981    noise floor 0.004 (±1.0×)
      best        0.842    @ a1b2c3d  (run 7)
      runs        23 total — 6 keep · 15 discard · 2 crash
      budget      23/100 runs · 4h12m/8h00m
      branch      ar/reduce-val-bpb-22-07-2026  (from main @ 9f31c07)
      last 3      r21 discard 0.851 · r22 discard 0.849 · r23 keep 0.842 ✓
      plateau     0 consecutive non-improvements
    ```

4. Flag anything anomalous without acting on it: the checked-out branch differing
   from `config.branch`, a `Result: pending` trailer on `HEAD` (an iteration
   interrupted mid-measurement), an exhausted budget, or a `stopped` sentinel.

## Hard rules

1. **Read-only.** No edits, commits, branch switches, reverts, or iterations —
   whatever the state looks like. Reporting a problem is the entire job here;
   fixing it belongs to `/ar:resume`.
2. State is read from `./.ar/` only.
3. Report the numbers as recorded. Never recompute a metric, and never infer one
   that was not measured.
