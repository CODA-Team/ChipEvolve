"""Recover deterministic delivery after an original professional has finished."""

from __future__ import annotations

import time
import urllib.error
import urllib.parse
from http.client import HTTPException
from pathlib import Path
from typing import Any

from .config import Deployment, read, write
from .jobs import Jobs, digest, http
from .lifecycle import pending


def import_snapshot(
    jobs: Jobs, producer: str, artifact: str, snapshot: str, subject: str
) -> dict[str, Any]:
    """Resolve one durable DF receipt after an uncertain response; no EDA retry."""
    base = jobs.deployment.value["data_url"]
    policy = jobs.deployment.value.get("lifecycle", {})
    path = jobs.experiment / "imports" / (artifact + ".json")
    identity = {
        "producer_run_id": producer,
        "artifact_id": artifact,
        "snapshot_id": snapshot,
        "subject_run_id": subject,
        "design_id": jobs.design_id,
    }
    if path.exists() and read(path)["identity"] != identity:
        raise ValueError("Saved import identity changed")
    read_timeout = float(policy.get("data_read_seconds", 15))

    def payload(value):
        return value.get("data", value)

    def receipt():
        try:
            value = payload(
                http(
                    base + "/imports/" + urllib.parse.quote(artifact, safe=""),
                    timeout=read_timeout,
                )
            )["import_receipt"]
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return None
            raise
        if value["artifact_id"] != artifact or value["run_id"] != producer:
            raise ValueError("DF import receipt belongs to another producer/artifact")
        if value["status"] == "failed":
            write(
                path,
                {
                    "phase": "delivery",
                    "status": "failed",
                    "identity": identity,
                    "import_receipt": value,
                },
            )
            raise RuntimeError(
                "DF import failed; evidence retained: " + str(value.get("error"))
            )
        if value["status"] != "imported" or value["snapshot_id"] != snapshot:
            raise ValueError("DF import receipt has an unexpected outcome/snapshot")
        return value

    def complete(value):
        data = payload(
            http(
                base + "/snapshots/" + urllib.parse.quote(snapshot, safe=""),
                timeout=read_timeout,
            )
        )
        actual = data["snapshot"]
        if (
            actual["snapshot_id"] != snapshot
            or actual["run_id"] != subject
            or actual["design_id"] != jobs.design_id
        ):
            raise ValueError("Imported snapshot differs from the measured design/run")
        result = {
            "snapshot": actual,
            "record_counts": actual.get("record_counts", {}),
            "import_receipt": value,
        }
        write(
            path,
            {
                "phase": "delivery",
                "status": "completed",
                "identity": identity,
                "import_receipt": value,
            },
        )
        return result

    def temporary(error):
        if isinstance(error, urllib.error.HTTPError):
            return error.code >= 500
        return isinstance(error, (OSError, HTTPException))

    requested = False

    def request():
        nonlocal requested
        write(
            path, {"phase": "delivery", "status": "request_sent", "identity": identity}
        )
        requested = True
        http(
            base + "/snapshots/from-run",
            {"run_id": producer, "artifact_id": artifact},
            timeout=float(policy.get("import_request_seconds", 900)),
        )

    detail = ""
    try:
        prior = receipt()
        if prior is not None:
            return complete(prior)
        request()
        value = receipt()
        if value is not None:
            return complete(value)
        detail = "Import response returned without a durable receipt"
    except Exception as error:
        if not temporary(error):
            write(
                path,
                {
                    "phase": "delivery",
                    "status": "failed",
                    "identity": identity,
                    "error_type": type(error).__name__,
                    "detail": str(error),
                },
            )
            raise
        detail = str(error)
    deadline = time.monotonic() + float(policy.get("import_reconcile_seconds", 120))
    while True:
        write(
            path,
            {
                "phase": "delivery",
                "status": "reconciling",
                "identity": identity,
                "detail": detail,
            },
        )
        try:
            value = receipt()
            if value is None and not requested:
                request()
                value = receipt()
            if value is not None:
                return complete(value)
        except Exception as error:
            if not temporary(error):
                write(
                    path,
                    {
                        "phase": "delivery",
                        "status": "failed",
                        "identity": identity,
                        "error_type": type(error).__name__,
                        "detail": str(error),
                    },
                )
                raise
            detail = str(error)
        if time.monotonic() >= deadline:
            raise pending(
                path,
                phase="delivery",
                reason="import_outcome_unknown",
                experiment=str(jobs.experiment),
                identity=identity,
                run_id=producer,
                artifact_id=artifact,
                detail=detail,
            )
        time.sleep(float(policy.get("poll_seconds", 1)))


def checkpoint(
    experiment: Path,
    *,
    design_id: str,
    odb: Path,
    producer: str,
    objective: Path,
    native_method: dict[str, Any],
    pdk: Path | None = None,
    source: Path | None = None,
) -> None:
    inputs = [odb, objective]
    if pdk:
        inputs += [pdk / "setRC.tcl", pdk / "rcx_patterns.rules"]
    if source:
        inputs.append(source)
    value = {
        "design_id": design_id,
        "kind": "layout" if source else "qualify",
        "odb": str(odb.resolve()),
        "producer": producer,
        "objective": str(objective.resolve()),
        "pdk": str(pdk.resolve()) if pdk else None,
        "source": str(source.resolve()) if source else None,
        "input_hashes": {str(p.resolve()): digest(p) for p in inputs},
        "native_method": native_method,
    }
    path = experiment / "delivery-checkpoint.json"
    if path.exists() and read(path) != value:
        raise ValueError("A completed professional delivery checkpoint cannot change")
    write(path, value)


def layout_source(
    deployment: Deployment, experiment: Path, source_path: Path
) -> dict[str, Any]:
    """New ORFS handoffs retain submitted scripts and defaults; old jobs stay bound."""
    frame = read(source_path)
    if frame.get("flow_recipe") or not frame.get("native_inputs"):
        return frame
    recipe_path = experiment / "recipe.json"
    preparing = experiment / "jobs/prepare-recipe/task.json"
    if (experiment / "source").exists() and not (
        recipe_path.exists() or preparing.exists()
    ):
        return frame
    if not recipe_path.exists():
        from .flow_recipe import prepare_flow_recipe

        prepare_flow_recipe(deployment, source_path, experiment)
    recipe = read(recipe_path)
    if (
        recipe["source_run_id"] != frame["run_id"]
        or recipe["result_sha256"] != digest(source_path)
        or recipe["design_id"] != frame["design_id"]
    ):
        raise ValueError("Prepared physical recipe belongs to another source")
    frame.update(
        flow_recipe=str(recipe_path),
        native_config=recipe["config_path"],
        native_flow_dir=str(Path(recipe["source"]) / "flow"),
    )
    return frame


def finish(deployment: Deployment, experiment: Path) -> dict[str, Any]:
    from .physical import qualify
    from .professional import resume_layout

    prior_result, prior_status = experiment / "result.json", experiment / "status.json"
    completed_legacy_result = (
        prior_result.is_file()
        and prior_status.is_file()
        and read(prior_status).get("status") == "succeeded"
        and "native_candidate_evidence" not in read(prior_result)
    )
    saved = read(experiment / "delivery-checkpoint.json")
    for name, sha in saved["input_hashes"].items():
        if digest(Path(name)) != sha:
            raise ValueError("Delivery input changed: " + name)
    jobs = Jobs(deployment, saved["design_id"], experiment)
    odb, objective = Path(saved["odb"]), Path(saved["objective"])
    modes: dict[str, Any] = (
        {"fact_modes": ("orfs", "opensta")}
        if saved["native_method"].get("kind") == "native-candidate"
        else {}
    )
    if saved["kind"] == "layout":
        result = resume_layout(
            jobs,
            odb,
            layout_source(deployment, experiment, Path(saved["source"])),
            objective,
            saved["producer"],
            **modes,
        )
    else:
        native = saved["native_method"]
        if (
            native.get("physical_stage") == "detailed_route"
            and native.get("route_drc") == 0
        ):
            modes["preserve_routing"] = True
            modes["native_route_drc"] = saved["native_method"].get("route_drc")
        result = qualify(
            jobs, odb, saved["producer"], objective, Path(saved["pdk"]), **modes
        )
    result["native_method"] = saved["native_method"]
    from .code_evidence import maybe_collect

    if not completed_legacy_result:
        maybe_collect(deployment, experiment, result, saved)
    write(experiment / "result.json", result)
    return result


def recover(deployment: Deployment, design_id: str, key: str) -> dict[str, Any]:
    """Reuse successful EDA tasks; never restart unfinished model searches."""
    from .physical import baseline
    from .professional import collect_flow

    experiment = deployment.state / "experiments" / design_id / key
    request = read(experiment / "request.json")
    if request["design"] != design_id:
        raise ValueError("Recovery request belongs to another design")
    status = experiment / "status.json"
    if status.exists():
        prior = read(status)
        completed = experiment / "result.json"
        if prior.get("status") == "succeeded" and completed.is_file():
            checkpoint_path = experiment / "delivery-checkpoint.json"
            if checkpoint_path.is_file():
                for name, sha in read(checkpoint_path)["input_hashes"].items():
                    if digest(Path(name)) != sha:
                        raise ValueError("Delivery input changed: " + name)
            result = read(completed)
            if result.get("design_id") != design_id:
                raise ValueError("Completed result belongs to another design")
            if (
                request.get("objective")
                and result.get("objective_id")
                != read(request["objective"])["objective_id"]
            ):
                raise ValueError(
                    "Completed result differs from original requested objective"
                )
            return result
        history = experiment / "status-before-recovery.json"
        if not history.exists():
            write(history, prior)
    if (experiment / "delivery-checkpoint.json").exists():
        result = finish(deployment, experiment)
    elif request["capability"] == "orfs":
        result = baseline(
            deployment,
            design_id,
            experiment,
            request["seconds"],
            objective=Path(request["objective"]) if request.get("objective") else None,
        )
    elif request["capability"] == "flow":
        objective = Path(read(experiment / "input-receipt.json")["objective"])
        result = collect_flow(deployment, design_id, experiment, objective)
    else:
        raise ValueError(
            "Native professional has no completed delivery checkpoint; "
            "preserve its session instead of rerunning the search"
        )
    write(status, {"status": "succeeded", "delivery_recovered": True})
    write(
        experiment / "delivery-recovery.json",
        {
            "status": "succeeded",
            "result": str(experiment / "result.json"),
            "run_id": result.get("run_id"),
            "candidate_results": result.get("candidate_results", []),
            "native_search_restarted": False,
        },
    )
    return result
