# Changelog

All notable changes to the `mf` (mindfunnel) plugin are documented here.
This project adheres to [Semantic Versioning](https://semver.org/).

## 0.6.0 — 2026-07-27

Coordinated marketplace version bump, alongside a repository-wide formatter pass
and the addition of the `parml` (paretoml) plugin. The formatter normalised the
newly added files only — this plugin's were already conformant from the `e8fd3cd`
pass and are byte-unchanged. No skill logic changed.

## 0.5.0 — 2026-07-27

Coordinated marketplace version bump, alongside the `ccsci` 0.4.0 kernel-syntax
fix. No skill logic changed.

## 0.4.2 — 2026-07-23

### AGENTS.md — two universal guidelines

Two more agent-neutral rules carried by `templates/AGENTS.md`: **dose-response is
a result** (judge a mechanism by direction and dose-response, not distance to
target; a sweep that stopped at its largest value is _under-tested_, not
_failed_; "best so far, still unsatisfactory" is a valid verdict) and **never
route around a human-required control** (don't disable, flag-skip, or work around
a signature / auth / review gate / confirmation — a bypassed control is
indistinguishable from a properly attested one). No skill logic changed.

## 0.4.1 — 2026-07-23

### AGENTS.md template sync + universal guidance

Sync the shipped `templates/AGENTS.md` with the current user-global baseline, and
carry two universal, agent-neutral guidelines in it: a **decision-brief** rule
(lead with a recommendation and reason, an honest upside _and_ downside per
option, never silently drop or merge one) and a **completion-status** rule
(`DONE` / `DONE_WITH_CONCERNS` / `BLOCKED` / `NEEDS_CONTEXT`, with a
`STATUS / REASON / ATTEMPTED / RECOMMENDATION` escalation shape). No skill logic
changed.

## 0.4.0 — 2026-07-23

### New — the provenance-and-trust ledger

Memory gains a second layer alongside the narrative Markdown: an append-only
`ledger.jsonl` in the auto-memory dir, holding atomic claims / decisions /
learnings. Each entry carries an **epistemic trust** level — `guaranteed` >
`observed` > `given` > `user-inferred` > `agent-inferred`, plus a non-truth-apt
`opinion` — and its **provenance** in a `sources` array (paths, commit-pinned
`path@sha`, run-ids, URLs). Supersession is a field (`supersedes`), not a
separate log: revisions append, and replay takes latest-wins per `key`.

- `/mf:dump` — new **Step 5b** appends ledger-worthy assertions (honest trust
  rung, real provenance, append-only). Prose state stays in Markdown; no
  double-logging.
- `/mf:spinup` — new **Step 3b** replays the ledger (drop superseded, newest per
  `key`), ranks by trust, and staleness-checks `sources` (`path@sha` changed →
  possibly-stale; missing `path` → orphaned), refusing to cite stale entries as
  current fact.
- Schema, trust ladder, and replay/staleness semantics: bundled
  `references/ledger.md` (single source of truth for both skills).

## 0.3.2 — 2026-07-09

Content patch to `templates/AGENTS.md`. No skill logic changed.

### New guidance — to-do lists for multi-step work

`## Planning & execution` gains a third bullet: any request that
decomposes into a list of tasks, or that is complex enough to carry
intermediate state, is tracked in the agent's native to-do / task-list
mechanism, created up front and kept current as work proceeds. Only
genuinely one-off, single-action tasks are exempt; harnesses exposing
no such tool fall back to an explicit checklist in the reply.

The bullet deliberately names no concrete tool. `AGENTS.md` is
agent-neutral, and harness tool names churn across releases. It also
states outright that a to-do list is in-session working state rather
than persisted memory, so it cannot be misread as contradicting
`/mf:dump`'s standing "don't create TODO lists in memory" anti-pattern.

### Template drift repaired

Two bullets present in a live `~/.mindfunnel/AGENTS.md` had never been
reflected back into the template, so a fresh `/mf:setup` seeded an
incomplete file. Both now ship in `templates/AGENTS.md`:

- **Small-sample signals are hypotheses, not results.**
  (`## Communication style`) — a trend across a handful of seeds or runs
  can reverse at the planned scale. Flag such signals as provisional and
  confirm at full sample size before reframing the narrative.
- **Specs are authoritative — never silently reconcile a spec-vs-reality
  mismatch.** (`## Autonomy and asking`) — when an authoritative source
  conflicts with what is observed, surface the conflict and ask. Do not
  amend the source to fit the observations, and do not quietly adapt the
  work to whatever happens to be there.

### No automatic migration

`/mf:setup` seeds with `cp -n` and never overwrites an existing
`~/.mindfunnel/AGENTS.md`. Machines bootstrapped under any earlier
release keep their current file untouched; merge the three bullets by
hand to pick them up. Fresh machines get them from the template.

## 0.3.1 — 2026-07-07

Formatting-only patch: normalised an emphasis delimiter in
`templates/SOUL.md`. No behavioural change.

## 0.3.0 — 2026-04-24

Major structural refactor: cleanly split user-global content from
project-scoped content. Contributors cloning a primed repo now see
`AGENTS.md`, `CLAUDE.md`, and `PROJECT.md` as committed source files —
no more gitignored symlinks into a per-machine path.

### New scaffolding file: `USER.md`

Captures per-machine, per-user preferences (shell, Python defaults,
formatter paths, multi-agent hook bridges) that used to be mixed into
`AGENTS.md`. Lives user-global at `~/.mindfunnel/USER.md`, reachable
via `~/.claude/USER.md` and `~/.codex/USER.md` symlinks. Never stamped
into a project.

### `SOUL.md` is now user-global only

No longer stamped into project roots. Lives at `~/.mindfunnel/SOUL.md`
with `~/.claude/SOUL.md` + `~/.codex/SOUL.md` symlinks. Same treatment
as the new `USER.md`: shapes every session on every project, but never
leaves the maintainer's machine.

### `AGENTS.md` split — user-global engineering style vs. committed project stub

- `~/.mindfunnel/AGENTS.md` (user-global): the maintainer's
  project-agnostic engineering style. Loaded via `~/.claude/CLAUDE.md`
  and `~/.codex/instructions.md` on every machine. Never stamped into
  a project.
- `./AGENTS.md` (per project): a small, committed, project-scoped stub
  from the new `templates/project-AGENTS.md`. Points at `PROJECT.md`
  for deep context, mentions `/mf:spinup` + `/mf:dump` for
  discoverability. Real file, owned by the project, extended per-project
  as it grows.
- `./CLAUDE.md` (per project): intra-repo symlink to `./AGENTS.md`,
  committed. Explicit Claude Code compatibility; no more symlinking
  into `~/.mindfunnel/`. Intra-repo symlinks track cleanly in git on
  POSIX.

### `/mf:setup`

Seeds `~/.mindfunnel/USER.md` from a bundled template (non-destructive,
same contract as `SOUL.md`) and creates `~/.claude/{SOUL,USER}.md` +
`~/.codex/{SOUL,USER}.md` symlinks idempotently. Skips an agent dotdir
that doesn't exist (Claude-only or Codex-only machines). Never clobbers
a real file in any target.

### `/mf:prime` rewritten

Stamps the project-scoped `AGENTS.md` stub (if absent), creates the
intra-repo `CLAUDE.md` symlink, touches an empty `PROJECT.md`, cleans
up legacy pre-0.3.0 symlinks (`./AGENTS.md`, `./CLAUDE.md`, `./SOUL.md`
pointing into `~/.mindfunnel/`), and strips stale `AGENTS.md` /
`CLAUDE.md` entries from `.gitignore` so the new committed files
actually stage. Hand-authored regular files at those paths are never
overwritten.

### `/mf:spinup` + `/mf:dump`

Priming-detection simplified: the "is this project primed?" check now
looks for `AGENTS.md` + `PROJECT.md` (instead of the old `CLAUDE.md` /
`SOUL.md` / `PROJECT.md` triple). Memory-dir existence under
`~/.claude/projects/<slug>/memory/` remains the authoritative "has this
session been worked on" signal; the two files are the secondary "wired
up for mindfunnel" signal.

`/mf:dump`'s "rare propose user-global edit" step now distinguishes the
user-global `~/.mindfunnel/AGENTS.md` from the per-project `./AGENTS.md`
explicitly, and covers all three user-global files (`SOUL.md`,
`AGENTS.md`, `USER.md`) as candidate targets. Writes go directly to
`~/.mindfunnel/`, never to the symlink aliases.

### Template refreshes

- `templates/AGENTS.md` (user-global): agent-neutral title, new
  Planning & Execution section (plan-first + pre-mortem bullet),
  strengthened code-hygiene guidance for multi-file refactors and
  sub-agent delegations, memory-system section framed conditionally
  so the file reads cleanly on a machine without `mindfunnel`,
  explicit `~/.mindfunnel/` paths for `SOUL.md` and `USER.md`
  references, opening paragraph reflects the user-global-only role.
- `templates/project-AGENTS.md` (new): the per-project stub.
- `templates/SOUL.md`: Locale & conventions section (language / date /
  time), interruption-cue example, "where do heavy commands belong"
  prompt in the Technical environment section, header docstring
  updated for user-global placement.
- `templates/USER.md` (new): skeleton with Memory-system /
  Shell / Python / Codex-compat sections for the maintainer to
  fill in.
- `templates/PROJECT.md`: three new commented-out sections (How to
  run / test / lint, Known pitfalls, What not to touch), External
  systems reordered before Glossary.

### Breaking change — automatically handled on re-prime

Every project primed under any 0.2.x release has `./CLAUDE.md`,
`./AGENTS.md`, `./SOUL.md` as symlinks into `~/.mindfunnel/`, plus the
corresponding `.gitignore` entries. Re-running `/mf:prime` in each
project migrates them:

- `./AGENTS.md` legacy symlink → replaced with the project stub (real file).
- `./CLAUDE.md` legacy symlink → repointed to local `./AGENTS.md`.
- `./SOUL.md` legacy symlink → removed (`SOUL.md` is user-global only now).
- `.gitignore` — `AGENTS.md` and `CLAUDE.md` lines stripped (the new
  committed files would otherwise fail to stage).
- `.gitignore` `SOUL.md` line → left in place (harmless; touching a
  tracked file unprompted is out of scope).

For repos primed under ≤ 0.2.1 (which committed `CLAUDE.md` /
`AGENTS.md` as symlinks because the `.gitignore` coverage was
incomplete at the time), run `git rm --cached CLAUDE.md AGENTS.md`
first to untrack the broken symlinks, then `/mf:prime` to stamp the
real files. See `/mf:prime`'s Troubleshooting section for the full
migration incantation.

## 0.2.2

- `/mf:prime` now adds `SOUL.md`, `CLAUDE.md`, **and** `AGENTS.md` to `.gitignore`. Previously only `SOUL.md` was excluded, which let `CLAUDE.md` and `AGENTS.md` get committed as symlinks pointing into `~/.mindfunnel/` — a per-user, per-machine path that doesn't exist for anyone else's clone. `PROJECT.md` stays committed as before; it's the only real, project-owned file of the four.
- **User migration required** for projects primed with 0.2.0 or 0.2.1. Existing primed repos already have `CLAUDE.md` and `AGENTS.md` tracked. After upgrading, in each such repo:

    ```fish
    # top up .gitignore (or just re-run /mf:prime, which does this now):
    printf 'CLAUDE.md\nAGENTS.md\n' >> .gitignore

    # untrack the committed symlinks without deleting them on disk:
    git rm --cached CLAUDE.md AGENTS.md

    git commit -m "mindfunnel: untrack per-machine symlinks"
    ```

    `git rm --cached` is deliberately NOT automated by `/mf:prime` — untracking already-committed files is a destructive operation on shared history and wants explicit user intent. Re-running `/mf:prime` on a <= 0.2.1 repo is safe: it will top up `.gitignore` with the missing entries, but won't touch the index.

## 0.2.1

- `/mf:dump` and `/mf:spinup` are now model-invocable. `/mf:dump` can fire autonomously at natural checkpoints or approaching context saturation; `/mf:spinup` has a narrow trigger (explicit resume / catch-up / "where were we" phrasing only) to avoid bloating trivial asks with a brief. `/mf:setup` and `/mf:prime` remain user-only — both have side effects that want deliberate invocation.
- `/mf:spinup` step 1 no longer shells out to compute the memory-dir slug. The path is deterministic, so the skill now reads `MEMORY.md` directly at the conventional location and only falls back to dir-probing on ENOENT.

## 0.2.0

- `/mf:prime` no longer touches `~/.claude/`. Removed the legacy global `~/.claude/SOUL.md` convenience symlink; the skill's scope is now strictly the current project root and `~/.mindfunnel/`.

## 0.1.0 — initial release

- `/mf:setup` — one-time bootstrap of `~/.mindfunnel/` from bundled templates.
- `/mf:prime` — prime the current project with symlinks to `~/.mindfunnel/` and a project-local `PROJECT.md`.
- `/mf:dump` — consolidate the current session's non-derivable state into Claude Code's auto-memory dir.
- `/mf:spinup` — read the auto-memory at the start of a new session and emit a tight "where we are + next action" brief.
