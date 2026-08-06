# ccplugins

Emanuele Ballarin's personal Claude Code plugin marketplace.

## Install the marketplace

From any Claude Code session:

```
/plugin marketplace add emaballarin/ccplugins
```

Then install individual plugins with `/plugin install <name>@ccplugins`.

## Plugins

| Name    | Description                                                                                                                                                                                                                                                                                                                                                                                         | Docs                                                   |
| ------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------ |
| `mf`    | **mindfunnel** — project-agnostic session management. Five skills (`/mf:setup`, `/mf:prime`, `/mf:dump`, `/mf:spinup`) that funnel session state into auto-memory and back, plus `/mf:author` — the reference for writing the documents an agent reads.                                                                                                                                                                                                                         | [plugins/mindfunnel](plugins/mindfunnel/README.md)     |
| `ccsci` | **ccscience** — research & scientific-computing skills adapted from Claude Science: literature-review, pdf-explore, the figure-style / figure-composer / paper-narrative trilogy, canvas-design, doc-coauthoring, web-artifacts-builder, plus the `computational-scientist` and `deep-researcher` subagents.                                                                                        | [plugins/ccscience](plugins/ccscience/README.md)       |
| `ar`    | **autoresearch** — an autonomous experiment loop for any numeric objective. Five skills (`/ar:start`, `/ar:resume`, `/ar:status`, `/ar:report`, `/ar:stop`) that propose one change, measure it, and keep it only if it beats the measured noise floor.                                                                                                                                             | [plugins/autoresearch](plugins/autoresearch/README.md) |
| `tml`   | **tuneml** — the scientific method for tuning _and_ the speed↔quality frontier, in one place. Five skills (`/tml:audit`, `/tml:plan`, `/tml:round`, `/tml:analyze`, `/tml:review`) that read a pipeline, fix an operating point and a step budget, design experiments with scientific/nuisance/fixed hyperparameters, and return variance-aware adopt verdicts. Replaces the former `parml` plugin. | [plugins/tuneml](plugins/tuneml/README.md)             |
| `ws`    | **whetstone** — sharpen the thinking before the work. One user-only skill (`/ws:grill`) that interviews a plan or decision in rounds over its design tree, asking the whole settled frontier at a time, and closes only when nothing is left silently assumed.                                          | [plugins/whetstone](plugins/whetstone/README.md)       |

## Install a plugin

```
/plugin install mf@ccplugins
/plugin install ccsci@ccplugins
/plugin install ar@ccplugins
/plugin install tml@ccplugins
/plugin install ws@ccplugins
```

## Layout

```
ccplugins/
├── .claude-plugin/
│   └── marketplace.json
├── .github/workflows/validate.yml        # CI: Tier-1 static validation
├── tests/                                # pytest Tier-1 suite (+ requirements.txt)
├── README.md                             # this file
├── LICENSE                               # MIT
└── plugins/
    ├── mindfunnel/                          # plugin name: mf
    │   ├── .claude-plugin/plugin.json
    │   ├── README.md  CHANGELOG.md  NOTICE
    │   ├── skills/{setup,prime,dump,spinup,author}/SKILL.md
    │   ├── references/{ledger,skill-mechanics}.md
    │   └── templates/{AGENTS,project-AGENTS,PROJECT,SOUL,USER}.md
    ├── ccscience/                           # plugin name: ccsci
    │   ├── .claude-plugin/plugin.json
    │   ├── README.md  CHANGELOG.md  LICENSE  # Apache-2.0
    │   ├── agents/{computational-scientist,deep-researcher}.md
    │   └── skills/{literature-review,pdf-explore,figure-style,
    │               figure-composer,paper-narrative,canvas-design,
    │               doc-coauthoring,web-artifacts-builder}/
    ├── autoresearch/                        # plugin name: ar
    │   ├── .claude-plugin/plugin.json
    │   ├── README.md  CHANGELOG.md  LICENSE  NOTICE  # MIT
    │   ├── skills/{start,resume,status,report,stop}/SKILL.md
    │   ├── references/{protocol,statistics,state-schema,resume-loop,completion-status}.md
    │   └── templates/{ar.config.json,benchmark.sh,checks.sh,
    │                  evaluator.py,ar-loop.sh}
    ├── tuneml/                              # plugin name: tml
    │   ├── .claude-plugin/plugin.json
    │   ├── README.md  CHANGELOG.md  LICENSE  NOTICE  # MIT (+ CC BY 4.0 material)
    │   ├── skills/{audit,plan,round,analyze,review}/SKILL.md
    │   ├── references/{evidence-grades,literature,optimisers,regime,
    │   │               hyperparameter-roles,study-design,diagnostics,
    │   │               instability,step-budget,tier-a-algorithmic,
    │   │               tier-b-systems,tier-c-protocol,tier-d-architecture,
    │   │               modality-map,hardware-notes,pitfalls}.md
    │   └── templates/{findings,frontier,study-spec}.md + results-example.jsonl
    └── whetstone/                           # plugin name: ws
        ├── .claude-plugin/plugin.json
        ├── README.md  CHANGELOG.md  LICENSE  NOTICE  # MIT
        └── skills/grill/SKILL.md
```

New plugins go under `plugins/<name>/` and get an entry in `.claude-plugin/marketplace.json`.

## Validation

A dependency-light `pytest` suite keeps the marketplace internally consistent —
frontmatter validity, `plugin.json` ↔ `CHANGELOG.md` version parity, marketplace
integrity, README ↔ disk skill-table sync, referenced bundled-path existence, the
`ccsci` kernel ↔ SKILL.md entrypoint contract, and the `tml` grading contract
(every tier-catalogue item carries an evidence grade, every change item also
declares a quality exposure, and both ladders match the reference). It reads
files only (no plugin code runs), so it needs nothing beyond `pytest` + `PyYAML`.

```
pip install -r tests/requirements.txt
python -m pytest tests/ -q
```

CI runs the same on every push and pull request
([`.github/workflows/validate.yml`](.github/workflows/validate.yml)). Details:
[`tests/README.md`](tests/README.md).

## License

The marketplace and the `mf` plugin are MIT — see [LICENSE](LICENSE). The `ccsci`
plugin is **Apache-2.0** with its own [plugins/ccscience/LICENSE](plugins/ccscience/LICENSE)
(its bundled `canvas-design` typefaces are under the SIL Open Font License). The
`ar` plugin is **MIT** with its own [LICENSE](plugins/autoresearch/LICENSE) and a
[NOTICE](plugins/autoresearch/NOTICE) crediting the three MIT upstreams whose
protocol behaviour it re-implements. The `tml` plugin is **MIT** with its own
[LICENSE](plugins/tuneml/LICENSE) and a
[NOTICE](plugins/tuneml/NOTICE) that additionally records its adaptation of the
**CC BY 4.0** Deep Learning Tuning Playbook, with the changes made.

## Contact

Emanuele Ballarin — [emanuele@ballarin.cc](mailto:emanuele@ballarin.cc)
