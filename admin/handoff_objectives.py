"""Local A2/A3 acceptance: retained placement and frozen shared final conditions."""

from __future__ import annotations

import argparse
import json
import shutil
import zipfile
from pathlib import Path

from gcd_common_remeasure import measure, reference_liberties
from resume_placement import resume
from run_dplevolve_native import digest, write_json


def freeze(state: Path) -> Path:
    from eda_toolkits.objectives import SCHEMA, objective_id

    folder = state / "fix-a2-a3"
    folder.mkdir(parents=True, exist_ok=True)
    objective = folder / "shared-objective.json"
    if objective.exists():
        raise FileExistsError("Keep the previously frozen objective")
    reference = json.loads(
        (state / "handoffs/opt2-original-qualified/measurement.json").read_text()
    )
    metrics = reference["metrics"]
    runtime = json.loads((state / "runtime.json").read_text())
    sdc = folder / "common.sdc"
    shutil.copyfile(state / "optimization-r1/common.sdc", sdc)
    value = {
        "schema_version": SCHEMA,
        "design_id": "gcd",
        "reference_run_id": reference["run_id"],
        "conditions": {
            "toolchain": runtime["toolchain"],
            "libraries": [
                {"path": str(p), "sha256": digest(p)}
                for p in reference_liberties(state)
            ],
            "sdc": {"path": str(sdc), "sha256": digest(sdc)},
            "corner": "FF",
            "clock_period_ns": 0.310,
            "propagated_clock": True,
            "analysis": "post_route",
            "parasitics": "full detailed-route extracted SPEF for each candidate",
            "units": {"time": "ns", "power": "W", "area": "um^2"},
            "area_scopes": {
                "cell": "instance area excluding fillers",
                "core": "core rectangle",
                "die": "die rectangle",
            },
        },
        "constraints": {
            "setup_tns_ns_min": 0,
            "hold_tns_ns_min": 0,
            "max_slew_violations": 0,
            "max_cap_violations": 0,
            "placement_violations": 0,
            "route_drc": 0,
            "power_total_w_max": metrics["finish__power__total"],
            "cell_area_um2_max": metrics["finish__design__instance__area"],
            "core_area_um2_max": metrics["finish__design__core__area"],
            "die_area_um2_max": metrics["finish__design__die__area"],
        },
    }
    value["objective_id"] = objective_id(value)
    write_json(objective, value)
    return objective


def common_profile(state: Path, objective: Path) -> Path:
    from eda_toolkits.objectives import load_objective, verify_conditions

    value = load_objective(objective)
    verify_conditions(value)
    old = json.loads((state / "agents/flow-r5/profile.json").read_text())
    source = Path(old["flow_dir"])
    destination = state / "fix-a2-a3/common-flow"
    shutil.copytree(
        source,
        destination,
        ignore=shutil.ignore_patterns(
            "results",
            "logs",
            "reports",
            "objects",
            "tmp",
            "backup_dir",
            "__pycache__",
            ".git",
        ),
    )
    # Change only this private copy; same-named FF SIMPLE_RVT differed upstream.
    bindings = []
    for lib in value["conditions"]["libraries"]:
        target = destination / "platforms/asap7/lib/NLDM" / Path(lib["path"]).name
        previous = digest(target)
        shutil.copyfile(lib["path"], target)
        bindings.append(
            {"path": str(target), "sha256": digest(target), "previous_sha256": previous}
        )
    profile = {
        **old,
        "flow_dir": str(destination),
        "objective_path": str(objective),
        "shared_libraries": bindings,
        "objective_id": value["objective_id"],
    }
    path = state / "fix-a2-a3/common-profile.json"
    write_json(path, profile)
    old_config = source / "backup_dir/asap7/gcd/result_dump_2/config_6.mk"
    text = old_config.read_text().replace(str(source), str(destination))
    # ASAP7 BC names the actual FF liberty corner; do not use a made-up FF key.
    text += "\nexport CORNER = BC\n"
    (path.parent / "common-config.mk").write_text(text)
    return path


def branch(state: Path, key: str, *, dpl: bool, common: bool) -> dict:
    folder = state / "fix-a2-a3"
    selected = json.loads((state / "flow-selection.json").read_text())
    archive = state / "requests/a2-dpl-retained/flow.zip"
    placement = folder / (key + ".odb")
    if dpl:
        shutil.copyfile(state / "requests/a2-dpl-retained/placement.odb", placement)
        parent = "run-b1c738b01d2a4eeb9ecd2266e65ec5d1"
    else:
        with zipfile.ZipFile(archive) as bundle:
            placement.write_bytes(bundle.read("flow/results/3_place.odb"))
        parent = selected["run_id"]
    if common:
        profile = folder / "common-profile.json"
        spec = json.loads(profile.read_text())
        for lib in spec["shared_libraries"]:
            if digest(Path(lib["path"])) != lib["sha256"]:
                raise ValueError("Frozen physical-stage library changed")
        objective = folder / "shared-objective.json"
        config, sdc = folder / "common-config.mk", folder / "common.sdc"
    else:
        profile = state / "agents/flow-r5/profile.json"
        config = (
            state
            / "agents/flow-r5/source/flow/backup_dir/asap7/gcd/result_dump_2/config_6.mk"
        )
        sdc = state / "handoffs/flow/flow/results/3_place.sdc"
        objective = None
    return resume(
        state,
        key,
        design="gcd",
        profile=profile,
        config=config,
        sdc=sdc,
        flow_archive=archive,
        placement=placement,
        parent_run=parent,
        objective=objective,
    )


def remeasure(state: Path, key: str, output_key: str) -> dict:
    folder = state / "handoffs" / key
    receipt = json.loads((folder / "handoff.json").read_text())
    inputs = folder / "results"
    return measure(
        state,
        output_key,
        inputs / "6_final.odb",
        inputs / "6_final.spef",
        state / "fix-a2-a3/common.sdc",
        receipt["route_run_id"],
        objective=state / "fix-a2-a3/shared-objective.json",
    )


def publish(state: Path, key: str) -> dict:
    """Keep measurement identity in DF's existing evaluation_conditions field."""
    from overnight_data import export, inspect

    source = state / "handoffs" / key
    record = json.loads((source / "measurement.json").read_text())
    metadata = json.loads((source / "metrics.json").read_text())
    folder = state / "fix-a2-a3/projected-metrics" / key
    folder.mkdir(parents=True, exist_ok=False)
    # Project metadata only; keep measured facts and old snapshots unchanged.
    conditions = metadata["metric_context"]["evaluation_conditions"]
    objective = json.loads((state / "fix-a2-a3/shared-objective.json").read_text())
    conditions.update(
        objective_id=record["objective_id"],
        condition_id=record["condition_id"],
        library_sha256=sorted(record["liberty_sha256"].values()),
        toolchain=record["toolchain"],
        clock_period_ns=objective["conditions"]["clock_period_ns"],
    )
    metadata_path = folder / "metrics.json"
    write_json(metadata_path, metadata)
    files = {
        "odb": source / "final.odb",
        "sdc": source / "final.sdc",
        "spef": Path(
            next(name for name in record["input_sha256"] if name.endswith(".spef"))
        ),
        "metrics": metadata_path,
        "objective": state / "fix-a2-a3/shared-objective.json",
    }
    data_key = key + "-context"
    export(state, data_key, record["run_id"], files)
    facts = inspect(state, data_key)
    rows = facts["metrics"]["data"]["metrics"]
    for row in rows:
        if row["evaluation_conditions"]["condition_id"] != record["condition_id"]:
            raise ValueError("DF query lost the common condition identity")
    return {
        "key": data_key,
        "condition_id": record["condition_id"],
        "metrics": len(rows),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=["freeze", "profile", "branch", "measure", "publish"]
    )
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--key")
    parser.add_argument("--output-key")
    parser.add_argument("--dpl", action="store_true")
    parser.add_argument("--common", action="store_true")
    args = parser.parse_args()
    state = args.state.resolve()
    if args.action == "freeze":
        print(freeze(state))
    elif args.action == "profile":
        print(common_profile(state, state / "fix-a2-a3/shared-objective.json"))
    elif args.action == "branch":
        print(
            branch(state, args.key, dpl=args.dpl, common=args.common)["run"]["status"]
        )
    elif args.action == "publish":
        print(json.dumps(publish(state, args.key)))
    else:
        result = remeasure(state, args.key, args.output_key)
        print(json.dumps({"run_id": result["run_id"], "metrics": result["metrics"]}))
