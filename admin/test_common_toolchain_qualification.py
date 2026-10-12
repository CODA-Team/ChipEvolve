"""Failure evidence and immutable source pins for common toolchain qualification."""

import json
import subprocess
import sys
from pathlib import Path

import pytest
import qualify_common_toolchain as q


def test_failed_preparation_retains_log_and_receipt(tmp_path):
    (tmp_path / "preparation").mkdir()
    with pytest.raises(RuntimeError, match="failed"):
        q.recorded(
            tmp_path,
            "failed",
            [sys.executable, "-c", "print('reason');exit(7)"],
            timeout=10,
        )
    assert (
        json.loads((tmp_path / "preparation/failed.json").read_text())["exit_code"] == 7
    )
    assert "reason" in (tmp_path / "preparation/failed.log").read_text()
    with pytest.raises(FileExistsError):
        q.recorded(tmp_path, "failed", [sys.executable, "-c", "exit(0)"], timeout=10)


def test_timeout_is_retained(tmp_path):
    (tmp_path / "preparation").mkdir()
    with pytest.raises(subprocess.TimeoutExpired):
        q.recorded(
            tmp_path,
            "timeout",
            [sys.executable, "-c", "import time;time.sleep(10)"],
            timeout=1,
        )
    assert (
        json.loads((tmp_path / "preparation/timeout.json").read_text())["timed_out"]
        is True
    )


def repository(path: Path):
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    (path / "algorithm.cc").write_text("int value = 1;\n")
    subprocess.run(["git", "add", "."], cwd=path, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "commit",
            "-qm",
            "source",
        ],
        cwd=path,
        check=True,
    )


def test_source_rejects_wrong_selected_commit(tmp_path):
    repository(tmp_path)
    with pytest.raises(ValueError, match="selected common version"):
        q.source_identity(tmp_path)


def test_source_rejects_modified_bytes(tmp_path):
    repository(tmp_path)
    (tmp_path / "algorithm.cc").write_text("int value = 2;\n")
    with pytest.raises(ValueError, match="tracked modifications"):
        q.source_identity(tmp_path)


def test_selected_dependencies_are_not_self_reported(tmp_path, monkeypatch):
    repository(tmp_path)
    monkeypatch.setattr(q, "OPENROAD", q.git(tmp_path, "rev-parse", "HEAD"))
    with pytest.raises(ValueError, match="dependencies differ"):
        q.source_identity(tmp_path)


def test_build_uses_explicit_container_and_binary(tmp_path):
    args = q.container(
        "chosen.sif", tmp_path, "/work/candidate/openroad", "-exit", "/work/check.tcl"
    )
    assert args[-4:] == [
        "chosen.sif",
        "/work/candidate/openroad",
        "-exit",
        "/work/check.tcl",
    ]
    assert "--containall" in args and str(tmp_path) + ":/work" in args
    assert str(tmp_path / "tmp") + ":/tmp" in args
    assert (tmp_path / "tmp").is_dir()


def test_declared_crlf_checkout_is_valid_source(tmp_path, monkeypatch):
    repository(tmp_path)
    (tmp_path / ".gitattributes").write_text("*.dsp text eol=crlf\n")
    (tmp_path / "windows.dsp").write_bytes(b"source\r\n")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "commit",
            "-qm",
            "declared CRLF",
        ],
        cwd=tmp_path,
        check=True,
    )
    monkeypatch.setattr(q, "OPENROAD", q.git(tmp_path, "rev-parse", "HEAD"))
    # Passing byte identity reaches the independent dependency pin check.
    with pytest.raises(ValueError, match="dependencies differ"):
        q.source_identity(tmp_path)


def test_frozen_source_unpack_preserves_exact_symlink_bytes(tmp_path):
    import os
    import tarfile

    source = tmp_path / "source"
    source.mkdir()
    (source / "input.def").write_text("design\n")
    (source / "link.def").symlink_to("./input.def")
    archive = tmp_path / "source.tar"
    with tarfile.open(archive, "w") as bundle:
        bundle.add(source, arcname="source")
    output = tmp_path / "attempt"
    output.mkdir()
    q.extract_source(archive, output)
    assert os.readlink(output / "source/link.def") == "./input.def"
    assert (output / "source/link.def").read_text() == "design\n"


@pytest.mark.parametrize("tamper", ["archive", "source", "flags"])
def test_checkpoint_rejects_tampered_bytes_or_different_build_inputs(tmp_path, tamper):
    import io
    import tarfile

    manifest = {
        "origin_run_id": "run-old",
        "source_archive_sha256": "source",
        "source_manifest_sha256": "manifest",
        "image_sha256": "image",
        "cmake_args": ["Release"],
    }
    archive = tmp_path / "cache.tar"
    payload = json.dumps(manifest).encode()
    with tarfile.open(archive, "w") as bundle:
        info = tarfile.TarInfo("checkpoint.json")
        info.size = len(payload)
        bundle.addfile(info, io.BytesIO(payload))
    config = {
        **manifest,
        "cmake_args": ["Release", "-DCMAKE_EXE_LINKER_FLAGS=-flto=1"],
        "build_checkpoint": {"origin_run_id": "run-old", "sha256": q.digest(archive)},
    }
    if tamper == "archive":
        archive.write_bytes(b"different bytes")
    elif tamper == "source":
        config["source_archive_sha256"] = "other source"
    else:
        config["cmake_args"] = ["Debug", "-DCMAKE_EXE_LINKER_FLAGS=-flto=1"]
    with pytest.raises(ValueError, match="checkpoint|Checkpoint"):
        q.restore_checkpoint(archive, tmp_path, config)
