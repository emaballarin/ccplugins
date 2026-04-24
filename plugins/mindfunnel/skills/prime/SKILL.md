---
name: prime
description: Prime the current project for the mindfunnel workflow — stamp a project-scoped `AGENTS.md` from the bundled stub (if absent), create a project-local `CLAUDE.md` symlink to `./AGENTS.md`, touch an empty `PROJECT.md` if absent, clean up legacy `SOUL.md` / `CLAUDE.md` / `AGENTS.md` symlinks left behind by pre-0.3.0 primings, and strip legacy `CLAUDE.md`/`AGENTS.md` entries from `.gitignore` so the new committed files track cleanly. Run from the project root. Idempotent with a safety guard — leaves pre-existing hand-authored files alone. Requires `/mf:setup` to have been run first.
disable-model-invocation: true
allowed-tools: [Read, Write, Bash]
---

# /mf:prime — prime a project for the mindfunnel workflow

Set up the current project's root with a small committed agent-entry-point so that every contributor — with or without the `mindfunnel` plugin installed — sees a clean project-scoped `AGENTS.md` on clone:

- `AGENTS.md` — project-scoped stub (copied from `templates/project-AGENTS.md`), real file, **committed**. Maintainers extend it per-project as the project grows.
- `CLAUDE.md` — intra-repo symlink to `./AGENTS.md`, **committed**. Explicit Claude Code compatibility.
- `PROJECT.md` — real file, empty by default, **committed**. Holds project-specific deep context.

**Nothing per-project points into `~/.mindfunnel/` anymore.** The maintainer's user-global engineering style (`~/.mindfunnel/AGENTS.md`) is loaded independently via the `~/.claude/CLAUDE.md` / `~/.codex/instructions.md` symlinks that `/mf:setup` manages; it is not conflated with each project's `AGENTS.md`. Likewise, `SOUL.md` and `USER.md` are user-global files reached via `~/.claude/` and `~/.codex/` symlinks and are never stamped into a project.

Run **once per project**, from the project root. Idempotent: re-running after the upgrade cleans up legacy pre-0.3.0 symlinks and legacy `.gitignore` lines automatically.

## Important

1. **Run from the project root.** The skill writes into the current working directory. Confirm with `pwd` before acting if there's any doubt.
2. **Never overwrite a pre-existing regular file.** A hand-authored `./AGENTS.md` or `./CLAUDE.md` always wins over the stub; leave it alone and flag in the report.
3. **`~/.mindfunnel/` must already be set up.** If it isn't, stop and tell the user to run `/mf:setup` first. (The stub template lives inside the plugin, not in `~/.mindfunnel/`, but `/mf:setup` is still the prerequisite for the rest of the workflow.)
4. **`.gitignore` edits are minimal, targeted, and one-way.** `/mf:prime` strips `AGENTS.md` and `CLAUDE.md` lines from `.gitignore` if they're there (required — leaving them would prevent the new committed files from staging). It does **not** touch the legacy `SOUL.md` line (harmless, orthogonal to this change).

## Instructions

### Step 1: Verify `~/.mindfunnel/` is ready

```bash
[ -r "$HOME/.mindfunnel/AGENTS.md" ] && echo ready || echo missing
```

If missing, stop with:

> `~/.mindfunnel/` isn't set up yet. Run `/mf:setup` first, then re-run `/mf:prime`.

Do not proceed.

### Step 2: Stamp `./AGENTS.md` from the stub

For `./AGENTS.md` in the cwd, classify and act:

- **regular file** (real content, possibly hand-authored) → leave alone. Do not overwrite under any circumstance. Flag in the report as "kept (existing hand-authored file)".
- **legacy symlink** pointing at `~/.mindfunnel/CLAUDE.md`, `~/.mindfunnel/AGENTS.md`, or local `./CLAUDE.md` → remove the symlink, then copy the stub.
- **absent** → copy the stub.
- **other symlink** (pointing somewhere unknown) → leave alone, flag, ask the user whether to replace. Only proceed on an explicit yes.

Shell form for the happy path:

```bash
if [ -L AGENTS.md ]; then
    target="$(readlink AGENTS.md)"
    case "$target" in
        "$HOME/.mindfunnel/CLAUDE.md"|"$HOME/.mindfunnel/AGENTS.md"|CLAUDE.md)
            rm -f AGENTS.md
            ;;
    esac
fi

if [ ! -e AGENTS.md ]; then
    cp "${CLAUDE_PLUGIN_ROOT}/templates/project-AGENTS.md" AGENTS.md
fi
```

### Step 3: Create the project-local `CLAUDE.md` symlink

`CLAUDE.md` is kept as an intra-repo symlink to `./AGENTS.md` for explicit Claude Code compatibility. The symlink is project-local (no user-path dependency), so git tracks it fine and every clone sees the same two-name alias.

- **absent** → `ln -s AGENTS.md CLAUDE.md`.
- **correct local symlink** (`readlink CLAUDE.md == AGENTS.md`) → no-op.
- **legacy symlink** pointing at `~/.mindfunnel/CLAUDE.md` or `~/.mindfunnel/AGENTS.md` → remove, then create the local symlink.
- **regular file** (hand-authored) → leave alone. Flag in the report.
- **other symlink** → leave alone, flag, ask before replacing.

```bash
if [ -L CLAUDE.md ]; then
    target="$(readlink CLAUDE.md)"
    case "$target" in
        AGENTS.md)                              ;;  # already correct
        "$HOME/.mindfunnel/CLAUDE.md"|"$HOME/.mindfunnel/AGENTS.md")
            rm -f CLAUDE.md
            ln -s AGENTS.md CLAUDE.md
            ;;
    esac
elif [ -e CLAUDE.md ]; then
    :   # hand-authored regular file — leave alone
else
    ln -s AGENTS.md CLAUDE.md
fi
```

### Step 4: Clean up a legacy `./SOUL.md` symlink

Earlier versions of `/mf:prime` (≤ 0.2.2) created `./SOUL.md` as a symlink to `~/.mindfunnel/SOUL.md`. Starting with 0.3.0, `SOUL.md` is user-global only (reachable via `~/.claude/SOUL.md` and `~/.codex/SOUL.md`, managed by `/mf:setup`) and should not live in the project root.

Remove the legacy symlink automatically — but **only** if it's exactly that known-safe symlink:

```bash
if [ -L SOUL.md ] && [ "$(readlink SOUL.md)" = "$HOME/.mindfunnel/SOUL.md" ]; then
    rm -f SOUL.md
    echo "Removed legacy SOUL.md symlink (pre-0.3.0 prime leftover)"
fi
```

Rules:

- If `./SOUL.md` is a **real file** — leave alone. The user authored it.
- If `./SOUL.md` is a **symlink to somewhere other than `~/.mindfunnel/SOUL.md`** — leave alone. Unknown target, unknown intent.
- If `./SOUL.md` is **absent** — no-op.

### Step 5: Touch `PROJECT.md` if absent

```bash
[ -e PROJECT.md ] || touch PROJECT.md
```

Never overwrite an existing `PROJECT.md`. If the project already has one, leave it alone.

### Step 6: Strip legacy `AGENTS.md` / `CLAUDE.md` entries from `.gitignore`

Earlier primings (≤ 0.2.x) added `AGENTS.md` and `CLAUDE.md` to the project's `.gitignore` because they used to be per-user symlinks. Under the new model they're committed files; those lines would prevent them from staging, so strip them.

This is the one and only forced `.gitignore` edit in `/mf:prime` and it exists to make the new model function.

```bash
if [ -f .gitignore ] && git rev-parse --git-dir >/dev/null 2>&1; then
    for f in AGENTS.md CLAUDE.md; do
        if grep -qx "$f" .gitignore; then
            # Strip the exact-match line in place.
            tmp="$(mktemp)"
            grep -vx "$f" .gitignore > "$tmp" && mv "$tmp" .gitignore
            echo "Removed $f from .gitignore (now committed under the new model)"
        fi
    done
fi
```

Leaves the `SOUL.md` line alone. It's harmless (guards against a future hand-authored project-local `SOUL.md` being committed by accident) and orthogonal to this change.

**Note:** this step only strips exact-match lines. It does not touch pattern entries (e.g. `*.md`, `AGENTS.*`) or lines with comments / trailing whitespace. If someone hand-edited the gitignore in a non-standard way, the line stays and the user can clean it up.

**This step does not `git rm --cached` anything.** If the project previously committed `AGENTS.md` or `CLAUDE.md` as broken symlinks (see troubleshooting below for the < 0.2.2 state), that's still the user's problem to untrack — a destructive history op.

### Step 7: Report

Emit a short summary, ≤ 10 lines. For each file / action:

- `AGENTS.md` — **created from stub** / **kept (existing file)** / **replaced legacy symlink**
- `CLAUDE.md` — **created** / **already correct** / **repointed from legacy** / **kept (hand-authored)**
- `SOUL.md` — **removed legacy symlink** / **absent (no-op)**
- `PROJECT.md` — **created empty** / **already present**
- `.gitignore` — **stripped AGENTS.md + CLAUDE.md** / **nothing to strip**

Skip lines that resolved to no-op.

## Examples

### Example 1: Clean project, first prime

```
AGENTS.md   created from stub
CLAUDE.md   created → AGENTS.md
PROJECT.md  created (empty)
```

### Example 2: Project already primed under 0.3.0, re-run

```
AGENTS.md   kept (existing file)
CLAUDE.md   already correct
PROJECT.md  present
Nothing to do.
```

### Example 3: Project primed under ≤ 0.2.2, re-run after upgrade

```
AGENTS.md   replaced legacy symlink with stub
CLAUDE.md   repointed from ~/.mindfunnel/CLAUDE.md → AGENTS.md
SOUL.md     removed legacy symlink (pre-0.3.0)
PROJECT.md  present
.gitignore  stripped AGENTS.md, CLAUDE.md (now committed; SOUL.md line left alone)
```

### Example 4: Project has a hand-authored `AGENTS.md`

```
AGENTS.md   kept (existing hand-authored file, 2.3 KB)
CLAUDE.md   created → AGENTS.md
PROJECT.md  present
.gitignore  stripped AGENTS.md, CLAUDE.md
```

The hand-authored `AGENTS.md` stays; the user gets to commit it under the new model.

## Troubleshooting

### Error: "`~/.mindfunnel/` isn't set up"

Run `/mf:setup` first. `/mf:prime` depends on the shared scaffolding existing (even though the stub it stamps lives inside the plugin, not in `~/.mindfunnel/`).

### Error: user accidentally said "yes" to replacing a real file

The old file is gone. Recover from git (`git show HEAD:AGENTS.md > AGENTS.md`) if possible. Otherwise, restore from backup or rewrite.

### The project's `AGENTS.md` / `CLAUDE.md` is a symlink pointing somewhere unexpected

That's an unusual setup — probably a different convention the user is following. **Ask**, don't replace blindly. The user may want to keep the existing symlink.

### Repo was primed under mindfunnel ≤ 0.2.1 and has `CLAUDE.md` / `AGENTS.md` committed as symlinks into `~/.mindfunnel/`

**Symptom:** `git ls-files` shows `CLAUDE.md` and `AGENTS.md` tracked in a repo primed by a very old `/mf:prime`. Other clones on other machines see dangling symlinks because `~/.mindfunnel/` doesn't exist there.

**Cause:** Versions 0.2.0 and 0.2.1 of `/mf:prime` only added `SOUL.md` to `.gitignore`, so `CLAUDE.md` and `AGENTS.md` got committed as broken-elsewhere symlinks.

**Solution (user-driven, never automated by `/mf:prime`):**

```fish
# in each previously-primed project root, after upgrading to 0.3.0:
git rm --cached CLAUDE.md AGENTS.md     # untrack the broken symlinks (keeps the on-disk files)
/mf:prime                                # stamps real AGENTS.md + intra-repo CLAUDE.md symlink, strips .gitignore lines
git add AGENTS.md CLAUDE.md .gitignore   # stage the real files and the .gitignore diff
git commit -m "mindfunnel: move to 0.3.0 split AGENTS.md model"
```

`git rm --cached` is deliberately NOT automated — untracking already-committed files is a destructive operation on shared history and wants explicit user intent.

## Anti-patterns

- **Don't run from anywhere but the project root.** Writes in the wrong cwd cause silent confusion later.
- **Don't replace a pre-existing non-symlink `AGENTS.md` or `CLAUDE.md` without explicit approval.** The user's hand-written file always wins over the stub.
- **Don't create `PROJECT.md` with placeholder content.** It's created empty on purpose; the user fills it in as the project develops. A non-empty default encourages copy-paste that never gets edited.
- **Don't add anything new to `.gitignore`.** `/mf:prime` only strips old entries under the new model; it never adds.
- **Don't auto-remove the legacy `SOUL.md` line from `.gitignore`.** It's harmless and touching a tracked file unprompted is out of scope beyond the forced AGENTS.md / CLAUDE.md cleanup.
- **Don't `git rm --cached` already-committed symlinks during prime.** That's a destructive operation on shared history — flag it, point the user at the troubleshooting entry, let them drive it.
- **Don't auto-run `/mf:setup`** if `~/.mindfunnel/` is missing. Ask the user; doing it silently hides the coupling.
- **Don't create a project-root `SOUL.md` or `USER.md`.** Those are user-global; `/mf:setup` manages them in `~/.claude/` and `~/.codex/`. Stamping them per-project was the pre-0.3.0 behaviour for `SOUL.md` and is no longer correct — see Step 4 for the legacy cleanup.
- **Don't symlink `AGENTS.md` into `~/.mindfunnel/`.** The maintainer's user-global engineering style is a separate file with a separate load path (`~/.claude/CLAUDE.md`); a project's `AGENTS.md` is a committed, project-scoped file owned by the project. Conflating them was the pre-0.3.0 design.
