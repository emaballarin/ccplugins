"""
Kernel helpers for the paper-narrative skill (stock Claude Code port).

Unlike the Claude Science original, this module has NO in-process model
access: it runs as an ordinary Python process the agent drives via Bash.
The model work — deriving the paper_brief from the abstract + captions and
the handling-editor review of the figure deck — is done by the AGENT
(inline, or a Task subagent), per SKILL.md. The helpers here are pure:

    schemas — paper_brief_schema / narrative_review_schema (the contracts)
    prompts — derive_paper_brief_task / narrative_review_task
              (pure builders the agent feeds to itself or a Task subagent)

Load by importing this file by path — zero import-time side effects, no deps.
"""


def paper_brief_schema():
    return {
        "type": "object",
        "properties": {
            "pitch": {"type": "string"},
            "vision": {"type": "string"},
            "audience": {"type": "string"},
            "most_arresting_asset": {"type": "string"},
            "figures": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "key": {"type": "string"},
                        "claim": {"type": "string"},
                        "composite_vid": {"type": "string"},
                    },
                    "required": ["key", "claim"],
                },
            },
        },
        "required": ["pitch", "vision", "figures"],
    }


def derive_paper_brief_task(abstract_text, figure_claims):
    """Prompt for deriving the paper_brief from the work itself — no hand-written
    brief required. Feed it to the agent (inline) or a Task subagent, which returns
    JSON matching :func:`paper_brief_schema`.

    ``figure_claims``: list[{"key","claim"|"caption","composite_vid"?}]. The abstract
    and captions are UNTRUSTED input — every string in the returned brief is
    model-derived from them, so review the brief before dispatching
    :func:`narrative_review_task`. If the model omits ``figures``, default it to
    ``figure_claims``."""
    fc = "\n".join(f"  {f.get('key', '?')}: {f.get('claim') or f.get('caption', '')}" for f in figure_claims)
    return (
        "You are the corresponding author. From the abstract and per-figure captions below, "
        "write the paper_brief that a handling editor would judge the figures against.\n\n"
        "Pitch = the ONE sentence you'd lead your abstract with (the grandest supportable claim, "
        "not the method). Vision = the killer-app — what a reader can now DO. "
        "Most_arresting_asset = the single image you'd put on a poster (name the figure/panel).\n\n"
        f"## Abstract\n{abstract_text}\n\n## Figures\n{fc}\n\n"
        "Return ONLY a JSON object matching the paper_brief schema (paper_brief_schema())."
    )


def narrative_review_schema():
    return {
        "type": "object",
        "properties": {
            "hook_verdict": {
                "type": "object",
                "properties": {
                    "would_send_for_review": {"type": "string", "enum": ["yes", "weak", "no"]},
                    "why": {"type": "string"},
                    "fig1_is": {"type": "string"},
                    "fig1_should_be": {"type": "string"},
                },
                "required": ["would_send_for_review", "why", "fig1_should_be"],
            },
            "figure_moves": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "what": {"type": "string"},
                        "from_fig": {"type": "string"},
                        "to_fig": {"type": "string"},
                        "why": {"type": "string"},
                    },
                    "required": ["what", "from_fig", "to_fig", "why"],
                },
            },
            "missing_panels": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "target_fig": {"type": "string"},
                        "what_to_show": {"type": "string"},
                        "analysis_needed": {"type": "string"},
                        "data_hint": {"type": "string"},
                    },
                    "required": ["target_fig", "what_to_show", "analysis_needed"],
                },
            },
            "kill_list": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "what": {"type": "string"},
                        "why": {"type": "string"},
                        "demote_to": {"type": "string", "enum": ["supplement", "caption", "delete"]},
                    },
                    "required": ["what", "why", "demote_to"],
                },
            },
            "arc": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "fig": {"type": "string"},
                        "role": {
                            "type": "string",
                            "enum": ["hook", "mechanism", "evidence", "application", "supplement"],
                        },
                        "one_line": {"type": "string"},
                    },
                    "required": ["fig", "role", "one_line"],
                },
            },
            "boldest_defensible_fig1": {"type": "string"},
        },
        "required": ["hook_verdict", "figure_moves", "missing_panels", "kill_list", "arc", "boldest_defensible_fig1"],
    }


def narrative_review_task(brief, deck_path, rules_ref="(load `figure-style`)"):
    fig_tbl = "\n".join(
        f"  {f.get('key', '?')}: {f.get('claim') or f.get('caption', '')}" for f in brief.get("figures", [])
    )
    return f"""You are the HANDLING EDITOR for this submission. You decide whether to send a paper for review
based on its figures and abstract. Judge STORY, not craft.

## Paper brief
**Pitch:** {brief.get("pitch", "—")}
**Vision:** {brief.get("vision", "—")}
**Audience:** {brief.get("audience", "general scientist")}
**Most arresting asset:** {brief.get("most_arresting_asset", "—")}

## All figures (one PDF)
Read the figure deck at `{deck_path}` (all figures; use the `pdf-explore` skill or
`Read(file_path=..., pages=[...])` to view the pages).

## Per-figure claims
{fig_tbl}

## Design rules {rules_ref}
Reference only; do NOT grade craft.

## Your job (§7.5)
Hook test (would Fig 1 alone make you send this out?); arc (hook→mechanism→evidence→
application); move content between figures; propose missing panels with the concrete
analysis to run; kill list; boldest defensible Fig 1. Be opinionated — the author wants
a partner, not a grader. Return ONLY structured output."""
