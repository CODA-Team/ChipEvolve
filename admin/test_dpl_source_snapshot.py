"""A source replay inside ignored runtime storage must retain a real Git inventory."""

from pathlib import Path
import subprocess

from chip_evolve.professional import freeze, inventory


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()


def source_repo(tmp_path):
    source = tmp_path / "original"
    source.mkdir()
    git(source, "init", "-q")
    (source / "src").mkdir()
    (source / "src/StudentAlgorithm.cpp").write_text("int mechanism() { return 7; }\n")
    (source / ".gitignore").write_text("*.o\n")
    git(source, "add", "-A")
    git(
        source,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.invalid",
        "commit",
        "-qm",
        "source",
    )
    outer = tmp_path / "platform"
    outer.mkdir()
    git(outer, "init", "-q")
    (outer / ".gitignore").write_text("var/\n")
    git(outer, "add", ".gitignore")
    git(
        outer,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.invalid",
        "commit",
        "-qm",
        "outer",
    )
    return source, outer / "var/variant/dpl_evolve"


def test_code_replay_snapshot_has_own_nonempty_inventory_in_ignored_storage(tmp_path):
    source, target = source_repo(tmp_path)
    original = inventory(source)
    commit = git(source, "rev-parse", "HEAD")
    freeze(source, target, git_metadata=True)
    assert git(target, "rev-parse", "--show-toplevel") == str(target)
    assert set(git(target, "ls-files").splitlines()) == set(original)
    assert not git(target, "status", "--porcelain")
    assert inventory(target) == original
    assert inventory(source) == original and git(source, "rev-parse", "HEAD") == commit
    (target / "src/StudentAlgorithm.cpp").write_text("int changed() { return 9; }\n")
    assert git(target, "status", "--porcelain")
    assert inventory(source) == original


def test_controller_export_keeps_default_without_new_git_metadata(tmp_path):
    source, target = source_repo(tmp_path)
    freeze(source, target)
    assert not (target / ".git").exists()
    assert inventory(target) == inventory(source)
    # This demonstrates why an exported source cannot use the parent's Git
    # inventory when runtime storage is ignored by that parent repository.
    assert not git(target, "ls-files")
