"""Measure owned native process disappearance separately from API completion.

The acceptance bound concerns all captured process IDs. The existing lifecycle
failure is retained; this observer does not change the product or that record.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import threading
import time
import urllib.request
from eda_toolkits.inputs import SnapshotExecutionClient, snapshot_inputs
from eda_toolkits.jobs import native_task
from openroad_platform_client import KernelClient


def stat_identity(pid):
    try:
        tail = Path("/proc", str(pid), "stat").read_text().rsplit(")", 1)[1].split()
        return {"state": tail[0], "start_ticks": int(tail[19])}
    except (OSError, ValueError, IndexError):
        return None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--kernel-url", required=True)
    p.add_argument("--data-url", required=True)
    p.add_argument("--snapshot", required=True)
    p.add_argument("--source-kernel-url")
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    if args.output.exists():
        raise ValueError("Use a fresh evidence directory")
    args.output.mkdir(parents=True)
    module_path = Path(__file__).with_name("execution_lifecycle.py")
    spec = importlib.util.spec_from_file_location(
        "lifecycle_observer_helpers", module_path
    )
    helpers = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helpers)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    snapshot = json.load(
        opener.open(
            args.data_url + "/snapshots/" + args.snapshot + "/summary?detail=full",
            timeout=30,
        )
    )["data"]["snapshot"]
    inputs, staged = snapshot_inputs(snapshot, False)
    client = (
        SnapshotExecutionClient(
            args.kernel_url,
            source_client=KernelClient(args.source_kernel_url, timeout=60),
            timeout=60,
        )
        if args.source_kernel_url
        else KernelClient(args.kernel_url, timeout=60)
    )
    rows = []
    for i in range(1, 4):
        task = native_task(
            snapshot,
            inputs,
            staged,
            'puts "CANCEL_OBSERVER_NATIVE_STARTED"; exec sleep 90',
        )
        task["task_id"] = "cancel-observer-" + str(time.time_ns())
        task["project_id"] = "clean-cancel-observer"
        task["timeout_seconds"] = 120
        task["expected_artifacts"] = []
        (args.output / f"cancel-{i}-task.json").write_text(
            json.dumps(task, indent=2) + "\n"
        )
        submitted = client.submit(task)
        run_id = submitted["run"]["run_id"]
        running = helpers.wait(client, run_id, wanted="running", timeout=120)
        if running["status"] != "running":
            raise RuntimeError("Run did not enter a native attempt")
        workspace = running["stages"][0]["attempts"][0]["workspace"]
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            tree = helpers.process_tree_for_workspace(workspace)
            if any(
                r["command"] and Path(r["command"][0]).name == "sleep" for r in tree
            ):
                break
            time.sleep(0.1)
        else:
            raise RuntimeError("Requires a real native process and sleep child")
        identities = {r["pid"]: stat_identity(r["pid"]) for r in tree}
        if any(v is None for v in identities.values()):
            raise RuntimeError("Process exited before observation handshake")
        samples = []
        done = threading.Event()
        started = time.monotonic()
        times = {}

        def observe():
            while not done.is_set():
                current = {pid: stat_identity(pid) for pid in identities}
                present = [
                    pid
                    for pid, v in current.items()
                    if v and v["start_ticks"] == identities[pid]["start_ticks"]
                ]
                runnable = [pid for pid in present if current[pid]["state"] != "Z"]
                elapsed = time.monotonic() - started
                samples.append(
                    {
                        "seconds": elapsed,
                        "present_pids": present,
                        "runnable_pids": runnable,
                    }
                )
                if not runnable and "runnable_gone_seconds" not in times:
                    times["runnable_gone_seconds"] = elapsed
                if not present:
                    times["all_pids_gone_seconds"] = elapsed
                    return
                if elapsed >= 30:
                    return
                done.wait(0.025)

        watcher = threading.Thread(target=observe)
        watcher.start()
        cancelled_at = datetime.now(timezone.utc).isoformat()
        error = None
        try:
            client.cancel(run_id)
            times["cancel_http_seconds"] = time.monotonic() - started
            terminal = helpers.wait(client, run_id, timeout=120)
            times["terminal_http_seconds"] = time.monotonic() - started
        except Exception as exc:
            error = str(exc)
            client.cancel(run_id)
            terminal = helpers.wait(client, run_id, timeout=120)
        finally:
            watcher.join(timeout=30)
            done.set()
            watcher.join()
        passed = (
            terminal["status"] == "cancelled"
            and times.get("all_pids_gone_seconds", float("inf")) <= 5
            and error is None
        )
        row = {
            "number": i,
            "run_id": run_id,
            "cancel_requested_at": cancelled_at,
            "tree": tree,
            "pid_identities": identities,
            "samples": samples,
            "times": times,
            "terminal_run": terminal,
            "request_error": error,
            "passed": passed,
            "logs": client.logs(run_id, max_bytes=65536),
            "resources": client.resources(run_id),
        }
        (args.output / f"cancel-{i}-result.json").write_text(
            json.dumps(row, indent=2) + "\n"
        )
        rows.append(row)
        print(json.dumps({"run_id": run_id, "passed": passed, **times}), flush=True)
    summary = {
        "passed": all(r["passed"] for r in rows),
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "acceptance": "All captured original PIDs gone within 5 seconds from sending cancellation; API completion latency reported separately. No direct signal by observer.",
        "prior_failure_retained": True,
        "program_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "helper_sha256": hashlib.sha256(module_path.read_bytes()).hexdigest(),
        "results": [
            {"run_id": r["run_id"], "passed": r["passed"], **r["times"]} for r in rows
        ],
    }
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
