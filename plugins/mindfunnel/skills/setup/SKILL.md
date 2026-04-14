---
name: setup
description: One-time bootstrap — seed ~/.mindfunnel/ with AGENTS.md, SOUL.md, and PROJECT.md.example from the plugin's bundled templates. Use the first time you run the mindfunnel plugin on a new machine, or when ~/.mindfunnel/ is missing. Idempotent — detects existing files and never overwrites. Also creates a CLAUDE.md symlink pointing at AGENTS.md inside ~/.mindfunnel/.
disable-model-invocation: true
allowed-tools: [Read, Write, Bash]
---

# /mf:setup — bootstrap `~/.mindfunnel/`

Seed the user's personal `~/.mindfunnel/` directory with the editable scaffolding the other mindfunnel skills depend on. Run **once per machine**. Idempotent: if `~/.mindfunnel/` already looks complete, say so and stop.

## Important

1. **Never overwrite.** Every target file is created only if it doesn't already exist. The user may have already edited `SOUL.md` — destroying it is unacceptable.
2. **Templates live at `${CLAUDE_PLUGIN_ROOT}/templates/`.** That environment variable is set by Claude Code when this skill runs. Do not hard-code a path; always use the variable.
3. **`CLAUDE.md` inside `~/.mindfunnel/` is a symlink** to `AGENTS.md` in the same directory. This is the standard convention; both names point at the same content.

## Instructions

### Step 1: Ensure `~/.mindfunnel/` exists

```bash
mkdir -p "$HOME/.mindfunnel"
```

### Step 2: Seed the three template files (non-destructive)

For each pair below, copy from the bundled template to the target **only if the target is absent**.

| Template                                    | Target                            |
| ------------------------------------------- | --------------------------------- |
| `${CLAUDE_PLUGIN_ROOT}/templates/AGENTS.md` | `~/.mindfunnel/AGENTS.md`         |
| `${CLAUDE_PLUGIN_ROOT}/templates/SOUL.md`   | `~/.mindfunnel/SOUL.md`           |
| `${CLAUDE_PLUGIN_ROOT}/templates/PROJECT.md`| `~/.mindfunnel/PROJECT.md.example`|

Note the asymmetry: `PROJECT.md` lands as `PROJECT.md.example` in `~/.mindfunnel/` because the live `PROJECT.md` belongs in each *project*, not in the shared scaffolding. The `.example` suffix makes that intent obvious.

Shell form (avoid clobbering):

```bash
cp -n "${CLAUDE_PLUGIN_ROOT}/templates/AGENTS.md"  "$HOME/.mindfunnel/AGENTS.md"
cp -n "${CLAUDE_PLUGIN_ROOT}/templates/SOUL.md"    "$HOME/.mindfunnel/SOUL.md"
cp -n "${CLAUDE_PLUGIN_ROOT}/templates/PROJECT.md" "$HOME/.mindfunnel/PROJECT.md.example"
```

`cp -n` is "no-clobber"; it silently skips an existing target. That is the desired behavior.

### Step 3: Create the `CLAUDE.md` symlink

```bash
ln -sfn AGENTS.md "$HOME/.mindfunnel/CLAUDE.md"
```

`-f` replaces a broken or pre-existing symlink, `-n` prevents following an existing `CLAUDE.md` symlink into its target when forcing. Safe because we're only ever symlinking to `AGENTS.md` in the same directory.

### Step 4: Report

Emit a short summary, ≤ 10 lines, listing for each target: **created**, **already present** (skipped), or **symlinked**. Example:

```
~/.mindfunnel/
  AGENTS.md          created
  SOUL.md            created
  PROJECT.md.example already present
  CLAUDE.md          symlinked → AGENTS.md
```

If everything was already present, say so in one line and skip the table:

```
~/.mindfunnel/ is already set up. Nothing to do.
```

### Step 5: Point the user at `SOUL.md`

On a fresh install (anything was created), close with:

> Edit `~/.mindfunnel/SOUL.md` to describe who you are, how you work, and what
> to avoid. This file is private — it's not checked into any project — and it
> shapes how Claude Code collaborates with you across every project. Then run
> `/mf:prime` from a project root to prime it for the mindfunnel workflow.

On a no-op run, skip this paragraph.

## Examples

### Example 1: Fresh machine, first install

```
~/.mindfunnel/
  AGENTS.md          created
  SOUL.md            created
  PROJECT.md.example created
  CLAUDE.md          symlinked → AGENTS.md
```

Followed by the "edit `SOUL.md`" hint.

### Example 2: Re-run after everything's in place

```
~/.mindfunnel/ is already set up. Nothing to do.
```

### Example 3: User deleted `SOUL.md` and re-ran setup

```
~/.mindfunnel/
  AGENTS.md          already present
  SOUL.md            created
  PROJECT.md.example already present
  CLAUDE.md          symlinked → AGENTS.md
```

## Anti-patterns

- **Don't overwrite `SOUL.md`** — or any other target — under any circumstance. The user's edits are sacred.
- **Don't hard-code `/home/<user>/repositories/.../templates/`.** Always use `${CLAUDE_PLUGIN_ROOT}`; the cache path changes on every update.
- **Don't create files inside the plugin cache (`${CLAUDE_PLUGIN_ROOT}`).** That directory is discarded and recreated on plugin update. Only read from it.
- **Don't touch per-project files.** `/mf:setup` only writes inside `~/.mindfunnel/`. Per-project work is `/mf:prime`'s job.
