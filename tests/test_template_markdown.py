"""The shipped mf templates are structurally valid Markdown.

`/mf:setup` seeds a new machine's `~/.mindfunnel/` from these files and
`/mf:prime` stamps `project-AGENTS.md`; most of `SOUL.md`, `USER.md` and
`PROJECT.md` sits inside `<!-- … -->` example blocks. An unclosed comment swallows everything after it, a
nested one closes early and leaks its tail as visible text, and an unclosed code
fence turns the rest of the file into code. None of these fails loudly, so this
checks the structure directly: every comment closes before the next one opens,
a comment opened after text on a line closes on that line, no `-->` appears
outside a comment, and every fence closes (CommonMark: same character, at least
as long, at most three spaces of indent). Not checked: fences or comments inside
list items and block quotes, and code spans across lines — no template uses them.
"""

import re

import _util as u
import pytest

TEMPLATES = sorted((u.PLUGINS_DIR / "mindfunnel" / "templates").glob("*.md"))
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
CODE_SPAN = re.compile(r"(`+).+?\1")
LINE_BREAK = re.compile(r"\r\n|\r|\n")


def structure_errors(text: str) -> list[str]:
    """Unclosed, nested, stray or mid-line-spanning comments and unclosed fences, as `line N: …`."""
    errors: list[str] = []
    comment_line = fence_line = None
    fence, block_start = "", True
    for n, line in enumerate(LINE_BREAK.split(text.removeprefix("\ufeff")), start=1):
        if fence_line is not None:
            m = FENCE.match(line)
            if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence) and not m.group(2).strip(" \t"):
                fence_line = None
            continue
        m = FENCE.match(line) if comment_line is None else None
        if m and not (m.group(1)[0] == "`" and "`" in m.group(2)):
            fence, fence_line = m.group(1), n
            continue
        rest, first = line, True
        while rest:
            if comment_line is not None:
                close, reopen = rest.find("-->"), rest.find("<!--")
                if reopen != -1 and (close == -1 or reopen < close):
                    errors.append(f"line {n}: `<!--` inside the comment opened at line {comment_line}")
                if close == -1:
                    break
                comment_line, rest, first = None, rest[close + 3 :], False
            else:
                # Outside a comment, markers inside code spans are literal text.
                masked = CODE_SPAN.sub(lambda m: " " * len(m.group()), rest)
                open_, stray = masked.find("<!--"), masked.find("-->")
                if stray != -1 and (open_ == -1 or stray < open_):
                    errors.append(f"line {n}: `-->` outside any comment")
                if open_ == -1:
                    break
                lead, body = rest[:open_], rest[open_ + 4 :]
                if body.startswith((">", "->")):  # `<!-->` and `<!--->` are complete comments
                    rest, first = body.removeprefix("-").removeprefix(">"), False
                    continue
                block_start = first and len(lead) <= 3 and not lead.strip(" ")
                comment_line, rest, first = n, body, False
        if comment_line == n and not block_start:
            errors.append(f"line {n}: a comment opened after text must close on the same line")
    if comment_line is not None:
        errors.append(f"line {comment_line}: comment never closed")
    if fence_line is not None:
        errors.append(f"line {fence_line}: code fence never closed")
    return errors


def test_templates_found():
    assert TEMPLATES, "no templates/*.md found under plugins/mindfunnel"


@pytest.mark.parametrize("template", TEMPLATES, ids=u.rel)
def test_template_is_structurally_valid_markdown(template):
    errors = structure_errors(u.read_text(template))
    assert not errors, f"{u.rel(template)}:\n  " + "\n  ".join(errors)


CASES = [
    ("block comment over lines", "# T\n<!--\nmulti\n\nblank inside\n-->\nafter\n", []),
    ("two comments on one line", "a <!-- x --> b <!-- y --> c\n", []),
    ("markers in code spans", "use `<!--` to open and `-->` to close\n", []),
    ("backticks inside a comment", "<!-- a `-->` b\n", []),
    ("CommonMark empty comments", "<!-->\n<!--->\nafter\n", []),
    ("markers inside a fence", "```md\n<!-- not a comment\n```\n", []),
    ("CRLF and a BOM", "\ufeff```\r\ncode\r\n```\r\n<!-- c -->\r\n", []),
    ("backtick in info string: not a fence", "```x``` is code\n<!-- c -->\n", []),
    ("unclosed comment", "# T\n<!-- a\ntext\n", ["line 2: comment never closed"]),
    (
        "nested comment",
        "<!-- outer\n<!-- inner -->\nleak -->\n",
        ["line 2: `<!--` inside the comment opened at line 1", "line 3: `-->` outside any comment"],
    ),
    ("stray close", "text -->\n", ["line 1: `-->` outside any comment"]),
    ("comment opened after text", "## Who <!-- Name.\n-->\n", ["line 1: a comment opened after text must close"]),
    ("unclosed fence", "```py\ncode\n", ["line 1: code fence never closed"]),
    ("shorter closing fence", "````\ncode\n```\n", ["line 1: code fence never closed"]),
    ("other-character closing fence", "```\ncode\n~~~\n", ["line 1: code fence never closed"]),
    ("non-breaking space after the closer", "```\ncode\n```\u00a0\n<!-- c -->\n", ["line 1: code fence never closed"]),
]


@pytest.mark.parametrize(("text", "expected"), [c[1:] for c in CASES], ids=[c[0] for c in CASES])
def test_structure_errors_separates_valid_from_broken(text, expected):
    errors = structure_errors(text)
    assert len(errors) == len(expected), errors
    for error, phrase in zip(errors, expected):
        assert error.startswith(phrase), (error, phrase)
