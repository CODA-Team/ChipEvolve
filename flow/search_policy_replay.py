"""Pure replay-evidence analysis used by the campaign search policy.

The state machine remains in :mod:`search_policy`.  This module only classifies
lineage recipes from already-ranked records.  Record interpretation is injected
as callbacks so the compatibility facade can retain its existing helper API and
monkeypatch behavior.
"""

from __future__ import annotations

import math
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple


RankedRecords = Sequence[Tuple[float, Mapping[str, Any]]]


def finite_float(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def record_metrics(record: Mapping[str, Any]) -> Mapping[str, Any]:
    metrics = record.get("metrics")
    return metrics if isinstance(metrics, Mapping) else record


def is_lineage_candidate(record: Mapping[str, Any]) -> bool:
    """Clean rows can confirm a recipe, but must never create/reset its seed."""
    kind = str(record.get("lineage_kind") or "").strip().lower()
    if kind == "clean":
        return False
    if kind in {"cts", "routing"}:
        return True
    stage = str(record.get("stage") or "").strip().lower()
    if stage in {"cts", "routing"}:
        return True
    stage_record = record.get("stage_record")
    return (isinstance(stage_record, Mapping)
            and str(stage_record.get("stage") or "").strip().lower()
            in {"cts", "routing"})


def replay_tolerance(reference: float, policy: Mapping[str, Any]) -> float:
    return max(
        float(policy["config_replay_abs_tolerance"]),
        abs(float(reference)) * float(policy["config_replay_rel_tolerance"]),
    )


def median(values: Sequence[float]) -> float:
    ordered = sorted(float(value) for value in values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2.0


def analyze_replays(
    clean_records: Sequence[Mapping[str, Any]],
    clean_ranked: RankedRecords,
    resolved_ranked: RankedRecords,
    routing_ranked: RankedRecords,
    policy: Mapping[str, Any],
    objective: str,
    context: Mapping[str, Any],
    objective_fn: Optional[Callable[[Mapping[str, Any]], Optional[float]]],
    *,
    is_lineage_candidate_fn: Callable[[Mapping[str, Any]], bool],
    record_params_fn: Callable[[Mapping[str, Any]], Dict[str, float]],
    record_recipe_fn: Callable[[Mapping[str, Any]], Optional[Dict[str, Any]]],
    record_iteration_fn: Callable[[Mapping[str, Any]], int],
    replay_signature_fn: Callable[[Mapping[str, Any], int], str],
    meaningfully_better_fn: Callable[[float, float, Mapping[str, Any]], bool],
    serialize_best_fn: Callable[
        [Optional[Mapping[str, Any]], Optional[float], str, int],
        Optional[Dict[str, Any]],
    ],
    replay_tolerance_fn: Callable[[float, Mapping[str, Any]], float],
    confirmation_evidence_fn: Callable[
        [Mapping[str, Any], str], Tuple[bool, List[str]]],
    objective_value_fn: Callable[..., Optional[float]],
    median_fn: Callable[[Sequence[float]], float],
) -> Dict[str, Any]:
    """Classify lineage recipes as collecting, promoted, or disproved."""
    decimals = int(policy["signature_decimals"])
    clean_best = clean_ranked[0][0] if clean_ranked else None
    candidates: Dict[str, Dict[str, Any]] = {}
    for source, ranked in (("observed_effective", resolved_ranked),
                           ("routing_child", routing_ranked)):
        for value, record in ranked:
            if not is_lineage_candidate_fn(record):
                continue
            record_params_fn(record)
            recipe = record_recipe_fn(record)
            if recipe is None:
                # Flat 12D rows omit the physical parent context and are report-only.
                continue
            signature = str(recipe["signature"])
            has_later_attempt = any(
                record_iteration_fn(clean) > record_iteration_fn(record)
                and replay_signature_fn(clean, decimals) == signature
                for clean in clean_records
            )
            if (clean_best is not None
                    and not meaningfully_better_fn(value, clean_best, policy)
                    and not has_later_attempt):
                continue
            item = serialize_best_fn(record, value, source, decimals)
            if item is None:
                continue
            previous = candidates.get(signature)
            if previous is None or value < previous["objective"]:
                first_observed = min(
                    int(item["iteration"]),
                    int((previous or {}).get(
                        "first_observed_iteration", item["iteration"])),
                )
                item["first_observed_iteration"] = first_observed
                candidates[signature] = item
            else:
                previous["first_observed_iteration"] = min(
                    int(previous.get(
                        "first_observed_iteration", previous["iteration"])),
                    int(item["iteration"]),
                )

    pending: List[Dict[str, Any]] = []
    statuses: List[Dict[str, Any]] = []
    promoted: List[Dict[str, Any]] = []
    required = int(policy["config_replay_required_successes"])
    max_attempts = int(policy["config_replay_max_attempts"])
    for signature, item in candidates.items():
        recipe = item.get("config_recipe")
        if not isinstance(recipe, Mapping):
            pending.append(item)
            continue
        attempts = []
        tolerance = replay_tolerance_fn(float(item["objective"]), policy)
        first_observed = int(item.get(
            "first_observed_iteration", item["iteration"]))
        matching = []
        seen_executions = set()
        for record in sorted(
                clean_records,
                key=lambda row: (
                    record_iteration_fn(row), str(row.get("run_id", "")))):
            if record_iteration_fn(record) <= first_observed:
                continue
            if replay_signature_fn(record, decimals) != signature:
                continue
            execution = (record_iteration_fn(record), record.get("run_id"))
            if execution[1] is None or execution in seen_executions:
                continue
            seen_executions.add(execution)
            matching.append(record)

        # The first bounded replay campaign is terminal; incidental later runs cannot
        # resurrect a recipe that reached its maximum number of attempts.
        ignored_attempts = max(0, len(matching) - max_attempts)
        for record in matching[:max_attempts]:
            evidence_valid, rejection_reasons = confirmation_evidence_fn(
                record, objective)
            value = None
            if evidence_valid:
                value = objective_value_fn(
                    record,
                    objective,
                    power_budget=context.get("power_budget"),
                    power_base=context.get("power_base"),
                    wl_base=float(context.get("wl_base", 1.0)),
                    ecp_base=float(context.get("ecp_base", 1.0)),
                    weight_wl=float(context.get("weight_wl", 0.5)),
                    weight_ecp=float(context.get("weight_ecp", 0.5)),
                    objective_fn=objective_fn,
                )
            if evidence_valid and value is None:
                rejection_reasons.append("objective_missing_or_infeasible")
            delta = (None if value is None
                     else abs(float(value) - float(item["objective"])))
            attempts.append({
                "iteration": record_iteration_fn(record),
                "run_id": record.get("run_id"),
                "objective": value,
                "delta": delta,
                "evidence_valid": evidence_valid and value is not None,
                "rejection_reasons": rejection_reasons,
                "matched": bool(delta is not None and delta <= tolerance),
            })
        successes = [attempt for attempt in attempts if attempt["matched"]]
        status = ("promoted" if len(successes) >= required else
                  "disproved" if len(attempts) >= max_attempts else "collecting")
        evidence = {
            "recipe_signature": signature,
            "status": status,
            "reference_objective": float(item["objective"]),
            "tolerance": tolerance,
            "required_successes": required,
            "max_attempts": max_attempts,
            "attempt_count": len(attempts),
            "ignored_attempt_count": ignored_attempts,
            "success_count": len(successes),
            "attempts": attempts,
        }
        statuses.append(evidence)
        if status == "collecting":
            queued = dict(item)
            queued["replay_evidence"] = evidence
            pending.append(queued)
        elif status == "promoted":
            values = [float(attempt["objective"]) for attempt in successes]
            center = median_fn(values)
            promoted_item = dict(item)
            promoted_item.update({
                "source": "config_reproducible",
                "objective": center,
                "observed_objective": float(item["objective"]),
                "confirmation_count": len(values),
                "confirmation_objectives": values,
                "objective_min": min(values),
                "objective_max": max(values),
                "objective_std": math.sqrt(sum(
                    (value - sum(values) / len(values)) ** 2
                    for value in values) / len(values)),
                "replay_evidence": evidence,
            })
            promoted.append(promoted_item)

    key = lambda item: (item["objective"], item["iteration"],
                        str(item.get("run_id", "")))
    return {
        "pending": sorted(pending, key=key)[: int(policy["pending_replay_limit"])],
        "statuses": sorted(statuses, key=lambda item: item["recipe_signature"]),
        "promoted": sorted(promoted, key=key),
    }
