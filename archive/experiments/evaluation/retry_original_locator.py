"""Record a read-only retry of one failed registered-original lookup."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from openroad_platform_client import KernelClient


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--previous-cache", type=Path, required=True)
    parser.add_argument("--key", required=True)
    parser.add_argument("--kernel-url", required=True)
    parser.add_argument("--timeout", type=float, default=60)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    old = json.loads(args.previous_cache.read_text())
    if args.key not in old or "errors" not in old[args.key]:
        raise ValueError("Retry must reference an explicitly recorded failed lookup")
    run_id, artifact_id = args.key.split("/")
    locator = KernelClient(args.kernel_url, timeout=args.timeout).artifact_locator(
        run_id, artifact_id
    )
    path = Path(locator["path"])
    native = {
        "endpoint": args.kernel_url,
        "locator": locator,
        "actual_sha256": digest(path),
        "actual_size_bytes": path.stat().st_size,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
    passed = (
        locator["run_id"] == run_id
        and locator["artifact_id"] == artifact_id
        and native["actual_sha256"] == locator["sha256"]
        and native["actual_size_bytes"] == locator["size_bytes"]
    )
    result = {
        "passed": passed,
        "key": args.key,
        "previous_cache_path": str(args.previous_cache.resolve()),
        "previous_cache_sha256": digest(args.previous_cache),
        "first_failure": old[args.key],
        "retry": native,
        "timeout_seconds": args.timeout,
        "program_sha256": digest(Path(__file__)),
        "actions": "GET artifact locator and read current bytes; no EDA submission",
    }
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"passed": passed, "key": args.key}))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
