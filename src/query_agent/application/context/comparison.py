"""Comparable-run metric selection."""

from __future__ import annotations

from collections.abc import Sequence

from query_agent.domain.errors import MissingDataError
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
            item
            for item in metrics
            if item.metric_name.upper() == metric_name.upper()
            and (design_id is None or item.design_id == design_id)
        ]
        if stage_key is None:
            complete = [item for item in candidates if item.complete]
            stages = {item.canonical_stage for item in complete or candidates}
            if len(stages) > 1:
                raise MissingDataError(
                    "Comparison covers multiple physical stages; specify a stage"
                )
            wanted_stage = next(iter(stages), None)
        aligned = [item for item in candidates if item.canonical_stage == wanted_stage]
        anchor = next((item for item in aligned if item.complete), None)
        if anchor is None and aligned:
            anchor = aligned[0]
        scope = ComparisonScope(
            design_id=design_id,
            stage_key=wanted_stage,
            metric_name=metric_name.upper(),
            unit=anchor.unit if anchor else None,
            corner=anchor.corner if anchor else None,
        )
        accepted: list[MetricObservation] = []
        rejected: list[CandidateRejection] = []
        for item in aligned:
            if not item.complete:
                rejected.append(
                    CandidateRejection(
                        candidate_id=item.run_id,
                        reason_code="PARTIAL_METRIC",
                        detail=item.incomplete_reason
                        or "metric source artifact is incomplete",
                    )
                )
            elif item.unit != scope.unit or item.corner != scope.corner:
                rejected.append(
                    CandidateRejection(
                        candidate_id=item.run_id,
                        reason_code="NON_COMPARABLE_SCOPE",
                        detail=(
                            "metric unit or corner does not match the comparison scope"
                        ),
                    )
                )
            else:
                accepted.append(item)
        return ComparisonSet(
            scope=scope,
            observations=tuple(accepted),
            rejected=tuple(rejected),
        )
