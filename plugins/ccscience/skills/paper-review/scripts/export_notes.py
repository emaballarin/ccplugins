"""Export review notes (Markdown) to an A4 PDF readable offline on an e-ink tablet.

Markdown → HTML with ``pandoc`` (GFM, tables) or, failing that, the ``markdown``
package; HTML → PDF with ``wkhtmltopdf`` or, failing that, ``weasyprint``. The
stylesheet is tuned for anchor tables: sans-serif cells, fixed column widths
for the three-column tables the skill produces, rows kept whole across pages.

Usage:
    python export_notes.py notes.md [notes.pdf] [--title "Review: X — notes"]
"""

import argparse
import html
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

CSS = """
@page { size: A4; margin: 14mm 13mm; }
body { font-family: "DejaVu Serif", Georgia, serif; font-size: 11.5pt; line-height: 1.38; color: #000; }
h1 { font-size: 18pt; margin: 0 0 4pt 0; }
h2 { font-size: 13pt; margin: 14pt 0 6pt 0; border-bottom: 1px solid #000; padding-bottom: 2pt; }
h3 { font-size: 11.5pt; margin: 10pt 0 4pt 0; }
p, li { margin: 0 0 5pt 0; }
ul, ol { padding-left: 16pt; margin: 4pt 0 8pt 0; }
table { border-collapse: collapse; width: 100%; margin: 6pt 0 10pt 0;
        font-family: "DejaVu Sans", Helvetica, sans-serif; font-size: 9.6pt; line-height: 1.3; }
th, td { border: 1px solid #555; padding: 3pt 4pt; vertical-align: top; text-align: left; }
th { background: #e6e6e6; }
tr { page-break-inside: avoid; }
table.c3 col:nth-child(1) { width: 20%; }
table.c3 col:nth-child(2) { width: 10%; }
table.c3 col:nth-child(3) { width: 70%; }
code, pre { font-family: "DejaVu Sans Mono", Menlo, monospace; font-size: 9pt; }
pre { white-space: pre-wrap; border: 1px solid #888; padding: 5pt; background: #f4f4f4; }
blockquote { margin: 4pt 0 8pt 10pt; padding-left: 8pt; border-left: 2px solid #888; }
hr { border: 0; border-top: 1px solid #aaa; margin: 10pt 0; }
"""


def md_to_html_body(md_path: Path) -> str:
    """Render Markdown to an HTML fragment, preferring pandoc's GFM tables."""
    if shutil.which("pandoc"):
        out = subprocess.run(
            ["pandoc", str(md_path), "-f", "gfm", "-t", "html5"],
            check=True,
            capture_output=True,
            text=True,
        )
        return out.stdout
    try:
        import markdown  # type: ignore[import-not-found]
    except ImportError as exc:
        raise SystemExit("export_notes: need either `pandoc` on PATH or `pip install markdown`") from exc
    return markdown.markdown(md_path.read_text(encoding="utf-8"), extensions=["tables", "fenced_code"])


def tag_three_column_tables(body: str) -> str:
    """Give every three-column table a fixed-width colgroup so the wide column wins.

    Tolerates attributes on the tags (older pandoc emits ``<tr class="header">``),
    merges into an existing ``class`` rather than adding a second one, and leaves
    alone any table that already carries a ``<colgroup>``: its widths were chosen
    by the renderer, and inline widths would override the stylesheet anyway.
    """

    def _fix(match: re.Match[str]) -> str:
        opening, rest = match.group(1), match.group(2)
        if "<colgroup" in rest:
            return match.group(0)
        header = re.search(r"<tr\b[^>]*>(.*?)</tr>", rest, flags=re.DOTALL)
        if not header or len(re.findall(r"<th\b", header.group(1))) != 3:
            return match.group(0)
        cls = re.search(r'\bclass="([^"]*)"', opening)
        if cls:
            opening = f"{opening[: cls.start(1)]}{cls.group(1)} c3{opening[cls.end(1) :]}"
        else:
            opening = f'{opening[:-1]} class="c3">'
        return f"{opening}<colgroup><col><col><col></colgroup>{rest}"

    return re.sub(r"(<table\b[^>]*>)(.*?</table>)", _fix, body, flags=re.DOTALL)


def html_to_pdf(html_path: Path, pdf_path: Path, title: str) -> str:
    """Render HTML to PDF with whichever engine is installed; return its name."""
    if shutil.which("wkhtmltopdf"):
        subprocess.run(
            [
                "wkhtmltopdf",
                "--quiet",
                "--enable-local-file-access",
                "--page-size",
                "A4",
                "--margin-top",
                "14mm",
                "--margin-bottom",
                "14mm",
                "--margin-left",
                "13mm",
                "--margin-right",
                "13mm",
                "--title",
                title,
                str(html_path),
                str(pdf_path),
            ],
            check=True,
        )
        return "wkhtmltopdf"
    try:
        from weasyprint import HTML  # type: ignore[import-not-found]
    except ImportError as exc:
        raise SystemExit("export_notes: need `wkhtmltopdf` on PATH or `pip install weasyprint`") from exc
    HTML(filename=str(html_path)).write_pdf(str(pdf_path))
    return "weasyprint"


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    # `python -OO` strips docstrings, leaving `__doc__` None.
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    ap.add_argument("markdown", type=Path)
    ap.add_argument("pdf", type=Path, nargs="?")
    ap.add_argument(
        "--title",
        default=None,
        help="<title> of the page; defaults to the first H1 or the file stem",
    )
    args = ap.parse_args(argv)

    md_path: Path = args.markdown
    if not md_path.is_file():
        raise SystemExit(f"export_notes: no such file: {md_path}")
    pdf_path: Path = args.pdf or md_path.with_suffix(".pdf")

    body = tag_three_column_tables(md_to_html_body(md_path))
    if args.title is None:
        h1 = re.search(r"^#\s+(.+)$", md_path.read_text(encoding="utf-8"), flags=re.MULTILINE)
        args.title = h1.group(1).strip() if h1 else md_path.stem
    page = (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        f"<title>{html.escape(args.title)}</title><style>{CSS}</style></head>"
        f"<body>{body}</body></html>"
    )

    with tempfile.TemporaryDirectory() as tmp:
        html_path = Path(tmp) / "notes.html"
        html_path.write_text(page, encoding="utf-8")
        engine = html_to_pdf(html_path, pdf_path, args.title)

    print(f"{pdf_path} ({engine})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
