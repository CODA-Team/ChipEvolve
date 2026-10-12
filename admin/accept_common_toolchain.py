"""Verify U1 build, physical flow and public SDK evidence without rerunning EDA."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from qualify_common_toolchain import IMAGE_SHA, OPENROAD, ORFS, ROOT, source_identity
from run_dplevolve_native import digest, now, write_json


def read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def validate_sdk(record: dict[str, Any], runtime: dict[str, Any]) -> None:
    jobs = runtime["jobs"]
    snapshot = record["summary"]["data"]["snapshot"]
    scope = record["scope"]["scope"]
    expected = {
        "design_id": "gcd",
        "snapshot_id": runtime["snapshot_id"],
        "run_id": jobs["flow"]["run"]["run_id"],
        "stage": "finish",
    }
    for key, value in expected.items():
        if snapshot[key] != value or scope[key] != value:
            raise ValueError("SDK design scope differs: " + key)
    if snapshot["producer_run_id"] != jobs["export"]["run"]["run_id"]:
        raise ValueError("Snapshot producer differs from the registered export")
    for name in (
        "entities",
        "relations",
        "physical_context",
        "timing_paths",
        "timing_points",
    ):
        if snapshot["record_counts"][name] <= 0:
            raise ValueError("Missing design facts: " + name)
    metric_scope = record["metrics"]["scope"]
    if (
        metric_scope["snapshot_id"] != runtime["metric_snapshot_id"]
        or metric_scope["run_id"] != expected["run_id"]
        or metric_scope["design_id"] != "gcd"
    ):
        raise ValueError("Metric snapshot has a different physical owner")
    if (
        not record["metrics"]["data"]["metrics"]
        or not record["paths"]["data"]["timing_paths"]
    ):
        raise ValueError("SDK metrics or timing paths are missing")
    by_name = {row["name"]: row for row in record["metrics"]["data"]["metrics"]}
    for name, unit in {
        "WNS": "ns",
        "TNS": "ns",
        "AREA": "um^2",
        "POWER_TOTAL": "W",
        "INSTANCE_COUNT": "count",
    }.items():
        if (
            name not in by_name
            or by_name[name]["status"] != "available"
            or by_name[name]["unit"] != unit
        ):
            raise ValueError("Required metric or its unit is unavailable: " + name)
    registered = {a["artifact_id"]: a for a in jobs["export"]["artifacts"]}
    for source in snapshot["source_artifacts"]:
        actual = registered[source["artifact_id"]]
        if source["sha256"] != actual["sha256"] or source["run_id"] != actual["run_id"]:
            raise ValueError("Snapshot source differs from the registered artifact")
    for stem in ("6_final.odb", "6_final.sdc", "6_final.spef"):
        original = next(
            a for a in jobs["flow"]["artifacts"] if Path(a["store_key"]).name == stem
        )
        staged = next(
            a
            for a in snapshot["source_artifacts"]
            if Path(a["logical_path"]).name == stem
        )
        if staged["sha256"] != original["sha256"]:
            raise ValueError("Export used a different physical input: " + stem)
    if (
        record["fragment"]["status"] != "available"
        or not record["fragment"]["data"]["fragments"]
    ):
        raise ValueError("Original timing evidence is unavailable")
    metric_raw = record["metric_raw_evidence"]
    original = next(
        a
        for a in jobs["flow"]["artifacts"]
        if Path(a["store_key"]).name == "6_report.json"
    )
    copied = next(
        a
        for a in jobs["metrics_export"]["artifacts"]
        if a["artifact_id"] == metric_raw["artifact_id"]
    )
    if (
        metric_raw["sha256"] != original["sha256"]
        or copied["sha256"] != original["sha256"]
    ):
        raise ValueError("Metrics used a different original ORFS report")
    for row in record["metrics"]["data"]["metrics"]:
        if (
            row["status"] == "available"
            and row["raw_value"] != metric_raw["source"][row["raw_key"]]
        ):
            raise ValueError("SDK metric differs from the original measured value")
    raw = record["raw_evidence"]
    if (
        registered[raw["artifact_id"]]["sha256"] != raw["sha256"]
        or raw["size_bytes"] <= 0
    ):
        raise ValueError("Raw evidence bytes differ from their registered identity")


def sdk(state: Path, receipt: Path | None = None) -> None:
    from eda_ai_client import EdaAiClient

    receipt = receipt or state / "runtime.json"
    runtime = read(receipt)
    client = EdaAiClient(data_url=runtime["data_url"], kernel_url=runtime["kernel_url"])
    snapshot_id = runtime["snapshot_id"]
    record = {
        "summary": client.read_query(
            "/snapshots/" + snapshot_id + "/summary", parameters={"detail": "full"}
        ),
        "scope": client.resolve_scope(snapshot_id=snapshot_id),
        "metrics": client.get_metrics(snapshot_id=runtime["metric_snapshot_id"]),
        "paths": client.get_timing_paths(snapshot_id, limit=2),
    }
    path = record["paths"]["data"]["timing_paths"][0]
    record["fragment"] = client.read_evidence(
        snapshot_id, "timing_paths", path["path_id"]
    )
    source = next(
        a
        for a in record["summary"]["data"]["snapshot"]["source_artifacts"]
        if a["category"] == "raw_timing_report"
    )
    raw = client.artifact_bytes(source["run_id"], source["artifact_id"])
    record["raw_evidence"] = {
        "artifact_id": source["artifact_id"],
        "size_bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }
    metric_raw = next(
        a
        for a in runtime["jobs"]["metrics_export"]["artifacts"]
        if Path(a["store_key"]).name == "6_report.json"
    )
    metric_bytes = client.artifact_bytes(
        metric_raw["run_id"], metric_raw["artifact_id"]
    )
    record["metric_raw_evidence"] = {
        "artifact_id": metric_raw["artifact_id"],
        "sha256": hashlib.sha256(metric_bytes).hexdigest(),
        "source": json.loads(metric_bytes),
    }
    write_json(receipt.with_name(receipt.stem + "-sdk-evidence.json"), record)
    validate_sdk(record, runtime)
    print(json.dumps({"sdk_verified": True, "snapshot_id": snapshot_id}), flush=True)


def validate_results(
    config: dict[str, Any],
    runtime: dict[str, Any],
    built: dict[str, Any],
    checked: dict[str, Any],
    sdk_record: dict[str, Any],
) -> None:
    if (config["image_sha256"], config["openroad_commit"], config["orfs_commit"]) != (
        IMAGE_SHA,
        OPENROAD,
        ORFS,
    ):
        raise ValueError("Qualification is not for the selected common baseline")
    if runtime["status"] != "succeeded":
        raise ValueError("Qualification did not complete")
    for name in ("build", "flow", "export", "check", "metrics_export", "units_export"):
        job = runtime["jobs"][name]
        if job["run"]["status"] != "succeeded" or not job["artifacts"]:
            raise ValueError("EF task or artifacts are incomplete: " + name)
    if (
        built["openroad_commit"] != OPENROAD
        or built["tracked_source_unchanged"] is not True
        or built["image_sha256"] != IMAGE_SHA
        or built["source_manifest_sha256"] != config["source_manifest_sha256"]
        or built["source_archive_sha256"] != config["source_archive_sha256"]
    ):
        raise ValueError("Build did not use frozen unmodified source")
    if (
        checked["design"] != "gcd"
        or checked["platform"] != "nangate45"
        or checked["instances"] <= 0
        or checked["nets"] <= 0
        or not math.isfinite(checked["wns_ns"])
        or checked["placement_check_passed"] is not True
        or checked["binary_sha256"] != built["binary_sha256"]
        or checked["image_sha256"] != IMAGE_SHA
    ):
        raise ValueError("Compiled binary has no valid real-design check")
    odb = next(
        a
        for a in runtime["jobs"]["flow"]["artifacts"]
        if Path(a["store_key"]).name == "6_final.odb"
    )
    if checked["input_odb_sha256"] != odb["sha256"]:
        raise ValueError("Compiled tool checked a different design input")
    for name in ("6_final.odb", "6_final.sdc", "6_final.spef", "6_final.gds"):
        if not any(
            Path(a["store_key"]).name == name and a["size_bytes"] > 0
            for a in runtime["jobs"]["flow"]["artifacts"]
        ):
            raise ValueError("Full flow is missing final output: " + name)
    validate_sdk(sdk_record, runtime)


def audit(state: Path, receipt: Path | None = None) -> dict[str, Any]:
    receipt = receipt or state / "runtime.json"
    config, runtime = read(state / "config.json"), read(receipt)
    built, checked = (
        read(state / "results" / phase / "qualification.json")
        for phase in ("build", "check")
    )
    validate_results(
        config,
        runtime,
        built,
        checked,
        read(receipt.with_name(receipt.stem + "-sdk-evidence.json")),
    )
    identities = {
        Path(config["image"]): IMAGE_SHA,
        state / "source-manifest.json": config["source_manifest_sha256"],
        state / "source.tar": config["source_archive_sha256"],
        state / "results/build/openroad": built["binary_sha256"],
        state / "results/check/roundtrip.odb": checked["roundtrip_sha256"],
    }
    repair = runtime.get("data_completion")
    driver_root = Path(repair["original_driver_root"]) if repair else ROOT / "admin"
    identities.update(
        {driver_root / name: sha for name, sha in config["driver_files"].items()}
    )
    if repair:
        original_receipt = state / "runtime.json"
        if digest(original_receipt) != repair["original_runtime_sha256"]:
            raise ValueError(
                "Original execution receipt changed during data completion"
            )
        prior = read(original_receipt)
        for phase in ("build", "flow", "export", "check"):
            if runtime["jobs"][phase] != prior["jobs"][phase]:
                raise ValueError("Data completion changed a completed physical task")
        identities.update(
            {
                ROOT / "admin" / name: sha
                for name, sha in repair["current_driver_sha256"].items()
            }
        )
    identities.update(
        {state / "wheels" / name: sha for name, sha in config["wheel_sha256"].items()}
    )
    for path, sha in identities.items():
        if digest(path) != sha:
            raise ValueError("Frozen qualification bytes changed: " + str(path))
    if source_identity(state / "source/OpenROAD") != read(
        state / "source-manifest.json"
    ):
        raise ValueError("Frozen source changed after execution")
    # Locally retrieved evidence must be the exact EF-registered containers.
    import zipfile

    for phase in ("build", "check"):
        archive = state / "results" / (phase + ".zip")
        artifact = next(
            a
            for a in runtime["jobs"][phase]["artifacts"]
            if a["kind"] == "data_snapshot"
        )
        if digest(archive) != artifact["sha256"]:
            raise ValueError("Qualification bundle differs from its registration")
        with zipfile.ZipFile(archive) as bundle:
            for name in bundle.namelist():
                if (
                    not name.endswith("/")
                    and bundle.read(name)
                    != (state / "results" / phase / name).read_bytes()
                ):
                    raise ValueError(
                        "Retrieved qualification evidence changed: " + name
                    )
    result = {
        "engineering_accepted": True,
        "business_acceptance": "pending_owner_verification",
        "checked_at": now(),
        "run_root": str(state),
        "image_sha256": IMAGE_SHA,
        "openroad_commit": OPENROAD,
        "orfs_commit": ORFS,
        "binary_sha256": built["binary_sha256"],
        "compiled_design_check": checked,
        "ef_runs": {k: v["run"]["run_id"] for k, v in runtime["jobs"].items()},
        "snapshot_id": runtime["snapshot_id"],
        "no_agent_migration_claimed": True,
    }
    write_json(state / "u1-acceptance.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("sdk", "audit"))
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--runtime-receipt", type=Path)
    args = parser.parse_args()
    if args.action == "sdk":
        sdk(args.run_root.resolve(), args.runtime_receipt)
    else:
        print(
            json.dumps(
                audit(args.run_root.resolve(), args.runtime_receipt), ensure_ascii=False
            )
        )


if __name__ == "__main__":
    main()
