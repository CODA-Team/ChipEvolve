"""Native runner delegation and deterministic source/task identities."""

from __future__ import annotations

import json
import os
from unittest.mock import patch

import pytest
from goalevolve.execution.execution import (
    ExecutionPolicy,
    ExecutionReport,
    ResilientCommandRunner,
)
from goalevolve.platform.execution import (
    build_root,
    maybe_delegate,
    request_for,
    task_for,
    validate_request,
)


def test_native_and_leaf_remain_native(tmp_path, monkeypatch):
    monkeypatch.delenv("GOALEVOLVE_PLATFORM_PROFILE", raising=False)
    assert (
        maybe_delegate(
            command=["true"],
            cwd=tmp_path,
            policy=ExecutionPolicy(),
            output_log=None,
            environment=None,
        )
        is None
    )
    monkeypatch.setenv("GOALEVOLVE_EXECUTION_LEAF", "1")
    p = tmp_path / "profile.json"
    p.write_text("{}")
    monkeypatch.setenv("GOALEVOLVE_PLATFORM_PROFILE", str(p))
    assert (
        maybe_delegate(
            command=["true"],
            cwd=tmp_path,
            policy=ExecutionPolicy(),
            output_log=None,
            environment=None,
        )
        is None
    )


def test_runner_returns_delegated_failure_without_native_subprocess(tmp_path):
    expected = ExecutionReport(False, 2, 17, "stdout", "stderr", "command_failed")
    with (
        patch(
            "goalevolve.platform.execution.maybe_delegate", return_value=expected
        ) as bridge,
        patch(
            "subprocess.Popen", side_effect=AssertionError("native execution forbidden")
        ),
    ):
        actual = ResilientCommandRunner(ExecutionPolicy(min_free_gb=0)).run(
            command=["make"], cwd=tmp_path
        )
    assert actual == expected
    assert bridge.call_count == 1


def test_build_root_handles_transitive_object_commands(tmp_path):
    build = tmp_path / "build"
    build.mkdir()
    (build / "CMakeCache.txt").write_text("CMAKE_HOME_DIRECTORY:INTERNAL=/source\n")
    object_dir = build / "src/rsz/CMakeFiles/rsz.dir"
    object_dir.mkdir(parents=True)
    assert build_root(["make", "RepairPowerPolicy.cc.o"], object_dir) == build
    assert (
        build_root([str(build / "bin/openroad"), "-exit", "flow.tcl"], tmp_path)
        == build
    )


def test_request_detects_source_change_and_preserves_native_policy(tmp_path):
    source = tmp_path / "source"
    file = source / "src/rsz/src/example.cc"
    file.parent.mkdir(parents=True)
    file.write_text("int example;\n")
    image = tmp_path / "image.sif"
    image.write_bytes(b"test")
    from goalevolve.platform.execution import digest

    profile = {
        "image": str(image),
        "input_files": {},
        "toolchain": {"image_sha256": digest(image)},
        "experiment_id": "u4",
        "design": "aes",
        "client_python": "python",
        "profile_path": "profile.json",
        "deadline_epoch": 9999999999,
        "resources": {"build": {"cpu_cores": 8}, "physical": {"cpu_cores": 1}},
    }
    call = {
        "command": ["cmake", "-S", str(source), "-B", str(tmp_path / "build")],
        "cwd": str(tmp_path),
        "policy": {"timeout_s": 100, "retries": 1},
        "output_log": None,
        "environment": dict(os.environ),
    }
    request = request_for(profile, call, 2)
    assert request["source"] == str(source)
    assert request["attempt"] == 2
    task = task_for(profile, request, tmp_path / "request.json", "key")
    assert task["max_attempts"] == 1
    assert task["resources"] == {"cpu_cores": 8}
    validate_request(profile, request)
    file.write_text("int changed;\n")
    with pytest.raises(ValueError, match="source changed"):
        validate_request(profile, request)


def test_profile_failure_never_returns_native_fallback(tmp_path, monkeypatch):
    path = tmp_path / "profile.json"
    path.write_text(
        json.dumps(
            {
                "client_python": "/bin/false",
                "profile_path": str(path),
                "operations_root": str(tmp_path / "operations"),
            }
        )
    )
    monkeypatch.setenv("GOALEVOLVE_PLATFORM_PROFILE", str(path))
    result = maybe_delegate(
        command=["true"],
        cwd=tmp_path,
        policy=ExecutionPolicy(),
        output_log=None,
        environment=None,
    )
    assert result is not None and not result.ok
    assert result.resource_error == "delegation_failed"


def test_physical_evaluation_rejects_stale_binary(tmp_path):
    from goalevolve.platform.execution import digest, record_build

    source = tmp_path / "source"
    source_file = source / "src/rsz/src/policy.cc"
    source_file.parent.mkdir(parents=True)
    source_file.write_text("int baseline;\n")
    binary = tmp_path / "build/bin/openroad"
    binary.parent.mkdir(parents=True)
    binary.write_bytes(b"binary")
    image = tmp_path / "image"
    image.write_bytes(b"image")
    profile = {
        "input_files": {},
        "toolchain": {"image_sha256": digest(image)},
        "cmake_args": [],
    }
    with patch(
        "goalevolve.platform.profile.load_platform_profile", return_value=profile
    ):
        record_build(source, binary)
    call = {"command": [str(binary), "-exit", "flow.tcl"], "cwd": str(tmp_path)}
    assert request_for(profile, call, 1)["source"] == str(source)
    source_file.write_text("int student;\n")
    with pytest.raises(ValueError, match="source/build"):
        request_for(profile, call, 1)


def test_leaf_timeout_terminates_owned_descendants(tmp_path, monkeypatch):
    import sys
    import time

    from goalevolve.platform.execution import leaf

    profile = {"agent_python": sys.executable}
    request = {
        "command": [
            sys.executable,
            "-c",
            "import subprocess,time; subprocess.Popen(['sleep','60']);time.sleep(60)",
        ],
        "operation": "analysis",
        "cwd": str(tmp_path),
        "receipt_root": str(tmp_path),
        "environment": {},
        "policy": {"timeout_s": 0.1},
        "output_log": str(tmp_path / "native.log"),
        "build": None,
    }
    monkeypatch.chdir(tmp_path)
    started = time.monotonic()
    with patch("goalevolve.platform.execution.validate_request"):
        assert leaf(profile, request) != 0
    receipt = json.loads((tmp_path / "leaf.json").read_text())
    assert receipt["timed_out"]
    assert time.monotonic() - started < 5


def test_common_mode_keeps_original_flow_with_explicit_diamond(tmp_path):
    from goalevolve.evaluation.contest2026 import (
        Contest2026Config,
        Contest2026OpenROADEvaluator,
    )

    benchmark = tmp_path / "benchmarks/unit"
    benchmark.mkdir(parents=True)
    asap7 = tmp_path / "asap7"
    (asap7 / "lef").mkdir(parents=True)
    (asap7 / "lib").mkdir()
    for path in (
        benchmark / "unit.def",
        benchmark / "unit.v",
        benchmark / "unit.sdc",
        asap7 / "lef/unit.lef",
        asap7 / "lib/unit.lib",
        asap7 / "setRC.tcl",
    ):
        path.write_text("")
    evaluator = Contest2026OpenROADEvaluator(
        Contest2026Config("unit", benchmark.parent, tmp_path)
    )
    script = tmp_path / "evaluate.tcl"
    with patch(
        "goalevolve.evaluation.contest2026.load_platform_profile", return_value=None
    ):
        evaluator._write_tcl(tcl=script, output=tmp_path / "out")
    native = script.read_text()
    with patch(
        "goalevolve.evaluation.contest2026.load_platform_profile",
        return_value={"enabled": True},
    ):
        evaluator._write_tcl(tcl=script, output=tmp_path / "out")
    common = script.read_text()
    assert "detailed_placement -use_diamond_legalizer\n" in common
    assert (
        common.replace(
            "detailed_placement -use_diamond_legalizer", "detailed_placement"
        )
        == native
    )
