---
name: setup
description: Bootstrap — seed ~/.mindfunnel/ with AGENTS.md, SOUL.md, USER.md, and PROJECT.md.example from the plugin's bundled templates. Use the first time you run the mindfunnel plugin on a new machine, when ~/.mindfunnel/ is missing, or after an mf upgrade that adds links. Idempotent — detects existing files and never overwrites. Also creates a CLAUDE.md symlink pointing at AGENTS.md inside ~/.mindfunnel/, and — for each agent installed — ~/.claude/{CLAUDE,SOUL,USER}.md + ~/.codex/{AGENTS,SOUL,USER}.md symlinks so both agents load the same baseline and personal files.
disable-model-invocation: true
allowed-tools: [Read, Write, Bash]
---

# /mf:setup — bootstrap `~/.mindfunnel/`

Seed the user's personal `~/.mindfunnel/` directory with the editable scaffolding the other mindfunnel skills depend on. Run **once per machine**, and again after an upgrade that adds a link. Idempotent: if `~/.mindfunnel/` already looks complete **and** Step 4 reports every link already in place, say so and stop. A complete `~/.mindfunnel/` alone is not enough — an upgrade can add links to it.

## Important

1. **Never overwrite user content.** Every target is created only if absent; the only things ever replaced are a dangling symlink and Step 3's own `CLAUDE.md` link. The user may have already edited `SOUL.md` or `USER.md` — destroying them is unacceptable.
2. **Templates live at `${CLAUDE_PLUGIN_ROOT}/templates/`.** That environment variable is set by Claude Code when this skill runs. Do not hard-code a path; always use the variable.
3. **`CLAUDE.md` inside `~/.mindfunnel/` is a symlink** to `AGENTS.md` in the same directory. This is the standard convention; both names point at the same content.
4. **`SOUL.md` and `USER.md` are user-global, not project-level.** Neither gets stamped into a project root by `/mf:prime`. This skill symlinks `~/.claude/{SOUL,USER}.md` and `~/.codex/{SOUL,USER}.md` to the corresponding files in `~/.mindfunnel/` so both agents reach the same source of truth.
5. **Each agent's baseline entry point is a symlink too**: `~/.claude/CLAUDE.md` → `~/.mindfunnel/CLAUDE.md`, and `$CODEX_HOME/AGENTS.md` (default `~/.codex/`) → `~/.mindfunnel/AGENTS.md`. Codex reads that file unless an `AGENTS.override.md` sits beside it, which Step 4 reports. Without these links, no agent loads the baseline.

## Instructions

### Step 1: Ensure `~/.mindfunnel/` exists

```bash
mkdir -p "$HOME/.mindfunnel"
```

### Step 2: Seed the four template files (non-destructive)

For each pair below, copy from the bundled template to the target **only if the target is absent**.

| Template                                     | Target                             |
| -------------------------------------------- | ---------------------------------- |
| `${CLAUDE_PLUGIN_ROOT}/templates/AGENTS.md`  | `~/.mindfunnel/AGENTS.md`          |
| `${CLAUDE_PLUGIN_ROOT}/templates/SOUL.md`    | `~/.mindfunnel/SOUL.md`            |
| `${CLAUDE_PLUGIN_ROOT}/templates/USER.md`    | `~/.mindfunnel/USER.md`            |
| `${CLAUDE_PLUGIN_ROOT}/templates/PROJECT.md` | `~/.mindfunnel/PROJECT.md.example` |

Note the asymmetry: `PROJECT.md` lands as `PROJECT.md.example` in `~/.mindfunnel/` because the live `PROJECT.md` belongs in each _project_, not in the shared scaffolding. The `.example` suffix makes that intent obvious.

Shell form (avoid clobbering):

```bash
cp -n "${CLAUDE_PLUGIN_ROOT}/templates/AGENTS.md"  "$HOME/.mindfunnel/AGENTS.md"
cp -n "${CLAUDE_PLUGIN_ROOT}/templates/SOUL.md"    "$HOME/.mindfunnel/SOUL.md"
cp -n "${CLAUDE_PLUGIN_ROOT}/templates/USER.md"    "$HOME/.mindfunnel/USER.md"
cp -n "${CLAUDE_PLUGIN_ROOT}/templates/PROJECT.md" "$HOME/.mindfunnel/PROJECT.md.example"
```

`cp -n` is "no-clobber"; it silently skips an existing target. That is the desired behavior.

### Step 3: Create the `CLAUDE.md` symlink inside `~/.mindfunnel/`

```bash
ln -sfn AGENTS.md "$HOME/.mindfunnel/CLAUDE.md"
```

`-f` replaces a broken or pre-existing symlink, `-n` prevents following an existing `CLAUDE.md` symlink into its target when forcing. Safe because we're only ever symlinking to `AGENTS.md` in the same directory.

### Step 4: Create the per-agent symlinks into `~/.claude/` and `~/.codex/`

`SOUL.md`, `USER.md` and the baseline `AGENTS.md` are user-global: Claude Code and Codex should reach the same source of truth at `~/.mindfunnel/`. For each agent dotdir that exists, install the symlinks idempotently. A target is created when absent and re-pointed only when it is a dangling symlink; a real file, or a symlink to somewhere else (a dotfiles setup, say), is the user's and stays as it is. Run the snippet as one block — `mf_link` exists only in the shell that defines it. It prints one status line per target; build the Step 5 report from those lines.

```bash
codex_dir=${CODEX_HOME:-$HOME/.codex}
mf_link() {  # mf_link <target> <src> — idempotent; replaces nothing but a dangling symlink
    local target=$1 src=$2 cur
    [ -d "$(dirname "$target")" ] || return 0   # agent not installed: the loop reports it
    if [ ! -e "$src" ]; then
        echo "$target: skipped (no $src)"
    elif [ -L "$target" ]; then
        cur=$(readlink "$target")
        if [ "$cur" = "$src" ]; then
            echo "$target: already symlinked correctly"
        elif [ -e "$target" ]; then
            echo "$target: left alone (symlink to $cur)"
        elif ln -sfn "$src" "$target"; then
            echo "$target: re-pointed (was dangling → $cur)"
        else
            echo "$target: FAILED to re-point"
        fi
    elif [ -e "$target" ]; then
        echo "$target: left alone (real file)"
    elif ln -s "$src" "$target"; then
        echo "$target: symlinked → $src"
    else
        echo "$target: FAILED to link"
    fi
}
for agent_dir in "$HOME/.claude" "$codex_dir"; do
    if [ ! -d "$agent_dir" ]; then
        echo "$agent_dir/: not present; skipped"
        continue
    fi
    mf_link "$agent_dir/SOUL.md" "$HOME/.mindfunnel/SOUL.md"
    mf_link "$agent_dir/USER.md" "$HOME/.mindfunnel/USER.md"
done
mf_link "$HOME/.claude/CLAUDE.md" "$HOME/.mindfunnel/CLAUDE.md"
mf_link "$codex_dir/AGENTS.md" "$HOME/.mindfunnel/AGENTS.md"
if [ -s "$codex_dir/AGENTS.override.md" ]; then
    echo "$codex_dir/AGENTS.override.md: present — Codex reads it instead of AGENTS.md"
fi
```

Skip an agent dir that doesn't exist (e.g. `~/.codex/` on a Claude-only machine). Don't create agent dirs yourself — they're owned by the respective agent installer.

### Step 5: Report

Emit a short summary listing for each target: **created**, **already present** (skipped), **symlinked**, **re-pointed** (was dangling), **left alone** (a real file, or a symlink elsewhere — name its target), or **skipped**. Flag an `AGENTS.override.md`. Example:

```
~/.mindfunnel/
  AGENTS.md          created
  SOUL.md            created
  USER.md            created
  PROJECT.md.example already present
  CLAUDE.md          symlinked → AGENTS.md
~/.claude/CLAUDE.md  symlinked → ~/.mindfunnel/CLAUDE.md
~/.claude/SOUL.md    symlinked → ~/.mindfunnel/SOUL.md
~/.claude/USER.md    symlinked → ~/.mindfunnel/USER.md
~/.codex/AGENTS.md   symlinked → ~/.mindfunnel/AGENTS.md
~/.codex/SOUL.md     symlinked → ~/.mindfunnel/SOUL.md
~/.codex/USER.md     symlinked → ~/.mindfunnel/USER.md
```

If everything was already present, say so in one line and skip the table:

```
~/.mindfunnel/ is already set up. Nothing to do.
```

### Step 6: Point the user at `SOUL.md` and `USER.md`

On a fresh install (anything was created), close with:

> Edit `~/.mindfunnel/SOUL.md` to describe who you are, how you work, and what
> to avoid. Edit `~/.mindfunnel/USER.md` to capture your shell, Python
> defaults, formatter paths, and any per-machine tooling the agent needs to
> know about. Neither file is checked into any project — they shape how
> every agent collaborates with you across every project.
>
> Then run `/mf:prime` from a project root to prime it for the mindfunnel workflow.

On a no-op run, skip this paragraph.

## Examples

### Example 1: Fresh machine, first install

```
~/.mindfunnel/
  AGENTS.md          created
  SOUL.md            created
  USER.md            created
  PROJECT.md.example created
  CLAUDE.md          symlinked → AGENTS.md
~/.claude/CLAUDE.md  symlinked → ~/.mindfunnel/CLAUDE.md
~/.claude/SOUL.md    symlinked → ~/.mindfunnel/SOUL.md
~/.claude/USER.md    symlinked → ~/.mindfunnel/USER.md
~/.codex/AGENTS.md   symlinked → ~/.mindfunnel/AGENTS.md
~/.codex/SOUL.md     symlinked → ~/.mindfunnel/SOUL.md
~/.codex/USER.md     symlinked → ~/.mindfunnel/USER.md
```

Followed by the "edit `SOUL.md` / `USER.md`" hint.

### Example 2: Re-run after everything's in place

```
~/.mindfunnel/ is already set up. Nothing to do.
```

### Example 3: User deleted `SOUL.md` and re-ran setup

```
~/.mindfunnel/
  AGENTS.md          already present
  SOUL.md            created
  USER.md            already present
  PROJECT.md.example already present
  CLAUDE.md          symlinked → AGENTS.md
~/.claude/CLAUDE.md  already symlinked correctly
~/.claude/SOUL.md    already symlinked correctly
~/.claude/USER.md    already symlinked correctly
~/.codex/AGENTS.md   already symlinked correctly
~/.codex/SOUL.md     already symlinked correctly
~/.codex/USER.md     already symlinked correctly
```

### Example 4: Claude-only machine (no `~/.codex/`)

```
~/.mindfunnel/
  AGENTS.md          created
  SOUL.md            created
  USER.md            created
  PROJECT.md.example created
  CLAUDE.md          symlinked → AGENTS.md
~/.claude/CLAUDE.md  symlinked → ~/.mindfunnel/CLAUDE.md
~/.claude/SOUL.md    symlinked → ~/.mindfunnel/SOUL.md
~/.claude/USER.md    symlinked → ~/.mindfunnel/USER.md
~/.codex/            not present; skipped
```

## Anti-patterns

- **Don't hard-code `/home/<user>/repositories/.../templates/`.** Always use `${CLAUDE_PLUGIN_ROOT}`; the cache path changes on every update.
- **Don't create files inside the plugin cache (`${CLAUDE_PLUGIN_ROOT}`).** That directory is discarded and recreated on plugin update. Only read from it.
- **Don't touch per-project files.** `/mf:setup` only writes inside `~/.mindfunnel/` and creates the per-agent symlinks in `~/.claude/` / `~/.codex/`. Per-project work is `/mf:prime`'s job.
- **Don't create `~/.claude/` or `~/.codex/` yourself.** If an agent's dotdir doesn't exist, the user hasn't installed that agent; installing a symlink into a non-existent dir would be premature. Skip and move on.
