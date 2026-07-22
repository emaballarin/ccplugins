---
name: start
description: 'Open a new autoresearch experiment loop — dedicated `ar/…` git branch, `./.ar/` state, and a measured baseline noise floor so later gains can be told apart from run-to-run scatter. Invoke ONLY when explicitly asked to start an autoresearch run, open an experiment loop, or `/ar:start` — e.g. "autoresearch this", "start an ar run", "set up a loop to minimise X". Do NOT auto-fire on ordinary optimisation work. "Make this faster", "improve the accuracy", "tune these hyperparameters", "benchmark this", "find the best configuration" are normal requests to handle directly, not loops. Warranted only when many measured iterations under a locked harness are wanted — it creates a git branch and a commit on first use.'
allowed-tools: [Read, Write, Edit, Glob, Grep, Bash]
---

# /ar:start — begin an autoresearch run

Stand up the loop: dedicated branch, `./.ar/` state, a real harness, and a
measured noise floor. Starting does **not** iterate — `/ar:resume` does that.

## First action, always

Check for existing state before anything else:

```bash
ls -la ./.ar/ar.jsonl 2>/dev/null && git branch --show-current
```

If `ar.jsonl` already exists, this is not a fresh run. Print the status block and
say so — offer `/ar:resume` to continue or an explicit new-segment start
over. Never silently overwrite a run in progress.

## Hard rules

1. **Confirm before creating.** If this fired on inferred rather than stated
   intent, describe what opening a loop would do and confirm it is wanted before
   step 2. Ordinary optimisation — making something faster, tuning a few
   hyperparameters, running a benchmark — is handled directly. A loop is for many
   measured iterations under a locked harness, and it is not free: it branches
   and commits.
2. **Never act on a branch this run did not create.** Create `ar/<slug>-<DD-MM-YYYY>`,
   carrying the current working tree across — uncommitted and untracked files
   included — then commit it immediately as the revert floor. Full sequence in
   `${CLAUDE_PLUGIN_ROOT}/references/protocol.md` §0.
3. **Never fabricate a benchmark.** The harness is filled in by the operator, and
   the loop does not start until it emits a real number. An invented benchmark
   makes every number downstream of it fiction.
4. **Locked harness.** `benchmark.sh`, `checks.sh`, `evaluator.py` and the code
   emitting the metric are never edited, for the whole run. A score is only
   meaningful while the thing measuring it holds still.
5. **State lives only under `./.ar/`.** Nothing is written outside the target
   repo, and no global or shared store is touched.
6. **Defer execution.** Print exact commands for long runs; do not launch
   training inside the session.
7. `./.ar/` is gitignored as `.ar/*` plus `!.ar/final_report.md` — which is also
   what keeps `git clean -fd` from eating the loop's own state.

## Steps

1. **Confirm the objective first** — goal, metric name, `minimize` or `maximize`,
   target if any, budget. State it back and get agreement **before touching
   anything**. Nothing in this step has side effects, which is the point: a
   misfired invocation costs one sentence rather than a branch and a commit in
   somebody's repository.
2. **Branch and snapshot** — `references/protocol.md` §0. First side effect of
   the run; everything after it is recoverable from the snapshot.
3. **Scaffold** `./.ar/` from `${CLAUDE_PLUGIN_ROOT}/templates/`
   (`ar.config.json`, `benchmark.sh`, `ar-loop.sh`, plus `checks.sh` /
   `evaluator.py` if that contract applies). Write the agreed objective into
   `ar.config.json`.
4. **Hand over the harness.** Stop here and ask for `benchmark.sh` and the
   config to be completed. This is the one point where starting waits on work it
   cannot do itself.
5. **Measure the noise floor** — `baselineRepeats` baseline runs, reduced to
   `baseline` and `noiseFloor` per `references/statistics.md`.
6. **Write the config header** to `./.ar/ar.jsonl`; seed `research.md`,
   `worklog.md`, `ideas.md` — see `references/state-schema.md`.
7. **Print the status block** and stop. Suggest `/ar:resume`.

## Read on demand

| Need                                    | File                                               |
| --------------------------------------- | -------------------------------------------------- |
| Branch interlock, start and loop detail | `${CLAUDE_PLUGIN_ROOT}/references/protocol.md`     |
| Baseline, noise floor, keep threshold   | `${CLAUDE_PLUGIN_ROOT}/references/statistics.md`   |
| File formats and metric contracts       | `${CLAUDE_PLUGIN_ROOT}/references/state-schema.md` |

Read a reference when the step that needs it is reached — not up front.

## Completion status

End with a terminal status token as the last line of your reply — `DONE`,
`DONE_WITH_CONCERNS`, `BLOCKED`, or `NEEDS_CONTEXT` — per
`references/completion-status.md`. For `/ar:start`, `NEEDS_CONTEXT` is the
expected outcome at the harness hand-over (step 4, waiting on `benchmark.sh` and
the config); `DONE` once the noise floor is measured and the config header is
written; `BLOCKED` if no clean baseline can be established.
