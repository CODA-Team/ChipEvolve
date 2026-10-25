"""Finite, resumable result checks; Codex still decides adoption."""

from __future__ import annotations

import json
import re
import shutil
import time
from pathlib import Path
from typing import Any

from eda_ai_client import EdaAiClient

from .comparisons import METRICS, compare
from .config import Deployment, business_lock, read, write
from .delivery import checkpoint, finish
from .jobs import Jobs, digest
from .lifecycle import WorkPending
from .logic import verify_outputs


def query_facts(deployment: Deployment, frame: dict[str, Any]) -> dict[str, Any]:
    client = EdaAiClient(
        data_url=deployment.value["data_url"], kernel_url=deployment.value["kernel_url"]
    )
    scopes = {}
    for mode, snapshot in frame["snapshot_ids"].items():
        scope = client.resolve_scope(snapshot_id=snapshot, origin="all")["scope"]
        if (scope["design_id"], scope["run_id"]) != (
            frame["design_id"],
            frame["run_id"],
        ):
            raise ValueError("Snapshot identity differs from the measured result")
        scopes[mode] = scope
    metrics = client.get_metrics(
        snapshot_id=frame["snapshot_ids"]["orfs"], include_raw=True
    )
    rows = {row["raw_key"]: row["raw_value"] for row in metrics["data"]["metrics"]}
    rows.update(
        {row["raw_key"]: row["value"] for row in metrics["data"]["raw_metrics"]}
    )
    if any(key not in rows or rows[key] != frame["metrics"][key] for key in METRICS):
        raise ValueError("DF metrics differ from the measured result")
    return {"scopes": scopes, "metrics": metrics}


def replay_checkpoint(result_path: Path) -> dict[str, Any]:
    """Read a current delivery checkpoint or the exact recorded legacy route input."""
    experiment, frame = result_path.parent, read(result_path)
    saved = experiment / "delivery-checkpoint.json"
    if saved.exists():
        value = read(saved)
        for name, sha in value["input_hashes"].items():
            if digest(Path(name)) != sha:
                raise ValueError("Replay input changed: " + name)
        return value
    request = experiment / "requests/qualification.json"
    if not request.exists():
        raise ValueError("Full routing replay needs a recorded professional checkpoint")
    original = read(request)
    odb = Path(original["capture"][0])
    if digest(odb) != frame["qualification"]["input_odb_sha256"]:
        raise ValueError("Recorded routing checkpoint differs from measured input")
    sources = re.findall(
        r"^source \{([^}]+)\}$", Path(original["command"][-1]).read_text(), re.MULTILINE
    )
    if len(sources) != 1 or Path(sources[0]).name != "setRC.tcl":
        raise ValueError("Cannot identify the recorded PDK routing model")
    return {
        "design_id": frame["design_id"],
        "kind": "qualify",
        "odb": str(odb),
        "pdk": str(Path(sources[0]).parent),
        "source": None,
        "objective": frame["objective"],
        "producer": frame["qualification"]["producer_run_id"],
        "native_method": frame.get("native_method", {}),
    }


def completed_proof(
    deployment: Deployment, reference: Path, candidate: Path, folder: Path
) -> dict[str, Any]:
    """Resume delivery after a completed proof, keeping its producer and inputs."""
    saved = folder / "logical-equivalence.json"
    if not saved.exists():
        return verify_outputs(deployment, reference, candidate, folder)
    proof = read(saved)
    if (proof["reference_result"], proof["candidate_result"]) != (
        str(reference),
        str(candidate),
    ):
        raise ValueError("Completed proof belongs to a different result pair")
    libraries = deployment.design(read(candidate)["design_id"])["libraries"]
    sources = {
        str(Path(read(path)["files"]["v"])) for path in (reference, candidate)
    } | {row["path"] for row in libraries}
    if not sources <= proof["input_hashes"].keys():
        raise ValueError("Completed proof lacks frozen netlist or Liberty inputs")
    if any(proof["input_hashes"][row["path"]] != row["sha256"] for row in libraries):
        raise ValueError("Completed proof used different declared Liberty models")
    for name, sha in proof["input_hashes"].items():
        if digest(Path(name)) != sha:
            raise ValueError("Completed proof input changed: " + name)
    if (
        proof["proven_points"] <= 0
        or proof["unproven_points"] != 0
        or proof["proven_points"] != proof["top_output_bits"]
    ):
        raise ValueError("Completed proof does not cover all output obligations")
    if proof["engine"] == "eqy":
        from .eqy import qualified_strategy

        qualified_strategy({"equivalence_strategy": proof.get("strategy", "sat")})
    jobs = Jobs(deployment, read(candidate)["design_id"], folder)
    if jobs.client.run(proof["run_id"])["status"] != "succeeded":
        raise ValueError("Completed proof has no successful EF evidence producer")
    return proof


def replay(
    deployment: Deployment, result_path: Path, experiment: Path
) -> dict[str, Any]:
    request = result_path.parent / "request.json"
    if (
        request.exists()
        and read(request)["capability"] == "orfs"
        # A registered delivery checkpoint defines the physical boundary,
        # independently of the professional's descriptive method label.
        and not (result_path.parent / "delivery-checkpoint.json").is_file()
        and read(result_path).get("native_method", {}).get("kind")
        != "native-ORFS-physical-repair"
    ):
        from .physical import baseline

        frame = read(result_path)
        experiment.mkdir(parents=True, exist_ok=True)
        return baseline(
            deployment,
            frame["design_id"],
            experiment,
            read(request)["seconds"],
            objective=Path(frame["objective"]),
        )
    if not (result_path.parent / "delivery-checkpoint.json").exists():
        frame = read(result_path)
        if frame.get("candidate_id") and frame.get("flow_recipe"):
            from .flow_replay import replay as replay_flow

            return replay_flow(deployment, result_path, experiment)
    saved = replay_checkpoint(result_path)
    inputs = experiment / "inputs"
    inputs.mkdir(parents=True, exist_ok=True)
    odb = inputs / "checkpoint.odb"
    shutil.copyfile(saved["odb"], odb)
    pdk = None
    if saved["pdk"]:
        pdk = inputs / "pdk"
        pdk.mkdir(exist_ok=True)
        for name in ("setRC.tcl", "rcx_patterns.rules"):
            shutil.copyfile(Path(saved["pdk"]) / name, pdk / name)
    checkpoint(
        experiment,
        design_id=saved["design_id"],
        odb=odb,
        producer=saved["producer"],
        objective=Path(saved["objective"]),
        pdk=pdk,
        source=Path(saved["source"]) if saved["source"] else None,
        native_method={
            "kind": "independent-routing-replay",
            "original_result": str(result_path),
            # Keep the input's physical boundary: an already routed result
            # needs independent extraction/measurement, not a fresh route.
            **{
                key: saved["native_method"][key]
                for key in ("physical_stage", "route_drc", "route_drc_evidence")
                if key in saved.get("native_method", {})
            },
        },
    )
    return finish(deployment, experiment)


def validate(
    deployment: Deployment, result_path: Path, reference_path: Path, key: str
) -> dict[str, Any]:
    from .candidates import result_frame

    frame = result_frame(result_path)
    request = {
        "result": str(result_path),
        "reference": str(reference_path),
        "result_sha256": digest(result_path),
        "reference_sha256": digest(reference_path),
    }
    experiment = deployment.state / "experiments" / frame["design_id"] / key
    if not experiment.exists():
        experiment = deployment.experiment(frame["design_id"], key)
        write(experiment / "validation-request.json", request)
    elif read(experiment / "validation-request.json") != request:
        raise ValueError("Validation resume cannot change its frozen results")
    with business_lock(experiment):
        status = experiment / "status.json"
        if status.exists():
            with (experiment / "validation-status-history.jsonl").open("a") as history:
                history.write(
                    json.dumps({"replaced_at": time.time(), "previous": read(status)})
                    + "\n"
                )
        write(status, {"status": "running", "kind": "validation"})
        try:
            return _validate(
                deployment, result_path, reference_path, experiment, frame, request
            )
        except WorkPending as error:
            receipt = {
                **error.receipt,
                "experiment": str(experiment),
                "upstream_experiment": error.receipt.get("experiment"),
                "kind": "validation",
            }
            write(status, receipt)
            raise WorkPending(receipt) from error
        except Exception as error:
            write(
                experiment / "status.json",
                {
                    "status": "failed",
                    "kind": "validation",
                    "error_type": type(error).__name__,
                    "detail": str(error),
                },
            )
            raise


def _validate(
    deployment: Deployment,
    result_path: Path,
    reference_path: Path,
    experiment: Path,
    frame: dict[str, Any],
    request: dict[str, Any],
) -> dict[str, Any]:
    write(experiment / "comparison.json", compare(read(reference_path), frame))
    from .design_facts import ensure

    frame = ensure(deployment, result_path, frame)
    sdk = query_facts(deployment, frame)
    write(experiment / "sdk-query.json", sdk)
    proof = completed_proof(
        deployment, reference_path, result_path, experiment / "logic"
    )
    repeated = replay(deployment, result_path, experiment / "replay")
    delta = compare(frame, repeated)
    write(experiment / "replay-comparison.json", delta)
    exact = all(row["delta"] == 0 for row in delta["deltas"].values())
    replay_sdk = query_facts(deployment, repeated)
    write(experiment / "replay-sdk-query.json", replay_sdk)
    receipt = {
        **request,
        "logic": proof,
        "independent_replay": delta,
        "replay_result": str(experiment / "replay/result.json"),
        "replay_exact": exact,
        "sdk_identity_passed": True,
        "passed": exact and not delta["constraint_violations"],
        "adoption": "Codex decision required; validation never selects automatically",
    }
    write(experiment / "validation.json", receipt)
    write(
        experiment / "status.json",
        {
            "status": "succeeded" if receipt["passed"] else "failed",
            "kind": "validation",
        },
    )
    return receipt
