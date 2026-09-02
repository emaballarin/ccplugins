# Validation suite

## Tier 1 — static

Fast (<1s), free, dependency-light checks that keep the marketplace internally
consistent. They read files only — no plugin code is imported or executed
(kernels are parsed with `ast`), so nothing here needs matplotlib, pypdfium2, or
any other skill dependency installed.

## Run

```bash
pip install -r tests/requirements.txt
python -m pytest tests/ -q
```

**Python 3.14+ is required**, here and for the `ccsci` kernels. It is the
marketplace's declared floor, not an incidental local version: the house
formatter (`hyperformat`) runs `reorder-python-imports --py314-plus`, so every
`.py` in the repo may carry syntax older interpreters reject. CI pins the same
floor — a lower CI version would fail on source that is correct by policy.

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

## Tier 2 — behavioural (`test_kernel_behaviour.py`)

Tier 1 never executes plugin code. This one does, for the narrow set of ccsci
kernel helpers that are **pure** — no network, no filesystem, no third-party
import. Kernels defer every heavy import into a function body, so importing one
still needs nothing beyond the stdlib and the tier stays as fast and as
dependency-light as Tier 1. Anything needing matplotlib, pypdfium2, pdfplumber
or a live service is out of scope here by construction.

Covered: `finalize_outline` and `finalize_paper_brief` (the two invariants that
guard model-returned JSON), `litrev_contact` (no address configured must mean no
`mailto:` sent at all), `extract_dois`, `dedupe_records`, `pdf_guard_text` (a
delimiter can never be forged out of untrusted page text), and the
`grid_geom` / `compose_crops` panel geometry.

This tier earns its keep: writing it surfaced a live defect in `extract_dois`
(a markdown-bolded DOI immediately before a full stop kept its asterisks),
inherited from the Claude Science original and fixed in ccsci 0.7.0. The
regression case is parametrised in the file.

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
