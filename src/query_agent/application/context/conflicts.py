"""Deterministic conflict detection for normalized metric facts."""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Sequence

from query_agent.domain.evidence import EvidenceScope
from query_agent.domain.experiment import Conflict, ConflictKind, MetricObservation


class ConflictDetector:
    """Retain incompatible authoritative values instead of choosing a winner."""

    def detect(self, metrics: Sequence[MetricObservation]) -> tuple[Conflict, ...]:
        groups: dict[
            tuple[str | None, str, str | None, str], list[MetricObservation]
        ] = defaultdict(list)
        for metric in metrics:
            groups[
                (
                    metric.design_id,
                    metric.run_id,
                    metric.canonical_stage,
                    metric.metric_name.upper(),
                )
            ].append(metric)
        conflicts: list[Conflict] = []
        for (design_id, run_id, stage, name), items in groups.items():
            authoritative = tuple(item for item in items if item.complete)
            authoritative_values = tuple(
                dict.fromkeys(
                    json.dumps(item.value, sort_keys=True, default=str)
                    for item in authoritative
                )
            )
            if len(authoritative_values) > 1:
                conflicts.append(
                    Conflict(
                        kind=ConflictKind.VALUE_MISMATCH,
                        fact_key=f"metric:{name}",
                        scope=EvidenceScope(
                            design_id=design_id, run_id=run_id, stage=stage
                        ),
                        evidence_ids=tuple(_metric_id(item) for item in items),
                        values=tuple(item.value for item in items),
                        reason=(
                            "authoritative sources disagree for one normalized scope"
                        ),
                    )
                )
        return tuple(conflicts)


def _metric_id(metric: MetricObservation) -> str:
    artifact = metric.artifact_id or "unregistered"
    return (
        f"{metric.run_id}:{metric.canonical_stage or 'unknown'}:"
        f"{metric.fact_key}:{artifact}"
    )
