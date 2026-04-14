# Changelog

All notable changes to the `mf` (mindfunnel) plugin are documented here.
This project adheres to [Semantic Versioning](https://semver.org/).

## 0.2.2

- `/mf:prime` now adds `SOUL.md`, `CLAUDE.md`, **and** `AGENTS.md` to `.gitignore`. Previously only `SOUL.md` was excluded, which let `CLAUDE.md` and `AGENTS.md` get committed as symlinks pointing into `~/.mindfunnel/` — a per-user, per-machine path that doesn't exist for anyone else's clone. `PROJECT.md` stays committed as before; it's the only real, project-owned file of the four.
- **User migration required** for projects primed with 0.2.0 or 0.2.1. Existing primed repos already have `CLAUDE.md` and `AGENTS.md` tracked. After upgrading, in each such repo:

    ```fish
    # top up .gitignore (or just re-run /mf:prime, which does this now):
    printf 'CLAUDE.md\nAGENTS.md\n' >> .gitignore

    # untrack the committed symlinks without deleting them on disk:
    git rm --cached CLAUDE.md AGENTS.md

    git commit -m "mindfunnel: untrack per-machine symlinks"
    ```

    `git rm --cached` is deliberately NOT automated by `/mf:prime` — untracking already-committed files is a destructive operation on shared history and wants explicit user intent. Re-running `/mf:prime` on a <= 0.2.1 repo is safe: it will top up `.gitignore` with the missing entries, but won't touch the index.

## 0.2.1

- `/mf:dump` and `/mf:spinup` are now model-invocable. `/mf:dump` can fire autonomously at natural checkpoints or approaching context saturation; `/mf:spinup` has a narrow trigger (explicit resume / catch-up / "where were we" phrasing only) to avoid bloating trivial asks with a brief. `/mf:setup` and `/mf:prime` remain user-only — both have side effects that want deliberate invocation.
- `/mf:spinup` step 1 no longer shells out to compute the memory-dir slug. The path is deterministic, so the skill now reads `MEMORY.md` directly at the conventional location and only falls back to dir-probing on ENOENT.

## 0.2.0

- `/mf:prime` no longer touches `~/.claude/`. Removed the legacy global `~/.claude/SOUL.md` convenience symlink; the skill's scope is now strictly the current project root and `~/.mindfunnel/`.

## 0.1.0 — initial release

- `/mf:setup` — one-time bootstrap of `~/.mindfunnel/` from bundled templates.
- `/mf:prime` — prime the current project with symlinks to `~/.mindfunnel/` and a project-local `PROJECT.md`.
- `/mf:dump` — consolidate the current session's non-derivable state into Claude Code's auto-memory dir.
- `/mf:spinup` — read the auto-memory at the start of a new session and emit a tight "where we are + next action" brief.
