"""Bundled-resource paths referenced inside a SKILL.md exist on disk.

Scope is deliberately narrow to avoid false positives on runtime paths
(`./.ar/…`, `~/.claude/…`) and on bare filenames that are copied from a
template at run time (`benchmark.sh`, `ar-loop.sh`). Only explicit
`templates/…`, `references/…`, `scripts/…` tokens and a bare `kernel.py`
are checked, resolved against the skill dir first, then the plugin root.
"""

import re

import _util as u
import pytest

_TOKEN = re.compile(
    r"(?<![\w/])(?:templates|references|scripts)/[\w./-]+"
    r"|(?<![\w/])kernel\.py"
)


def _referenced_tokens(text: str) -> set[str]:
    tokens: set[str] = set()
    for line in text.splitlines():
        if "http" in line:  # skip URLs
            continue
        for m in _TOKEN.finditer(line):
            tokens.add(m.group(0).rstrip("."))
    return tokens


@pytest.mark.parametrize("skill", u.skill_files(), ids=u.rel)
def test_referenced_bundled_paths_exist(skill):
    skill_dir = skill.parent
    plugin_root = skill.parents[2]

    missing = [
        tok
        for tok in sorted(_referenced_tokens(u.read_text(skill)))
        if not (skill_dir / tok).exists() and not (plugin_root / tok).exists()
    ]
    assert not missing, (
        f"{u.rel(skill)} references bundled path(s) that do not exist "
        f"(checked {u.rel(skill_dir)}/ and {u.rel(plugin_root)}/): {missing}"
    )
