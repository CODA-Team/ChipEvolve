from __future__ import annotations

import json
import subprocess
import zipfile

import pytest
from accept_common_dplevolve import (
    check_operation,
    same_physical_result,
    source_binary_bound,
    within_native_runtime_budget,
)
from run_dplevolve_native import digest, source_inventory


def physical_result():
    return {
        "hpwl_stages": {
            "global_micron": 20.0,
            "final_micron": 21.0,
            "log": "/original.log",
            "source": "openroad_dpl_log",
        },
        "legality": {"placement_violations": "", "check_report": "/original.json"},
        "hpwl": {"after_micron": 21.0},
        "displacement": {"max_displacement_micron": 2.0},
    }


def test_independent_paths_do_not_change_physical_comparison():
    original = physical_result()
    replay = physical_result()
    replay["hpwl_stages"]["log"] = "/replay.log"
    replay["legality"]["check_report"] = "/replay.json"
    assert same_physical_result(original, replay)


@pytest.mark.parametrize("field", ["hpwl_stages", "hpwl", "displacement", "legality"])
def test_changed_physical_values_are_not_a_match(field):
    original = physical_result()
    replay = physical_result()
    key = next(k for k in replay[field] if k not in {"log", "source", "check_report"})
    replay[field][key] = 99
    assert not same_physical_result(original, replay)


def test_missing_public_output_is_not_accepted(tmp_path):
    request = {
        "operation": "baseline",
        "toolchain": {"image_sha256": "bad"},
        "outputs": ["/native"],
        "inputs": {},
    }
    (tmp_path / "request.json").write_text(json.dumps(request))
    (tmp_path / "execution.json").write_text(
        json.dumps(
            {"run": {"run_id": "run-one", "status": "succeeded"}, "artifacts": []}
        )
    )
    (tmp_path / "leaf.json").write_text(
        json.dumps(
            {
                "request": request,
                "exit_code": 0,
                "output_files": {"/native/metrics.json": "hash"},
            }
        )
    )
    row = check_operation(tmp_path)
    assert row["successful"]
    assert not row["outputs_match"]
    assert not row["image_matches"]
    assert not row["public_evidence"]


def test_corrupted_registered_output_is_not_accepted(tmp_path):
    request = {
        "operation": "baseline",
        "toolchain": {"image_sha256": "bad"},
        "outputs": ["/native"],
        "inputs": {},
    }
    (tmp_path / "request.json").write_text(json.dumps(request))
    (tmp_path / "execution.json").write_text(
        json.dumps(
            {"run": {"run_id": "run-one", "status": "succeeded"}, "artifacts": []}
        )
    )
    (tmp_path / "leaf.json").write_text(
        json.dumps(
            {
                "request": request,
                "exit_code": 0,
                "output_files": {"/native/metrics.json": "bad-sha"},
            }
        )
    )
    with zipfile.ZipFile(tmp_path / "evidence.zip", "w") as bundle:
        bundle.writestr("outputs/0/metrics.json", "corrupted")
    assert not check_operation(tmp_path)["outputs_match"]


def test_candidate_binding_rejects_replaced_binary_and_source(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    subprocess.run(["git", "init", "--quiet"], cwd=source, check=True)
    (source / "algorithm.cpp").write_text("first algorithm")
    subprocess.run(["git", "add", "algorithm.cpp"], cwd=source, check=True)
    binary = tmp_path / "bin/openroad"
    binary.parent.mkdir()
    binary.write_bytes(b"candidate-binary")
    metrics = tmp_path / "metrics.json"
    metrics.write_text("original metrics")
    record = {
        "source": str(source),
        "binary": str(binary),
        "metrics": str(metrics),
        "source_files": source_inventory(source),
        "binary_sha256": digest(binary),
        "metrics_sha256": digest(metrics),
    }
    (binary.parent / "platform-build.json").write_text(json.dumps(record))
    assert source_binary_bound(record)
    binary.write_bytes(b"different tool")
    assert not source_binary_bound(record)
    binary.write_bytes(b"candidate-binary")
    (source / "algorithm.cpp").write_text("changed algorithm")
    assert not source_binary_bound(record)


@pytest.mark.parametrize("runtime", [1.177, 0, -1, float("inf"), float("nan"), None])
def test_replay_cannot_exceed_or_omit_native_runtime_budget(runtime):
    assert not within_native_runtime_budget(
        {"runtime_seconds": runtime}, {"runtime_seconds": 0.588}
    )


def test_native_runtime_budget_accepts_boundary_and_real_variation():
    for runtime in (0.737, 0.751, 0.768, 1.176):
        assert within_native_runtime_budget(
            {"runtime_seconds": runtime}, {"runtime_seconds": 0.588}
        )
