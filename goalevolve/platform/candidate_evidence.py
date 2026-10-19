"""Read completed native evidence; final PPA judgment belongs to the caller."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from goalevolve.evaluation.evidence import REQUIRED_CHECKS


def reference(path: Path) -> dict[str, str]:
    return {
        "path": str(path.resolve()),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def export(profile: dict[str, Any]) -> dict[str, Any]:
    rounds = Path(profile["state_root"]) / "campaign/rounds"
    candidates = []
    for folder in sorted(rounds.glob("round_*")):
        # epd_search uses round zero for retrieval traces, before any Student
        # round. Preserve that evidence without treating it as unfinished work.
        if folder.name == "round_000" and not (folder / "students").exists():
            continue
        if not (folder / "round.json").is_file():
            raise ValueError("Candidate export requires a completed native round")
        for path in sorted(folder.glob("students/*/artifacts/candidate.json")):
            candidate = json.loads(path.read_text())
            verdict_path = path.with_name("evidence.json")
            verdict = json.loads(verdict_path.read_text())
            checks = {row["name"]: row["passed"] for row in candidate["checks"]}
            problems = [name for name in REQUIRED_CHECKS if not checks.get(name, False)]
            if (
                not verdict["integrity_ok"]
                or candidate.get("evaluation_error")
                or candidate.get("legacy")
            ):
                problems.append("native_integrity_not_admitted")
            checkpoint = candidate["artifacts"].get("checkpoint_post_route_db")
            odb = Path(checkpoint) if checkpoint else None
            if odb is None or not odb.is_file():
                problems.append("missing_completed_checkpoint")
            candidates.append(
                {
                    "candidate_id": folder.name + "-" + candidate["student_id"],
                    "checkpoint": str(odb.resolve()) if odb else None,
                    "checkpoint_sha256": reference(odb)["sha256"]
                    if odb and odb.is_file()
                    else None,
                    "native_record": reference(path),
                    "native_verdict_record": reference(verdict_path),
                    "native_verdict": verdict,
                    "native_artifact_problems": problems,
                    "eligible_for_common_measurement": not problems,
                    "source_ref": candidate["source_commit"],
                    "hypothesis": candidate["hypothesis"],
                }
            )
    return {
        "capability": "goal",
        "design_id": profile["design_id"],
        "design": profile["design"],
        "candidates": candidates,
        "interpretation": "Original integrity and quality verdicts retained. This does not promote a source or establish final PPA/functional acceptance.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = export(json.loads(args.profile.read_text()))
    args.output.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
