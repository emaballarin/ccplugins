---
name: spinup
description: Read project memory and produce a tight "where we are + next action" brief, then wait for direction. Invoke ONLY when the user explicitly asks to get oriented on prior project work (spin up, catch up, get up to speed, where were we) — not to continue an autoresearch loop, which is /ar:resume. Do NOT auto-fire on general project questions, code edits, or unrelated asks. Works on any project primed with /mf:prime; reads from the Claude Code auto-memory dir under ~/.claude/projects/<slug>/memory/.
allowed-tools: [Read, Glob, Grep, Bash]
---

# /mf:spinup — project memory → session prime

Get up to speed on a project without starting any new work. Read persistent memory in priority order, summarise, then **stop** and wait for user direction.

## Important

1. **Spinup is read-only.** Never start work unprompted. Even if the memory says "the next thing to do is X", your job is to _report_ that — not to start doing X.
2. **Read selectively.** Let `MEMORY.md`'s descriptions decide which files bear on the current question; read those and skip the rest.
3. **Verify what you're about to cite.** Memory is a point-in-time snapshot; file paths, commits, and symbols may be stale.
4. **Don't re-derive settled decisions.** If a feedback memory says "closed as failed", don't re-propose it.

## Instructions

### Step 1: Open `MEMORY.md` directly

Auto-memory lives in the directory Claude Code names in its system prompt; use that path. Without one, derive it as `/mf:dump` Step 1 does: `~/.claude/projects/<slug>/memory/`, where `<slug>` is the repository root (`$PWD` outside git) with every non-alphanumeric character replaced by `-`. On the happy path, go straight to `Read ~/.claude/projects/<slug>/memory/MEMORY.md`. If that read succeeds, you've simultaneously located the dir and loaded the index — skip the rest of this step.

Only fall back to diagnostics if the read fails:

- **ENOENT on `MEMORY.md`** but the memory dir itself exists → treat as "primed but no memory yet" (step 2 behaviour).
- **ENOENT on the memory dir** → the slug convention may differ on this host. Run `ls ~/.claude/projects/ | grep <project_name_fragment>` to find the actual dir; if multiple matches exist, prefer the one with the most recent `MEMORY.md`.

### Step 2: Verify the project is primed

Memory-dir existence under `~/.claude/projects/<slug>/memory/` is the authoritative "has this session been worked on before" signal. `AGENTS.md` and `PROJECT.md` in the project root are the secondary "is this project wired up for mindfunnel" signal.

Confirm `AGENTS.md` and `PROJECT.md` exist in the project root (a regular file or a symlink both count). If either is missing:

- **Flag it** and suggest running `/mf:prime` from the project root.
- **Do not run `/mf:prime` silently** — pre-existing files with the same name matter.

If the memory dir doesn't exist, is empty, or only contains `MEMORY.md` with no referenced files, **say so and stop**. The project is either fresh or the memory was wiped. Invite the user to describe the task — don't fabricate context.

### Step 3: Read in priority order, stop early

Read these files in order. **Stop** once you have enough signal to act on the user's current question (or the next action implied by the memory).

1. **`MEMORY.md`** — always first. The index tells you what's available and how each file is described. Read every line.
2. **`project_state.md`** (or equivalently-named "current state" file — check `MEMORY.md`'s descriptions) — almost always second. The canonical "where we are + pending actions" file in the standard auto-memory layout.
3. **`user_*.md`** — short, high-value for tone calibration on the first message of a new session. Read if present, skip silently if not.
4. **Most recent `results_*.md`** — only if `project_state.md` points at it or the user's question is about results.
5. **`feedback_*.md`** — selectively. Read only the ones whose descriptions indicate load-bearing relevance to the immediate task. Skim-reading all of them is expensive and rarely helpful.
6. **`reference_*.md`** — only if the user or project state mentions an external system (issue tracker, experiment tracker, cloud resource).

If the index doesn't make clear what bears on the question, summarise what you have and ask the user where to focus.

### Step 3b: Replay and staleness-check the ledger

If `ledger.jsonl` exists in the memory dir, replay it for trust-ranked, provenance-checked assertions. Schema and full semantics: `${CLAUDE_PLUGIN_ROOT}/references/ledger.md`.

1. Read the lines, then compute the **current view**: drop any entry whose `id` is named in a later entry's `supersedes`, and within each `key` keep only the newest `ts`.
2. **Rank by trust** — `guaranteed` > `observed` > `given` > `user-inferred` > `agent-inferred`. Treat `opinion` entries as preferences, not facts. A low-trust (`agent-inferred`) claim is a hypothesis to re-check, not a settled fact — say so if you cite it.
3. **Staleness-check `sources`** — for a `path@<sha>`, run `git diff --quiet <sha> -- <path>` (non-zero exit: the file changed since `<sha>`, committed or not); if it changed, the entry is **possibly-stale**. For a plain `path` that no longer exists, the entry is **orphaned**. Do **not** cite a stale or orphaned entry as current — flag it for re-verification in the brief.

Budget this like any other read: skip entirely if the ledger is absent or empty; otherwise skim to the entries relevant to the user's question.

### Step 3c: Note parked scratchpads

If `<project root>/.mf/park/*/MANIFEST.md` exists, `/mf:park` saved scratchpads that are still parked: never restored, or restored with `--keep`. List each (session id, parked date, file count) under **Pending / next action**, with `/mf:unpark` as the way back. Report only: restoring is unpark's job.

### Step 4: Verify claims you're about to cite

For each specific claim you plan to put in the summary:

| Claim type                             | Verification                                               |
| -------------------------------------- | ---------------------------------------------------------- |
| File path                              | `ls` or `Read` to confirm it exists                        |
| Function / symbol / flag name          | `grep` for it                                              |
| Git / branch / commit state            | `git status`, `git log -1`, `git branch --show-current`    |
| Remote-host run results                | **Do not verify.** Flag as "according to memory"           |
| User preferences / collaboration style | Trust (not time-sensitive)                                 |
| Closed-hypothesis histories            | Trust (not time-sensitive)                                 |
| Ledger claim with a `path@sha` source  | Re-check the source; stale/orphaned → don't cite (Step 3b) |

If verification fails, **don't cite the claim**. Flag the drift in the brief with the proposed correction; it is applied on the user's go-ahead or by the next `/mf:dump`.

### Step 5: Produce the brief

Emit a tight summary in this shape. Adapt section headings to the project's reality — omit sections with no content rather than padding:

```markdown
## Where we are

<1–3 sentences: current state, most recent decision, what just happened.>

## Pending / next action

<The one concrete next step: a command to run, a decision to make, or an
experiment waiting for a result. If more than one, list them and flag
which is primary.>

## Open threads

- <thread 1, one line>
- <thread 2, one line>

## Load-bearing reminders

- <feedback memory directly relevant to the current task, one line>
- <a possibly-stale or low-trust ledger claim needing re-verification, if any>
```

### Step 6: Stop

Stop after the brief and wait for direction. The memory's "next action" is something to report, not to start; new experiments and analysis come after the user responds.

## Examples

### Example 1: Normal resumption mid-project

**User says:** "Spin up."

**Actions:**

1. Read `MEMORY.md` directly at the conventional path. It exists — no dir-probing needed.
2. Read `project_state.md` — finds current-state + pending action.
3. Read the `user_*.md` files — short, read them.
4. Skim `MEMORY.md` descriptions for feedback entries that look relevant to the pending action; read the one that matches.
5. Quick verification: `git status` to confirm the branch and working-tree state match what memory says.
6. Emit the brief. Stop.

**Result:** a short summary, one concrete next action, user responds with "OK, go" or a redirect.

### Example 2: Fresh project with no memory yet

**User says:** "Catch up."

**Actions:**

1. Memory dir doesn't exist yet, or is empty except for a placeholder.
2. Report: "This project has no stored memory. The conventional priming files (AGENTS.md, PROJECT.md) **are/are not** present. Describe the task you want help with and I'll start fresh."
3. Stop. Do not infer context from the file tree.

### Example 3: Spin up for a specific topic, not everything

**User says:** "Spin up — I want to work on the data pipeline."

**Actions:**

1. Read `MEMORY.md`, `project_state.md`.
2. Use `MEMORY.md` descriptions to find memory files relevant to "data pipeline" specifically. Read those.
3. Skip unrelated feedback files and results dossiers.
4. Emit a brief scoped to the pipeline context.
5. Stop.

## Troubleshooting

### Error: Memory directory path is empty or wrong

**Symptom:** The computed path under `~/.claude/projects/` has no files, but the project has been worked on before.

**Cause:** An `autoMemoryDirectory` setting or `CLAUDE_CODE_PROJECT_DIR_NAME` moved the directory, or the project was worked on from outside its repository.

**Solution:** Run `ls ~/.claude/projects/ | grep <project_name_fragment>` to find the actual dir. If multiple matches exist (e.g. a project outside git opened from both `/work/foo` and `/work/foo/src`), prefer the one with the most recent `MEMORY.md`.

### Error: Memory files cite a file path that no longer exists

**Symptom:** `project_state.md` says "see `src/old_module.py`" but the file isn't there.

**Cause:** Code moved / was renamed / was deleted since the memory was written.

**Solution:** Don't cite the dead reference. Find the likely replacement with `grep` and flag the drift in the brief with the proposed correction, or ask the user to clarify. Don't guess.

### Error: Citing a stale `feedback_*.md` entry

**Symptom:** You quote a feedback memory that is several sessions old and no longer reflects the user's current stance.

**Cause:** Treating memory as ground truth without verification.

**Solution:** When citing feedback, preface with "according to memory: ..." and invite correction if the user's stance has shifted. The user's live feedback always overrides stored memory.

## Anti-patterns

- **Don't re-derive settled decisions.** Closed hypotheses stay closed unless the user reopens them.
- **Don't quote verbatim.** Summarise; the brief is for signal extraction.
- **Don't verify claims you don't need** — only check assertions you're about to commit to.
- **Don't report on things you didn't read.** The brief reflects only files you actually opened.
- **Don't project confidence where memory is stale.** Phrase uncertain claims as "according to memory" and invite correction.
- **Don't over-format the brief.** Markdown tables are for results. Prose bullets fit spinup summaries.
