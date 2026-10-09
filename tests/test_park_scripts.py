"""Behavioural: mf's park.sh / unpark.sh never lose or overwrite a scratchpad file.

`/mf:park` and `/mf:unpark` copy a session scratchpad into the project and back, and unpark
deletes the snapshot once the restore verifies. These tests run both scripts as the skills do
(`bash <script> …`) on a throwaway tree in `tmp_path`. Skipped where bash, GNU tar, sha256sum or
git is missing.
"""

import os
import shutil
import subprocess
from pathlib import Path

import _util as u
import pytest

SCRIPTS = u.PLUGINS_DIR / "mindfunnel" / "scripts"
SID = "11111111-aaaa"


def _have_tools() -> bool:
    if not all(shutil.which(t) for t in ("bash", "tar", "sha256sum", "git")):
        return False
    return "GNU tar" in subprocess.run(["tar", "--version"], capture_output=True, text=True, check=False).stdout


pytestmark = pytest.mark.skipif(not _have_tools(), reason="needs bash, GNU tar, sha256sum and git")


def run(script: str, *args: object) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", str(SCRIPTS / script), *map(str, args)], capture_output=True, text=True, check=False)


def tree(root: Path) -> dict[str, object]:
    """Every entry under root: file bytes, a symlink's target, or None for a directory."""
    out: dict[str, object] = {}
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root).as_posix()
        out[rel] = ("link", p.readlink().as_posix()) if p.is_symlink() else p.read_bytes() if p.is_file() else None
    return out


@pytest.fixture
def scratch(tmp_path: Path) -> tuple[Path, Path]:
    """A scratchpad with awkward names, caches, a near-duplicate name and a symlink; a git project root."""
    sp = tmp_path / "slug" / SID / "scratchpad"
    for rel, data in {
        "a b.txt": "hi\n",
        "-dash.txt": "x\n",
        "sub/c.py": "print(1)\n",
        "sub/__pycache__/c.pyc": "bin",
        "__pycache__/m.pyc": "bin",
        "results/r.csv": "r1\n",
        "results/r.csv.bak": "r1 old\n",
    }.items():
        (sp / rel).parent.mkdir(parents=True, exist_ok=True)
        (sp / rel).write_text(data)
    (sp / "link").symlink_to("a b.txt")
    root = tmp_path / "root"
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    return sp, root / ".mf" / "park" / SID


def test_round_trip_restores_an_identical_tree_and_pops(scratch, tmp_path):
    sp, snap = scratch
    assert run("park.sh", sp, snap).returncode == 0
    (snap / "MANIFEST.md").write_text("# manifest\n")
    target = tmp_path / "new" / "scratchpad"
    r = run("unpark.sh", snap, target)
    assert r.returncode == 0, r.stderr
    restored = tree(target)
    assert restored.pop(f"PARKED-{SID}.md") == b"# manifest\n"
    assert restored == tree(sp)
    assert not snap.exists() and not snap.parent.exists()


def test_drop_list_drops_exact_paths_and_directory_prefixes_only(scratch, tmp_path):
    sp, snap = scratch
    drop = tmp_path / "drop.list"
    drop.write_text("./__pycache__/\n./sub/__pycache__/\n./results/r.csv\n")
    assert run("park.sh", sp, snap, drop).returncode == 0
    kept = (snap / "keep.list").read_text().splitlines()
    assert kept == ["./-dash.txt", "./a b.txt", "./link", "./results/r.csv.bak", "./sub/c.py"]


@pytest.mark.parametrize("drop", [None, "empty-file"])
def test_an_empty_or_absent_drop_list_keeps_everything(scratch, tmp_path, drop):
    # Regression: an awk NR==FNR filter read the file list as the drop list when the drop list was empty.
    sp, snap = scratch
    args = [sp, snap]
    if drop:
        (tmp_path / "empty.list").write_text("")
        args.append(tmp_path / "empty.list")
    assert run("park.sh", *args).returncode == 0
    assert (snap / "keep.list").read_text() == (snap / "all.list").read_text()
    assert len((snap / "all.list").read_text().splitlines()) == 8


def test_dropping_everything_parks_nothing_and_leaves_no_snapshot(scratch, tmp_path):
    sp, snap = scratch
    (tmp_path / "all.drop").write_text("./\n")
    r = run("park.sh", sp, snap, tmp_path / "all.drop")
    assert r.returncode == 6 and "nothing to park" in r.stderr
    assert not snap.exists()


def test_a_snapshot_never_unparked_is_not_overwritten(scratch):
    sp, snap = scratch
    assert run("park.sh", sp, snap).returncode == 0
    before = (snap / "SHA256SUMS").read_text()
    (sp / "results" / "r.csv").write_text("changed\n")
    r = run("park.sh", sp, snap)
    assert r.returncode == 4 and "never unparked" in r.stderr
    assert (snap / "SHA256SUMS").read_text() == before


def test_a_differing_file_is_left_alone_and_the_snapshot_kept(scratch, tmp_path):
    sp, snap = scratch
    assert run("park.sh", sp, snap).returncode == 0
    target = tmp_path / "new" / "scratchpad"
    (target / "results").mkdir(parents=True)
    (target / "results" / "r.csv").write_text("newer work\n")
    r = run("unpark.sh", snap, target)
    assert r.returncode == 1 and "were left as they are" in r.stderr
    assert (target / "results" / "r.csv").read_text() == "newer work\n"
    assert (target / "sub" / "c.py").read_text() == "print(1)\n"
    assert (snap / "SHA256SUMS").exists()


def test_a_corrupted_snapshot_fails_the_restore_and_is_not_popped(scratch, tmp_path):
    sp, snap = scratch
    assert run("park.sh", sp, snap).returncode == 0
    (snap / "files" / "sub" / "c.py").write_text("tampered\n")
    r = run("unpark.sh", snap, tmp_path / "new" / "scratchpad")
    assert r.returncode == 4 and "./sub/c.py: FAILED" in r.stdout + r.stderr and "inspect it by hand" in r.stderr
    assert (snap / "SHA256SUMS").exists()


def test_keep_retains_the_snapshot_and_an_unknown_option_touches_nothing(scratch, tmp_path):
    sp, snap = scratch
    assert run("park.sh", sp, snap).returncode == 0
    typo = tmp_path / "typo" / "scratchpad"
    r = run("unpark.sh", snap, typo, "--kep")
    assert r.returncode == 2 and "unknown option" in r.stderr
    assert not typo.exists() and snap.exists()
    r = run("unpark.sh", snap, tmp_path / "new" / "scratchpad", "--keep")
    assert r.returncode == 0, r.stderr
    assert (snap / "SHA256SUMS").exists()


def test_park_keeps_snapshots_out_of_git_once(scratch):
    sp, snap = scratch
    root = snap.parents[2]
    assert run("park.sh", sp, snap).returncode == 0
    assert run("park.sh", sp, snap.with_name("22222222-bbbb")).returncode == 0
    status = subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain"], capture_output=True, text=True, check=True
    )
    assert status.stdout == ""
    exclude = (root / ".git" / "info" / "exclude").read_text().splitlines()
    assert exclude.count("/.mf/park/") == 1


def test_a_failed_park_leaves_nothing_behind_and_blocks_nothing(scratch):
    if os.geteuid() == 0:
        pytest.skip("root reads an unreadable file")
    sp, snap = scratch
    (sp / "sub" / "c.py").chmod(0)
    try:
        r = run("park.sh", sp, snap)
    finally:
        (sp / "sub" / "c.py").chmod(0o644)
    assert r.returncode == 1
    assert not snap.exists() and not snap.with_name(f"{SID}.partial").exists()
    assert run("park.sh", sp, snap).returncode == 0


def test_a_name_with_a_backslash_round_trips(scratch, tmp_path):
    sp, snap = scratch
    (sp / "back\\tslash.txt").write_text("b\n")
    assert run("park.sh", sp, snap).returncode == 0
    target = tmp_path / "new" / "scratchpad"
    assert run("unpark.sh", snap, target).returncode == 0
    assert (target / "back\\tslash.txt").read_text() == "b\n"


def test_a_name_with_a_newline_is_refused_before_anything_is_written(scratch):
    sp, snap = scratch
    (sp / "two\nlines.txt").write_text("x")
    r = run("park.sh", sp, snap)
    assert r.returncode == 6 and "newline" in r.stderr
    assert not snap.exists() and not snap.with_name(f"{SID}.partial").exists()


def test_a_drop_line_that_matches_nothing_is_an_error(scratch, tmp_path):
    sp, snap = scratch
    drop = tmp_path / "drop.list"
    drop.write_text("./sub/__pycache__/\n./__pycache__\n")
    r = run("park.sh", sp, snap, drop)
    assert r.returncode == 6 and "matches nothing: ./__pycache__\n" in r.stderr
    assert "./sub/__pycache__/" not in r.stderr
    assert not snap.exists()


def test_a_different_entry_where_a_symlink_was_fails_the_restore(scratch, tmp_path):
    sp, snap = scratch
    assert run("park.sh", sp, snap).returncode == 0
    target = tmp_path / "new" / "scratchpad"
    target.mkdir(parents=True)
    (target / "link").write_text("a regular file\n")
    r = run("unpark.sh", snap, target)
    assert r.returncode == 1 and "./link: FAILED" in r.stdout
    assert (target / "link").read_text() == "a regular file\n"
    assert snap.exists()


def test_a_scratchpad_of_symlinks_only_parks_and_restores(tmp_path):
    sp = tmp_path / "slug" / SID / "scratchpad"
    sp.mkdir(parents=True)
    (sp / "l").symlink_to("/nonexistent/target")
    root = tmp_path / "root"
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    snap = root / ".mf" / "park" / SID
    r = run("park.sh", sp, snap)
    assert r.returncode == 0, r.stderr
    target = tmp_path / "new" / "scratchpad"
    r = run("unpark.sh", snap, target)
    assert r.returncode == 0, r.stderr
    assert (target / "l").readlink().as_posix() == "/nonexistent/target"


def test_identical_entries_at_the_target_pass_and_pop(scratch, tmp_path):
    sp, snap = scratch
    assert run("park.sh", sp, snap).returncode == 0
    target = tmp_path / "new" / "scratchpad"
    (target / "sub").mkdir(parents=True)
    (target / "sub" / "c.py").write_text("print(1)\n")
    (target / "link").symlink_to("a b.txt")
    r = run("unpark.sh", snap, target)
    assert r.returncode == 0, r.stderr
    assert not snap.exists()


def test_the_restored_manifest_never_overwrites_a_file(scratch, tmp_path):
    sp, snap = scratch
    assert run("park.sh", sp, snap).returncode == 0
    (snap / "MANIFEST.md").write_text("# second\n")
    target = tmp_path / "new" / "scratchpad"
    target.mkdir(parents=True)
    (target / f"PARKED-{SID}.md").write_text("# first\n")
    assert run("unpark.sh", snap, target).returncode == 0
    assert (target / f"PARKED-{SID}.md").read_text() == "# first\n"
    assert (target / f"PARKED-{SID}.2.md").read_text() == "# second\n"


def test_replace_takes_the_scratchpads_state_after_a_refusal_that_counts_why(scratch):
    sp, snap = scratch
    assert run("park.sh", sp, snap).returncode == 0
    (sp / "results" / "r.csv").write_text("v2\n")
    (sp / "-dash.txt").unlink()
    r = run("park.sh", sp, snap)
    assert (
        r.returncode == 4 and "(1 of its entries missing from the scratchpad, 1 edited since, 0 new since)" in r.stderr
    )
    r = run("park.sh", "--replace", sp, snap)
    assert r.returncode == 0, r.stderr
    assert (snap / "files" / "results" / "r.csv").read_text() == "v2\n"
    assert not (snap / "files" / "-dash.txt").exists()


def test_the_exclude_keeps_a_last_line_that_had_no_newline(scratch):
    sp, snap = scratch
    root = snap.parents[2]
    exclude = root / ".git" / "info" / "exclude"
    exclude.write_text("*.log")
    (root / "a.log").write_text("x\n")
    assert run("park.sh", sp, snap).returncode == 0
    assert exclude.read_text().splitlines()[-2:] == ["*.log", "/.mf/park/"]
    status = subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain"], capture_output=True, text=True, check=True
    )
    assert status.stdout == ""


def test_relative_paths_work_and_a_target_inside_the_snapshot_is_refused(scratch, tmp_path):
    sp, snap = scratch
    r = subprocess.run(
        ["bash", str(SCRIPTS / "park.sh"), os.path.relpath(sp, tmp_path), os.path.relpath(snap, tmp_path)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0, r.stderr
    r = run("unpark.sh", snap, snap / "files")
    assert r.returncode == 2 and "inside SNAPSHOT" in r.stderr
    assert (snap / "SHA256SUMS").exists()


def test_the_refusal_counts_alike_under_another_locale(scratch):
    sp, snap = scratch
    assert run("park.sh", sp, snap).returncode == 0
    (sp / "results" / "r.csv").write_text("v2\n")
    (sp / "-dash.txt").unlink()
    # gettext reads LANGUAGE only under a real locale, never under C or C.UTF-8: pick an installed one.
    have = {
        loc.lower().replace("-", ""): loc
        for loc in subprocess.run(["locale", "-a"], capture_output=True, text=True, check=False).stdout.split()
    }
    base = next((have[k] for k in ("en_us.utf8", "en_gb.utf8") if k in have), None)
    if base is None:
        pytest.skip("no en_US or en_GB UTF-8 locale installed to translate under")
    env = {**os.environ, "LANGUAGE": "de", "LC_ALL": base}
    probe = subprocess.run(["sha256sum", "-c", "/dev/null"], capture_output=True, text=True, check=False, env=env)
    if "no properly formatted" in probe.stderr:
        pytest.skip("coreutils has no German messages installed")
    r = subprocess.run(
        ["bash", str(SCRIPTS / "park.sh"), str(sp), str(snap)], capture_output=True, text=True, check=False, env=env
    )
    assert (
        r.returncode == 4 and "(1 of its entries missing from the scratchpad, 1 edited since, 0 new since)" in r.stderr
    )


def test_the_refusal_counts_symlinks_too(scratch):
    sp, snap = scratch
    assert run("park.sh", sp, snap).returncode == 0
    (sp / "link").unlink()
    r = run("park.sh", sp, snap)
    assert (
        r.returncode == 4 and "(1 of its entries missing from the scratchpad, 0 edited since, 0 new since)" in r.stderr
    )


def test_an_extraction_error_still_lists_every_differing_entry(scratch, tmp_path):
    sp, snap = scratch
    assert run("park.sh", sp, snap).returncode == 0
    target = tmp_path / "new" / "scratchpad"
    (target / "results").mkdir(parents=True)
    (target / "sub").write_text("a file where the snapshot has a directory\n")
    (target / "results" / "r.csv").write_text("newer work\n")
    r = run("unpark.sh", snap, target)
    assert r.returncode == 1
    assert "./results/r.csv: FAILED" in r.stdout and "./sub/c.py: FAILED" in r.stdout
    assert (target / "results" / "r.csv").read_text() == "newer work\n"
    assert snap.exists()


def test_a_snapshot_git_will_not_ignore_stays_in_place_with_exit_3_and_one_exclude_line(scratch):
    sp, snap = scratch
    root = snap.parents[2]
    (root / ".gitignore").write_text("!/.mf/park/\n")
    r = run("park.sh", sp, snap)
    assert r.returncode == 3 and "does not ignore .mf/park/" in r.stderr
    assert (snap / "SHA256SUMS").exists()
    assert run("park.sh", "--replace", sp, snap).returncode == 3
    assert (root / ".git" / "info" / "exclude").read_text().splitlines().count("/.mf/park/") == 1


def test_an_empty_scratchpad_says_so(tmp_path):
    sp = tmp_path / "slug" / SID / "scratchpad"
    sp.mkdir(parents=True)
    r = run("park.sh", sp, tmp_path / "root" / ".mf" / "park" / SID)
    assert r.returncode == 6 and "holds no files" in r.stderr


def test_a_symlinked_directory_at_the_target_is_never_written_through(scratch, tmp_path):
    sp, snap = scratch
    assert run("park.sh", sp, snap).returncode == 0
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    target = tmp_path / "new" / "scratchpad"
    target.mkdir(parents=True)
    (target / "sub").symlink_to(elsewhere)
    r = run("unpark.sh", snap, target)
    assert r.returncode == 1 and "./sub/c.py: FAILED (a directory on its path is a symlink)" in r.stdout
    assert list(elsewhere.iterdir()) == [] and snap.exists()


def test_a_symlink_at_the_target_to_an_identical_file_is_a_conflict(scratch, tmp_path):
    sp, snap = scratch
    assert run("park.sh", sp, snap).returncode == 0
    outside = tmp_path / "outside.csv"
    outside.write_text("r1\n")
    target = tmp_path / "new" / "scratchpad"
    (target / "results").mkdir(parents=True)
    (target / "results" / "r.csv").symlink_to(outside)
    r = run("unpark.sh", snap, target)
    assert r.returncode == 1 and "./results/r.csv: FAILED" in r.stdout and snap.exists()


def test_a_snapshot_that_changed_after_the_park_is_not_restored(scratch, tmp_path):
    sp, snap = scratch
    assert run("park.sh", sp, snap).returncode == 0
    (snap / "files" / "notes.md").write_text("added later\n")
    target = tmp_path / "new" / "scratchpad"
    r = run("unpark.sh", snap, target)
    assert r.returncode == 4 and "inspect it by hand" in r.stderr
    assert not target.exists() and snap.exists()


def test_an_unreadable_or_incomplete_snapshot_is_refused_without_counts(scratch):
    if os.geteuid() == 0:
        pytest.skip("root reads an unreadable file")
    sp, snap = scratch
    assert run("park.sh", sp, snap).returncode == 0
    (snap / "keep.list").chmod(0)
    try:
        r = run("park.sh", sp, snap)
    finally:
        (snap / "keep.list").chmod(0o600)
    assert r.returncode == 5 and "inspect it by hand" in r.stderr and "missing" not in r.stderr
    (snap / "all.list").unlink()
    r = run("park.sh", sp, snap)
    assert r.returncode == 5 and "no all.list" in r.stderr


def test_a_snapshot_inside_the_scratchpad_is_refused(scratch):
    sp, _ = scratch
    r = run("park.sh", sp, sp / "x" / ".mf" / "park" / SID)
    assert r.returncode == 2 and "inside SCRATCHPAD" in r.stderr
    assert not (sp / "x").exists()


def test_unrelated_files_at_the_target_are_left_alone(scratch, tmp_path):
    sp, snap = scratch
    assert run("park.sh", sp, snap).returncode == 0
    target = tmp_path / "new" / "scratchpad"
    target.mkdir(parents=True)
    (target / "mine.txt").write_text("this session's own\n")
    assert run("unpark.sh", snap, target).returncode == 0
    assert (target / "mine.txt").read_text() == "this session's own\n"
    assert not list(target.rglob("*.mf-unpark"))


def test_a_file_named_like_a_temporary_is_left_alone(scratch, tmp_path):
    sp, snap = scratch
    assert run("park.sh", sp, snap).returncode == 0
    target = tmp_path / "new" / "scratchpad"
    (target / "sub").mkdir(parents=True)
    (target / "sub" / ".c.py.mf-unpark").write_text("print(")
    assert run("unpark.sh", snap, target).returncode == 0
    assert (target / "sub" / "c.py").read_text() == "print(1)\n"
    assert (target / "sub" / ".c.py.mf-unpark").read_text() == "print("
    assert not list(target.rglob(".mf-unpark.*"))


def test_a_dangling_symlink_where_the_record_would_go_is_not_written_through(scratch, tmp_path):
    sp, snap = scratch
    assert run("park.sh", sp, snap).returncode == 0
    (snap / "MANIFEST.md").write_text("# manifest\n")
    target = tmp_path / "new" / "scratchpad"
    target.mkdir(parents=True)
    (target / f"PARKED-{SID}.md").symlink_to(tmp_path / "nowhere.md")
    assert run("unpark.sh", snap, target).returncode == 0
    assert not (tmp_path / "nowhere.md").exists()
    assert (target / f"PARKED-{SID}.2.md").read_text() == "# manifest\n"


def test_a_project_outside_git_parks_without_an_exclude(tmp_path):
    sp = tmp_path / "slug" / SID / "scratchpad"
    sp.mkdir(parents=True)
    (sp / "a.txt").write_text("a\n")
    snap = tmp_path / "plain" / ".mf" / "park" / SID
    r = run("park.sh", sp, snap)
    assert r.returncode == 0 and "excluded" not in r.stdout
    assert (snap / "files" / "a.txt").read_text() == "a\n"


def test_a_symlink_target_is_compared_exactly(scratch, tmp_path):
    sp, snap = scratch
    (sp / "nl").symlink_to("target\n")
    assert run("park.sh", sp, snap).returncode == 0
    target = tmp_path / "new" / "scratchpad"
    target.mkdir(parents=True)
    (target / "nl").symlink_to("target")
    r = run("unpark.sh", snap, target)
    assert r.returncode == 1 and "./nl: FAILED" in r.stdout


def test_the_refusal_counts_from_the_snapshots_own_files_not_its_checksums(scratch):
    sp, snap = scratch
    assert run("park.sh", sp, snap).returncode == 0
    (snap / "SHA256SUMS").write_text("not a checksum line\n")
    (sp / "new.txt").write_text("written after the park\n")
    r = run("park.sh", sp, snap)
    assert (
        r.returncode == 4 and "(0 of its entries missing from the scratchpad, 0 edited since, 1 new since)" in r.stderr
    )


def test_beside_restores_each_conflict_next_to_the_targets_own_and_pops(scratch, tmp_path):
    sp, snap = scratch
    assert run("park.sh", sp, snap).returncode == 0
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    target = tmp_path / "new" / "scratchpad"
    (target / "results").mkdir(parents=True)
    (target / "results" / "r.csv").write_text("newer work\n")
    (target / "sub").symlink_to(elsewhere)
    r = run("unpark.sh", snap, target, "--beside")
    assert r.returncode == 0, r.stdout + r.stderr
    assert (target / "results" / "r.csv").read_text() == "newer work\n"
    assert (target / f"PARKED-{SID}" / "results" / "r.csv").read_text() == "r1\n"
    assert (target / f"PARKED-{SID}" / "sub" / "c.py").read_text() == "print(1)\n"
    assert list(elsewhere.iterdir()) == []
    assert not snap.exists()


def test_beside_with_keep_retains_the_snapshot(scratch, tmp_path):
    sp, snap = scratch
    assert run("park.sh", sp, snap).returncode == 0
    target = tmp_path / "new" / "scratchpad"
    (target / "results").mkdir(parents=True)
    (target / "results" / "r.csv").write_text("newer work\n")
    assert run("unpark.sh", snap, target, "--keep", "--beside").returncode == 0
    assert snap.exists() and (target / f"PARKED-{SID}" / "results" / "r.csv").exists()


def test_the_refusal_counts_a_file_turned_symlink_and_a_retargeted_link_as_edited(scratch, tmp_path):
    sp, snap = scratch
    assert run("park.sh", sp, snap).returncode == 0
    outside = tmp_path / "outside.csv"
    outside.write_text("r1\n")
    (sp / "results" / "r.csv").unlink()
    (sp / "results" / "r.csv").symlink_to(outside)
    (sp / "link").unlink()
    (sp / "link").symlink_to("-dash.txt")
    r = run("park.sh", sp, snap)
    assert (
        r.returncode == 4 and "(0 of its entries missing from the scratchpad, 2 edited since, 0 new since)" in r.stderr
    )


def test_unpark_failing_to_create_its_target_keeps_the_snapshot(scratch, tmp_path):
    if os.geteuid() == 0:
        pytest.skip("root writes anywhere")
    sp, snap = scratch
    assert run("park.sh", sp, snap).returncode == 0
    locked = tmp_path / "locked"
    locked.mkdir()
    locked.chmod(0o555)
    try:
        r = run("unpark.sh", snap, locked / "scratchpad")
    finally:
        locked.chmod(0o755)
    assert r.returncode == 5 and snap.exists()


def test_a_changed_symlink_in_the_snapshot_is_not_restored(scratch, tmp_path):
    sp, snap = scratch
    assert run("park.sh", sp, snap).returncode == 0
    (snap / "files" / "link").unlink()
    (snap / "files" / "link").symlink_to("elsewhere")
    r = run("unpark.sh", snap, tmp_path / "new" / "scratchpad")
    assert r.returncode == 4 and "inspect it by hand" in r.stderr


def test_a_failed_pop_says_so_after_a_verified_restore(scratch, tmp_path):
    if os.geteuid() == 0:
        pytest.skip("root deletes anywhere")
    sp, snap = scratch
    assert run("park.sh", sp, snap).returncode == 0
    snap.parent.chmod(0o555)
    try:
        r = run("unpark.sh", snap, tmp_path / "new" / "scratchpad")
    finally:
        snap.parent.chmod(0o700)
    assert r.returncode == 3 and "restored: " in r.stdout and (snap / "SHA256SUMS").exists()


@pytest.mark.parametrize(
    "case",
    ["snapshot inside target", "partial", "scratchpad inside snapshot"],
)
def test_overlapping_or_partial_paths_are_refused(scratch, tmp_path, case):
    sp, snap = scratch
    if case == "scratchpad inside snapshot":
        inner = snap / "scratch"
        inner.mkdir(parents=True)
        (inner / "a.txt").write_text("a\n")
        r = run("park.sh", "--replace", inner, snap)
        assert r.returncode == 2 and "SCRATCHPAD lies inside SNAPSHOT" in r.stderr
        assert (inner / "a.txt").exists()
        return
    assert run("park.sh", sp, snap).returncode == 0
    if case == "snapshot inside target":
        r = run("unpark.sh", snap, snap.parents[2])
        assert r.returncode == 2 and "SNAPSHOT lies inside TARGET" in r.stderr
    else:
        partial = snap.with_name(f"{SID}.partial")
        shutil.copytree(snap, partial, symlinks=True)
        r = run("unpark.sh", partial, tmp_path / "new" / "scratchpad")
        assert r.returncode == 2 and "killed midway" in r.stderr
    assert snap.exists()
