"""Fixed-method replay inherits the frozen PDK and preserves the native Tcl."""

from types import SimpleNamespace
from typing import cast

import pytest

from chip_evolve import comparisons
from chip_evolve.config import Deployment, write
from chip_evolve.jobs import digest


@pytest.mark.parametrize("platform", ["asap7", "nangate45"])
@pytest.mark.parametrize("explicit_pdk", [False, True])
def test_fixed_goal_replay_preserves_original_inputs_actions_and_technology(
    tmp_path, monkeypatch, platform, explicit_pdk
):
    original = tmp_path / "goal/baseline"
    original.mkdir(parents=True)
    binary = tmp_path / "original-openroad"
    binary.write_bytes(b"fixed professional executable")
    sdc = original.parent / "inputs/design.sdc"
    sdc.parent.mkdir()
    sdc.write_text("frozen native constraints\n")
    script = original / "evaluate.tcl"
    script.write_text(
        f"read_sdc {{{sdc}}}\nrepair_design\nrepair_timing -setup\n"
        f"detailed_placement\nglobal_route\nwrite_db {{{original / 'post_route.odb'}}}\n"
    )
    request = {
        "operation": "physical",
        "cwd": str(original),
        "command": [str(binary), "-threads", "8", "-exit", str(script)],
        "inputs": {str(sdc): digest(sdc)},
    }
    write(original.parent / "operations/physical/request.json", request)
    pdk = original.parent / "inputs" / platform
    if explicit_pdk:
        pdk = tmp_path / "frozen-original-technology"
    pdk.mkdir(parents=True)
    (pdk / "setRC.tcl").write_text(platform + " original RC\n")
    write(
        original.parent / "profile.json",
        {
            "state_root": str(original.parent),
            **({"pdk_root": str(pdk)} if explicit_pdk else {}),
        },
    )
    result = original.parent / "result.json"
    frame = {
        "run_id": "native-reference",
        "design_id": "example",
        "objective": str(tmp_path / "objective.json"),
        "native_method": {"kind": "native-baseline"},
    }
    write(result, frame)
    hashes = {path: digest(path) for path in (binary, sdc, script, result)}
    experiment = tmp_path / "replayed"

    def new_experiment(design, key):
        assert (design, key) == ("example", "fixed")
        experiment.mkdir()
        return experiment

    class Jobs:
        def __init__(self, _deployment, design, path):
            assert design == "example" and path == experiment

        def command(self, key, argv, **options):
            assert key == "native-method"
            assert argv == [
                *request["command"][:-1],
                str(experiment / "native/evaluate.tcl"),
            ]
            assert options["parent"] == frame["run_id"]
            text = (experiment / "native/evaluate.tcl").read_text()
            assert text == script.read_text().replace(
                str(original), str(experiment / "native")
            )
            assert str(sdc) in text and "repair_timing -setup" in text
            return {"run": {"run_id": "replayed-native"}}

        def log(self, _record, destination):
            destination.write_text("unit native output\n")

    def qualify(_jobs, odb, parent, objective, selected_pdk):
        assert odb == experiment / "native/post_route.odb"
        assert parent == "replayed-native"
        assert objective == tmp_path / "objective.json"
        assert selected_pdk == pdk
        return {"run_id": "measured"}

    monkeypatch.setattr(comparisons, "Jobs", Jobs)
    monkeypatch.setattr(comparisons, "container", lambda _deployment, argv: argv)
    monkeypatch.setattr(comparisons, "qualify", qualify)
    monkeypatch.setattr(
        comparisons,
        "compare",
        lambda left, right: {
            "same_method": left == frame and right["run_id"] == "measured"
        },
    )
    deployment = SimpleNamespace(
        experiment=new_experiment,
        design=lambda _design: {"platform": platform, "top": "example"},
    )
    receipt = comparisons.replay_goal(cast(Deployment, deployment), result, "fixed")
    assert receipt["comparison"] == {"same_method": True}
    assert receipt["input_files"] == request["inputs"]
    assert all(digest(path) == sha for path, sha in hashes.items())
