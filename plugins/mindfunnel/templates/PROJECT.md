# PROJECT.md: Project-specific context

> This file is created empty by `/mf:prime`. Edit it to capture
> project-specific structure, conventions, and domain context that would
> otherwise have to be re-explained in every session. Unlike SOUL.md, this
> file _is_ checked into source control — it belongs to the project, not to
> you.

## What this project is

<!-- 1-3 sentences: the high-level goal, the problem it solves, the
     deliverable. -->

## Source layout

<!-- A compact map of the repo. One line per directory that matters. -->

<!-- Example:
```
src/
├── foo.py           # entry point for X
├── bar/             # module for Y
└── lib/             # reusable utilities
scripts/             # standalone CLI wrappers
experiments/         # experimental configs (gitignored outputs)
```
-->

## Conventions

<!-- Things the agent would get wrong if it assumed generic defaults. -->

<!-- Examples:
  - Run all Python with `python -O`.
  - Config files are in `configs/`, one per experiment.
  - Outputs go to `results/<experiment_name>/<timestamp>/`.
  - Never commit anything under `data/`, `models/`, or `logs/`.
  - Test with `pytest tests/` from the repo root.
-->

## Glossary / domain shorthand

<!-- Domain terms or internal jargon that a stranger wouldn't know. -->

<!-- Example:
  - "FKP" = first-K-consecutive plateau step (a sample-efficiency metric)
  - "the plain variant" = the model without the X augmentation
  - "the headline metric" = terminal reward averaged over the last 10%
-->

## External systems

<!-- Issue trackers, experiment trackers, dashboards, storage buckets. -->

<!-- Example:
  - Bugs: GitHub Issues at <org>/<repo>/issues
  - Experiments: Weights & Biases at <entity>/<project>
  - Dashboards: <grafana-url>
-->

## Current state (short)

<!-- 1-3 sentences for what's in flight right now. Most of the state should
     live in the auto-memory dir (~/.claude/projects/<slug>/memory/), not
     here — but a pointer to "we're working on X" is useful for humans. -->
