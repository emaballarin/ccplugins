# autoresearch — loop protocol

Read this when running `/ar:start` or `/ar:resume`. Companion files:
`statistics.md` (keep/revert maths), `state-schema.md` (file and record formats),
`resume-loop.md` (continuation and overnight runs).

---

## 0. Branch interlock (read before touching anything)

The loop hard-reverts working trees. That is only safe if it can never reach work
it did not create. Two rules make it safe, and they are not optional.

**Never act on a branch you did not create.** Every phase that edits, commits or
reverts runs on a branch `ar` brought into existence. If the current branch was
not created by `ar` for this run, create one before doing anything else.

**Carry the incoming state across, then floor it with a snapshot commit.**
`git switch -c` takes uncommitted and untracked files with it, so nothing is lost
in the move — but an uncommitted file is still one `git clean` away from
oblivion. Committing it immediately turns the incoming state into the revert
floor.

```bash
ORIGIN="$(git branch --show-current)"
BRANCH="ar/<slug>-$(date +%d-%m-%Y)"
git switch -c "${BRANCH}"                       # brings the dirty tree along
printf '.ar/*\n!.ar/final_report.md\n' >>.gitignore
git add -A
git commit --allow-empty -m "ar: snapshot of pre-existing working tree

Revert floor for the ${BRANCH} loop. Everything present when the run
started is captured here, so discard/crash reverts cannot destroy it."
SNAPSHOT="$(git rev-parse --short HEAD)"
```

Record `originBranch`, `branch` and `snapshotCommit` in the config header
(`state-schema.md`). If `BRANCH` already exists, suffix `-2`, `-3`, … rather than
reusing it — reusing a branch means acting on one `ar` did not create _this run_.

**Revert with `git clean -fd`, never `-fdx`.** `./.ar/` is gitignored precisely so
that plain `clean` leaves it alone. The `-x` flag would delete the loop's own
state mid-run. This is the single most destructive mistake available here.

```bash
git checkout -- . && git clean -fd              # correct
git checkout -- . && git clean -fdx             # NEVER — wipes ./.ar/
```

Leave the operator on their original branch when the run ends: `/ar:report` and
`/ar:stop` print `git switch ${ORIGIN}` rather than running it, so the experiment
branch stays checked out for inspection until they choose otherwise.

---

## 1. Start — a fresh run

1. **Agree the objective before any side effect.** Goal, metric name, direction,
   target if any, budget. State it back and get agreement while nothing has yet
   been created. This ordering is deliberate: starting is the only part of the loop
   that can fire on a misread intent, and every step below it writes to somebody
   else's repository. Confirming first makes that failure cost a sentence.
2. **Establish the branch and snapshot** per §0. Slug the goal to lowercase
   alphanumerics and hyphens, capped at ~40 characters. This is the run's first
   side effect; everything after it is recoverable from the snapshot.
3. **Create `./.ar/` and populate it** from the bundled templates:

    ```bash
    mkdir -p ./.ar
    cp -n "${CLAUDE_PLUGIN_ROOT}/templates/ar.config.json" ./.ar/
    cp -n "${CLAUDE_PLUGIN_ROOT}/templates/benchmark.sh"   ./.ar/
    cp -n "${CLAUDE_PLUGIN_ROOT}/templates/ar-loop.sh"     ./.ar/
    # checks.sh and evaluator.py only if that contract is in use
    chmod +x ./.ar/*.sh ./.ar/evaluator.py 2>/dev/null || true
    ```

4. **Hand the harness over.** Write the agreed objective into `ar.config.json`,
   then stop and ask for `benchmark.sh` and the remaining config to be filled in.
   **Never fabricate a benchmark.** A benchmark invented to make the loop start is
   a benchmark that measures nothing, and every number downstream of it is
   fiction. The stub exits non-zero on purpose; that is the correct behaviour
   until it is wired to a real run.
5. **Measure the noise floor.** Run the unmodified baseline `baselineRepeats`
   times (default 5) and reduce to a baseline value and a noise floor per
   `statistics.md`. Print the exact command; do not launch a long job.
6. **Write the config header** to `./.ar/ar.jsonl`, then seed `research.md`
   (living state), `worklog.md` (narrative) and `ideas.md` (backlog).
7. **Print the status block** and hand back. Starting does not iterate.

---

## 2. Iteration

One pass of the loop. Everything here is per-iteration; no step is skippable.

1. **Pick one hypothesis.** Smallest structural change first; anything that
   merely scales compute goes last. Prefer an idea already in `ideas.md`; if a
   better one surfaces, log it there first.
2. **Apply exactly one atomic change.** No compound edits. Two changes measured
   together yield one number and no attribution — the iteration is wasted even
   if the number improves.
3. **Refuse locked-harness edits.** If the change would touch any path in
   `lockedPaths`, abandon it and pick another hypothesis. Verify before
   committing:

    ```bash
    git diff --name-only HEAD -- ./.ar/benchmark.sh ./.ar/checks.sh ./.ar/evaluator.py
    ```

    Non-empty output means stop, revert, and record the attempt in `worklog.md`.

4. **Commit before measuring**, with a pending trailer:

    ```bash
    git add -A && git commit -m "ar<NNN>: <one-line description>

    Result: pending"
    ```

    Committing first is what makes the revert cheap and total. A change measured
    before it is committed cannot be reverted to a known point.

5. **Measure.** Print the exact command and let it be run:

    ```bash
    AR_SEED=0 bash ./.ar/benchmark.sh
    ```

    Parse the result per the declared contract in `state-schema.md`. If the run
    crashed or emitted no parsable metric, the status is `crash` — not a keep, not
    a discard on merit.

6. **Gate on correctness.** If `checks.sh` is in use, run it. Non-zero exit means
   `checks_failed`, which blocks a keep regardless of the metric.
7. **Decide** per `statistics.md`: `keep`, `discard`, `checks_failed` or `crash`.
   Borderline candidates get a multi-seed re-run before the verdict, not after.
8. **Apply the verdict.**
    - **keep** — amend the trailer to the real result, update best-so-far:

        ```bash
        git commit --amend -m "ar<NNN>: <description>

        Result: {\"metric\":<num>,\"delta\":<num>,\"confidence\":<num>,\"status\":\"keep\"}"
        ```

    - **discard / crash / checks_failed** — hard-revert to the last good commit:

        ```bash
        git checkout -- . && git clean -fd
        git reset --hard HEAD~1        # drop the pending commit itself
        ```

        Never `-fdx` (§0).

9. **Persist.** Append a result line to `ar.jsonl` and a row to `results.tsv`;
   refresh `research.md`; append hypothesis, outcome and the next idea to
   `worklog.md`; move the spent idea out of `ideas.md`.
10. **Continue.** Do not stop to ask permission. Go straight to the next
    iteration until a stopping condition in §4 fires.

---

## 3. Plateau handling

Consecutive non-improvements are the signal to widen the search, not to stop.

A streak counts `discard` and `checks_failed` iterations. **`crash` does not
count** — it is a failed measurement, not evidence against the hypothesis, and
letting an OOM push the run toward a paradigm shift throws away a strategy family
that was never actually tested. A crash interrupts the streak without resetting
it: the two discards either side of a crash are a streak of two.

| Streak            | Response                                                                                                                                               |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **3 in a row**    | Switch strategy family. If the last three were all regularisation tweaks, move to architecture, data, or objective. Log the switch.                    |
| **5 in a row**    | Propose a paradigm shift — question a premise the run has held fixed since the run began (the loss, the representation, the evaluation split). Log it. |
| **After a shift** | Reset the streak counter. A paradigm shift that fails is itself information; record why in `worklog.md` before moving on.                              |

A plateau never ends the loop on its own. Only §4 does.

---

## 4. Stopping

The loop ends when, and only when, one of these holds:

- `targetMetric` reached, honouring `direction`.
- `maxRuns` iterations completed.
- `maxSeconds` of wall-clock elapsed since the config header timestamp.
- `/ar:stop` was invoked, or a `status:stopped` sentinel is present.
- The operator interrupts.

On any of these, write `./.ar/final_report.md` (see `state-schema.md`) and print
the command to return to the original branch. Do not switch branches unasked.
