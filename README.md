# ccplugins

Emanuele Ballarin's personal Claude Code plugin marketplace.

## Install the marketplace

From any Claude Code session:

```
/plugin marketplace add emaballarin/ccplugins
```

Then install individual plugins with `/plugin install <name>@ccplugins`.

## Plugins

| Name    | Description                                                                                                                                                                                                                                                                                                  | Docs                                                   |
| ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------ |
| `mf`    | **mindfunnel** — project-agnostic session management. Four skills (`/mf:setup`, `/mf:prime`, `/mf:dump`, `/mf:spinup`) that funnel session state into auto-memory and back.                                                                                                                                  | [plugins/mindfunnel](plugins/mindfunnel/README.md)     |
| `ccsci` | **ccscience** — research & scientific-computing skills adapted from Claude Science: literature-review, pdf-explore, the figure-style / figure-composer / paper-narrative trilogy, canvas-design, doc-coauthoring, web-artifacts-builder, plus the `computational-scientist` and `deep-researcher` subagents. | [plugins/ccscience](plugins/ccscience/README.md)       |
| `ar`    | **autoresearch** — an autonomous experiment loop for any numeric objective. Five skills (`/ar:start`, `/ar:resume`, `/ar:status`, `/ar:report`, `/ar:stop`) that propose one change, measure it, and keep it only if it beats the measured noise floor.                                                      | [plugins/autoresearch](plugins/autoresearch/README.md) |
| `parml` | **paretoml** — a read-first advisor for the speed↔quality frontier of a training pipeline. Three skills (`/parml:audit`, `/parml:plan`, `/parml:review`) that price changes in time-to-target-quality rather than throughput, grade the evidence behind each, and name what each would silently break.       | [plugins/paretoml](plugins/paretoml/README.md)         |

## Install a plugin

```
/plugin install mf@ccplugins
/plugin install ccsci@ccplugins
/plugin install ar@ccplugins
/plugin install parml@ccplugins
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
    │   ├── README.md
    │   ├── CHANGELOG.md
    │   ├── skills/{setup,prime,dump,spinup}/SKILL.md
    │   ├── references/ledger.md
    │   └── templates/{AGENTS,SOUL,PROJECT}.md
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
    └── paretoml/                            # plugin name: parml
        ├── .claude-plugin/plugin.json
        ├── README.md  CHANGELOG.md  LICENSE  NOTICE  # MIT
        ├── skills/{audit,plan,review}/SKILL.md
        ├── references/{evidence-grades,tier-a-algorithmic,tier-b-systems,
        │               tier-c-protocol,modality-map,hardware-notes,pitfalls}.md
        └── templates/{findings,frontier}.md
```

New plugins go under `plugins/<name>/` and get an entry in `.claude-plugin/marketplace.json`.

## Validation

A dependency-light `pytest` suite keeps the marketplace internally consistent —
frontmatter validity, `plugin.json` ↔ `CHANGELOG.md` version parity, marketplace
integrity, README ↔ disk skill-table sync, referenced bundled-path existence, the
`ccsci` kernel ↔ SKILL.md entrypoint contract, and the `parml` grading contract
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
protocol behaviour it re-implements.

## Contact

Emanuele Ballarin — [emanuele@ballarin.cc](mailto:emanuele@ballarin.cc)
