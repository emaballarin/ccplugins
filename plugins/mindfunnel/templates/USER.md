# USER.md — User-specific preferences

> Copy this to `~/.mindfunnel/USER.md` (the `mindfunnel` installer does
> that automatically if none exists) and fill in the sections you want
> the agent to know about. This file is user-global, not project-
> specific, and not checked into source control. `AGENTS.md` points here
> for anything personal to the current maintainer.
>
> The installer also creates `~/.claude/USER.md` and `~/.codex/USER.md`
> as symlinks to `~/.mindfunnel/USER.md` so the same file is reachable
> from either agent's dotdir.

## Memory system usage

<!-- Do you use `mindfunnel` for session-persistent memory? Where does
     per-project memory live? Give the explicit path so the agent
     doesn't have to re-derive it every session. -->

<!-- Example:
  This user relies on `mindfunnel` (`/mf:dump`, `/mf:spinup`,
  `/mf:prime`, `/mf:setup`). Per-project memory lives at
  `~/.claude/projects/<slug>/memory/` where `<slug>` is the project CWD
  with every `/` replaced by `-`.
-->

## Shell environment

<!-- Shell, alias quirks, anything that could make a plain command hang
     or behave unexpectedly. -->

<!-- Example:
  - Shell is Fish. `rm` is aliased to interactive mode; use `rm -f` in
    scripts so prompts don't stall the session.
-->

## Python conventions

<!-- Default Python version, run flags, preferred layout, formatter /
     linter paths, personally-preferred libraries. -->

<!-- Example:
  - Python 3.14+, run with `python -O`, typically from `src/`.
  - PyTorch is the default for tensors / differentiable programming / ML.
  - Modern native type-hint syntax: `tuple[int, float]`, `int | None`,
    `collections.abc` imports.
  - Ruff with `~/ruffconfigs/default/ruff.toml`.
  - Succinct docstrings on all modules / functions / classes.
  - Personal libraries: `simple_parsing`, `safetensors`.
-->

## Codex / multi-agent compatibility

<!-- Only relevant if you use more than one agent in parallel (Claude
     Code + Codex, etc.). Describe how instructions and hooks are
     bridged across them. -->

<!-- Example:
  - `~/.codex/instructions.md`, `~/.codex/SOUL.md`, `~/.codex/USER.md`
    are symlinks into `~/.mindfunnel/`.
  - `~/.codex/hooks` is a symlink to `~/.claude/hooks` so both agents
    share the same hook scripts.
  - Manual fallback when hooks don't fire: run
    `reorder-python-imports --py314-plus <file>` then
    `ruff format <file>` then `ruff check <file>`.
-->
