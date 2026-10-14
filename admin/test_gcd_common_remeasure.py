"""Keep comparison units and authoritative power parsing unambiguous."""

import hashlib
import json
import subprocess
import zipfile

import pytest
from gcd_common_remeasure import (
    measure,
    power_total,
    reference_liberties,
    reference_sdc,
)


def test_reference_sdc_uses_explicit_ns_with_ps_reader(tmp_path):
    source = tmp_path / "original.sdc"
    source.write_text("create_clock -name core_clock -period 0.3100 [get_ports clk]\n")
    destination = tmp_path / "fixed.sdc"
    reference_sdc(source, destination)
    script = """
set unit ps
proc set_cmd_units {flag value} { global unit; set unit $value }
proc get_ports {name} { return $name }
proc create_clock {args} {
    global unit
    set period [lindex $args [expr {[lsearch $args -period]+1}]]
    puts [expr {$unit eq "ns" ? $period : $period / 1000.0}]
}
"""
    result = subprocess.run(
        ["tclsh"],
        input=script + f"source {{{destination}}}\n",
        text=True,
        capture_output=True,
        check=True,
    )
    assert not result.stderr
    assert float(result.stdout.strip()) == pytest.approx(0.310)


def test_power_uses_total_not_component_or_percentage():
    assert power_total("Total 1e-3 2e-3 3e-6 0.003003 100%\n") == pytest.approx(
        0.003003
    )


@pytest.mark.parametrize("log", ["", "Total 1 2 3 6\nTotal 1 2 3 6\n"])
def test_missing_or_multiple_power_reports_are_not_a_measurement(log):
    with pytest.raises(ValueError):
        power_total(log)


def test_reference_library_identity_rejects_same_filename_different_content(tmp_path):
    lib = tmp_path / "same_name_FF.lib"
    lib.write_text("original reference")
    folder = tmp_path / "handoffs/original-qualified"
    folder.mkdir(parents=True)
    receipt = {
        "library_sha256": {str(lib): hashlib.sha256(lib.read_bytes()).hexdigest()}
    }
    (folder / "input-receipt.json").write_text(json.dumps(receipt))
    assert reference_liberties(tmp_path) == [lib]
    lib.write_text("another nominal corner")
    with pytest.raises(ValueError, match="reference liberty changed"):
        reference_liberties(tmp_path)


def test_final_measurement_rejects_changed_sdc_before_submitting_eda(
    tmp_path, monkeypatch
):
    from eda_toolkits.objectives import SCHEMA, objective_id

    lib, sdc, other = (
        tmp_path / "FF.lib",
        tmp_path / "common.sdc",
        tmp_path / "native.sdc",
    )
    lib.write_text("common liberty")
    sdc.write_text("create_clock -period 0.31 clk")
    other.write_text("create_clock -period 0.45 clk")
    value = {
        "schema_version": SCHEMA,
        "design_id": "example",
        "reference_run_id": "reference",
        "conditions": {
            "libraries": [
                {
                    "path": str(lib),
                    "sha256": hashlib.sha256(lib.read_bytes()).hexdigest(),
                }
            ],
            "sdc": {
                "path": str(sdc),
                "sha256": hashlib.sha256(sdc.read_bytes()).hexdigest(),
            },
        },
        "constraints": {},
    }
    value["objective_id"] = objective_id(value)
    objective = tmp_path / "objective.json"
    objective.write_text(json.dumps(value))
    (tmp_path / "runtime.json").write_text("{}")

    def forbidden(*args, **kwargs):
        raise AssertionError("mismatched conditions may not start an EDA measurement")

    monkeypatch.setattr("gcd_common_remeasure.command", forbidden)
    with pytest.raises(ValueError, match="SDC differs"):
        measure(
            tmp_path,
            "bad-measurement",
            tmp_path / "design.odb",
            tmp_path / "design.spef",
            other,
            "producer",
            objective=objective,
        )


def test_relative_objective_survives_ef_working_directory_and_data_projection(
    tmp_path, monkeypatch
):
    from eda_toolkits.objectives import SCHEMA, file_sha256, objective_id

    monkeypatch.chdir(tmp_path)
    toolchain = {"image_sha256": "frozen"}
    (tmp_path / "runtime.json").write_text(
        json.dumps({"toolchain": toolchain, "image": "image.sif"})
    )
    lib, sdc, odb, spef = [
        tmp_path / name
        for name in ("FF.lib", "common.sdc", "design.odb", "design.spef")
    ]
    for path in (lib, sdc, odb, spef):
        path.write_text("test input")
    value = {
        "schema_version": SCHEMA,
        "design_id": "example",
        "reference_run_id": "reference",
        "conditions": {
            "toolchain": toolchain,
            "clock_period_ns": 0.31,
            "libraries": [{"path": str(lib), "sha256": file_sha256(lib)}],
            "sdc": {"path": str(sdc), "sha256": file_sha256(sdc)},
        },
        "constraints": {},
    }
    value["objective_id"] = objective_id(value)
    objective = tmp_path / "objective.json"
    objective.write_text(json.dumps(value))

    def execution(state, key, argv, **kwargs):
        assert kwargs["capture"][-1] == str(objective)
        assert kwargs["objective"] == objective
        (tmp_path / "handoffs/check/native-metrics.json").write_text("{}")
        task = tmp_path / "tasks/check"
        task.mkdir(parents=True)
        with zipfile.ZipFile(task / "output.zip", "w") as archive:
            archive.writestr("stdout.log", "Total 0.001 0.002 0 0.003\n")
        return {"run": {"run_id": "measured", "status": "succeeded"}}

    monkeypatch.setattr("gcd_common_remeasure.command", execution)
    record = measure(
        tmp_path,
        "check",
        odb,
        spef,
        sdc,
        "physical",
        objective=objective.relative_to(tmp_path),
    )
    metadata = json.loads((tmp_path / "handoffs/check/metrics.json").read_text())
    conditions = metadata["metric_context"]["evaluation_conditions"]
    assert conditions["objective_id"] == value["objective_id"]
    assert conditions["condition_id"] == record["condition_id"]
    assert conditions["library_sha256"] == [file_sha256(lib)]
