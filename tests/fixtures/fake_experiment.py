"""Deterministic provider fixture for Phase-II context reasoning tests."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from query_agent.domain.capability import Capability
from query_agent.domain.experiment import (
    ArtifactRef,
    ExperimentRun,
    ExperimentStage,
    ExperimentStatus,
    MetricObservation,
    ProvenanceRef,
    StageStatus,
)


class FakeExperimentContextProvider:
    """A provider with completed, failed, and active runs."""

    def __init__(self, *, include_routing_metric: bool = True) -> None:
        when = datetime(2026, 9, 22, tzinfo=UTC)
        self.runs = (
            ExperimentRun(
                run_id="run_001",
                design_id="gcd",
                status=ExperimentStatus.SUCCEEDED,
                created_at=when,
                completed_at=when,
                stages=(
                    ExperimentStage(
                        stage_key="placement", status=StageStatus.SUCCEEDED
                    ),
                    ExperimentStage(stage_key="routing", status=StageStatus.SUCCEEDED),
                ),
            ),
            ExperimentRun(
                run_id="run_002",
                design_id="gcd",
                status=ExperimentStatus.FAILED,
                created_at=when.replace(hour=13),
                stages=(
                    ExperimentStage(stage_key="routing", status=StageStatus.FAILED),
                ),
            ),
            ExperimentRun(
                run_id="run_003",
                design_id="gcd",
                status=ExperimentStatus.RUNNING,
                created_at=when.replace(hour=14),
                stages=(
                    ExperimentStage(stage_key="routing", status=StageStatus.RUNNING),
                ),
            ),
        )
        self.artifacts = (
            ArtifactRef(
                artifact_id="route-report-001",
                run_id="run_001",
                design_id="gcd",
                stage_key="routing",
                kind="timing_report",
                locator="reports/run_001/route.timing.rpt",
                source_hash="a" * 64,
                created_at=when,
            ),
        )
        self.metrics = (
            (
                MetricObservation(
                    metric_name="WNS",
                    value=-0.2,
                    unit="ns",
                    run_id="run_001",
                    design_id="gcd",
                    stage_key="routing",
                    artifact_id="route-report-001",
                    source_hash="a" * 64,
                    observed_at=when,
                ),
            )
            if include_routing_metric
            else ()
        )

    @property
    def capabilities(self) -> frozenset[Capability]:
        return frozenset(
            {
                Capability.RUN_EVIDENCE,
                Capability.ARTIFACT_DISCOVERY,
                Capability.TEXT_SEARCH,
                Capability.EXPLICIT_METRIC,
            }
        )

    def list_runs(
        self,
        *,
        design_id: str | None = None,
        run_ids: Sequence[str] = (),
        limit: int = 100,
    ) -> Sequence[ExperimentRun]:
        result = tuple(
            run
            for run in self.runs
            if (not design_id or run.design_id == design_id)
            and (not run_ids or run.run_id in run_ids)
        )
        return result[:limit]

    def get_run(self, run_id: str) -> ExperimentRun:
        return next(run for run in self.runs if run.run_id == run_id)

    def get_stage_state(
        self, run_id: str, *, stage_key: str | None = None
    ) -> Sequence[ExperimentStage]:
        stages = self.get_run(run_id).stages
        return tuple(
            stage
            for stage in stages
            if stage_key is None or stage.canonical_key == stage_key
        )

    def list_artifacts(
        self, run_id: str, *, stage_key: str | None = None
    ) -> Sequence[ArtifactRef]:
        return tuple(
            item
            for item in self.artifacts
            if item.run_id == run_id
            and (stage_key is None or item.canonical_stage == stage_key)
        )

    def list_metrics(
        self,
        run_id: str,
        *,
        metric_name: str | None = None,
        stage_key: str | None = None,
    ) -> Sequence[MetricObservation]:
        return tuple(
            item
            for item in self.metrics
            if item.run_id == run_id
            and (metric_name is None or item.metric_name.upper() == metric_name.upper())
            and (stage_key is None or item.canonical_stage == stage_key)
        )

    def get_provenance(self, run_id: str) -> Sequence[ProvenanceRef]:
        return (
            ProvenanceRef(
                run_id=run_id,
                provider="fake-experiment",
                locator=f"fake://runs/{run_id}",
            ),
        )
