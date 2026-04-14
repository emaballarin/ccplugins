# ccplugins

Emanuele Ballarin's personal Claude Code plugin marketplace.

## Install the marketplace

From any Claude Code session:

```
/plugin marketplace add emaballarin/ccplugins
```

Then install individual plugins with `/plugin install <name>@ccplugins`.

## Plugins

| Name | Description                                                                                                                                                                | Docs                                              |
| ---- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------- |
| `mf` | **mindfunnel** — project-agnostic session management. Four skills (`/mf:setup`, `/mf:prime`, `/mf:dump`, `/mf:spinup`) that funnel session state into auto-memory and back. | [plugins/mindfunnel](plugins/mindfunnel/README.md) |

## Install a plugin

```
/plugin install mf@ccplugins
```

## Layout

```
ccplugins/
├── .claude-plugin/
│   └── marketplace.json
├── README.md                             # this file
├── LICENSE                               # MIT
└── plugins/
    └── mindfunnel/
        ├── .claude-plugin/plugin.json
        ├── README.md
        ├── CHANGELOG.md
        ├── skills/{setup,prime,dump,spinup}/SKILL.md
        └── templates/{AGENTS,SOUL,PROJECT}.md
```

New plugins go under `plugins/<name>/` and get an entry in `.claude-plugin/marketplace.json`.

## License

MIT. See [LICENSE](LICENSE).

## Contact

Emanuele Ballarin — [emanuele@ballarin.cc](mailto:emanuele@ballarin.cc)
