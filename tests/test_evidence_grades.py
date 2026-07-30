"""The evidence-grade contract holds, and catalogue cross-references resolve.

A grading plugin's whole claim to being an analyst rather than a folklore
dispenser is that every catalogue item carries a grade from a fixed ladder, and
that the skills can route between catalogues by item id. Both are hand-maintained
prose, so both drift silently. These checks are cheap and catch the drift.

Applies to every plugin that ships `references/evidence-grades.md` — currently
`tuneml`. Tier files are discovered rather than listed, so a new
tier catalogue is covered the moment it exists.

Reads files only; nothing is imported or executed.
"""

import re

import _util as u
import pytest

# The ladder, highest-supported first. Must match `references/evidence-grades.md` §1.
ALLOWED_GRADES = (
    "measured-here",
    "measured-elsewhere",
    "mechanism",
    "analogy",
    "folklore",
)

# The quality-exposure ladder. Must match `references/evidence-grades.md` §3.2.
ALLOWED_EXPOSURES = ("neutral", "bounded", "spending", "unknown")

# Tier catalogues whose items are protocol *rules* rather than *changes*, and so
# are exempt from declaring a quality exposure.
RULE_TIERS = ("tier-c-protocol.md",)

# `### A1 — title`, `### A1b — title`, `### B12 — title`, `### D3 — title`, `### P7 — title`
_ITEM_HEADING = re.compile(r"^###\s+(?P<id>[ABCDP]\d+[a-z]?)\s+—", re.MULTILINE)
_BACKTICKED = re.compile(r"`([^`]+)`")
# A `**Grade**` field may cite the source that earns the grade — ``measured-elsewhere`
# (`L-HE16`)``. Literature keys resolve in `references/literature.md` and are not
# candidate grades; anything else backticked there is a typo or an undocumented grade.
_LITERATURE_KEY = re.compile(r"^L-[A-Z0-9]+$")
# A bare item reference in prose: A3, B11, C6, D8, P14. Hyphenated forms (`P-1`,
# the hardware probes) and `#` placeholders in templates deliberately do not match.
_ITEM_REF = re.compile(r"(?<![\w-])([ABCDP]\d+[a-z]?)(?![\w-])")


def _grading_plugins():
    """Plugin dirs that ship an evidence-grade contract."""
    return [p for p in u.plugin_dirs() if (p / "references" / "evidence-grades.md").is_file()]


def _tier_files(plugin):
    """Tier catalogue paths for one plugin, discovered on disk."""
    return sorted((plugin / "references").glob("tier-*.md"))


def _tier_params(change_only: bool):
    """Tier catalogue paths across every grading plugin, optionally change tiers only."""
    return [
        pytest.param(path, id=f"{plugin.name}/{path.name}")
        for plugin in _grading_plugins()
        for path in _tier_files(plugin)
        if not (change_only and path.name in RULE_TIERS)
    ]


def _items(path):
    """{item id: body text} for one catalogue file, split on `### <ID> —` headings."""
    text = u.read_text(path)
    matches = list(_ITEM_HEADING.finditer(text))
    return {
        m.group("id"): text[m.end() : (matches[i + 1].start() if i + 1 < len(matches) else len(text))]
        for i, m in enumerate(matches)
    }


def _field(body: str, marker: str) -> str | None:
    """The text of a `**Marker**` field: from the marker to the next bold marker.

    Header blocks wrap across lines and the next field (`**Moves**`, `**Radius**`,
    `**Governs**`) can start mid-line, so a field ends at the next `**` rather
    than at the next newline.
    """
    start = body.find(f"**{marker}**")
    if start == -1:
        return None
    start += len(marker) + 4
    end = body.find("**", start)
    return body[start : end if end != -1 else len(body)]


def test_at_least_one_grading_plugin_exists():
    """Guards against the discovery above silently matching nothing."""
    assert _grading_plugins(), "no plugin ships references/evidence-grades.md — did the layout change?"


@pytest.mark.parametrize("path", _tier_params(change_only=False))
def test_every_catalogue_item_carries_a_valid_grade(path):
    items = _items(path)
    assert items, f"{u.rel(path)}: no `### <ID> — title` items found"

    ungraded, bad = [], []
    for item_id, body in items.items():
        field = _field(body, "Grade")
        if field is None:
            ungraded.append(item_id)
            continue
        tokens = [t for t in _BACKTICKED.findall(field) if not _LITERATURE_KEY.match(t)]
        if not any(t in ALLOWED_GRADES for t in tokens):
            ungraded.append(item_id)
        bad += [f"{item_id}:{t}" for t in tokens if t not in ALLOWED_GRADES]

    assert not ungraded, (
        f"{u.rel(path)}: item(s) with no grade from the ladder: {sorted(ungraded)}. "
        f"Every catalogue item needs a `**Grade**` field naming one of {list(ALLOWED_GRADES)}."
    )
    assert not bad, (
        f"{u.rel(path)}: backticked token(s) in a `**Grade**` field that are not on "
        f"the ladder (typo, or a new grade needing a ladder entry): {sorted(bad)}"
    )


@pytest.mark.parametrize("path", _tier_params(change_only=True))
def test_every_change_item_declares_a_quality_exposure(path):
    """Radius is not exposure: a change's quality cost is stated, never inferred.

    The first backticked token after `**Exposure**` is the level; the prose after
    it names the dimensions and the knob, and may contain other backticks.
    """
    items = _items(path)
    assert items, f"{u.rel(path)}: no `### <ID> — title` items found"

    missing, bad = [], []
    for item_id, body in items.items():
        field = _field(body, "Exposure")
        if field is None:
            missing.append(item_id)
            continue
        token = _BACKTICKED.search(field)
        if token is None:
            missing.append(item_id)
        elif token.group(1) not in ALLOWED_EXPOSURES:
            bad.append(f"{item_id}:{token.group(1)}")

    assert not missing, (
        f"{u.rel(path)}: item(s) with no `**Exposure**` field: {sorted(missing)}. "
        f"Every change must state what quality it can cost — one of "
        f"{list(ALLOWED_EXPOSURES)} — because radius does not imply it."
    )
    assert not bad, (
        f"{u.rel(path)}: `**Exposure**` level(s) not on the ladder: {sorted(bad)}. Allowed: {list(ALLOWED_EXPOSURES)}"
    )


@pytest.mark.parametrize(
    ("ladder", "values"),
    [("grade", ALLOWED_GRADES), ("exposure", ALLOWED_EXPOSURES)],
)
@pytest.mark.parametrize("plugin", _grading_plugins(), ids=u.rel)
def test_ladders_are_documented(plugin, ladder, values):
    """The values this test enforces are the ones evidence-grades.md defines."""
    path = plugin / "references" / "evidence-grades.md"
    text = u.read_text(path)
    undocumented = [v for v in values if f"`{v}`" not in text]
    assert not undocumented, (
        f"{u.rel(path)}: {ladder} value(s) enforced by tests/test_evidence_grades.py but not documented: {undocumented}"
    )


@pytest.mark.parametrize("plugin", _grading_plugins(), ids=u.rel)
def test_item_cross_references_resolve(plugin):
    """Every A#/B#/C#/D#/P# mentioned anywhere in the plugin is defined in a catalogue."""
    defined: set[str] = set()
    for path in (*_tier_files(plugin), plugin / "references" / "pitfalls.md"):
        if path.is_file():
            defined |= set(_items(path))
    assert defined, f"{u.rel(plugin)}: no catalogue items found at all — did the reference layout change?"

    dangling: dict[str, set[str]] = {}
    for path in sorted(plugin.rglob("*.md")):
        refs = {
            r
            for line in u.read_text(path).splitlines()
            if not line.lstrip().startswith("###")  # a heading defines, it does not refer
            for r in _ITEM_REF.findall(line)
        }
        if missing := refs - defined:
            dangling[u.rel(path)] = missing

    assert not dangling, f"{u.rel(plugin)}: reference(s) to catalogue items that do not exist: " + "; ".join(
        f"{f}: {sorted(m)}" for f, m in sorted(dangling.items())
    )
