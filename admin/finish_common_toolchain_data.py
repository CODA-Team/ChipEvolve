"""Complete U1 metric import and SDK checks from preserved successful EF runs."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path
from typing import Any

from qualify_common_toolchain import (
    ROOT,
    available_port,
    environment,
    http,
    metric_task,
    wait_run,
)
from run_dplevolve_native import digest, now, write_json
from run_goalevolve_native import stop_native_tree


def finish(
    state: Path, previous_receipt: Path | None = None, receipt: Path | None = None
) -> None:
    from openroad_platform_client import KernelClient

    original = state / "runtime.json"
    prior = json.loads((previous_receipt or original).read_text())
    for phase in ("build", "flow", "export", "check"):
        if prior["jobs"][phase]["run"]["status"] != "succeeded":
            raise ValueError("Data completion requires successful physical tasks")
    config = json.loads((state / "config.json").read_text())
    originals = state / "preparation/original-drivers"
    for name, sha in config["driver_files"].items():
        if digest(originals / name) != sha:
            raise ValueError("Original frozen driver is unavailable: " + name)
    receipt = receipt or state / (
        "unit-completion-runtime.json"
        if previous_receipt
        else "data-completion-runtime.json"
    )
    if receipt.exists():
        raise FileExistsError("Keep the previous data completion evidence")
    ports = [available_port(), available_port()]
    while ports[0] == ports[1]:
        ports[1] = available_port()
    urls = [f"http://127.0.0.1:{port}" for port in ports]
    commands = {k: list(v) for k, v in prior["service_commands"].items()}
    for name, port in zip(("execution", "data"), ports, strict=True):
        commands[name][commands[name].index("--port") + 1] = str(port)
    commands["data"][commands["data"].index("--kernel-url") + 1] = urls[0]
    runtime = {
        **prior,
        "status": "running",
        "started_at": now(),
        "kernel_url": urls[0],
        "data_url": urls[1],
        "service_commands": commands,
        "data_completion": {
            "original_runtime_sha256": digest(original),
            "original_driver_root": str(originals),
            "reason": "ORFS canonical metrics require the existing metadata adapter; physical/timing export has no observations.",
            "current_driver_sha256": {
                name: digest(ROOT / "admin" / name)
                for name in (
                    "qualify_common_toolchain.py",
                    "accept_common_toolchain.py",
                    "finish_common_toolchain_data.py",
                )
            },
        },
    }
    runtime.pop("error", None)
    write_json(receipt, runtime)
    env = environment()
    services: list[subprocess.Popen[bytes]] = []
    logs: list[Any] = []
    client = KernelClient(urls[0], timeout=60)
    active = None
    try:
        for name, url in zip(("execution", "data"), urls, strict=True):
            log = (state / (receipt.stem + "-" + name + ".log")).open("x")
            logs.append(log)
            process = subprocess.Popen(
                commands[name], env=env, stdout=log, stderr=log, start_new_session=True
            )
            services.append(process)
            deadline = time.monotonic() + 60
            endpoint = "/kernel/health" if name == "execution" else "/health"
            while True:
                try:
                    http(url + endpoint)
                    break
                except OSError:
                    if process.poll() is not None or time.monotonic() >= deadline:
                        raise RuntimeError(
                            "Data completion service failed to start: " + name
                        )
                    time.sleep(0.2)
        before = {run["run_id"] for run in client.runs(limit=100)}
        for phase in ("build", "flow", "export", "check"):
            known = runtime["jobs"][phase]["run"]
            actual = client.run(known["run_id"])
            if actual != known:
                raise ValueError("Preserved physical run changed: " + phase)
        profiles = [("units_export", "-units", "2_1_floorplan.json", "floorplan")]
        if not previous_receipt:
            profiles.append(("metrics_export", "-metrics", "6_report.json", "finish"))
        new_runs = set()
        for phase, suffix, report_name, stage in profiles:
            snapshot_id = state.name + suffix
            submitted = client.submit(
                metric_task(
                    runtime["jobs"]["flow"],
                    snapshot_id,
                    report_name=report_name,
                    stage=stage,
                )
            )
            active = submitted["run"]["run_id"]
            new_runs.add(active)
            runtime["jobs"][phase] = {"submission": submitted}
            write_json(receipt, runtime)
            run = wait_run(client, active, time.monotonic() + 120)
            artifacts = client.artifacts(active)
            runtime["jobs"][phase].update(
                run=run, artifacts=artifacts, resources=client.resources(active)
            )
            active = None
            artifact = next(a for a in artifacts if a["kind"] == "data_snapshot")
            imported = http(
                urls[1] + "/snapshots/from-run",
                {"run_id": run["run_id"], "artifact_id": artifact["artifact_id"]},
            )
            runtime.update(
                {
                    "unit_snapshot_id"
                    if phase == "units_export"
                    else "metric_snapshot_id": snapshot_id,
                    "unit_imported"
                    if phase == "units_export"
                    else "metric_imported": imported,
                }
            )
            write_json(receipt, runtime)
        subprocess.run(
            [
                str(state / "envs/data-interface/bin/python"),
                str(ROOT / "admin/accept_common_toolchain.py"),
                "sdk",
                "--run-root",
                str(state),
                "--runtime-receipt",
                str(receipt),
            ],
            env=env,
            check=True,
        )
        after = {row["run_id"] for row in client.runs(limit=100)}
        runtime["only_new_metadata_task"] = after == before | new_runs
        if not runtime["only_new_metadata_task"]:
            raise ValueError("Data completion unexpectedly submitted additional tasks")
        runtime.update(status="succeeded", ended_at=now())
        write_json(receipt, runtime)
        print(
            json.dumps(
                {"data_completion_succeeded": True, "no_physical_tasks_repeated": True}
            ),
            flush=True,
        )
    except BaseException as error:
        runtime.update(status="failed", error=str(error), ended_at=now())
        write_json(receipt, runtime)
        raise
    finally:
        if active is not None:
            client.cancel(active)
        for process in reversed(services):
            stop_native_tree(process)
        for log in logs:
            log.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--previous-receipt", type=Path)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    finish(args.run_root.resolve(), args.previous_receipt, args.receipt)


if __name__ == "__main__":
    main()
