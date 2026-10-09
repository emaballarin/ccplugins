"""The shipped AGENTS.md template is byte-identical to the live baseline.

`/mf:setup` seeds a new machine from `plugins/mindfunnel/templates/AGENTS.md`;
the maintainer edits the live `~/.mindfunnel/AGENTS.md`, which runs ahead. The
sync is live → shipped, and only for `AGENTS.md` (`SOUL.md` / `USER.md` are
personal). Skips where no live file exists, as in CI.
"""

import difflib
import shlex
from pathlib import Path

import _util as u
import pytest

SHIPPED = u.PLUGINS_DIR / "mindfunnel" / "templates" / "AGENTS.md"
LIVE = Path.home() / ".mindfunnel" / "AGENTS.md"
MAX_DIFF_LINES = 40


@pytest.mark.skipif(not LIVE.is_file(), reason=f"no live baseline at {LIVE}")
def test_shipped_agents_md_matches_live():
    live, shipped = LIVE.read_bytes(), SHIPPED.read_bytes()
    if live == shipped:
        return
    diff = list(
        difflib.unified_diff(
            shipped.decode("utf-8-sig").splitlines(),
            live.decode("utf-8-sig").splitlines(),
            fromfile=u.rel(SHIPPED),
            tofile=str(LIVE),
            lineterm="",
        )
    )
    if not diff:
        shown = "(the text is identical; they differ only in line endings, a BOM or the final newline)"
    elif len(diff) > MAX_DIFF_LINES:
        shown = "\n".join(diff[:MAX_DIFF_LINES] + [f"… {len(diff) - MAX_DIFF_LINES} more diff lines not shown"])
    else:
        shown = "\n".join(diff)
    pytest.fail(
        f"{u.rel(SHIPPED)} differs from {LIVE}.\n"
        f"On the machine where the baseline is edited, sync live → shipped:\n"
        f"  cp {shlex.quote(str(LIVE))} {shlex.quote(str(SHIPPED))}\n"
        f"On any other machine the live copy is stale or personalised: refresh it from the "
        f"shipped template, and never copy it into the repo.\n{shown}"
    )
