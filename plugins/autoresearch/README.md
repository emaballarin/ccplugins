# ar

**autoresearch** — an autonomous experiment loop that runs on stock Claude Code.
Propose one change, measure it, keep it only if it beats the noise floor, repeat.

Metric-agnostic: anything that reduces to a number works — a validation loss, a
wall-clock time, a throughput figure, a solver's residual, a yield.

## Install

```
/plugin marketplace add emaballarin/ccplugins
/plugin install ar@ccplugins
```

## Skills

| Skill        | When                  | What it does                                                                                                                           |
| ------------ | --------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| `/ar:start`  | Once per experiment   | Open a dedicated `ar/…` branch, scaffold `./.ar/`, take the harness, and measure the baseline noise floor. Does not iterate.           |
| `/ar:resume` | To run the loop       | One atomic change → commit → measure → keep or revert → repeat, until target, budget, or stop. Rebuilds its state from disk each time. |
| `/ar:status` | Any time              | Read-only status block: baseline, noise floor, best-so-far, tallies, budget, branch, last iterations.                                  |
| `/ar:report` | When there's a result | Write `./.ar/final_report.md` — trajectory, best commit, what worked, what failed, what to try next.                                   |
| `/ar:stop`   | To end                | Append the `status:stopped` sentinel, write the report, and leave every kept commit intact.                                            |

## A worked example

Minimising a training loss, from nothing to a running loop:

```
/ar:start minimise val_loss on the 30M-param run in src/train.py
```

`/ar:start` opens `ar/minimise-val-loss-22-07-2026`, commits the current working tree
as a revert floor, and drops `ar.config.json` + `benchmark.sh` into `./.ar/`.
Fill the harness in so it ends by printing one line:

```bash
python -O -m src.train --seed "${AR_SEED:-0}" --config ./config.yaml >run.log 2>&1
echo "METRIC val_loss=$(grep -oP 'final val_loss: \K[0-9.]+' run.log | tail -1)"
```

It then runs the unmodified baseline five times to learn how much the number
moves on its own — say `0.981 ± 0.004`. That scatter is the bar: a change that
buys 0.002 has bought nothing.

```
/ar:resume
```

Each iteration makes one change, commits it with a `Result: pending` trailer,
prints the measurement command, and either amends the trailer with a real result
or hard-reverts. Improvements inside 1–2× the noise floor are re-run across seeds
before being believed. Three flat iterations switch strategy family; five propose
a paradigm shift.

```
/ar:status     # where are we
/ar:stop       # done — writes final_report.md, keeps every winning commit
```

For unattended runs, `./.ar/ar-loop.sh` drives `/ar:resume` in a terminal:

```bash
tmux new -s ar './.ar/ar-loop.sh'
```

## Design notes

**No hooks, no MCP, no settings patching.** Skills and templates only. Loop
continuity comes from `./.ar/ar.jsonl` being re-read as the first action of every
invocation — not from a `Stop` hook and not from context — which is also why a
compaction, a `/clear`, or a machine reboot costs nothing. `ar-loop.sh` is an
ordinary process, not a registered hook; it stops when its terminal does.

**All state is project-local.** Everything lives in the target repo's `./.ar/`.
Nothing global is written, so installing `ar` cannot change what any other plugin
sees.

**The harness is locked.** `benchmark.sh`, `checks.sh`, `evaluator.py` and the
metric-emitting code are never edited during a run. An agent allowed to redefine
the number it is optimising will eventually improve the number by weakening the
measurement — loosening a tolerance or dropping a test case reads as progress and
is pure score inflation. Changing the harness ends the segment and forces a fresh
baseline.

**Nothing acts on a branch it did not create.** The loop hard-reverts working
trees, which is only safe because `/ar:start` first creates its own branch,
carries the incoming tree across — untracked files included — and commits it as
the revert floor. Reverts use `git clean -fd`, never `-fdx`, so the gitignored
`./.ar/` state survives.

**Execution is deferred.** The skills print exact run commands; long jobs belong
on a cluster, not inside an agent session.

## Attribution

Protocol behaviour re-implemented from three MIT-licensed projects — see
[`NOTICE`](NOTICE). Ultimately inspired by
[karpathy/autoresearch](https://github.com/karpathy/autoresearch).

MIT — see [`LICENSE`](LICENSE).

## Links

- Marketplace: [emaballarin/ccplugins](https://github.com/emaballarin/ccplugins)
- Changelog: [CHANGELOG.md](CHANGELOG.md)
