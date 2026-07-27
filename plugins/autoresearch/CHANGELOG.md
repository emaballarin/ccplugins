# Changelog

All notable changes to the `ar` (autoresearch) plugin are documented here.
This project adheres to [Semantic Versioning](https://semver.org/).

## 0.3.0 — 2026-07-27

Coordinated marketplace version bump, alongside the `ccsci` 0.4.0 kernel-syntax
fix. No skill logic changed.

## 0.2.1 — 2026-07-23

Housekeeping — coordinated marketplace version alignment. No skill logic changed.

## 0.2.0 — 2026-07-23

### New — completion-status protocol

The four action skills (`/ar:start`, `/ar:resume`, `/ar:report`, `/ar:stop`) now
end with a terminal status token — `DONE`, `DONE_WITH_CONCERNS`, `BLOCKED`, or
`NEEDS_CONTEXT` — plus a `STATUS / REASON / ATTEMPTED / RECOMMENDATION` shape at
escalation points. This gives a human, or the unattended `ar-loop.sh` driver, a
grep-able outcome for each run without parsing the whole reply; it is additive
and never replaces `ar.jsonl` state or the skill's own output. `/ar:status` is
read-only and exempt. Shared contract: bundled `references/completion-status.md`.

Initial release. A skill-only autonomous experiment loop: propose one change,
measure it, keep it only if it beats the noise floor, repeat.

### Five skills

`/ar:start` opens a run (dedicated branch, `./.ar/` scaffold, baseline noise
floor), `/ar:resume` advances it, `/ar:status` reports read-only, `/ar:report`
writes the summary, `/ar:stop` ends it. One loop plus a small control surface —
no verb sprawl.

### Statistical gating

A change is kept only when its improvement exceeds the measured noise floor.
Baseline and floor are fixed once per segment from `baselineRepeats` repeats of
the unmodified harness. Confidence (`improvement / noiseFloor`) is recorded and
surfaced but never auto-acts beyond the keep threshold. Candidates in the
1.0×–2.0× band are re-run across seeds and compared on means before a verdict.

### Locked harness

`benchmark.sh`, `checks.sh`, `evaluator.py` and the metric-emitting code are
off-limits for the whole run, enforced by rejecting any diff that touches them.
An agent free to redefine the number it is optimising will eventually improve
the number by weakening the measurement. A harness change ends the segment and
forces a fresh baseline, because metrics either side of it are not comparable.

### Branch interlock

Nothing acts on a branch it did not create. `/ar:start` opens `ar/<slug>-<date>`,
carries the incoming working tree across — uncommitted and untracked files
included — and commits it immediately as the revert floor, so the loop's
`git checkout -- . && git clean -fd` can never reach pre-existing work. Reverts
deliberately omit `-x`: `./.ar/` is gitignored, and that is what keeps `clean`
from deleting the run's own state.

### No hooks, no MCP

No hooks, no MCP servers, no settings patching, no daemon. Loop
continuity comes from state on disk being re-read as the first action of every
invocation, which also makes the loop survive compaction and session resets.
Unattended overnight runs use `templates/ar-loop.sh`, an ordinary process run by
hand rather than a registered hook.

### State boundary

Every artefact lives in the target repo's `./.ar/`. Nothing is written outside
it, and no shared or global store is touched — installing `ar` cannot change what
any other plugin sees.
