---
name: park
description: Save this project's Claude Code scratchpads into the project before a reboot — triaged (kept or dropped, a reason for every drop) or, with `all`, whole. /mf:unpark brings them back.
disable-model-invocation: true
allowed-tools: [Read, Write, Glob, Grep, Bash]
---

# /mf:park — scratchpads → project, before a reboot

Session scratchpads live under `/tmp`, which a reboot usually clears, taking with it every probe, intermediate result and script that would then have to be regenerated. Park copies what is worth keeping into `<project root>/.mf/park/<session-id>/`, each file checked against its source; `/mf:unpark` restores it afterwards. `all` in the arguments skips the triage and parks every file. Empty directories and special files (FIFOs, sockets, devices) are never kept.

## Steps

### 1. Locate the scratchpads

- **This session's**: the scratchpad directory your system prompt names. Its parent directory's name is the session id, and must equal `$CLAUDE_CODE_SESSION_ID`. If the directory is missing or the two disagree, stop and report both: a wrong path parks an empty snapshot that looks fine.
- **The project's others**: the sibling session directories, `<this scratchpad>/../../*/scratchpad`, each named by its own session id. Other sessions may still be running; a park copies them as they are now.
- **Project root**: `git rev-parse --show-toplevel`, else the working directory.

A scratchpad counts when it holds a file or a symlink. For each, record its session id, path, entry count (`find <sp> \( -type f -o -type l \) | wc -l`) and bytes (`du -sb <sp>`).

Done when every scratchpad of the project holding an entry is listed with its counts, or the run stopped with the reason.

### 2. Triage (skipped under `all`)

Sort every entry of each scratchpad into keep or drop, with a one-line reason. A directory whose contents share one fate — a cache, a virtualenv — is one row.

- **Drop** what nothing will need again: regenerable byproducts (`__pycache__/`, `.pytest_cache/`, `node_modules/`, virtualenvs, build output); empty files; a file whose content now lives elsewhere — committed to the project, written to memory — naming where; a version superseded by a later one nothing still uses; a probe whose answer is already recorded.
- **Keep** everything else, and anything uncertain: a wrong drop costs the work, a wrong keep costs disk.
- **Another session's scratchpad**: this session lacks the context of why its files exist, so drop only regenerable byproducts there.
- Give the size of any kept entry over 100 MB, so the person can choose to drop it. Name any kept symlink that points outside the scratchpad: it is parked as a link and keeps pointing there, and an absolute one into the old scratchpad dangles once restored into a new session.

Show one table per scratchpad — entry, size, keep or drop, reason — with totals, and wait for one go-ahead; the person may move rows between the columns. Then write each scratchpad's drops to a file from `mktemp`, one `./`-prefixed path per line: a file exactly, or a directory and everything under it when the line ends in `/`. The script rejects a line that matches nothing; a `/`-ended line still takes everything under it, which step 3 checks.

Done when every entry of every scratchpad sits in exactly one row and the person has answered.

### 3. Copy and verify

For each scratchpad:

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/park.sh" "<scratchpad>" "<root>/.mf/park/<session-id>" ["<drop list>"]
```

The script copies everything not dropped, checks every file by sha256 and every symlink by its target, and moves the snapshot into place only once that passes; inside git it adds `.mf/park/` to `.git/info/exclude` (local, never committed) unless it is already ignored. Its exit status:

- **0**: parked.
- **3**: parked, but git does not ignore `.mf/park/`: tell the person, so the snapshot stays out of commits.
- **4**: a snapshot of that session already exists, never unparked; the message counts its entries missing from the scratchpad, those edited since and those new since. Missing entries mean a reboot (or a deletion) took them: for this session, `/mf:unpark` comes first; for another session, leave it, and if it counts edited or new entries, say in the report that that session's newer work is not saved: resuming it, `/mf:unpark` and `/mf:park` there saves both. None missing means the scratchpad is the newer state: ask the person, and on a yes re-run with `--replace` as the first argument.
- **5**: something sits at the snapshot's path that is no readable snapshot. Report it for the person to inspect by hand, and leave it alone.
- **6**: the input needs fixing. A drop line that matches nothing: correct it and re-run. A name containing a newline: ask the person to rename the file, or drop it. Nothing to park: report it.
- **1 or 2**: the park failed (1) or a path was refused (2); nothing was left behind. Report the message and go on with the other scratchpads.

After 0 or 3, check the snapshot against the table: every entry the table kept, or every file and symlink under a kept directory, is a line of `<snapshot>/keep.list`. One that is not was taken by a `/`-ended drop line: narrow that line and re-run with `--replace`. Then write `<snapshot>/MANIFEST.md`, Kept from `keep.list` and Dropped from the lines of `all.list` not in it, each with the table's reason:

```markdown
# Parked scratchpad — <session-id>

- parked: <ISO-8601 UTC> · mode: triaged | all
- from: <scratchpad path>
- project: <root> @ <git HEAD, or "not a git repository">

## Kept (<n> files, <bytes>)

| entry | bytes | reason |

## Dropped (<n> files, <bytes>)

| entry | bytes | reason |
```

Under `all`, the Kept table may list directories rather than files and Dropped is empty.

Done when every scratchpad was parked, matches its table and has its manifest, or has its exit status handled as above.

### 4. Report

Per scratchpad: kept and dropped counts with bytes, the snapshot path or what stopped it, and the exclude line if one was added. Say that anything written to a scratchpad from now on is not in the snapshot unless it is parked again (`--replace`), and that `git clean -x` would delete the snapshot. Then the way back: after the reboot, resume this session (`claude --resume <session-id>`, or `/resume`) and run `/mf:unpark`, which restores the files where they were. A fresh session works too: unpark then offers to bring a snapshot into its new scratchpad.
