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
