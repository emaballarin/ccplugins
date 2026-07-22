"""Shared helpers for the ccplugins Tier-1 static-validation suite.

Pure filesystem + text inspection over the marketplace. No plugin code is
imported or executed — kernels are read as source and parsed with `ast`.
"""

import ast
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGINS_DIR = REPO_ROOT / "plugins"
MARKETPLACE = REPO_ROOT / ".claude-plugin" / "marketplace.json"

# Tools a skill may legitimately list under `allowed-tools`. A typo (e.g.
# "Wrtie") should fail; genuinely new tools get added here as part of the
# change that introduces them.
KNOWN_TOOLS = {
    "Read",
    "Write",
    "Edit",
    "MultiEdit",
    "NotebookEdit",
    "Glob",
    "Grep",
    "Bash",
    "BashOutput",
    "KillShell",
    "KillBash",
    "WebSearch",
    "WebFetch",
    "Task",
    "Agent",
    "Skill",
    "SlashCommand",
    "AskUserQuestion",
    "TodoWrite",
    "Artifact",
}

_VERSION_HEADING = re.compile(r"^##\s+v?(\d+\.\d+\.\d+)", re.MULTILINE)


def plugin_dirs() -> list[Path]:
    """Every directory under plugins/ that is a real plugin."""
    return sorted(p for p in PLUGINS_DIR.iterdir() if (p / ".claude-plugin" / "plugin.json").is_file())


def skill_files() -> list[Path]:
    """Every plugins/*/skills/*/SKILL.md."""
    return sorted(PLUGINS_DIR.glob("*/skills/*/SKILL.md"))


def agent_files() -> list[Path]:
    """Every plugins/*/agents/*.md."""
    return sorted(PLUGINS_DIR.glob("*/agents/*.md"))


def rel(path: Path) -> str:
    """Repo-relative string, for stable pytest ids and messages."""
    return str(path.relative_to(REPO_ROOT))


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def split_frontmatter(path: Path) -> str | None:
    """Return the raw YAML frontmatter block, or None if the file has none.

    Frontmatter is the text between a leading `---` line and the next `---`.
    """
    text = read_text(path)
    if not text.startswith("---"):
        return None
    lines = text.splitlines()
    # lines[0] == "---"; find the closing delimiter.
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return "\n".join(lines[1:i])
    return None


def parse_frontmatter(path: Path) -> dict:
    """Parse frontmatter to a dict. Raises on missing/invalid/non-mapping."""
    import yaml  # local import so a missing dep fails only the tests that need it

    block = split_frontmatter(path)
    if block is None:
        raise ValueError(f"{rel(path)}: no YAML frontmatter (must start with '---')")
    data = yaml.safe_load(block)
    if not isinstance(data, dict):
        raise TypeError(f"{rel(path)}: frontmatter is not a mapping")
    return data


def load_json(path: Path) -> dict:
    return json.loads(read_text(path))


def plugin_json(plugin_dir: Path) -> dict:
    return load_json(plugin_dir / ".claude-plugin" / "plugin.json")


def newest_changelog_version(changelog: Path) -> str | None:
    """First `## X.Y.Z` version heading in a CHANGELOG (newest-first convention)."""
    m = _VERSION_HEADING.search(read_text(changelog))
    return m.group(1) if m else None


def top_level_names(kernel: Path) -> set[str]:
    """Top-level def/class/assignment names defined in a Python source file.

    Uses ast only — the kernel is never imported, so heavy or optional
    third-party imports (matplotlib, pypdfium2, …) never need to be installed.
    """
    tree = ast.parse(read_text(kernel), filename=str(kernel))
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name):
                    names.add(tgt.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names
