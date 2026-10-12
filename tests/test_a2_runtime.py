"""Check the real runtime boundary without substituting physical acceptance."""

import hashlib
import json

import pytest
from eda_toolkits.openroad.a2_runtime import (
    binary_identity,
    runtime_environment,
    stage_command,
)


@pytest.fixture
def profile(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text("{}")
    return {
        "flow_dir": str(tmp_path / "native"),
        "runtime": {
            "kind": "apptainer",
            "executable": "/usr/bin/apptainer",
            "image": "/fixed.sif",
        },
        "openroad_bin": "/image/openroad",
        "yosys_bin": "/image/yosys",
        "toolchain": {
            "source_manifest_path": str(manifest),
            "source_manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
            "binaries": {
                "openroad": {"path": "/image/openroad", "sha256": "a" * 64},
                "yosys": {"path": "/image/yosys", "sha256": "b" * 64},
            },
        },
    }


def test_stage_binds_frozen_source_workspace_disk_tmp_and_evaluation(tmp_path, profile):
    environment = {
        "CP0": ".792",
        "LIB_FILES": "/lib/a.lib /lib/b.lib",
        "API_KEY": "secret",
    }
    command = stage_command(
        ["make", "cts", "-o", "/input/3_place.odb"], tmp_path, profile, environment
    )
    assert f"{profile['flow_dir']}:{profile['flow_dir']}:ro" in command
    assert f"{tmp_path}:{tmp_path}" in command
    assert f"{tmp_path}/scratch:/tmp" in command
    assert command[command.index("--pwd") + 1] == str(tmp_path)
    assert "CP0=.792" in command and "LIB_FILES=/lib/a.lib /lib/b.lib" in command
    assert command[-4:] == ["make", "cts", "-o", "/input/3_place.odb"]
    assert not any("API_KEY" in arg for arg in command)


def test_host_model_and_container_overrides_not_forwarded(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    monkeypatch.setenv("APPTAINER_BIND", "/host:/image")
    monkeypatch.setenv("PYTHONPATH", "/sibling/source")
    env = runtime_environment()
    assert not {"OPENAI_API_KEY", "APPTAINER_BIND", "PYTHONPATH"} & env.keys()


def test_binary_identity_reads_actual_image_tools(monkeypatch, profile):
    captured = []

    def inspect(command, **kwargs):
        captured.append((command, kwargs))
        return json.dumps(profile["toolchain"]["binaries"])

    monkeypatch.setattr(
        "eda_toolkits.openroad.a2_runtime.subprocess.check_output", inspect
    )
    assert binary_identity(profile)["binaries"] == profile["toolchain"]["binaries"]
    assert captured[0][0][:4] == [
        "/usr/bin/apptainer",
        "exec",
        "--cleanenv",
        "--containall",
    ]


def test_changed_actual_binary_is_rejected(monkeypatch, profile):
    monkeypatch.setattr(
        "eda_toolkits.openroad.a2_runtime.subprocess.check_output", lambda *a, **k: "{}"
    )
    with pytest.raises(ValueError, match="actual common tools"):
        binary_identity(profile)


def test_profile_cannot_execute_another_binary(profile):
    profile["openroad_bin"] = "/old/openroad"
    with pytest.raises(ValueError, match="declared binary"):
        binary_identity(profile)


def test_source_evidence_cannot_be_changed(profile):
    profile["toolchain"]["source_manifest_sha256"] = "c" * 64
    with pytest.raises(ValueError, match="manifest changed"):
        binary_identity(profile)
