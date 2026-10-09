"""A single permitted ECO candidate, followed by independent reloading/export."""

from __future__ import annotations

import fcntl
import hashlib
import json
import time
import urllib.request
from pathlib import Path
from typing import Any

from eda_ai_client import EdaAiClient
from eda_toolkits.eco import buffer_eco_task, eco_export_task
from eda_toolkits.inputs import SnapshotExecutionClient

from query_agent.domain.handoff import HandoffPackage


class EcoReceiver:
    def __init__(
        self, data: EdaAiClient, execution: SnapshotExecutionClient, output: Path
    ) -> None:
        self.data, self.execution, self.output = data, execution, output.resolve()

    def run(self, package: HandoffPackage, proposal: dict[str, Any]) -> dict[str, Any]:
        if package.role != "eco" or package.consumer_status != "ready":
            raise ValueError("requested role has no connected receiver")
        self.output.mkdir(parents=True, exist_ok=True)
        with (self.output / "receiver.lock").open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise RuntimeError("handoff receiver is already active") from exc
            identity = {
                "package_sha256": hashlib.sha256(
                    package.model_dump_json().encode()
                ).hexdigest(),
                "proposal": proposal,
            }
            accepted = self.output / "identity.json"
            if accepted.exists() and json.loads(accepted.read_text()) != identity:
                raise ValueError("handoff dispatch/proposal changed after acceptance")
            self.write("identity.json", identity)
            receipt = self.output / "receipt.json"
            if receipt.exists():
                return json.loads(receipt.read_text())
            try:
                return self._execute(package, proposal)
            except (OSError, ValueError, RuntimeError):
                outstanding = self.output / "outstanding.json"
                if outstanding.exists():
                    run_id = json.loads(outstanding.read_text())["run_id"]
                    self.execution.set_timeout(5)
                    try:
                        self.execution.cancel(run_id)
                    except (OSError, ValueError, RuntimeError) as exc:
                        self.write(
                            "cancel-error.json",
                            {"run_id": run_id, "error_type": type(exc).__name__},
                        )
                raise

    def _execute(
        self, package: HandoffPackage, proposal: dict[str, Any]
    ) -> dict[str, Any]:
        started = time.monotonic()
        deadline = started + package.budget.max_seconds
        self.execution.set_timeout(package.budget.max_seconds)
        self.data.timeout = min(30, package.budget.max_seconds)
        response = self.data.read_query(
            "/snapshots/" + package.scope.snapshot_id + "/summary",
            parameters={"detail": "full"},
        )
        snapshot = response["data"]["snapshot"]
        task = buffer_eco_task(snapshot, package.model_dump(mode="json"), proposal)
        self.write(
            "accepted.json",
            {
                "handoff_id": package.handoff_id,
                "proposal": proposal,
                "package_sha256": hashlib.sha256(
                    package.model_dump_json().encode()
                ).hexdigest(),
                "task": task,
            },
        )
        # One key for the entire handed-off experiment; a changed proposal cannot
        # obtain a second experiment by inventing another task ID.
        run = self.execution.submit(task, idempotency_key=package.handoff_id)["run"]
        self.write("outstanding.json", {"run_id": run["run_id"]})
        physical = self.wait(run["run_id"], deadline)
        (self.output / "outstanding.json").unlink()
        artifacts = self.execution.artifacts(run["run_id"])
        self.write(
            "physical.json",
            {
                "run": physical,
                "artifacts": artifacts,
                "logs": self.execution.logs(run["run_id"], max_bytes=65536),
                "resources": self.execution.resources(run["run_id"]),
            },
        )
        if physical["status"] != "succeeded":
            raise RuntimeError(
                "permitted ECO execution failed; original records retained"
            )
        export = eco_export_task(
            snapshot, package.model_dump(mode="json"), physical, artifacts
        )
        export["timeout_seconds"] = min(120, max(1, int(deadline - time.monotonic())))
        self.write("export-task.json", export)
        exported = self.execution.submit(
            export, idempotency_key=package.handoff_id + "-export"
        )["run"]
        self.write("outstanding.json", {"run_id": exported["run_id"]})
        result = self.wait(exported["run_id"], deadline)
        (self.output / "outstanding.json").unlink()
        export_artifacts = self.execution.artifacts(result["run_id"])
        self.write(
            "export.json",
            {
                "run": result,
                "artifacts": export_artifacts,
                "logs": self.execution.logs(result["run_id"], max_bytes=65536),
            },
        )
        if result["status"] != "succeeded":
            raise RuntimeError("ECO result export failed; no imported snapshot claimed")
        bundle = next(ref for ref in export_artifacts if ref["kind"] == "data_snapshot")
        request = urllib.request.Request(
            self.data.data_url + "/snapshots/from-run",
            data=json.dumps(
                {"run_id": result["run_id"], "artifact_id": bundle["artifact_id"]}
            ).encode(),
            headers={"Content-Type": "application/json"},
        )
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(
            request, timeout=max(0.01, min(30, deadline - time.monotonic()))
        ) as response:
            imported = json.load(response)
        self.write("import.json", imported)
        receipt = {
            "handoff_id": package.handoff_id,
            "physical_run_id": physical["run_id"],
            "export_run_id": result["run_id"],
            "snapshot_id": export["inputs"]["snapshot_id"],
            "import": {
                "snapshot_id": imported["snapshot"]["snapshot_id"],
                "record_counts": imported["record_counts"],
            },
            "seconds": time.monotonic() - started,
            "status": "awaiting independent investigation review",
        }
        self.write("receipt.json", receipt)
        return receipt

    def wait(self, run_id: str, deadline: float) -> dict[str, Any]:
        while time.monotonic() < deadline:
            run = self.execution.run(run_id)
            if run["status"] in (
                "succeeded",
                "failed",
                "timed_out",
                "cancelled",
                "lost",
            ):
                return run
            time.sleep(min(0.2, max(0, deadline - time.monotonic())))
        self.execution.set_timeout(5)
        self.execution.cancel(run_id)
        raise TimeoutError("receiver budget exhausted; its EDA task was cancelled")

    def write(self, name: str, value: object) -> None:
        path = self.output / name
        text = json.dumps(value, indent=2) + "\n"
        if path.exists() and path.read_text() != text:
            old = path.read_bytes()
            (
                self.output / (hashlib.sha256(old).hexdigest()[:16] + "-" + name)
            ).write_bytes(old)
        path.write_text(text)
