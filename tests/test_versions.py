"""Each plugin.json version matches the newest CHANGELOG heading."""

import _util as u
import pytest


@pytest.mark.parametrize("plugin", u.plugin_dirs(), ids=u.rel)
def test_version_matches_changelog(plugin):
    meta = u.plugin_json(plugin)
    version = meta.get("version")
    assert isinstance(version, str) and version.strip(), f"{u.rel(plugin)}: plugin.json has no version string"

    changelog = plugin / "CHANGELOG.md"
    assert changelog.is_file(), f"{u.rel(plugin)}: missing CHANGELOG.md"

    newest = u.newest_changelog_version(changelog)
    assert newest is not None, f"{u.rel(changelog)}: no '## X.Y.Z' version heading found"
    assert version == newest, f"{u.rel(plugin)}: plugin.json version {version!r} != newest CHANGELOG heading {newest!r}"
