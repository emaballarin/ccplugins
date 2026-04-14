# mindfunnel

Funnel a messy, high-bandwidth Claude Code session into a narrow, persistent memory channel — then spin it back up at the start of the next session. Four slash-command skills and a tiny amount of project scaffolding. Nothing else.

Designed for researchers, power users, and anyone running multi-day engagements where context matters more than compute. Works on any project on any machine with Claude Code installed.

## Install

From any Claude Code session:

```
/plugin marketplace add emaballarin/ccplugins
/plugin install mf@ccplugins
```

That's it. After installation, four skills are available under the `mf` namespace: `/mf:setup`, `/mf:prime`, `/mf:dump`, `/mf:spinup`.

## The four skills

| Skill         | When                  | What it does                                                                                                                                              |
| ------------- | --------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `/mf:setup`   | Once per machine      | Seed `~/.mindfunnel/` with editable scaffolding: `AGENTS.md`, `SOUL.md`, `PROJECT.md.example`, and a `CLAUDE.md → AGENTS.md` symlink. Never overwrites.   |
| `/mf:prime`   | Once per project      | In the current project root: symlink `CLAUDE.md` / `AGENTS.md` / `SOUL.md` into `~/.mindfunnel/`, touch an empty `PROJECT.md`, `.gitignore` `SOUL.md`.    |
| `/mf:spinup`  | Start of each session | Read auto-memory in priority order and emit a tight "where we are + next action" brief. **Read-only** — stops and waits for direction.                    |
| `/mf:dump`    | End / mid-session     | Consolidate the session's non-derivable state into `~/.claude/projects/<slug>/memory/`. Updates `MEMORY.md`. Rarely proposes `SOUL.md` / `AGENTS.md` edits.|

## Typical rhythm

```
Machine setup (once):     /mf:setup
                          then edit ~/.mindfunnel/SOUL.md

New project (once):       cd <project-root>
                          /mf:prime

Day 1:                    /mf:spinup → work → /mf:dump → close
Day 2:                    /mf:spinup → work → /mf:dump → close
Day N:                    /mf:spinup → work → /mf:dump → close
```

After the first few cycles the memory stabilises into a compact set of files that make each subsequent `/mf:spinup` fast and reliable.

## What sits where

- **`~/.mindfunnel/`** — shared, machine-wide. Your `SOUL.md` (who you are, private, gitignored), baseline `AGENTS.md` (project-agnostic engineering guidelines), and a `PROJECT.md.example` you can crib from. `/mf:setup` creates this; nothing else touches it.
- **Project root** — symlinks into `~/.mindfunnel/` for `CLAUDE.md`, `AGENTS.md`, `SOUL.md`, plus a real, project-local `PROJECT.md`. `/mf:prime` creates these; the project owns `PROJECT.md`.
- **`~/.claude/projects/<slug>/memory/`** — Claude Code's auto-memory directory, one per project. Owned by Claude Code, not by this plugin. `/mf:dump` writes into it; `/mf:spinup` reads from it. The plugin does not manage its lifecycle — memory survives plugin uninstalls and updates.

## Customise

### Fill in `SOUL.md`

After `/mf:setup`, open `~/.mindfunnel/SOUL.md` and replace the example scaffolding with real content:

- **Who you are** — name, role, domain.
- **How you work** — fast-iteration vs. deliberate, tolerance for sycophancy, communication preferences.
- **What to avoid** — specific anti-patterns you've hit before.
- **Technical environment** — shell, venvs, cluster paths, internal libraries.

`SOUL.md` is intentionally *not* checked into source control by `/mf:prime` (it gets added to per-project `.gitignore`). It's your private trait file and shapes every session on every project.

### Fill in `PROJECT.md` per project

After `/mf:prime`, open the (empty) `PROJECT.md` in the project root and capture project-specific structure, conventions, domain context, and glossary. Unlike `SOUL.md`, `PROJECT.md` *is* checked in — it belongs to the project.

## Uninstall

```
/plugin uninstall mf@ccplugins
```

This removes the plugin skills from Claude Code. It does **not** touch `~/.mindfunnel/`, `~/.claude/projects/*/memory/`, or any project-local files — your memory, your scaffolding, and your `SOUL.md` edits all survive the uninstall.

To also remove the machine-wide scaffolding:

```
rm -rf ~/.mindfunnel/
```

Per-project symlinks created by `/mf:prime` become dangling after that — clean them up manually in each affected project root if you care.

## Design notes

- **Skills are generic by design.** They reference Claude Code's auto-memory system (which is global) and the `/mf:prime` convention (which ships in this plugin). No domain-specific vocabulary, no single-project assumptions.
- **Personal customisation lives in `SOUL.md`.** The skills don't need to know who you are; `SOUL.md` tells them.
- **`disable-model-invocation: true`** on all four skills. These are user-triggered rituals, never autonomous behaviour. Claude won't decide to dump state or prime a project without an explicit `/mf:...` invocation.
- **Self-contained.** Templates live inside the plugin at `templates/`. `/mf:setup` copies them to `~/.mindfunnel/` on first run. No separate install script, no cloning, no `chmod`.
- **Idempotent everywhere.** Re-running `/mf:setup` or `/mf:prime` after the fact is safe. Destructive operations (replacing a real file) always ask first.

## Links

- Marketplace: [emaballarin/ccplugins](https://github.com/emaballarin/ccplugins)
- Changelog: [CHANGELOG.md](CHANGELOG.md)

## License

MIT. See [LICENSE](../../LICENSE) at the marketplace root.
