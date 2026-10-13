"""Audit U4 physical and execution evidence offline; do not replace selection."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any

from run_dplevolve_native import digest, write_json

METRICS = ("tns_abs_ns", "dynamic_power_pw", "leakage_power_pw")


def validate_archive(folder: Path, request: dict[str, Any]) -> None:
    """Check actual registered bytes against the leaf's source/output receipt."""
    leaf = json.loads((folder / "leaf.json").read_text())
    if leaf["request"] != request:
        raise ValueError("Leaf execution request mismatch")
    with zipfile.ZipFile(folder / "evidence.zip") as archive:
        manifest = json.loads(archive.read("manifest.json"))
        if not manifest["evidence_only"] or manifest["receipt"] != leaf:
            raise ValueError("Archived execution receipt mismatch")
        actual: Counter[tuple[str, str]] = Counter()
        for name in archive.namelist():
            if name == "manifest.json" or name.endswith("/"):
                continue
            hasher = hashlib.sha256()
            with archive.open(name) as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    hasher.update(block)
            actual[(Path(name).name, hasher.hexdigest())] += 1
        expected = Counter(
            (Path(name).name, checksum)
            for name, checksum in leaf["output_files"].items()
        )
        if actual != expected:
            raise ValueError("Archived output bytes mismatch")


def measured(value: dict[str, Any]) -> dict[str, float]:
    if not value.get("ok", value.get("evaluation_error") is None):
        raise ValueError("Evaluation failed")
    checks = value.get("checks") or []
    required = {"build", "flow", "metrics", "placement", "lec"}
    passed = {item["name"] for item in checks if item["passed"]}
    if not required.issubset(passed) or any(not item["passed"] for item in checks):
        raise ValueError("Native validity checks are incomplete")
    result = {key: float(value["metrics"][key]) for key in METRICS}
    if any(not math.isfinite(v) or v < 0 for v in result.values()):
        raise ValueError("Invalid physical metric")
    if float(value["metrics"]["drv_count"]) != 0:
        raise ValueError("Nonzero DRV")
    return result


def compare_replay(candidate: dict[str, Any], replay: dict[str, Any]) -> dict[str, Any]:
    original, repeated = measured(candidate), measured(replay)
    delta = {}
    for key in METRICS:
        absolute = abs(repeated[key] - original[key])
        # QoR print precision: 0.01 ns for TNS, five relative decimal places
        # for the official power report. Runtime is measured, not compared.
        tolerance = (
            0.011 if key == "tns_abs_ns" else max(1.0, abs(original[key]) * 1e-5)
        )
        if absolute > tolerance:
            raise ValueError("Independent replay differs: " + key)
        delta[key] = {
            "candidate": original[key],
            "replay": repeated[key],
            "absolute_difference": absolute,
            "tolerance": tolerance,
        }
    return delta


def audit_operations(state: Path, profile: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    for path in sorted((state / "operations").glob("*/submission.json")):
        folder = path.parent
        submitted = json.loads(path.read_text())
        request = json.loads((folder / "request.json").read_text())
        execution = json.loads((folder / "execution.json").read_text())
        run = execution["run"]
        if (
            run["run_id"] != submitted["run_id"]
            or request["image_sha256"] != profile["toolchain"]["image_sha256"]
        ):
            raise ValueError("Execution identity mismatch")
        if run["status"] not in {
            "succeeded",
            "failed",
            "cancelled",
            "timed_out",
            "lost",
        }:
            raise ValueError("Nonterminal deterministic operation")
        evidence = folder / "evidence.zip"
        if run["status"] == "succeeded":
            leaf = json.loads((folder / "leaf.json").read_text())
            if leaf["returncode"] or leaf.get("timed_out"):
                raise ValueError("False success")
            snapshots = [
                item
                for item in execution["artifacts"]
                if item["kind"] == "data_snapshot"
            ]
            if len(snapshots) != 1 or not evidence.is_file():
                raise ValueError("Missing registered evidence archive")
            # SHA field naming follows the saved public artifact envelope.
            actual = digest(evidence)
            artifact = snapshots[0]
            expected = artifact.get("sha256") or artifact.get("checksum_sha256")
            if expected and expected != actual:
                raise ValueError("Materialized evidence hash mismatch")
            validate_archive(folder, request)
        result.append(
            {
                "key": folder.name,
                "run_id": run["run_id"],
                "status": run["status"],
                "operation": request["operation"],
                "source": request["source"],
                "attempt": request["attempt"],
                "evidence_sha256": digest(evidence) if evidence.exists() else None,
            }
        )
    if not result:
        raise ValueError("No EF operations")
    return result


def audit(state: Path) -> dict[str, Any]:
    profile = json.loads((state / "config.json").read_text())
    campaign = state / "campaigns/aes_cipher_top/u4"
    baseline = json.loads((campaign / "baseline/baseline.json").read_text())
    baseline_metrics = measured(baseline)
    round_roots = sorted((campaign / "campaign/rounds").glob("round_*"))
    if not round_roots or not (round_roots[-1] / "round.json").is_file():
        raise ValueError("Latest native round is incomplete")
    round_root = round_roots[-1]
    rounds = [
        path / "round.json" for path in round_roots if (path / "round.json").is_file()
    ]
    summary = json.loads((round_root / "round.json").read_text())
    if summary["student_count"] != 4:
        raise ValueError("Four native Students required")
    candidates = []
    for path in sorted(round_root.glob("students/*/artifacts/candidate.json")):
        value = json.loads(path.read_text())
        candidates.append(
            {
                "path": str(path),
                "student_id": value["student_id"],
                "source_commit": value["source_commit"],
                "evaluation_error": value["evaluation_error"],
                "metrics": value["metrics"],
                "checks": value["checks"],
            }
        )
    if {c["student_id"] for c in candidates} != {
        "student_1",
        "student_2",
        "student_3",
        "student_4",
    }:
        raise ValueError("Missing Student result")
    replay_receipt = json.loads((state / "replay/replay.json").read_text())
    if (
        not Path(replay_receipt["candidate_json"])
        .resolve()
        .is_relative_to(round_root.resolve())
    ):
        raise ValueError("Replay candidate belongs to a different native round")
    candidate = json.loads(Path(replay_receipt["candidate_json"]).read_text())
    replay = json.loads(Path(replay_receipt["measurement_json"]).read_text())
    if (
        not candidate["implementation_diff"]
        or candidate["legacy"]
        or replay_receipt["used_build_donor"]
    ):
        raise ValueError(
            "Replay requires real new source and an independent clean build"
        )
    delta = compare_replay(candidate, replay)
    operations = audit_operations(state, profile)
    replay_service = state / "replay-service"
    if replay_service.is_dir():
        replay_profile = json.loads((replay_service / "config.json").read_text())
        if replay_profile["toolchain"] != profile["toolchain"]:
            raise ValueError("Independent replay toolchain differs")
        operations.extend(audit_operations(replay_service, replay_profile))
    return {
        "engineering_status": "physical_evidence_passed_pending_remaining_gates_and_owner",
        "baseline_metrics": baseline_metrics,
        "candidates": candidates,
        "native_promoted_student": summary["promoted_student"],
        "audited_round": str(round_root),
        "prior_rounds": [json.loads(path.read_text()) for path in rounds[:-1]],
        "replay": replay_receipt,
        "replay_metric_comparison": delta,
        "operations": operations,
        "unified_data": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.state.resolve())
    write_json(args.state / "u4-physical-acceptance.json", result)
    print(
        json.dumps(
            {"status": result["engineering_status"], "runs": len(result["operations"])}
        )
    )


if __name__ == "__main__":
    main()
