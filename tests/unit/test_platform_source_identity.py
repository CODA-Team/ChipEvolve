"""A frozen source directory must not inherit the enclosing platform commit."""

import json
import subprocess
from pathlib import Path

import pytest

from goalevolve.platform.execution import toolchain_evidence


def repository(path: Path) -> str:
    path.mkdir(parents=True)
    subprocess.run(["git", "init", "--quiet", str(path)], check=True)
    (path / "source.cc").write_text("int value = 1;\n")
    subprocess.run(["git", "add", "source.cc"], cwd=path, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Source identity test",
            "-c",
            "user.email=source-test@local.invalid",
            "commit",
            "--quiet",
            "-m",
            "source fixture",
        ],
        cwd=path,
        check=True,
    )
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=path, text=True
    ).strip()


def bind(tmp_path: Path, monkeypatch, seed: Path):
    profile = tmp_path / "profile.json"
    profile.write_text(json.dumps({"source_seed": str(seed)}))
    monkeypatch.setenv("GOALEVOLVE_PLATFORM_PROFILE", str(profile))


@pytest.mark.parametrize("default_source", [False, True])
def test_plain_source_inside_other_repository_does_not_inherit_its_commit(
    tmp_path, monkeypatch, default_source
):
    platform = tmp_path / "platform"
    repository(platform)
    seed = platform / "var/frozen-openroad"
    seed.mkdir(parents=True)
    bind(tmp_path, monkeypatch, seed)
    result = toolchain_evidence(None if default_source else seed)
    assert result is not None
    assert result["source_git_commit"] is None


def test_source_own_repository_commit_is_retained(tmp_path, monkeypatch):
    seed = tmp_path / "openroad"
    commit = repository(seed)
    bind(tmp_path, monkeypatch, seed)
    result = toolchain_evidence(seed)
    assert result is not None
    assert result["source_git_commit"] == commit


def test_git_worktree_identity_is_retained(tmp_path, monkeypatch):
    original = tmp_path / "openroad"
    commit = repository(original)
    seed = tmp_path / "detached-worktree"
    subprocess.run(
        ["git", "worktree", "add", "--quiet", "--detach", str(seed), "HEAD"],
        cwd=original,
        check=True,
    )
    assert (seed / ".git").is_file()
    bind(tmp_path, monkeypatch, seed)
    result = toolchain_evidence(seed)
    assert result is not None
    assert result["source_git_commit"] == commit


def test_plain_standalone_snapshot_has_no_git_commit(tmp_path, monkeypatch):
    seed = tmp_path / "plain-source"
    seed.mkdir()
    bind(tmp_path, monkeypatch, seed)
    result = toolchain_evidence(seed)
    assert result is not None
    assert result["source_git_commit"] is None
