"""ccsci kernels compile and still define every entrypoint their SKILL advertises.

The manifest is the maintained public contract: the functions each SKILL.md
tells the agent to call. Adding or renaming a kernel entrypoint means updating
both the SKILL.md and this manifest — the test enforces that they agree.
"""

import _util as u
import pytest

# skill name -> public entrypoints the SKILL.md instructs the agent to call
KERNEL_API: dict[str, set[str]] = {
    "figure-composer": {
        "panel_task",
        "compose_figure",
        "compose_crops",
        "composite_review_task",
        "derive_outline_task",
    },
    "figure-style": {
        "apply_figure_style",
        "focal_palette",
        "bar_with_points",
        "strip_with_median",
        "end_of_line_labels",
        "panel_letter",
        "set_frame",
        "panel_crops",
    },
    "literature-review": {
        "verify_dois",
        "to_bibtex",
        "bibtex_tidy",
        "expand_citations",
        "resolve_published",
        "resolve_published_all",
        "dedupe_records",
        "style_pass",
    },
    "paper-narrative": {
        "derive_paper_brief_task",
        "narrative_review_task",
        "paper_brief_schema",
        "narrative_review_schema",
    },
    "pdf-explore": {
        "pdf_pages",
        "pdf_outline",
        "pdf_tables",
        "pdf_images",
        "pdf_crop",
    },
}

_KERNELS = sorted(u.PLUGINS_DIR.glob("*/skills/*/kernel.py"))


def test_every_kernel_has_a_manifest_entry():
    """A new kernel must be added to KERNEL_API, so it can't slip past uncovered."""
    uncovered = sorted(k.parent.name for k in _KERNELS if k.parent.name not in KERNEL_API)
    assert not uncovered, f"kernel(s) with no KERNEL_API manifest in tests/test_kernels.py: {uncovered}"


@pytest.mark.parametrize("kernel", _KERNELS, ids=u.rel)
def test_kernel_contract(kernel):
    skill_name = kernel.parent.name
    expected = KERNEL_API.get(skill_name)
    if expected is None:
        pytest.skip(f"no manifest for {skill_name} (covered by the manifest test)")

    defined = u.top_level_names(kernel)  # also asserts the source parses
    skill_text = u.read_text(kernel.parent / "SKILL.md")

    missing_in_kernel = sorted(n for n in expected if n not in defined)
    assert not missing_in_kernel, f"{u.rel(kernel)} no longer defines advertised entrypoint(s): {missing_in_kernel}"

    missing_in_skill = sorted(n for n in expected if n not in skill_text)
    assert not missing_in_skill, (
        f"{u.rel(kernel.parent / 'SKILL.md')} no longer mentions manifest "
        f"entrypoint(s) (stale manifest?): {missing_in_skill}"
    )
