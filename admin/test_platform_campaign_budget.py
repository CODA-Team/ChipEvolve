"""Exercise actual admission of the supervisor's dedicated resource allocation."""

import os
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest
from openroad_platform_client import KernelClient, KernelError
from openroad_platform_contracts import ResourceRequest, TaskSpec
from run_platform_campaign import WORKSPACE, gateway_command, port, wait_service


@pytest.mark.parametrize("large_task", [False, True])
def test_dedicated_budget_accepts_eight_cores_and_rejects_nine(
    tmp_path: Path, large_task
):
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    environment.update(PYTHONNOUSERSITE="1", NO_PROXY="127.0.0.1,localhost")
    plugins = tmp_path / "plugins"
    subprocess.run(
        [
            str(WORKSPACE / "toolkits/.venv/bin/python"),
            "-m",
            "eda_toolkits",
            "configure",
            "--output",
            str(plugins),
        ],
        env=environment,
        check=True,
        capture_output=True,
    )
    number = port()
    execution = {"capacity_memory_bytes": 32 << 30} if large_task else None
    command = gateway_command(tmp_path, plugins, number, execution) + ["--api-only"]
    # API-only exercises real validation without launching an EDA worker.
    with (tmp_path / "gateway.log").open("w") as log:
        process = subprocess.Popen(command, env=environment, stdout=log, stderr=log)
        try:
            wait_service(process, number)
            client = KernelClient(f"http://127.0.0.1:{number}", timeout=10)
            task = TaskSpec(
                task_id="budget-eight",
                project_id="p3-budget-check",
                design_id="aes",
                plugin_id="openroad-data",
                inputs={"adapter": "a2_stage", "stage": "place"},
                labels={"memory_approval": "manual"} if large_task else {},
                resources=ResourceRequest(
                    cpu_cores=8,
                    memory_bytes=(24 if large_task else 6) << 30,
                    processes=2048 if large_task else 256,
                ),
            )
            accepted = client.submit(task.to_dict())["run"]
            assert accepted["status"] == "queued"
            assert (
                client.cancel(accepted["run_id"])["run"]["status"] == "cancel_requested"
            )
            task = replace(
                task,
                task_id="budget-nine",
                resources=ResourceRequest(
                    cpu_cores=9, memory_bytes=6 << 30, processes=256
                ),
            )
            with pytest.raises(KernelError, match="cpu_cores exceed platform budget"):
                client.submit(task.to_dict())
            assert len(client.runs(project_id="p3-budget-check")) == 1
        finally:
            process.terminate()
            process.wait(timeout=30)
