"""Actual image identity is independent of unchanged host wrappers."""

import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from platform_toolchain import tool_fingerprint


@pytest.fixture
def profile(tmp_path):
    image = tmp_path / "fixed.sif"
    image.write_bytes(b"image-a")
    source = tmp_path / "source.json"
    source.write_text("{}")
    return {
        "runtime": {
            "kind": "apptainer",
            "executable": "/apptainer",
            "image": str(image),
        },
        "openroad_bin": "/image/openroad",
        "yosys_bin": "/image/yosys",
        "toolchain": {
            "image_sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
            "source_manifest_path": str(source),
            "source_manifest_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "binaries": {
                "openroad": {"path": "/image/openroad", "sha256": "a" * 64},
                "yosys": {"path": "/image/yosys", "sha256": "b" * 64},
            },
        },
    }


def test_image_tools_are_fingerprinted_instead_of_host_paths(profile):
    with patch(
        "platform_toolchain.subprocess.check_output",
        return_value=json.dumps(profile["toolchain"]["binaries"]),
    ):
        result = tool_fingerprint(profile)
    assert result["binaries"] == profile["toolchain"]["binaries"]
    assert result["image_sha256"] == profile["toolchain"]["image_sha256"]


def test_changed_image_refuses_old_experiment(profile):
    Path(profile["runtime"]["image"]).write_bytes(b"image-b")
    with pytest.raises(ValueError, match="image changed"):
        tool_fingerprint(profile)


def test_actual_binary_hash_is_required(profile):
    with (
        patch("platform_toolchain.subprocess.check_output", return_value="{}"),
        pytest.raises(ValueError, match="actual tools"),
    ):
        tool_fingerprint(profile)


def test_host_profile_preserves_existing_fingerprint(tmp_path):
    tool = tmp_path / "tool"
    tool.write_bytes(b"native")
    assert tool_fingerprint({"openroad_bin": str(tool), "yosys_bin": str(tool)}) == {
        "openroad_bin": hashlib.sha256(b"native").hexdigest(),
        "yosys_bin": hashlib.sha256(b"native").hexdigest(),
    }
