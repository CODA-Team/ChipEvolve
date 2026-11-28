"""Recover A22 negative-case deliveries, retaining their original EDA identities."""

from __future__ import annotations

import subprocess
import time

from openroad_platform_client import KernelClient

from admin.lease_stability_probe import ROOT, ROUND
from chip_evolve.comparisons import compare
from chip_evolve.config import Deployment, read, write
from chip_evolve.delivery import finish
from chip_evolve.jobs import digest, http
from chip_evolve.validation import query_facts


def main(mode: str) -> None:
    folder = ROUND / mode
    deployment = Deployment(folder / "local.json")
    config = deployment.value
    experiment = deployment.state / "experiments/aes/physical-0"
    acceptance_hash = digest(folder / "acceptance.json")
    identity = {
        key: read(experiment / "jobs" / key / "submission.json")["run"]["run_id"]
        for key in ("qualification", "common")
    }
    logs, processes = [], []
    python = ROUND / "runtime/after-r2-env/bin/python"
    ef = [
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
        config["kernel_url"].rsplit(":", 1)[1],
        "--input-root",
        str(ROOT),
        "--worker-concurrency",
        "2",
        "--capacity-cpu-cores",
        "32",
        "--capacity-memory-bytes",
        str(128 << 30),
        "--platform-fraction",
        "1",
    ]
    df = [
        str(ROOT / "var/business/a14-a17-20261016/df-check-env/bin/python"),
        "-m",
        "openroad_app_data_foundation",
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
    ]
    try:
        for name, command, endpoint in (
            ("execution", ef, config["kernel_url"] + "/kernel/health"),
            ("data", df, config["data_url"] + "/designs"),
        ):
            handle = (folder / ("recovery-" + name + ".log")).open("w")
            logs.append(handle)
            service = subprocess.Popen(command, cwd=ROOT, stdout=handle, stderr=handle)
            processes.append(service)
            deadline = time.monotonic() + 120
            while True:
                if service.poll() is not None:
                    raise RuntimeError(f"{name} exited: {service.returncode}")
                try:
                    http(endpoint, timeout=2)
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise TimeoutError(name + " recovery startup")
                    time.sleep(0.2)
        client = KernelClient(config["kernel_url"], timeout=60)
        before = {row["run_id"] for row in client.runs(limit=100)}
        assert all(
            client.run(value)["status"] == "succeeded" for value in identity.values()
        )
        for path in (experiment / "imports").glob("*.json"):
            write(path.with_suffix(".before-recovery.json"), read(path))
        started = time.monotonic()
        result = finish(deployment, experiment)
        query_facts(deployment, result)
        original = read(experiment / "delivery-checkpoint.json")["native_method"][
            "original_result"
        ]
        delta = compare(read(original), result)
        assert all(row["delta"] == 0 for row in delta["deltas"].values())
        assert {
            key: read(experiment / "jobs" / key / "submission.json")["run"]["run_id"]
            for key in identity
        } == identity
        assert digest(folder / "acceptance.json") == acceptance_hash
        write(
            folder / "delivery-recovery.json",
            {
                "status": "succeeded",
                "elapsed_seconds": time.monotonic() - started,
                "original_physical_run_ids": identity,
                "physical_run_ids_unchanged": True,
                "seven_metrics_exact": True,
                "snapshot_ids": result["snapshot_ids"],
                "new_export_run_ids": sorted(
                    {row["run_id"] for row in client.runs(limit=100)} - before
                ),
                "negative_acceptance_sha256_unchanged": acceptance_hash,
            },
        )
        print(mode, "delivery recovered; original physical tasks reused", flush=True)
    finally:
        for service in reversed(processes):
            if service.poll() is None:
                service.terminate()
                service.wait(timeout=120)
        for handle in logs:
            handle.close()


if __name__ == "__main__":
    for mode in ("before", "after"):
        main(mode)
