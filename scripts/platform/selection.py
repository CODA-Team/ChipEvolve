"""Expose the original promotion rules as a read-only platform receipt."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from runtime_paths import resolve_runtime_paths
from scripts.teacher_loop.evidence import (
    best_round_candidate,
    discover_case_metrics,
    source_repo_ref_for_candidate,
    value_reference_anchor,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True)
    parser.add_argument("--flow-variant", required=True)
    parser.add_argument("--round-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    runtime = resolve_runtime_paths(
        anchor_file=__file__, agent_root_levels_up=2, script_name="platform_selection"
    )
    metrics = discover_case_metrics(
        orfs_root=runtime.orfs_root, case_id=args.case, flow_variant=args.flow_variant
    )
    candidate = best_round_candidate(
        runtime=runtime,
        case_id=args.case,
        flow_variant=args.flow_variant,
        round_id=args.round_id,
        baseline=value_reference_anchor(metrics)[1],
        require_baseline_beat=True,
    )
    source = source_repo_ref_for_candidate(
        round_dir=runtime.state_root / args.round_id / "teacher_rounds",
        round_id=args.round_id,
        case_id=args.case,
        candidate=candidate,
    )
    receipt = {
        "accepted": candidate is not None,
        "candidate": candidate.tag if candidate else None,
        "source_ref": str(source[1]) if source else None,
        "source_repo": str(source[0]) if source else None,
        "rule": "native best_round_candidate(require_baseline_beat=True)",
    }
    args.output.write_text(json.dumps(receipt, indent=2) + "\n")


if __name__ == "__main__":
    main()
