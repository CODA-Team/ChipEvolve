"""Explicit ORFS successors preserve native producers and saved routing states."""

from pathlib import Path
from unittest.mock import patch

import pytest

from admin.test_local_business import deployment
from chip_evolve import cli, native_physical, physical
from chip_evolve.config import read, write
from chip_evolve.delivery import checkpoint, finish
from chip_evolve.jobs import Jobs, digest


def test_orfs_replay_does_not_silently_launch_a_new_baseline(tmp_path, monkeypatch):
    d = deployment(tmp_path)
    source = tmp_path / "source/result.json"
    source.parent.mkdir()
    write(source, {"design_id": "gcd"})

    def baseline(*args, **kwargs):
        pytest.fail("Explicit physical replay must consume its registered source")

    called = []

    def successor(deploy, design_id, experiment, actual_source, seconds, *, objective):
        assert deploy.path == d.path
        assert design_id == "gcd" and actual_source == source
        called.append(experiment)
        return {"run_id": "new-physical-run", "metrics": {}}

    monkeypatch.setattr(physical, "baseline", baseline)
    monkeypatch.setattr(native_physical, "repair", successor)
    with patch(
        "sys.argv",
        [
            "chip-evolve",
            "--config",
            str(d.path),
            "run",
            "--design",
            "gcd",
            "--key",
            "successor",
            "--capability",
            "orfs",
            "--operation",
            "replay",
            "--source",
            str(source),
        ],
    ):
        assert cli.main() == 0
    assert called == [d.state / "experiments/gcd/successor"]


@pytest.mark.parametrize(
    "extra", [["--source", "/source/result.json"], ["--operation", "replay"]]
)
def test_incomplete_orfs_replay_request_stops_before_creating_experiment(
    tmp_path, extra
):
    d = deployment(tmp_path)
    with (
        patch(
            "sys.argv",
            [
                "chip-evolve",
                "--config",
                str(d.path),
                "run",
                "--design",
                "gcd",
                "--key",
                "unused",
                "--capability",
                "orfs",
                *extra,
            ],
        ),
        pytest.raises(SystemExit) as error,
    ):
        cli.main()
    assert error.value.code == 2
    assert not (tmp_path / "experiments").exists()


def test_explicit_global_route_delivery_keeps_native_guides(tmp_path, monkeypatch):
    d = deployment(tmp_path)
    sdc = tmp_path / "design.sdc"
    sdc.write_text("frozen constraints")
    d.value.update(
        runtime={"executable": "runtime", "image": "image", "bind_roots": []},
        tools={"openroad": "openroad"},
    )
    d.value["designs"]["gcd"] = {
        "libraries": [],
        "sdc": str(sdc),
        "orfs_execution": {"memory_gib": 4},
    }
    objective = tmp_path / "objective.json"
    write(
        objective,
        {
            "design_id": "gcd",
            "conditions": {
                "libraries": [],
                "sdc": {"path": str(sdc), "sha256": digest(sdc)},
            },
        },
    )
    pdk = tmp_path / "pdk"
    pdk.mkdir()
    for name in ("setRC.tcl", "rcx_patterns.rules"):
        (pdk / name).write_text("frozen RC")
    odb = tmp_path / "native-grt.odb"
    odb.write_bytes(b"repaired cells and saved native guides")
    e = d.experiment("gcd", "successor")
    checkpoint(
        e,
        design_id="gcd",
        odb=odb,
        producer="physical-successor",
        objective=objective,
        pdk=pdk,
        native_method={
            "kind": "native-ORFS-physical-repair",
            "physical_stage": "global_route",
            "origin_producer": "original-Goal",
        },
    )

    def command(self, key, argv, **options):
        script = (e / "qualification/route.tcl").read_text()
        assert "global_route -congestion_iterations" not in script
        assert "set_routing_layers" not in script
        assert "getGuides" in script
        assert "detailed_route -output_drc" in script
        assert options["parent"] == "physical-successor"
        write(e / "qualification/native-metrics.json", {"route__drc_errors": 0})
        return {"run": {"run_id": "DRT"}}

    monkeypatch.setattr(Jobs, "command", command)
    monkeypatch.setattr(physical, "measure", lambda *a: {"run_id": "measured"})
    monkeypatch.setattr(physical, "publish", lambda _jobs, frame, **kw: frame)
    monkeypatch.setattr("chip_evolve.code_evidence.maybe_collect", lambda *a: None)
    frame = finish(d, e)
    assert frame["qualification"]["routing_action"] == "consumed_native_global_route"
    assert frame["native_method"]["origin_producer"] == "original-Goal"
    assert odb.read_bytes() == b"repaired cells and saved native guides"


def prepared_source(tmp_path):
    d = deployment(tmp_path)
    image = tmp_path / "image.sif"
    image.write_bytes(b"pinned test image")
    sdc = tmp_path / "design.sdc"
    sdc.write_text(
        "set_cmd_units -time ps\ncreate_clock -name core -period 310 [get_ports clk]\n"
    )
    d.value.update(
        runtime={"image": str(image), "executable": "runtime", "bind_roots": []},
        toolchain={"image_sha256": digest(image)},
        tools={"openroad": "openroad", "yosys": "yosys"},
    )
    d.value["designs"]["gcd"] = {
        "sdc": str(sdc),
        "clock_period_ns": 0.31,
        "libraries": [],
        "orfs_config": "designs/asap7/gcd/config.mk",
    }
    odb = tmp_path / "parent.odb"
    odb.write_bytes(b"post CTS state")
    source, objective = tmp_path / "source.json", tmp_path / "objective.json"
    write(source, {"original_result": "unchanged"})
    write(objective, {"original_objective": "unchanged"})
    pdk = tmp_path / "pdk"
    pdk.mkdir()
    for name in ("setRC.tcl", "rcx_patterns.rules"):
        (pdk / name).write_text("frozen RC")
    experiment = d.experiment("gcd", "successor")
    return (
        Jobs(d, "gcd", experiment),
        source,
        {"odb": str(odb), "pdk": str(pdk)},
        objective,
    )


@pytest.mark.parametrize("changed", ["source", "staged_ODB", "RC_model"])
def test_preparation_and_recovery_keep_original_source_and_frozen_inputs(
    tmp_path, changed
):
    jobs, source, original, objective = prepared_source(tmp_path)
    root = native_physical.prepare(jobs, source, original, objective, 900)
    assert native_physical.prepare(jobs, source, original, objective, 900) == root
    assert (root / "orfs/results/4_cts.odb").read_bytes() == b"post CTS state"
    target = {
        "source": source,
        "staged_ODB": root / "orfs/results/4_cts.odb",
        "RC_model": Path(original["pdk"]) / "rcx_patterns.rules",
    }[changed]
    target.write_text("changed after preparation")
    with pytest.raises(ValueError, match="changed"):
        native_physical.prepare(jobs, source, original, objective, 900)


def test_native_observations_preserve_signed_setup_and_hold_separately():
    facts = native_physical.timing_facts(
        "CHIPEVOLVE_GRT_TIMING_NS -0.28 -92.96 0.0025 0.0\nCHIPEVOLVE_GRT_ELECTRICAL 0 2 0\n"
    )
    assert facts["globalroute__timing__setup__tns"] == -92.96
    assert facts["globalroute__timing__hold__tns"] == 0
    assert facts["globalroute__timing__hold__ws"] == 0.0025
    assert facts["globalroute__timing__drv__max_cap"] == 2


@pytest.mark.parametrize(
    "text",
    [
        "",
        "CHIPEVOLVE_GRT_TIMING_NS 0 0 0 0\n",
        "CHIPEVOLVE_GRT_TIMING_NS 0 0 0 0\nCHIPEVOLVE_GRT_TIMING_NS 1 0 0 0\nCHIPEVOLVE_GRT_ELECTRICAL 0 0 0\n",
    ],
)
def test_incomplete_or_ambiguous_native_observations_are_not_adopted(text):
    with pytest.raises(ValueError):
        native_physical.timing_facts(text)


def test_recovery_before_delivery_checkpoint_reuses_the_explicit_successor(
    tmp_path, monkeypatch
):
    from chip_evolve.delivery import recover

    d = deployment(tmp_path)
    e = d.experiment("gcd", "recover")
    source = tmp_path / "source.json"
    write(
        e / "request.json",
        {
            "design": "gcd",
            "capability": "orfs",
            "operation": "replay",
            "source": str(source),
            "seconds": 900,
        },
    )
    calls = []

    def repair(deploy, design, experiment, original, seconds, *, objective):
        calls.append((design, experiment, original, seconds))
        return {"run_id": "same-successor"}

    monkeypatch.setattr(native_physical, "repair", repair)
    monkeypatch.setattr(
        physical, "baseline", lambda *a, **k: pytest.fail("Must not restart synthesis")
    )
    assert recover(d, "gcd", "recover")["run_id"] == "same-successor"
    assert calls == [("gcd", e, source, 900)]


@pytest.mark.parametrize(
    "kind", ["native-ORFS-physical-repair", "native-explicit-GRT-repair"]
)
def test_independent_validation_of_successor_does_not_rerun_native_repair(
    tmp_path, monkeypatch, kind
):
    from chip_evolve import validation

    jobs, source, original, objective = prepared_source(tmp_path)
    result = jobs.experiment / "result.json"
    write(
        result,
        {
            "design_id": "gcd",
            "objective": str(objective),
            "native_method": {"kind": kind},
        },
    )
    write(
        jobs.experiment / "request.json",
        {"design": "gcd", "capability": "orfs", "operation": "replay", "seconds": 900},
    )
    checkpoint(
        jobs.experiment,
        design_id="gcd",
        odb=Path(original["odb"]),
        producer="native-successor",
        objective=objective,
        pdk=Path(original["pdk"]),
        extra_inputs=(source,),
        native_method={
            "kind": kind,
            "physical_stage": "global_route",
        },
    )
    child = jobs.deployment.experiment("gcd", "independent")

    def finish(deploy, experiment):
        saved = read(experiment / "delivery-checkpoint.json")
        assert saved["producer"] == "native-successor"
        assert saved["native_method"]["physical_stage"] == "global_route"
        assert Path(saved["odb"]).read_bytes() == b"post CTS state"
        return {"run_id": "independent-measurement"}

    monkeypatch.setattr(validation, "finish", finish)
    monkeypatch.setattr(
        physical,
        "baseline",
        lambda *a, **kw: pytest.fail("Must not rerun full baseline"),
    )
    assert (
        validation.replay(jobs.deployment, result, child)["run_id"]
        == "independent-measurement"
    )


def test_completed_recovery_checks_the_frozen_origin_reference(tmp_path):
    from chip_evolve.delivery import recover

    jobs, source, original, objective = prepared_source(tmp_path)
    e = jobs.experiment
    checkpoint(
        e,
        design_id="gcd",
        odb=Path(original["odb"]),
        producer="native-successor",
        objective=objective,
        pdk=Path(original["pdk"]),
        extra_inputs=(source,),
        native_method={"physical_stage": "global_route"},
    )
    write(
        e / "request.json",
        {"design": "gcd", "capability": "orfs", "operation": "replay"},
    )
    write(e / "result.json", {"design_id": "gcd", "run_id": "completed"})
    write(e / "status.json", {"status": "succeeded"})
    assert recover(jobs.deployment, "gcd", e.name)["run_id"] == "completed"
    source.write_text("unrelated origin")
    with pytest.raises(ValueError, match="Delivery input changed"):
        recover(jobs.deployment, "gcd", e.name)


def test_successful_job_receipt_is_immutable_while_recovery_checks_live_status(
    tmp_path, monkeypatch
):
    class Client:
        def submit(self, task, **options):
            return {"run": {"run_id": "original-successful-run"}}

    observed = []

    def wait(client, run_id, folder, policy):
        observed.append(run_id)
        return {
            "run": {"run_id": run_id, "status": "succeeded"},
            "artifacts": [],
            "wait_seconds": 8.0 if len(observed) == 1 else 0.01,
        }

    monkeypatch.setattr("chip_evolve.jobs.KernelClient", lambda *a, **kw: Client())
    monkeypatch.setattr("chip_evolve.jobs.wait_run", wait)
    d = deployment(tmp_path)
    jobs = Jobs(d, "gcd", d.experiment("gcd", "receipt"))
    first = jobs.submit("export", {"adapter": "orfs"}, [])
    second = jobs.submit("export", {"adapter": "orfs"}, [])
    assert second == first
    assert first["wait_seconds"] == 8.0
    assert observed == ["original-successful-run", "original-successful-run"]


def test_routing_context_preserves_script_specific_environment_and_clock_bounds(
    tmp_path,
):
    import os
    import subprocess
    import sys

    jobs, source, original, objective = prepared_source(tmp_path)
    root = native_physical.prepare(jobs, source, original, objective, 900)
    initializer = tmp_path / "fastroute.tcl"
    initializer.write_text(
        "set_global_routing_layer_adjustment $::env(MIN_ROUTING_LAYER)-$::env(MAX_ROUTING_LAYER) $::env(FLOORPLAN_PIN_LAYER_ADJUST)\n"
    )
    env = dict(
        os.environ,
        MIN_ROUTING_LAYER="metal2",
        MAX_ROUTING_LAYER="metal10",
        MIN_CLK_ROUTING_LAYER="metal4",
        ROUTING_LAYER_ADJUSTMENT="0.5",
        FASTROUTE_TCL=str(initializer),
        PLATFORM_DIR=str(tmp_path),
        FLOORPLAN_PIN_LAYER_ADJUST="0.37",
    )
    proc = subprocess.run(
        [sys.executable, str(root / "read-routing-env.py")], env=env, check=False
    )
    assert proc.returncode == 0
    assert read(root / "routing-settings.json")["FLOORPLAN_PIN_LAYER_ADJUST"] == "0.37"
    script = (root / "routing-init.tcl").read_text()
    assert "set_routing_layers -clock" in script
    assert "$::env(MIN_CLK_ROUTING_LAYER)-$::env(MAX_ROUTING_LAYER)" in script


def test_registered_native_checkpoint_can_relay_without_final_PPA(
    tmp_path, monkeypatch
):
    from chip_evolve import validation

    jobs, _, original, objective = prepared_source(tmp_path)
    root = tmp_path / "native-parent"
    root.mkdir()
    checkpoint(
        root,
        design_id="gcd",
        odb=Path(original["odb"]),
        producer="native-parent",
        objective=objective,
        pdk=Path(original["pdk"]),
        native_method={
            "physical_stage": "global_route",
            "stage_snapshot_id": "registered-stage",
        },
    )
    requested = []

    class Data:
        def __init__(self, *args, **kwargs):
            pass

        def resolve_scope(self, **kwargs):
            requested.append(kwargs)
            return {
                "scope": {
                    "run_id": "native-parent",
                    "design_id": "gcd",
                    "snapshot_id": "registered-stage",
                }
            }

        def get_metrics(self, **kwargs):
            assert kwargs == {"snapshot_id": "registered-stage"}
            return {"data": {"metrics": [{"name": "TNS", "value": -10.0}]}}

    class Admitted(Exception):
        pass

    monkeypatch.setattr(native_physical, "EdaAiClient", Data)
    monkeypatch.setattr(
        native_physical, "verify_measurement_conditions", lambda *a: None
    )
    monkeypatch.setattr(
        validation,
        "query_facts",
        lambda *a: pytest.fail(
            "A native-stage handoff must not require final routed PPA"
        ),
    )
    monkeypatch.setattr(
        native_physical,
        "bundle",
        lambda *a: (
            None,
            {"output_files": {original["odb"]: digest(Path(original["odb"]))}},
        ),
    )
    monkeypatch.setattr(
        native_physical, "prepare", lambda *a: (_ for _ in ()).throw(Admitted())
    )
    jobs.deployment.value["data_url"] = "http://localhost:1"
    with pytest.raises(Admitted):
        native_physical.repair(
            jobs.deployment,
            "gcd",
            jobs.experiment,
            root / "delivery-checkpoint.json",
            900,
        )
    assert requested[0]["run_id"] == "native-parent"
    assert requested[0]["snapshot_id"] == "registered-stage"


@pytest.mark.parametrize("source", [None, "/legacy-ignored-source.json"])
def test_legacy_orfs_baseline_replay_tag_keeps_its_original_job(
    tmp_path, monkeypatch, source
):
    from chip_evolve import validation
    from chip_evolve.delivery import recover

    d = deployment(tmp_path)
    e = d.experiment("gcd", "legacy-baseline")
    objective = tmp_path / "objective.json"
    request = {
        "design": "gcd",
        "capability": "orfs",
        "operation": "replay",
        "source": source,
        "seconds": 900,
    }
    write(e / "request.json", request)
    write(e / "jobs/orfs/task.json", {"original_baseline_task": True})
    write(e / "result.json", {"design_id": "gcd", "objective": str(objective)})
    calls = []

    def baseline(deploy, design, experiment, seconds, **kwargs):
        calls.append(experiment)
        return {"run_id": "original-baseline"}

    monkeypatch.setattr(physical, "baseline", baseline)
    monkeypatch.setattr(
        native_physical,
        "repair",
        lambda *a, **kw: pytest.fail(
            "A historical baseline must not turn into a new repair"
        ),
    )
    assert recover(d, "gcd", e.name)["run_id"] == "original-baseline"
    child = d.experiment("gcd", "legacy-replay")
    assert (
        validation.replay(d, e / "result.json", child)["run_id"] == "original-baseline"
    )
    assert calls == [e, child]
