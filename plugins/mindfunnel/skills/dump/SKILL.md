---
name: dump
description: Consolidate the current session's progress into the project's auto-memory directory — the "log everything, update state, prepare for resumption" drill. Use when the user says "log everything", "checkpoint", "save progress", "update memory", "dump state", or when a long session is about to end and context is saturated. Works on any project primed with /mf:prime; writes to the Claude Code auto-memory dir under ~/.claude/projects/<slug>/memory/.
disable-model-invocation: true
allowed-tools: [Read, Write, Edit, Glob, Grep, Bash]
---

# /mf:dump — session → project memory

Write the current session's non-derivable state to the project's auto-memory directory so a future session can resume cleanly. Idempotent: can run mid-session, at a natural checkpoint, or at end-of-session.

## Important

1. **Never proliferate files.** Update existing memory first; create new files only when a topic genuinely deserves its own dossier.
2. **Only log non-derivable signal.** Facts recoverable from `git log`, current code, or `CLAUDE.md` do not belong in memory.
3. **SOUL.md and CLAUDE.md are sacred.** Propose edits, never apply silently, and only when the insight is genuinely general.
4. **Convert every "today" / "tomorrow" to an absolute date** before writing. Run `date -I` if uncertain.

## Instructions

### Step 1: Locate the memory directory

Claude Code's auto-memory system lives at `~/.claude/projects/<slug>/memory/` where `<slug>` is the project's absolute path with every `/` replaced by `-`.

```bash
bash -c 'echo ~/.claude/projects/$(echo "$PWD" | sed "s|/|-|g")/memory'
```

The directory is usually already created by Claude Code. If not, create it before writing.

### Step 2: Verify the project is primed

Confirm `CLAUDE.md`, `SOUL.md`, `PROJECT.md` exist in the project root (these are set up by `/mf:prime`). If any are missing:

- **Flag it** and offer to run `/mf:prime` from the project root.
- **Do not run `/mf:prime` silently** — pre-existing files with the same name matter.
- **Proceed with the dump anyway**, noting the priming gap in the final report.

### Step 3: Survey existing memory

Read `<memory_dir>/MEMORY.md` (the index) and the most recently modified files:

```bash
ls -lt <memory_dir>/*.md 2>/dev/null | head -10
```

Decide for each signal you want to log: does it belong in an **existing file** (preferred) or a **new file** (rare)?

### Step 4: Extract signal from the conversation

Identify, in priority order:

1. **Results + numbers** — experiment outcomes, benchmarks, sweep tables. Always keep the actual numbers, never just "it worked".
2. **Decisions + rationale** — especially tradeoffs. The _why_ is more durable than the _what_.
3. **Load-bearing code changes** — structural shifts, new entry points, architectural moves. Not trivial edits.
4. **Open threads** — pending experiments, unresolved questions, "run this next" commands.
5. **Surprises and corrections** — failed hypotheses, midcourse reversals, negative results.

Skip anything derivable from `git log`, the current code, or the primed config files.

### Step 5: Write using the auto-memory type taxonomy

Every memory file has YAML frontmatter with `name`, `description`, `type`. The four types:

- **`project`** — ongoing work state, results, decisions, deadlines, pending experiments. High churn.
- **`feedback`** — behavioural guidance (both corrections _and_ validated choices). Each entry: rule + **Why:** + **How to apply:**. Moderate churn.
- **`user`** — durable facts about the user's role, expertise, responsibilities. Low churn.
- **`reference`** — pointers to external systems (issue trackers, experiment trackers, dashboards, buckets). Low churn.

Filename convention: `<type>_<topic>.md` (e.g. `project_state.md`, `results_full_sweep.md`, `feedback_offline_vs_online.md`, `reference_wandb.md`).

### Step 6: Refresh the index

Update `<memory_dir>/MEMORY.md` with one line per entry:

```markdown
- [Title](file.md) — one-line hook, under ~150 characters.
```

`MEMORY.md` has no frontmatter — it's an index, not a memory. For any file you updated or created, re-word its hook if the content shifted substantively.

### Step 7: Cross-check, then write

Before writing: for any file you're about to modify, read it first to preserve load-bearing context. Duplication is a smell — if the same fact appears in two files, pick one canonical home and cross-reference.

### Step 8: (Rare) Propose SOUL.md / CLAUDE.md edits

If the session surfaced a **general** guideline or preference worth propagating to every future session on any project, propose an edit to:

- `SOUL.md` at `~/.mindfunnel/SOUL.md` — user traits, collaboration style, communication preferences.
- `CLAUDE.md` at `~/.mindfunnel/AGENTS.md` (the `CLAUDE.md` symlink points there) — general engineering guidelines.

**Guardrails:**

- **Propose, never apply silently.** Show the proposed passage, explain _why_ it's general, wait for explicit approval, then apply.
- **Budget**: 0 proposals in the common case, 1 every 5–10 dumps at most.
- **Three conditions must all hold**: genuinely general (applies to any project), stable (not contradicted elsewhere), actionable (a concrete rule, not a vibe).
- **Never edit the `CLAUDE.md` symlink directly** — always edit the underlying `AGENTS.md`.

If in doubt, skip. SOUL.md and CLAUDE.md churn creates noise.

### Step 9: Report

End with a concise summary, ≤ 15 lines:

```
Memory dir: <path>
Updated:
  - <file> — <one-line reason>
Created:
  - <file> — <one-line reason>
Index (MEMORY.md): refreshed | unchanged
Proposed SOUL.md / CLAUDE.md edits: none | <one-line summary, pending approval>
```

If nothing was worth logging, say "no new signal; memory is current" and do nothing.

## Examples

### Example 1: Mid-sweep checkpoint after a production run

**User says:** "Log everything, the sweep results just came in."

**Actions:**

1. Compute memory dir via the sed snippet; confirm `MEMORY.md` exists; read it.
2. Read the most recent `project_state.md` and `results_*.md` files.
3. From the conversation, extract: sweep numbers (per-seed, aggregate), the decision made ("v3 recipe wins cleanly"), any flagged concerns.
4. Update `project_state.md` with the new "where we are + next action".
5. Create `results_<experiment>_<date>.md` if the sweep is a major dossier; otherwise append to an existing results file.
6. Refresh `MEMORY.md` one-liner for each touched file.
7. No SOUL.md / CLAUDE.md proposals.

**Result:** One report block listing what was updated, memory ready for the next session.

### Example 2: End-of-session cleanup with no new findings

**User says:** "Dump before I close."

**Actions:**

1. Scan the conversation for signal. Finds: only tool invocations and small Q&A, no new results or decisions.
2. Skip the dump entirely.
3. Report: "no new signal since the last dump; memory is current."

### Example 3: General guideline surfaces, worth a CLAUDE.md proposal

**User says:** "Log everything. That lesson about always verifying memory claims before citing them is something I want to keep."

**Actions:**

1. Update `project_state.md` and any `results_*.md` as usual.
2. Draft a one-paragraph addition to `~/.mindfunnel/AGENTS.md` under "Handling Existing Code" or "Autonomy and Asking".
3. Show the proposed diff to the user.
4. **Wait for approval.** Do not apply.
5. On approval: apply the edit, confirm, and note it in the dump report.

## Troubleshooting

### Error: Memory directory path seems wrong

**Symptom:** Files land at an unexpected location, or Claude Code complains about an unknown memory dir.

**Cause:** The slug transformation doesn't match Claude Code's internal convention on this host.

**Solution:** Check with `ls ~/.claude/projects/` — the current project's dir should appear. If absent, Claude Code hasn't indexed this project yet; create the dir manually with `mkdir -p ~/.claude/projects/<slug>/memory` and Claude Code will adopt it.

### Error: Conflicting facts between memory files

**Symptom:** Two memory files disagree on a number or decision.

**Cause:** A previous dump duplicated content instead of cross-referencing.

**Solution:** Pick the **newer** or **more specific** statement as canonical. Edit the other file to cross-reference the canonical one (`See [results_foo.md](results_foo.md) for current numbers.`). Note the consolidation in the final dump report.

### Error: Memory churn — dumping too often with too little signal

**Symptom:** `git log` of the memory dir shows many small updates, many of them trivial.

**Cause:** The empty-dump guard is being skipped.

**Solution:** Skip the dump when the conversation contains only tool noise / small Q&A. Say "no new signal; memory is current" and do nothing. Memory is not a commit log.

### Error: Proposed a SOUL.md / CLAUDE.md edit that was rejected

**Symptom:** The user said "no" to a proposed general-guideline edit.

**Cause:** The insight wasn't actually general, or was contradicted by other contexts.

**Solution:** Accept the rejection, do **not** re-propose in the same session, and move the insight into a **project-level `feedback_*.md`** instead if it's still useful at the project scope.

## Anti-patterns

- **Don't dump verbatim tool output** — summarise signal, cite key numbers only.
- **Don't log bug-fix recipes** — the fix is in the code, its context is in the commit. Log _why_ the bug existed if non-obvious.
- **Don't overwrite** existing content without reading first.
- **Don't propose SOUL.md / CLAUDE.md edits routinely.** Once every few dumps at most, or if really needed.
- **Don't create a new file** when an existing one can absorb the update.
- **Don't list every tool call you made** — memory is for signal, not process.
- **Don't re-run experiments or verify against current code** — that's spinup's job. Dump is mostly write.
- **Don't include ephemeral task details** (current conversation turn, in-progress tool output) — those live in the conversation.
- **Don't create TODO lists in memory.** Pending actions belong in `project_state.md` under a "Next actions" section, tied to a concrete command or decision.
