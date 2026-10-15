"""Local business boundaries: producer identity, inputs and retained incumbent."""

import subprocess
import zipfile
from unittest.mock import patch

import pytest

from chip_evolve.clock import flow_sdc
from chip_evolve.config import Deployment, write
from chip_evolve.jobs import Jobs, digest
from chip_evolve.native import latest_producer
from chip_evolve.professional import flatten_archive, recover_config
from chip_evolve.selection import select


def deployment(root):
    path = root / "local.json"
    write(
        path,
        {
            "schema_version": "chip-evolve.local.v1",
            "state_root": str(root),
            "kernel_url": "http://localhost:1",
            "designs": {"gcd": {}, "aes": {}},
        },
    )
    return Deployment(path)


def test_flow_clock_binding_preserves_delays_and_matching_virtual_clocks():
    sdc = "set_cmd_units -time ps\ncreate_clock -name core -period 310 [get_ports clk]\ncreate_clock -name virtual -period 310\nset_input_delay 62 -clock virtual [get_ports d]\n"
    actual = flow_sdc(sdc, 0.31)
    assert actual.count("-period $clk_period") == 2
    assert "set_input_delay 62 -clock virtual [get_ports d]" in actual
    assert actual.startswith(
        "set clk_period 310.0\nset clk_port_name clk\nset_cmd_units -time ps"
    )
    with pytest.raises(ValueError, match="one declared period"):
        flow_sdc(sdc.replace("virtual -period 310", "virtual -period 400"), 0.31)


def test_business_help_needs_no_tool_environment():
    process = subprocess.run(
        ["/usr/bin/python3.12", "chip-evolve.py", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert process.returncode == 0
    assert "diagnose" in process.stdout


@pytest.mark.parametrize(
    "arguments",
    [
        ["--capability", "goal", "--operation", "framework"],
        ["--capability", "flow", "--operation", "framework"],
        ["--capability", "goal", "--candidates", "1"],
        ["--capability", "dpl", "--code-source", "/saved/source"],
        ["--capability", "dpl", "--flow-recipe", "source"],
        [
            "--capability",
            "eco",
            "--operation",
            "replay",
            "--code-source",
            "/saved/source",
        ],
    ],
)
def test_invalid_professional_mode_fails_before_starting_an_experiment(
    tmp_path, arguments
):
    from chip_evolve.cli import main

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
                *arguments,
            ],
        ),
        pytest.raises(SystemExit) as stopped,
    ):
        main()
    assert stopped.value.code == 2
    assert not (tmp_path / "experiments").exists()


def test_export_declares_actual_analysis_parent_and_design_identity(tmp_path):
    class Client:
        def submit(self, task, **kwargs):
            self.task = task
            return {"run": {"run_id": "export-producer"}}

        def run(self, run_id):
            return {"run_id": run_id, "status": "succeeded"}

        def artifacts(self, run_id):
            return []

        def resources(self, run_id):
            return {}

    client = Client()
    with patch("chip_evolve.jobs.KernelClient", return_value=client):
        d = deployment(tmp_path)
        for design in ("gcd", "aes"):
            jobs = Jobs(d, design, tmp_path / design / "same-key")
            jobs.submit(
                "publish",
                {"adapter": "orfs"},
                [],
                parent="physical-source",
                analysis_parent="physical-source",
            )
            assert client.task["design_id"] == design
            assert client.task["labels"]["run_type"] == "analysis"
            assert client.task["labels"]["analysis_of_run_id"] == "physical-source"
            assert client.task["experiment_id"] == design + "-same-key"


def test_archive_supports_stock_and_resumed_designs_but_rejects_mixed_design(tmp_path):
    for label, names in [
        ("stock", ["flow/results/asap7/aes/base/3_4_place_resized.odb"]),
        ("resume", ["flow/results/3_4_place_resized.odb"]),
    ]:
        original = tmp_path / (label + ".zip")
        with zipfile.ZipFile(original, "w") as z:
            z.writestr(names[0], b"actual checkpoint")
        flat = tmp_path / (label + "-flat.zip")
        flatten_archive(original, flat)
        with zipfile.ZipFile(flat) as z:
            assert z.read("flow/results/3_4_place_resized.odb") == b"actual checkpoint"
    mixed = tmp_path / "mixed.zip"
    with zipfile.ZipFile(mixed, "w") as z:
        for design in ("gcd", "aes"):
            z.writestr(
                f"flow/results/asap7/{design}/base/3_4_place_resized.odb", design
            )
    with pytest.raises(ValueError, match="mixed archive"):
        flatten_archive(mixed, tmp_path / "invalid.zip")


def test_checkpoint_producer_uses_content_not_filename(tmp_path):
    checkpoint = tmp_path / "design_checkpoint.odb"
    checkpoint.write_bytes(b"selected physical state")
    operations = tmp_path / "operations"
    for key, sha in [("old", "wrong"), ("actual", digest(checkpoint))]:
        folder = operations / key
        write(
            folder / "leaf.json",
            {
                "request": {"operation": "physical"},
                "output_files": {"/original/post_route.odb": sha},
            },
        )
        write(folder / "execution.json", {"run": {"run_id": key}})
    assert latest_producer(operations, checkpoint, "input-source") == "actual"
    checkpoint.write_bytes(b"unmanaged state")
    with pytest.raises(ValueError, match="no EF producer"):
        latest_producer(operations, checkpoint, "input-source")


def test_flow_configuration_is_recovered_after_the_next_round_replaces_it(tmp_path):
    flow = tmp_path / "flow"
    flow.mkdir()
    (flow / "config_2.mk").write_text("new round configuration")
    checkpoint = tmp_path / "state/checkpoints/iteration-1-phase-0/native-state.zip"
    checkpoint.parent.mkdir(parents=True)
    actual = b"original evaluated configuration"
    with zipfile.ZipFile(checkpoint, "w") as bundle:
        bundle.writestr("designs/asap7/gcd/config_2.mk", actual)
    import hashlib

    row = {
        "candidate_slot": 2,
        "input_hashes": {"config": hashlib.sha256(actual).hexdigest()},
    }
    target = tmp_path / "recovered.mk"
    recover_config(flow, tmp_path / "state", row, target)
    assert target.read_bytes() == actual
    row["input_hashes"]["config"] = "unrecorded"
    with pytest.raises(ValueError, match="actual native candidate"):
        recover_config(flow, tmp_path / "state", row, target)


def test_selection_retains_feasible_incumbent_and_rejects_mismatched_conditions(
    tmp_path,
):
    d = deployment(tmp_path)
    limits = {
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
    }
    objective = tmp_path / "objective.json"
    write(objective, {"constraints": limits})
    frame = {
        "design_id": "gcd",
        "run_id": "baseline",
        "objective": str(objective),
        "objective_id": "goal",
        "condition_id": "same",
        "route_drc": 0,
        "metrics": {
            "finish__timing__setup__tns": 0,
            "finish__timing__hold__tns": 0,
            "finish__timing__drv__max_slew": 0,
            "finish__timing__drv__max_cap": 0,
            "design__violations": 0,
            "finish__power__total": 1,
            "finish__design__instance__area": 10,
            "finish__design__core__area": 30,
            "finish__design__die__area": 40,
        },
    }
    baseline = tmp_path / "baseline.json"
    write(baseline, frame)
    assert select(d, baseline, "Codex accepts legal reference")["adopted"]
    frame["run_id"] = "worse"
    frame["metrics"]["finish__power__total"] = 1.1
    frame["metrics"]["finish__design__instance__area"] = 11
    candidate = tmp_path / "candidate.json"
    write(candidate, frame)
    assert not select(d, candidate, "Check dominated alternative")["adopted"]
    frame["condition_id"] = "other"
    write(candidate, frame)
    with pytest.raises(ValueError, match="different shared conditions"):
        select(d, candidate, "Different clock cannot establish a gain")
