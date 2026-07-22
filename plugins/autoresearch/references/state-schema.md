# autoresearch — measurement contracts and state schema

Everything the loop knows lives in the target repo's `./.ar/`. Nothing is written
anywhere else, and no memory system is involved. `ar.jsonl` is the source of
truth; every other file is a convenience view that can be rebuilt from it.

---

## Measurement contracts

Exactly one is in force per segment, declared as `contract` in `ar.config.json`.

### `metric` — stdout lines (primary)

The harness prints one or more lines to stdout:

```
METRIC val_bpb=0.842
METRIC tokens_per_sec=14320
```

Parse with `^METRIC\s+(\S+)=(-?[0-9.eE+]+)\s*$`. The metric named by
`config.metric` is primary; if absent, the first `METRIC` line is primary.
Secondary metrics are optional — but once one appears it must appear on every
later run, so the table stays rectangular. A missing secondary is a `crash`, not
a silently blank cell.

### `evaluator` — a JSON verdict (alternative)

A scorer prints exactly one JSON object on stdout:

```json
{ "pass": true, "score": 0.913 }
```

`pass: false` maps to `checks_failed` and blocks a keep regardless of `score`.
Use this when the score is a real computation — separation quality, a custom
loss, a composite — rather than something greppable out of a log.

**Unparsable output under either contract is `crash`.** Never guess a number from
surrounding text, and never carry forward the previous run's value. A fabricated
measurement corrupts the baseline and every comparison after it.

---

## `ar.jsonl` — source of truth, append-only

Segment-aware: a segment is a span over which the harness and noise floor are
constant. Anything that invalidates comparability — a harness change, a new
baseline — opens a new segment with a fresh header.

**Config header**, one line, first of each segment:

```json
{
    "config": {
        "goal": "reduce val bits-per-byte on the 30M-param run",
        "metric": "val_bpb",
        "direction": "minimize",
        "contract": "metric",
        "command": "bash ./.ar/benchmark.sh",
        "maxRuns": 100,
        "maxSeconds": 28800,
        "targetMetric": 0.9,
        "baseline": 0.981,
        "noiseFloor": 0.004,
        "noiseFloorMultiple": 1.0,
        "borderlineSeeds": [0, 1, 2],
        "lockedPaths": ["benchmark.sh", "checks.sh", "evaluator.py"],
        "originBranch": "main",
        "branch": "ar/reduce-val-bpb-22-07-2026",
        "snapshotCommit": "9f31c07",
        "startedAt": "22/07/2026 03:14"
    },
    "segment": 0
}
```

`originBranch`, `branch` and `snapshotCommit` are what make the revert floor
recoverable after a session reset — without them a resumed loop cannot tell how
far back it is allowed to reset. They are written once and never edited.

**Result line**, one per iteration:

```json
{
    "run": 7,
    "commit": "a1b2c3d",
    "metric": 0.842,
    "metrics": { "val_bpb": 0.842, "tokens_per_sec": 14320 },
    "seedMetrics": null,
    "delta": 0.021,
    "status": "keep",
    "confidence": 2.4,
    "segment": 0,
    "note": "tie psi_j across blocks"
}
```

- `status ∈ {keep, discard, crash, checks_failed, stopped}`.
- `seedMetrics` — array of per-seed values when a borderline re-run happened,
  otherwise `null`.
- `confidence` — `improvement / noiseFloor`, or `null` on a deterministic
  harness.
- A `stopped` line carries `{"run": <n>, "status": "stopped", "reason": "..."}`
  and is the sentinel `ar-loop.sh` greps for.

---

## Derived files

| File              | Shape                                                                                                          |
| ----------------- | -------------------------------------------------------------------------------------------------------------- |
| `results.tsv`     | Tab-separated: `iteration  commit  metric  delta  status  confidence  description`. Header row. Rebuildable.   |
| `worklog.md`      | Append-only narrative — hypothesis, what happened, what it means, next idea. The part a person actually reads. |
| `ideas.md`        | Backlog of deferred experiments. Ideas move out when spent, with their outcome noted.                          |
| `research.md`     | Living one-screen summary: goal, baseline, current best, open threads. Overwritten, not appended.              |
| `final_report.md` | Written at stop: trajectory, best commit and its diff, what worked, what failed, what to try next.             |

`.gitignore` carries `.ar/*` and `!.ar/final_report.md`, so the scratch state
stays untracked (and therefore survives `git clean -fd`) while the report can be
committed if wanted. The negation needs `.ar/*` rather than `.ar/` — git will not
re-include a file inside a directory it has already excluded.

---

## Winner tracking

The branch is the durable record. Every `keep` is a commit on
`ar/<slug>-<DD-MM-YYYY>` carrying a `Result:` trailer with the measured JSON;
discards leave no trace beyond their `ar.jsonl` line. So:

```bash
git log --format='%h %s' --grep='"status":"keep"' ar/reduce-val-bpb-22-07-2026
```

reconstructs the winner chain from git alone, with no state file at all. That
redundancy is deliberate — `ar.jsonl` and the branch are independent records of
the same run, and disagreement between them is a signal something went wrong.
