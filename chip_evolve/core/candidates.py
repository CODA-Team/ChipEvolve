"""Deliver all measured branches without inventing a business winner."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from chip_evolve.core.config import write
from chip_evolve.core.contracts import CandidateCollection
from chip_evolve.core.jobs import digest
from chip_evolve.core.result_io import load_result, load_single_result, wire_object
from chip_evolve.core.selection import violations

SCHEMA = "chip-evolve.candidate-delivery.v1"


def result_frame(path: Path) -> dict[str, Any]:
    """Explicit legacy wire facade over the canonical validated reader."""
    return wire_object(load_single_result(path, physical=True).wire)


def expand_results(paths: list[Path]) -> list[Path]:
    expanded = []
    for path in paths:
        result = load_result(path)
        if isinstance(result, CandidateCollection):
            expanded.extend(row.origin.path for row in result.candidates)
        else:
            expanded.append(result.origin.path)
    return list(dict.fromkeys(expanded))


def deliver_candidates(
    experiment: Path,
    paths: list[Path],
    *,
    native_campaign: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rows = []
    for path in paths:
        frame = result_frame(path)
        failed = violations(frame)
        rows.append(
            {
                "result": str(path.resolve()),
                "sha256": digest(path),
                "run_id": frame["run_id"],
                "design_id": frame["design_id"],
                "objective_id": frame["objective_id"],
                "condition_id": frame["condition_id"],
                "metrics": frame["metrics"],
                "constraint_violations": failed,
                "final_feasible": not failed,
            }
        )
    if (
        not rows
        or len({(r["design_id"], r["objective_id"], r["condition_id"]) for r in rows})
        != 1
    ):
        raise ValueError(
            "Deliver nonempty candidates for the same design and conditions"
        )
    delivery = {
        "schema_version": SCHEMA,
        "design_id": rows[0]["design_id"],
        "objective_id": rows[0]["objective_id"],
        "condition_id": rows[0]["condition_id"],
        "execution_state": "succeeded",
        "delivery_state": "completed",
        "candidate_results": rows,
        "selected_source": None,
        "validation": None,
        "adopted": False,
        "interpretation": "Codex selects an explicit branch; native promotion is unchanged. Final feasibility does not establish logical validation or adoption.",
    }
    if native_campaign is not None:
        delivery.update(
            execution_state=native_campaign["status"],
            native_campaign=native_campaign,
            native_search_completed=False,
            evidence_only=True,
        )
    write(experiment / "result.json", delivery)
    return delivery
