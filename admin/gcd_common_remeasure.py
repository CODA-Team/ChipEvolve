"""Measure frozen routed GCD candidates under one explicit constraint contract.

This is a local experiment driver, not a promotion policy. Public EF receipts
identify inputs and execute OpenROAD; Codex judges the resulting tradeoffs.
"""

from __future__ import annotations

import argparse
import json
import re
import zipfile
from pathlib import Path

from overnight_finish import sdc_export_commands
from overnight_runtime import command
from run_dplevolve_native import digest, write_json


def reference_sdc(source: Path, destination: Path) -> None:
    """The historical reference was serialized in ns without a unit header."""
    text = source.read_text()
    if not re.search(r"create_clock[^\n]*-period 0\.3100\b", text):
        raise ValueError("Expected the frozen 310 ps reference, serialized in ns")
    destination.write_text("set_cmd_units -time ns\n" + text)


def power_total(log: str) -> float:
    rows = re.findall(
        r"^Total\s+([\deE.+-]+)\s+([\deE.+-]+)\s+([\deE.+-]+)\s+([\deE.+-]+)",
        log,
        re.MULTILINE,
    )
    if len(rows) != 1:
        raise ValueError("Require one authoritative report_power Total row")
    return float(rows[0][3])


def reference_liberties(state: Path) -> list[Path]:
    """Use the actual common reference libraries, not a same-named Flow copy."""
    receipt = json.loads(
        (state / "handoffs/original-qualified/input-receipt.json").read_text()
    )
    libraries = receipt["library_sha256"]
    for name, expected in libraries.items():
        if digest(Path(name)) != expected:
            raise ValueError("Frozen reference liberty changed: " + name)
    return [Path(name) for name in libraries]


def materialize(state: Path, iteration: int, slot: int) -> dict:
    from openroad_platform_client import KernelClient

    runtime = json.loads((state / "runtime.json").read_text())
    receipt = state / "agents/flow-r5/platform-state" / f"iteration-{iteration}"
    native = json.loads((receipt / f"slot-{slot}-eval_final.json").read_text())
    producer = native["parent_run_id"]
    folder = state / "optimization-r1" / f"flow-i{iteration}-s{slot}"
    folder.mkdir(exist_ok=False)
    client = KernelClient(runtime["kernel_url"])
    artifact = next(
        a for a in client.artifacts(producer) if a["kind"] == "flow_archive"
    )
    archive = folder / "flow.zip"
    client.materialize_artifact(producer, artifact["artifact_id"], str(archive))
    # Extract only the explicitly named members, never arbitrary archive paths.
    names = ["6_final.odb", "6_final.sdc", "6_final.spef", "6_final.v"]
    with zipfile.ZipFile(archive) as bundle:
        for name in names:
            (folder / name).write_bytes(bundle.read("flow/results/" + name))
        floorplan = json.loads(bundle.read("flow/logs/2_1_floorplan.json"))
        final = json.loads(bundle.read("flow/logs/6_report.json"))
        route = json.loads(bundle.read("flow/logs/5_2_route.json"))
    config = state / "agents/flow-r5/source/flow/backup_dir/asap7/gcd"
    config = config / f"result_dump_{iteration}" / f"config_{slot}.mk"
    (folder / "config.mk").write_bytes(config.read_bytes())
    result = {
        "iteration": iteration,
        "slot": slot,
        "parent_run_id": producer,
        "flow_archive": artifact,
        "folder": str(folder),
        "config_sha256": digest(config),
        "original_floorplan_metrics": floorplan,
        "original_final_metrics": final,
        "original_route_metrics": route,
    }
    write_json(folder / "source-receipt.json", result)
    return result


def measure(
    state: Path,
    key: str,
    odb: Path,
    spef: Path,
    sdc: Path,
    parent: str,
    objective: Path | None = None,
) -> dict:
    runtime = json.loads((state / "runtime.json").read_text())
    output = state / "handoffs" / key
    output.mkdir(parents=True, exist_ok=False)
    shared = None
    if objective is not None:
        from eda_toolkits.objectives import (
            condition_id,
            load_objective,
            verify_conditions,
        )

        objective = objective.resolve()
        shared = load_objective(objective)
        verify_conditions(shared, sdc=sdc)
        if shared["conditions"]["toolchain"] != runtime["toolchain"]:
            raise ValueError("Measurement toolchain differs from the shared objective")
        libs = [Path(row["path"]) for row in shared["conditions"]["libraries"]]
    else:
        libs = reference_liberties(state)
    script = output / "measure.tcl"
    script.write_text(
        "\n".join(
            [
                *[f"read_liberty {{{p}}}" for p in libs],
                f"read_db {{{odb}}}",
                "set_cmd_units -time ns -power W -distance um",
                f"read_sdc {{{sdc}}}",
                f"read_spef {{{spef}}}",
                "set_propagated_clock [all_clocks]",
                "check_placement -verbose",
                "report_units",
                "report_clock_properties [all_clocks]",
                "report_tns -digits 8",
                "report_wns -digits 8",
                "report_power -digits 10",
                "report_check_types -max_slew -max_capacitance -max_fanout -violators",
                "utl::metric_float finish__timing__setup__tns [total_negative_slack -max]",
                "utl::metric_float finish__timing__setup__ws [worst_slack -max]",
                "utl::metric_float finish__timing__hold__tns [total_negative_slack -min]",
                "utl::metric_float finish__timing__hold__ws [worst_slack -min]",
                "utl::metric_integer finish__timing__drv__max_slew [sta::max_slew_violation_count]",
                "utl::metric_integer finish__timing__drv__max_cap [sta::max_capacitance_violation_count]",
                "utl::metric_float finish__design__instance__area [expr {[rsz::design_area] * 1e12}]",
                "set block [ord::get_db_block]",
                "set scale [$block getDbUnitsPerMicron]",
                "foreach {kind rect} [list core [$block getCoreArea] die [$block getDieArea]] {",
                "  utl::metric_float finish__design__${kind}__area [expr {[$rect dx]*double([$rect dy])/$scale/$scale}]",
                "}",
                f"write_db {{{output / 'final.odb'}}}",
                f"write_verilog {{{output / 'final.v'}}}",
                *sdc_export_commands(output / "final.sdc"),
                "exit",
            ]
        )
        + "\n"
    )
    identity = {
        "parent_run_id": parent,
        "input_sha256": {str(p): digest(p) for p in [odb, spef, sdc]},
        "liberty_sha256": {str(p): digest(p) for p in libs},
        "toolchain": runtime["toolchain"],
        "conditions": {
            "corner": "FF",
            "sdc_sha256": digest(sdc),
            "propagated_clock": True,
            "parasitics": "unchanged input routed SPEF",
            "units": {"time": "ns", "power": "W", "area": "um^2"},
        },
    }
    write_json(output / "input-receipt.json", identity)
    if shared is not None:
        identity.update(
            objective_id=shared["objective_id"], condition_id=condition_id(shared)
        )
        identity["conditions"].update(
            objective_id=identity["objective_id"],
            condition_id=identity["condition_id"],
            clock_period_ns=shared["conditions"]["clock_period_ns"],
            library_sha256=sorted(identity["liberty_sha256"].values()),
            toolchain=runtime["toolchain"],
        )
        write_json(output / "input-receipt.json", identity)
    execution = command(
        state,
        key,
        [
            "apptainer",
            "exec",
            "--cleanenv",
            "--no-home",
            "--bind",
            str(state) + ":" + str(state),
            runtime["image"],
            "/OpenROAD-flow-scripts/tools/install/OpenROAD/bin/openroad",
            "-threads",
            "2",
            "-metrics",
            str(output / "native-metrics.json"),
            "-exit",
            str(script),
        ],
        timeout=300,
        memory_gib=8,
        cpu=2,
        objective=objective,
        capture=[
            str(odb),
            str(spef),
            str(sdc),
            str(script),
            *([str(objective)] if objective else []),
        ],
    )
    if execution["run"]["status"] != "succeeded":
        raise RuntimeError("Common measurement failed: " + key)
    with zipfile.ZipFile(next((state / "tasks" / key).glob("*.zip"))) as bundle:
        log = bundle.read("stdout.log").decode()
    metrics = json.loads((output / "native-metrics.json").read_text())
    metrics.update(
        {
            "finish__power__total": power_total(log),
            "run__flow__platform__time_units": "1ns",
            "run__flow__platform__power_units": "1W",
            "run__flow__platform__distance_units": "1um",
        }
    )
    write_json(
        output / "metrics.json",
        {
            "metrics": metrics,
            "metric_context": {
                "corner": "FF",
                "analysis": "post_route",
                "evaluation_conditions": identity["conditions"],
                **(
                    {
                        "objective_id": identity["objective_id"],
                        "condition_id": identity["condition_id"],
                    }
                    if shared
                    else {}
                ),
                "authoritative_source": "common OpenROAD read-only routed checkpoint remeasurement",
            },
        },
    )
    result = {"run_id": execution["run"]["run_id"], **identity, "metrics": metrics}
    write_json(output / "measurement.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--key", required=True)
    parser.add_argument("--odb", type=Path, required=True)
    parser.add_argument("--spef", type=Path, required=True)
    parser.add_argument("--sdc", type=Path, required=True)
    parser.add_argument("--parent-run", required=True)
    parser.add_argument("--objective", type=Path)
    args = parser.parse_args()
    row = measure(
        args.state.resolve(),
        args.key,
        args.odb.resolve(),
        args.spef.resolve(),
        args.sdc.resolve(),
        args.parent_run,
        objective=args.objective,
    )
    print(json.dumps({"run_id": row["run_id"], "metrics": row["metrics"]}))
