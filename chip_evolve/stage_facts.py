"""Expose existing native checkpoints through scoped EF evidence, without EDA."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any

from .config import Deployment, read, write
from .jobs import Jobs, digest
from .validation import query_facts


def bundle(jobs: Jobs, run_id: str, folder: Path) -> tuple[Path, dict[str, Any]]:
    run = jobs.client.run(run_id)
    if run["design_id"] != jobs.design_id or run["status"] != "succeeded":
        raise ValueError("Stage producer is not a successful run of this design")
    artifacts = [
        a for a in jobs.client.artifacts(run_id) if a["kind"] == "data_snapshot"
    ]
    if len(artifacts) != 1:
        raise ValueError("Choose one registered native evidence bundle")
    artifact = artifacts[0]
    path = folder / (run_id + ".zip")
    jobs.client.materialize_artifact(run_id, artifact["artifact_id"], str(path))
    if digest(path) != artifact["sha256"]:
        raise ValueError("Native evidence differs from its registered artifact")
    with zipfile.ZipFile(path) as archive:
        manifest = json.loads(archive.read("manifest.json"))
    return path, {"run_id": run_id, "artifact_id": artifact["artifact_id"], **manifest}


def extract(path: Path, receipt: dict[str, Any], name: str, output: Path) -> Path:
    expected = receipt["output_files"][str(Path(receipt["request"]["cwd"]) / name)]
    with zipfile.ZipFile(path) as archive:
        candidates = [n for n in archive.namelist() if Path(n).name == name]
        matches = [
            archive.read(n)
            for n in candidates
            if hashlib.sha256(archive.read(n)).hexdigest() == expected
        ]
    if len(matches) != 1:
        raise ValueError("Native file lacks unique hash-matched evidence: " + name)
    output.write_bytes(matches[0])
    return output


def observations(
    checkpoints: dict[str, Any], output_files: dict[str, str]
) -> list[dict[str, Any]]:
    rows = []
    previous: dict[str, Any] | None = None
    for stage, metrics in checkpoints["checkpoints"].items():
        hashes = {
            sha for p, sha in output_files.items() if p.endswith("/" + stage + ".v")
        }
        row = {
            "stage": stage,
            "native_metrics": metrics,
            "netlist_sha256": next(iter(hashes)) if len(hashes) == 1 else None,
            "same_reported_metrics_as_previous": metrics == previous["native_metrics"]
            if previous
            else None,
            "same_netlist_as_previous": previous["netlist_sha256"] in hashes
            if hashes and previous and previous["netlist_sha256"]
            else None,
        }
        rows.append(row)
        previous = row
    return rows


def matches_evaluation(native: dict[str, Any], measured: dict[str, Any]) -> bool:
    cwd = native["request"]["cwd"]
    log = str(Path(cwd) / "evaluation.log")
    return (
        measured["request"]["cwd"] == cwd
        and measured["request"]["inputs"].get(log) == native["output_files"].get(log)
        and log in native["output_files"]
        and str(Path(cwd) / "checkpoint_metrics.json") in measured["output_files"]
    )


def ensure_stage_facts(deployment: Deployment, result_path: Path) -> Path | None:
    frame = read(result_path)
    if (frame.get("native_method") or {}).get("kind") not in {
        "native-baseline",
        "native-search",
        "native-fixed-source",
    }:
        return None
    checkpoint = result_path.parent / "delivery-checkpoint.json"
    if not checkpoint.exists():
        return None
    saved = read(checkpoint)
    operations = result_path.parent / "operations"
    if not operations.exists() or saved["native_method"] != frame.get("native_method"):
        return None
    key = (
        "stages-"
        + digest(result_path)[:12]
        + "-"
        + hashlib.sha256(str(deployment.state).encode()).hexdigest()[:8]
    )
    folder = deployment.state / "experiments" / frame["design_id"] / key
    folder.mkdir(parents=True, exist_ok=True)
    final, receipt_path = folder / "native-stages.json", folder / "stage-receipt.json"
    if receipt_path.exists():
        receipt = read(receipt_path)
        if receipt["result_sha256"] != digest(result_path) or receipt[
            "facts_sha256"
        ] != digest(final):
            raise ValueError("Registered stage evidence changed")
        return final
    jobs = Jobs(deployment, frame["design_id"], folder)
    producer = saved["producer"]
    source_zip, physical = bundle(jobs, producer, folder)
    if "receipt" not in physical:
        return None
    native = physical["receipt"]
    cwd = native["request"]["cwd"]
    log_name = str(Path(cwd) / "evaluation.log")
    if log_name not in native["output_files"]:
        return None
    if saved["input_hashes"][saved["odb"]] not in native["output_files"].values():
        raise ValueError("Stage producer does not own the selected checkpoint")
    matches = []
    for record in sorted(operations.glob("*/execution.json")):
        request = read(record.parent / "request.json")
        if request["operation"] != "analysis" or request["cwd"] != cwd:
            continue
        run = read(record)["run"]
        if run["status"] != "succeeded":
            continue
        path, evidence = bundle(jobs, run["run_id"], folder)
        measured = evidence["receipt"]
        if matches_evaluation(native, measured):
            matches.append((path, evidence))
    if not matches:
        return None
    signatures = {
        e["receipt"]["output_files"][str(Path(cwd) / "checkpoint_metrics.json")]
        for _, e in matches
    }
    if len(signatures) != 1:
        raise ValueError("Same native evaluation has conflicting checkpoint facts")
    path, evidence = matches[0]
    stages = extract(
        path,
        evidence["receipt"],
        "checkpoint_metrics.json",
        folder / "checkpoints.json",
    )
    tcl = extract(source_zip, native, "evaluate.tcl", folder / "native-evaluate.tcl")
    log = extract(
        source_zip, native, "evaluation.log", folder / "native-evaluation.log"
    )
    query_facts(deployment, frame)
    write(
        final,
        {
            "schema_version": "chip-evolve.native-stages.v1",
            "design_id": frame["design_id"],
            "run_id": frame["run_id"],
            "objective_id": frame["objective_id"],
            "condition_id": frame["condition_id"],
            "native_producer_run_id": producer,
            "native_identity": {
                "image_sha256": native["request"]["image_sha256"],
                "binary_sha256": native["request"]["inputs"][
                    native["request"]["command"][0]
                ],
                "tcl_sha256": digest(tcl),
            },
            "native_method": frame["native_method"],
            "stages": observations(read(stages), evidence["receipt"]["output_files"]),
            "declared_commands": [
                line.strip()
                for line in tcl.read_text().splitlines()
                if line.strip().startswith(
                    (
                        "repair_design",
                        "repair_timing",
                        "repair_power",
                        "detailed_placement",
                        "global_route",
                    )
                )
            ],
            "evidence": [
                {k: e[k] for k in ("run_id", "artifact_id")}
                for e in [physical, evidence]
            ],
            "interpretation": "Native reported checkpoint metrics; *_ns and *_pw retain original units. These are not common final DRT/RCX metrics. Equal reported values alone do not prove an action never ran or establish causality; netlist equality is listed separately. Declared Tcl commands are not an action counter.",
        },
    )
    captured = [final, stages, tcl, log]
    registered = jobs.command(
        "register-stages",
        [
            deployment.value["client_python"],
            "-c",
            "print('registered native stage facts')",
        ],
        capture=captured,
        extra_paths=[
            "query-data/" + str(i) + "/" + p.name for i, p in enumerate(captured)
        ],
        analysis_parent=frame["run_id"],
        parent=producer,
        objective=Path(frame["objective"]),
        seconds=300,
        cpu=1,
        memory_gib=2,
    )
    write(
        receipt_path,
        {
            "result_sha256": digest(result_path),
            "facts_sha256": digest(final),
            "analysis_run_id": registered["run"]["run_id"],
            "analysis_of_run_id": frame["run_id"],
            "eda_jobs_launched": 0,
        },
    )
    return final
