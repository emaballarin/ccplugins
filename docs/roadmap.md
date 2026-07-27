# Plan — gstack-inspired improvements to ccplugins

## Context

A survey of [`garrytan/gstack`](https://github.com/garrytan/gstack) (MIT) for
ideas portable into this marketplace turned up two worth building and one worth
adopting narrowly. Everything here is **skill-only / tooling-only** — no hooks,
no remote telemetry, no vendored runtime, no auto-running background processes.

**Status — 2026-07-23: all in-scope work landed.** W1 (Tier-1 validation + CI),
W2 (provenance/trust ledger, `mf` 0.4.1), and W3 (completion-status protocol,
`ar` 0.2.1) are committed and pushed; A2 + A3 were additionally generalized as
universal, agent-neutral guidance in the `mindfunnel` AGENTS.md template. The
Deferred / Parked / Dropped items below are unchanged.

Two committed workstreams, built in parallel:

1. **Tier-1 static validation + CI** — a fast, free safety net the marketplace
   currently lacks entirely. Catches frontmatter drift, version/CHANGELOG skew,
   README↔disk mismatch, dangling file references, and (the one live risk today)
   `ccsci` kernel↔SKILL.md contract drift.
2. **A provenance-and-trust ledger for mindfunnel** — an append-only JSONL record
   of atomic claims/decisions/learnings, each carrying an ordered _trust_ status
   and its _provenance_ (files, SHAs, run-ids, URLs). Upgrades the memory model
   from "narrative Markdown only" to "narrative Markdown + queryable, historied,
   staleness-checkable ledger."

Plus a scoped adoption (completion-status protocol) and two parked items.

## Scope

| Status                | Item                                                                                                                                                                         |
| --------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **DONE** (2026-07-23) | W1 Tier-1 validation + CI · W2 ledger (`mf` 0.4.1) · W3 completion-status (`ar` 0.2.1) · A2+A3 generalized as universal `mindfunnel` AGENTS.md guidance                      |
| **DEFERRED**          | SKILL.md generation from `.tmpl` — build only if ≥3 skills carry the same block verbatim _and_ it changes more than once                                                     |
| **PARKED**            | Full AskUserQuestion decision-brief ceremony (compressed form adopted universally; full rides on generation) · Codex second-opinion skill (`codex exec` verified — see note) |
| **DROPPED**           | Importing gstack skills (investigate / health / office-hours / retro / cso / …) — no demonstrated need; would inflate surface                                                |

---

## Workstream 1 — Tier-1 static validation + CI

Fast (<5s), free, gates every commit. Python + `pytest` (repo already uses Python
tooling — `.ruff_cache`, `ccsci` kernels). A single `tests/` suite plus one GitHub
Actions workflow.

### Assertions

- **Frontmatter** — every `plugins/*/skills/*/SKILL.md` (and `agents/*.md`) parses
  as YAML frontmatter; `name` matches its directory; `description` non-empty;
  `allowed-tools` (if present) is a well-formed list of known tool names.
- **Version ↔ CHANGELOG** — each `plugins/*/.claude-plugin/plugin.json` `version`
  equals the newest version heading in that plugin's `CHANGELOG.md`.
- **Marketplace integrity** — every entry in `.claude-plugin/marketplace.json`
  resolves to a real `source` dir containing a real `plugin.json` whose `name`
  matches the marketplace entry's `name`.
- **README ↔ disk** — every skill named in a plugin's `README.md` table exists on
  disk; every on-disk skill is documented (no orphans, no undocumented skills).
- **Referenced-path existence** — every `templates/…`, `references/…`, `kernel.py`,
  or other repo-relative path _mentioned inside_ a SKILL.md exists on disk.
- **ccsci kernel contract** — for each skill with a `kernel.py`:
    - it compiles (`ast.parse`, or import under a guarded namespace);
    - every public entrypoint the SKILL.md advertises is actually defined. Start
      pragmatic: extract the advertised names (e.g. figure-composer promises
      `panel_task`, `compose_figure`, `compose_crops`, `composite_review_task`,
      `derive_outline_task`) and assert each has a matching `def`/assignment. Keep
      it a maintained check, not a magic parser.

### Files

- `tests/` at repo root — one module per assertion group
  (`test_frontmatter.py`, `test_versions.py`, `test_marketplace.py`,
  `test_readme_sync.py`, `test_referenced_paths.py`, `test_kernels.py`).
- Optional shared helpers in `tests/_util.py` (frontmatter parse, plugin discovery).
- `.github/workflows/validate.yml` — run `pytest` on push / PR.
- Dev dep: `pyyaml` (+ `pytest`). Note in the relevant README / dev docs.

### Explicitly out of scope

LLM-as-judge scoring (gstack Tier 3) and any E2E `claude -p` runner. Tier 1 only.

---

## Workstream 2 — provenance-and-trust ledger (mindfunnel)

One new artifact per project: **`~/.claude/projects/<slug>/memory/ledger.jsonl`**
— append-only, one JSON object per line. It sits _alongside_ the existing Markdown
memory, with a clean division of labour:

- **Markdown** (`MEMORY.md` + `*_*.md`) = narrative "where we are," human-facing,
  updated in place — what `/mf:spinup` reads for its brief.
- **`ledger.jsonl`** = atomic claims / decisions / learnings with trust + provenance
  — machine-queryable, historied, never rewritten.

### Entry schema

```json
{
    "id": "<short-unique>",
    "ts": "2026-07-23T12:00:00Z",
    "kind": "claim|decision|learning",
    "status": "guaranteed|observed|given|user-inferred|agent-inferred|opinion",
    "text": "<the claim/decision/learning>",
    "sources": ["path", "path@<sha>", "run-id", "https://…"],
    "supersedes": "<id?>",
    "key": "<optional grouping key>"
}
```

### Trust ladder (`status`, decreasing trust; `opinion` is orthogonal)

| `status`         | meaning                                               | trust   |
| ---------------- | ----------------------------------------------------- | ------- |
| `guaranteed`     | theoretically guaranteed (proof / spec-mandated)      | highest |
| `observed`       | experimentally observed / measured / reproduced       | ↓       |
| `given`          | user stated as given                                  | ↓       |
| `user-inferred`  | user's own deduction                                  | ↓       |
| `agent-inferred` | agent's deduction                                     | lowest  |
| `opinion`        | preference/taste — **not truth-apt** ("I like pizza") | n/a     |

Deliberately _not_ gstack's `confidence: 1-10` + separate `source` enum — this one
ordered field plus the opinion escape carries the same signal with less ceremony.

### Design decisions (resolving the open questions)

- **Append-only JSONL.** No read-modify-write → concurrent worktrees/sessions can't
  clobber; full history preserved (a belief's evolution is visible); the "current
  view" is a replay taking latest-wins per `key`. Right substrate for a provenance
  ledger; does **not** replace narrative Markdown.
- **Supersession is a field, not a subsystem.** No `--supersede` CLI verb, no
  separate decision log. Decisions are just `kind:"decision"` entries; "belief B
  replaced belief A" is an optional `supersedes:"<id>"` on a normal append. Replay
  drops the superseded entry.
- **Provenance = the `sources` array.** Each assertion records the paths / commit
  SHAs / run-ids / URLs it's grounded in. This _is_ the "files ledger for provenance
  of experimental information."

### Skill changes

- **`/mf:dump`** — after writing narrative Markdown, append ledger entries for
  non-derivable claims/decisions/learnings surfaced this session, each with a
  `status` from the trust ladder and `sources` provenance. Reuse the existing
  slug/memory-dir resolution. Keep the empty-dump guard (no signal → no append).
- **`/mf:spinup`** — after the narrative read, do a cheap ledger pass: replay
  latest-wins, rank what to trust by `status`, and **staleness-check** `sources` —
  if a referenced file changed since its pinned SHA, flag the claim "possibly
  stale"; if a referenced path is gone, flag "orphaned." Surface stale/orphaned
  claims in the brief instead of citing them as current.
- Documentation: update `plugins/mindfunnel/README.md` + `CHANGELOG.md`; bump
  `plugin.json` version (W1's version↔CHANGELOG check will enforce the pairing).

---

## Workstream 3 — completion-status protocol (scoped)

A terminal status line on **action/loop** skills only (`ar:*`, any future debugging
skill). Read-only skills (`mf:spinup`) are exempt — they already end by stopping.

```
DONE                — finished, with evidence (tests pass / output shown)
DONE_WITH_CONCERNS  — finished, caveats listed
BLOCKED             — can't proceed: blocker + what was tried
NEEDS_CONTEXT       — missing info: state exactly what

# at an escalation point (e.g. after N failed attempts):
STATUS / REASON / ATTEMPTED / RECOMMENDATION
```

Buys: (1) a grep-able signal an autonomous loop (`ar:resume` / `ar:report`) can read
to decide continue/retry/stop; (2) forced honesty — DONE-with-evidence vs
DONE_WITH_CONCERNS made unavoidable; (3) kills the "this should work" ending. Pairs
with W2 — a `BLOCKED` + `ATTEMPTED` is a natural `kind:"learning"` ledger entry.

Implement as a short shared prose block added by hand to the qualifying skills. If
it ends up duplicated across ≥3 skills and churns, that triggers the deferred
generation work.

---

## Parked note — Codex second-opinion skill (feasible)

Verified: a skill can obtain a **non-interactive** Codex second opinion with no human
keystroke. Slash commands are user-input-layer only (not model-invocable), but the
`codex` CLI is installed (`~/.bun/bin/codex`) and its `codex exec` subcommand runs to
completion with no TUI:

```bash
codex exec -s read-only -C "$(pwd)" "<assembled context + question>"
```

The model invokes Bash → Bash runs `codex exec` → output returns to context. Trigger
would be an **explicit juncture** (model decides "this is hard," or a skill step like
"if N hypotheses fail → cold-read"), not a daemon watching the reasoning trace.
Fallback when the binary is absent: dispatch an independent Claude subagent via the
Agent tool. ~40 lines if built. Not designed further until requested.

---

## Verification

**W1** — run `pytest` locally; it passes on the clean tree. Then intentionally break
one of each: bump a `plugin.json` version out of sync with its CHANGELOG; rename a
skill dir without updating the README; reference a non-existent template path; delete
an advertised kernel entrypoint. Confirm each breakage fails a distinct test with a
clear message. Revert. Confirm the GitHub Action runs on a PR.

**W2** — in a throwaway primed project: run `/mf:dump`, inspect `ledger.jsonl` (well-
formed lines, correct `status`/`sources`). Run `/mf:spinup`, confirm it replays
latest-wins and ranks by trust. Add an entry with `sources:["some/file.py@<sha>"]`,
then modify that file; re-run `/mf:spinup` and confirm the claim is flagged
possibly-stale. Delete a referenced path; confirm "orphaned." Append a `supersedes`
entry; confirm the superseded claim drops from the current view.

**W3** — invoke a qualifying skill to each terminal state (force a `BLOCKED` by
withholding a prerequisite); confirm the terminal line renders in the documented
format and, where applicable, produces a matching ledger `learning`.

## Attribution

gstack is MIT (© 2026 Garry Tan). Any prose/behaviour adapted from it gets a credit
line in the relevant plugin's `NOTICE` (precedent: `plugins/autoresearch/NOTICE`).
No gstack code is copied — these are re-implementations of ideas.
