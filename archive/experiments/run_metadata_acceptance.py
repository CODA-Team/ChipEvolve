"""Reuse the real EDA/data and lifecycle acceptance with an explicit EF wheel."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from admin import lease_failure_probe, lease_stability_probe
from chip_evolve.config import read, write


def summarize(folder: Path) -> dict:
    record = read(folder / "acceptance.json")
    reads = record["sustained_reads"]
    writes = [
        json.loads(line)
        for line in (folder / "data-writes.jsonl").read_text().splitlines()
    ]
    windows = []
    starts = {}
    for row in writes:
        identity = row["snapshot_id"]
        if row["event"] == "started":
            starts[identity] = row["wall"]
            continue
        if row["event"] != "completed":
            continue
        started, ended = starts[identity], row["wall"]
        overlap = [
            r
            for r in reads
            if r["wall"] >= started and r["wall"] + r["seconds"] <= ended
        ]
        windows.append(
            {
                "snapshot_id": row["snapshot_id"],
                "seconds": ended - started,
                "fully_overlapping_reads": len(overlap),
                "passed": sum(r["ok"] for r in overlap),
            }
        )
    pulses = [
        json.loads(line)
        for line in (folder / "kernel/heartbeats.jsonl").read_text().splitlines()
    ]
    summary = {
        "physical_success": all(
            r["ok"] and r["seven_metrics_exact"] for r in record["physical"]
        ),
        "lost_runs": sum(r["status"] == "lost" for r in record["runs"]),
        "large_data": record["large_data"]["ok"],
        "sdk_initial_passed": sum(r["ok"] for r in record["reads"]),
        "sdk_initial_total": len(record["reads"]),
        "sustained_passed": sum(r["ok"] for r in reads),
        "sustained_total": len(reads),
        "max_sdk_seconds": max(r["seconds"] for r in reads),
        "health_2s_errors": record["health_errors"],
        "max_heartbeat_seconds": max(r["elapsed"] for r in pulses),
        "heartbeat_errors": [r for r in pulses if r["error"]],
        "write_windows": windows,
        "storage": "original owned /home project directory; WAL/FULL",
        "scope": "Real fixed physical replays and data concurrency; no new search or PPA claim",
    }
    write(folder / "business-acceptance.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["concurrent", "lifecycle", "summarize"])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--runtime-python", type=Path, required=True)
    args = parser.parse_args()
    folder, python = args.output.resolve(), args.runtime_python.absolute()
    if args.mode == "lifecycle":
        lease_failure_probe.main(folder, runtime_python=python)
        return
    if args.mode == "concurrent":
        lease_stability_probe.execute(
            folder.name,
            storage_root=folder.parent,
            data_wal=True,
            runtime_python=python,
        )
    print(json.dumps(summarize(folder), ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
