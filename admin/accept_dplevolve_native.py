"""Audit one native DPLEvolve reproduction from its preserved real evidence."""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
from pathlib import Path
from typing import Any

from run_dplevolve_native import digest, now, source_inventory, write_json

CANONICAL_LINES = (
    "openroad_dpl_flow",
    "openroad_dpl_negotiation",
    "evolve_default",
)


def audit_metrics(path: Path, line: str, flow_variant: str) -> dict[str, Any]:
    data = json.loads(path.read_text())
    hpwl = data.get("hpwl", {})
    legality = data.get("legality", {})
    manifest = data.get("manifest", {})
    final = hpwl.get("after_micron")
    log_path = Path(hpwl.get("log", "/missing"))
    log = log_path.read_text() if log_path.is_file() else ""
    values = re.findall(
        r"^\[INFO DPL-0022\]\s+HPWL after\s+([0-9.+eE-]+)\s+u",
        log,
        re.MULTILINE,
    )
    supporting = data.get("supporting_files", {})
    raw_path = path.parent / supporting.get("raw_metrics_json", "missing-raw-metrics")
    post_path = path.parent / supporting.get(
        "post_metrics_summary_json", "missing-post-metrics"
    )
    raw = json.loads(raw_path.read_text()) if raw_path.is_file() else {}
    post = json.loads(post_path.read_text()) if post_path.is_file() else {}
    expected_checker = (
        "check_placement_evolve" if line == "evolve_default" else "check_placement"
    )
    checks = {
        "status_ok": data.get("status") == "ok"
        and data.get("legalize_exit_status") == 0,
        "expected_scope": manifest.get("line") == line
        and manifest.get("flow_variant") == flow_variant
        and manifest.get("input_stage") == "3_4_place_resized",
        "legality_present_and_clean": "placement_violations" in legality
        and str(legality["placement_violations"]).strip().lower()
        in {"", "0", "clean", "none"}
        and post.get("status") == "ok"
        and post.get("check_command") == expected_checker
        and raw.get("detailedplace__design__violations") == 0,
        "canonical_hpwl": hpwl.get("source") == "openroad_dpl_log"
        and isinstance(final, (int, float))
        and math.isfinite(final)
        and final > 0,
        "matches_raw_final_log": bool(values)
        and isinstance(final, (int, float))
        and math.isclose(final, float(values[-1]), abs_tol=0.001),
        "runtime_measured": isinstance(data.get("runtime_seconds"), (int, float))
        and data["runtime_seconds"] > 0,
    }
    return {
        "path": str(path),
        "sha256": digest(path),
        "checks": checks,
        "accepted": all(checks.values()),
        "hpwl_micron": final,
        "runtime_seconds": data.get("runtime_seconds"),
        "displacement": data.get("displacement"),
        "raw_log_sha256": digest(log_path) if log_path.is_file() else None,
        "raw_metrics_sha256": digest(raw_path) if raw_path.is_file() else None,
    }


def audit_candidate_source(record: dict[str, Any]) -> dict[str, bool]:
    source = Path(record["source_repo"])

    def git(*args: str) -> str:
        return subprocess.check_output(["git", *args], cwd=source, text=True).strip()

    changed_files = git(
        "diff", "--name-only", record["source_base_commit"], record["source_commit"]
    ).splitlines()
    binary = Path(record["binary"])
    return {
        "pinned_source": git("rev-parse", record["candidate_ref"])
        == record["source_commit"]
        == git("rev-parse", "HEAD"),
        "source_clean": git("status", "--porcelain") == "",
        "new_algorithm_source": any(
            Path(name).suffix in {".cpp", ".cxx", ".cc", ".h", ".tcl"}
            for name in changed_files
        ),
        "frozen_source_unchanged": source_inventory(source) == record["source_files"],
        "same_binary_after_evaluation": digest(binary) == record["binary_sha256"],
        "same_input_odb": digest(Path(record["input_odb"]))
        == record["input_odb_sha256"],
        "same_input_sdc": digest(Path(record["input_sdc"]))
        == record["input_sdc_sha256"],
        "same_metrics": digest(Path(record["metrics_path"]))
        == record["metrics_sha256"],
    }


def audit(run_root: Path) -> dict[str, Any]:
    evidence = json.loads((run_root / "native-evidence.json").read_text())
    config = json.loads((run_root / "config.json").read_text())
    checks: dict[str, bool] = {}
    step_rows = {}
    for name in evidence["required_steps"]:
        step = run_root / "steps" / name
        row = json.loads((step / "receipt.json").read_text())
        checks[f"step_{name}"] = (
            row["status"] == "succeeded"
            and row["exit_code"] == 0
            and row["source_changed"] == []
            and digest(step / "output.log") == row["log_sha256"]
            and digest(step / "config.json") == row["config_sha256"]
        )
        step_rows[name] = row
    source_manifest = json.loads((run_root / "source-manifest.json").read_text())
    checks["control_source_unchanged"] = (
        source_inventory(Path(source_manifest["source"])) == source_manifest["files"]
    )
    baseline_rows = {
        line: audit_metrics(
            Path(evidence["baselines"][line]), line, config["flow_variant"]
        )
        for line in CANONICAL_LINES
    }
    checks.update(
        {f"baseline_{line}": row["accepted"] for line, row in baseline_rows.items()}
    )
    round_manifest = json.loads(Path(evidence["round_manifest"]).read_text())
    launch_command = step_rows[evidence["launch_step"]]["command"]
    baseline_freeze = json.loads(Path(evidence["baseline_freeze"]).read_text())
    checks["baseline_and_inputs_unchanged"] = all(
        digest(Path(path)) == sha for path, sha in baseline_freeze["files"].items()
    )
    checks["real_native_round"] = (
        round_manifest["launch"] is True
        and round_manifest["dry_run"] is False
        and (
            bool(round_manifest["baseline_preflight_commands"])
            or "--reuse-baseline-preflight" in launch_command
        )
        and "--skip-baseline-preflight" not in launch_command
        and round_manifest["case"] == config["case"]
        and round_manifest["flow_variant"] == config["flow_variant"]
    )
    operations = []
    for path in evidence["operation_summaries"]:
        summary = json.loads(Path(path).read_text())
        checks[f"model_{summary['operation_id']}"] = (
            summary["returncode"] == 0
            and bool(summary["thread_id"])
            and summary["agent_message_count"] > 0
        )
        operations.append(summary)
    checks["teacher_student_review_recorded"] = len(operations) >= 3
    candidate = evidence["candidate"]
    checks.update(audit_candidate_source(candidate))
    candidate_metrics = audit_metrics(
        Path(candidate["metrics_path"]), "evolve_default", config["flow_variant"]
    )
    checks["candidate_metrics"] = candidate_metrics["accepted"]
    build_command = step_rows[candidate["build_step"]]["command"]
    evaluation_command = step_rows[candidate["evaluation_step"]]["command"]
    checks["explicit_candidate_build"] = (
        "--dpl-src" in build_command
        and build_command[build_command.index("--dpl-src") + 1]
        == candidate["source_repo"]
    )
    checks["explicit_candidate_evaluation"] = (
        "--openroad-binary" in evaluation_command
        and evaluation_command[evaluation_command.index("--openroad-binary") + 1]
        == candidate["binary"]
    )
    baseline_hpwl = baseline_rows["openroad_dpl_flow"]["hpwl_micron"]
    return {
        "audited_at": now(),
        "checks": checks,
        "engineering_accepted": all(checks.values()),
        "business_acceptance": "pending owner review",
        "unified_execution": False,
        "unified_data": False,
        "baselines": baseline_rows,
        "candidate": {**candidate, "metrics_audit": candidate_metrics},
        "candidate_hpwl_reduction_pct": 100
        * (baseline_hpwl - candidate_metrics["hpwl_micron"])
        / baseline_hpwl,
        "model_operations": operations,
        "limitations": [
            "Native reproduction is not a platform integration acceptance.",
            "Detailed-placement HPWL is not final routed PPA.",
            "One small design and one bounded round do not prove general optimization quality.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, required=True)
    args = parser.parse_args()
    output = args.run_root / "l2-acceptance.json"
    if output.exists():
        parser.error("Acceptance exists; preserve it and select a fresh audit output.")
    result = audit(args.run_root.resolve())
    write_json(output, result)
    print(
        json.dumps({"output": str(output), "accepted": result["engineering_accepted"]})
    )
    raise SystemExit(0 if result["engineering_accepted"] else 1)


if __name__ == "__main__":
    main()
