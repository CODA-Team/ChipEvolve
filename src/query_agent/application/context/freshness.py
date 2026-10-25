"""Explainable freshness checks for current-state requirements."""

from collections.abc import Sequence

from query_agent.domain.experiment import (
    ExperimentRun,
    FreshnessAssessment,
    FreshnessState,
    MetricObservation,
)


class FreshnessPolicy:
    """Assess metric freshness using run completion and artifact lineage."""

    def assess(
        self,
        run: ExperimentRun,
        metrics: Sequence[MetricObservation],
        *,
        requires_current: bool,
    ) -> tuple[FreshnessAssessment, ...]:
        if not requires_current:
            return ()
        result: list[FreshnessAssessment] = []
        for metric in metrics:
            evidence_id = (
                f"{metric.run_id}:{metric.fact_key}:"
                f"{metric.artifact_id or 'unregistered'}"
            )
            if not metric.complete or metric.artifact_id is None:
                result.append(
                    FreshnessAssessment(
                        state=FreshnessState.STALE,
                        evidence_id=evidence_id,
                        run_id=metric.run_id,
                        reason=metric.incomplete_reason
                        or "metric has no complete registered source artifact",
                    )
                )
            elif (
                run.completed_at
                and metric.observed_at
                and metric.observed_at < run.completed_at
            ):
                result.append(
                    FreshnessAssessment(
                        state=FreshnessState.STALE,
                        evidence_id=evidence_id,
                        run_id=metric.run_id,
                        reason="metric source predates run completion",
                    )
                )
            elif run.status.valid:
                result.append(
                    FreshnessAssessment(
                        state=FreshnessState.CURRENT,
                        evidence_id=evidence_id,
                        run_id=metric.run_id,
                        reason="metric belongs to the selected completed run",
                    )
                )
            else:
                result.append(
                    FreshnessAssessment(
                        state=FreshnessState.UNKNOWN,
                        evidence_id=evidence_id,
                        run_id=metric.run_id,
                        reason="selected run is not a completed successful run",
                    )
                )
        return tuple(result)
