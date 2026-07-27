"""parml's evidence-grade contract holds, and its cross-references resolve.

The plugin's whole claim to being an analyst rather than a folklore dispenser is
that every catalogue item carries a grade from a fixed ladder, and that the
skills can route between catalogues by item id. Both are hand-maintained prose,
so both drift silently. These checks are cheap and catch the drift.

Reads files only; nothing is imported or executed.
"""

import re

import _util as u
import pytest

PARML = u.PLUGINS_DIR / "paretoml"

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

# Catalogue files whose items must each carry a grade.
TIER_FILES = ("tier-a-algorithmic.md", "tier-b-systems.md", "tier-c-protocol.md")

# Of those, the ones whose items are *changes* and so must also declare a quality
# exposure. Tier C items are protocol rules, not changes, and are exempt.
CHANGE_TIER_FILES = ("tier-a-algorithmic.md", "tier-b-systems.md")

# `### A1 — title`, `### A1b — title`, `### B12 — title`, `### P7 — title`
_ITEM_HEADING = re.compile(r"^###\s+(?P<id>[ABCP]\d+[a-z]?)\s+—", re.MULTILINE)
_BACKTICKED = re.compile(r"`([^`]+)`")
# A bare item reference in prose: A3, B11, C6, P14. Hyphenated forms (`P-1`, the
# hardware probes) and `#` placeholders in templates deliberately do not match.
_ITEM_REF = re.compile(r"(?<![\w-])([ABCP]\d+[a-z]?)(?![\w-])")

pytestmark = pytest.mark.skipif(not PARML.is_dir(), reason="parml plugin not present")


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


@pytest.mark.parametrize("filename", TIER_FILES)
def test_every_catalogue_item_carries_a_valid_grade(filename):
    path = PARML / "references" / filename
    assert path.is_file(), f"{u.rel(path)}: missing catalogue file"

    items = _items(path)
    assert items, f"{u.rel(path)}: no `### <ID> — title` items found"

    ungraded, bad = [], []
    for item_id, body in items.items():
        field = _field(body, "Grade")
        if field is None:
            ungraded.append(item_id)
            continue
        tokens = _BACKTICKED.findall(field)
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


@pytest.mark.parametrize("filename", CHANGE_TIER_FILES)
def test_every_change_item_declares_a_quality_exposure(filename):
    """Radius is not exposure: a change's quality cost is stated, never inferred.

    The first backticked token after `**Exposure**` is the level; the prose after
    it names the dimensions and the knob, and may contain other backticks.
    """
    path = PARML / "references" / filename
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
def test_ladders_are_documented(ladder, values):
    """The values this test enforces are the ones evidence-grades.md defines."""
    path = PARML / "references" / "evidence-grades.md"
    assert path.is_file(), f"{u.rel(path)}: missing"
    text = u.read_text(path)
    undocumented = [v for v in values if f"`{v}`" not in text]
    assert not undocumented, (
        f"{u.rel(path)}: {ladder} value(s) enforced by tests/test_evidence_grades.py but not documented: {undocumented}"
    )


def test_item_cross_references_resolve():
    """Every A#/B#/C#/P# mentioned anywhere in parml is defined in a catalogue."""
    defined: set[str] = set()
    for filename in (*TIER_FILES, "pitfalls.md"):
        defined |= set(_items(PARML / "references" / filename))
    assert defined, "no catalogue items found at all — did the reference layout change?"

    dangling: dict[str, set[str]] = {}
    for path in sorted(PARML.rglob("*.md")):
        refs = {
            r
            for line in u.read_text(path).splitlines()
            if not line.lstrip().startswith("###")  # a heading defines, it does not refer
            for r in _ITEM_REF.findall(line)
        }
        if missing := refs - defined:
            dangling[u.rel(path)] = missing

    assert not dangling, "reference(s) to catalogue items that do not exist: " + "; ".join(
        f"{f}: {sorted(m)}" for f, m in sorted(dangling.items())
    )
