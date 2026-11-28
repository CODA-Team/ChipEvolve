"""The generated GCD deployment is validation-ready without enabling Flow."""

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from admin.release import stack


def prepared_stack(tmp_path, monkeypatch):
    state = tmp_path / "var/instance"
    state.mkdir(parents=True)
    image = tmp_path / "toolchain.sif"
    image.write_bytes(b"pinned test image")
    (tmp_path / "SOURCE_MANIFEST.json").write_text("{}\n")
    python = tmp_path / "agent/flow-agent/.venv/bin/python"
    python.parent.mkdir(parents=True)
    python.touch()
    config = {
        "workspace": str(tmp_path),
        "state_root": str(state),
        "orfs_image": str(image),
        "kernel_port": 29710,
        "data_port": 29934,
        "cpu_cores": 4,
        "memory_gib": 12,
    }
    monkeypatch.setattr(stack.shutil, "which", lambda name: "/usr/bin/apptainer")

    def run(command, **kwargs):
        if command[-2] == "cat":
            kwargs["stdout"].write(b"Liberty input")
        else:
            assert command[-3:] == [
                "test",
                "-x",
                "/OpenROAD-flow-scripts/tools/install/yosys/bin/yosys",
            ]
        return SimpleNamespace(returncode=0)

    def output(command, **kwargs):
        if command[0] == "git":
            return "a" * 40 + "\n"
        if "sha256sum" in command:
            return "".join("b" * 64 + "  " + p + "\n" for p in command[-2:])
        return "set clk_period 1.0\ncreate_clock -period $clk_period clk\n"

    monkeypatch.setattr(stack.subprocess, "run", run)
    monkeypatch.setattr(stack.subprocess, "check_output", output)
    return config, state


@pytest.mark.parametrize("flow", [False, True])
def test_prepare_gcd_keeps_common_recipe_and_binds_only_requested_flow(
    tmp_path, monkeypatch, flow
):
    config, state = prepared_stack(tmp_path, monkeypatch)
    if not flow:
        Path(config["workspace"], "agent/flow-agent/.venv/bin/python").unlink()
    stack.prepare_gcd(config, flow=flow)
    value = json.loads((state / "local.json").read_text())
    assert value["tools"]["yosys"].endswith("/yosys/bin/yosys")
    assert value["validation"] == {
        "equivalence_memory_gib": 8,
        "equivalence_seconds": 600,
    }
    design = value["designs"]["gcd"]
    assert design["clock_period_ns"] == 0.5
    assert "ABC_CLOCK_PERIOD_IN_PS" in design["baseline_overrides"]
    assert len(design["flow_dependencies"]) == 2
    assert all(Path(row["source"]).is_file() for row in design["flow_dependencies"])
    assert ("flow" in value.get("professional", {})) is flow
    assert ("flow_tool_profile" in value) is flow
    assert (state / "flow-tool-profile.json").exists() is flow


@pytest.mark.parametrize("cpu,memory", [(2, 12), (4, 4)])
def test_prepare_refuses_capacity_smaller_than_the_qualified_proof(
    tmp_path, monkeypatch, cpu, memory
):
    config, state = prepared_stack(tmp_path, monkeypatch)
    config.update(cpu_cores=cpu, memory_gib=memory)
    with pytest.raises(ValueError, match="four CPU cores and 8 GiB"):
        stack.prepare_gcd(config)
    assert not (state / "inputs").exists()
    assert not (state / "local.json").exists()


def test_prepare_does_not_publish_config_when_image_yosys_is_missing(
    tmp_path, monkeypatch
):
    config, state = prepared_stack(tmp_path, monkeypatch)
    original = stack.subprocess.run

    def missing(command, **kwargs):
        if "test" in command:
            raise subprocess.CalledProcessError(1, command)
        return original(command, **kwargs)

    monkeypatch.setattr(stack.subprocess, "run", missing)
    with pytest.raises(subprocess.CalledProcessError):
        stack.prepare_gcd(config)
    assert not (state / "local.json").exists()
