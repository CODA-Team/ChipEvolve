"""Compare explicitly selected terminal run records across an owned restart."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from openroad_platform_client import KernelClient


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("before", "after"))
    parser.add_argument("--kernel-url", required=True)
    parser.add_argument("--lifecycle", type=Path, required=True)
    parser.add_argument("--run", action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    ids = sorted(
        {row["run_id"] for row in json.loads(args.lifecycle.read_text())["results"]}
        | set(args.run)
    )
    client = KernelClient(args.kernel_url)
    records = {}
    for run_id in ids:
        run = client.run(run_id)
        if run["status"] not in (
            "succeeded",
            "failed",
            "cancelled",
            "timed_out",
            "lost",
        ):
            raise ValueError("Capture only terminal runs: " + run_id)
        records[run_id] = {
            "run": run,
            "resources": client.resources(run_id),
            "artifacts": client.artifacts(run_id),
            "logs": client.logs(run_id, max_bytes=65536),
        }
    args.output.mkdir(parents=True, exist_ok=True)
    target = args.output / (args.mode + ".json")
    with target.open("x") as stream:
        json.dump(records, stream, indent=2, sort_keys=True)
        stream.write("\n")
    if args.mode == "after":
        before_path = args.output / "before.json"
        before = json.loads(before_path.read_text())
        if set(before) != set(records):
            raise ValueError("Restart comparison must use the same run identities")
        checks = {
            run_id: {key: value == before[run_id][key] for key, value in row.items()}
            for run_id, row in records.items()
        }
        summary = {
            "passed": all(all(row.values()) for row in checks.values()),
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "kernel_url": args.kernel_url,
            "checks": checks,
            "before_sha256": digest(before_path),
            "after_sha256": digest(target),
            "lifecycle_sha256": digest(args.lifecycle),
            "program_sha256": digest(Path(__file__)),
        }
        with (args.output / "summary.json").open("x") as stream:
            json.dump(summary, stream, indent=2)
            stream.write("\n")
        print(json.dumps({"passed": summary["passed"], "runs": len(records)}))
        return 0 if summary["passed"] else 1
    print(json.dumps({"captured": len(records), "health": client.health()}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
