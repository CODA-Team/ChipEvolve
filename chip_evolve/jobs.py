"""Public EF composition; agents do not manage EDA processes or artifact transport."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from openroad_platform_client import KernelClient

from .config import Deployment, read, write
from .lifecycle import pending, transient, wait_run

ROOT = Path(__file__).resolve().parents[1]


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def http(
    url: str, value: dict[str, Any] | None = None, *, timeout: float = 60
) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        json.dumps(value).encode() if value is not None else None,
        {"Content-Type": "application/json"},
    )
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(
        request, timeout=timeout
    ) as response:
        return json.load(response)


class Jobs:
    def __init__(self, deployment: Deployment, design_id: str, experiment: Path):
        self.deployment, self.design_id, self.experiment = (
            deployment,
            design_id,
            experiment,
        )
        self.campaign = design_id + "-" + experiment.name
        try:
            relative = experiment.relative_to(
                deployment.state / "experiments" / design_id
            )
        except ValueError:
            relative = Path(experiment.name)
        if len(relative.parts) > 1:
            # Independent validation children must not collide with another
            # validation's equally named logic/replay child.
            self.campaign += (
                "-" + hashlib.sha256(str(relative).encode()).hexdigest()[:12]
            )
        self.client = KernelClient(deployment.value["kernel_url"], timeout=60)

    def cancel_active(self) -> dict[str, Any]:
        """Retire this experiment's EF work after its frontend has stopped."""
        scopes: list[tuple[str, str, str | None]] = [
            (self.design_id, self.campaign, None)
        ]
        journal = self.experiment / "platform-state/campaign.json"
        if journal.exists():
            native = read(journal)
            design = self.deployment.design(self.design_id)
            if (native["platform"], native["design"]) != (
                design["platform"],
                design["nickname"],
            ):
                raise RuntimeError("Native Flow campaign belongs to another design")
            scopes.append((native["design"], native["campaign_id"], "a2-flow"))
        rows = {}
        for design_id in dict.fromkeys(scope[0] for scope in scopes):
            for status in (
                "queued",
                "preparing",
                "running",
                "retry_wait",
                "cancel_requested",
            ):
                offset = 0
                while batch := self.client.runs(
                    design_id=design_id, status=status, limit=100, offset=offset
                ):
                    rows.update(
                        {
                            row["run_id"]: row
                            for row in batch
                            if any(
                                row.get("experiment_id") == campaign
                                and (
                                    project is None or row.get("project_id") == project
                                )
                                for scoped_design, campaign, project in scopes
                                if scoped_design == design_id
                            )
                        }
                    )
                    offset += len(batch)
        # Gather before cancellation: changing a status while paging would skip rows.
        cancelled = []
        for row in rows.values():
            response = self.client.cancel(row["run_id"])
            cancelled.append({"run_id": row["run_id"], "response": response})
        receipt = {
            "experiment_id": self.campaign,
            "experiment_scopes": [
                {"design_id": d, "experiment_id": c, "project_id": p}
                for d, c, p in scopes
            ],
            "cancel_requests": cancelled,
            "note": "Cancellation requests; EF owns process cleanup and terminal state.",
        }
        write(self.experiment / "native-job-cancellation.json", receipt)
        return receipt

    def submit(
        self,
        key: str,
        inputs: dict[str, Any],
        staged: list[dict[str, Any]],
        *,
        seconds: int = 1800,
        cpu: int = 8,
        memory_gib: int = 24,
        parent: str | None = None,
        objective: Path | None = None,
        context: Path | None = None,
        analysis_parent: str | None = None,
    ) -> dict[str, Any]:
        folder = self.experiment / "jobs" / key
        folder.mkdir(parents=True, exist_ok=True)
        task = {
            "schema_version": 3,
            "task_id": self.campaign + "-" + key,
            "project_id": "chip-evolve-local",
            "design_id": self.design_id,
            "experiment_id": self.campaign,
            "plugin_id": "openroad-data",
            "inputs": inputs,
            "staged_inputs": staged,
            "labels": {
                "memory_approval": "manual",
                **({"parent_run_id": parent} if parent else {}),
                **(
                    {"run_type": "analysis", "analysis_of_run_id": analysis_parent}
                    if analysis_parent
                    else {}
                ),
            },
            "timeout_seconds": seconds,
            "max_attempts": 1,
            "resources": {
                "cpu_cores": cpu,
                "memory_bytes": memory_gib << 30,
                "processes": 2048,
            },
        }
        if objective:
            from eda_toolkits.objectives import bind_task_objective

            bind_task_objective(task, objective)
        if context:
            from eda_toolkits.context import bind_task_context

            bind_task_context(task, context)
        saved = folder / "task.json"
        if saved.exists() and read(saved) != task:
            raise ValueError("A saved business job cannot silently change inputs")
        identity = {row["source"]: digest(Path(row["source"])) for row in staged}
        hashes = folder / "staged-hashes.json"
        if hashes.exists() and read(hashes) != identity:
            raise ValueError("A saved business job cannot change staged content")
        write(hashes, identity)
        write(saved, task)
        submission = folder / "submission.json"
        if submission.exists():
            submitted = read(submission)
        else:
            try:
                submitted = self.client.submit(
                    task, idempotent=True, idempotency_key=self.campaign + ":" + key
                )
            except Exception as error:
                if not transient(error):
                    raise
                raise pending(
                    folder / "lifecycle.json",
                    phase="submission",
                    reason="submission_response_unknown",
                    task_id=task["task_id"],
                    idempotency_key=self.campaign + ":" + key,
                    detail=str(error),
                ) from error
            write(submission, submitted)
        run_id = submitted["run"]["run_id"]
        result = wait_run(
            self.client, run_id, folder, self.deployment.value.get("lifecycle", {})
        )
        write(folder / "execution.json", result)
        if result["run"]["status"] != "succeeded":
            raise RuntimeError("EDA job failed; evidence retained: " + run_id)
        return result

    def materialize(
        self,
        record: dict[str, Any],
        kind: str,
        destination: Path,
        *,
        suffix: str | None = None,
    ) -> dict[str, Any]:
        candidates = [
            a
            for a in record["artifacts"]
            if a["kind"] == kind and (suffix is None or a["store_key"].endswith(suffix))
        ]
        if len(candidates) != 1:
            raise ValueError(
                "Select one actual producer artifact: " + str((kind, suffix))
            )
        artifact = candidates[0]
        destination.parent.mkdir(parents=True, exist_ok=True)
        self.client.materialize_artifact(
            record["run"]["run_id"], artifact["artifact_id"], str(destination)
        )
        return artifact

    def command(
        self,
        key: str,
        command: list[str],
        *,
        capture: list[Path] | None = None,
        cwd: Path | None = None,
        seconds: int = 1800,
        memory_gib: int = 24,
        cpu: int = 8,
        parent: str | None = None,
        objective: Path | None = None,
        environment: dict[str, str] | None = None,
        analysis_parent: str | None = None,
        extra_paths: list[str] | None = None,
    ) -> dict[str, Any]:
        request = self.experiment / "requests" / (key + ".json")
        value = {
            "command": command,
            "cwd": str(cwd or self.experiment),
            "capture": [str(p.resolve()) for p in capture or []],
            "environment": environment or {},
        }
        if request.exists() and read(request) != value:
            raise ValueError("A saved command cannot change on recovery")
        write(request, value)
        return self.submit(
            key,
            {
                "adapter": "command",
                "extractor_command": [
                    self.deployment.value["client_python"],
                    str(ROOT / "chip-evolve.py"),
                    "leaf",
                    "--request",
                    "inputs/request.json",
                ],
                **({"native_extra_paths": extra_paths} if extra_paths else {}),
            },
            [{"source": str(request), "destination": "inputs/request.json"}],
            seconds=seconds,
            cpu=cpu,
            memory_gib=memory_gib,
            parent=parent,
            objective=objective,
            analysis_parent=analysis_parent,
        )

    def log(self, record: dict[str, Any], destination: Path) -> str:
        self.materialize(record, "extractor_log", destination)
        return destination.read_text()


def leaf(request_path: Path) -> int:
    request = read(request_path)
    output = Path.cwd() / "query-data"
    output.mkdir()
    environment = {
        key: value
        for key, value in os.environ.items()
        if key in {"PATH", "HOME", "USER", "LANG", "LC_ALL", "TMPDIR"}
    }
    environment.update(
        PYTHONNOUSERSITE="1",
        NO_PROXY="127.0.0.1,localhost",
        no_proxy="127.0.0.1,localhost",
    )
    environment.update(request.get("environment", {}))
    with (
        (output / "stdout.log").open("w") as log,
        subprocess.Popen(
            request["command"],
            cwd=request["cwd"],
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        ) as process,
    ):
        assert process.stdout is not None
        for line in process.stdout:
            log.write(line)
            log.flush()
            print(line, end="", flush=True)
        code = process.wait()
    files = {}
    missing = []
    for number, name in enumerate(request["capture"]):
        source = Path(name)
        if code and not source.exists():
            missing.append(name)
            continue
        target = output / str(number) / source.name
        target.parent.mkdir()
        shutil.copyfile(source, target)
        files[name] = digest(target)
    write(
        output / "manifest.json",
        {
            "evidence_only": True,
            "request": request,
            "returncode": code,
            "output_files": files,
            **({"missing_output_files": missing} if missing else {}),
        },
    )
    return code
