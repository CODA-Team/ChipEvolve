"""Audit U3 raw native evidence and public EF execution receipts offline."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import zipfile
from pathlib import Path
from typing import Any

from accept_dplevolve_native import audit_metrics
from run_dplevolve_native import digest, now, source_inventory, write_json


def same_physical_result(original: dict[str, Any], replay: dict[str, Any]) -> bool:
    def stages(value: dict[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in value["hpwl_stages"].items() if k != "log"}

    return (
        stages(original) == stages(replay)
        and original["legality"].get("placement_violations")
        == replay["legality"].get("placement_violations")
        and original["displacement"] == replay["displacement"]
        and math.isclose(
            original["hpwl"]["after_micron"],
            replay["hpwl"]["after_micron"],
            abs_tol=0.001,
        )
    )


def check_operation(folder: Path) -> dict[str, Any]:
    request = json.loads((folder / "request.json").read_text())
    execution = json.loads((folder / "execution.json").read_text())
    leaf = (
        json.loads((folder / "leaf.json").read_text())
        if (folder / "leaf.json").exists()
        else {}
    )
    artifacts = execution["artifacts"]
    recorded_outputs = leaf.get("output_files", {})
    outputs_match = bool(recorded_outputs)
    if request["operation"].endswith("build"):
        outputs_match = outputs_match and all(
            sha in {a["sha256"] for a in artifacts} for sha in recorded_outputs.values()
        )
    elif (folder / "evidence.zip").is_file():
        with zipfile.ZipFile(folder / "evidence.zip") as bundle:
            for name, sha in recorded_outputs.items():
                for index, root in enumerate(request["outputs"]):
                    try:
                        relative = Path(name).relative_to(root)
                    except ValueError:
                        continue
                    member = "outputs/" + str(index) + "/" + relative.as_posix()
                    outputs_match = (
                        outputs_match
                        and member in bundle.namelist()
                        and hashlib.sha256(bundle.read(member)).hexdigest() == sha
                    )
                    break
                else:
                    outputs_match = False
    else:
        outputs_match = False
    return {
        "operation": request["operation"],
        "run_id": execution["run"]["run_id"],
        "successful": execution["run"]["status"] == "succeeded"
        and leaf.get("exit_code") == 0,
        "image_matches": request["toolchain"]["image_sha256"]
        == "8e6ee7aac233da078364649fa8111dac5de33a3589f5445dcffd96f9d6d8dd39",
        "source_and_inputs_match": leaf.get("request") == request,
        "outputs_match": outputs_match,
        "public_evidence": any(a["kind"] == "data_snapshot" for a in artifacts)
        and any(a["kind"] == "extractor_log" for a in artifacts),
        "receipt": str(folder / "execution.json"),
    }


def source_binary_bound(record: dict[str, Any]) -> bool:
    source = Path(record["source"])
    binary = Path(record["binary"])
    build = json.loads((binary.parent / "platform-build.json").read_text())
    return (
        source_inventory(source) == record["source_files"] == build["source_files"]
        and digest(binary) == record["binary_sha256"] == build["binary_sha256"]
        and Path(build["source"]).resolve() == source.resolve()
        and digest(Path(record["metrics"])) == record["metrics_sha256"]
    )


def within_native_runtime_budget(
    metrics: dict[str, Any], baseline: dict[str, Any]
) -> bool:
    runtime = metrics.get("runtime_seconds")
    reference = baseline.get("runtime_seconds")
    return (
        isinstance(runtime, (int, float))
        and isinstance(reference, (int, float))
        and math.isfinite(runtime)
        and math.isfinite(reference)
        and 0 < runtime <= 2 * reference
    )


def audit(state: Path) -> dict[str, Any]:
    evidence = json.loads((state / "evidence.json").read_text())
    checks: dict[str, bool] = {}
    metrics = {}
    profile = json.loads((state / "config.json").read_text())
    checks["fixed_common_toolchain"] = (
        profile["toolchain"]["openroad_base_commit"]
        == "27288f5c90265ae5296b2f5a9fa6e8714fa191ad"
        and profile["toolchain"]["orfs_base_commit"]
        == "5105b0a77fe8b3ae107bed67112eb5f83caca5d5"
        and digest(Path(profile["image"])) == profile["toolchain"]["image_sha256"]
    )
    for line, path in evidence["baselines"].items():
        metrics[line] = audit_metrics(
            Path(path), line=line, flow_variant=profile["flow_variant"]
        )
        checks["legal_baseline_" + line] = metrics[line]["accepted"]
    checks["three_canonical_baselines"] = set(metrics) == {
        "openroad_dpl_flow",
        "openroad_dpl_negotiation",
        "evolve_default",
    }
    operations = {}
    for key in evidence["required_operations"]:
        row = check_operation(state / "operations" / key)
        operations[key] = row
        for name in (
            "successful",
            "image_matches",
            "source_and_inputs_match",
            "outputs_match",
            "public_evidence",
        ):
            checks[key + ":" + name] = row[name]
    checks["all_deterministic_kinds"] = {
        row["operation"] for row in operations.values()
    } >= {"core_build", "variant_build", "baseline", "placement"}
    for name in evidence["required_steps"]:
        row = json.loads((state / "steps" / name / "receipt.json").read_text())
        checks["step:" + name] = row["status"] == "succeeded" and row["exit_code"] == 0
    candidate = evidence["candidate"]
    checks["candidate_source_binary_metrics_bound"] = source_binary_bound(candidate)
    checks["replay_source_binary_metrics_bound"] = source_binary_bound(
        evidence["replay"]
    )
    checks["same_fixed_replay_source"] = (
        candidate["source_files"] == evidence["replay"]["source_files"]
    )
    source = Path(candidate["source"])
    changed = subprocess.check_output(
        [
            "git",
            "diff",
            "--name-only",
            candidate["source_base_commit"],
            candidate["source_commit"],
        ],
        cwd=source,
        text=True,
    ).splitlines()
    checks["genuine_new_algorithm"] = any(
        Path(n).suffix in {".cpp", ".cxx", ".cc", ".h"} for n in changed
    )
    checks["stable_candidate_ref"] = (
        subprocess.check_output(
            ["git", "rev-parse", candidate["candidate_ref"]], cwd=source, text=True
        ).strip()
        == candidate["source_commit"]
    )
    checks["candidate_clean_at_fixed_commit"] = (
        subprocess.check_output(["git", "status", "--porcelain"], cwd=source, text=True)
        == ""
        and subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=source, text=True
        ).strip()
        == candidate["source_commit"]
    )
    candidate_metrics = audit_metrics(
        Path(candidate["metrics"]),
        line="evolve_default",
        flow_variant=profile["flow_variant"],
    )
    replay_metrics = audit_metrics(
        Path(evidence["replay"]["metrics"]),
        line="evolve_default",
        flow_variant=profile["flow_variant"],
    )
    checks["legal_candidate"] = candidate_metrics["accepted"]
    checks["legal_independent_replay"] = replay_metrics["accepted"]
    checks["candidate_native_runtime_budget"] = within_native_runtime_budget(
        candidate_metrics, metrics["openroad_dpl_flow"]
    )
    checks["replay_native_runtime_budget"] = within_native_runtime_budget(
        replay_metrics, metrics["openroad_dpl_flow"]
    )
    checks["same_physical_result"] = same_physical_result(
        json.loads(Path(candidate["metrics"]).read_text()),
        json.loads(Path(evidence["replay"]["metrics"]).read_text()),
    )
    checks["independent_source_and_binary"] = (
        Path(candidate["source"]).resolve()
        != Path(evidence["replay"]["source"]).resolve()
        and Path(candidate["binary"]).resolve()
        != Path(evidence["replay"]["binary"]).resolve()
    )
    checks["gates_passed"] = json.loads((state / "gates/receipt.json").read_text())[
        "passed"
    ]
    result = {
        "created_at": now(),
        "engineering_accepted": all(checks.values()),
        "business_acceptance": "pending",
        "checks": checks,
        "baselines": metrics,
        "operations": operations,
        "candidate": candidate_metrics,
        "replay": replay_metrics,
        "unified_data": False,
        "whole_platform_collaboration": False,
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["audit"])
    parser.add_argument("--run-root", type=Path, required=True)
    args = parser.parse_args()
    state = args.run_root.resolve()
    result = audit(state)
    write_json(state / "u3-acceptance.json", result)
    print(
        json.dumps(
            {
                "engineering_accepted": result["engineering_accepted"],
                "checks": len(result["checks"]),
                "failed": [k for k, v in result["checks"].items() if not v],
            }
        )
    )
    raise SystemExit(0 if result["engineering_accepted"] else 1)


if __name__ == "__main__":
    main()
