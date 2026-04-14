# Changelog

All notable changes to the `mf` (mindfunnel) plugin are documented here.
This project adheres to [Semantic Versioning](https://semver.org/).

## 0.1.0 — initial release

- `/mf:setup` — one-time bootstrap of `~/.mindfunnel/` from bundled templates.
- `/mf:prime` — prime the current project with symlinks to `~/.mindfunnel/` and a project-local `PROJECT.md`.
- `/mf:dump` — consolidate the current session's non-derivable state into Claude Code's auto-memory dir.
- `/mf:spinup` — read the auto-memory at the start of a new session and emit a tight "where we are + next action" brief.
