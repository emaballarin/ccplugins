"""Tier-2: the ccsci kernels' pure functions actually behave.

Tier-1 (`test_kernels.py`) parses kernels with `ast` and never runs them. This
module does the opposite for the narrow set of helpers that are *pure* — no
network, no filesystem, no third-party import — and pins the invariants that a
reasonable-looking edit could silently break.

Kernels defer every heavy import into a function body, so importing one costs
nothing and needs no skill dependency installed. Anything requiring matplotlib,
pypdfium2, pdfplumber or the network stays out of this file by construction.
"""

import importlib.util
import re

import _util as u
import pytest


def _kernel(skill: str):
    """Import a ccsci kernel by path, as SKILL.md instructs the agent to."""
    path = u.PLUGINS_DIR / "ccscience" / "skills" / skill / "kernel.py"
    spec = importlib.util.spec_from_file_location(f"ccsci_{skill.replace('-', '_')}", path)
    assert spec is not None and spec.loader is not None, f"cannot load {u.rel(path)}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


litrev = _kernel("literature-review")
pdfx = _kernel("pdf-explore")
figcomp = _kernel("figure-composer")
papernar = _kernel("paper-narrative")


# ── figure-composer.finalize_outline ────────────────────────────────────────
# The invariant: a vision model cannot know a data ref, so whatever it puts in
# data_vid is invented and would send a panel subagent to a nonexistent path.


def test_finalize_outline_nulls_every_data_vid():
    outline = {
        "claim": "x",
        "panels": [
            {"letter": "a", "data_vid": "results.csv"},
            {"letter": "b", "data_vid": None},
            {"letter": "c"},
        ],
    }
    out = figcomp.finalize_outline(outline)
    assert [p["data_vid"] for p in out["panels"]] == [None, None, None]


def test_finalize_outline_does_not_mutate_its_input():
    outline = {"panels": [{"letter": "a", "data_vid": "invented.csv"}]}
    figcomp.finalize_outline(outline)
    assert outline["panels"][0]["data_vid"] == "invented.csv", "input was mutated; helper must be pure"


def test_finalize_outline_preserves_every_other_field():
    outline = {
        "claim": "c",
        "width_mm": 180,
        "ncol": 12,
        "row_heights_mm": [40, 60],
        "panels": [{"letter": "a", "role": "hero", "ask": "show it", "colspan": 6, "data_vid": "x"}],
    }
    out = figcomp.finalize_outline(outline)
    assert out["claim"] == "c" and out["width_mm"] == 180 and out["row_heights_mm"] == [40, 60]
    assert out["panels"][0]["role"] == "hero" and out["panels"][0]["colspan"] == 6


def test_finalize_outline_rejects_malformed_input():
    with pytest.raises(TypeError):
        figcomp.finalize_outline(["not", "a", "dict"])
    with pytest.raises(ValueError):
        figcomp.finalize_outline({"claim": "no panels key"})
    with pytest.raises(TypeError):
        figcomp.finalize_outline({"panels": "not a list"})


# ── paper-narrative.finalize_paper_brief ────────────────────────────────────
# The invariant: an empty `figures` makes narrative_review_task render an empty
# per-figure table, so the reviewer grades a deck it was never shown.

CLAIMS = [{"key": "fig1", "claim": "the hook"}, {"key": "fig2", "claim": "the mechanism"}]


@pytest.mark.parametrize("returned", [{}, {"figures": None}, {"figures": []}], ids=["absent", "null", "empty"])
def test_finalize_paper_brief_fills_missing_figures(returned):
    out = papernar.finalize_paper_brief({"pitch": "p", "vision": "v", **returned}, CLAIMS)
    assert out["figures"] == CLAIMS


def test_finalize_paper_brief_keeps_a_populated_figures_list():
    model_figures = [{"key": "fig1", "claim": "the model's own read"}]
    out = papernar.finalize_paper_brief({"pitch": "p", "figures": model_figures}, CLAIMS)
    assert out["figures"] == model_figures, "a non-empty model list must survive — reviewing it is the point"


def test_finalize_paper_brief_does_not_mutate_its_input():
    brief = {"pitch": "p"}
    papernar.finalize_paper_brief(brief, CLAIMS)
    assert "figures" not in brief, "input was mutated; helper must be pure"


def test_finalize_paper_brief_rejects_malformed_input():
    with pytest.raises(TypeError):
        papernar.finalize_paper_brief("not a dict", CLAIMS)


# ── literature-review.litrev_contact ────────────────────────────────────────
# The invariant: no address configured => no mailto at all. A placeholder in the
# Crossref/doi.org polite pool identifies nobody and is worse than sending none.


@pytest.mark.parametrize("value", [None, "", "   "], ids=["unset", "empty", "blank"])
def test_litrev_contact_is_none_without_a_real_address(monkeypatch, value):
    if value is None:
        monkeypatch.delenv("LITREVIEW_CONTACT_EMAIL", raising=False)
    else:
        monkeypatch.setenv("LITREVIEW_CONTACT_EMAIL", value)
    assert litrev.litrev_contact() is None


def test_litrev_contact_returns_a_configured_address(monkeypatch):
    monkeypatch.setenv("LITREVIEW_CONTACT_EMAIL", " someone@example.org ")
    assert litrev.litrev_contact() == "someone@example.org"


# ── literature-review.extract_dois ──────────────────────────────────────────


def test_extract_dois_strips_trailing_markdown_and_punctuation():
    text = "See [a](https://doi.org/10.1234/abcdefgh), and 10.5555/zyxwvuts. Also **10.1111/qrstuvwx**, too."
    got = litrev.extract_dois(text)
    assert "10.1234/abcdefgh" in got
    assert "10.5555/zyxwvuts" in got, "a sentence-final period must not be kept as part of the DOI"
    assert "10.1111/qrstuvwx" in got, "markdown bold must not be kept as part of the DOI"
    assert all(not d.endswith((".", ",", "*", ")")) for d in got)


@pytest.mark.parametrize(
    "text",
    [
        "Also **10.1111/qrstuvwx**.",
        "Also **10.1111/qrstuvwx**,",
        "Also __10.1111/qrstuvwx__.",
        "Also 10.1111/qrstuvwx..",
        "Also 10.1111/qrstuvwx.,",
    ],
    ids=["bold-then-stop", "bold-then-comma", "underscore-then-stop", "two-stops", "stop-then-comma"],
)
def test_extract_dois_strips_mixed_trailing_runs_in_one_pass(text):
    """Regression: a bolded DOI before a full stop used to keep its asterisks.

    The trailing strip is anchored at end-of-string, and the full stop used to
    be removed *afterwards* by a separate `removesuffix`. On `**10.x/y**.` the
    regex therefore matched nothing (no `.` in its class, so nothing matched at
    the end), and by the time the period went the asterisks were stranded with
    no second pass to catch them. `**10.x/y**,` always worked, because a comma
    *is* in the class and went in the same bite.

    Inherited from the Claude Science original; fixed in ccsci 0.7.0 by folding
    `.` into the class, which also makes the pass order-independent."""
    assert litrev.extract_dois(text) == ["10.1111/qrstuvwx"]


def test_extract_dois_keeps_interior_periods():
    """Only *trailing* punctuation goes — a DOI suffix may contain periods."""
    assert litrev.extract_dois("see 10.1234/v1.2.3 and 10.1234/a.b.c.") == ["10.1234/a.b.c", "10.1234/v1.2.3"]


def test_extract_dois_balances_parentheses():
    (doi,) = litrev.extract_dois("(see 10.1234/abc(def)ghi)")
    assert doi == "10.1234/abc(def)ghi", "an inner balanced pair must survive; the outer wrapper must not"


def test_extract_dois_deduplicates_and_sorts():
    got = litrev.extract_dois("10.1234/abcdefgh and again 10.1234/abcdefgh")
    assert got == ["10.1234/abcdefgh"]


# ── literature-review.dedupe_records ────────────────────────────────────────


def test_dedupe_records_merges_on_shared_doi():
    got = litrev.dedupe_records([
        {"doi": "10.1234/abcdefgh", "title": "A Paper", "year": 2024},
        {"doi": "10.1234/ABCDEFGH", "title": "A Paper", "cited_by": 7},
    ])
    assert len(got) == 1, "DOI matching must be case-insensitive"
    assert got[0].get("year") == 2024 and got[0].get("cited_by") == 7, "fields from both records must survive"


def test_dedupe_records_keeps_genuinely_distinct_work():
    got = litrev.dedupe_records([
        {"doi": "10.1234/aaaaaaaa", "title": "First"},
        {"doi": "10.5678/bbbbbbbb", "title": "Second"},
    ])
    assert len(got) == 2


# ── pdf-explore.pdf_guard_text ──────────────────────────────────────────────
# The invariant: untrusted page text can never forge a prompt delimiter, and
# neutralisation is single-pass safe (nothing is deleted, so nothing can
# reassemble into a tag).

_TAGS = ("instructions", "page", "query")


def _forges_a_delimiter(text: str) -> bool:
    """Does `text` still contain an openable instructions/page/query tag?

    This — not "contains no `<`" — is the actual invariant. A `<` that is not
    followed by a delimiter keyword cannot open a block, so it is harmless and
    is deliberately left in place (nothing is deleted, which is what makes the
    substitution single-pass safe).
    """
    return re.search(r"<\s*/?\s*(?:instructions|page|query)\b", text, re.IGNORECASE) is not None


@pytest.mark.parametrize("tag", _TAGS)
def test_pdf_guard_text_neutralises_tag_lookalikes(tag):
    for probe in (f"<{tag}>", f"</{tag}>", f"<{tag.upper()}>", f"< {tag}>", f"</ {tag}>"):
        assert not _forges_a_delimiter(pdfx.pdf_guard_text(probe)), f"{probe!r} survived as an openable delimiter"


def test_pdf_guard_text_is_single_pass_safe_against_nesting():
    """Deleting matches would let fragments reassemble; neutralising cannot.

    On `<in<page>structions>` the inner bracket is neutralised and the outer one
    is left alone — correctly, since `<in…` is not a delimiter keyword. The
    result contains a `<`, but no openable tag, and no second pass can create
    one.
    """
    out = pdfx.pdf_guard_text("<in<page>structions>")
    assert not _forges_a_delimiter(out)
    assert not _forges_a_delimiter(pdfx.pdf_guard_text(out))


def test_pdf_guard_text_is_idempotent():
    once = pdfx.pdf_guard_text("<instructions>text</page>")
    assert pdfx.pdf_guard_text(once) == once


def test_pdf_guard_text_preserves_benign_text_and_length():
    for benign in ("<page-size>", "a < b and c > d", "<div>", ""):
        out = pdfx.pdf_guard_text(benign)
        assert len(out) == len(benign), "neutralisation must replace, never delete"
    assert pdfx.pdf_guard_text("a < b") == "a < b", "a bare angle bracket is not tag-shaped"
    assert pdfx.pdf_guard_text(None) == ""


# ── figure-composer geometry ────────────────────────────────────────────────

_OUTLINE = {
    "claim": "c",
    "width_mm": 180,
    "ncol": 12,
    "row_heights_mm": [40, 60],
    "panels": [
        {
            "letter": "a",
            "role": "hero",
            "message": "m",
            "chart_family": "line",
            "row": 0,
            "col": 0,
            "colspan": 12,
            "ask": "x",
        },
        {
            "letter": "b",
            "role": "primary",
            "message": "m",
            "chart_family": "bar",
            "row": 1,
            "col": 0,
            "colspan": 6,
            "ask": "x",
        },
        {
            "letter": "c",
            "role": "primary",
            "message": "m",
            "chart_family": "bar",
            "row": 1,
            "col": 6,
            "colspan": 6,
            "ask": "x",
        },
    ],
}


def test_compose_crops_covers_every_panel_within_the_canvas():
    crops = figcomp.compose_crops(_OUTLINE)
    assert set(crops) == {"a", "b", "c"}
    W, *_ = figcomp.grid_geom(_OUTLINE)
    for letter, (x0, y0, x1, y1) in crops.items():
        assert 0 <= x0 < x1 <= W, f"panel {letter} crop escapes the canvas horizontally"
        assert 0 <= y0 < y1, f"panel {letter} crop is inverted or negative vertically"


def test_compose_crops_places_side_by_side_panels_side_by_side():
    crops = figcomp.compose_crops(_OUTLINE)
    assert crops["b"][0] < crops["c"][0], "col 0 must sit left of col 6"
    assert crops["a"][3] <= crops["b"][3], "row 0 must sit above row 1"


def test_grid_geom_row_heights_track_the_outline_ratio():
    rowh = figcomp.grid_geom(_OUTLINE)[3]
    assert rowh[1] > rowh[0], "row_heights_mm [40, 60] must yield a taller second row"
    assert rowh[1] / rowh[0] == pytest.approx(60 / 40, rel=0.02)
