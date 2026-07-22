# The ledger — `ledger.jsonl`

An append-only, machine-queryable record of atomic **claims**, **decisions**, and
**learnings**, each carrying its epistemic **trust** and its **provenance**. It
lives beside the narrative Markdown memory and serves a different purpose:

- **Markdown** (`MEMORY.md` + `*_*.md`) = the human-facing "where we are" narrative,
  updated in place. `/mf:spinup` reads it for the brief.
- **`ledger.jsonl`** = atomic assertions with trust + provenance, never rewritten.
  `/mf:dump` appends; `/mf:spinup` replays and staleness-checks it.

The ledger does **not** replace narrative memory. Do not move prose state into it,
and do not duplicate a ledger claim as a Markdown paragraph — cross-reference instead.

## Location

```
~/.claude/projects/<slug>/memory/ledger.jsonl
```

Same `<slug>` and memory dir as the Markdown files (`$PWD` with every `/` → `-`).
One JSON object per line. Create the file on first append if absent.

## Entry schema

```json
{
    "id": "<short-unique>",
    "ts": "<ISO-8601 UTC>",
    "kind": "claim|decision|learning",
    "status": "guaranteed|observed|given|user-inferred|agent-inferred|opinion",
    "text": "<the claim / decision / learning, one sentence>",
    "sources": ["<path>", "<path@sha>", "<run-id>", "<https://…>"],
    "supersedes": "<id of the entry this replaces, optional>",
    "key": "<optional grouping key for latest-wins replay>"
}
```

- **`id`** — short and unique within the file. A timestamp-derived slug is fine
  (e.g. `20260723-<n>`); it only has to be unique so `supersedes` can name it.
- **`kind`** — `claim` (a fact about the world/system), `decision` (a settled
  choice, with the `text` naming choice + why), `learning` (a durable pitfall,
  pattern, or gotcha worth surfacing next time).
- **`status`** — the trust ladder below. Required on every entry.
- **`text`** — one sentence. Keep the number/decision/rule concrete.
- **`sources`** — provenance: the paths, commit-pinned paths (`src/x.py@<sha>`),
  experiment run-ids, or URLs the entry is grounded in. Omit or `[]` when there is
  genuinely no artifact (e.g. a bare user preference).
- **`supersedes`** — set when this entry replaces an earlier one (a corrected
  number, a reversed decision). Supersession is a _field_, not a command: replay
  drops the named entry. No separate decision log, no rewrite of the old line.
- **`key`** — optional. Entries that share a `key` are collapsed to the newest on
  replay. Use it for a value that evolves (`eval-accuracy`, `chosen-db`); omit it
  for one-off facts.

## Trust ladder (`status`)

Decreasing order of trust. `opinion` is orthogonal — it is not truth-apt.

| `status`         | Use when the entry is…                                                                  |
| ---------------- | --------------------------------------------------------------------------------------- |
| `guaranteed`     | theoretically guaranteed — a proof, a spec/requirement mandate, a mathematical identity |
| `observed`       | experimentally observed — measured, benchmarked, reproduced from a run                  |
| `given`          | stated by the user as a given fact                                                      |
| `user-inferred`  | the user's own deduction (reasoned, not directly observed)                              |
| `agent-inferred` | the agent's deduction                                                                   |
| `opinion`        | a preference or taste call, carrying no truth claim ("prefers dark mode")               |

Pick the **highest** rung the evidence actually supports; do not inflate. An
`agent-inferred` claim dressed as `observed` is the failure this field exists to
prevent. When two entries conflict, the higher rung (or, at equal rung, the newer
`ts`) wins.

## Replay (current view)

To get the current state from the log: read all lines, then

1. drop any entry whose `id` appears in a later entry's `supersedes`;
2. within each `key`, keep only the newest `ts`;
3. rank what remains by trust (`guaranteed` → `agent-inferred`); `opinion` entries
   are listed separately as preferences, not ranked as facts.

## Staleness / orphan checks

For each surviving entry, check its `sources`:

- a `path@<sha>` whose current file content no longer matches `<sha>` (the file
  changed since the claim) → flag the entry **possibly-stale**;
- a `path` that no longer exists → flag the entry **orphaned**.

A stale or orphaned entry is **not** cited as current fact. Surface it as needing
re-verification, or (if the drift is unambiguous) append a corrected entry that
`supersedes` it.
