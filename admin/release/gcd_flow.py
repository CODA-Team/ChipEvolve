"""Bind the released Flow controller and GCD recipe to the stack's ORFS image."""

import hashlib
import subprocess
from pathlib import Path

GCD_OVERRIDES = """\
export SYNTH_USE_SYN = 0
export SYNTH_HIERARCHICAL = 0
export CELL_PAD_IN_SITES_GLOBAL_PLACEMENT = 0
export CELL_PAD_IN_SITES_DETAIL_PLACEMENT = 0
export ENABLE_DPO = 1
export PLACE_DENSITY_LB_ADDON = 0.20
export TNS_END_PERCENT = 100
export CTS_CLUSTER_SIZE = 25
export CTS_CLUSTER_DIAMETER = 100
export FLOORPLAN_PIN_LAYER_ADJUST = 0.25
export FLOORPLAN_ABOVE_LAYER_ADJUST = 0.25
export PIN_LAYER_ADJUST = 0.25
export ABOVE_LAYER_ADJUST = 0.25
export FASTROUTE_TCL = /work/inputs/gcd-floorplan-route.tcl
export PRE_GLOBAL_ROUTE_TCL = /work/inputs/gcd-global-route.tcl
export ABC_CLOCK_PERIOD_IN_PS = $(shell awk '$$1 == "set" && $$2 == "clk_period" {print $$3 * 1000; exit}' "$(SDC_FILE)")
"""


def prepare_gcd_flow(root, state, inputs, runtime, value):
    source = root / "agent/flow-agent"
    python = source / ".venv/bin/python"
    if not python.is_file():
        raise FileNotFoundError(
            f"Install the Flow environment with bootstrap.py: {python}"
        )
    for phase, prefix in [("floorplan", "FLOORPLAN_"), ("global", "")]:
        (inputs / f"gcd-{phase}-route.tcl").write_text(
            f"set_global_routing_layer_adjustment metal2-metal3 $::env({prefix}PIN_LAYER_ADJUST)\n"
            f"set_global_routing_layer_adjustment metal4-$::env(MAX_ROUTING_LAYER) $::env({prefix}ABOVE_LAYER_ADJUST)\n"
            "set_routing_layers -signal $::env(MIN_ROUTING_LAYER)-$::env(MAX_ROUTING_LAYER)\n"
            "set ::env(PL_ROUTING_ADJUSTMENT) 1.0\n"
        )

    tools = value["tools"]
    tools["yosys"] = "/OpenROAD-flow-scripts/tools/install/yosys/bin/yosys"
    image = value["runtime"]["image"]
    paths = {tool: tools[tool] for tool in ("openroad", "yosys")}
    hashes = subprocess.check_output(
        [
            runtime,
            "exec",
            "--cleanenv",
            "--no-home",
            image,
            "sha256sum",
            *paths.values(),
        ],
        text=True,
    ).splitlines()
    binaries = {}
    for (tool, expected), line in zip(paths.items(), hashes, strict=True):
        digest, path = line.split(maxsplit=1)
        if path != expected:
            raise ValueError(f"Unexpected tool path in the ORFS image: {path}")
        binaries[tool] = {"path": path, "sha256": digest}

    manifest = root / "SOURCE_MANIFEST.json"
    profile = {
        "source_commit": subprocess.check_output(
            ["git", "-C", source, "rev-parse", "HEAD"], text=True
        ).strip(),
        "openroad_bin": paths["openroad"],
        "yosys_bin": paths["yosys"],
        "python_bin": str(python),
        "runtime": {"kind": "apptainer", "executable": runtime, "image": image},
        "toolchain": {
            **value["toolchain"],
            "binaries": binaries,
            "source_manifest_path": str(manifest),
            "source_manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
        },
    }
    value["flow_tool_profile"] = str(state / "flow-tool-profile.json")
    design = value["designs"]["gcd"]
    design.update(
        baseline_overrides=GCD_OVERRIDES,
        signal_layers="metal2-metal10",
        clock_layers="metal4-metal10",
        flow_dependencies=[
            {"source": str(inputs / name), "destination": f"inputs/{name}"}
            for name in ("gcd-floorplan-route.tcl", "gcd-global-route.tcl")
        ],
    )
    value.setdefault("professional", {})["flow"] = {
        "source": str(source),
        "python": str(python),
        "execution": {
            "threads": design["orfs_execution"]["cpu_cores"],
            "memory_gib": 4,
            "stage_timeout_seconds": 180,
        },
    }
    return Path(value["flow_tool_profile"]), profile
