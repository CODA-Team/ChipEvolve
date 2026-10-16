"""Adoption uses verified results and serializes competing business decisions."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from eda_toolkits.objectives import objective_id

from admin.test_local_business import deployment
from chip_evolve import selection
from chip_evolve.config import read, write
from chip_evolve.jobs import digest


def validation_for(result, reference):
    frame = read(result)
    netlist = read(reference)["files"]["v"]
    path = result.parent / (result.stem + "-validation.json")
    write(
        path,
        {
            "result": str(result),
            "reference": str(reference),
            "result_sha256": digest(result),
            "reference_sha256": digest(reference),
            "passed": True,
            "replay_exact": True,
            "sdk_identity_passed": True,
            "logic": {
                "proven_points": 1,
                "top_output_bits": 1,
                "unproven_points": 0,
                "input_hashes": {netlist: digest(reference.parent / "design.v")},
            },
            "independent_replay": {
                "reference_run_id": frame["run_id"],
                "condition_id": frame["condition_id"],
                "objective_id": frame["objective_id"],
                "constraint_violations": [],
                "deltas": {
                    key: {"delta": 0}
                    for key in (
                        "finish__timing__setup__tns",
                        "finish__timing__setup__ws",
                        "finish__timing__hold__tns",
                        "finish__power__total",
                        "finish__design__instance__area",
                        "finish__design__core__area",
                        "finish__design__die__area",
                    )
                },
            },
        },
    )
    return path


def frame_at(root, name, power=1.0):
    directory = root / name
    directory.mkdir()
    netlist = root / "reference/design.v"
    if not netlist.exists():
        netlist.parent.mkdir(exist_ok=True)
        netlist.write_text("module test(input a, output y); assign y=a; endmodule\n")
    goal = {
        "schema_version": "chip-evolve.objective.v1",
        "design_id": "gcd",
        "conditions": {
            "libraries": [{"path": str(netlist), "sha256": digest(netlist)}],
            "sdc": {"path": str(netlist), "sha256": digest(netlist)},
        },
        "constraints": {
            "setup_tns_ns_min": 0,
            "hold_tns_ns_min": 0,
            "max_slew_violations": 0,
            "max_cap_violations": 0,
            "placement_violations": 0,
            "route_drc": 0,
            "power_total_w_max": 2,
            "cell_area_um2_max": 20,
            "core_area_um2_max": 30,
            "die_area_um2_max": 40,
        },
    }
    goal["objective_id"] = objective_id(goal)
    write(root / "objective.json", goal)
    result = directory / "result.json"
    write(
        result,
        {
            "design_id": "gcd",
            "run_id": name,
            "objective": str(root / "objective.json"),
            "objective_id": goal["objective_id"],
            "condition_id": "condition",
            "files": {"v": str(netlist)},
            "route_drc": 0,
            "metrics": {
                "finish__timing__setup__tns": 0,
                "finish__timing__setup__ws": 0.1,
                "finish__timing__hold__tns": 0,
                "finish__timing__drv__max_slew": 0,
                "finish__timing__drv__max_cap": 0,
                "design__violations": 0,
                "finish__power__total": power,
                "finish__design__instance__area": 10,
                "finish__design__core__area": 30,
                "finish__design__die__area": 40,
            },
        },
    )
    return result


@pytest.mark.parametrize("mutation", ["result", "proof", "replay", "receipt"])
def test_missing_or_mismatched_validation_never_adopts(tmp_path, mutation):
    d = deployment(tmp_path)
    reference = frame_at(tmp_path, "reference")
    result = frame_at(tmp_path, "candidate", 0.9)
    validation = validation_for(result, reference)
    data = read(validation)
    if mutation == "result":
        value = read(result)
        value["run_id"] = "different"
        write(result, value)
    elif mutation == "proof":
        data["logic"]["unproven_points"] = 1
    elif mutation == "replay":
        data["independent_replay"]["deltas"]["finish__power__total"]["delta"] = 0.01
    else:
        data["passed"] = False
    write(validation, data)
    with pytest.raises(ValueError):
        selection.select(d, result, "must reject", validation=validation)
    assert not (tmp_path / "designs/gcd/incumbent.json").exists()
    with pytest.raises(FileNotFoundError):
        selection.select(d, result, "no receipt", validation=tmp_path / "missing")


def test_competing_adoptions_keep_better_result_and_leave_history_unchanged(
    tmp_path, monkeypatch
):
    d = deployment(tmp_path)
    reference = frame_at(tmp_path, "reference")
    better = frame_at(tmp_path, "better", 0.8)
    worse = frame_at(tmp_path, "worse", 0.9)
    paths = [(path, validation_for(path, reference)) for path in (better, worse)]
    historical = better.parent / "adoption.json"
    historical.write_text("historical decision remains immutable\n")
    barrier = Barrier(2)
    original = selection.checked_validation

    def checked(*args):
        verified = original(*args)
        barrier.wait(timeout=5)
        return verified

    monkeypatch.setattr(selection, "checked_validation", checked)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda row: selection.select(d, row[0], "parallel", validation=row[1]),
                paths,
            )
        )
    assert read(tmp_path / "designs/gcd/incumbent.json")["run_id"] == "better"
    assert len(list((tmp_path / "designs/gcd/decisions").glob("*.json"))) == 2
    assert all(read(row["decision"]) == row for row in results)
    assert historical.read_text() == "historical decision remains immutable\n"


def test_changed_retained_result_cannot_be_silently_replaced(tmp_path):
    d = deployment(tmp_path)
    reference = frame_at(tmp_path, "reference")
    first = frame_at(tmp_path, "first", 0.9)
    selection.select(d, first, "first", validation=validation_for(first, reference))
    value = read(first)
    value["run_id"] = "tampered"
    write(first, value)
    second = frame_at(tmp_path, "second", 0.8)
    with pytest.raises(ValueError, match="Retained result changed"):
        selection.select(
            d, second, "next", validation=validation_for(second, reference)
        )
