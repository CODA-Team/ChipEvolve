"""Common facts expose real fanout counts and preserve dispatched legacy inputs."""

import subprocess
from types import SimpleNamespace
from typing import cast

import pytest

from chip_evolve.config import Deployment, read, write
from chip_evolve.jobs import Jobs, digest
from chip_evolve.physical import measure


def run_measurement(tmp_path, count):
    lib, sdc, odb, spef = [
        tmp_path / name
        for name in ("FF.lib", "original.sdc", "design.odb", "design.spef")
    ]
    for path in (lib, sdc, odb, spef):
        path.write_text("fixture " + path.name)
    config = tmp_path / "config.json"
    write(
        config,
        {
            "schema_version": "chip-evolve.local.v1",
            "state_root": str(tmp_path),
            "toolchain": {"identity": "same"},
            "runtime": {
                "executable": "apptainer",
                "image": "fixed.sif",
                "bind_roots": [],
            },
            "tools": {"openroad": "openroad"},
            "designs": {
                "example": {
                    "corner": "FF",
                    "clock_period_ns": 0.8,
                    "libraries": [{"path": str(lib), "sha256": digest(lib)}],
                }
            },
        },
    )
    deployment = Deployment(config)
    native = tmp_path / "common/native-metrics.json"

    def command(key, argv, **kwargs):
        if not native.exists():
            # Exercise the generated fanout Tcl in a small stateful native boundary:
            # the count API requires the report's initialization, as pinned STA does.
            text = (tmp_path / "common/measure.tcl").read_text()
            snippet = "\n".join(
                line for line in text.splitlines() if "max_fanout" in line
            )
            interpreter = f"""set initialized 0
proc report_check_types {{args}} {{set ::initialized 1}}
namespace eval sta {{
  proc max_fanout_violation_count {{}} {{
    if {{!$::initialized}} {{error "fanout checker not initialized"}}
    return {count}
  }}
}}
namespace eval utl {{proc metric_integer {{name value}} {{puts "$name $value"}}}}
"""
            process = subprocess.run(
                ["tclsh"],
                input=interpreter + snippet,
                text=True,
                capture_output=True,
                check=True,
            )
            assert not process.stderr
            metrics = {
                "finish__timing__setup__tns": 0,
                "finish__timing__setup__ws": 0.1,
                "finish__timing__hold__tns": 0,
                "finish__design__instance__area": 42,
                "finish__design__core__area": 50,
                "finish__design__die__area": 60,
            }
            for line in process.stdout.splitlines():
                name, value = line.split()
                metrics[name] = int(value)
            write(native, metrics)
        return {"run": {"run_id": "same-measurement"}}

    jobs = cast(
        Jobs,
        SimpleNamespace(
            deployment=deployment,
            design_id="example",
            experiment=tmp_path,
            command=command,
            log=lambda record, path: "Total 0.001 0.002 0.000003 0.003003\n",
        ),
    )
    return (
        jobs,
        (odb, spef, sdc),
        lambda: measure(jobs, "common", odb, spef, sdc, "original-physical"),
    )


@pytest.mark.parametrize("count", [0, 7])
def test_same_common_measurement_exposes_actual_zero_or_nonzero_fanout(tmp_path, count):
    _, inputs, run = run_measurement(tmp_path, count)
    hashes = {p: digest(p) for p in inputs}
    actual = run()
    assert actual["metrics"]["finish__timing__drv__max_fanout"] == count
    assert actual["metrics"]["finish__power__total"] == 0.003003
    assert all(digest(p) == sha for p, sha in hashes.items())
    assert "objective" not in actual


def test_legacy_dispatched_measurement_keeps_exact_script_and_unknown_fanout(tmp_path):
    _, _, run = run_measurement(tmp_path, 0)
    run()
    script = tmp_path / "common/measure.tcl"
    legacy = (
        "\n".join(
            line for line in script.read_text().splitlines() if "max_fanout" not in line
        )
        + "\n"
    )
    script.write_text(legacy)
    original = digest(script)
    write(tmp_path / "jobs/common/task.json", {"task_id": "already-dispatched"})
    native = tmp_path / "common/native-metrics.json"
    old = read(native)
    old.pop("finish__timing__drv__max_fanout", None)
    write(native, old)
    actual = run()
    assert digest(script) == original
    assert "finish__timing__drv__max_fanout" not in actual["metrics"]
    assert actual["metrics"]["finish__power__total"] == 0.003003
