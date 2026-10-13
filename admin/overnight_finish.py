"""Complete a real Agent checkpoint with common routing, RCX and explicit PPA units."""

from __future__ import annotations

import argparse
import json
import re
import zipfile
from pathlib import Path

from overnight_runtime import command
from run_dplevolve_native import digest, write_json


def finish(state: Path, key: str, odb: Path, sdc: Path, pdk: Path, parent_run: str):
    runtime = json.loads((state / "runtime.json").read_text())
    output = state / "handoffs" / key
    output.mkdir(parents=True, exist_ok=False)
    libs = [
        pdk / "lib/NLDM" / ("asap7sc7p5t_" + group + "_" + vt + "_FF_nldm_" + version)
        for vt in ("RVT", "LVT", "SLVT")
        for group, version in (
            ("AO", "211120.lib.gz"),
            ("INVBUF", "220122.lib.gz"),
            ("OA", "211120.lib.gz"),
            ("SIMPLE", "211120.lib.gz"),
            ("SEQ", "220123.lib"),
        )
    ]
    if not all(path.is_file() for path in libs):
        raise FileNotFoundError("Matching real FF libraries are required")
    script = output / "finish.tcl"
    script.write_text(
        "\n".join(
            [
                *[f"read_liberty {{{p}}}" for p in libs],
                f"read_db {{{odb}}}",
                f"read_sdc {{{sdc}}}",
                f"source {{{pdk / 'setRC.tcl'}}}",
                "remove_fillers",
                "foreach net [[ord::get_db_block] getNets] { if {[$net getSigType] ni {POWER GROUND}} { set wire [$net getWire]; if {$wire ne {NULL}} { odb::dbWire_destroy $wire } } }",
                "set_routing_layers -signal M2-M7 -clock M2-M7",
                "global_route -congestion_iterations 50",
                f"detailed_route -output_drc {{{output / 'drc.rpt'}}}",
                "define_process_corner -ext_model_index 0 X",
                f"extract_parasitics -ext_model_file {{{pdk / 'rcx_patterns.rules'}}}",
                f"write_spef {{{output / 'final.spef'}}}",
                f"read_spef {{{output / 'final.spef'}}}",
                "set_propagated_clock [all_clocks]",
                "set_cmd_units -time ns -power W -distance um",
                "check_placement -verbose",
                "report_units",
                "report_tns -digits 6",
                "report_wns -digits 6",
                "report_power -digits 8",
                "report_design_area",
                "utl::metric_float finish__timing__tns [total_negative_slack -max]",
                "utl::metric_float finish__timing__setup__ws [worst_slack -max]",
                "utl::metric_float finish__design__instance__area [expr {[rsz::design_area] * 1e12}]",
                f"write_db {{{output / 'final.odb'}}}",
                f"write_def {{{output / 'final.def'}}}",
                f"write_verilog {{{output / 'final.v'}}}",
                f"write_sdc {{{output / 'final.sdc'}}}",
                "exit",
            ]
        )
        + "\n"
    )
    write_json(
        output / "input-receipt.json",
        {
            "parent_run_id": parent_run,
            "input_odb": str(odb),
            "input_odb_sha256": digest(odb),
            "input_sdc": str(sdc),
            "input_sdc_sha256": digest(sdc),
            "library_corner": "FF",
            "library_sha256": {str(p): digest(p) for p in libs},
            "metrics_units": {"timing": "ns", "power": "W", "area": "um^2"},
            "routing": "full default detailed_route, not the native ECO one-iteration route",
        },
    )
    result = command(
        state,
        key + "-finish",
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
            "8",
            "-metrics",
            str(output / "native-metrics.json"),
            "-exit",
            str(script),
        ],
        timeout=1800,
        memory_gib=24,
        cpu=8,
    )
    if result["run"]["status"] != "succeeded":
        raise RuntimeError("Full physical qualification failed: " + key)
    archive_path = next((state / "tasks" / (key + "-finish")).glob("*.zip"))
    with zipfile.ZipFile(archive_path) as archive:
        log = archive.read("stdout.log").decode()
    totals = re.findall(
        r"^Total\s+([\deE.+-]+)\s+([\deE.+-]+)\s+([\deE.+-]+)\s+([\deE.+-]+)",
        log,
        re.MULTILINE,
    )
    if not totals:
        raise ValueError("The authoritative report_power Total row is missing")
    power = [float(value) for value in totals[-1]]
    metrics = json.loads((output / "native-metrics.json").read_text())
    metrics.update(
        {
            "finish__timing__setup__tns": metrics["finish__timing__tns"],
            "finish__power__total": power[3],
            "finish__power__internal": power[0],
            "finish__power__switching": power[1],
            "finish__power__leakage": power[2],
            "run__flow__platform__time_units": "1ns",
            "run__flow__platform__distance_units": "1um",
            "run__flow__platform__power_units": "1W",
        }
    )
    write_json(
        output / "metrics.json",
        {
            "metrics": metrics,
            "metric_context": {
                "corner": "FF",
                "analysis": "post_route",
                "authoritative_source": "common OpenROAD full DRT+RCX",
                "evaluation_conditions": {
                    "sdc_sha256": digest(sdc),
                    "image_sha256": runtime["toolchain"]["image_sha256"],
                },
            },
        },
    )
    write_json(
        output / "qualification.json",
        {
            "run_id": result["run"]["run_id"],
            "parent_run_id": parent_run,
            "drc_errors": metrics["route__drc_errors"],
            "placement_violations": metrics["design__violations"],
            "tns_ns": metrics["finish__timing__setup__tns"],
            "worst_slack_ns": metrics["finish__timing__setup__ws"],
            "power_w": power[3],
            "cell_area_um2": metrics["finish__design__instance__area"],
            "metric_digest": digest(output / "metrics.json"),
            "full_routing_complete": True,
        },
    )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--key", required=True)
    parser.add_argument("--odb", type=Path, required=True)
    parser.add_argument("--sdc", type=Path, required=True)
    parser.add_argument("--pdk", type=Path, required=True)
    parser.add_argument("--parent-run", required=True)
    args = parser.parse_args()
    result = finish(
        args.state.resolve(),
        args.key,
        args.odb.resolve(),
        args.sdc.resolve(),
        args.pdk.resolve(),
        args.parent_run,
    )
    print(result["run"]["run_id"], result["run"]["status"])
