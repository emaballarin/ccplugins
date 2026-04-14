---
name: spinup
description: Read project memory at session start and produce a tight "where we are + next action" brief, then wait for direction. Use when the user says "spin up", "catch up", "resume", "where were we", "get up to speed", or at the beginning of a fresh session on a project that already has memory. Works on any project primed with /mf:prime; reads from the Claude Code auto-memory dir under ~/.claude/projects/<slug>/memory/.
disable-model-invocation: true
allowed-tools: [Read, Glob, Grep, Bash]
---

# /mf:spinup — project memory → session prime

Get up to speed on a project without starting any new work. Read persistent memory in priority order, summarise, then **stop** and wait for user direction.

## Important

1. **Spinup is read-only.** Never start work unprompted. Even if the memory says "the next thing to do is X", your job is to _report_ that — not to start doing X.
2. **Read selectively.** Budget 3–6 files for a typical spinup. Reading everything is expensive on context and rarely useful.
3. **Verify what you're about to cite.** Memory is a point-in-time snapshot; file paths, commits, and symbols may be stale.
4. **Don't re-derive settled decisions.** If a feedback memory says "closed as failed", don't re-propose it.

## Instructions

### Step 1: Locate the memory directory

Auto-memory lives at `~/.claude/projects/<slug>/memory/` where `<slug>` is `$PWD` with every `/` replaced by `-`.

```bash
bash -c 'echo ~/.claude/projects/$(echo "$PWD" | sed "s|/|-|g")/memory'
```

### Step 2: Verify the project is primed

Confirm `CLAUDE.md`, `SOUL.md`, `PROJECT.md` exist in the project root. If any are missing:

- **Flag it** and suggest running `/mf:prime` from the project root.
- **Do not run `/mf:prime` silently** — pre-existing files with the same name matter.

If the memory dir doesn't exist, is empty, or only contains `MEMORY.md` with no referenced files, **say so and stop**. The project is either fresh or the memory was wiped. Invite the user to describe the task — don't fabricate context.

### Step 3: Read in priority order, stop early

Read these files in order. **Stop** once you have enough signal to act on the user's current question (or the next action implied by the memory). Budget: 3–6 files typically.

1. **`MEMORY.md`** — always first. The index tells you what's available and how each file is described. Read every line.
2. **`project_state.md`** (or equivalently-named "current state" file — check `MEMORY.md`'s descriptions) — almost always second. The canonical "where we are + pending actions" file in the standard auto-memory layout.
3. **`user_prefs.md` + `collaboration_style.md`** — short, high-value for tone calibration on the first message of a new session. Read if present, skip silently if not.
4. **Most recent `results_*.md`** — only if `project_state.md` points at it or the user's question is about results.
5. **`feedback_*.md`** — selectively. Read only the ones whose descriptions indicate load-bearing relevance to the immediate task. Skim-reading all of them is expensive and rarely helpful.
6. **`reference_*.md`** — only if the user or project state mentions an external system (issue tracker, experiment tracker, cloud resource).

If you've read 6 files and still feel you need more, you're over-reading. Stop, summarise what you have, and ask the user where to focus.

### Step 4: Verify claims you're about to cite

For each specific claim you plan to put in the summary:

| Claim type                             | Verification                                            |
| -------------------------------------- | ------------------------------------------------------- |
| File path                              | `ls` or `Read` to confirm it exists                     |
| Function / symbol / flag name          | `grep` for it                                           |
| Git / branch / commit state            | `git status`, `git log -1`, `git branch --show-current` |
| Remote-host run results                | **Do not verify.** Flag as "according to memory"        |
| User preferences / collaboration style | Trust (not time-sensitive)                              |
| Closed-hypothesis histories            | Trust (not time-sensitive)                              |

If verification fails, **don't cite the claim**. If the correction is unambiguous (e.g. file renamed, commit rolled back), update the memory file to reflect current reality. Otherwise flag the drift and ask the user.

### Step 5: Produce the brief

Emit a tight summary, ≤ 20 lines, in this shape. Adapt section headings to the project's reality — omit sections with no content rather than padding:

```markdown
## Where we are

<1–3 sentences: current state, most recent decision, what just happened.>

## Pending / next action

<The one concrete next step: a command to run, a decision to make, or an
experiment waiting for a result. If more than one, list max 3 and flag
which is primary.>

## Open threads

- <thread 1, one line>
- <thread 2, one line>

## Load-bearing reminders

- <feedback memory directly relevant to the current task, one line>
```

### Step 6: Stop

Do **not** start work. Do **not** propose new experiments. Do **not** offer unsolicited analysis. Wait for the user to direct.

## Examples

### Example 1: Normal resumption mid-project

**User says:** "Spin up."

**Actions:**

1. Compute memory dir, confirm project priming, read `MEMORY.md`.
2. Read `project_state.md` — finds current-state + pending action.
3. Read `user_prefs.md` and `collaboration_style.md` — short, read both.
4. Skim `MEMORY.md` descriptions for feedback entries that look relevant to the pending action; read the one that matches.
5. Quick verification: `git status` to confirm the branch and working-tree state match what memory says.
6. Emit the brief. Stop.

**Result:** ~15-line summary, one concrete next action, user responds with "OK, go" or a redirect.

### Example 2: Fresh project with no memory yet

**User says:** "Catch up."

**Actions:**

1. Memory dir doesn't exist yet, or is empty except for a placeholder.
2. Report: "This project has no stored memory. The conventional priming files (CLAUDE.md, SOUL.md, PROJECT.md) **are/are not** present. Describe the task you want help with and I'll start fresh."
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

**Cause:** The slug transformation differs from Claude Code's internal convention on this host, or the project was worked on from a different CWD.

**Solution:** Run `ls ~/.claude/projects/ | grep <project_name_fragment>` to find the actual dir. If multiple matches exist (e.g. the project was opened from both `/repos/foo` and `/repos/foo/src`), prefer the one with the most recent `MEMORY.md`.

### Error: Memory files cite a file path that no longer exists

**Symptom:** `project_state.md` says "see `src/old_module.py`" but the file isn't there.

**Cause:** Code moved / was renamed / was deleted since the memory was written.

**Solution:** Don't cite the dead reference. Either (a) find the replacement with `grep` and update the memory file to match, or (b) flag the drift in the brief and ask the user to clarify. Don't guess.

### Error: Over-reading — reading every memory file just in case

**Symptom:** You've read 10+ files and you're still "gathering context".

**Cause:** Trying to understand everything before acting, instead of trusting the index.

**Solution:** Stop reading. `MEMORY.md` descriptions exist precisely so you don't have to read every file. If the descriptions don't clearly point at what you need, ask the user to scope the spinup.

### Error: Starting work without go-ahead

**Symptom:** After producing the brief, you immediately propose a next experiment, edit, or command.

**Cause:** Misreading "the next action is X" in memory as a directive.

**Solution:** Stop. Emit the brief. Wait for the user to say "go" or to redirect. The memory's "next action" is a report, not a command.

### Error: Citing a stale `feedback_*.md` entry

**Symptom:** You quote a feedback memory that is several sessions old and no longer reflects the user's current stance.

**Cause:** Treating memory as ground truth without verification.

**Solution:** When citing feedback, preface with "according to memory: ..." and invite correction if the user's stance has shifted. The user's live feedback always overrides stored memory.

## Anti-patterns

- **Don't start work without go-ahead.** Spinup is read-only.
- **Don't read every memory file.** Budget 3–6. If you need more, the index is failing — ask the user to scope.
- **Don't re-derive settled decisions.** Closed hypotheses stay closed unless the user reopens them.
- **Don't quote verbatim.** Summarise; the brief is for signal extraction.
- **Don't propose new experiments during spinup.** That's post-spinup territory.
- **Don't verify claims you don't need** — only check assertions you're about to commit to.
- **Don't report on things you didn't read.** The brief reflects only files you actually opened.
- **Don't project confidence where memory is stale.** Phrase uncertain claims as "according to memory" and invite correction.
- **Don't over-format the brief.** Markdown tables are for results. Prose bullets fit spinup summaries.
