# PROJECT.md: Project-specific context

## What this project is

`ccplugins`: a personal Claude Code plugin marketplace, developed in the
open. Six plugins: `mf` (mindfunnel), `ccsci` (ccscience), `ar`
(autoresearch), `tml` (tuneml), `ws` (whetstone), `ccbar` (ccbar).
`ccbar` is the one function-hook plugin: TypeScript hooks, no skills.

## Source layout

```
.claude-plugin/marketplace.json   # the catalogue: one entry per plugin
plugins/<descriptive-name>/       # one plugin each
├── .claude-plugin/plugin.json    # short `name` + `version`
├── skills/<skill>/SKILL.md       # auto-discovered — no "skills" key in plugin.json
├── agents/ references/ templates/
└── README.md CHANGELOG.md [LICENSE] [NOTICE]
plugins/ccbar/                    # function hooks instead of skills:
├── hooks/hooks.json + *.ts(x)    #   the hooks module and its helpers
├── types/index.d.ts              #   its $.state contract
└── tests/*.test.ts(x)            #   run by `claude plugin test`, not CI
tests/                            # Tier-1 static + Tier-2 behavioural validation
docs/roadmap.md                   # deferred and parked ideas
```

## How to run / test / format

- Tests, from the repo root (Python 3.14+ is the declared floor; CI pins
  it): `pip install -r tests/requirements.txt && python -m pytest tests/ -q`.
  What each module checks: `tests/README.md`.
- `ccbar` (TypeScript, run by Claude Code), not in CI and part of every
  `ccbar` release:

    ```
    claude plugin validate plugins/ccbar
    claude plugin test plugins/ccbar
    tsc -p plugins/ccbar
    ```

    `tsc` needs the typings Claude Code lays in `.claude-plugin/types/` when it
    loads the folder (`claude --plugin-dir plugins/ccbar`).

- Format: `~/bin/hyperformat .` (maintainer-local) — the house formatter;
  never hand-roll its steps. Its import reorder and `ruff format` can undo each
  other, so "N files reformatted" may net to no change: check `git diff --stat`.

## Conventions

- **Descriptive directory, short plugin `name`** (`mindfunnel` → `mf`).
  Everything user-facing uses the short name, including a plugin's state
  dir (`./.ar/`, `./.tml/`).
- **A release is** version bump + CHANGELOG entry + every doc restating the
  changed fact (plugin README, root README, `plugin.json` description,
  marketplace entry). Grep for restatements and check `git status` for
  scratch files before calling it done. Tier-1 enforces `plugin.json`
  version == newest CHANGELOG heading.
- **Before asking for commit approval**, state the install impact: is there
  a migration path, do existing installs need manual action?
- **Coordinated bump** — every other plugin up one patch, with a
  "Housekeeping — coordinated marketplace version alignment alongside …
  No skill logic changed." entry — happens only on explicit request; adding
  or removing a plugin never triggers one. When a change could warrant one,
  ask at commit approval; never silently omit it.
- **Bump what was released**: a plugin new in the same commit is not bumped
  again.
- **New plugin**: `plugins/` dir, marketplace entry, root README table row,
  layout-tree stanza, install line, license-paragraph mention.
- **Retiring a plugin**: one patch bump recording the supersession, committed
  alone, then the removal commit.
- Unrelated changes go in separate commits.

## Known pitfalls

- `ccbar` stands on the function-hook API, which is early access and moves
  between Claude Code releases; it also sits behind a rollout switch, so an
  install can load nothing. Re-run the three `ccbar` checks after a Claude Code
  update. The validator's one non-obvious rule: `$` is only ever spelled
  `$.noun.method(…)` where it is called (`read`/`update` excepted), never
  stored, passed or returned.
- Nothing checks the root README's prose, layout tree or license paragraph:
  grep it on every plugin or skill change.
- `test_referenced_paths.py` checks that a referenced file exists, not that
  its contents name the right plugin. After copying between plugins, grep
  for the source plugin's name.
- `§` section anchors are unchecked; prefer item references (`C7`), which
  `test_evidence_grades.py` resolves.
- `plugins/mindfunnel/templates/AGENTS.md` drifts behind the live
  `~/.mindfunnel/AGENTS.md`: `tests/test_template_drift.py` fails locally
  until they are byte-identical (it skips where no live file exists, as in
  CI), so run the suite before an `mf` release. Sync live →
  shipped: copy `AGENTS.md` verbatim; never copy `SOUL.md` / `USER.md`
  (personal, and this repo is public) — port only the generic patterns of
  their live edits, as placeholder examples, when warranted.
- CHANGELOG heading date formats are mixed (`— YYYY-MM-DD` dominates) and
  unvalidated.

## What not to touch

- Released CHANGELOG entries: history, not amended to match the present.
- Python-3.14-only syntax in kernels is correct by policy; don't "fix" it.
