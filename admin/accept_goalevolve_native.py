"""Audit native GoalEvolve results; simulation never satisfies EDA acceptance."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from run_dplevolve_native import digest, now, write_json
from run_goalevolve_native import control_inventory

SURFACE = ("src/rsz", "src/rmp")
SUFFIXES = {".cc", ".cpp", ".cxx", ".hh", ".hpp", ".h", ".tcl"}
METRICS = ("tns_abs_ns", "dynamic_power_pw", "leakage_power_pw")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text()) if path.is_file() else {}


def surface_inventory(source: Path) -> tuple[dict[str, str], str]:
    files = sorted(
        path
        for relative in SURFACE
        for path in (source / relative).rglob("*")
        if path.is_file() and path.suffix in SUFFIXES
    )
    hasher = hashlib.sha256()
    inventory = {}
    for path in files:
        relative = str(path.relative_to(source))
        content = path.read_bytes()
        hasher.update(relative.encode())
        hasher.update(content)
        inventory[relative] = hashlib.sha256(content).hexdigest()
    return inventory, hasher.hexdigest()


def metric_row(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    with path.open(newline="") as stream:
        rows = [row for row in csv.DictReader(stream) if row.get("design")]
    return rows[-1] if rows else {}


def audit_candidate(candidate_path: Path, seed: Path) -> dict[str, Any]:
    candidate = read_json(candidate_path)
    artifacts = candidate.get("artifacts", {})
    source = Path(artifacts.get("candidate_source", "/nonexistent"))
    original, _ = surface_inventory(seed)
    observed, source_hash = surface_inventory(source)
    changed = sorted(
        name
        for name in original.keys() | observed.keys()
        if original.get(name) != observed.get(name)
    )
    native_checks = {row["name"]: row["passed"] for row in candidate.get("checks", [])}
    output = candidate_path.parent / "contest_output"
    log_path = Path(artifacts.get("evaluation_log", "/nonexistent"))
    official_path = Path(artifacts.get("official_4of4_log", "/nonexistent"))
    csv_path = Path(artifacts.get("metrics_csv", "/nonexistent"))
    log = log_path.read_text(errors="replace") if log_path.is_file() else ""
    official = (
        official_path.read_text(errors="replace") if official_path.is_file() else ""
    )
    row = metric_row(csv_path)
    metrics = candidate.get("metrics", {})
    parsed = {}
    if row:
        parsed = {
            "tns_abs_ns": abs(float(row["tns"])),
            "dynamic_power_pw": float(row["total_power"]) - float(row["leakage_power"]),
            "leakage_power_pw": float(row["leakage_power"]),
        }
    binary = candidate_path.parent.parent / "workspace/build_goalevolve/bin/openroad"
    checks = {
        "real_cpp_change": any(
            Path(name).suffix in {".cc", ".cpp", ".cxx"} for name in changed
        ),
        "native_patch_recorded": bool(candidate.get("implementation_diff")),
        "source_content_matches_candidate": bool(observed)
        and source_hash == candidate.get("source_commit"),
        "native_build_flow_metrics_placement_validity": all(
            native_checks.get(name) is True
            for name in ("build", "flow", "metrics", "placement", "lec")
        ),
        "no_evaluation_error": candidate.get("evaluation_error") is None,
        "private_binary": binary.is_file(),
        "same_output_sources": log_path == output / "evaluation.log"
        and csv_path == output / "metrics.csv",
        "real_flow_completed": "GOALEVOLVE_CHECKPOINT_END post_route" in log
        and "[INFO] Flow running time:" in log,
        "official_four_checks": "SUMMARY: 4/4 checks passed" in official,
        "metrics_match_csv": all(
            name in parsed
            and name in metrics
            and math.isfinite(float(metrics[name]))
            and math.isclose(
                float(metrics[name]), parsed[name], rel_tol=1e-12, abs_tol=1e-9
            )
            for name in METRICS
        ),
        "zero_drvs": bool(row)
        and all(
            row.get(name) not in (None, "") and float(row[name]) == 0
            for name in ("slew_over_count", "cap_over_count", "fanout_over_count")
        ),
        "physical_outputs": all(
            (output / name).is_file()
            for name in (
                "post_route.odb",
                "aes_cipher_top.def",
                "aes_cipher_top.v",
            )
        ),
    }
    evidence = {
        str(path): digest(path)
        for path in (candidate_path, log_path, official_path, csv_path, binary)
        if path.is_file()
    }
    return {
        "student_id": candidate.get("student_id"),
        "checks": checks,
        "passed": all(checks.values()),
        "changed_files": changed,
        "source_content_hash": source_hash,
        "metrics": metrics,
        "evidence_sha256": evidence,
    }


def audit(run_root: Path) -> dict[str, Any]:
    source = run_root / "source"
    campaign = run_root / "p0/aes_cipher_top/l3_aes_20261011"
    baseline = read_json(campaign / "baseline/baseline.json")
    profile = read_json(campaign / "config/evolve.json")
    round_root = campaign / "campaign/rounds/round_001"
    round_result = read_json(round_root / "round.json")
    ae2 = read_json(
        source / "outputs/ae2/aes_cipher_top_student_code/report/ae2_report.json"
    )
    seed = source / "artifact_evaluation/lineage/openroad_power/p0/source"
    candidates = [
        audit_candidate(path, seed)
        for path in sorted(round_root.glob("students/*/artifacts/candidate.json"))
    ]
    checks: dict[str, bool] = {}
    for name in (
        "native-check",
        "control-smoke",
        "p0-init",
        "p0-baseline",
        "ae2-replay2",
    ):
        receipt = read_json(run_root / "qualification/steps" / name / "receipt.json")
        checks[f"step_{name}"] = (
            receipt.get("status") == "succeeded" and receipt.get("source_changed") == []
        )
    checks["ae2_published_tolerances_and_validity"] = ae2.get("passed") is True
    inputs = read_json(run_root / "inputs-manifest.json")
    checks["design_and_library_inputs_unchanged"] = bool(inputs.get("files")) and all(
        (source / name).is_file() and digest(source / name) == expected
        for name, expected in inputs.get("files", {}).items()
    )
    for name in ("workspace-regression", "data-regression"):
        receipt = read_json(run_root / "qualification/steps" / name / "receipt.json")
        checks[name] = receipt.get("status") == "succeeded"
    upstream = read_json(
        run_root / "qualification/steps/upstream-original-unit-local/receipt.json"
    )
    checks["upstream_unit_regression_all_passed"] = (
        upstream.get("status") == "succeeded"
    )
    checks["baseline_real_and_valid"] = baseline.get("ok") is True and all(
        any(
            check.get("name") == name and check.get("passed") is True
            for check in baseline.get("checks", [])
        )
        for name in ("build", "flow", "metrics", "placement", "lec")
    )
    checks["frozen_measured_baseline"] = bool(baseline.get("metrics")) and all(
        profile.get("baseline_metrics", {}).get(name)
        == baseline.get("metrics", {}).get(name)
        for name in METRICS
    )
    checks["original_policy_and_four_students"] = (
        profile.get("planning_mode") == "ast_graph"
        and profile.get("promotion") == "power_first_promotion"
        and profile.get("students") == [f"student_{i}" for i in range(1, 5)]
        and profile.get("allowed_patch_roots") == list(SURFACE)
        and profile.get("require_cpp_patch") is True
        and profile.get("target_metrics")
        == {
            "tns_abs_ns": 12.0,
            "dynamic_power_pw": 350000000000.0,
            "leakage_power_pw": 35000000.0,
        }
    )
    evolution = read_json(run_root / "steps/evolution/receipt.json")
    checks["bounded_native_evolution_completed"] = (
        evolution.get("status") == "succeeded" and evolution.get("source_changed") == []
    )
    checks["one_round_four_results"] = (
        round_result.get("student_count") == 4 and len(candidates) == 4
    )
    checks["at_least_one_valid_new_cpp_candidate"] = any(
        row["passed"] for row in candidates
    )
    checks["selection_and_reasons_recorded"] = bool(
        round_result.get("results")
    ) and all(
        "verdict" in row and "reasons" in row["verdict"]
        for row in round_result.get("results", [])
    )
    frozen = read_json(run_root / "control-manifest.json")
    checks["evolution_controls_unchanged"] = bool(frozen) and frozen.get(
        "files"
    ) == control_inventory(source)
    return {
        "schema": "eda-development.l3-goalevolve-native-acceptance.v1",
        "created_at": now(),
        "passed": all(checks.values()),
        "checks": checks,
        "baseline_metrics": baseline.get("metrics", {}),
        "ae2": ae2,
        "candidates": candidates,
        "promoted_student": round_result.get("promoted_student"),
        "token_usage": round_result.get("token_usage", {}),
        "smoke_is_mock": True,
        "lec_is_structural_not_boolean_equivalence": True,
        "unified_execution": False,
        "unified_data": False,
        "business_accepted": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, required=True)
    args = parser.parse_args()
    root = args.run_root.resolve()
    report = audit(root)
    write_json(root / "l3-acceptance.json", report)
    print(
        json.dumps(
            {"passed": report["passed"], "checks": report["checks"]}, ensure_ascii=False
        )
    )
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
