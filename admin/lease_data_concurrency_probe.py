"""Offline WAL configuration and real import/read overlap, without new EDA."""

from __future__ import annotations

import concurrent.futures
import json
import sqlite3
import subprocess
import time
from typing import Any

from eda_ai_client import EdaAiClient
from openroad_platform_client import KernelClient

from admin.lease_stability_probe import ROOT, ROUND, port
from chip_evolve.config import read, write
from chip_evolve.jobs import http


def main() -> None:
    from pathlib import Path

    root = Path(read(ROUND / "parallel-ssd-location.json")["root"])
    previous = root / "after-r2"
    folder = root / "wal-data"
    folder.mkdir(exist_ok=False)
    kernel_url, data_url = f"http://127.0.0.1:{port()}", f"http://127.0.0.1:{port()}"
    database = folder / "data.sqlite"
    # Offline maintenance of a new, isolated state file; no product DB is opened.
    with sqlite3.connect(database) as db:
        assert db.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
        assert db.execute("PRAGMA synchronous").fetchone()[0] == 2
    python = ROUND / "runtime/after-r2-env/bin/python"
    ef = [
        str(python),
        "-m",
        "openroad_platform_gateway",
        "--state-root",
        str(previous / "kernel"),
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
        kernel_url.rsplit(":", 1)[1],
        "--input-root",
        str(ROOT),
        "--input-root",
        str(root),
    ]
    df = [
        str(ROOT / "var/business/a14-a17-20261016/df-check-env/bin/python"),
        str(ROOT / "admin/lease_data_probe_service.py"),
        "--host",
        "127.0.0.1",
        "--port",
        data_url.rsplit(":", 1)[1],
        "--db",
        str(database),
        "--native-root",
        str(folder / "native"),
        "--kernel-url",
        kernel_url,
        "--no-auto-import",
    ]
    processes, logs = [], []
    try:
        for name, command, endpoint in (
            ("execution", ef, kernel_url + "/kernel/health"),
            ("data", df, data_url + "/designs"),
        ):
            handle = (folder / (name + ".log")).open("w")
            logs.append(handle)
            process = subprocess.Popen(command, cwd=ROOT, stdout=handle, stderr=handle)
            processes.append(process)
            deadline = time.monotonic() + 120
            while True:
                if process.poll() is not None:
                    raise RuntimeError(f"{name} exited: {process.returncode}")
                try:
                    http(endpoint, timeout=2)
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise TimeoutError(name + " startup")
                    time.sleep(0.1)
        client = KernelClient(kernel_url)
        before = {row["run_id"] for row in client.runs(limit=100)}
        assert not client.runs(status="running", limit=100)
        seed = read(previous / "business/experiments/gcd/read-seed/result.json")
        large = read(previous / "business/experiments/jpeg/large-facts/result.json")

        def import_result(result):
            execution = result["exports"]["opendb"]["execution"]
            artifact = next(
                a for a in execution["artifacts"] if a["kind"] == "data_snapshot"
            )
            return http(
                data_url + "/snapshots/from-run",
                {
                    "run_id": execution["run"]["run_id"],
                    "artifact_id": artifact["artifact_id"],
                },
                timeout=900,
            )

        import_result(seed)
        sdk = EdaAiClient(data_url=data_url, kernel_url=kernel_url)
        observations = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(import_result, large)
            deadline = time.monotonic() + 900
            with (folder / "reads.jsonl").open("w", buffering=1) as out:
                while not future.done():
                    assert time.monotonic() < deadline
                    started, wall = time.monotonic(), time.time()
                    row: dict[str, Any]
                    try:
                        value = sdk.query_objects(
                            seed["snapshot_ids"]["opendb"], kind="instance", limit=5
                        )
                        assert value["scope"]["run_id"] == seed["run_id"]
                        row = {"ok": True}
                    except (OSError, RuntimeError, ValueError, AssertionError) as error:
                        row = {"ok": False, "detail": str(error)}
                    row.update(wall=wall, seconds=time.monotonic() - started)
                    observations.append(row)
                    out.write(json.dumps(row) + "\n")
                    time.sleep(0.25)
            imported = future.result(timeout=900)
        assert {row["run_id"] for row in client.runs(limit=100)} == before
        events = [
            json.loads(s)
            for s in (folder / "data-writes.jsonl").read_text().splitlines()
        ]
        start = next(
            e["wall"]
            for e in events
            if e["design_id"] == "jpeg" and e["event"] == "started"
        )
        end = next(
            e["wall"]
            for e in events
            if e["design_id"] == "jpeg" and e["event"] == "completed"
        )
        overlap = [
            r
            for r in observations
            if start <= r["wall"] and r["wall"] + r["seconds"] <= end
        ]
        assert len(overlap) >= 10 and all(r["ok"] for r in observations)
        with sqlite3.connect(database) as db:
            assert db.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
            assert db.execute("PRAGMA synchronous").fetchone()[0] == 2
        summary = {
            "status": "passed",
            "directory": str(folder),
            "journal_mode": "wal",
            "synchronous": "FULL",
            "new_eda_runs": 0,
            "reads": len(observations),
            "reads_entirely_within_import": len(overlap),
            "all_reads_passed": True,
            "max_read_seconds": max(r["seconds"] for r in observations),
            "import_seconds": end - start,
            "import_result": imported,
        }
        write(folder / "acceptance.json", summary)
        write(ROUND / "data-wal-acceptance.json", summary)
        print({k: v for k, v in summary.items() if k != "import_result"}, flush=True)
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=120)
        for handle in logs:
            handle.close()


if __name__ == "__main__":
    main()
