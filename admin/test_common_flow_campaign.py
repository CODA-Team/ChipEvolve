"""Preparation must bind a qualified common environment without old state."""

import json
from pathlib import Path

import pytest
import run_common_flow_campaign as common


def test_prepare_never_overwrites_an_existing_experiment(tmp_path):
    with pytest.raises(FileExistsError):
        common.prepare(tmp_path, tmp_path / "qualification")


def test_unqualified_environment_is_not_used(tmp_path):
    (tmp_path / "config.json").write_text("{}")
    (tmp_path / "u1-acceptance.json").write_text('{"engineering_accepted":false}')
    with pytest.raises(ValueError, match="qualification is required"):
        common.qualification(tmp_path)


def test_image_inspection_reads_image_paths_not_host_wrappers(monkeypatch):
    captured = []

    def execute(command, **kwargs):
        captured.append(command)
        return json.dumps(
            {"openroad": {"path": common.TOOLS["openroad"], "sha256": "a" * 64}}
        )

    monkeypatch.setattr(common.subprocess, "check_output", execute)
    result = common.image_identity("/apptainer", Path("/fixed.sif"))
    assert result["openroad"]["path"] == common.TOOLS["openroad"]
    assert captured[0][:5] == [
        "/apptainer",
        "exec",
        "--cleanenv",
        "--containall",
        "/fixed.sif",
    ]


def test_different_common_version_is_rejected(tmp_path):
    (tmp_path / "config.json").write_text(
        json.dumps(
            {
                "image_sha256": "wrong",
                "orfs_commit": common.ORFS,
                "openroad_commit": common.OPENROAD,
            }
        )
    )
    (tmp_path / "u1-acceptance.json").write_text('{"engineering_accepted":true}')
    with pytest.raises(ValueError, match="qualified common toolchain"):
        common.qualification(tmp_path)
