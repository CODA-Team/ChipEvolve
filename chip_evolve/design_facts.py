"""Publish, import and verify design facts through installed EF/DF clients."""

from __future__ import annotations

import time
import urllib.error
import urllib.parse
from concurrent.futures import Future
from http.client import HTTPException
from pathlib import Path
from threading import Thread
from typing import Any

from eda_ai_client import EdaAiClient, EdaAiError

from .artifact_inputs import registered_files
from .config import Deployment, read, write
from .jobs import Jobs, http
from .lifecycle import pending
from .metrics import METRICS
from .runtime import now


def ensure(
    deployment: Deployment, source: Path, frame: dict[str, Any]
) -> dict[str, Any]:
    deferred = frame.get("deferred_facts", {}).get("opendb")
    if deferred is None:
        return frame
    jobs = Jobs(deployment, frame["design_id"], Path(deferred["publication_root"]))
    registered_files(jobs, frame, tuple(frame["files"]))
    return publish(
        jobs,
        frame,
        result_path=source.parent / "materialized-result.json",
        modes=("opendb",),
    )


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
        nonlocal requested, detail
        write(
            path, {"phase": "delivery", "status": "request_sent", "identity": identity}
        )
        requested = True
        acknowledged: Future[Any] = Future()

        def post():
            try:
                acknowledged.set_result(
                    http(
                        base + "/snapshots/from-run",
                        {"run_id": producer, "artifact_id": artifact},
                        timeout=float(policy.get("import_request_seconds", 900)),
                    )
                )
            except Exception as error:  # noqa: BLE001 - Propagate HTTP errors unchanged.
                acknowledged.set_exception(error)

        # DF's commit can expose a durable receipt while SQLite is still
        # checkpointing before returning the POST response. Read that committed
        # state now; do not keep the caller idle until its socket timeout.
        # The thread owns only this bounded HTTP request, never local receipts.
        Thread(target=post, name="df-import-ack", daemon=True).start()
        while not acknowledged.done():
            try:
                value = receipt()
                if value is not None:
                    return value
            except Exception as error:
                if not temporary(error):
                    raise
                detail = str(error)
            try:
                acknowledged.result(timeout=float(policy.get("poll_seconds", 1)))
            except TimeoutError:
                pass
        acknowledged.result()
        return receipt()

    detail = ""
    try:
        prior = receipt()
        if prior is not None:
            return complete(prior)
        value = request()
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
                value = request()
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


def publish(
    jobs: Jobs,
    measured: dict[str, Any],
    *,
    result_path: Path | None = None,
    modes: tuple[str, ...] = ("opendb", "orfs", "opensta"),
) -> dict[str, Any]:
    snapshot_ids = dict(measured.get("snapshot_ids", {}))
    exports = dict(measured.get("exports", {}))
    deployment = jobs.deployment
    export_seconds = (
        deployment.design(jobs.design_id)
        .get("fact_execution", {})
        .get("timeout_seconds", 300)
    )
    memory_gib = (
        deployment.design(jobs.design_id).get("fact_execution", {}).get("memory_gib", 8)
    )
    for mode, field, source in (
        ("opendb", "odb_path", measured["files"]["odb"]),
        ("orfs", "metadata_path", measured["files"]["metrics"]),
        ("opensta", "odb_path", measured["files"]["odb"]),
    ):
        if mode not in modes:
            continue
        snapshot = "local-" + measured["run_id"] + "-" + mode
        files = {name: Path(value) for name, value in measured["files"].items()}
        inputs = {
            "adapter": mode,
            field: "inputs/" + Path(source).name,
            "snapshot_id": snapshot,
            "design_id": jobs.design_id,
            "revision_id": jobs.experiment.name,
            "run_id": measured["run_id"],
            "stage": "finish" if mode != "opensta" else "timing",
            "created_at": now(),
            "threads": 2,
            "openroad_bin": deployment.value["openroad_launcher"],
            "native_extra_paths": ["inputs/" + p.name for p in files.values()],
        }
        if mode == "opensta":
            inputs.update(
                analysis="post_route",
                corner=measured.get("conditions", {}).get("corner"),
                # OpenSTA report_checks JSON emits SI values, independently
                # of the Tcl display/metric time unit selected by the caller.
                unit="s",
                sdc_path="inputs/final.sdc",
                spef_path="inputs/" + files["spef"].name,
                liberty_paths=[
                    "inputs/lib/" + str(i) + "-" + Path(row["path"]).name
                    for i, row in enumerate(
                        deployment.design(jobs.design_id)["libraries"]
                    )
                ],
                include_hold=True,
            )
        staged = [
            {"source": str(p), "destination": "inputs/" + p.name}
            for p in files.values()
        ]
        if mode == "opensta":
            staged += [
                {"source": row["path"], "destination": inputs["liberty_paths"][i]}
                for i, row in enumerate(deployment.design(jobs.design_id)["libraries"])
            ]
        key = "publish-v3-" + measured["run_id"][-8:] + "-" + mode
        if export_seconds != 300:
            key += "-t" + str(export_seconds)
        if memory_gib != 8:
            key += "-m" + str(memory_gib)
        saved = jobs.experiment / "jobs" / key / "task.json"
        if saved.exists():
            prior = read(saved)["inputs"]
            inputs["created_at"] = prior["created_at"]
            if mode == "opensta":
                # Resume the original immutable export. Legacy context remains
                # unknown; a supplemental export needs its own task/snapshot.
                for name in ("analysis", "corner", "unit"):
                    if name not in prior:
                        inputs.pop(name, None)
        record = jobs.submit(
            key,
            inputs,
            staged,
            seconds=export_seconds,
            cpu=2,
            memory_gib=memory_gib,
            parent=measured["run_id"],
            analysis_parent=measured["run_id"],
            objective=Path(measured["objective"]),
        )
        artifact = next(a for a in record["artifacts"] if a["kind"] == "data_snapshot")
        imported = import_snapshot(
            jobs,
            record["run"]["run_id"],
            artifact["artifact_id"],
            snapshot,
            measured["run_id"],
        )
        snapshot_ids[mode], exports[mode] = (
            snapshot,
            {"execution": record, "import": imported},
        )
    data = EdaAiClient(
        data_url=deployment.value["data_url"], kernel_url=deployment.value["kernel_url"]
    )
    try:
        facts = data.get_metrics(snapshot_id=snapshot_ids["orfs"])
    except (EdaAiError, OSError, HTTPException) as error:
        if isinstance(error, EdaAiError):
            if error.status is not None:
                if error.status < 500:
                    raise
            elif not isinstance(error.__cause__, (OSError, HTTPException)):
                raise
        if isinstance(error, urllib.error.HTTPError) and error.code < 500:
            raise
        raise pending(
            jobs.experiment / "published-facts-lifecycle.json",
            phase="delivery",
            reason="published_facts_read_unavailable",
            experiment=str(jobs.experiment),
            run_id=measured["run_id"],
            snapshot_ids=snapshot_ids,
            detail=str(error),
        ) from error
    if facts["scope"]["design_id"] != jobs.design_id:
        raise ValueError("Returned facts belong to another design")
    frame = {
        **measured,
        "snapshot_ids": snapshot_ids,
        "exports": exports,
        "native_inputs": str(jobs.experiment / "native-inputs.json")
        if (jobs.experiment / "native-inputs.json").exists()
        else None,
    }
    if "opendb" not in snapshot_ids:
        frame["deferred_facts"] = {
            "opendb": {"publication_root": str(jobs.experiment.resolve())}
        }
    else:
        frame.pop("deferred_facts", None)
    destination = result_path or jobs.experiment / "result.json"
    write(destination, frame)
    write(destination.parent / "queried-facts.json", facts)
    lifecycle = jobs.experiment / "published-facts-lifecycle.json"
    if lifecycle.exists():
        write(
            lifecycle,
            {
                "phase": "delivery",
                "status": "completed",
                "run_id": measured["run_id"],
                "snapshot_ids": snapshot_ids,
            },
        )
    return frame


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
