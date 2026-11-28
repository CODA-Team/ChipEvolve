"""Record explicit manual semantic judgments without inferring answer correctness.

This module is used by the implementing reviewer after inspecting the answer,
cited responses and independent native reference. It is never a model tool.
"""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


CHECKS = (
    "fixed_scope",
    "numeric_objects",
    "critical_sources",
    "causal_uncertainty",
    "case_success_conditions",
    "allowed_actions",
    "deadline",
)


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def record(dossier_path, output_path, judgments, *, policy=None):
    """All booleans and reasons must be supplied by the manual reviewer."""
    dossier_path, output_path = Path(dossier_path), Path(output_path)
    if output_path.exists():
        raise ValueError("Manual records are immutable; choose a new version")
    dossier = json.loads(dossier_path.read_text())
    episodes = {row["episode_id"]: row for row in dossier["episodes"]}
    reviews = []
    for episode_id, judgment in judgments.items():
        episode = episodes[episode_id]
        if "receipt" not in episode:
            raise ValueError("Cannot review an unrun prediction")
        if set(judgment["checks"]) != set(CHECKS):
            raise ValueError("Supply each of the seven manual checks")
        checks = []
        for name in CHECKS:
            passed, reason = judgment["checks"][name]
            if (
                type(passed) is not bool
                or not isinstance(reason, str)
                or not reason.strip()
            ):
                raise ValueError("Check needs explicit boolean and substantive reason")
            checks.append({"name": name, "passed": passed, "reason": reason})
        grade = judgment["grade"]
        critical = judgment["critical_error"]
        if (
            grade not in ("passed", "failed", "evidence_insufficient")
            or type(critical) is not bool
        ):
            raise ValueError("Invalid manual grade")
        if grade == "passed" and (critical or not all(row["passed"] for row in checks)):
            raise ValueError("A passing judgment cannot have a failing required check")
        answer = episode.get("answer")
        folder = Path(episode["receipt"]["folder"])
        cited = sorted(
            {
                cid
                for claim in (answer or {}).get("claims", [])
                for cid in claim.get("evidence_ids", [])
            }
        )
        files = []
        missing = []
        for cid in cited:
            path = folder / "evidence" / (cid + ".json")
            if path.is_file():
                files.append({"path": str(path), "sha256": digest(path)})
            else:
                missing.append(cid)
        result_path = folder / "result.json"
        state_paths = (
            list((folder / "investigations").glob("*/state.json"))
            if episode["arm"] in ("D", "E")
            else [folder / "state.json"]
        )
        state_file = (
            state_paths[0]
            if len(state_paths) == 1 and state_paths[0].is_file()
            else None
        )
        reviews.append(
            {
                "episode_id": episode_id,
                "grade": grade,
                "critical_error": critical,
                "reasonable_refusal": judgment["reasonable_refusal"],
                "purposeful_progress": judgment["purposeful_progress"],
                "reviewed_at": datetime.now(timezone.utc).isoformat(),
                "reviewer": "implementing Codex agent; independent raw native reference, not externally blinded",
                "dossier": {"path": str(dossier_path), "sha256": digest(dossier_path)},
                "checks": checks,
                "critical_evidence_files": files,
                "missing_cited_files": missing,
                "missing_cited_files_note": "An excerpt may be persisted in state rather than a separate file. Absence here alone does not invalidate a citation; validate its parent, pointer and text against the original response.",
                "state_file": {"path": str(state_file), "sha256": digest(state_file)}
                if state_file
                else None,
                "answer_sha256": hashlib.sha256(
                    json.dumps(answer, ensure_ascii=False, sort_keys=True).encode()
                ).hexdigest(),
                "cli_result": {"path": str(result_path), "sha256": digest(result_path)}
                if result_path.is_file()
                else None,
            }
        )
    output_path.write_text(
        json.dumps({"policy": policy, "reviews": reviews}, ensure_ascii=False, indent=2)
        + "\n"
    )
    return {
        "output": str(output_path),
        "reviews": len(reviews),
        "passed": sum(row["grade"] == "passed" for row in reviews),
    }
