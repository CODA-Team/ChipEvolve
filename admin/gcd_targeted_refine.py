"""Local GCD cell experiments using fixed SDK inputs and public EF execution.

Changes are supplied by Codex from path evidence; this driver has no search,
ranking or promotion policy and does not alter specialist algorithms.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from gcd_common_remeasure import measure, reference_liberties
from overnight_finish import finish
from overnight_runtime import command
from run_dplevolve_native import digest, write_json


def connection_signature(netlist: str) -> dict[str, dict[str, str]]:
    """Compare named connections in the flat OpenROAD write_verilog format."""
    cells = re.findall(
        r"^\s*(\w+)\s+(\\[^\s]+|[^\s(]+)\s*\((.*?)\);",
        netlist,
        re.MULTILINE | re.DOTALL,
    )
    return {
        name: {
            pin: re.sub(r"\s+", "", net)
            for pin, net in re.findall(r"\.([^\s(]+)\s*\(([^()]*)\)", pins)
        }
        for master, name, pins in cells
        if master != "module"
    }


def change_commands(changes: list[dict[str, str]]) -> list[str]:
    """Assert each recorded input master before applying the chosen action."""
    lines = []
    for change in changes:
        instance, before, after = (change[k] for k in ("instance", "before", "after"))
        lines.extend(
            [
                f"set target [[ord::get_db_block] findInst {{{instance}}}]",
                f'if {{$target eq "NULL"}} {{error "Missing instance {instance}"}}',
                f'if {{[[$target getMaster] getName] ne "{before}"}} {{error "Input master differs for {instance}"}}',
                f"replace_cell [get_cells {{{instance}}}] {{{after}}}",
            ]
        )
    return lines


def prepare_input(state: Path, data_key: str) -> Path:
    from eda_ai_client import EdaAiClient
    from openroad_platform_client import KernelClient

    runtime = json.loads((state / "runtime.json").read_text())
    data = json.loads((state / (data_key + "-data.json")).read_text())
    folder = state / "optimization-r2" / "inputs" / data_key
    folder.mkdir(parents=True, exist_ok=False)
    sdk = EdaAiClient(data_url=runtime["data_url"], kernel_url=runtime["kernel_url"])
    context = {
        "objects": sdk.get_stage_summary(data["opendb"]["snapshot_id"]),
        "metrics": sdk.get_metrics(snapshot_id=data["orfs"]["snapshot_id"]),
    }
    producer = context["metrics"]["data"]["run_id"]
    write_json(folder / "sdk-context.json", context)
    client = KernelClient(runtime["kernel_url"])
    export_run = data["opendb"]["execution"]["run"]["run_id"]
    artifacts = client.artifacts(export_run)
    selected = {}
    for kind, name in (
        ("raw_design_database", "design.odb"),
        ("raw_constraints", "design.sdc"),
        ("raw_parasitics", "design.spef"),
    ):
        artifact = next(a for a in artifacts if a["kind"] == kind)
        client.materialize_artifact(
            export_run, artifact["artifact_id"], str(folder / name)
        )
        selected[name] = artifact
    write_json(
        folder / "input-receipt.json",
        {
            "parent_run_id": producer,
            "export_run_id": export_run,
            "snapshots": {k: data[k]["snapshot_id"] for k in ("opendb", "orfs")},
            "artifacts": selected,
        },
    )
    return folder


def refine(state: Path, key: str, inputs: Path, changes: list[dict[str, str]]) -> dict:
    runtime = json.loads((state / "runtime.json").read_text())
    folder = state / "optimization-r2" / key
    folder.mkdir(exist_ok=False)
    common_sdc = state / "optimization-r1/common.sdc"
    pdk = state / "agents/eco-smoke-r4/source/asap7"
    script = folder / "refine.tcl"
    script.write_text(
        "\n".join(
            [
                *[f"read_liberty {{{p}}}" for p in reference_liberties(state)],
                f"read_db {{{inputs / 'design.odb'}}}",
                "set_cmd_units -time ns -power W -distance um",
                f"read_sdc {{{common_sdc}}}",
                f"source {{{pdk / 'setRC.tcl'}}}",
                f"read_spef {{{inputs / 'design.spef'}}}",
                "set_propagated_clock [all_clocks]",
                f"write_verilog {{{folder / 'before.v'}}}",
                *change_commands(changes),
                "detailed_placement",
                "check_placement -verbose",
                f"write_db {{{folder / 'changed.odb'}}}",
                f"write_verilog {{{folder / 'changed.v'}}}",
                "exit",
            ]
        )
        + "\n"
    )
    receipt = json.loads((inputs / "input-receipt.json").read_text())
    identity = {
        "input_receipt": receipt,
        "changes": changes,
        "common_sdc_sha256": digest(common_sdc),
        "script_sha256": digest(script),
        "input_sha256": {p.name: digest(p) for p in inputs.glob("design.*")},
        "liberty_sha256": {str(p): digest(p) for p in reference_liberties(state)},
        "toolchain": runtime["toolchain"],
    }
    write_json(folder / "input-receipt.json", identity)
    execution = command(
        state,
        key + "-change",
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
            "-exit",
            str(script),
        ],
        memory_gib=24,
        cpu=8,
        capture=[str(script)],
    )
    if execution["run"]["status"] != "succeeded":
        raise RuntimeError("Cell experiment failed: " + key)
    before = connection_signature((folder / "before.v").read_text())
    after = connection_signature((folder / "changed.v").read_text())
    if not before or before != after:
        raise ValueError("Named logical connections changed")
    routed = finish(
        state,
        key + "-qualified",
        folder / "changed.odb",
        common_sdc,
        pdk,
        execution["run"]["run_id"],
    )
    physical = state / "handoffs" / (key + "-qualified")
    final = connection_signature((physical / "final.v").read_text())
    if before != final:
        raise ValueError("Named logical connections changed during qualification")
    result = measure(
        state,
        key + "-common",
        physical / "final.odb",
        physical / "final.spef",
        common_sdc,
        routed["run"]["run_id"],
    )
    result["connection_check"] = {
        "named_connections_equal": True,
        "instance_count": len(before),
        "formal_equivalence_proven": False,
    }
    result["changes"] = changes
    write_json(folder / "result.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--key", required=True)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--changes", type=Path, required=True)
    args = parser.parse_args()
    result = refine(
        args.state.resolve(),
        args.key,
        args.inputs.resolve(),
        json.loads(args.changes.read_text()),
    )
    print(json.dumps({"run_id": result["run_id"], "metrics": result["metrics"]}))
