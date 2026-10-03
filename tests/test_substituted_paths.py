"""Paths written with Claude Code's substituted variables resolve on disk.

`${CLAUDE_PLUGIN_ROOT}/…` must exist under the plugin root and
`${CLAUDE_SKILL_DIR}/…` under the skill's own directory. The bare-token check
in `test_referenced_paths.py` skips both forms (a token preceded by `/`).
"""

import re

import _util as u
import pytest

_VAR = re.compile(r"\$\{(CLAUDE_PLUGIN_ROOT|CLAUDE_SKILL_DIR)\}/([\w./-]+)")


@pytest.mark.parametrize("skill", u.skill_files(), ids=u.rel)
def test_substituted_paths_exist(skill):
    roots = {"CLAUDE_PLUGIN_ROOT": skill.parents[2], "CLAUDE_SKILL_DIR": skill.parent}
    missing = sorted(
        f"${{{var}}}/{tok}"
        for var, raw in _VAR.findall(u.read_text(skill))
        if not (roots[var] / (tok := raw.rstrip("."))).exists()
    )
    assert not missing, f"{u.rel(skill)} references substituted path(s) that do not exist: {missing}"
