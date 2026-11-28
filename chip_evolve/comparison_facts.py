"""Compare recorded result facts without invoking execution or replay."""

from __future__ import annotations

from typing import Any

from eda_toolkits.objectives import require_same_conditions

from .contracts import BusinessInputError, JSONValue, SingleResult
from .metrics import METRICS, metric_issues
from .result_io import wire_object
from .selection import result_violations, violations


def compare(reference: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    require_same_conditions(reference, candidate)
    if (
        reference["design_id"] != candidate["design_id"]
        or reference["objective_id"] != candidate["objective_id"]
    ):
        raise ValueError("Compare the same design and business objective")
    for name, frame in (("reference", reference), ("candidate", candidate)):
        invalid = metric_issues(frame)
        if invalid:
            raise ValueError("Invalid " + name + " metrics: " + ", ".join(invalid))
    deltas = {}
    for key in METRICS:
        old, new = reference["metrics"][key], candidate["metrics"][key]
        deltas[key] = {
            "reference": old,
            "candidate": new,
            "delta": new - old,
            "percent": 100 * (new - old) / abs(old) if old else None,
        }
    return {
        "reference_run_id": reference["run_id"],
        "candidate_run_id": candidate["run_id"],
        "condition_id": reference["condition_id"],
        "objective_id": reference["objective_id"],
        "deltas": deltas,
        "constraint_violations": violations(candidate),
        "professional_facts": {
            "reference": professional_facts(reference),
            "candidate": professional_facts(candidate),
        },
    }


def professional_facts(frame: dict[str, Any]) -> dict[str, Any]:
    """Keep the original professional decision separate from final feasibility."""
    native = frame.get("native_method")
    failed = violations(frame)
    metrics = frame.get("metrics")
    if not isinstance(metrics, dict):
        metrics = {}
    return {
        "run_id": frame["run_id"],
        "design_id": frame["design_id"],
        "objective_id": frame["objective_id"],
        "condition_id": frame["condition_id"],
        "native_method": native,
        "native_evidence_available": native is not None,
        "final_metrics": {key: metrics.get(key) for key in METRICS},
        "final_constraint_violations": failed,
        "final_feasible": not failed,
        "snapshot_ids": frame.get("snapshot_ids", {}),
    }


def compare_results(
    reference: SingleResult, candidate: SingleResult
) -> dict[str, JSONValue]:
    """Canonical comparison consumes explicit identities and validated metrics."""
    if (reference.design_id, reference.objective_id, reference.condition_id) != (
        candidate.design_id,
        candidate.objective_id,
        candidate.condition_id,
    ):
        raise BusinessInputError(
            "identity_mismatch",
            "$.condition_id",
            "Compare the same design and business objective/conditions",
        )
    deltas: dict[str, JSONValue] = {}
    for key, old, new in zip(
        METRICS,
        reference.metrics.quantities(),
        candidate.metrics.quantities(),
        strict=True,
    ):
        deltas[key] = {
            "reference": old,
            "candidate": new,
            "delta": new - old,
            "percent": 100 * (new - old) / abs(old) if old else None,
        }
    return {
        "reference_run_id": reference.run_id,
        "candidate_run_id": candidate.run_id,
        "condition_id": reference.condition_id,
        "objective_id": reference.objective_id,
        "deltas": deltas,
        "constraint_violations": result_violations(candidate),
        "professional_facts": {
            "reference": result_facts(reference),
            "candidate": result_facts(candidate),
        },
    }


def result_facts(result: SingleResult) -> dict[str, JSONValue]:
    failed = result_violations(result)
    # Additional native evidence is an explicit wire projection, not another result.
    from .contracts import PhysicalResult

    return {
        "run_id": result.run_id,
        "design_id": result.design_id,
        "objective_id": result.objective_id,
        "condition_id": result.condition_id,
        "native_method": wire_object(result.native_method.wire)
        if isinstance(result, PhysicalResult) and result.native_method
        else None,
        "native_evidence_available": isinstance(result, PhysicalResult)
        and result.native_method is not None,
        "final_metrics": dict(zip(METRICS, result.metrics.quantities(), strict=True)),
        "final_constraint_violations": failed,
        "final_feasible": not failed,
        "snapshot_ids": dict(result.snapshot_ids)
        if isinstance(result, PhysicalResult)
        else {},
    }
