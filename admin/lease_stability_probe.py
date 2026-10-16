"""Bounded isolated EDA/data replay with a slow evidence-custody fault."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import signal
import socket
import sqlite3
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from eda_ai_client import EdaAiClient
from openroad_platform_client import KernelClient, KernelUnavailable

from chip_evolve.comparisons import compare
from chip_evolve.config import Deployment, read, write
from chip_evolve.jobs import Jobs, http
from chip_evolve.physical import measure, publish
from chip_evolve.validation import query_facts, replay

ROOT = Path(__file__).resolve().parents[1]
ROUND = ROOT / "var/business/a22-lease-stability-20261016"
PREVIOUS = ROOT / "var/business/a19-a21-purposeful-relay-20261016/runtime"


def port() -> int:
    with socket.socket() as channel:
        channel.bind(("127.0.0.1", 0))
        return channel.getsockname()[1]


def execute(
    mode: str, *, storage_root: Path | None = None, data_wal: bool = False
) -> None:
    folder = (storage_root or ROUND) / mode
    folder.mkdir(exist_ok=False)
    config = read(PREVIOUS / "local.json")
    python = ROUND / "runtime" / (mode + "-env/bin/python")
    config.update(
        state_root=str(folder / "business"),
        kernel_url=f"http://127.0.0.1:{port()}",
        data_url=f"http://127.0.0.1:{port()}",
        client_python=str(python),
    )
    if storage_root is not None:
        config["runtime"]["bind_roots"].append(str(storage_root.resolve()))
    write(folder / "local.json", config)
    deployment = Deployment(folder / "local.json")
    services, handles = [], []
    stop_monitor = threading.Event()
    monitor = None

    def start(command: list[str], name: str, endpoint: str):
        log = (folder / (name + ".log")).open("w")
        handles.append(log)
        process = subprocess.Popen(command, cwd=ROOT, stdout=log, stderr=log)
        services.append(process)
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(f"{name} exited: {process.returncode}")
            try:
                http(endpoint, timeout=1)
                return process
            except OSError:
                time.sleep(0.1)
        raise TimeoutError(name + " startup")

    def measured_source(design: str, source: Path, key: str) -> dict[str, Any]:
        original = read(source)
        experiment = deployment.experiment(design, key)
        jobs = Jobs(deployment, design, experiment)
        measured = measure(
            jobs,
            "common",
            Path(original["files"]["odb"]),
            Path(original["files"]["spef"]),
            Path(deployment.design(design)["sdc"]),
            original["run_id"],
            Path(original["objective"]),
        )
        measured["route_drc"] = original["route_drc"]
        result = publish(jobs, measured)
        write(experiment / "result.json", result)
        query_facts(deployment, result)
        return result

    try:
        ef = start(
            [
                str(python),
                str(
                    ROOT / "execution-foundation/tests/fixtures/lease_probe_service.py"
                ),
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
                config["kernel_url"].rsplit(":", 1)[1],
                "--input-root",
                str(ROOT),
                "--input-root",
                str(folder),
                "--capacity-cpu-cores",
                "32",
                "--capacity-memory-bytes",
                str(128 << 30),
                "--platform-fraction",
                "1",
                "--worker-concurrency",
                "4",
            ],
            "execution",
            config["kernel_url"] + "/kernel/health",
        )
        df_python = ROOT / "var/business/a14-a17-20261016/df-check-env/bin/python"
        if data_wal:
            # Offline configuration of this new diagnostic DB, never a live DB.
            with sqlite3.connect(folder / "data.sqlite") as database:
                assert (
                    database.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
                )
                assert database.execute("PRAGMA synchronous").fetchone()[0] == 2
        write(
            folder / "storage-configuration.json",
            {
                "state_root": str(folder),
                "data_journal_mode": "wal" if data_wal else "delete",
                "synchronous": "FULL",
                "production": False,
            },
        )
        start(
            [
                str(df_python),
                str(ROOT / "admin/lease_data_probe_service.py"),
                "--host",
                "127.0.0.1",
                "--port",
                config["data_url"].rsplit(":", 1)[1],
                "--db",
                str(folder / "data.sqlite"),
                "--native-root",
                str(folder / "native"),
                "--kernel-url",
                config["kernel_url"],
                "--no-auto-import",
            ],
            "data",
            config["data_url"] + "/designs",
        )
        write(
            folder / "services.json",
            {"pids": [p.pid for p in services], "config": str(deployment.path)},
        )
        seed = measured_source(
            "gcd",
            PREVIOUS / "experiments/gcd/a21-gcd-power-single/result.json",
            "read-seed",
        )
        client = KernelClient(config["kernel_url"], timeout=120)
        observations: list[dict[str, Any]] = []

        def observe():
            public = KernelClient(config["kernel_url"], timeout=2)
            dumped = False
            with (folder / "health.jsonl").open("w", buffering=1) as output:
                while not stop_monitor.is_set():
                    started = time.monotonic()
                    row: dict[str, Any] = {"wall": time.time(), "monotonic": started}
                    try:
                        health = public.health()
                        row.update(workers=health["workers"], queue=health["queue"])
                        dumped = False
                    except KernelUnavailable as error:
                        row.update(error=type(error).__name__, detail=str(error))
                        if not dumped:
                            os.kill(ef.pid, signal.SIGUSR1)
                            dumped = True
                    row["seconds"] = time.monotonic() - started
                    observations.append(row)
                    output.write(json.dumps(row) + "\n")
                    stop_monitor.wait(1)

        monitor = threading.Thread(target=observe)
        monitor.start()
        sdk = EdaAiClient(data_url=config["data_url"], kernel_url=config["kernel_url"])

        def read_one(index: int):
            started = time.monotonic()
            wall = time.time()
            try:
                value = sdk.query_objects(
                    seed["snapshot_ids"]["opendb"],
                    kind="instance",
                    limit=5,
                    offset=index % 5,
                )
                assert value["scope"]["run_id"] == seed["run_id"]
                return {"ok": True, "wall": wall, "seconds": time.monotonic() - started}
            except (OSError, RuntimeError, ValueError, AssertionError) as error:
                return {
                    "ok": False,
                    "wall": wall,
                    "error": type(error).__name__,
                    "detail": str(error),
                    "seconds": time.monotonic() - started,
                }

        sources = [
            PREVIOUS / f"experiments/aes/a21-aes-{kind}/result.json"
            for kind in ("power-single", "power-relay", "routing-control")
        ]
        outcomes = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            work = []
            for index, source in enumerate(sources):
                experiment = deployment.experiment("aes", "physical-" + str(index))
                work.append(
                    (
                        str(source),
                        experiment,
                        pool.submit(replay, deployment, source, experiment),
                    )
                )
            deadline = time.monotonic() + 60
            while len(client.runs(design_id="aes", status="running", limit=10)) < 3:
                if time.monotonic() >= deadline:
                    raise TimeoutError("Three real physical attempts did not start")
                time.sleep(0.2)
            large = pool.submit(
                measured_source,
                "jpeg",
                PREVIOUS / "experiments/jpeg/a19-jpeg-source/result.json",
                "large-facts",
            )
            sustained_results: list[dict[str, Any]] = []

            def sustained_reads():
                with (folder / "sustained-reads.jsonl").open("w", buffering=1) as out:
                    for index in range(2400):
                        row = read_one(index)
                        sustained_results.append(row)
                        out.write(json.dumps(row) + "\n")
                        if large.done():
                            return
                        time.sleep(0.5)
                raise TimeoutError("bounded sustained read probe exceeded its budget")

            with concurrent.futures.ThreadPoolExecutor(max_workers=9) as readers:
                packed = readers.submit(client.bundle, seed["run_id"])
                slow = folder / "kernel/slow-custody.json"
                while not slow.exists():
                    if packed.done():
                        packed.result()
                        raise AssertionError(
                            "Expected slow-custody hook was not reached"
                        )
                    time.sleep(0.1)
                reads = [readers.submit(read_one, i) for i in range(64)]
                bundle = packed.result(timeout=180)
                read_results = [f.result(timeout=180) for f in reads]
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as reader:
                sustained = reader.submit(sustained_reads)
                sustained.result(timeout=2400)
            for source, experiment, future in work:
                try:
                    result = future.result(timeout=2400)
                    query_facts(deployment, result)
                    delta = compare(read(source), result)
                    write(experiment / "comparison.json", delta)
                    outcomes.append(
                        {
                            "source": source,
                            "ok": True,
                            "run_id": result["run_id"],
                            "seven_metrics_exact": all(
                                v["delta"] == 0 for v in delta["deltas"].values()
                            ),
                        }
                    )
                except (OSError, RuntimeError, ValueError, AssertionError) as error:
                    outcomes.append(
                        {
                            "source": source,
                            "ok": False,
                            "error": type(error).__name__,
                            "detail": str(error),
                        }
                    )
            try:
                data = large.result(timeout=2400)
                large_result = {
                    "ok": True,
                    "run_id": data["run_id"],
                    "snapshot_ids": data["snapshot_ids"],
                }
            except (OSError, RuntimeError, ValueError, AssertionError) as error:
                large_result = {
                    "ok": False,
                    "error": type(error).__name__,
                    "detail": str(error),
                }
        statuses = client.runs(limit=100)
        summary = {
            "mode": mode,
            "physical": outcomes,
            "large_data": large_result,
            "bundle": bundle,
            "reads": read_results,
            "sustained_reads": sustained_results,
            "health_errors": sum("error" in row for row in observations),
            "runs": statuses,
        }
        write(folder / "acceptance.json", summary)
        print(
            mode,
            "physical",
            [x["ok"] for x in outcomes],
            "large",
            large_result["ok"],
            "SDK",
            sum(x["ok"] for x in read_results),
            "/64",
            "health errors",
            summary["health_errors"],
            flush=True,
        )
    finally:
        stop_monitor.set()
        if monitor is not None:
            monitor.join(10)
        for service in reversed(services):
            if service.poll() is None:
                service.terminate()
                service.wait(timeout=2000)
        for handle in handles:
            handle.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["before", "after", "after-r2", "after-r3"])
    parser.add_argument("--storage-root", type=Path)
    parser.add_argument("--data-wal", action="store_true")
    args = parser.parse_args()
    execute(args.mode, storage_root=args.storage_root, data_wal=args.data_wal)
