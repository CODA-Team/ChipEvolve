"""Export completed native candidates without altering the native winner."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from runtime_paths import resolve_runtime_paths
from scripts.repo.case_registry import get_case
from scripts.teacher_loop.evidence import (
    candidate_artifact_problems,
    discover_round_candidate_metrics,
    source_repo_ref_for_candidate,
)
from scripts.teacher_loop.orchestrator import runtime_with_round_outputs


def reference(path: Path) -> dict[str, str]:
    return {
        "path": str(path.resolve()),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def export(profile: dict[str, Any], round_id: str) -> dict[str, Any]:
    runtime = resolve_runtime_paths(
        anchor_file=str(Path(profile["agent_root"]) / "scripts/platform/selection.py"),
        agent_root_levels_up=2,
        script_name="platform_candidate_evidence",
    )
    runtime = runtime_with_round_outputs(runtime, runtime.state_root / round_id)
    case = get_case(profile["case"])
    round_dir = runtime.state_root / round_id / "teacher_rounds"
    candidates = []
    for candidate in discover_round_candidate_metrics(
        orfs_root=runtime.orfs_root,
        case_id=profile["case"],
        flow_variant=profile["flow_variant"],
        round_id=round_id,
    ):
        problems = candidate_artifact_problems(
            runtime=runtime,
            round_dir=round_dir,
            round_id=round_id,
            case_id=profile["case"],
            candidate=candidate,
        )
        source = source_repo_ref_for_candidate(
            round_dir=round_dir,
            round_id=round_id,
            case_id=profile["case"],
            candidate=candidate,
        )
        odb = (
            runtime.orfs_root
            / "flow/results"
            / case.platform
            / case.design
            / profile["flow_variant"]
            / "dpl_evolve_baseline"
            / candidate.tag
            / "legalized.odb"
        )
        if not odb.is_file():
            problems.append("missing_completed_checkpoint")
        candidates.append(
            {
                "candidate_id": candidate.tag,
                "checkpoint": str(odb.resolve()),
                "checkpoint_sha256": reference(odb)["sha256"]
                if odb.is_file()
                else None,
                "native_record": reference(candidate.metrics_path),
                "native_artifact_problems": problems,
                "eligible_for_common_measurement": not problems,
                "source_repo": str(source[0]) if source else None,
                "source_ref": str(source[1]) if source else None,
            }
        )
    return {
        "capability": "dpl",
        "design": case.design,
        "platform": case.platform,
        "case": profile["case"],
        "round_id": round_id,
        "candidates": candidates,
        "interpretation": "Read-only native artifact gates; no HPWL re-ranking, promotion or EDA.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--round-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    profile = json.loads(args.profile.read_text())
    os.environ.update(
        DPL_EVOLVE_AGENT_ROOT=profile["agent_root"],
        DPL_EVOLVE_STATE_ROOT=profile["state_root"],
        ORFS_ROOT=profile["orfs_root"],
    )
    result = export(profile, args.round_id)
    args.output.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
