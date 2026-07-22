"""Each plugin's README skills table matches the skills on disk."""

import _util as u
import pytest


def _norm(cell: str) -> str:
    """Normalise a skills-table first cell to a bare skill name.

    Handles `/mf:setup`, `/ar:start`, and **literature-review** forms.
    """
    s = cell.strip().replace("`", "").replace("*", "").strip()
    if ":" in s:
        s = s.rsplit(":", 1)[-1]
    return s.strip().lstrip("/").strip()


def _documented_skills(readme_text: str) -> set[str]:
    """Skill names from the table whose header's first column is 'Skill'."""
    names: set[str] = set()
    in_table = False
    for line in readme_text.splitlines():
        if not line.lstrip().startswith("|"):
            in_table = False
            continue
        first = line.strip().strip("|").split("|")[0].strip()
        if first.lower() == "skill":  # header row of the skills table
            in_table = True
            continue
        if set(first) <= set("-: "):  # markdown separator row
            continue
        if in_table:
            names.add(_norm(first))
    return names


def _disk_skills(plugin_dir) -> set[str]:
    skills = plugin_dir / "skills"
    if not skills.is_dir():
        return set()
    return {d.name for d in skills.iterdir() if (d / "SKILL.md").is_file()}


@pytest.mark.parametrize("plugin", u.plugin_dirs(), ids=u.rel)
def test_readme_lists_exactly_the_skills_on_disk(plugin):
    readme = plugin / "README.md"
    assert readme.is_file(), f"{u.rel(plugin)}: missing README.md"

    documented = _documented_skills(u.read_text(readme))
    on_disk = _disk_skills(plugin)

    undocumented = sorted(on_disk - documented)
    orphaned = sorted(documented - on_disk)
    assert not undocumented and not orphaned, (
        f"{u.rel(plugin)} README skills table out of sync:\n"
        f"  on disk but undocumented: {undocumented}\n"
        f"  documented but not on disk: {orphaned}"
    )
