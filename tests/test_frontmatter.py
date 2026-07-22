"""Every skill and agent has valid, load-bearing frontmatter."""

import _util as u
import pytest


@pytest.mark.parametrize("skill", u.skill_files(), ids=u.rel)
def test_skill_frontmatter(skill):
    fm = u.parse_frontmatter(skill)

    expected_name = skill.parent.name
    assert fm.get("name") == expected_name, (
        f"{u.rel(skill)}: frontmatter name {fm.get('name')!r} != directory name {expected_name!r}"
    )

    desc = fm.get("description")
    assert isinstance(desc, str) and desc.strip(), f"{u.rel(skill)}: description must be a non-empty string"

    if "allowed-tools" in fm:
        tools = fm["allowed-tools"]
        assert isinstance(tools, list) and tools, f"{u.rel(skill)}: allowed-tools must be a non-empty list"
        unknown = [t for t in tools if t not in u.KNOWN_TOOLS]
        assert not unknown, (
            f"{u.rel(skill)}: unknown tool(s) in allowed-tools: {unknown}. "
            f"If genuinely new, add them to KNOWN_TOOLS in tests/_util.py."
        )


@pytest.mark.parametrize("agent", u.agent_files(), ids=u.rel)
def test_agent_frontmatter(agent):
    fm = u.parse_frontmatter(agent)

    expected_name = agent.stem
    assert fm.get("name") == expected_name, (
        f"{u.rel(agent)}: frontmatter name {fm.get('name')!r} != file stem {expected_name!r}"
    )

    desc = fm.get("description")
    assert isinstance(desc, str) and desc.strip(), f"{u.rel(agent)}: description must be a non-empty string"
