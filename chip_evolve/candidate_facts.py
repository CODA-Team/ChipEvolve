"""SDK-verified candidate facts for Codex; native promotion remains untouched."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from eda_toolkits.objectives import condition_id, load_objective

from .comparisons import METRICS, compare
from .config import Deployment, read, write
from .jobs import Jobs, digest
from .selection import violations
from .validation import query_facts

SCHEMA = "chip-evolve.candidate-facts.v1"
BRIEF_BYTES = 32 * 1024


def file_ref(path: Path) -> dict[str, Any]:
    return {"path": str(path.resolve()), "sha256": digest(path)}


def flow_feedback(jobs: Jobs, frame: dict[str, Any], folder: Path) -> dict[str, Any]:
    """Native fixed-clock feedback belongs to the actual physical producer."""
    evaluations = []
    offset = 0
    while runs := jobs.client.runs(
        analysis_of_run_id=frame["physical_run_id"],
        run_type="analysis",
        design_id=frame["design_id"],
        limit=100,
        offset=offset,
    ):
        for run in runs:
            if run["status"] != "succeeded":
                continue
            for artifact in jobs.client.artifacts(run["run_id"]):
                if artifact["kind"] != "raw_flow_metadata" or not artifact[
                    "store_key"
                ].endswith("a2-evaluation.json"):
                    continue
                path = folder / (run["run_id"] + "-native.json")
                jobs.client.materialize_artifact(
                    run["run_id"], artifact["artifact_id"], str(path)
                )
                if digest(path) != artifact["sha256"]:
                    raise ValueError("Native Flow feedback differs from its artifact")
                value = read(path)
                observation = {
                    k: value[k]
                    for k in ("observations", "evaluation", "parasitic_mode")
                }
                evidence = {
                    "run_id": run["run_id"],
                    "artifact_id": artifact["artifact_id"],
                    **file_ref(path),
                }
                previous = next(
                    (
                        entry
                        for entry in evaluations
                        if all(entry[k] == v for k, v in observation.items())
                    ),
                    None,
                )
                if previous is None:
                    evaluations.append({**observation, "evidence_refs": [evidence]})
                else:
                    previous["evidence_refs"].append(evidence)
        offset += len(runs)
    return {
        "kind": "native-Flow-feedback",
        "decision": None,
        "candidate_id": frame["candidate_id"],
        "evaluations": evaluations,
        "limitation": "Original fixed-CP0/library conditions, not final PPA; no native winner inferred",
    }


def native_facts(
    jobs: Jobs, frame: dict[str, Any], folder: Path, source: Path | None = None
) -> dict[str, Any]:
    """Read original verdicts and registered producer metrics, never re-score."""
    method = frame.get("native_method") or {}
    result: dict[str, Any] = {
        "kind": method.get("kind"),
        "decision": method.get("choice"),
        "parent": method.get("parent"),
        "metrics": method.get("metrics"),
        "evidence": [],
    }
    producer = (
        method.get("selected_producer")
        or method.get("producer")
        or method.get("producer_run_id")
        or frame.get("qualification", {}).get("producer_run_id")
    )
    if not producer and frame.get("candidate_id"):
        return flow_feedback(jobs, frame, folder)
    if (
        not producer
        and source
        and (source.parent / "delivery-checkpoint.json").exists()
    ):
        checkpoint = source.parent / "delivery-checkpoint.json"
        saved = read(checkpoint)
        if saved["design_id"] != frame["design_id"] or saved["native_method"] != method:
            raise ValueError("Native delivery checkpoint differs from the result")
        producer = saved["producer"]
        result["evidence"].append(file_ref(checkpoint))
    if not producer:
        result["limitation"] = "No explicit native producer; native score not inferred"
        return result
    run = jobs.client.run(producer)
    if run["design_id"] != frame["design_id"] or run["status"] != "succeeded":
        raise ValueError("Native producer is not a successful run of this design")
    artifacts = [
        row
        for row in jobs.client.artifacts(producer)
        if row["kind"] == "raw_flow_metadata"
        and row["store_key"].endswith("/metrics.json")
    ]
    if len(artifacts) != 1:
        result["limitation"] = "No single registered native metrics.json; see result"
        return result
    artifact = artifacts[0]
    path = folder / "native-metrics.json"
    jobs.client.materialize_artifact(producer, artifact["artifact_id"], str(path))
    if digest(path) != artifact["sha256"]:
        raise ValueError("Native metrics differ from the registered artifact")
    payload = read(path)
    # These are original payload fields, including their own unit declarations.
    # An unrecognized native format remains available through its evidence ref.
    result["metrics"] = {
        k: payload[k]
        for k in ("hpwl", "legality", "timing_metrics", "power_metrics")
        if k in payload
    }
    result["units"] = payload.get("units")
    result["interpretation"] = (
        "Original native conditions; not the common final measurement. "
        "Use explicitly unit-bearing fields (e.g. after_micron); other units "
        "are unknown unless declared by the producer."
    )
    result["evidence"].append(
        {
            "run_id": producer,
            "artifact_id": artifact["artifact_id"],
            "store_key": artifact["store_key"],
            **file_ref(path),
        }
    )
    return result


def candidate_row(
    jobs: Jobs, frame: dict[str, Any], path: Path, folder: Path
) -> dict[str, Any]:
    folder.mkdir()
    verified = query_facts(jobs.deployment, frame)
    receipt = folder / "sdk-verification.json"
    write(receipt, verified)
    # Verify the hard-constraint metrics too, not just the seven PPA quantities.
    payload = verified["metrics"]["data"]
    actual = {r["raw_key"]: r["raw_value"] for r in payload["metrics"]}
    actual.update({r["raw_key"]: r["value"] for r in payload["raw_metrics"]})
    checked = (
        *METRICS,
        "finish__timing__drv__max_slew",
        "finish__timing__drv__max_cap",
        "design__violations",
    )
    if any(actual.get(key) != frame["metrics"][key] for key in checked):
        raise ValueError("DF hard-constraint facts differ from the result")
    failed = violations(frame)
    from .stage_facts import ensure_stage_facts

    stages = ensure_stage_facts(jobs.deployment, path)
    return {
        "run_id": frame["run_id"],
        "physical_run_id": frame["physical_run_id"],
        "snapshot_ids": frame["snapshot_ids"],
        "native": native_facts(jobs, frame, folder, path),
        "stage_facts": file_ref(stages) if stages else None,
        "final_metrics": {k: frame["metrics"][k] for k in checked},
        "route_drc": frame.get("route_drc"),
        "final_constraint_violations": failed,
        "final_feasible": not failed,
        "evidence": {
            "result": file_ref(path),
            "sdk_verification": file_ref(receipt),
        },
    }


def compact_view(document: dict[str, Any], full_path: Path) -> dict[str, Any]:
    """Keep all constraints; move large per-candidate details behind refs."""
    if (
        len(json.dumps(document, ensure_ascii=False, indent=2).encode()) + 1
        <= BRIEF_BYTES
    ):
        return document
    rows = [document["reference"], *document["candidates"]]
    catalog = [
        {
            k: row[k]
            for k in (
                "run_id",
                "final_metrics",
                "route_drc",
                "final_feasible",
                "final_constraint_violations",
                "detail_ref",
            )
            if k in row
        }
        for row in rows
    ]
    return {
        **{k: v for k, v in document.items() if k not in {"reference", "candidates"}},
        "view": "catalog; expand explicitly selected candidate details",
        "reference": catalog[0],
        "candidates": catalog[1:],
        "full_facts": file_ref(full_path),
    }


def build_candidate_facts(
    deployment: Deployment,
    reference_path: Path,
    result_paths: list[Path],
    experiment: Path,
) -> Path:
    from .candidates import expand_results, result_frame

    result_paths = expand_results(result_paths)
    reference = result_frame(reference_path)
    frames = [read(path) for path in result_paths]
    if not frames:
        raise ValueError("Candidate facts need at least one candidate")
    goal = load_objective(reference["objective"])
    if (reference["objective_id"], reference["condition_id"]) != (
        goal["objective_id"],
        condition_id(goal),
    ):
        raise ValueError("Reference does not match its frozen objective")
    # Validate all comparison identities before publishing anything.
    for frame in frames:
        compare(reference, frame)
        if load_objective(frame["objective"])["objective_id"] != goal["objective_id"]:
            raise ValueError("Candidate constraints differ from the frozen objective")
    jobs = Jobs(deployment, reference["design_id"], experiment)
    rows = []
    for index, (frame, path) in enumerate(
        zip([reference, *frames], [reference_path, *result_paths], strict=True)
    ):
        folder = experiment / ("candidate-" + str(index))
        row = candidate_row(jobs, frame, path, folder)
        details = folder / "facts.json"
        write(details, row)
        row["detail_ref"] = file_ref(details)
        rows.append(row)
    document = {
        "schema_version": SCHEMA,
        "design_id": reference["design_id"],
        "objective_id": reference["objective_id"],
        "condition_id": reference["condition_id"],
        "reference_run_id": reference["run_id"],
        "conditions": goal["conditions"],
        "constraints": goal["constraints"],
        "reference": rows[0],
        "candidates": rows[1:],
        "interpretation": (
            "Native decisions and scores are original observations, not final PPA. "
            "Feasibility means the frozen physical constraints, not adoption or "
            "logic proof. Codex decides the business source and any tradeoff. "
            "Read this compact view first; expand original refs only as needed."
        ),
    }
    full = experiment / "candidate-facts.json"
    write(full, document)
    brief = experiment / "candidate-brief.json"
    write(brief, compact_view(document, full))
    captured = [brief, full, *sorted(experiment.glob("candidate-*/*.json"))]
    # Existing analysis artifacts make this view discoverable from the reference
    # scope. Original result paths and hashes remain intact; no EDA is launched.
    record = jobs.command(
        "register-facts",
        [
            deployment.value["client_python"],
            "-c",
            "print('SDK-verified candidate facts')",
        ],
        capture=captured,
        extra_paths=[
            "query-data/" + str(i) + "/" + path.name for i, path in enumerate(captured)
        ],
        analysis_parent=reference["run_id"],
        parent=reference["run_id"],
        objective=Path(reference["objective"]),
        seconds=300,
        cpu=1,
        memory_gib=2,
    )
    write(
        experiment / "facts-receipt.json",
        {
            "brief": file_ref(brief),
            "brief_bytes": brief.stat().st_size,
            "analysis_run_id": record["run"]["run_id"],
            "analysis_of_run_id": reference["run_id"],
            "candidate_count": len(frames),
            "eda_jobs_launched": 0,
        },
    )
    return brief
