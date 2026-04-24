# PROJECT.md: Project-specific context

> This file is dropped as an empty stub by `/mf:prime`. The structure
> below is a commented-out template — uncomment sections as the
> project takes shape. Unlike `SOUL.md` (user-global, never committed),
> this file _is_ checked into source control: it belongs to the
> project, not to you.

## What this project is

<!-- 1–3 sentences: the high-level goal, the problem it solves, the
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

## How to run / test / lint

<!-- The exact commands. Every agent asks for these at the start of
     every session — committing them once saves the churn. -->

<!-- Example:
  - Run: `python -O src/main.py`
  - Tests: `pytest tests/` from the repo root
  - Lint: `ruff check src/ && ruff format --check src/`
  - Typecheck: `pyright src/`
-->

## Conventions

<!-- Things the agent would get wrong if it assumed generic defaults. -->

<!-- Examples:
  - Run all Python with `python -O`.
  - Config files are in `configs/`, one per experiment.
  - Outputs go to `results/<experiment_name>/<timestamp>/`.
  - Never commit anything under `data/`, `models/`, or `logs/`.
-->

## Known pitfalls

<!-- Gotchas that have burned contributors — the "I wish someone had
     told me" list. -->

<!-- Example:
  - The X environment silently swallows NaN rewards at step 0. Always
    assert finite rewards in the first smoke test.
  - `seed=0` triggers a known degenerate init in module Y; use any
    non-zero seed for reproducibility experiments.
-->

## What not to touch

<!-- Generated files, vendored code, third-party patches. -->

<!-- Example:
  - `src/vendored/`: upstream snapshot. Patch via the overlay in
    `patches/`, don't edit in place.
  - `src/_generated/`: regenerated from `schema.proto` — edits will be
    overwritten on next build.
-->

## External systems

<!-- Issue trackers, experiment trackers, dashboards, storage buckets. -->

<!-- Example:
  - Bugs: GitHub Issues at <org>/<repo>/issues
  - Experiments: Weights & Biases at <entity>/<project>
  - Dashboards: <grafana-url>
-->

## Glossary / domain shorthand

<!-- Domain terms or internal jargon that a stranger wouldn't know. -->

<!-- Example:
  - "FKP" = first-K-consecutive plateau step (a sample-efficiency metric)
  - "the plain variant" = the model without the X augmentation
  - "the headline metric" = terminal reward averaged over the last 10%
-->

## Current state (short)

<!-- 1–3 sentences for what's in flight right now. Most of the state
     should live in the agent's per-project memory directory (see
     `USER.md` or the `mindfunnel` plugin), not here — but a pointer to
     "we're working on X" is useful for humans. -->
