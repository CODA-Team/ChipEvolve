"""Pure ranking and clone-plan selection for staged DRP.

This module deliberately has no filesystem, predictor, lineage, or OpenROAD
dependency.  ``drp.py`` re-exports these helpers so existing callers keep the
same API while orchestration remains separate from population selection.
"""
from __future__ import annotations

import math
import random
from typing import Dict, List, Optional, Tuple


def _finite_metric(value) -> bool:
    """Return whether a metric is a finite, sortable numeric value."""
    if isinstance(value, bool):
        return False
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError, OverflowError):
        return False


def sort_runs(metrics: List[Dict], objective: str) -> List[Dict]:
    """Sort runs ascending by objective, placing invalid values last."""

    def sort_key(metric):
        value = metric.get(objective)
        if not _finite_metric(value):
            return float("inf")
        return float(value)

    return sorted(metrics, key=sort_key)


def select_survivors_and_victims(
    sorted_metrics: List[Dict],
    num_kill: int,
    rank_key: Optional[str] = None,
    protected_ids: Optional[set] = None,
    eligible_ids: Optional[set] = None,
) -> Tuple[List[int], List[int], List[int]]:
    """Build an elitist clone plan while excluding hard-invalid sources.

    ``sorted_metrics`` must be best-first.  Failed runs are always victims,
    protected eligible runs are never victims, and clone sources are cycled from
    the best remaining eligible runs to keep the population size fixed.
    """
    ids = [metric["run_id"] for metric in sorted_metrics]
    eligible = set(ids) if eligible_ids is None else set(eligible_ids) & set(ids)
    protected = set(protected_ids or ()) & eligible
    if rank_key is not None:
        valid = [
            metric["run_id"]
            for metric in sorted_metrics
            if metric["run_id"] in eligible
            and _finite_metric(metric.get(rank_key))
        ]
        failed = [
            metric["run_id"]
            for metric in sorted_metrics
            if metric["run_id"] not in valid
        ]
    else:
        valid = [run_id for run_id in ids if run_id in eligible]
        failed = [run_id for run_id in ids if run_id not in eligible]
    n_valid = len(valid)
    failed = [run_id for run_id in failed if run_id not in protected]

    if n_valid == 0:
        return ids, [], []

    killable = [run_id for run_id in valid if run_id not in protected]
    extra = max(0, int(num_kill) - len(failed))
    max_extra = (
        len(killable)
        if set(valid) - set(killable)
        else max(0, len(killable) - 1)
    )
    extra = min(extra, max_extra)
    victim_valid = killable[len(killable) - extra :] if extra > 0 else []

    victim_set = set(failed) | set(victim_valid)
    victim_ids = [run_id for run_id in ids if run_id in victim_set]
    survivor_ids = [run_id for run_id in ids if run_id not in victim_set]

    valid_survivors = [run_id for run_id in valid if run_id not in victim_set]
    source_ids = [
        valid_survivors[index % len(valid_survivors)]
        for index in range(len(victim_ids))
    ]
    return survivor_ids, source_ids, victim_ids


def _systematic_resample(
    weights: List[float], n: int, rng: random.Random
) -> List[int]:
    """Return low-variance categorical resampling counts."""
    counts = [0] * len(weights)
    if n <= 0:
        return counts

    total = sum(weights)
    if total <= 0:
        return counts

    cumulative = []
    accumulated = 0.0
    for weight in weights:
        accumulated += weight / total
        cumulative.append(accumulated)
    cumulative[-1] = 1.0

    start = rng.random() / n
    index = 0
    for draw in range(n):
        point = start + draw / n
        while index < len(cumulative) - 1 and point > cumulative[index]:
            index += 1
        counts[index] += 1
    return counts


def gwtw_select(
    sorted_metrics: List[Dict],
    objective: str,
    beta: float,
    n_elite: int,
    seed: Optional[int],
    protected_ids: Optional[set] = None,
    eligible_ids: Optional[set] = None,
) -> Tuple[
    Optional[List[int]],
    Optional[List[int]],
    Optional[List[int]],
    Optional[List[float]],
    Optional[List[int]],
]:
    """Select a fixed-size population by Boltzmann-weighted resampling."""
    rng = random.Random(seed)
    ids = [metric["run_id"] for metric in sorted_metrics]
    eligible = set(ids) if eligible_ids is None else set(eligible_ids) & set(ids)
    values = [
        float(metric.get(objective))
        if metric["run_id"] in eligible
        and _finite_metric(metric.get(objective))
        else None
        for metric in sorted_metrics
    ]
    finite = [value for value in values if value is not None]
    if not finite:
        return None, None, None, None, None

    minimum, maximum = min(finite), max(finite)
    span = (maximum - minimum) or 1.0
    raw = [
        0.0
        if value is None
        else math.exp(-beta * (value - minimum) / span)
        for value in values
    ]
    total = sum(raw)
    weights = (
        [weight / total for weight in raw]
        if total > 0
        else [0.0] * len(raw)
    )

    population = len(ids)
    counts = [0] * population
    finite_indices = [
        index for index, value in enumerate(values) if value is not None
    ]
    n_elite = max(0, min(n_elite, len(finite_indices)))
    forced_indices = set(finite_indices[:n_elite])
    if protected_ids:
        forced_indices.update(
            index
            for index, metric in enumerate(sorted_metrics)
            if metric["run_id"] in protected_ids
            and metric["run_id"] in eligible
        )
    for index in forced_indices:
        counts[index] += 1

    draws = _systematic_resample(
        weights, population - len(forced_indices), rng
    )
    for index in range(population):
        counts[index] += draws[index]

    survivor_ids = [
        ids[index] for index in range(population) if counts[index] >= 1
    ]
    victim_ids = [
        ids[index] for index in range(population) if counts[index] == 0
    ]
    clone_sources: List[int] = []
    for index in range(population):
        if counts[index] > 1:
            clone_sources.extend([ids[index]] * (counts[index] - 1))

    return survivor_ids, clone_sources, victim_ids, weights, counts


__all__ = [
    "_finite_metric",
    "_systematic_resample",
    "gwtw_select",
    "select_survivors_and_victims",
    "sort_runs",
]
