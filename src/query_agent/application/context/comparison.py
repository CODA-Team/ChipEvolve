"""Comparable-run metric selection."""

from __future__ import annotations

from collections.abc import Sequence

from query_agent.domain.experiment import (
    CandidateRejection,
    ComparisonScope,
    ComparisonSet,
    MetricObservation,
    canonical_stage_key,
)


class ComparisonPolicy:
    """Require semantic alignment before returning a comparison set."""

    def select(
        self,
        metrics: Sequence[MetricObservation],
        *,
        metric_name: str,
        stage_key: str | None,
        design_id: str | None,
    ) -> ComparisonSet:
        wanted_stage = canonical_stage_key(stage_key) if stage_key else None
        candidates = [
            item for item in metrics if item.metric_name.upper() == metric_name.upper()
        ]
        aligned = [
            item
            for item in candidates
            if item.canonical_stage == wanted_stage
            and (design_id is None or item.design_id == design_id)
        ]
        scope = ComparisonScope(
            design_id=design_id,
            stage_key=wanted_stage,
            metric_name=metric_name.upper(),
            unit=aligned[0].unit if aligned else None,
            corner=aligned[0].corner if aligned else None,
        )
        accepted: list[MetricObservation] = []
        rejected: list[CandidateRejection] = []
        for item in aligned:
            if item.unit != scope.unit or item.corner != scope.corner:
                rejected.append(
                    CandidateRejection(
                        candidate_id=item.run_id,
                        reason_code="NON_COMPARABLE_SCOPE",
                        detail=(
                            "metric unit or corner does not match the comparison scope"
                        ),
                    )
                )
            elif item.complete:
                accepted.append(item)
            else:
                rejected.append(
                    CandidateRejection(
                        candidate_id=item.run_id,
                        reason_code="PARTIAL_METRIC",
                        detail="metric source artifact is incomplete",
                    )
                )
        return ComparisonSet(
            scope=scope,
            observations=tuple(accepted),
            rejected=tuple(rejected),
        )
