"""A routing control must preserve checkpoints and placement/routing commands."""

from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from admin import goal_route_control
from admin.goal_route_control import without_repairs
from chip_evolve.config import Deployment, read, write
from chip_evolve.jobs import digest


def test_control_removes_actions_but_preserves_reports_and_physical_pipeline():
    text = 'read_def {input.def}\nrepair_design\nrepair_power -phase early_forced_reclaim -proportion 80\nputs "post_repair_power"\ndetailed_placement\nglobal_route\nwrite_db {post_route.odb}\n'
    control, removed = without_repairs(text)
    assert removed == [
        "repair_design",
        "repair_power -phase early_forced_reclaim -proportion 80",
    ]
    assert (
        control
        == 'read_def {input.def}\nputs "post_repair_power"\ndetailed_placement\nglobal_route\nwrite_db {post_route.odb}\n'
    )
    assert "repair_power -phase" in text


@pytest.mark.parametrize(
    "text",
    [
        "repair_design\n",
        "repair_power -phase p \\\n  -proportion 80\n",
        "repair_power -phase {complex}\n",
    ],
)
def test_unsupported_controls_are_rejected_instead_of_partially_removing_actions(text):
    with pytest.raises(ValueError):
        without_repairs(text)


def test_timing_only_control_keeps_the_actual_reports_and_route():
    text = "read_db {design.odb}\nrepair_design\nrepair_timing -setup\nreport_checks\ndetailed_placement -use_diamond_legalizer\nglobal_route\nwrite_db {post_route.odb}\n"
    control, removed = without_repairs(text)
    assert removed == ["repair_design", "repair_timing -setup"]
    assert (
        control
        == "read_db {design.odb}\nreport_checks\ndetailed_placement -use_diamond_legalizer\nglobal_route\nwrite_db {post_route.odb}\n"
    )


@pytest.mark.parametrize("platform", ["asap7", "nangate45"])
@pytest.mark.parametrize("explicit_pdk", [False, True])
def test_native_timing_baseline_control_uses_its_own_input_binary_and_pipeline(
    tmp_path, monkeypatch, platform, explicit_pdk
):
    original = tmp_path / "goal" / "baseline"
    original.mkdir(parents=True)
    binary = tmp_path / "install" / "bin" / "openroad"
    binary.parent.mkdir(parents=True)
    binary.write_bytes(b"original professional executable")
    write(binary.parent / "platform-build.json", {"binary_sha256": digest(binary)})
    write(original / "baseline.json", {"checks": [{"detail": str(binary)}]})
    script = original / "evaluate.tcl"
    script.write_text(
        f"read_def {{{tmp_path / 'input.def'}}}\nrepair_design\nrepair_timing -setup\ndetailed_placement -use_diamond_legalizer\nglobal_route\nwrite_db {{{original / 'post_route.odb'}}}\n"
    )
    source = tmp_path / "source.json"
    write(source, {"run_id": "actual-source"})
    write(original.parent / "input-receipt.json", {"source": str(source)})
    result = original.parent / "result.json"
    write(
        result,
        {
            "design_id": "jpeg",
            "objective": "original-objective.json",
            "native_method": {"kind": "native-baseline"},
        },
    )
    pdk = original.parent / "inputs" / platform
    if explicit_pdk:
        pdk = tmp_path / "frozen-technology"
        write(original.parent / "profile.json", {"pdk_root": str(pdk)})
    hashes = {p: digest(p) for p in [script, result, source, binary]}
    folder = tmp_path / "experiments" / "jpeg" / "control"

    def experiment(design, key):
        assert (design, key) == ("jpeg", "control")
        folder.mkdir(parents=True)
        return folder

    class Jobs:
        def __init__(self, deployment, design, path):
            assert design == "jpeg" and path == folder

        def command(self, key, command, **options):
            assert command == [
                str(binary),
                "-exit",
                str(folder / "native/evaluate.tcl"),
            ]
            assert options["parent"] == "actual-source"
            assert options["objective"] == Path("original-objective.json")
            rendered = (folder / "native/evaluate.tcl").read_text()
            assert "repair_" not in rendered
            assert "detailed_placement -use_diamond_legalizer\nglobal_route" in rendered
            assert str(tmp_path / "input.def") in rendered
            assert str(folder / "native/post_route.odb") in rendered
            return {"run": {"run_id": "control-producer"}}

        def log(self, record, destination):
            destination.write_text("actual control output")

    checkpoints = []
    monkeypatch.setattr(goal_route_control, "Jobs", Jobs)
    monkeypatch.setattr(
        goal_route_control, "container", lambda deployment, command: command
    )
    monkeypatch.setattr(
        goal_route_control, "checkpoint", lambda path, **kw: checkpoints.append(kw)
    )
    monkeypatch.setattr(
        goal_route_control,
        "finish",
        lambda deployment, path: {"run_id": "common-measurement"},
    )
    deployment = SimpleNamespace(
        state=tmp_path,
        experiment=experiment,
        design=lambda _design: {"platform": platform},
    )
    assert goal_route_control.run(cast(Deployment, deployment), result, "control") == {
        "run_id": "common-measurement"
    }
    saved = read(folder / "control-method.json")
    assert saved["removed_commands"] == ["repair_design", "repair_timing -setup"]
    assert checkpoints[0]["producer"] == "control-producer"
    assert checkpoints[0]["pdk"] == pdk
    assert checkpoints[0]["native_method"]["kind"] == "conversion-routing-control"
    assert all(digest(p) == sha for p, sha in hashes.items())
