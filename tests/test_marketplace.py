"""marketplace.json and on-disk plugins agree."""

import _util as u
import pytest

_MARKET = u.load_json(u.MARKETPLACE)
_ENTRIES = _MARKET.get("plugins", [])


def test_marketplace_has_plugins():
    assert isinstance(_ENTRIES, list) and _ENTRIES, ".claude-plugin/marketplace.json has no 'plugins' array"


@pytest.mark.parametrize("entry", _ENTRIES, ids=lambda e: e.get("name", "?"))
def test_entry_resolves_to_real_plugin(entry):
    name = entry.get("name")
    source = entry.get("source")
    assert name and source, f"marketplace entry incomplete: {entry!r}"

    plugin_dir = (u.REPO_ROOT / source).resolve()
    assert plugin_dir.is_dir(), f"marketplace entry {name!r}: source {source!r} is not a directory"

    manifest = plugin_dir / ".claude-plugin" / "plugin.json"
    assert manifest.is_file(), f"marketplace entry {name!r}: {u.rel(manifest)} missing"

    disk_name = u.load_json(manifest).get("name")
    assert disk_name == name, f"name mismatch for {source!r}: marketplace={name!r} vs plugin.json={disk_name!r}"


def test_every_plugin_on_disk_is_listed():
    listed = {(u.REPO_ROOT / e["source"]).resolve() for e in _ENTRIES if e.get("source")}
    on_disk = set(u.plugin_dirs())
    missing = sorted(u.rel(p) for p in on_disk - listed)
    assert not missing, f"plugin(s) on disk but absent from marketplace.json: {missing}"
