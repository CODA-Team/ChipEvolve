from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import types
from pathlib import Path

import pytest
from scripts.platform import execution as pe


def test_native_and_leaf_paths_do_not_delegate(monkeypatch):
    monkeypatch.delenv("DPL_EVOLVE_PLATFORM_PROFILE", raising=False)
    assert pe.maybe_delegate("baseline", []) is None
    monkeypatch.setenv("DPL_EVOLVE_PLATFORM_PROFILE", "/missing/profile.json")
    monkeypatch.setenv("DPL_EVOLVE_EXECUTION_LEAF", "1")
    assert pe.maybe_delegate("variant_build", []) is None


def test_enabled_missing_profile_does_not_fall_back(monkeypatch):
    monkeypatch.setenv("DPL_EVOLVE_PLATFORM_PROFILE", "/missing/profile.json")
    monkeypatch.delenv("DPL_EVOLVE_EXECUTION_LEAF", raising=False)
    with pytest.raises(FileNotFoundError):
        pe.maybe_delegate("core_build", [])


@pytest.mark.parametrize("operation", ["core_build", "variant_build", "baseline"])
def test_delegate_preserves_arguments_and_failure(tmp_path, monkeypatch, operation):
    profile = tmp_path / "profile.json"
    profile.write_text(json.dumps({"client_python": "/client/bin/python"}))
    monkeypatch.setenv("DPL_EVOLVE_PLATFORM_PROFILE", str(profile))
    monkeypatch.delenv("DPL_EVOLVE_EXECUTION_LEAF", raising=False)
    calls = []

    def run(argv, **kwargs):
        calls.append(argv)
        return type("Result", (), {"returncode": 7})()

    monkeypatch.setattr(pe.subprocess, "run", run)
    assert pe.maybe_delegate(operation, ["--run-tag", "specific-tag"]) == 7
    assert calls[0][-4:] == [operation, "--", "--run-tag", "specific-tag"]


def test_image_and_input_validation(tmp_path, monkeypatch):
    source = tmp_path / "source"
    image = tmp_path / "image"
    image.write_bytes(b"image")
    item = tmp_path / "input.odb"
    item.write_bytes(b"original")
    monkeypatch.setattr(pe, "tree_files", lambda root: {"a.cpp": "source-hash"})
    request = {
        "toolchain": {"image_sha256": pe.digest(image)},
        "controller_files": {},
        "source": str(source),
        "source_files": {"a.cpp": "source-hash"},
        "inputs": {str(item): pe.digest(item)},
    }
    profile = {"image": str(image), "agent_root": str(tmp_path)}
    pe.validate_request(profile, request)
    item.write_bytes(b"changed")
    with pytest.raises(ValueError, match="Input changed"):
        pe.validate_request(profile, request)
    image.write_bytes(b"changed-image")
    with pytest.raises(ValueError, match="image identity"):
        pe.validate_request(profile, request)


def test_source_changes_rejected(tmp_path, monkeypatch):
    image = tmp_path / "image"
    image.write_bytes(b"image")
    monkeypatch.setattr(pe, "tree_files", lambda root: {"a.cpp": "new"})
    with pytest.raises(ValueError, match="Source changed"):
        pe.validate_request(
            {"image": str(image), "agent_root": str(tmp_path)},
            {
                "toolchain": {"image_sha256": pe.digest(image)},
                "controller_files": {},
                "source": str(tmp_path),
                "source_files": {"a.cpp": "old"},
                "inputs": {},
            },
        )


def test_private_binary_cannot_be_evaluated_with_stale_source(tmp_path, monkeypatch):
    binary = tmp_path / "bin/openroad"
    binary.parent.mkdir()
    binary.write_bytes(b"binary")
    pe.write_json(
        binary.parent / "platform-build.json",
        {
            "binary_sha256": pe.digest(binary),
            "source": str(tmp_path / "source"),
            "source_files": {"algorithm.cpp": "old"},
        },
    )
    monkeypatch.setattr(pe, "tree_files", lambda root: {"algorithm.cpp": "new"})
    profile = {
        "orfs_root": str(tmp_path),
        "core_root": str(tmp_path),
        "agent_root": str(tmp_path),
        "flow_variant": "one",
        "core_binary": str(binary),
    }
    with pytest.raises(ValueError, match="rebuild"):
        pe.request_for(
            profile, "baseline", ["--flow-variant", "one", "--run-tag", "trial"]
        )


def test_wrong_native_design_is_rejected_before_ef_request(tmp_path, monkeypatch):
    agent = tmp_path / "controller"
    registry = agent / "scripts/repo/case_registry.py"
    registry.parent.mkdir(parents=True)
    shutil.copyfile(
        Path(__file__).resolve().parents[1] / "scripts/repo/case_registry.py", registry
    )
    problem = agent / "problems/gcd_asap7/problem.yaml"
    problem.parent.mkdir(parents=True)
    problem.write_text(
        "name: gcd\ndesign: gcd\nplatform: asap7\ndesign_config: ./designs/asap7/gcd/config.mk\n"
    )
    binary = tmp_path / "bin/openroad"
    binary.parent.mkdir()
    binary.write_bytes(b"binary")
    pe.write_json(
        binary.parent / "platform-build.json",
        {
            "binary_sha256": pe.digest(binary),
            "source": str(tmp_path / "source"),
            "source_files": {},
        },
    )
    monkeypatch.setattr(pe, "tree_files", lambda root: {})
    result = tmp_path / "flow/results/asap7/jpeg/one"
    result.mkdir(parents=True)
    for name in ["3_4_place_resized.odb", "2_floorplan.sdc"]:
        (result / name).write_text("registered JPEG input")
    profile = {
        "orfs_root": str(tmp_path),
        "core_root": str(tmp_path),
        "agent_root": str(agent),
        "flow_variant": "one",
        "core_binary": str(binary),
        "case": "gcd_asap7",
        "platform": "asap7",
        "design": "jpeg",
        "controller_files": {},
        "prepared_source_sha256": "source",
        "toolchain": {},
        "cmake_args": [],
        "container_environment": {},
        "resources": {},
    }
    with pytest.raises(ValueError, match="case.*design.*binding"):
        pe.request_for(
            profile, "baseline", ["--case", "gcd_asap7", "--run-tag", "trial"]
        )


def test_container_keeps_stable_paths_and_core_read_only(tmp_path):
    profile = {
        "agent_root": "/control",
        "orfs_root": "/orfs",
        "state_root": "/state",
        "flow_output_roots": ["/orfs/flow/results"],
        "core_root": "/state/core",
        "container_environment": {},
        "container_python": "/usr/bin/python3",
        "image": "/image",
    }
    request = {
        "operation": "variant_build",
        "cwd": "/control",
        "argv": ["--dpl-src", "/state/candidate"],
    }
    command = pe.container_command(profile, request, tmp_path)
    assert "/state/core:/state/core:ro" in command
    assert "/control:/control:ro" in command
    assert "DPL_EVOLVE_EXECUTION_LEAF=1" in command
    assert "--no-home" in command
    assert command[-2:] == ["--dpl-src", "/state/candidate"]


def test_relocated_flow_keeps_compiled_cmake_source_prefix(tmp_path):
    cache = tmp_path / "core/build/CMakeCache.txt"
    cache.parent.mkdir(parents=True)
    cache.write_text("CMAKE_HOME_DIRECTORY:INTERNAL=/original/orfs/tools/OpenROAD\n")
    profile = {
        "agent_root": "/control",
        "orfs_root": "/new/orfs",
        "state_root": "/state",
        "flow_output_roots": [],
        "core_root": str(tmp_path / "core"),
        "container_environment": {},
        "container_python": "python3",
        "image": "/image",
    }
    workspace = tmp_path / "attempt"
    workspace.mkdir()
    command = pe.container_command(
        profile,
        {"operation": "variant_build", "cwd": "/control", "argv": []},
        workspace,
    )
    assert (
        str(tmp_path / "core/generated-source") + ":/original/orfs/tools/OpenROAD:ro"
        in command
    )
    assert (
        str(tmp_path / "core/generated-source") + ":/new/orfs/tools/OpenROAD:ro"
        in command
    )


def test_task_registers_original_metrics_and_odb(tmp_path):
    profile = {
        "experiment_id": "u3",
        "design": "gcd",
        "client_python": "/python",
        "agent_root": "/control",
        "profile_path": "/profile",
        "resources": {"physical": {"cpu_cores": 8}},
    }
    task = pe.task_for(
        profile, {"operation": "baseline", "outputs": []}, tmp_path / "request", "key"
    )
    assert "outputs/0/metrics.json" in task["inputs"]["native_extra_paths"]
    assert "outputs/2/legalized.odb" in task["inputs"]["native_extra_paths"]
    assert task["max_attempts"] == 1


@pytest.mark.parametrize(
    "operation", ["baseline", "variant_build", "core_build", "placement"]
)
@pytest.mark.parametrize("threads", [4, 10, 16])
def test_task_reserves_explicit_native_threads_without_rewriting_them(
    tmp_path, operation, threads
):
    resources = {"cpu_cores": 8, "memory_bytes": 32 << 30, "processes": 2048}
    profile = {
        "experiment_id": "thread-audit",
        "design": "jpeg",
        "client_python": "/python",
        "agent_root": "/control",
        "profile_path": "/profile",
        "resources": {"physical": dict(resources), "build": dict(resources)},
    }
    flag = "-threads" if operation == "placement" else "--threads"
    request = {"operation": operation, "outputs": [], "argv": [flag, str(threads)]}
    original = json.loads(json.dumps(request))
    task = pe.task_for(profile, request, tmp_path / "request", "key")
    assert task["resources"] == {**resources, "cpu_cores": max(8, threads)}
    assert profile["resources"] == {"physical": resources, "build": resources}
    assert request == original
    assert task["max_attempts"] == 1


def test_repeated_thread_flags_follow_native_last_value(tmp_path):
    profile = {
        "experiment_id": "thread-audit",
        "design": "jpeg",
        "client_python": "/python",
        "agent_root": "/control",
        "profile_path": "/profile",
        "resources": {"physical": {"cpu_cores": 8}},
    }
    for argv, expected in [
        (["--threads", "10", "--threads", "16"], 16),
        (["--threads", "16", "--threads", "10"], 10),
    ]:
        task = pe.task_for(
            profile,
            {"operation": "baseline", "outputs": [], "argv": argv},
            tmp_path / "request",
            "key",
        )
        assert task["resources"]["cpu_cores"] == expected


@pytest.mark.parametrize(
    "operation", ["core_build", "variant_build", "baseline", "placement"]
)
def test_explicit_operation_reservation_keeps_full_build_and_other_operations(
    tmp_path, operation
):
    build = {"cpu_cores": 8, "memory_bytes": 64 << 30, "processes": 2048}
    physical = {"cpu_cores": 8, "memory_bytes": 24 << 30, "processes": 2048}
    variant = {"cpu_cores": 8, "memory_bytes": 16 << 30, "processes": 2048}
    profile = {
        "experiment_id": "operation-resources",
        "design": "jpeg",
        "client_python": "/python",
        "agent_root": "/control",
        "profile_path": "/profile",
        "resources": {"physical": physical, "build": build, "variant_build": variant},
    }
    original = json.loads(json.dumps(profile))
    request = {
        "operation": operation,
        "outputs": [],
        "argv": ["-threads" if operation == "placement" else "--threads", "10"],
    }
    task = pe.task_for(profile, request, tmp_path / "request", "key")
    expected = (
        variant
        if operation == "variant_build"
        else build
        if operation == "core_build"
        else physical
    )
    assert task["resources"] == {**expected, "cpu_cores": 10}
    assert profile == original


@pytest.mark.parametrize("common", [False, True])
@pytest.mark.parametrize(
    "name", ["detail_place_openroad.tcl", "detail_place_openroad_negotiation.tcl"]
)
def test_actual_baseline_command_assembly(tmp_path, name, common):
    source = Path(__file__).resolve().parents[1] / "baseline" / name
    prefix = source.read_text().split("set hpwl_after", 1)[0]
    harness = r"""
rename source original_source
proc source {args} {}
namespace eval dpl_evolve_baseline {
  proc parse_options {args defaults} {return $defaults}
  proc option_value {options name} {return [dict get $options $name]}
  proc resolve_flow_path {path} {return $path}
  proc get_dbu_per_micron {} {return 2000}
  proc compute_hpwl_proxy {} {return 0}
  proc dump_instance_snapshot {path} {}
}
proc load_design {args} {}
proc source_step_tcl {args} {}
set calls {}
proc log_cmd {args} {lappend ::calls $args}
set argv {}
"""
    env = dict(os.environ)
    env.update(
        SCRIPTS_DIR=str(tmp_path),
        RESULTS_DIR=str(tmp_path / "results"),
        REPORTS_DIR=str(tmp_path / "reports"),
    )
    env.pop("DPL_EVOLVE_PLATFORM_PROFILE", None)
    if common:
        env["DPL_EVOLVE_PLATFORM_PROFILE"] = "/explicit-profile"
    result = subprocess.run(
        ["tclsh"],
        input=harness
        + prefix
        + '\nforeach call $calls {if {[lindex $call 0] eq "detailed_placement"} {puts $call}}\n',
        text=True,
        capture_output=True,
        env=env,
        check=True,
    )
    assert "detailed_placement" in result.stdout
    assert (
        "-use_diamond_legalizer" in result.stdout
        if common and name == "detail_place_openroad.tcl"
        else "-use_diamond_legalizer" not in result.stdout
    )
    assert (
        "-use_negotiation" in result.stdout
        if not common and name.endswith("negotiation.tcl")
        else "-use_negotiation" not in result.stdout
    )


def test_reopening_same_request_does_not_create_another_run(tmp_path, monkeypatch):
    runs = {}
    request = {"operation": "baseline", "outputs": [], "source_files": {"a.cpp": "one"}}

    class Client:
        def __init__(self, *args, **kwargs):
            pass

        def submit(self, task, *, idempotent, idempotency_key):
            assert idempotent
            if idempotency_key not in runs:
                runs[idempotency_key] = "run-" + str(len(runs) + 1)
            return {"run": {"run_id": runs[idempotency_key]}}

        def run(self, run_id):
            return {"run_id": run_id, "status": "succeeded"}

        def artifacts(self, run_id):
            return []

    module = types.ModuleType("openroad_platform_client")
    setattr(module, "KernelClient", Client)
    monkeypatch.setitem(sys.modules, "openroad_platform_client", module)
    monkeypatch.setattr(pe, "request_for", lambda *args: dict(request))
    monkeypatch.setattr(pe, "validate_request", lambda *args: None)
    profile = {
        "experiment_id": "one",
        "operations_root": str(tmp_path),
        "kernel_url": "http://localhost",
        "client_python": "/python",
        "agent_root": "/agent",
        "profile_path": "/profile",
        "design": "gcd",
        "resources": {"physical": {}},
        "deadline_epoch": time.time() + 60,
    }
    assert pe.delegate(profile, "baseline", []) == 0
    assert pe.delegate(profile, "baseline", []) == 0
    assert len(runs) == 1
    request["source_files"] = {"a.cpp": "new-candidate"}
    assert pe.delegate(profile, "baseline", []) == 0
    assert len(runs) == 2


def test_private_allocator_sees_candidate_layout_without_writing_core(
    tmp_path, monkeypatch
):
    from scripts.workspace import build_openroad_variant_relink as relink

    core = tmp_path / "core"
    core.mkdir()
    (core / "compile_commands.json").write_text(
        json.dumps(
            [
                {
                    "file": "/source/src/OpenRoad.cc",
                    "directory": str(core),
                    "command": "/compiler -I/source/include -o CMakeFiles/openroad.dir/OpenRoad.cc.o -c /source/src/OpenRoad.cc",
                }
            ]
        )
    )
    commands = []
    monkeypatch.setattr(
        relink.subprocess, "run", lambda argv, **kwargs: commands.append((argv, kwargs))
    )
    output = relink.compile_variant_allocator(
        core_build=core,
        variant_build=tmp_path / "private",
        variant_dpl_src=tmp_path / "candidate",
    )
    argv, kwargs = commands[0]
    assert argv[1:3] == [
        "-I" + str(tmp_path / "candidate/include"),
        "-I" + str(tmp_path / "candidate/src"),
    ]
    assert argv[argv.index("-o") + 1] == str(output)
    assert output.is_relative_to(tmp_path / "private")
    assert not (core / "CMakeFiles/openroad.dir/OpenRoad.cc.o").exists()
    assert kwargs["check"]


def test_private_link_uses_recompiled_allocator(tmp_path, monkeypatch):
    from scripts.workspace import build_openroad_variant_relink as relink

    core = tmp_path / "core"
    link = core / "src/CMakeFiles/openroad.dir/link.txt"
    link.parent.mkdir(parents=True)
    link.write_text(
        "/compiler CMakeFiles/openroad.dir/OpenRoad.cc.o dpl_evolve/dpl_evolve.a -o ../bin/openroad"
    )
    calls = []
    monkeypatch.setattr(
        relink, "run_shell", lambda command, **kwargs: calls.append(command)
    )
    private = tmp_path / "private"
    relink.relink_openroad(
        core_build=core, variant_build=private, install_root=private / "install"
    )
    assert str(private / "src/CMakeFiles/openroad.dir/OpenRoad.cc.o") in calls[0]
    assert str(private / "src/dpl_evolve/dpl_evolve.a") in calls[0]
