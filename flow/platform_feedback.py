"""Publish actual CP0 evaluation metadata through existing Toolkits/DF APIs."""

import datetime
import hashlib
import json
import time
import urllib.request
from pathlib import Path

from openroad_platform_contracts import InputFile, ResourceRequest, TaskSpec

from platform_execution import TERMINAL, write_record


def request(base, path, payload=None):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    message = urllib.request.Request(
        base + path,
        data=None if payload is None else json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with opener.open(message, timeout=120) as response:
        return json.load(response)


def publish_feedback(
    client,
    state,
    data_url,
    evaluation,
    timeout_seconds=180,
    *,
    wait_timeout_seconds=None,
):
    """A saved request plus public idempotency also covers a lost export reply."""
    state = Path(state)
    path = (
        state
        / f"iteration-{evaluation['iteration']}"
        / (f"slot-{evaluation['candidate_slot']}-{evaluation['stage']}-feedback.json")
    )
    source = next(
        row
        for row in evaluation["artifacts"]
        if row["store_key"] == "a2-evaluation.json"
    )
    key = evaluation["idempotency_key"] + ":feedback"
    snapshot_id = "a2-cp0-" + hashlib.sha256(key.encode()).hexdigest()[:24]
    identity = {
        "campaign_id": evaluation["campaign_id"],
        "evaluation_run_id": evaluation["run_id"],
        "physical_run_id": evaluation["parent_run_id"],
        "metadata": source,
        "snapshot_id": snapshot_id,
        "data_url": data_url,
    }
    if path.exists():
        record = json.loads(path.read_text())
        if any(record[name] != value for name, value in identity.items()):
            raise ValueError("Saved feedback identity or evaluation metadata changed.")
    else:
        labels = {
            **evaluation["task"]["labels"],
            "analysis_of_run_id": evaluation["parent_run_id"],
            "run_type": "analysis",
            "stage": evaluation["stage"] + "_feedback",
        }
        task = TaskSpec(
            task_id=f"a2-feedback-{evaluation['iteration']}-{evaluation['candidate_slot']}-{evaluation['stage']}",
            project_id="a2-flow",
            design_id=evaluation["design"],
            experiment_id=evaluation["campaign_id"],
            plugin_id="openroad-data",
            inputs={
                "adapter": "orfs",
                "metadata_path": "inputs/a2-evaluation.json",
                "snapshot_id": snapshot_id,
                "design_id": evaluation["design"],
                "revision_id": evaluation["candidate_id"],
                "run_id": evaluation["parent_run_id"],
                "stage": evaluation["stage"],
                "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            },
            labels=labels,
            staged_inputs=(
                InputFile(
                    artifact_id=source["artifact_id"],
                    destination="inputs/a2-evaluation.json",
                ),
            ),
            timeout_seconds=timeout_seconds,
            resources=ResourceRequest(cpu_cores=1, memory_bytes=512 << 20, processes=8),
        )
        record = {
            **identity,
            "task": task.to_dict(),
            "idempotency_key": key,
            "status": "prepared",
        }
        write_record(path, record)
    run = (
        client.run(record["producer_run_id"])
        if "producer_run_id" in record
        else client.submit(record["task"], idempotency_key=record["idempotency_key"])[
            "run"
        ]
    )
    record.update(producer_run_id=run["run_id"], status=run["status"])
    write_record(path, record)
    deadline = time.monotonic() + (
        timeout_seconds if wait_timeout_seconds is None else wait_timeout_seconds
    )
    running_deadline = None
    while run["status"] not in TERMINAL:
        current = time.monotonic()
        if run["status"] == "running" and running_deadline is None:
            running_deadline = current + timeout_seconds
        if current > deadline or (
            running_deadline is not None and current > running_deadline
        ):
            client.cancel(run["run_id"])
            raise TimeoutError("Feedback snapshot export exceeded its budget.")
        time.sleep(0.2)
        run = client.run(run["run_id"])
    record.update(status=run["status"], artifacts=client.artifacts(run["run_id"]))
    write_record(path, record)
    if run["status"] != "succeeded":
        raise RuntimeError("Actual evaluation metadata export failed.")
    copied = next(
        row
        for row in record["artifacts"]
        if row["store_key"] == "inputs/a2-evaluation.json"
    )
    if copied["sha256"] != source["sha256"]:
        raise ValueError("Feedback did not retain the actual evaluation bytes.")
    bundle = next(row for row in record["artifacts"] if row["kind"] == "data_snapshot")
    record["import_request"] = {
        "run_id": run["run_id"],
        "artifact_id": bundle["artifact_id"],
    }
    write_record(path, record)
    record["import_response"] = request(
        data_url, "/snapshots/from-run", record["import_request"]
    )
    write_record(path, record)
    imported = request(data_url, "/imports/" + bundle["artifact_id"])["data"][
        "import_receipt"
    ]
    summary = request(data_url, "/snapshots/" + snapshot_id + "/summary?detail=full")[
        "data"
    ]
    if (
        imported["status"] != "imported"
        or imported["attempts"] != 1
        or summary["snapshot"]["run_id"] != evaluation["parent_run_id"]
        or summary["snapshot"]["producer_run_id"] != run["run_id"]
    ):
        raise ValueError("Feedback import lacks its exact physical/analysis lineage.")
    record.update(import_receipt=imported, summary=summary, imported=True)
    write_record(path, record)
    return record
