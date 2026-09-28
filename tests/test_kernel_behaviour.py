"""Tier-2: the pure helpers in the ccsci skills actually behave.

Tier-1 (`test_kernels.py`) parses kernels with `ast` and never runs them. This
module does the opposite for the narrow set of helpers that are *pure* — no
network, no filesystem, no third-party import — and pins the invariants that a
reasonable-looking edit could silently break.

Kernels defer every heavy import into a function body, and the skill scripts
covered here import only the stdlib at module level, so importing either costs
nothing and needs no skill dependency installed. Anything requiring matplotlib,
pypdfium2, pdfplumber, pandoc or the network stays out of this file by
construction.
"""

import importlib.util
import re

import _util as u
import pytest


def _kernel(skill: str, file: str = "kernel.py"):
    """Import a ccsci skill module by path, as SKILL.md instructs the agent to."""
    path = u.PLUGINS_DIR / "ccscience" / "skills" / skill / file
    name = f"ccsci_{skill.replace('-', '_')}_{path.stem}"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None, f"cannot load {u.rel(path)}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


litrev = _kernel("literature-review")
pdfx = _kernel("pdf-explore")
figcomp = _kernel("figure-composer")
papernar = _kernel("paper-narrative")
export = _kernel("paper-review", "scripts/export_notes.py")
bibaudit = _kernel("bib-audit")


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


# ── paper-review scripts/export_notes.tag_three_column_tables ───────────────
# The invariant: every three-column table (the skill's Block/Words/Content
# tables) gets the fixed-width colgroup, whatever attributes the renderer puts
# on its tags — and nothing else is touched. A matcher that silently matches
# nothing degrades the PDF without any error, so each shape is pinned here.


def _table(n_cols: int, table_attrs: str = "", tr_attrs: str = "") -> str:
    head = "".join(f"<th>h{i}</th>" for i in range(n_cols))
    cells = "".join(f"<td>c{i}</td>" for i in range(n_cols))
    return f"<table{table_attrs}><thead><tr{tr_attrs}>{head}</tr></thead><tbody><tr>{cells}</tr></tbody></table>"


def _is_tagged(html: str) -> bool:
    return 'class="c3"' in html and "<colgroup><col><col><col></colgroup>" in html


def test_export_tags_a_plain_three_column_table():
    out = export.tag_three_column_tables(_table(3))
    assert _is_tagged(out)
    assert out.count("<colgroup>") == 1


def test_export_tolerates_attributes_on_table_and_row():
    """Older pandoc emits `<tr class="header">`; a literal-tag matcher missed it."""
    out = export.tag_three_column_tables(_table(3, table_attrs=' style="x"', tr_attrs=' class="header"'))
    assert 'style="x"' in out and 'class="c3"' in out
    assert "<colgroup><col><col><col></colgroup>" in out


def test_export_merges_into_an_existing_class():
    out = export.tag_three_column_tables(_table(3, table_attrs=' class="wide"'))
    assert 'class="wide c3"' in out
    assert out.count("class=") == 1, "a second class attribute would be ignored by the renderer"


@pytest.mark.parametrize("n_cols", [2, 4, 6])
def test_export_leaves_other_widths_alone(n_cols):
    html = _table(n_cols)
    assert export.tag_three_column_tables(html) == html


def test_export_leaves_a_renderer_colgroup_alone():
    """pandoc's `markdown` reader emits inline-width colgroups; those win anyway."""
    html = _table(3).replace("<thead>", '<colgroup><col style="width: 10%" /></colgroup><thead>', 1)
    assert export.tag_three_column_tables(html) == html


def test_export_handles_several_tables_and_is_idempotent():
    body = f"<p>a</p>{_table(2)}<p>b</p>{_table(3)}<p>c</p>"
    once = export.tag_three_column_tables(body)
    assert once.count("<colgroup>") == 1, "only the three-column table is tagged"
    assert "<p>a</p>" in once and "<p>c</p>" in once, "text between tables must survive"
    assert export.tag_three_column_tables(once) == once


# ── bib-audit.same_work ─────────────────────────────────────────────────────
# The invariant: an entry is matched only to its own work. A false match is
# silent — the entry is overwritten with a stranger's metadata and stays valid
# BibTeX — so every negative here must fail to match, while the variants a real
# bibliography carries (dropped accents and prepositions, typos, a dropped
# subtitle, a year off by one, swapped name order) must still match.


def _view(title, authors, year):
    return {"title": title, "authors": bibaudit.split_authors(authors), "year": year}


_SAME_WORK = {
    "accents": (
        _view("Neural syntax: cell assemblies, synapsembles, and readers", "Buzsaki, Gyorgy", 2010),
        _view("Neural Syntax: Cell Assemblies, Synapsembles, and Readers", "Buzsáki, György", 2010),
    ),
    "prepositions": (
        _view("Learning representations back-propagating errors", "Rumelhart, David E.", 1986),
        _view(
            "Learning representations by back-propagating errors", "Rumelhart, David E. and Hinton, Geoffrey E.", 1986
        ),
    ),
    "typo": (
        _view("Denoising Difusion Probabilistic Models", "Ho, Jonathan", 2020),
        _view("Denoising Diffusion Probabilistic Models", "Ho, Jonathan and Jain, Ajay", 2020),
    ),
    "spelling": (
        _view(
            "Modelling cellular perturbations with the sparse additive mechanism shift variational autoencoder",
            "Bereket, Michael",
            2023,
        ),
        _view(
            "Modeling Cellular Perturbations with the Sparse Additive Mechanism Shift Variational Autoencoder",
            "Bereket, Michael",
            2023,
        ),
    ),
    "subtitle": (
        _view("Neural Tangent Kernel", "Jacot, Arthur", 2018),
        _view("Neural Tangent Kernel: Convergence and Generalization in Neural Networks", "Jacot, Arthur", 2018),
    ),
    "year off by one": (
        _view("Neural Tangent Kernel Convergence and Generalisation in Neural Networks", "Jacot, A.", 2019),
        _view("Neural Tangent Kernel: Convergence and Generalization in Neural Networks", "Jacot, Arthur", 2018),
    ),
    "name order": (
        _view("Remove Symmetries to Control Model Expressivity", "Ziyin, Liu and Xu, Yizhou", 2024),
        _view("Remove Symmetries to Control Model Expressivity", "Liu Ziyin and Yizhou Xu", 2024),
    ),
    "author order": (
        _view("Introduction to the theory of neural computation", "Krogh, Anders", 1991),
        _view(
            "Introduction to the Theory of Neural Computation",
            "Hertz, John and Krogh, Anders and Palmer, Richard G.",
            1991,
        ),
    ),
}

_OTHER_WORK = {
    "follow-up by another author": (
        _view("Improved Denoising Diffusion Probabilistic Models", "Nichol, Alex", 2021),
        _view("Denoising Diffusion Probabilistic Models", "Ho, Jonathan", 2020),
    ),
    "title contains the other": (
        _view("Attention is all you need", "Vaswani, Ashish", 2017),
        _view("Tensor Product Attention Is All You Need", "Zhang, Yifan", 2025),
    ),
    "DOI of another paper": (
        _view(
            "Overcoming potential energy distortions in constrained internal coordinate molecular dynamics simulations",
            "Kandel, Saugat",
            2016,
        ),
        _view("Modeling Soil Carbon Dynamics in Northern Forests", "Dimassi, Bassem", 2016),
    ),
    "same author, same year": (
        _view("Symmetry Induces Structure and Constraint of Learning", "Ziyin, Liu", 2024),
        _view("Parameter Symmetry and Noise Equilibrium of Stochastic Gradient Descent", "Ziyin, Liu", 2024),
    ),
    "journal slot of another paper": (
        _view("Risk and parameter convergence of logistic regression", "Ji, Ziwei", 2020),
        _view("Scalable Approximate MCMC Algorithms for the Horseshoe Prior", "Johndrow, James", 2020),
    ),
    "same title, other authors": (
        _view("Deep learning", "LeCun, Yann", 2015),
        _view("Deep Learning", "Goodfellow, Ian", 2016),
    ),
}


@pytest.mark.parametrize("pair", _SAME_WORK.values(), ids=_SAME_WORK.keys())
def test_same_work_accepts_variants_of_one_work(pair):
    assert bibaudit.same_work(*pair) != "no"


@pytest.mark.parametrize("pair", _OTHER_WORK.values(), ids=_OTHER_WORK.keys())
def test_same_work_rejects_other_works(pair):
    assert bibaudit.same_work(*pair) == "no"


# ── bib-audit.openreview_status ─────────────────────────────────────────────
# The invariant: only an accepted paper counts as published. An allowlist,
# because a denylist once let `TMLR/Submitted` through and "upgraded" two
# preprints to journal papers they are not.


@pytest.mark.parametrize(
    "venueid, status",
    [
        ("ICLR.cc/2025/Conference", "published"),
        ("aistats.org/AISTATS/2024/Conference", "published"),
        ("TMLR", "published"),
        ("dblp.org/conf/ICLR/2019", "published"),
        ("dblp.org/journals/CORR/2024", "preprint"),
        ("NeurIPS.cc/2024/Workshop/OPT", "workshop"),
        ("ICLR.cc/2026/Conference/Rejected_Submission", "other"),
        ("ICLR.cc/2024/Conference/Withdrawn_Submission", "other"),
        ("ICML.cc/2026/Conference/Submission", "other"),
        ("TMLR/Submitted", "other"),
        ("OpenReview.net/Public_Article", "other"),
        ("", "other"),
    ],
)
def test_openreview_status_is_an_allowlist(venueid, status):
    assert bibaudit.openreview_status(venueid) == status


# ── bib-audit._map_cites ────────────────────────────────────────────────────
# The invariant: every key in every citation command is mapped exactly once, so a
# rename chain (a→b, b→c) cannot cascade and a key that prefixes another is
# never clobbered.


def test_map_cites_is_single_pass_and_exact():
    keymap = {"a": "b", "b": "c", "Ney2015": "Ney2015Path", "lecun-mnist": "LeCun2010MNIST"}
    tex = r"\cite{a,b} \citet{Ney2015X} \citep[see][p.~3]{Ney2015} \cites[1]{a}[2]{lecun-mnist} \nocite{*}"
    new, before, after = bibaudit._map_cites(tex, keymap)
    assert (
        new == r"\cite{b,c} \citet{Ney2015X} \citep[see][p.~3]{Ney2015Path} \cites[1]{b}[2]{LeCun2010MNIST} \nocite{*}"
    )
    assert before == {"a", "b", "Ney2015X", "Ney2015", "lecun-mnist"}
    assert "*" not in after


# ── bib-audit.restore_caps ──────────────────────────────────────────────────
# bibtex-tidy --drop-all-caps title-cases whole-caps values; the repair restores
# them from the pre-tidy entries, and only inside the entry they belong to.


def test_restore_caps_is_confined_to_its_own_entry():
    before = bibaudit.parse_bib("@article{x1, journal={PLOS ONE}}\n@article{x2, journal={Plos One}}\n")["entries"]
    # bibtex-tidy re-sorts entries, so the lookalike value can come first.
    tidied = "@article{x2,\n  journal = {Plos One},\n}\n@article{x1,\n  journal = {Plos One},\n}\n"
    text, restored = bibaudit.restore_caps(tidied, before)
    head, tail = text.split("@article{x1")
    assert "journal = {Plos One}" in head, "x2 was never all caps"
    assert "journal = {PLOS ONE}" in tail
    assert len(restored) == 1


# ── bib-audit keys ──────────────────────────────────────────────────────────
# Keys accepted in the hand-run audit this scheme was taken from.


@pytest.mark.parametrize(
    "author, title, year, key",
    [
        (
            "von Neumann, John",
            "Zur Operatorenmethode in der klassischen Mechanik",
            "1932",
            "VonNeumann1932Operatorenmethode",
        ),
        ("Han Xiao and Kashif Rasul", "{Fashion-MNIST}: a Novel Image Dataset", "2017", "Xiao2017FashionMNIST"),
        ("Hadi M. Dolatabadi", r"$\ell_\infty$-Robustness and Beyond", "2022", "Dolatabadi2022Robustness"),
        (r"Buzs\'{a}ki, Gy\"{o}rgy", "Neural syntax: cell assemblies", "2010", "Buzsaki2010Neural"),
        ("De Handschutter, Pierre", "A survey on deep matrix factorizations", "2021", "DeHandschutter2021Survey"),
        (
            "{TorchVision maintainers and contributors}",
            "TorchVision: PyTorch's Computer Vision library",
            "2016",
            "TorchVision2016TorchVision",
        ),
        ("", "{P-AGI}: The 1st Post-{AGI} Science and Society Workshop", "2026", "PAGI2026PostAGI"),
    ],
)
def test_base_key(author, title, year, key):
    fields = {"title": title, "year": year} | ({"author": author} if author else {})
    assert bibaudit.base_key({"type": "article", "key": "x", "fields": fields}) == key


def test_key_collision_takes_the_venue_then_a_letter():
    import re as _re

    venues = [
        {
            "acronym": "ICML",
            "type": "inproceedings",
            "canonical": "",
            "re": _re.compile("machine learning"),
            "adapter": "",
        }
    ]

    def e(key, journal):
        fields = {"author": "Doe, Jane", "title": "Robust things", "year": "2020", "journal": journal}
        return {"type": "article", "key": key, "fields": fields}

    keys = bibaudit.assign_keys(
        [e("a", "International Conference on Machine Learning"), e("b", "Nature"), e("c", "Nature")], venues
    )
    assert keys == ["Doe2020RobustICML", "Doe2020RobustNA", "Doe2020RobustNB"]


# ── bib-audit.version_year ──────────────────────────────────────────────────
# An unpinned preprint cites the year of v1 — unless title or authors changed
# across versions, then the year of the first version carrying the final ones.


def _arx(version, updated, title, authors):
    return {
        "arxiv": "2301.00001",
        "year": 2023,
        "title": title,
        "authors": bibaudit.split_authors(authors),
        "extra": {"version": version, "updated": updated},
    }


def test_version_year_stays_on_v1_when_nothing_changed():
    latest = _arx(3, "2025-02-01", "A title", "Doe, Jane")
    older = {
        "2301.00001v1": _arx(1, "2023-01-02", "A title", "Doe, Jane"),
        "2301.00001v2": _arx(2, "2024-05-01", "A title", "Doe, Jane"),
    }
    assert bibaudit.version_year(latest, older) == 2023


def test_version_year_moves_to_the_version_that_fixed_the_authors():
    latest = _arx(3, "2025-02-01", "A title", "Doe, Jane and Roe, Rich")
    older = {
        "2301.00001v1": _arx(1, "2023-01-02", "A title", "Doe, Jane"),
        "2301.00001v2": _arx(2, "2024-05-01", "A title", "Doe, Jane and Roe, Rich"),
    }
    assert bibaudit.version_year(latest, older) == 2024


# ── bib-audit.content_hash ──────────────────────────────────────────────────
# The cache key: blind to key, field order, bracing, escaping and month
# spelling (all of which bibtex-tidy changes), sensitive to any real edit.


def test_content_hash_ignores_layout_and_catches_edits():
    a = bibaudit.parse_bib("@article{k1, title={Caf{\\'e} {Theory}}, year={2020}, month=jan}")["entries"][0]
    b = bibaudit.parse_bib("@article{K2,\n  month = {1},\n  year = 2020,\n  title = {Café Theory},\n}")["entries"][0]
    c = bibaudit.parse_bib("@article{k1, title={Cafe Theory}, year={2020}, month=jan}")["entries"][0]
    assert bibaudit.content_hash(a) == bibaudit.content_hash(b)
    assert bibaudit.content_hash(a) != bibaudit.content_hash(c)


# ── bib-audit.parse_bib ─────────────────────────────────────────────────────


def test_parse_bib_quarantines_a_broken_entry_without_losing_the_next():
    parsed = bibaudit.parse_bib("@misc{broken, title = {unbalanced }\n@article{ok, title={Fine}, month=jan}\n")
    assert [e["key"] for e in parsed["entries"]] == ["ok"]
    assert parsed["entries"][0]["bare"] == ["month"]
    assert len(parsed["garbage"]) == 1


# ── bib-audit.apply_record ──────────────────────────────────────────────────
# A correction never degrades what the entry already had right: Crossref records
# only the first page of some articles, and flattens LaTeX math in titles.


def _record(**kw):
    base = {
        "source": "crossref",
        "id": "10.2307/2974908",
        "type": "article",
        "title": None,
        "authors": [],
        "year": None,
        "venue": None,
        "volume": None,
        "number": None,
        "pages": None,
        "publisher": None,
        "series": None,
        "doi": None,
        "arxiv": None,
        "url": None,
        "extra": {},
    }
    return base | kw


def test_apply_record_keeps_a_page_range_the_source_truncates():
    entry = {"type": "article", "key": "k", "fields": {"title": "Isometries", "pages": "452--453", "year": "1994"}}
    res = {
        "status": "verified",
        "record": _record(title="Isometries", pages="452", year=1994, venue="The American Mathematical Monthly"),
        "ids": {},
    }
    fixed, _ = bibaudit.apply_record(entry, res, [])
    assert fixed["fields"]["pages"] == "452--453"


def test_apply_record_keeps_a_title_whose_math_the_source_flattened():
    entry = {"type": "article", "key": "k", "fields": {"title": r"Isometries of $\ell_p$-norm", "year": "1994"}}
    res = {
        "status": "verified",
        "record": _record(title="Isometries of l p -norm", year=1994, venue="The American Mathematical Monthly"),
        "ids": {},
    }
    fixed, _ = bibaudit.apply_record(entry, res, [])
    assert fixed["fields"]["title"] == r"Isometries of $\ell_p$-norm"


# ── bib-audit: reprints, editions and reviews are not the entry's publication ──
# Found on a 437-entry bibliography: a 1950 journal article matched to its 1988
# reprint in an edited volume, a 1991 book to its 2018 reissue, and a book to a
# journal review of it (whose Crossref record lists the book's author too).


def _cview(title, authors, year, type_, venue="", publisher=""):
    return _view(title, authors, year) | {"type": type_, "venue": venue, "publisher": publisher}


def _crec(title, authors, year, type_, venue=None, publisher=None):
    return _record(
        title=title, authors=bibaudit.split_authors(authors), year=year, type=type_, venue=venue, publisher=publisher
    )


def test_compatible_rejects_a_reprint_in_an_edited_volume():
    entry = _cview("Computing Machinery and Intelligence", "Turing, A. M.", 1950, "article", venue="Mind")
    reprint = _crec(
        "Computing Machinery and Intelligence",
        "Turing, A. M.",
        1988,
        "incollection",
        venue="Readings in Cognitive Science",
    )
    assert not bibaudit.compatible(entry, reprint)


@pytest.mark.parametrize(
    "title, author, year, publisher, reissued, reissuer",
    [
        (
            "Introduction to the Theory of Neural Computation",
            "Hertz, John",
            1991,
            "Perseus Publishing",
            2018,
            "CRC Press",
        ),
        ("Geometric Measure Theory", "Federer, Herbert", 1969, "Springer", 1996, "Springer Berlin Heidelberg"),
    ],
    ids=["other publisher", "same publisher"],
)
def test_compatible_rejects_another_edition_of_a_book(title, author, year, publisher, reissued, reissuer):
    """A book more than a year away is another edition, whoever published it."""
    entry = _cview(title, author, year, "book", publisher=publisher)
    assert not bibaudit.compatible(entry, _crec(title, author, reissued, "book", publisher=reissuer))


def test_compatible_accepts_a_wrong_year_in_the_same_journal():
    entry = _cview(
        "Gradient-based learning applied to document recognition",
        "LeCun, Yann",
        2002,
        "article",
        venue="Proceedings of the IEEE",
    )
    record = _crec(
        "Gradient-based learning applied to document recognition",
        "LeCun, Y.",
        1998,
        "article",
        venue="Proceedings of the IEEE",
    )
    assert bibaudit.compatible(entry, record)


def test_a_review_of_a_book_is_not_the_book():
    entry = _cview("What Is the Name of This Book?", "Smullyan, Raymond M.", 1978, "book", publisher="Prentice-Hall")
    review = _crec(
        "What is the Name of this Book?: The Riddle of Dracula and Other Logical Puzzles",
        "Boolos, George and Smullyan, Raymond M.",
        1979,
        "article",
        venue="The Philosophical Review",
    )
    assert not bibaudit.compatible(entry, review)
    assert bibaudit.same_work(entry, review) == "no", "a soft title needs the first authors to agree"


# ── bib-audit.merge_authors ─────────────────────────────────────────────────


def test_merge_authors_keeps_a_particle_once():
    merged = bibaudit.merge_authors(
        bibaudit.split_authors("J. v. Neumann"), [{"first": "J.", "von": "", "last": "v. Neumann", "jr": ""}]
    )
    assert bibaudit.detex(bibaudit.join_name(merged[0])) == "v. Neumann, J."


def test_merge_authors_takes_the_sources_split_of_a_compound_surname():
    merged = bibaudit.merge_authors(
        bibaudit.split_authors("Javier Del Ser"), [{"first": "Javier", "von": "", "last": "Del Ser", "jr": ""}]
    )
    assert bibaudit.join_name(merged[0]) == "Del Ser, Javier"


def test_merge_authors_keeps_the_entrys_full_given_name_over_initials():
    merged = bibaudit.merge_authors(
        bibaudit.split_authors("Bonanno, Giovanni"), [{"first": "G.", "von": "", "last": "Bonanno", "jr": ""}]
    )
    assert bibaudit.join_name(merged[0]) == "Bonanno, Giovanni"


# ── bib-audit._crossref_record ──────────────────────────────────────────────


def test_crossref_record_drops_the_journals_article_number_from_the_title():
    rec = bibaudit._crossref_record({
        "DOI": "10.1080/14786440109462720",
        "type": "journal-article",
        "title": ["LIII. On lines and planes of closest fit to systems of points in space"],
    })
    assert rec["title"] == "On lines and planes of closest fit to systems of points in space"


def test_crossref_record_reads_an_lncs_chapter_as_a_conference_paper():
    rec = bibaudit._crossref_record({
        "DOI": "10.1007/978-3-030-58592-1_29",
        "type": "book-chapter",
        "title": ["Square Attack"],
        "container-title": ["Lecture Notes in Computer Science", "Computer Vision – ECCV 2020"],
        "event": {"name": "European Conference on Computer Vision"},
    })
    assert rec["type"] == "inproceedings"
    assert rec["venue"] == "European Conference on Computer Vision"


def test_crossref_record_uses_the_article_number_when_there_are_no_pages():
    rec = bibaudit._crossref_record({
        "DOI": "10.1063/1.3223548",
        "type": "journal-article",
        "title": ["T"],
        "article-number": "105106",
    })
    assert rec["pages"] == "105106"


# ── bib-audit.apply_record: article numbers and conference years ────────────


def test_apply_record_keeps_an_article_number_over_an_internal_page_range():
    entry = {"type": "article", "key": "k", "fields": {"title": "T", "pages": "041403", "year": "2022"}}
    res = {
        "status": "verified",
        "record": _record(title="T", pages="1-10", year=2022, venue="Neurophotonics"),
        "ids": {},
    }
    fixed, _ = bibaudit.apply_record(entry, res, [])
    assert fixed["fields"]["pages"] == "041403"


def test_apply_record_keeps_the_conference_year_over_the_volumes():
    entry = {
        "type": "inproceedings",
        "key": "k",
        "fields": {"title": "Is backpropagation biologically plausible?", "year": "1989", "booktitle": "IJCNN"},
    }
    rec = _record(
        title="Is backpropagation biologically plausible?",
        year=1990,
        type="inproceedings",
        venue="International Joint Conference on Neural Networks",
        extra={"year_from_event": False, "containers": []},
    )
    fixed, _ = bibaudit.apply_record(entry, {"status": "verified", "record": rec, "ids": {}}, [])
    assert fixed["fields"]["year"] == "1989"


# ── bib-audit.clean_venue_name ──────────────────────────────────────────────


@pytest.mark.parametrize(
    "raw, name",
    [
        (
            "2023 Systems and Information Engineering Design Symposium (SIEDS)",
            "Proceedings of the Systems and Information Engineering Design Symposium",
        ),
        (
            "IEEE Conference on Secure and Trustworthy Machine Learning",
            "Proceedings of the IEEE Conference on Secure and Trustworthy Machine Learning",
        ),
        (
            "Proceedings of the Tenth Italian Conference on Computational Linguistics (CLiC-it 2024)",
            "Proceedings of the Italian Conference on Computational Linguistics",
        ),
    ],
)
def test_clean_venue_name(raw, name):
    assert bibaudit.clean_venue_name(raw) == name


# ── bib-audit.normalise_entry ───────────────────────────────────────────────


def test_normalise_converts_a_workshop_entry_whatever_its_month():
    for month in ("", ", month={April}"):
        entry = bibaudit.parse_bib("@workshop{w, title={T}, author={A, B}" + month + "}")["entries"][0]
        fixed, _ = bibaudit.normalise_entry(entry)
        assert fixed["type"] == "inproceedings"


def test_normalise_makes_months_bare_macros():
    entry = bibaudit.parse_bib("@article{a, title={T}, journal={J}, month={April}}")["entries"][0]
    fixed, _ = bibaudit.normalise_entry(entry)
    assert fixed["fields"]["month"] == "apr" and "month" in fixed["bare"]


# ── bib-audit proceedings indices ───────────────────────────────────────────
# Index pages change format over the years; a missed index silently turns a
# published paper into an unconfirmed one.


class _PageNet:
    def __init__(self, pages):
        self.pages = pages

    def get(self, url, **_):
        return self.pages.get(url)

    def once(self, _key, compute):
        return compute()


def test_jmlr_index_reads_old_and_new_layouts():
    old = "<dl><dt>Non-negative Matrix Factorization with Sparseness Constraints <dd><b><i>Patrik O. Hoyer</i></b>; 5(Nov):1457--1469, 2004. [<a href='/papers/v5/hoyer04a.html'>abs</a>]</dl>"
    new = "<dl><dt>Scalable Approximate MCMC Algorithms for the Horseshoe Prior</dt><dd><b><i>James Johndrow, Paulo Orenstein</i></b>; (73):1&minus;61, 2020. [<a href='/papers/v21/19-536.html'>abs</a>]</dl>"
    net = _PageNet({"https://jmlr.org/papers/v5/": old, "https://jmlr.org/papers/v21/": new})
    (a,), (b,) = bibaudit._jmlr_volume(net, 5), bibaudit._jmlr_volume(net, 21)
    assert (a["pages"], a["number"], a["year"]) == ("1457--1469", None, 2004)
    assert (b["pages"], b["number"], b["year"]) == ("1--61", "73", 2020)


def test_pmlr_index_reads_every_label_form_and_skips_workshops():
    items = [
        (125, "COLT 2020 Proceedings"),
        (99, "COLT 2019"),
        (75, "Proceedings of COLT 2018"),
        (202, "Proceedings of ICML 2023"),
        (251, "Proceedings of GRaM at ICML 2024"),
    ]
    html = "".join(f'<li><a href="v{v}"><b>Volume {v}</b></a> {label}</li>' for v, label in items)
    vols = bibaudit._pmlr_volumes(_PageNet({"https://proceedings.mlr.press/": html}))
    assert vols == {("COLT", 2020): 125, ("COLT", 2019): 99, ("COLT", 2018): 75, ("ICML", 2023): 202}


def test_mangled_author_lists_are_noticed():
    view = _view("T", "{Garnier} and {Simon} and {Ross} and {Noam} and {Rudis} and {Robert}", 2024)
    assert bibaudit._mangled_authors(view)
    assert not bibaudit._mangled_authors(_view("T", "{OpenAI} and Doe, Jane and Roe, Rich and Poe, Pat", 2024))


# ── bib-audit: conference-site indices and OpenReview's budget ─────────────


class _CountingNet(_PageNet):
    def __init__(self, pages):
        super().__init__(pages)
        self.urls = []

    def get(self, url, **kw):
        self.urls.append(url)
        return super().get(url, **kw)

    def get_json(self, url, ttl=None):
        import json

        body = self.get(url)
        return json.loads(body) if body else None


def test_virtual_index_reads_accepted_papers_once_each():
    import json

    rows = [
        {
            "name": "A Paper",
            "decision": "Accept: poster",
            "paper_url": "https://openreview.net/forum?id=x",
            "authors": [{"fullname": "Jane Doe"}],
        },
        {
            "name": "A Paper",
            "decision": "Accept: poster",
            "paper_url": "https://openreview.net/forum?id=x",
            "authors": [{"fullname": "Jane Doe"}],
        },
        {"name": "Rejected", "decision": "Reject", "paper_url": "https://openreview.net/forum?id=y", "authors": []},
    ]
    net = _CountingNet({
        "https://iclr.cc/static/virtual/data/iclr-2023-orals-posters.json": json.dumps({"results": rows})
    })
    (rec,) = bibaudit._virtual_index(net, "iclr", 2023)
    assert (rec["title"], rec["year"], bibaudit.surname(rec["authors"][0])) == ("A Paper", 2023, "doe")


def test_openreview_older_api_is_asked_only_for_old_work():
    """api.openreview.net allows 5 requests a minute; asking it for every entry
    stalled a 437-entry run for tens of minutes."""
    import json

    empty = json.dumps({"notes": []})
    pages = {}
    for api in ("api2.openreview.net", "api.openreview.net"):
        for t in ("New Work", "Old Work"):
            pages[
                f"https://{api}/notes/search?term={t.replace(' ', '%20')}&type=terms&content=title&source=forum&limit=10"
            ] = empty
    net = _CountingNet(pages)
    bibaudit._openreview_search(net, "New Work", 2024)
    assert not any("//api.openreview.net" in u for u in net.urls)
    bibaudit._openreview_search(net, "Old Work", 2018)
    assert any("//api.openreview.net" in u for u in net.urls)


def test_complete_leaves_a_conference_site_record_alone():
    """A NeurIPS record from the conference site has no papers.nips.cc hash; the
    completion step once raised KeyError on it and aborted a whole run."""
    import json

    body = json.dumps({
        "results": [{"name": "A Paper", "decision": "Accept (poster)", "paper_url": "u", "authors": []}]
    })
    net = _CountingNet({"https://neurips.cc/static/virtual/data/neurips-2025-orals-posters.json": body})
    (rec,) = bibaudit._virtual_index(net, "neurips", 2025)
    assert bibaudit._complete(net, rec) == rec


# ── bib-audit: the fourth round on the 437-entry bibliography ───────────────


def test_a_conference_site_record_never_reorders_authors():
    """ICLR's own paper list does not keep the paper's author order (Wong, Rice,
    Kolter came back as Rice, Wong, Kolter)."""
    entry = {
        "type": "inproceedings",
        "key": "k",
        "fields": {
            "title": "Fast is better than free",
            "author": "Eric Wong and Leslie Rice and J. Zico Kolter",
            "year": "2020",
        },
    }
    rec = _record(
        source="iclr-site",
        title="Fast is better than free",
        year=2020,
        type="inproceedings",
        venue="International Conference on Learning Representations",
        authors=bibaudit.split_authors("Leslie Rice and Eric Wong and Zico Kolter"),
    )
    fixed, _ = bibaudit.apply_record(entry, {"status": "verified", "record": rec, "ids": {}}, [])
    assert fixed["fields"]["author"] == entry["fields"]["author"]


@pytest.mark.parametrize("comment", ["10 pages, 11 figures, submitted for ICLR 2016", "Under review at NeurIPS 2023"])
def test_a_submission_is_not_a_venue_hint(comment):
    rows = [
        {"acronym": "ICLR", "type": "inproceedings", "canonical": "", "re": re.compile(r"\biclr\b"), "adapter": "iclr"},
        {
            "acronym": "NeurIPS",
            "type": "inproceedings",
            "canonical": "",
            "re": re.compile(r"\bneurips\b"),
            "adapter": "neurips",
        },
    ]
    assert bibaudit._hint_venues(comment, rows) == []


def test_an_affirmative_comment_is_a_venue_hint():
    rows = [
        {
            "acronym": "COLT",
            "type": "inproceedings",
            "canonical": "",
            "re": re.compile(r"\bcolt\b"),
            "adapter": "pmlr:COLT",
        }
    ]
    ((row, year),) = bibaudit._hint_venues("Appears in COLT 2019 with the title ...", rows)
    assert (row["acronym"], year) == ("COLT", 2019)


def test_a_linked_arxiv_record_renamed_across_versions_is_the_same_work():
    authors = "Guang Lin and Zerui Tao and Jianhai Zhang"
    entry, arxiv = (
        _view("Robust Diffusion Models for Adversarial Purification", authors, 2024),
        _view("Adversarial Guided Diffusion Models for Adversarial Purification", authors, 2024),
    )
    assert bibaudit.same_work(entry, arxiv, linked=True) == "soft"
    assert bibaudit.same_work(entry, arxiv) == "no", "without the identifier a different title stays a different work"


def test_apply_record_keeps_an_entry_year_that_is_one_of_the_works_dates():
    """Online-first 2022, print 2024: an entry saying 2022 is not wrong."""
    entry = {
        "type": "article",
        "key": "k",
        "fields": {"title": "Recent advances", "year": "2022", "journal": "Information Geometry"},
    }
    rec = _record(title="Recent advances", year=2024, venue="Information Geometry", extra={"years": [2022, 2024]})
    fixed, _ = bibaudit.apply_record(entry, {"status": "verified", "record": rec, "ids": {}}, [])
    assert fixed["fields"]["year"] == "2022"


def test_openreview_older_api_is_still_asked_when_the_newer_has_only_a_preprint():
    """Auto-Encoding Variational Bayes: api2 holds the CoRR record with the exact
    title, only the older API the ICLR 2014 one."""
    import json

    corr = {
        "forum": "c",
        "content": {
            "title": {"value": "Old Work"},
            "venueid": {"value": "dblp.org/journals/CORR/2013"},
            "venue": {"value": "CoRR 2013"},
        },
    }
    q = "Old%20Work&type=terms&content=title&source=forum&limit=10"
    net = _CountingNet({
        f"https://api2.openreview.net/notes/search?term={q}": json.dumps({"notes": [corr]}),
        f"https://api.openreview.net/notes/search?term={q}": json.dumps({"notes": []}),
    })
    bibaudit._openreview_search(net, "Old Work", 2013)
    assert any("//api.openreview.net" in u for u in net.urls)


def test_a_lookup_that_met_a_skipped_host_is_flagged_for_its_own_thread_only():
    import threading

    net = bibaudit.Net(offline=False)
    net.down.add("export.arxiv.org")
    seen = {}

    def work(name, url):
        net.begin()
        net.get(url)
        seen[name] = net.missed()

    t = threading.Thread(target=work, args=("arxiv", "https://export.arxiv.org/api/query?id_list=x"))
    t.start()
    t.join()
    net.begin()
    seen["main"] = net.missed()
    assert seen == {"arxiv": True, "main": False}


def test_crossref_search_puts_the_author_in_the_citation_string():
    """A separate `query.author` returned nothing for "Boguna" (Crossref: "Boguñá")
    and for a Dheeraj whom Crossref files under "M N"."""
    import json

    net = _CountingNet({})
    net.get = lambda url, **kw: (net.urls.append(url), json.dumps({"message": {"items": []}}))[1]
    bibaudit._crossref_search(net, "Models of social networks", "Boguna", context="Physical Review E 2004")
    (url,) = net.urls
    assert "query.author" not in url and "Boguna" in url and "Physical+Review+E+2004" in url


def test_datacite_title_search_ands_the_title_words():
    import json

    net = _CountingNet({})
    net.get = lambda url, **kw: (net.urls.append(url), json.dumps({"data": []}))[1]
    bibaudit.arxiv_search(net, "Intriguing properties of neural networks")
    assert "titles.title%3A%28Intriguing+AND+properties+AND+neural+AND+networks%29" in net.urls[0]


def test_normalise_moves_a_web_pages_note_url_to_url():
    entry = bibaudit.parse_bib(r"@misc{m, title={Site}, author={Doe, J.}, note={\url{https://a.b/c}}}")["entries"][0]
    fixed, _ = bibaudit.normalise_entry(entry)
    assert fixed["fields"].get("url") == "https://a.b/c" and "note" not in fixed["fields"]


def test_apply_record_never_re_dates_a_book():
    entry = {
        "type": "book",
        "key": "k",
        "fields": {"title": "Bayesian Reasoning and Machine Learning", "year": "2011", "publisher": "CUP"},
    }
    rec = _record(
        title="Bayesian Reasoning and Machine Learning",
        year=2012,
        type="book",
        publisher="Cambridge University Press",
        extra={"years": [2012]},
    )
    fixed, _ = bibaudit.apply_record(entry, {"status": "verified", "record": rec, "ids": {}}, [])
    assert fixed["fields"]["year"] == "2011"


def test_slot_holder_checks_pmlr_volumes_of_the_claimed_venue_year_only():
    import re as _re

    index = '<li><a href="v202"><b>Volume 202</b></a> Proceedings of ICML 2023</li><li><a href="v40"><b>Volume 40</b></a> COLT 2015 Proceedings</li>'
    volume = (
        "@inproceedings{p1, title={A Real Paper}, author={Roe, Rich}, booktitle={ICML}, year={2023}, pages={100--110}}"
    )
    net = _PageNet({
        "https://proceedings.mlr.press/": index,
        "https://proceedings.mlr.press/v202/assets/bib/bibliography.bib": volume,
        "https://proceedings.mlr.press/v40/assets/bib/bibliography.bib": volume,
    })
    venues = [
        {
            "acronym": "ICML",
            "type": "inproceedings",
            "canonical": "ICML",
            "re": _re.compile("machine learning"),
            "adapter": "pmlr:ICML",
        }
    ]

    def claim(vol):
        fields = {
            "title": "A Fabricated Title",
            "author": "Doe, Jane",
            "year": "2023",
            "booktitle": "International Conference on Machine Learning",
            "volume": vol,
            "pages": "100--110",
        }
        entry = {"type": "inproceedings", "key": "k", "fields": fields}
        return bibaudit._slot_holder(net, bibaudit.entry_view(entry), entry, venues)

    assert claim("202")["title"] == "A Real Paper"
    assert claim("40") is None, "volume 40 is COLT 2015's, not ICML 2023's"


# ── bib-audit.fullest_names ─────────────────────────────────────────────────
# The rule: a name is completed only from what a record of the same work (or
# its author registry) spells, with every aligned initial agreeing; nothing is
# inferred and nobody is reordered.


def _registry(names):
    return [[{**a, "_source": "openalex"} for a in bibaudit.split_authors(names)]]


@pytest.mark.parametrize(
    "entry, registry, expected",
    [
        ("J. v. Neumann", "John von Neumann", "von Neumann, John"),
        ("J. V. Neumann", "John von Neumann", "von Neumann, John"),
        (
            "Bonanno, G. and Caldarelli, G.",
            "Giovanni Bonanno and Guido Caldarelli",
            "Bonanno, Giovanni and Caldarelli, Guido",
        ),
        ("Buzsaki, G.", "György Buzsáki", "Buzsáki, György"),
        ("Lecun, Y.", "Yann LeCun", "LeCun, Yann"),
        ("Dupont, J.-P.", "Jean-Pierre Dupont", "Dupont, Jean-Pierre"),
        ("van der Waals, J. D.", "Johannes Diderik van der Waals", "van der Waals, Johannes Diderik"),
    ],
)
def test_fullest_names_completes_from_attested_spellings(entry, registry, expected):
    names, notes = bibaudit.fullest_names(bibaudit.split_authors(entry), _registry(registry))
    assert bibaudit.authors_field(names) == expected and notes


@pytest.mark.parametrize(
    "entry, registry",
    [
        ("Smith, J.", "Robert Smith"),  # initials disagree: another person
        ("Hopfield, John J", "J. J. Hopfield"),  # the entry is already the fuller
        ("Turing, A. M.", "A. M. TURING"),  # capitals are not information
        ("Wong, Eric and Rice, Leslie", "Leslie Rice and Eric Wong"),  # order is never touched
    ],
)
def test_fullest_names_leaves_what_no_record_improves(entry, registry):
    before = bibaudit.split_authors(entry)
    names, notes = bibaudit.fullest_names(before, _registry(registry))
    assert bibaudit.authors_field(names) == bibaudit.authors_field(before) and not notes


# ── bib-audit: optional credentials, degrading when refused ────────────────


def test_credentials_come_from_the_environment_and_are_optional(monkeypatch):
    for name in ("S2_API_KEY", "OPENALEX_API_KEY", "OPENREVIEW_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    assert bibaudit.credentials() == {}
    monkeypatch.setenv("S2_API_KEY", "k1")
    monkeypatch.setenv("OPENALEX_API_KEY", "k2")
    monkeypatch.setenv("OPENREVIEW_TOKEN", "t3")
    auth = bibaudit.credentials()
    assert auth["api.semanticscholar.org"] == {"x-api-key": "k1"}
    assert auth["api.openalex.org"] == {"Authorization": "Bearer k2"}
    assert auth["api.openreview.net"] == auth["api2.openreview.net"] == {"Authorization": "Bearer t3"}


def test_a_refused_credential_is_dropped_and_the_request_repeated_anonymously(monkeypatch):
    import email.message
    import io
    import urllib.error

    sent = []

    class _Resp(io.BytesIO):
        headers = email.message.Message()

    def fake_urlopen(req, timeout=None):
        sent.append(dict(req.header_items()))
        if req.get_header("X-api-key"):
            raise urllib.error.HTTPError(req.full_url, 403, "Forbidden", email.message.Message(), None)
        return _Resp(b'{"ok": true}')

    monkeypatch.setattr(bibaudit.urllib.request, "urlopen", fake_urlopen)
    net = bibaudit.Net(auth={"api.semanticscholar.org": {"x-api-key": "bad"}})
    net.last["api.semanticscholar.org"] = -1e9
    assert net.get_json("https://api.semanticscholar.org/graph/v1/paper/x") == {"ok": True}
    assert "X-api-key" in sent[0] and "X-api-key" not in sent[1]
    assert "api.semanticscholar.org" not in net.auth and "credentials rejected" in net.notes[0]


# ── bib-audit: Semantic Scholar, DBLP and OpenAlex records ─────────────────


def test_s2_record_reads_a_conference_paper_and_an_arxiv_only_one():
    conf = bibaudit._s2_record({
        "paperId": "p",
        "title": "Deep Residual Learning for Image Recognition",
        "year": 2016,
        "publicationVenue": {"name": "Computer Vision and Pattern Recognition", "type": "conference"},
        "journal": {
            "name": "2016 IEEE Conference on Computer Vision and Pattern Recognition (CVPR)",
            "pages": "770-778",
        },
        "externalIds": {"DOI": "10.1109/CVPR.2016.90", "DBLP": "conf/cvpr/HeZRS16"},
        "authors": [{"name": "Kaiming He"}],
        "publicationTypes": ["Conference"],
    })
    assert (conf["type"], conf["pages"], conf["doi"], conf["extra"]["dblp"]) == (
        "inproceedings",
        "770--778",
        "10.1109/cvpr.2016.90",
        "conf/cvpr/HeZRS16",
    )
    pre = bibaudit._s2_record({
        "paperId": "q",
        "title": "T",
        "venue": "arXiv.org",
        "journal": {"name": "ArXiv", "volume": "abs/2301.00001"},
        "authors": [],
    })
    assert (pre["type"], pre["venue"], pre["volume"]) == ("preprint", None, None)


def test_dblp_record_reads_order_suffixes_and_arxiv_published_proceedings():
    b = {
        "pub": {"value": "https://dblp.org/rec/journals/corr/KingmaW13"},
        "t": {"value": "Auto-Encoding Variational Bayes."},
        "venue": {"value": "ICLR"},
        "year": {"value": "2014"},
        "au": {"value": "2=Max Welling|1=Diederik P. Kingma 0001"},
    }
    rec = bibaudit._dblp_record(b)
    assert (rec["type"], rec["venue"], rec["year"], rec["title"]) == (
        "inproceedings",
        "ICLR",
        2014,
        "Auto-Encoding Variational Bayes",
    )
    assert [bibaudit.join_name(a) for a in rec["authors"]] == ["Kingma, Diederik P.", "Welling, Max"]
    corr = bibaudit._dblp_record({
        **b,
        "pub": {"value": "https://dblp.org/rec/journals/corr/abs-1"},
        "venue": {"value": "CoRR"},
    })
    assert (corr["type"], corr["venue"]) == ("preprint", None)


def test_openalex_records_carry_byline_and_registry_names_in_one_unicode_form():
    w = {
        "doi": "https://doi.org/10.1103/PhysRevE.70.056122",
        "display_name": "Models of social networks",
        "publication_year": 2004,
        "biblio": {"volume": "70", "first_page": "056122", "last_page": "056122"},
        "authorships": [{"raw_author_name": "A. Díaz-Guilera", "author": {"display_name": "Albert Dı́az‐Guilera"}}],
    }
    byline, registry = bibaudit._openalex_records(w)
    assert byline["doi"] == "10.1103/physreve.70.056122"
    assert bibaudit.join_name(byline["authors"][0]) == "Díaz-Guilera, A."
    assert bibaudit.join_name(registry["authors"][0]) == "Díaz-Guilera, Albert"


@pytest.mark.parametrize(
    "a, b, agree",
    [
        ("PLoS ONE", "PLOS ONE", True),
        ("Phys. Rev. E", "Physical Review E", True),
        ("Physical Review E: Statistical, Nonlinear, and Soft Matter Physics", "Physical Review E", True),
        ("Journal of Machine Learning Research", "J. Mach. Learn. Res.", True),
        ("Nature", "Nature Physics", False),
        ("Physical Review A", "Physical Review E", False),
        ("Proc. Natl. Acad. Sci.", "Proceedings of the National Academy of Sciences", True),
        ("PNAS", "Proceedings of the National Academy of Sciences", True),
        ("The Bulletin of Mathematical Biophysics", "Bulletin of Mathematical Biology", False),
        ("The European Physical Journal B - Condensed Matter", "The European Physical Journal B", False),
        ("Chemical Physics", "Chemistry Physics", False),
    ],
)
def test_venues_agree(a, b, agree):
    assert bibaudit._venues_agree(a, b) is agree


def test_a_keyless_best_effort_source_being_down_leaves_entries_checked():
    """Semantic Scholar without a key answers 429 and drops out of every run; that
    must not turn every entry that asked it into `unchecked` (it hid two
    fabricated-slot findings). With a key, its absence does count."""
    for auth, counted in (({}, False), ({"api.semanticscholar.org": {"x-api-key": "k"}}, True)):
        net = bibaudit.Net(auth=auth)
        net.down.add("api.semanticscholar.org")
        net.begin()
        net.get("https://api.semanticscholar.org/graph/v1/paper/search/match?query=x")
        assert net.missed() is counted


def test_apply_record_does_not_keep_a_venue_of_another_kind():
    """A DBLP proceedings record for an entry filed as a journal article: the
    entry's journal name must not become the booktitle."""
    entry = {
        "type": "article",
        "key": "k",
        "fields": {
            "title": "Adversarial Examples",
            "journal": "Artificial Intelligence Safety and Security",
            "year": "2017",
        },
    }
    rec = _record(source="dblp", title="Adversarial Examples", type="inproceedings", venue="Some Conference", year=2017)
    fixed, _ = bibaudit.apply_record(entry, {"status": "verified", "record": rec, "ids": {}}, [])
    assert fixed["fields"].get("booktitle") != "Artificial Intelligence Safety and Security"


def test_apply_record_leaves_a_preprints_own_arxiv_fields_unlogged():
    entry = {
        "type": "misc",
        "key": "k",
        "fields": {
            "title": "Gaussian Error Linear Units (GELUs)",
            "eprint": "1606.08415",
            "archiveprefix": "arXiv",
            "primaryclass": "cs.LG",
            "year": "2016",
        },
    }
    rec = _record(
        source="arxiv",
        id="1606.08415",
        title="Gaussian Error Linear Units (GELUs)",
        type="preprint",
        arxiv="1606.08415",
        year=2016,
        extra={"category": "cs.LG"},
    )
    _, changes = bibaudit.apply_record(
        entry, {"status": "preprint", "record": rec, "ids": {}, "reference_year": 2016}, []
    )
    assert not [c for c in changes if c["field"] in ("eprint", "archiveprefix", "primaryclass")]


@pytest.mark.parametrize("etype", ["software", "misc"])
def test_a_code_host_is_not_a_venue(etype):
    src = (
        "@"
        + etype
        + r"{t, title={TorchVision}, author={{TorchVision maintainers}}, year={2016}, journal={GitHub repository}, publisher={GitHub}, howpublished={\url{https://github.com/pytorch/vision}}}"
    )
    fixed, _ = bibaudit.normalise_entry(bibaudit.parse_bib(src)["entries"][0])
    assert "journal" not in fixed["fields"] and "publisher" not in fixed["fields"]
    assert bibaudit.is_web(fixed)


def test_a_biorxiv_preprint_keeps_its_own_form():
    """Crossref's posted-content record verifies a bioRxiv entry: metadata only,
    no arXiv eprint fields (there is no arXiv id to build them from)."""
    entry = {
        "type": "article",
        "key": "k",
        "fields": {
            "title": "Brain-Score: Which network is most brain-like?",
            "journal": "bioRxiv",
            "year": "2018",
            "author": "Schrimpf, Martin",
        },
    }
    rec = _record(
        source="crossref",
        id="10.1101/407007",
        title="Brain-Score: Which network is most brain-like?",
        type="preprint",
        venue="bioRxiv",
        year=2018,
        authors=bibaudit.split_authors("Schrimpf, Martin and Kubilius, Jonas"),
        extra={"years": [2018]},
    )
    fixed, _ = bibaudit.apply_record(entry, {"status": "verified", "record": rec, "ids": {}}, [])
    assert fixed["type"] == "article" and fixed["fields"]["journal"] == "bioRxiv" and "eprint" not in fixed["fields"]
    assert bibaudit._preprint_entry(bibaudit.entry_view(entry), rec)


# ── bib-audit: review round (H1–H4, M2, M3, M7, L2, L4) ─────────────────────


def test_names_are_completed_only_from_bylines():
    """H1: the paper's byline decides; a registry or DBLP profile name never does."""
    entry = {"type": "article", "key": "k", "fields": {"title": "T", "author": "Das, Abhishek"}}
    registry = {"source": "openalex-registry", "authors": bibaudit.split_authors("Abhishek Kumar Das")}
    dblp = {"source": "dblp", "authors": bibaudit.split_authors("Abhishek Kumar Das")}
    assert bibaudit.complete_names(entry, [registry, dblp]) == (entry, [])
    byline = {"source": "crossref", "authors": bibaudit.split_authors("Das, Abhishek K.")}
    fixed, changes = bibaudit.complete_names(entry, [byline])
    assert fixed["fields"]["author"] == "Das, Abhishek K." and changes


def test_a_profile_source_does_not_rewrite_an_intact_author_list():
    entry = {
        "type": "inproceedings",
        "key": "k",
        "fields": {"title": "Adam", "author": "Kingma, Diederik and Ba, Jimmy", "year": "2015"},
    }
    rec = _record(
        source="dblp",
        title="Adam",
        type="inproceedings",
        venue="ICLR",
        year=2015,
        authors=bibaudit.split_authors("Diederik P. Kingma and Jimmy Ba"),
    )
    fixed, _ = bibaudit.apply_record(entry, {"status": "verified", "record": rec, "ids": {}}, [])
    assert fixed["fields"]["author"] == "Kingma, Diederik and Ba, Jimmy"


def test_initials_written_together_are_not_duplicated():
    """H2: "David GT" + a byline "David G. T." gave "David GT T."."""
    names, _ = bibaudit.fullest_names(
        bibaudit.split_authors("Barrett, David GT"),
        [[{**a, "_source": "crossref"} for a in bibaudit.split_authors("Barrett, David G. T.")]],
    )
    assert bibaudit.authors_field(names) == "Barrett, David G. T."


def test_disagreeing_bylines_are_listed_for_review():
    evidence = [
        {"source": "crossref", "authors": bibaudit.split_authors("Smith, Jane")},
        {"source": "arxiv", "authors": bibaudit.split_authors("Smith, Robert")},
    ]
    assert bibaudit.name_conflicts(bibaudit.split_authors("Smith, J."), evidence)


def test_a_cache_from_other_rules_is_not_trusted():
    """H3: entries settled under older rules are audited again."""
    old = {"version": 1, "rules": "older", "entries": {"h": {"status": "verified"}}}
    assert bibaudit.usable_cache(old)["entries"] == {}
    current = {"version": 1, "rules": bibaudit.RULES_VERSION, "entries": {"h": {"status": "verified"}}}
    assert bibaudit.usable_cache(current)["entries"] == {"h": {"status": "verified"}}


def test_a_conference_paper_and_its_same_year_journal_version_are_two_works():
    """H4: same title, first author and year, different venues: not merged."""
    conf = bibaudit.parse_bib(
        "@inproceedings{a, title={Deep Things}, author={Doe, Jane}, year={2020}, booktitle={Advances in Neural Information Processing Systems}}"
    )["entries"][0]
    jour = bibaudit.parse_bib(
        "@article{b, title={Deep Things}, author={Doe, Jane}, year={2020}, journal={Journal of Machine Learning Research}}"
    )["entries"][0]
    pre = bibaudit.parse_bib(
        "@misc{c, title={Deep Things}, author={Doe, Jane}, year={2020}, eprint={2001.00001}, archiveprefix={arXiv}}"
    )["entries"][0]
    groups, _ = bibaudit.dedupe([conf, jour], [None, None])
    assert len(groups) == 2
    groups, _ = bibaudit.dedupe([conf, pre], [None, None])
    assert len(groups) == 1


def test_pinned_keys_survive_and_fresh_keys_avoid_them():
    """M2: a key assigned by an earlier run stays; a new entry gets a fresh key
    that cannot collide with it."""
    e = lambda k, t: {
        "type": "article",
        "key": k,
        "fields": {"author": "Doe, Jane", "title": t, "year": "2020", "journal": "Nature"},
    }
    keys = bibaudit.pin_keys([e("x", "Robust things"), e("y", "Robust stuff")], [], ["Doe2020Robust", None])
    assert keys[0] == "Doe2020Robust" and keys[1] != "Doe2020Robust" and keys[1].startswith("Doe2020Robust")


def test_harmonise_names_uses_an_unambiguous_fuller_form_only():
    a = bibaudit.parse_bib("@article{a, title={A}, author={LeCun, Y.}, year={2015}}")["entries"][0]
    b = bibaudit.parse_bib("@article{b, title={B}, author={LeCun, Yann}, year={2016}}")["entries"][0]
    z1 = bibaudit.parse_bib("@article{c, title={C}, author={Zhang, Y.}, year={2017}}")["entries"][0]
    z2 = bibaudit.parse_bib("@article{d, title={D}, author={Zhang, Yu}, year={2018}}")["entries"][0]
    z3 = bibaudit.parse_bib("@article{e, title={E}, author={Zhang, Yi}, year={2019}}")["entries"][0]
    out, _ = bibaudit.harmonise_names([a, b, z1, z2, z3])
    assert out[0]["fields"]["author"] == "LeCun, Yann"
    assert out[2]["fields"]["author"] == "Zhang, Y.", "Yu or Yi: ambiguous, left alone"


@pytest.mark.parametrize(
    "title, protected",
    [
        (
            "GPTs are GPTs: Labor market impact potential of LLMs",
            "{GPTs} are {GPTs}: Labor market impact potential of {LLMs}",
        ),
        ("A 3D U-Net for users", "A {3D} {U-Net} for users"),
        ("Deep Residual Learning for Image Recognition", "Deep Residual Learning for Image Recognition"),
        ("{BERT}: Pre-training", "{BERT}: Pre-training"),
        (r"Isometries of $\ell_p$-norm on ImageNet", r"Isometries of $\ell_p$-norm on {ImageNet}"),
    ],
)
def test_protect_title(title, protected):
    assert bibaudit.protect_title(title) == protected


def test_journal_names_come_from_one_authority_then_the_alias_table():
    """M7: the name Crossref's latest articles carry, by ISSN (found through OpenAlex
    when the entry has none); the table only when that authority has nothing."""
    import json
    import urllib.parse

    class _Net(_CountingNet):
        missing = False

        def get(self, url, **_):
            self.urls.append(url)
            if "api.crossref.org/journals/1539-3755/works" in url:
                return json.dumps({"message": {"items": [{"container-title": ["Physical Review E"]}] * 3}})
            if "api.crossref.org/journals/0007-4985/works" in url:
                return json.dumps({"message": {"items": [{"container-title": ["Bulletin of Mathematical Biology"]}]}})
            if "api.crossref.org/journals/2047-7538/works" in url:
                return json.dumps({"message": {"items": [{"container-title": ["Light: Science &amp; Applications"]}]}})
            if "api.openalex.org/sources" in url and "Light" in urllib.parse.unquote_plus(url):
                src = {"display_name": "Light Science & Applications", "issn_l": "2047-7538", "issn": ["2047-7538"]}
                return json.dumps({"results": [src]})
            return json.dumps({"results": [], "message": {"items": []}})

        def begin(self):
            pass

        def missed(self):
            return self.missing

    net = _Net({})
    items = [
        ("Phys. Rev. E", ["1539-3755"]),
        ("Light: Science & Applications", []),
        ("Zh. Eksp. Teor. Fiz.", []),
        ("Obscure Letters", []),
        ("The Bulletin of Mathematical Biophysics", ["0007-4985"]),  # renamed since: keeps the name it appeared under
    ]
    assert bibaudit.canonical_journals_with_source(net, items, []) == [
        ("Physical Review E", "crossref:issn"),
        ("Light: Science & Applications", "crossref:name"),
        ("Zhurnal Eksperimental'noi i Teoreticheskoi Fiziki", "journals.tsv"),
        (None, None),
        (None, None),
    ]
    net.missing = True  # Crossref out of the run: nothing is decided, not even from the table
    assert bibaudit.canonical_journals_with_source(net, [("Zh. Eksp. Teor. Fiz.", ["0044-4510"])], []) == [
        (None, "unreachable")
    ]


def test_semantic_scholar_is_not_asked_without_a_key():
    class _Keyless(_CountingNet):
        def __init__(self):
            super().__init__({})
            self.auth = {}

    net = _Keyless()
    assert bibaudit.s2_batch(net, ["DOI:10.1/x"]) == {} and bibaudit.s2_match(net, "A title") == [] and not net.urls


def test_detex_reads_text_symbol_commands():
    """L4: bibtex-tidy writes "®" as "\\textregistered{}"; both must compare equal."""
    assert (
        bibaudit.detex(r"Foundations and Trends\textregistered{} in Machine Learning")
        == "Foundations and Trends® in Machine Learning"
    )


def test_same_surname_co_authors_are_not_confused():
    """Kendall D. G. and W. S., the Mosers, the Leutgebs: a byline name belongs to
    the co-author it fits, never to another author with the same surname."""
    entry = bibaudit.split_authors("Moser, E. I. and Moser, M.-B. and Kendall, David G. and Kendall, Wilfrid S.")
    byline = [
        {
            "source": "crossref",
            "authors": bibaudit.split_authors(
                "Edvard I. Moser and May-Britt Moser and David G. Kendall and Wilfrid S. Kendall"
            ),
        }
    ]
    assert bibaudit.name_conflicts(entry, byline) == []
    names, _ = bibaudit.fullest_names(entry, [[{**a, "_source": "crossref"} for a in byline[0]["authors"]]])
    assert [bibaudit.join_name(n) for n in names[:2]] == ["Moser, Edvard I.", "Moser, May-Britt"]


def test_a_name_two_co_authors_could_complete_is_left_alone():
    names, notes = bibaudit.fullest_names(
        bibaudit.split_authors("Zhang, Y."),
        [[{**a, "_source": "crossref"} for a in bibaudit.split_authors("Yu Zhang and Yi Zhang")]],
    )
    assert bibaudit.authors_field(names) == "Zhang, Y." and not notes


def test_byline_printed_surname_first_is_read_surname_first():
    """A whole byline in "Surname I." form is reordered; one such name among "First
    Last" names is a one-letter surname (OpenAlex prints "Weinan E.") and is not."""
    flipped = bibaudit._full_names(["Cavazzoni S.", "Razzoli L.", "Paris M. G. A."])
    assert [(n["last"], n["first"]) for n in flipped] == [("Cavazzoni", "S."), ("Razzoli", "L."), ("Paris", "M. G. A.")]
    as_written = bibaudit._full_names(["Zehao Don", "Weinan E.", "Chao Ma", "J. Smith", "Smith, J.", "Wei LEE"])
    assert [(n["last"], n["first"]) for n in as_written] == [
        ("Don", "Zehao"),
        ("E.", "Weinan"),
        ("Ma", "Chao"),
        ("Smith", "J."),
        ("Smith", "J."),
        ("LEE", "Wei"),
    ]
    assert bibaudit._full_names(["Weinan E."])[0]["last"] == "E."


def test_content_hash_ignores_quote_style():
    """bibtex-tidy writes "O’Gara" as "O'Gara": the audited entry must still hit the cache."""

    def e(name):
        return {
            "type": "article",
            "key": "k",
            "fields": {"author": f"{name}, Aidan", "title": "AI deception", "year": "2024"},
        }

    assert bibaudit.content_hash(e("O’Gara")) == bibaudit.content_hash(e("O'Gara"))
    assert bibaudit.content_hash(e("O’Gara")) != bibaudit.content_hash(e("OGara"))


@pytest.mark.parametrize(
    "field, flagged",
    [
        ("Devries , Paul L. Hasburn, Javier E.", ['"Paul L. Hasburn" is not a name suffix']),
        ("Smith, John, Doe, Jane", ["3 commas in one name"]),
        ("King, Jr., Martin Luther and Gates, III, William H. and Smith, {Jr.}, John", []),
        ("Doe, Jane and Roe, Richard and others", []),
    ],
)
def test_malformed_names_flags_a_missing_and(field, flagged):
    out = bibaudit.malformed_names(field)
    assert len(out) == len(flagged) and all(f in o for f, o in zip(flagged, out, strict=True))


def test_audit_lists_a_name_bibtex_misreads(tmp_path):
    bib = tmp_path / "refs.bib"
    bib.write_text(
        "@book{d, author = {Devries , Paul L. Hasburn, Javier E.}, title = {A First Course in Computational Physics},"
        " publisher = {Wiley}, year = 2011}\n"
    )
    s = bibaudit.audit(bib, offline=True, run_tidy=False, run_validate=False)
    assert [x["key"] for x in s["name_conflicts"]] == ["d"] and "missing" in s["name_conflicts"][0]["conflicts"][0]


def test_validation_style_is_the_one_the_tex_names(tmp_path):
    (tmp_path / "mine.bst").write_text("% a style\n")
    (tmp_path / "other.bst").write_text("% commented out in the .tex\n")
    tex = tmp_path / "main.tex"
    tex.write_text("% \\bibliographystyle{other}\n\\bibliography{refs}\n\\bibliographystyle{mine}\n")
    assert bibaudit.validation_style(None, [tex]) == (str(tmp_path / "mine.bst"), "\\bibliographystyle in the .tex")
    assert bibaudit.validation_style(str(tmp_path / "mine.bst"), [tex]) == (str(tmp_path / "mine.bst"), "given")


@pytest.mark.parametrize(
    "tex, style",
    [
        pytest.param(("main.tex", "typo.tex"), None, id="missing-tex"),
        pytest.param(
            (),
            "no-such-style-xyz",
            id="unknown-style",
            marks=pytest.mark.skipif(not __import__("shutil").which("kpsewhich"), reason="needs TeX's kpsewhich"),
        ),
    ],
)
def test_audit_with_a_bad_argument_writes_nothing(tmp_path, tex, style):
    """A mistyped .tex path or style must stop the audit before the .bib is
    rekeyed, or the citations would be left pointing at keys that no longer exist."""
    bib = tmp_path / "refs.bib"
    bib.write_text("@article{a, author = {Doe, Jane}, title = {A title}, journal = {Nature}, year = 2020}\n")
    (tmp_path / "main.tex").write_text("\\cite{a}\n")
    before = sorted(p.name for p in tmp_path.iterdir())
    with pytest.raises(FileNotFoundError, match="nothing was written"):
        bibaudit.audit(bib, tuple(tmp_path / t for t in tex), style=style, offline=True, run_tidy=False)
    assert sorted(p.name for p in tmp_path.iterdir()) == before


# ── bib-audit against a fake web ────────────────────────────────────────────


class _Web:
    """A fake internet at the `urlopen` boundary: the first route whose fragment
    occurs in the (unquoted) URL answers — a dict or list as JSON; anything else
    is a 404."""

    def __init__(self, routes):
        self.routes, self.urls = routes, []

    def __call__(self, req, timeout=None):
        import email.message
        import io
        import json
        import urllib.error
        import urllib.parse

        class _Body(io.BytesIO):
            headers = email.message.Message()

        url = urllib.parse.unquote_plus(req.full_url)
        self.urls.append(url)
        for frag, body in self.routes:
            if frag in url:
                return _Body(json.dumps(body).encode())
        raise urllib.error.HTTPError(req.full_url, 404, "Not Found", email.message.Message(), None)


class _NoGap(dict):
    def get(self, key, default=None):
        return 0.0


@pytest.fixture
def web(monkeypatch, tmp_path):
    """Install a `_Web` from routes; the HTTP cache is a scratch directory, no
    credential is set and requests are not paced."""
    for var in ("S2_API_KEY", "OPENALEX_API_KEY", "OPENREVIEW_USERNAME", "OPENREVIEW_PASSWORD", "OPENREVIEW_TOKEN"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "http-cache"))
    monkeypatch.setattr(bibaudit, "_GAP", _NoGap())

    def install(routes):
        w = _Web(routes)
        monkeypatch.setattr(bibaudit.urllib.request, "urlopen", w)
        return w

    return install


def _cr_item(doi, kind, title, authors, year, **kw):
    """A Crossref work as the API returns it; `authors` as "Given Family" strings."""
    return {
        "DOI": doi,
        "type": kind,
        "title": [title],
        "author": [{"given": a.rsplit(" ", 1)[0], "family": a.rsplit(" ", 1)[1]} for a in authors],
        "issued": {"date-parts": [[year]]},
        **kw,
    }


@pytest.mark.parametrize(
    "entry, own, other",
    [
        (  # Crossref's record of a discussion piece on the paper, by a namesake
            (
                "@article{k, author = {David G. Kendall}, title = {A Survey of the Statistical Theory of Shape},"
                " journal = {Statistical Science}, year = 1989, volume = 4, number = 2, pages = {87--99}}"
            ),
            _cr_item(
                "10.1214/ss/1177012582",
                "journal-article",
                "A Survey of the Statistical Theory of Shape",
                ["David G. Kendall"],
                1989,
                **{"container-title": ["Statistical Science"], "volume": "4", "issue": "2", "page": "87-99"},
            ),
            _cr_item(
                "10.1214/ss/1177012586",
                "journal-article",
                "[A Survey of the Statistical Theory of Shape]: Comment",
                ["Wilfrid S. Kendall"],
                1989,
                **{"container-title": ["Statistical Science"], "volume": "4", "issue": "2", "page": "99-101"},
            ),
        ),
        (  # a journal's review of the book, the reviewer among its authors
            (
                "@book{k, author = {DeVries, Paul L. and Hasbun, Javier E.}, title = {A First Course in"
                " Computational Physics}, publisher = {Jones and Bartlett}, year = 2011}"
            ),
            _cr_item(
                "10.9999/book",
                "book",
                "A First Course in Computational Physics",
                ["Paul L. DeVries", "Javier E. Hasbun"],
                2011,
                publisher="Jones and Bartlett",
            ),
            _cr_item(
                "10.9999/review",
                "journal-article",
                "A First Course in Computational Physics",
                ["Paul L. DeVries", "Robert P. Wolf"],
                2011,
                **{"container-title": ["Computers in Physics"]},
            ),
        ),
    ],
)
def test_name_evidence_is_the_work_itself_not_a_piece_about_it(web, entry, own, other):
    web([("api.crossref.org/works?", {"message": {"items": [own, other]}})])
    e = bibaudit.parse_bib(entry)["entries"][0]
    res = bibaudit.lookup_entry(bibaudit.Net(), e, bibaudit.load_venues(), {"crossref": {}, "arxiv": {}})
    assert [r["id"] for r in res["evidence"]] == [own["DOI"]]


_PLOS = _cr_item(
    "10.1371/journal.pone.0002148",
    "journal-article",
    "Neural networks with realistic connectivity",
    ["Roberto F. Galán"],
    2008,
    **{"container-title": ["PLoS ONE"], "ISSN": ["1932-6203"], "volume": "3", "issue": "5", "page": "e2148"},
)


def test_a_second_audit_of_an_audited_bib_changes_nothing(web, tmp_path):
    """The input normaliser and the journal authority must agree ("PLOS One"), or
    the audited entry misses the cache and is looked up again on every run."""
    web([
        ("api.crossref.org/journals/1932-6203/works", {"message": {"items": [{"container-title": ["PLOS One"]}]}}),
        ("api.crossref.org/works?", {"message": {"items": [_PLOS]}}),
    ])
    bib = tmp_path / "refs.bib"
    bib.write_text(
        "@article{g, author = {Gal{\\'a}n, Roberto F.}, title = {Neural networks with realistic connectivity},"
        " journal = {PloS one}, year = 2008, volume = 3, number = 5, pages = {e2148},"
        " doi = {10.1371/journal.pone.0002148}}\n"
    )
    first = bibaudit.audit(bib, run_tidy=False, run_validate=False)
    audited = bib.read_text()
    second = bibaudit.audit(bib, run_tidy=False, run_validate=False)
    assert first["status"] == {"corrected": 1} and "PLOS One" in audited
    assert second["status"] == {"cached": 1} and bib.read_text() == audited


def test_byline_name_conflicts_are_listed_again_on_a_cached_run(web, tmp_path):
    """A cached entry is not looked up, so it has no bylines to compare: the
    conflict found by the run that settled it must still be listed."""
    oa = {
        "doi": "https://doi.org/10.1371/journal.pone.0002148",
        "display_name": "Neural networks with realistic connectivity",
        "publication_year": 2008,
        "authorships": [{"raw_author_name": "Roberto M. Galán", "author": {"display_name": "Roberto M. Galán"}}],
    }
    web([
        ("api.crossref.org/journals/1932-6203/works", {"message": {"items": [{"container-title": ["PLOS One"]}]}}),
        ("api.crossref.org/works?", {"message": {"items": [_PLOS]}}),
        ("api.openalex.org/works?", {"results": [oa]}),
    ])
    bib = tmp_path / "refs.bib"
    bib.write_text(
        "@article{g, author = {Gal{\\'a}n, R. F.}, title = {Neural networks with realistic connectivity},"
        " journal = {PLOS One}, year = 2008, volume = 3, number = 5, pages = {e2148},"
        " doi = {10.1371/journal.pone.0002148}}\n"
    )
    first = bibaudit.audit(bib, run_tidy=False, run_validate=False)
    second = bibaudit.audit(bib, run_tidy=False, run_validate=False)
    assert first["name_conflicts"] and second["status"] == {"cached": 1}
    assert second["name_conflicts"] == first["name_conflicts"]


@pytest.mark.parametrize(
    "a, b, merged",
    [
        ("G.", "Giovanni", "Giovanni"),  # an initial expands
        ("JF", "John Fitzgerald", "John Fitzgerald"),
        ("Ch.", "Charles", "Charles"),  # so does an abbreviation
        ("J.-P.", "Jean-Pierre", "Jean-Pierre"),
        ("Jose", "José", "José"),  # the same name, accented
        ("Ben", "Benedict", None),  # two written names are two names, never merged
        ("Nati", "Nathan", None),
        ("Roberto", "Rodrigo", None),
        ("J.", "M.", None),
    ],
)
def test_given_names_merge_only_initials_and_accents(a, b, merged):
    assert bibaudit._merge_given(a, b) == merged and bibaudit._merge_given(b, a) == merged
