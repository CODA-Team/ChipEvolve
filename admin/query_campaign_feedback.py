"""Check every actual P3 evaluation through the installed Data Interface SDK."""

import argparse
import hashlib
import json
import math
from pathlib import Path

from eda_ai_client import EdaAiClient


def verify_metrics(rows, measured, metadata):
    for name, observation in (("TNS", "tns"), ("WNS", "wns"), ("POWER_TOTAL", "power")):
        row = rows[name]
        expected = measured["observations"][observation]
        if (
            row["status"] != "available"
            or row["unit"] != expected["unit"]
            or not math.isclose(row["value"], expected["value"], abs_tol=1e-9)
            or row["authoritative_source"] != "a2_cp0_evaluator"
            or row["evaluation_conditions"]
            != measured["metric_context"]["evaluation_conditions"]
            or not row["evidence"]
        ):
            raise ValueError("SDK feedback differs from actual evaluator: " + name)
        evidence = row["evidence"][0]
        if (
            evidence["artifact_id"] != metadata["artifact_id"]
            or evidence["sha256"] != metadata["sha256"]
            or evidence["resolution"] not in {"exact_path", "exact_artifact"}
        ):
            raise ValueError("SDK metric has a different producer: " + name)


def audit(run, data_url, kernel_url):
    client = EdaAiClient(data_url=data_url, kernel_url=kernel_url)
    output = run / "sdk-feedback"
    output.mkdir(exist_ok=True)
    receipts = []
    for path in sorted((run / "platform-state").glob("iteration-*/*-feedback.json")):
        value = json.loads(path.read_text())
        if value.get("imported") is not True:
            raise ValueError("Evaluation feedback was not imported: " + str(path))
        measured_bytes = client.artifact_bytes(
            value["evaluation_run_id"], value["metadata"]["artifact_id"]
        )
        measured = json.loads(measured_bytes)
        copied = next(
            row
            for row in value["artifacts"]
            if row["store_key"] == "inputs/a2-evaluation.json"
        )
        raw = client.artifact_bytes(value["producer_run_id"], copied["artifact_id"])
        if raw != measured_bytes or hashlib.sha256(raw).hexdigest() != copied["sha256"]:
            raise ValueError("Imported source bytes differ from the actual evaluator.")
        metrics = client.get_metrics(snapshot_id=value["snapshot_id"])
        rows = {row["name"]: row for row in metrics["data"]["metrics"]}
        verify_metrics(rows, measured, copied)
        receipt = {
            "accepted": True,
            "snapshot_id": value["snapshot_id"],
            "physical_run_id": value["physical_run_id"],
            "evaluation_run_id": value["evaluation_run_id"],
            "producer_run_id": value["producer_run_id"],
            "source_metadata": copied,
            "metrics": metrics,
            "parasitic_mode": measured["parasitic_mode"],
        }
        destination = output / (path.parent.name + "-" + path.name)
        destination.write_text(json.dumps(receipt, indent=2) + "\n")
        receipts.append({"snapshot_id": value["snapshot_id"], "path": str(destination)})
    if not receipts:
        raise ValueError("No actual evaluation feedback is available.")
    return {"accepted": True, "snapshots": receipts}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--data-url", required=True)
    parser.add_argument("--kernel-url", required=True)
    args = parser.parse_args()
    result = audit(args.run_root.resolve(), args.data_url, args.kernel_url)
    print(json.dumps(result))
