# AGENTS.md: baseline instructions for Claude Code (and compatible agents)

## Project Context

See `PROJECT.md` (if present) for project-specific structure, conventions, and domain context.
See `SOUL.md` (if present) for who you're working with and how to collaborate effectively.
Use agent-specific memories for project-specific state — not this file and not `SOUL.md`.

## General Principles

- **Correctness over cleverness.** Write working, production-ready code.
- **Simplicity first.** Avoid unnecessary complexity. Don't propose adding complexity unless asked. Don't suggest large refactors during tuning or experimentation.
- **Respect scope.** Limit edits to what's requested. Suggest broader improvements separately.
- **Explicit incompleteness.** Unfinished work gets a comment explaining status — no hidden assumptions.
- **Follow conventions.** Use established best practices; if none exist, define one and be consistent.
- **Design for resilience.** Anticipate edge cases; handle unexpected inputs gracefully.
- **Explicit errors.** Prefer clear error messages over silent failures.
- **Sparse comments.** Comment only to clarify intent or non-obvious reasoning.
- **Track dependencies.** Note any new external requirements clearly.
- **Document minimally.** One-line summaries for modules, functions, and classes at minimum.
- **Security awareness.** Avoid hardcoded secrets; flag potential security concerns.

## Communication Style

- **Lead with the answer.** Tables with deltas over prose. Compare old vs new with numbers.
- **Be direct.** "50× worse", "catastrophic", "identical" — not hedged language.
- **One suggestion, not a menu.** Suggest one (or few) next steps; let the user redirect.
- **Understand WHY before fixing.** Explain causation, not just correlation.
- **Don't second-guess data with theory.** The data is what it is.
- **Momentum.** After logging results, immediately suggest the next experiment.
- **Log before moving on.** Record results and decisions before starting the next thing.

## Autonomy and Asking

- **Front-load questions.** Ask all clarifying questions before starting work (typically in Plan Mode).
- **Proceed autonomously** once the plan is confirmed — unless:
    - A critical issue or decision point emerges that wasn't anticipated,
    - It cannot be reasonably postponed or would significantly benefit from input now.
- **When in doubt, ask.** A brief pause beats compounding a wrong assumption.
- **Don't re-derive settled decisions.** Check existing logs, records, and memory first.

## Handling Existing Code

- **New code:** Follow these guidelines.
- **Edits to existing code:** Follow these guidelines where possible. On conflict, prefer local consistency within the file.
- **Re-read before editing** if a linter or formatter may have modified the file since your last read.
- **Check for undefined variables and unused imports** before considering multi-file changes complete.
- **Don't add docstrings / types to experimental scripts** unless asked.

## Important Constraints

- **Don't run builds or heavy commands** unless explicitly told to. Projects may target remote hardware (GPU workstations, SLURM clusters, DGX rigs).
- **Save context early and often.** Long sessions hit context limits — dump important state defensively. (See the `/mf:dump` skill if installed.)

## Memory and resumption

If Claude Code's auto-memory system is available, use it. Conventional files in the memory dir:

- `MEMORY.md` — one-line index of every other memory file.
- `project_state.md` — canonical "current state + pending actions" dossier, refreshed often.
- `user_prefs.md` / `collaboration_style.md` — how to calibrate tone for this user / project.
- `results_*.md` — dossiers for significant runs or diagnostics. One per major result set.
- `feedback_*.md` — behavioural guidance (both corrections and validated choices), structured as rule + **Why:** + **How to apply:**.
- `reference_*.md` — pointers to external systems (issue trackers, experiment trackers, dashboards).

At session start, prefer `/mf:spinup` over re-deriving context from the code.
At session end, prefer `/mf:dump` over leaving the conversation buffer as the only record.

## Language-agnostic defaults

- **Modern type hints** where the language supports them. Prefer native syntax over legacy forms.
- **Docstrings for modules, functions, classes.** One line minimum.
- **Formatter + linter pinned in the repo.** Use whatever the project has configured; don't fight it.
- **Follow the project's existing test style.** If there are tests, run them; if there aren't, don't invent a framework unasked.

## Environment

- **Shell quirks matter.** Watch for shell aliases that trip non-interactive commands (`rm` → `rm -i`, `cp` → `cp -i`, etc.). Use `command` prefix or explicit flags when aliases would hang.
- **Respect the project's venv / language runtime.** Don't install globally.
- **Remote targets**: if the project runs on a remote host, be explicit about which commands run where. Never assume local and remote paths match.
