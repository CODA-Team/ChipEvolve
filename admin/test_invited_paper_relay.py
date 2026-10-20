"""Professional handoffs preserve routed work and pursue the business timing goal."""

import pytest

from admin.test_local_business import deployment
from chip_evolve import physical
from chip_evolve.config import write
from chip_evolve.delivery import checkpoint, finish
from chip_evolve.jobs import Jobs
from chip_evolve.native import _goal_targets


@pytest.mark.parametrize("baseline_tns", [0.0061528841, 2.000549078])
def test_goal_closes_timing_without_replacing_declared_power_targets(
    tmp_path, baseline_tns
):
    objective = tmp_path / "objective.json"
    write(objective, {"constraints": {"setup_tns_ns_min": 0}})
    targets = {
        "dynamic_power_pw": 37,
        "leakage_power_pw": 4,
        "tns_abs_ns": baseline_tns,
    }
    assert _goal_targets(targets, objective) == {
        "dynamic_power_pw": 37,
        "leakage_power_pw": 4,
        "tns_abs_ns": 0,
    }
    assert targets["tns_abs_ns"] == baseline_tns


@pytest.mark.parametrize("preserve", [False, True])
@pytest.mark.parametrize("design_id,memory_gib", [("gcd", 4), ("ibex", 12)])
def test_delivery_routes_only_when_the_checkpoint_requires_it(
    tmp_path, monkeypatch, preserve, design_id, memory_gib
):
    d = deployment(tmp_path)
    d.value.update(
        runtime={"executable": "runtime", "image": "image", "bind_roots": []},
        tools={"openroad": "openroad"},
    )
    d.value["designs"][design_id] = {
        "libraries": [],
        "sdc": str(tmp_path / "design.sdc"),
        "orfs_execution": {"memory_gib": memory_gib},
    }
    experiment = d.experiment(design_id, "routed" if preserve else "global")
    odb = tmp_path / "parent.odb"
    odb.write_bytes(b"actual native geometry")
    objective = tmp_path / "objective.json"
    write(objective, {})
    pdk = tmp_path / "pdk"
    pdk.mkdir()
    for name in ["setRC.tcl", "rcx_patterns.rules"]:
        (pdk / name).write_text("frozen RC")
    native = {"kind": "native-ECO" if preserve else "native-search"}
    if preserve:
        native["physical_stage"] = "detailed_route"
        native["route_drc"] = 0
    checkpoint(
        experiment,
        design_id=design_id,
        odb=odb,
        producer="actual-native-run",
        objective=objective,
        pdk=pdk,
        native_method=native,
    )
    requests = []

    def command(self, key, argv, **options):
        assert options["parent"] == "actual-native-run"
        assert options["memory_gib"] == memory_gib
        script = (experiment / "qualification/route.tcl").read_text()
        for operation in ["dbWire_destroy", "global_route", "detailed_route -"]:
            assert (operation in script) is not preserve
        assert ("check_drc -output_file" in script) is preserve
        assert ("Routed delivery requires existing signal wires" in script) is preserve
        assert "extract_parasitics" in script
        write(
            experiment / "qualification/native-metrics.json",
            {"route__drc_errors": 99 if preserve else 0},
        )
        requests.append(options)
        return {"run": {"run_id": "extraction"}}

    monkeypatch.setattr(Jobs, "command", command)
    monkeypatch.setattr(physical, "measure", lambda *a: {"run_id": "measured"})
    monkeypatch.setattr(physical, "publish", lambda _jobs, frame, **kw: frame)
    monkeypatch.setattr("chip_evolve.code_evidence.maybe_collect", lambda *a: None)
    frame = finish(d, experiment)
    assert len(requests) == 1
    assert frame["route_drc"] == 0
    assert frame["native_method"] == native
    if preserve:
        assert frame["qualification"]["standalone_drc_markers"] == 99
    assert odb.read_bytes() == b"actual native geometry"
    assert (
        frame["qualification"].get("routing_action")
        == "preserved_native_detailed_route"
    ) is preserve
