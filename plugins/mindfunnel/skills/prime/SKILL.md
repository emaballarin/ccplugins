---
name: prime
description: Prime the current project for the mindfunnel workflow — create CLAUDE.md / AGENTS.md / SOUL.md symlinks into ~/.mindfunnel/, touch an empty PROJECT.md if absent, and add SOUL.md to .gitignore if this is a git repo. Run from the project root. Idempotent with a safety guard — prompts before overwriting pre-existing non-symlink files with the same names. Requires /mf:setup to have been run first.
disable-model-invocation: true
allowed-tools: [Read, Write, Bash]
---

# /mf:prime — prime a project for the mindfunnel workflow

Set up the current project's root so that `/mf:spinup` and `/mf:dump` have the files they expect: `CLAUDE.md`, `AGENTS.md`, `SOUL.md` as symlinks into `~/.mindfunnel/`, plus a project-local `PROJECT.md`. Run **once per project**, from the project root.

## Important

1. **Run from the project root.** The skill writes symlinks into the current working directory. Confirm with `pwd` before acting if there's any doubt.
2. **Never clobber a pre-existing non-symlink file without confirmation.** If the project already has a real `AGENTS.md` or `CLAUDE.md`, flag it and **ask the user** before replacing it. A symlink already pointing at the correct target is a no-op.
3. **`~/.mindfunnel/` must already be set up.** If it isn't, stop and tell the user to run `/mf:setup` first.
4. **`SOUL.md` is personal.** It's added to `.gitignore` in any git repo — never checked in.

## Instructions

### Step 1: Verify `~/.mindfunnel/` is ready

Check that `~/.mindfunnel/AGENTS.md` exists and is readable:

```bash
[ -r "$HOME/.mindfunnel/AGENTS.md" ] && echo ready || echo missing
```

If missing, stop with:

> `~/.mindfunnel/` isn't set up yet. Run `/mf:setup` first, then re-run `/mf:prime`.

Do not proceed.

### Step 2: Survey the current directory

For each of `CLAUDE.md`, `AGENTS.md`, `SOUL.md` in the cwd, classify:

- **absent** — no file, no symlink → safe to create.
- **correct symlink** — already a symlink pointing at the expected target → skip silently.
- **other symlink** — a symlink pointing somewhere else → flag, ask before replacing.
- **regular file** — real file, possibly user-authored → flag, ask before replacing.

```bash
for f in CLAUDE.md AGENTS.md SOUL.md; do
    if [ -L "$f" ]; then
        printf '%s → %s\n' "$f" "$(readlink "$f")"
    elif [ -e "$f" ]; then
        printf '%s (regular file)\n' "$f"
    else
        printf '%s (absent)\n' "$f"
    fi
done
```

If anything lands in the **other symlink** or **regular file** bucket, present the findings to the user in one short block and ask "Replace these with mindfunnel symlinks? [y/N]". Only proceed on an explicit yes. On no or silence, skip those targets and continue with the absent ones.

### Step 3: Create the symlinks

The symlink chain mirrors what the old `bin/mindfunnel` shell script did:

```bash
# CLAUDE.md points at ~/.mindfunnel/CLAUDE.md (which itself symlinks to AGENTS.md)
ln -s "$HOME/.mindfunnel/CLAUDE.md" CLAUDE.md

# AGENTS.md points at the local CLAUDE.md (same content, standard alias)
ln -s CLAUDE.md AGENTS.md

# SOUL.md points directly at the shared one in ~/.mindfunnel/
if [ -e "$HOME/.mindfunnel/SOUL.md" ]; then
    ln -s "$HOME/.mindfunnel/SOUL.md" SOUL.md
else
    echo "!! $HOME/.mindfunnel/SOUL.md is missing. Skipping SOUL.md symlink."
    echo "   Create it (or re-run /mf:setup), then re-run /mf:prime."
fi
```

For any target the user approved replacing in step 2, `rm -f` it before the `ln -s`. For a **correct symlink** that already points at the right target, do nothing — don't re-create it.

### Step 4: Touch `PROJECT.md` if absent

```bash
[ -e PROJECT.md ] || touch PROJECT.md
```

Never overwrite an existing `PROJECT.md`. If the project already has one, leave it alone.

### Step 5: Add `SOUL.md` to `.gitignore` in a git repo

Check whether the current directory is inside a git working tree. If so, ensure `SOUL.md` is listed in `.gitignore`:

```bash
if git rev-parse --git-dir >/dev/null 2>&1; then
    if [ ! -f .gitignore ] || ! grep -qx 'SOUL.md' .gitignore; then
        echo 'SOUL.md' >> .gitignore
        echo "Added SOUL.md to .gitignore"
    fi
fi
```

Don't do this if the project isn't a git repo — the file is pointless otherwise.

### Step 6: Report

Emit a short summary, ≤ 10 lines. For each symlink: **created**, **already correct** (no-op), **replaced** (user approved), or **skipped** (user declined or source missing). For `PROJECT.md` and `.gitignore`: one-liner each.

## Examples

### Example 1: Clean project, first prime

```
CLAUDE.md   created → ~/.mindfunnel/CLAUDE.md
AGENTS.md   created → CLAUDE.md
SOUL.md     created → ~/.mindfunnel/SOUL.md
PROJECT.md  created (empty)
.gitignore  added SOUL.md
```

### Example 2: Project already primed, re-run

```
All three symlinks already correct. PROJECT.md present. .gitignore already lists SOUL.md. Nothing to do.
```

### Example 3: Project has a pre-existing `AGENTS.md`

```
Found: AGENTS.md (regular file, 2.3 KB)
This looks like an existing, hand-written AGENTS.md. Replacing it with the
mindfunnel symlink would discard its contents.

Replace it with a mindfunnel symlink? [y/N]
```

If user says **no**: prime the other two targets, skip `AGENTS.md`, note the skip in the report.

## Troubleshooting

### Error: "`~/.mindfunnel/` isn't set up"

Run `/mf:setup` first. `/mf:prime` depends on the shared scaffolding existing.

### Error: user accidentally said "yes" to replacing a real file

The old file is gone. Symlinks don't preserve history. Recover from git (`git show HEAD:AGENTS.md > AGENTS.md`) if possible. Otherwise, restore from backup or rewrite.

### The project's `AGENTS.md` / `CLAUDE.md` is already a symlink pointing into some other directory

That's an unusual setup — probably a different convention the user is following. **Ask**, don't replace blindly. The user may want to keep the existing symlink.

## Anti-patterns

- **Don't run from anywhere but the project root.** Symlinks in the wrong cwd cause silent confusion later.
- **Don't replace a pre-existing non-symlink without explicit approval.** The user's hand-written file always wins over a template.
- **Don't create `PROJECT.md` with placeholder content.** It's created empty on purpose; the user fills it in as the project develops. A non-empty default encourages copy-paste that never gets edited.
- **Don't add `SOUL.md` to `.gitignore` outside a git repo.** The file would be meaningless and leave noise behind.
- **Don't auto-run `/mf:setup`** if `~/.mindfunnel/` is missing. Ask the user; doing it silently hides the coupling.
