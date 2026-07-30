# Tier-1 static validation

Fast (<1s), free, dependency-light checks that keep the marketplace internally
consistent. They read files only — no plugin code is imported or executed
(kernels are parsed with `ast`), so nothing here needs matplotlib, pypdfium2, or
any other skill dependency installed.

## Run

```bash
pip install -r tests/requirements.txt
python -m pytest tests/ -q
```

CI runs the same command on every push and pull request
(`.github/workflows/validate.yml`).

## What is checked

| Module                     | Invariant                                                                                                                                                                                                                                                                                                                                                     |
| -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `test_frontmatter.py`      | Each skill/agent has valid frontmatter: `name` matches its dir/file, `description` is non-empty, and any `allowed-tools` are known (see `KNOWN_TOOLS` in `_util.py`).                                                                                                                                                                                         |
| `test_versions.py`         | Each `plugin.json` `version` equals the newest `## X.Y.Z` heading in that plugin's `CHANGELOG.md`.                                                                                                                                                                                                                                                            |
| `test_marketplace.py`      | Every `marketplace.json` entry resolves to a real plugin dir whose `plugin.json` name matches; every plugin on disk is listed.                                                                                                                                                                                                                                |
| `test_readme_sync.py`      | Each plugin README's skills table lists exactly the skills on disk — no undocumented skills, no orphaned rows.                                                                                                                                                                                                                                                |
| `test_referenced_paths.py` | `templates/…`, `references/…`, `scripts/…`, and `kernel.py` paths referenced inside a SKILL.md exist.                                                                                                                                                                                                                                                         |
| `test_kernels.py`          | Each ccsci `kernel.py` parses and still defines every entrypoint its SKILL.md advertises (`KERNEL_API` manifest).                                                                                                                                                                                                                                             |
| `test_evidence_grades.py`  | Every `tml` tier-catalogue item carries a grade, every _change_ tier item (A/B/D — C is protocol rules, exempt) also declares a quality exposure, both ladders match what `evidence-grades.md` documents, and every `A#`/`B#`/`C#`/`D#`/`P#` cross-reference resolves. Tier files are discovered on disk, so a new catalogue is covered as soon as it exists. |

## When a check fails

The message names the offending file and value. Three cases need a test edit
rather than a content fix:

- A genuinely new tool in `allowed-tools` → add it to `KNOWN_TOOLS` in `_util.py`.
- A new or renamed kernel entrypoint → update `KERNEL_API` in `test_kernels.py`
  (and the SKILL.md that calls it).
- A genuinely new evidence grade or exposure level → add it to `ALLOWED_GRADES` /
  `ALLOWED_EXPOSURES` in `test_evidence_grades.py` **and** to the matching ladder
  in `plugins/tuneml/references/evidence-grades.md`; the test cross-checks the
  two in both directions.
