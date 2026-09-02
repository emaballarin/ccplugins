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
  - Ruff for formatting and linting.
  - Default libraries: `simple_parsing` for config, `safetensors` for I/O.
-->

<!-- State each convention once. Anything that holds for every project —
     docstring policy, error handling, naming — belongs in `AGENTS.md`;
     repeating it here inflates it and gives it two places to go stale. -->

## Personal libraries and compute

<!-- Internal packages and private indexes, then where work actually
     runs. Both are facts about the machine, so they live here rather
     than in `SOUL.md`. -->

<!-- Example:
  - `<your-lib>`: personal library, at `<private-index-url>`.
  - Cluster: `<hostname>:/<path>`. Use `srun` for Python in job scripts.
  - Which jobs run where is set by cost, not kind — see `AGENTS.md`
    §Important constraints.
-->

## Other agents — how each reaches this baseline

<!-- Only relevant if you run more than one agent against these files.
     One row per agent, naming the path `AGENTS.md` is auto-loaded as.
     Keep it a table: it is the contract, and a wrong row sends an agent
     looking for a file that is not there. -->

<!-- Example:
  | Agent       | `AGENTS.md` is auto-loaded as        |
  | ----------- | ------------------------------------ |
  | Claude Code | `~/.claude/CLAUDE.md`                |
  | Codex       | `~/.codex/instructions.md`           |

  Every entry is a symlink into `~/.mindfunnel/`, so one edit at the real
  file propagates to all of them. Check with `stat -Lc %i` rather than by
  filename if that ever looks doubtful. An agent with no user-global
  instructions file needs a short pointer file instead of a copy — a copy
  goes stale silently.
-->

## Formatting and linting

<!-- Name the directory holding the hook scripts and let it be the
     authority on what they run. Record only what the scripts cannot say
     themselves: which agent fires them on which event, which agents have
     no bridge at all, and any config path that is secretly a symlink to
     another. Pasting the commands here guarantees they drift. -->
