"""A failed native command keeps its own code and all existing evidence."""

import sys

import pytest

from chip_evolve.config import read, write
from chip_evolve.jobs import digest, leaf


def test_failed_command_keeps_partial_outputs_and_original_exit_code(
    tmp_path, monkeypatch
):
    work = tmp_path / "native"
    work.mkdir()
    actual, missing = work / "actual.log", work / "PASS"
    request = tmp_path / "request.json"
    write(
        request,
        {
            "command": [
                sys.executable,
                "-c",
                'from pathlib import Path;Path("actual.log").write_text("native stopped before proof completed");print("original native failure",flush=True);raise SystemExit(23)',
            ],
            "cwd": str(work),
            "capture": [str(actual), str(missing)],
        },
    )
    monkeypatch.chdir(tmp_path)
    assert leaf(request) == 23
    manifest = read(tmp_path / "query-data/manifest.json")
    assert manifest["returncode"] == 23 and manifest["evidence_only"]
    assert manifest["output_files"] == {str(actual): digest(actual)}
    assert manifest["missing_output_files"] == [str(missing)]
    assert (tmp_path / "query-data/0/actual.log").read_bytes() == actual.read_bytes()
    assert (
        tmp_path / "query-data/stdout.log"
    ).read_text() == "original native failure\n"
    assert not missing.exists()


def test_success_still_requires_its_declared_output_files(tmp_path, monkeypatch):
    request = tmp_path / "request.json"
    write(
        request,
        {
            "command": [sys.executable, "-c", "print('command exited zero')"],
            "cwd": str(tmp_path),
            "capture": [str(tmp_path / "PASS")],
        },
    )
    monkeypatch.chdir(tmp_path)
    with pytest.raises(FileNotFoundError):
        leaf(request)
