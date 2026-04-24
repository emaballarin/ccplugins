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

| Skill        | When                  | What it does                                                                                                                                                                                                                                                                                                                                               |
| ------------ | --------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `/mf:setup`  | Once per machine      | Seed `~/.mindfunnel/` with editable scaffolding: `AGENTS.md`, `SOUL.md`, `USER.md`, `PROJECT.md.example`, a `CLAUDE.md → AGENTS.md` symlink, plus `~/.claude/{SOUL,USER}.md` and `~/.codex/{SOUL,USER}.md` symlinks so both agents reach the same source. Never overwrites.                                                                                |
| `/mf:prime`  | Once per project      | In the current project root: stamp a project-scoped `AGENTS.md` from the bundled stub (if absent), create a project-local `CLAUDE.md` symlink to `./AGENTS.md`, touch an empty `PROJECT.md`. All three are committed. Also cleans up legacy pre-0.3.0 symlinks into `~/.mindfunnel/` and strips stale `CLAUDE.md` / `AGENTS.md` entries from `.gitignore`. |
| `/mf:spinup` | Start of each session | Read auto-memory in priority order and emit a tight "where we are + next action" brief. **Read-only** — stops and waits for direction.                                                                                                                                                                                                                     |
| `/mf:dump`   | End / mid-session     | Consolidate the session's non-derivable state into `~/.claude/projects/<slug>/memory/`. Updates `MEMORY.md`. Rarely proposes `SOUL.md` / `AGENTS.md` / `USER.md` edits.                                                                                                                                                                                    |

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

- **`~/.mindfunnel/`** — shared, machine-wide. Your `SOUL.md` (who you are — private), baseline `AGENTS.md` (project-agnostic engineering guidelines), `USER.md` (per-machine preferences — shell, Python defaults, formatter paths, multi-agent hook bridges), and a `PROJECT.md.example` you can crib from. `/mf:setup` creates this; nothing else touches it.
- **`~/.claude/{SOUL,USER}.md` and `~/.codex/{SOUL,USER}.md`** — symlinks into the matching files in `~/.mindfunnel/`. Give Claude Code and Codex a stable pointer to the same user-global personal content. `/mf:setup` creates these; they are the only files the plugin writes outside `~/.mindfunnel/` and the current project root.
- **Project root** — a committed project-scoped `AGENTS.md` (real file, stamped from the bundled stub), a committed intra-repo `CLAUDE.md` symlink pointing at `./AGENTS.md`, and a real, project-local `PROJECT.md`. All three are owned by the project and checked into source control. Nothing here points into `~/.mindfunnel/` — the maintainer's user-global engineering style is loaded separately via `~/.claude/CLAUDE.md`. `SOUL.md` and `USER.md` are deliberately **not** stamped into projects — they're user-global.
- **`~/.claude/projects/<slug>/memory/`** — Claude Code's auto-memory directory, one per project. Owned by Claude Code, not by this plugin. `/mf:dump` writes into it; `/mf:spinup` reads from it. The plugin does not manage its lifecycle — memory survives plugin uninstalls and updates.

## Customise

### Fill in `SOUL.md`

After `/mf:setup`, open `~/.mindfunnel/SOUL.md` and replace the example scaffolding with real content:

- **Who you are** — name, role, domain.
- **How you work** — fast-iteration vs. deliberate, tolerance for sycophancy, communication preferences.
- **What to avoid** — specific anti-patterns you've hit before.
- **Locale & conventions** — language, date / time format, locale defaults.
- **Technical environment** — personal libraries, compute environment, where heavy commands belong.

`SOUL.md` is intentionally _not_ stamped into any project by `/mf:prime`. It lives user-global at `~/.mindfunnel/SOUL.md`, reachable via `~/.claude/SOUL.md` and `~/.codex/SOUL.md` (both managed by `/mf:setup`). Your private trait file shapes every session on every project without ever leaving your machine. The maintainer's user-global `~/.mindfunnel/AGENTS.md` (project-agnostic engineering style) is loaded the same way via `~/.claude/CLAUDE.md` and `~/.codex/instructions.md` — also user-global, never stamped into projects. Each project's own `./AGENTS.md` is a separate, project-scoped file, committed like any other source file.

### Fill in `USER.md`

Also after `/mf:setup`, open `~/.mindfunnel/USER.md` and capture what's specific to this machine and user rather than to you as a collaborator:

- **Memory system usage** — whether you use mindfunnel itself, and the explicit auto-memory path so the agent doesn't have to re-derive it.
- **Shell environment** — shell, any alias quirks that could stall a command.
- **Language conventions** — default Python version, run flags, preferred layout, formatter / linter paths, personally-preferred libraries.
- **Multi-agent hook bridges** — relevant if you run Claude Code + Codex in parallel and share hooks / instructions between them.

`USER.md` complements `SOUL.md`: `SOUL.md` describes _you_, `USER.md` describes _your machine_. Both are user-global and symlinked identically — `/mf:setup` creates `~/.claude/{SOUL,USER}.md` and `~/.codex/{SOUL,USER}.md` pointing at `~/.mindfunnel/`, so both agents reach the same source of truth. Neither is ever stamped into a project by `/mf:prime`.

### Fill in `PROJECT.md` per project

After `/mf:prime`, open the (empty) `PROJECT.md` in the project root and capture project-specific structure, conventions, domain context, and glossary. `PROJECT.md` is checked in alongside the project-scoped `AGENTS.md` stub and the intra-repo `CLAUDE.md` symlink — all three belong to the project and are committed together.

## Uninstall

```
/plugin uninstall mf@ccplugins
```

This removes the plugin skills from Claude Code. It does **not** touch `~/.mindfunnel/`, `~/.claude/projects/*/memory/`, or any project-local files — your memory, your scaffolding, and your `SOUL.md` / `USER.md` edits all survive the uninstall.

To also remove the machine-wide scaffolding:

```
rm -rf ~/.mindfunnel/
rm -f ~/.claude/SOUL.md ~/.claude/USER.md ~/.codex/SOUL.md ~/.codex/USER.md
```

Per-project files created by `/mf:prime` (the committed `AGENTS.md` stub, the intra-repo `CLAUDE.md` symlink, and `PROJECT.md`) are owned by each project and stay put after uninstall — they're just regular checked-in source files at that point. The four `SOUL.md` / `USER.md` symlinks in `~/.claude/` and `~/.codex/` would otherwise become dangling once `~/.mindfunnel/` is gone; the `rm -f` above clears them.

## Design notes

- **Skills are generic by design.** They reference Claude Code's auto-memory system (which is global) and the `/mf:prime` convention (which ships in this plugin). No domain-specific vocabulary, no single-project assumptions.
- **Personal customisation lives in `SOUL.md` and `USER.md`.** The skills don't need to know who you are or which machine you're on; `SOUL.md` describes _you_ (role, workflow, preferences), `USER.md` describes _your machine_ (shell, toolchain, paths). Both are user-global — never stamped into projects, never committed anywhere.
- **Side-effect skills stay user-only.** `/mf:setup` and `/mf:prime` set `disable-model-invocation: true` — both mutate the filesystem (writing `~/.mindfunnel/`, creating symlinks in a project root), and the user always drives them. `/mf:dump` and `/mf:spinup` are model-invocable: dump can fire at natural checkpoints or approaching context saturation, and spinup has a narrow trigger (explicit resume / catch-up phrasing only) so it won't bloat trivial asks with a brief.
- **Self-contained.** Templates live inside the plugin at `templates/`. `/mf:setup` copies them to `~/.mindfunnel/` on first run. No separate install script, no cloning, no `chmod`.
- **Idempotent everywhere.** Re-running `/mf:setup` or `/mf:prime` after the fact is safe. Destructive operations (replacing a real file) always ask first.

## Links

- Marketplace: [emaballarin/ccplugins](https://github.com/emaballarin/ccplugins)
- Changelog: [CHANGELOG.md](CHANGELOG.md)

## License

MIT. See [LICENSE](../../LICENSE) at the marketplace root.
