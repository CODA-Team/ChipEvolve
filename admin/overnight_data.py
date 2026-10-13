"""Export real checkpoints through EF and inspect them through the installed SDK."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from overnight_runtime import collect, submit
from qualify_common_toolchain import http
from run_dplevolve_native import now, write_json


def export(state: Path, key: str, physical_run: str, files: dict[str, Path]) -> dict:
    runtime = json.loads((state / "runtime.json").read_text())
    result = {}
    plans = [("opendb", "odb_path", files["odb"])]
    if files.get("metrics") is not None:
        plans.append(("orfs", "metadata_path", files["metrics"]))
    for mode, field, source in plans:
        snapshot = state.name + "-" + key + "-" + mode
        destination = "inputs/" + source.name
        spec = {
            "schema_version": 3,
            "task_id": snapshot,
            "project_id": "overnight-gcd",
            "design_id": "gcd",
            "experiment_id": state.name,
            "plugin_id": "openroad-data",
            "labels": {
                "run_type": "analysis",
                "analysis_of_run_id": physical_run,
                "memory_approval": "manual",
            },
            "inputs": {
                "adapter": mode,
                field: destination,
                "openroad_bin": str(
                    Path(runtime["client_python"]).parent / "eda-openroad"
                ),
                "threads": 2,
                "snapshot_id": snapshot,
                "design_id": "gcd",
                "revision_id": key,
                "run_id": physical_run,
                "stage": "finish",
                "created_at": now(),
                "native_extra_paths": [
                    "inputs/" + p.name for p in files.values() if p is not None
                ],
            },
            "staged_inputs": [
                {"source": str(p.resolve()), "destination": "inputs/" + p.name}
                for p in files.values()
                if p is not None
            ],
            "timeout_seconds": 300,
            "resources": {"cpu_cores": 2, "memory_bytes": 8 << 30, "processes": 2048},
            "max_attempts": 1,
            "expected_artifacts": ["data_snapshot"],
        }
        task_key = key + "-" + mode
        submit(state, task_key, spec)
        record = collect(state, task_key)
        if record["run"]["status"] != "succeeded":
            raise RuntimeError("Real export failed: " + task_key)
        artifact = next(a for a in record["artifacts"] if a["kind"] == "data_snapshot")
        receipt = http(
            runtime["data_url"] + "/snapshots/from-run",
            {"run_id": record["run"]["run_id"], "artifact_id": artifact["artifact_id"]},
        )
        result[mode] = {"snapshot_id": snapshot, "execution": record, "import": receipt}
        write_json(state / (key + "-data.json"), result)
    return result


def inspect(state: Path, key: str) -> dict:
    from eda_ai_client import EdaAiClient

    runtime = json.loads((state / "runtime.json").read_text())
    data = json.loads((state / (key + "-data.json")).read_text())
    client = EdaAiClient(data_url=runtime["data_url"], kernel_url=runtime["kernel_url"])
    objects = data["opendb"]["snapshot_id"]
    metrics = data["orfs"]["snapshot_id"]
    run = data["opendb"]["execution"]["run"]["labels"]["analysis_of_run_id"]
    result = {
        "designs": client.list_designs(),
        "runs": client.list_runs(design_id="gcd"),
        "summary": client.get_run_summary(run),
        "instances": client.query_objects(objects, kind="instance", limit=5),
        "nets": client.query_objects(objects, kind="net", limit=5),
        "metrics": client.get_metrics(snapshot_id=metrics),
        "raw_artifacts": client.list_artifacts(
            data["opendb"]["execution"]["run"]["run_id"]
        ),
    }
    write_json(state / (key + "-sdk-query.json"), result)
    return result


def timing(state: Path, key: str) -> dict:
    runtime = json.loads((state / "runtime.json").read_text())
    record = json.loads((state / (key + "-data.json")).read_text())["opendb"][
        "execution"
    ]
    sources = {}
    for kind, name in (
        ("raw_design_database", "design.odb"),
        ("raw_constraints", "design.sdc"),
        ("raw_parasitics", "design.spef"),
    ):
        sources[name] = next(a for a in record["artifacts"] if a["kind"] == kind)[
            "artifact_id"
        ]
    pdk = state / "agents/eco-smoke/source/asap7/lib/NLDM"
    libs = [
        pdk / ("asap7sc7p5t_" + group + "_" + vt + "_FF_nldm_" + version)
        for vt in ("RVT", "LVT", "SLVT")
        for group, version in (
            ("AO", "211120.lib.gz"),
            ("INVBUF", "220122.lib.gz"),
            ("OA", "211120.lib.gz"),
            ("SIMPLE", "211120.lib.gz"),
            ("SEQ", "220123.lib"),
        )
    ]
    if not all(p.is_file() for p in libs):
        raise FileNotFoundError("Actual ORFS FF RVT libraries are missing")
    snapshot = state.name + "-" + key + "-timing"
    physical_run = record["run"]["labels"]["analysis_of_run_id"]
    spec = {
        "schema_version": 3,
        "task_id": snapshot,
        "project_id": "overnight-gcd",
        "design_id": "gcd",
        "experiment_id": state.name,
        "plugin_id": "openroad-data",
        "labels": {
            "analysis_of_run_id": physical_run,
            "run_type": "analysis",
            "memory_approval": "manual",
        },
        "inputs": {
            "adapter": "openroad",
            "odb_path": "inputs/design.odb",
            "sdc_path": "inputs/design.sdc",
            "spef_path": "inputs/design.spef",
            "parasitic_mode": "spef",
            "liberty_paths": ["inputs/" + p.name for p in libs],
            "unit": "s",
            "corner": "FF",
            "analysis": "post_route",
            "path_count": 5,
            "openroad_bin": str(Path(runtime["client_python"]).parent / "eda-openroad"),
            "threads": 2,
            "snapshot_id": snapshot,
            "design_id": "gcd",
            "revision_id": key,
            "run_id": physical_run,
            "stage": "timing",
            "created_at": now(),
        },
        "staged_inputs": [
            {"artifact_id": aid, "destination": "inputs/" + name}
            for name, aid in sources.items()
        ]
        + [{"source": str(p), "destination": "inputs/" + p.name} for p in libs],
        "timeout_seconds": 300,
        "resources": {"cpu_cores": 2, "memory_bytes": 8 << 30, "processes": 2048},
        "max_attempts": 1,
        "expected_artifacts": ["data_snapshot"],
    }
    submit(state, key + "-timing", spec)
    result = collect(state, key + "-timing")
    if result["run"]["status"] != "succeeded":
        raise RuntimeError("Actual STA export failed")
    artifact = next(a for a in result["artifacts"] if a["kind"] == "data_snapshot")
    receipt = http(
        runtime["data_url"] + "/snapshots/from-run",
        {"run_id": result["run"]["run_id"], "artifact_id": artifact["artifact_id"]},
    )
    write_json(
        state / (key + "-timing-data.json"),
        {"snapshot_id": snapshot, "execution": result, "import": receipt},
    )
    return receipt


def goal_metrics(state: Path, key: str, physical_run: str, measurement: Path) -> dict:
    """Project a completed original Goal result, retaining the native result as evidence."""
    from openroad_platform_client import KernelClient

    runtime = json.loads((state / "runtime.json").read_text())
    source = json.loads(measurement.read_text())
    if not source["ok"]:
        raise ValueError("A failed native result is not an authoritative measurement")
    client = KernelClient(runtime["kernel_url"])
    if client.run(physical_run)["status"] != "succeeded":
        raise ValueError("The physical producer must have succeeded")
    values = source["metrics"]
    metadata = state / "requests" / (key + "-metrics.json")
    metadata.parent.mkdir(exist_ok=True)
    write_json(
        metadata,
        {
            "metrics": {
                "finish__timing__setup__tns": -values["tns_abs_ns"],
                "finish__power__total": (
                    values["dynamic_power_pw"] + values["leakage_power_pw"]
                )
                * 1e-12,
                "finish__power__dynamic": values["dynamic_power_pw"] * 1e-12,
                "finish__power__leakage": values["leakage_power_pw"] * 1e-12,
                "run__flow__platform__time_units": "1ns",
                "run__flow__platform__distance_units": "1um",
                "run__flow__platform__power_units": "1W",
            },
            "metric_context": {
                "corner": "FF",
                "analysis": "global_routing",
                "authoritative_source": "original GoalEvolve official result",
                "evaluation_conditions": {
                    "ideal_clocks": True,
                    "parasitics": "global_routing",
                },
            },
        },
    )
    snapshot = state.name + "-" + key
    spec = {
        "schema_version": 3,
        "task_id": snapshot,
        "project_id": "overnight-gcd",
        "design_id": "gcd",
        "experiment_id": state.name,
        "plugin_id": "openroad-data",
        "labels": {"analysis_of_run_id": physical_run, "run_type": "analysis"},
        "inputs": {
            "adapter": "orfs",
            "metadata_path": "inputs/metrics.json",
            "snapshot_id": snapshot,
            "design_id": "gcd",
            "revision_id": key,
            "run_id": physical_run,
            "stage": "global_route",
            "created_at": now(),
            "native_extra_paths": ["inputs/native-result.json"],
        },
        "staged_inputs": [
            {"source": str(metadata), "destination": "inputs/metrics.json"},
            {"source": str(measurement), "destination": "inputs/native-result.json"},
        ],
        "timeout_seconds": 120,
        "resources": {"cpu_cores": 1, "memory_bytes": 512 << 20, "processes": 2048},
        "max_attempts": 1,
        "expected_artifacts": ["data_snapshot"],
    }
    submit(state, key, spec)
    result = collect(state, key)
    if result["run"]["status"] != "succeeded":
        raise RuntimeError("Native result publication failed")
    artifact = next(a for a in result["artifacts"] if a["kind"] == "data_snapshot")
    receipt = http(
        runtime["data_url"] + "/snapshots/from-run",
        {"run_id": result["run"]["run_id"], "artifact_id": artifact["artifact_id"]},
    )
    write_json(
        state / (key + "-data.json"),
        {"snapshot_id": snapshot, "execution": result, "import": receipt},
    )
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["export", "inspect", "timing"])
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--key", required=True)
    parser.add_argument("--run")
    parser.add_argument("--odb", type=Path)
    parser.add_argument("--metrics", type=Path)
    parser.add_argument("--raw", nargs="*", type=Path, default=[])
    args = parser.parse_args()
    state = args.state.resolve()
    if args.action == "export":
        files = {"odb": args.odb, "metrics": args.metrics}
        files.update({str(i): path for i, path in enumerate(args.raw)})
        result = export(state, args.key, args.run, files)
        print(json.dumps({mode: row["snapshot_id"] for mode, row in result.items()}))
    elif args.action == "timing":
        print(json.dumps(timing(state, args.key)))
    else:
        result = inspect(state, args.key)
        print(json.dumps({key: type(value).__name__ for key, value in result.items()}))


if __name__ == "__main__":
    main()
