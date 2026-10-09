---
name: unpark
description: Bring back scratchpads saved by /mf:park after a reboot — into this session's scratchpad, every file verified, then the saved copy deleted (`--keep` retains it).
disable-model-invocation: true
allowed-tools: [Read, Glob, Bash]
---

# /mf:unpark — project → scratchpad, after a reboot

Restores the snapshots `/mf:park` left in `<project root>/.mf/park/`, verifies every entry, then pops each one: its manifest is copied into the scratchpad as `PARKED-<session-id>.md` and the snapshot is deleted. `--keep` in the arguments retains the snapshots; `--beside` restores, beside them, the parked versions of entries the target already holds differently (step 3).

## Steps

### 1. Find the snapshots and this session

- **Project root**: `git rev-parse --show-toplevel`, else the working directory. Snapshots are the directories `<root>/.mf/park/*/`, each named by the session id it came from; its `MANIFEST.md` gives the source path, the date and the counts. A directory named `<id>.partial` is a park that was killed midway: report it, and restore nothing from it. With no snapshot, say so and stop.
- **This session**: the scratchpad your system prompt names, and `$CLAUDE_CODE_SESSION_ID`.

Done when each snapshot is listed with its session id, parked date and file count.

### 2. Choose what goes where

- **This session's snapshot** (resumed: the ids match) goes into this scratchpad. Its manifest's `from:` should be this same path; if it is not, say so, restore here anyway, and give the old → new path.
- **Another session's snapshot** comes in only on the person's word: a snapshot taken into this session is no longer where its own session will look when resumed. List them and ask which, if any, to bring in. One goes into this scratchpad; several go into subdirectories of it named by their session ids.
- The rest stay parked. Name them: each comes back by resuming its own session and running `/mf:unpark` there.

Done when every snapshot has a destination or is named as staying parked.

### 3. Restore, verify, pop

For each snapshot being restored:

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/unpark.sh" "<root>/.mf/park/<session-id>" "<target>" [--keep] [--beside]
```

The script checks the snapshot against its own records, then puts each entry in place under a temporary name, renames it and compares it, so an interrupted restore never leaves a partial file under a real name. It never overwrites: an entry already at the target that differs from the snapshot, or one reached through a symlinked directory, is listed as `FAILED` with the reason and left as it is. Its exit status:

- **0**: restored and verified; popped, or `kept` under `--keep`. Under `--beside` it names each parked version it put under `<target>/PARKED-<session-id>/`.
- **1**: the `FAILED` entries were left as they are, and the snapshot stays. Show them to the person with both versions' size and modification time (`ls -l --time-style=full-iso`; the parked one is in `<snapshot>/files/`) and ask: leave the snapshot parked, to sort out by hand later, or re-run with `--beside` (keeping `--keep` if it was given), which restores each parked version under a fresh `<target>/PARKED-<session-id>/` beside the target's own, overwriting nothing. If `--beside` still exits 1, a copy failed: report it, and the snapshot stays.
- **2**: a usage error or a refused path; nothing was touched. Report it.
- **3**: restored and verified, but popping the snapshot failed. Report the message: the snapshot (or the leftover it names) is the person's to delete once satisfied.
- **4**: no snapshot there, or one that no longer matches its own records. Report it for the person to inspect by hand; restore nothing from it.
- **5**: failed before the restore finished; nothing was overwritten and the snapshot stays. Report the message.

Done when every snapshot being restored has its exit status handled as above.

### 4. Report

The files restored and where, and any parked versions put under `PARKED-<session-id>/`; each snapshot popped, kept or still parked; and, wherever a target differs from the manifest's `from:`, the old → new path — notes or memory that name the old path need updating.
