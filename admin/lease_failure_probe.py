"""Verify cancellation and real worker loss against an isolated installed EF."""

from __future__ import annotations

import concurrent.futures
import os
import socket
import subprocess
import time
from pathlib import Path

from openroad_platform_client import KernelClient, KernelUnavailable

from chip_evolve.config import Deployment, read, write
from chip_evolve.jobs import Jobs

ROOT = Path(__file__).resolve().parents[1]
ROUND = ROOT / "var/business/a22-lease-stability-20261016"


def main(folder: Path | None = None) -> None:
    folder = folder or ROUND / "failure-scenarios-r4"
    folder.mkdir(exist_ok=False)
    with socket.socket() as channel:
        channel.bind(("127.0.0.1", 0))
        port = channel.getsockname()[1]
    config = read(
        ROOT / "var/business/a19-a21-purposeful-relay-20261016/runtime/local.json"
    )
    python = ROUND / "runtime/after-r3-env/bin/python"
    config.update(
        kernel_url=f"http://127.0.0.1:{port}",
        client_python=str(python),
        state_root=str(folder / "business"),
    )
    write(folder / "local.json", config)
    deployment = Deployment(folder / "local.json")
    client = KernelClient(config["kernel_url"])
    command = [
        str(python),
        "-m",
        "openroad_platform_gateway",
        "--state-root",
        str(folder / "kernel"),
        "--plugins-root",
        str(ROOT / "var/business/a4-a5-20261014/runtime/plugins"),
        "--admissions-root",
        str(
            ROOT
            / "var/toolchains/common-u1-20261012-retry6/dependency-sources/execution-foundation/admissions"
        ),
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--input-root",
        str(ROOT),
        "--input-root",
        str(folder),
        "--capacity-cpu-cores",
        "2",
        "--capacity-memory-bytes",
        str(8 << 30),
        "--platform-fraction",
        "1",
        "--worker-concurrency",
        "2",
    ]
    logs, processes = [], []

    def start(name):
        log = (folder / (name + ".log")).open("w")
        logs.append(log)
        process = subprocess.Popen(command, stdout=log, stderr=log, cwd=ROOT)
        processes.append(process)
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(f"isolated worker exited: {process.returncode}")
            try:
                client.health()
                return process
            except KernelUnavailable:
                time.sleep(0.1)
        raise TimeoutError("isolated worker startup")

    try:
        service = start("first-worker")
        outcomes = {}
        for mode in ["cancel", "lost"]:
            experiment = deployment.experiment("gcd", mode)
            marker = experiment / "owned-child.pid"
            script = (
                "import os,time;from pathlib import Path;Path("
                + repr(str(marker))
                + ").write_text(str(os.getpid()));time.sleep(120)"
            )
            jobs = Jobs(deployment, "gcd", experiment)
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(
                    jobs.command,
                    "controlled-lifecycle",
                    [str(python), "-c", script],
                    capture=[marker],
                    cpu=1,
                    memory_gib=1,
                    seconds=150,
                )
                deadline = time.monotonic() + 30
                submission = experiment / "jobs/controlled-lifecycle/submission.json"
                while not (marker.exists() and submission.exists()):
                    assert time.monotonic() < deadline
                    time.sleep(0.1)
                run_id = read(submission)["run"]["run_id"]
                child = int(marker.read_text())
                started = time.monotonic()
                if mode == "cancel":
                    client.cancel(run_id)
                else:
                    service.kill()
                    service.wait(timeout=5)
                    service = start("replacement-worker")
                try:
                    future.result(timeout=90)
                    raise AssertionError(
                        "faulted task was incorrectly reported as succeeded"
                    )
                except RuntimeError as error:
                    failure = str(error)
                view = client.run(run_id)
                expected = "cancelled" if mode == "cancel" else "lost"
                assert view["status"] == expected, view
                deadline = time.monotonic() + 5
                while True:
                    try:
                        os.kill(child, 0)
                    except ProcessLookupError:
                        break
                    assert time.monotonic() < deadline, "owned child survived fencing"
                    time.sleep(0.1)
                resources = client.resources(run_id)
                assert resources["reserved"] == {"cpu_cores": 0, "memory_bytes": 0}
                outcomes[mode] = {
                    "run_id": run_id,
                    "status": expected,
                    "elapsed_seconds": time.monotonic() - started,
                    "owned_child_gone": True,
                    "resources_released": True,
                    "driver_failure": failure,
                }
        write(folder / "acceptance.json", outcomes)
        print(outcomes, flush=True)
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=180)
        for log in logs:
            log.close()


if __name__ == "__main__":
    main()
