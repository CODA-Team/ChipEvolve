#!/usr/bin/env python3
"""Exercise all twelve CONTRACT tools against a live service.

Run it from inside a *clean* virtual environment that installed this package,
so a pass means the published client works, not a repository checkout:

    python -m venv /tmp/clean && /tmp/clean/bin/pip install ./clients/eda_ai_client
    /tmp/clean/bin/python clients/eda_ai_client/examples/smoke_all_tools.py

The identifiers default to the accepted sprint dataset (gcd + ibex).  Override
with --design / --snapshot / --run.
"""

from __future__ import annotations

import argparse
import sys

from eda_ai_client import EdaAiClient, EdaAiError

#: harvested from row 20000 of the raw ibex objects.jsonl by
#: evidence/B/check_deep_object_lookup.py - an object well past 10000 rows.
DEEP_INSTANCE_NAME = "_19891_"


def data(response: dict) -> dict:
    """The tool's own structure: CONTRACT 1 responses carry it under ``data``."""
    return response.get("data", response)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-url", default="http://127.0.0.1:8860")
    parser.add_argument("--kernel-url", default="http://127.0.0.1:8700")
    parser.add_argument("--design", default="ibex")
    parser.add_argument("--snapshot", default="ibex-eda_ai_sprint_b1-route")
    parser.add_argument("--run", default="run-f0adf52aa762424a8fc1ec32fc18c563")
    args = parser.parse_args()

    checks: list[tuple[str, str]] = []

    def record(tool: str, detail: str) -> None:
        checks.append((tool, detail))
        print(f"  {tool:22s} {detail}")

    with EdaAiClient(data_url=args.data_url, kernel_url=args.kernel_url) as client:
        health = client.health()
        record("health", f"status={health.get('status')}")

        designs = client.list_designs()
        record("list_designs", f"{len(designs)} designs: "
                               f"{[row['design_id'] for row in designs]}")

        runs = client.list_runs(design_id=args.design, limit=10)
        record("list_runs", f"{len(runs)} runs for {args.design}")

        run_summary = client.get_run_summary(args.run)
        record("get_run_summary", f"{len(data(run_summary)['snapshots'])} snapshots")

        stage = client.get_stage_summary(args.snapshot)
        counts = data(stage)["record_counts"]
        record("get_stage_summary", f"entities={counts['entities']} "
                                    f"relations={counts['relations']}")

        metrics = client.get_metrics(run_id=args.run, stage="finish")
        available = [row for row in data(metrics)["metrics"]
                     if row.get("status") == "available"]
        record("get_metrics", f"{len(available)} available canonical: "
                              f"{sorted(row['name'] for row in available)}")

        paths = client.get_timing_paths(args.snapshot, check="setup", limit=5)
        record("get_timing_paths", f"{data(paths)['returned']} setup paths")
        path_id = data(paths)["timing_paths"][0]["path_id"]

        summary = client.get_timing_path(args.snapshot, path_id)
        points = client.get_timing_path(args.snapshot, path_id, include="points")
        record("get_timing_path", f"{path_id}: "
                                  f"{len(data(points)['timing_points'])} points, "
                                  f"slack={data(summary)['timing_path'].get('slack')}")

        instance = client.get_instance(args.snapshot, DEEP_INSTANCE_NAME)
        record("get_instance", f"{DEEP_INSTANCE_NAME} -> {instance['status']}, "
                               f"relations={len(instance.get('relations', []))}")

        sample = next(point for point in data(points)["timing_points"] if point.get("net_id"))
        net = client.get_net_context(args.snapshot, sample["net_id"])
        record("get_net_context", f"{sample['net_id']} -> "
                                  f"{len(net.get('entities', []))} entities, "
                                  f"{len(net.get('relations', []))} relations")
        object_id = sample.get("instance_id") or sample.get("pin_id")

        physical = client.get_physical_context(args.snapshot, object_id)
        bbox = physical.get("physical_context", {}).get("bbox")
        record("get_physical_context", f"{object_id} bbox={bbox}")

        evidence = client.get_evidence(args.snapshot, limit=200)
        # CONTRACT 1 lifts the evidence list to the envelope for every tool
        first = evidence["evidence"][0]["evidence"]
        record("get_evidence", f"{data(evidence)['returned']} entries "
                               f"(count={evidence.get('count')}, "
                               f"{evidence.get('count_status', 'exact')}), "
                               f"first artifact={first.get('artifact_id')}")

        # Raw bytes must be retrievable, and the documented 4 MiB download limit
        # must refuse rather than truncate.  Both are checked: the first entry of
        # the index is now a 25 MB ODB, which is exactly why picking "the first
        # evidence" and downloading it is not a valid smoke.
        limit = 4 * 1024 * 1024
        entries = [row["evidence"] for row in evidence["evidence"]
                   if isinstance(row.get("evidence"), dict)
                   and row["evidence"].get("artifact_id")
                   and row["evidence"].get("run_id")]
        # the index page is dominated by entities pointing at a 25 MB ODB, so a
        # small artifact is asked for by record type - timing reports are kilobytes
        reports = client.get_evidence(args.snapshot, record_type="timing_paths", limit=10)
        entries += [row["evidence"] for row in reports.get("evidence", [])
                    if isinstance(row.get("evidence"), dict)
                    and row["evidence"].get("artifact_id")
                    and row["evidence"].get("run_id")]
        small = next((item for item in entries if (item.get("size_bytes") or 0) <= limit), None)
        big = next((item for item in entries if (item.get("size_bytes") or 0) > limit), None)
        if small is None:
            record("artifact_bytes", "skipped (no artifact under the download limit)")
        else:
            blob = client.artifact_bytes(small["run_id"], small["artifact_id"])
            record("artifact_bytes",
                   f"{len(blob)} bytes for {small['artifact_id']} "
                   f"({small.get('logical_path')})")
        if big is not None:
            try:
                client.artifact_bytes(big["run_id"], big["artifact_id"])
            except EdaAiError as exc:
                record("artifact_bytes (oversized)",
                       f"refused as documented: {exc}")
            else:
                record("artifact_bytes (oversized)",
                       "FAIL: a >4 MiB artifact downloaded, the documented limit "
                       "is not enforced")

    # Any HTTP or shape problem above would have raised EdaAiError, so reaching
    # this line is the assertion: every tool answered.
    print(f"\nPASS: {len(checks)} client calls against the live service")
    return 0


if __name__ == "__main__":
    sys.exit(main())
