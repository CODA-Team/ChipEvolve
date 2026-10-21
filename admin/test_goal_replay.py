"""Fixed Goal replay must retain the measured source's native recipe."""

import hashlib
import runpy
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from admin.test_local_business import deployment
from chip_evolve.config import read, write
from chip_evolve.goal_replay import descriptor, write_driver


def test_cli_accepts_explicit_goal_replay_source_before_creating_experiment(
    monkeypatch,
):
    from chip_evolve import cli

    class Accepted(Exception):
        pass

    def experiment(design, key):
        assert (design, key) == ("gcd", "replay")
        raise Accepted()

    monkeypatch.setattr(
        cli,
        "Deployment",
        lambda path: SimpleNamespace(
            value={"qualified_environments": {}}, experiment=experiment
        ),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "chip-evolve",
            "--config",
            "/config.json",
            "run",
            "--design",
            "gcd",
            "--key",
            "replay",
            "--capability",
            "goal",
            "--source",
            "/physical/result.json",
            "--code-source",
            "/method/result.json",
            "--operation",
            "replay",
        ],
    )
    with pytest.raises(Accepted):
        cli.main()


def source_result(tmp_path):
    root = tmp_path / "original-goal"
    root.mkdir()
    source = root / "campaign/parents/cpp-hash/source"
    source.mkdir(parents=True)
    (source.parent / ".source_snapshot_complete").write_text("complete\n")
    write(root / "evolve-config.json", {"power_reclaim_proportion_percent": 80})
    cpp = source / "src/rsz/Example.cc"
    cpp.parent.mkdir(parents=True)
    cpp.write_text("original source")
    write(root / "delivery-checkpoint.json", {"producer": "measured-producer"})
    operation = root / "operations/physical"
    write(
        operation / "execution.json",
        {"run": {"run_id": "measured-producer", "status": "succeeded"}},
    )
    write(
        operation / "request.json",
        {
            "source_files": {
                "src/rsz/Example.cc": hashlib.sha256(cpp.read_bytes()).hexdigest()
            }
        },
    )
    result = root / "result.json"
    write(
        result,
        {
            "design_id": "aes",
            "conditions": {"toolchain": {"image": "fixed"}},
            "native_method": {
                "kind": "native-search",
                "parent": {
                    "source_hash": "cpp-hash",
                    "evaluation_mode": "power_only",
                    "timing_recipe_id": "legacy_setup",
                },
            },
        },
    )
    return result


def test_original_power_mode_is_kept_instead_of_the_p0_timing_default(tmp_path):
    d = deployment(tmp_path)
    d.value["toolchain"] = {"image": "fixed"}
    result = source_result(tmp_path)
    method = descriptor(d, result)
    assert method["source_root"].endswith("/cpp-hash/source")
    assert method["origin_design_id"] == "aes"
    assert method["evaluation_mode"] == "power_only"
    assert method["timing_recipe_id"] == "legacy_setup"
    assert method["recipe_parameters"] == {"power_reclaim_proportion_percent": 80}


@pytest.mark.parametrize(
    "change", ["p0", "toolchain", "unknown_mode", "missing_source", "changed_source"]
)
def test_wrong_or_incomplete_source_never_falls_back_to_default(tmp_path, change):
    d = deployment(tmp_path)
    d.value["toolchain"] = {"image": "fixed"}
    result = source_result(tmp_path)
    value = read(result)
    if change == "p0":
        value["native_method"]["kind"] = "native-baseline"
    elif change == "toolchain":
        value["conditions"]["toolchain"] = {"image": "other"}
    elif change == "unknown_mode":
        value["native_method"]["parent"]["evaluation_mode"] = "unknown"
    elif change == "missing_source":
        (result.parent / "campaign/parents/cpp-hash/.source_snapshot_complete").unlink()
    else:
        (
            result.parent / "campaign/parents/cpp-hash/source/src/rsz/Example.cc"
        ).write_text("wrong source")
    write(result, value)
    with pytest.raises(ValueError):
        descriptor(d, result)


def test_driver_calls_native_parent_evaluator_with_private_source_and_original_mode(
    tmp_path, monkeypatch
):
    output = tmp_path / "measurement"
    method = tmp_path / "method.json"
    write(
        method,
        {
            "source_root": "/original/source",
            "parent": {"source_hash": "selected"},
            "evaluation_mode": "power_only",
            "timing_recipe_id": "original_recipe",
        },
    )
    calls = []
    config = SimpleNamespace(state_root=output, evaluator="native")

    def evaluate(**kwargs):
        calls.append(kwargs)
        assert kwargs["source"] == output / "workspace/source"
        assert kwargs["parent"].source_hash == "selected"
        assert kwargs["optimization_mode"] == "power_only"
        assert kwargs["timing_recipe_id"] == "original_recipe"
        return {"ok": True, "metrics": {"dynamic_power_pw": 123}}

    def clone(source, destination):
        assert source == Path("/original/source")
        destination.mkdir(parents=True)

    registry = SimpleNamespace(
        evaluator=lambda name: SimpleNamespace(evaluate_parent=evaluate)
    )
    modules = {
        "goalevolve.config": {
            "load_config": lambda path: config,
            "build_runtime": lambda config: ("original-contract", registry),
        },
        "goalevolve.core.models": {"Parent": SimpleNamespace},
        "goalevolve.core.io": {"atomic_json": write},
        "goalevolve.execution.workspace": {"clone_source_tree": clone},
    }
    for name, values in modules.items():
        module = ModuleType(name)
        module.__dict__.update(values)
        monkeypatch.setitem(sys.modules, name, module)
    script = tmp_path / "native-driver.py"
    write_driver(script)
    monkeypatch.setattr(sys, "argv", [str(script), "/config.json", str(method)])
    runpy.run_path(str(script))
    assert len(calls) == 1
    assert read(output / "baseline.json")["metrics"] == {"dynamic_power_pw": 123}


def measured_candidate_result(tmp_path):
    from chip_evolve.jobs import digest

    promoted = source_result(tmp_path)
    origin = promoted.parent
    source = origin / "campaign/parents/cpp-hash/source"
    artifact = origin / "campaign/rounds/round_001/students/student_2/artifacts"
    record = artifact / "candidate.json"
    write(
        record,
        {
            "source_commit": "measured-student2-commit",
            "metrics": {
                "dynamic_power_pw": 123,
                "leakage_power_pw": 4,
                "tns_abs_ns": 0.2,
            },
            "implementation_diff": "actual tested CPP change",
            "evaluation_error": None,
            "artifacts": {"candidate_source": str(source)},
            "checks": [
                {"name": name, "passed": True}
                for name in ["build", "flow", "metrics", "placement", "lec"]
            ],
            "hypothesis": {
                "evaluation_mode": "power_then_timing",
                "timing_recipe_id": "wns_path_deep",
            },
        },
    )
    verdict = artifact / "evidence.json"
    write(verdict, {"state": "validated", "goal_distance": 0.25})
    write(
        artifact.parent / "workspace_manifest.json",
        {"parent_source_hash": "original-parent"},
    )
    candidate = origin / "native-candidates/candidates/student2/result.json"
    write(
        candidate,
        {
            "design_id": "aes",
            "conditions": {"toolchain": {"image": "fixed"}},
            "native_method": {
                "kind": "native-candidate",
                "capability": "goal",
                "origin_experiment": str(origin),
                "candidate": {
                    "candidate_id": "round_001-student_2",
                    "source_ref": "measured-student2-commit",
                    "native_record": {"path": str(record), "sha256": digest(record)},
                    "native_verdict_record": {
                        "path": str(verdict),
                        "sha256": digest(verdict),
                    },
                },
            },
        },
    )
    write(
        candidate.parent / "delivery-checkpoint.json", {"producer": "measured-producer"}
    )
    request = origin / "operations/physical/request.json"
    settings = read(request)
    settings["source"] = str(source)
    write(request, settings)
    return candidate, promoted, record


def test_measured_student_candidate_reuses_its_own_source_and_recipe_without_promotion(
    tmp_path,
):
    d = deployment(tmp_path)
    d.value["toolchain"] = {"image": "fixed"}
    result, promoted, _ = measured_candidate_result(tmp_path)
    original_parent_bytes = promoted.read_bytes()
    method = descriptor(d, result)
    assert method["evaluation_mode"] == "power_then_timing"
    assert method["timing_recipe_id"] == "wns_path_deep"
    assert method["parent"]["source_commit"] == "measured-student2-commit"
    assert method["parent"]["metrics"]["dynamic_power_pw"] == 123
    assert method["source_identity"]["checked_files"] == 1
    assert (
        method["source_identity"]["candidate_evidence"]["native_promotion_changed"]
        is False
    )
    assert promoted.read_bytes() == original_parent_bytes


@pytest.mark.parametrize(
    "problem",
    [
        "record_changed",
        "wrong_source_commit",
        "failed_native_check",
        "changed_cpp",
        "wrong_producer_source",
    ],
)
def test_candidate_replay_rejects_wrong_or_failed_native_evidence(tmp_path, problem):
    from chip_evolve.jobs import digest

    d = deployment(tmp_path)
    d.value["toolchain"] = {"image": "fixed"}
    result, promoted, record = measured_candidate_result(tmp_path)
    frame = read(result)
    if problem in ["record_changed", "wrong_source_commit", "failed_native_check"]:
        value = read(record)
        if problem == "failed_native_check":
            value["checks"][0]["passed"] = False
        else:
            value["source_commit"] = "different"
        write(record, value)
        if problem != "record_changed":
            frame["native_method"]["candidate"]["native_record"]["sha256"] = digest(
                record
            )
    elif problem == "changed_cpp":
        (
            promoted.parent / "campaign/parents/cpp-hash/source/src/rsz/Example.cc"
        ).write_text("changed")
    else:
        request = promoted.parent / "operations/physical/request.json"
        value = read(request)
        value["source"] = "/different/candidate/source"
        write(request, value)
    write(result, frame)
    with pytest.raises(ValueError):
        descriptor(d, result)
