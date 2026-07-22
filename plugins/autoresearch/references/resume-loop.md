# autoresearch — continuation without hooks

The loop outlives any single session, and it does so without a `Stop`,
`PreCompact` or `SessionStart` hook. Two mechanisms, one internal and one
external.

---

## 1. State on disk, re-read every invocation

Continuity comes from `./.ar/ar.jsonl` being re-read as the **mandatory first
action** of every `ar` skill, before anything else is said or done. Context is
never the carrier. A compaction, a `/clear`, a crashed terminal or a machine
reboot costs nothing: the next invocation reconstructs from disk.

Reconstruct in this order:

1. Read every line of `ar.jsonl`. Take the **last** config header — that is the
   active segment.
2. Filter result lines to that segment.
3. `runCount` = highest `run`, or 0.
4. `best` = the best `metric` among `status: "keep"` lines, honouring
   `direction`; falls back to `config.baseline` when nothing has been kept.
5. `bestCommit` = the `commit` of that line.
6. Plateau streak = consecutive `discard` and `checks_failed` statuses at the
   tail. **`crash` lines are skipped, not counted** — a crash is a failed
   measurement, not evidence against the hypothesis family, and counting it
   would pivot the strategy on the strength of an OOM.
7. Elapsed = now minus `config.startedAt`, against `maxSeconds`.

Then confirm the branch. `git branch --show-current` must equal `config.branch`.
If it does not — a session ended elsewhere, or somebody switched — **do not
switch onto it.** Create a fresh branch from the current state and open a new
segment, per the branch interlock in `protocol.md` §0. Acting on a branch this
run did not create is the one thing the interlock exists to prevent.

Print the status block before doing anything else:

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

---

## 2. The external loop — genuinely unattended runs

For overnight work, `templates/ar-loop.sh` is copied into `./.ar/` when the run starts and
run by hand:

```bash
tmux new -s ar './.ar/ar-loop.sh'
```

It invokes `claude -p "/ar:resume"` repeatedly until the state file shows
`"status":"stopped"` or a session exits non-zero. Each pass is a **fresh session
with an empty context** — which is exactly why §1's disk-first rule is not
optional.

This is an ordinary process, not a Claude Code hook. It registers nothing,
patches no settings, and stops when the terminal does. Nothing about `ar`
survives its own uninstallation.

**Guard the budget in wall-clock terms too.** `AR_MAX_PASSES` caps the driver
independently of `maxRuns`, so a pathological session that exits cleanly without
advancing the run counter cannot spin forever.

---

## 3. Cross-agent portability

The state format is plain JSONL and Markdown, so another agent can drive the same
loop. One caveat worth stating plainly: Codex honours a standing "keep going"
instruction less reliably than Claude, tending to stop and report after a single
iteration. Under Codex, drive the loop from `ar-loop.sh` rather than relying on
in-session continuation, and supervise it rather than leaving it overnight.

---

## 4. Interrupted mid-iteration

A session killed between "commit" and "measure" leaves a commit trailing
`Result: pending`. On resume, that is unambiguous and recoverable — the change is
already committed, so re-measure it and amend the trailer, rather than reverting.

```bash
git log -1 --format='%B' | grep -q 'Result: pending' && echo "re-measure HEAD"
```

A session killed during measurement leaves no commit and no result line: the
working tree is clean at the last keep, and the loop simply proceeds. Neither
case needs manual repair, and neither is a reason to reset past
`config.snapshotCommit`.
