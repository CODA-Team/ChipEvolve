"""Compose experiment context from a provider and small deterministic policies."""

from __future__ import annotations

from collections.abc import Sequence

from query_agent.domain.experiment import (
    ContextSelection,
    ExperimentContext,
    MetricObservation,
    ResolvedExperimentContext,
)
from query_agent.domain.query import (
    QueryPlan,
    QueryRequest,
    QuerySource,
    RunSelectionMode,
)
from query_agent.ports.experiment_context import ExperimentContextProvider

from .comparison import ComparisonPolicy
from .conflicts import ConflictDetector
from .freshness import FreshnessPolicy
from .run_selection import RunSelectionPolicy


class ExperimentContextResolver:
    """Resolve an authoritative run/stage context without provider conditionals."""

    def __init__(
        self,
        provider: ExperimentContextProvider,
        *,
        run_selection: RunSelectionPolicy | None = None,
        comparison: ComparisonPolicy | None = None,
        freshness: FreshnessPolicy | None = None,
        conflicts: ConflictDetector | None = None,
    ) -> None:
        self.provider = provider
        self._run_selection = run_selection or RunSelectionPolicy()
        self._comparison = comparison or ComparisonPolicy()
        self._freshness = freshness or FreshnessPolicy()
        self._conflicts = conflicts or ConflictDetector()

    def resolve(
        self, request: QueryRequest, plan: QueryPlan
    ) -> ResolvedExperimentContext:
        context = request.context
        if context.source is not QuerySource.MANAGED_RUN:
            return ResolvedExperimentContext(
                context=ExperimentContext(design_id=context.design_id),
                selection=self._empty_selection(),
            )
        runs = tuple(
            self.provider.list_runs(
                design_id=context.design_id,
                run_ids=context.run_ids
                or ((context.run_id,) if context.run_id else ()),
            )
        )
        selected, selection = self._run_selection.select(
            runs,
            mode=plan.run_selection,
            requested_stage=context.stage,
            explicit_run_id=context.run_id,
        )
        selected_ids = tuple(run.run_id for run in selected)
        artifacts = tuple(
            artifact
            for run_id in selected_ids
            for artifact in self.provider.list_artifacts(
                run_id, stage_key=context.stage
            )
        )
        metric_name = _metric_name(plan)
        metrics = tuple(
            metric
            for run_id in selected_ids
            for metric in self.provider.list_metrics(
                run_id, metric_name=metric_name, stage_key=context.stage
            )
        )
        provenance = tuple(
            item
            for run_id in selected_ids
            for item in self.provider.get_provenance(run_id)
        )
        comparison = None
        if plan.run_selection is RunSelectionMode.COMPARISON and metric_name:
            comparison = self._comparison.select(
                metrics,
                metric_name=metric_name,
                stage_key=context.stage,
                design_id=context.design_id,
            )
        conflicts = self._conflicts.detect(metrics)
        freshness = tuple(
            item
            for run in selected
            for item in self._freshness.assess(
                run,
                metrics_for_run(metrics, run.run_id),
                requires_current=any(
                    requirement.requires_current
                    for requirement in plan.evidence_requirements
                ),
            )
        )
        return ResolvedExperimentContext(
            context=ExperimentContext(
                design_id=context.design_id,
                runs=tuple(runs),
                artifacts=artifacts,
                metrics=metrics,
                provenance=provenance,
            ),
            selection=selection,
            comparison=comparison,
            conflicts=conflicts,
            freshness=freshness,
        )

    @staticmethod
    def _empty_selection() -> ContextSelection:
        return ContextSelection(reason_codes=("NO_MANAGED_CONTEXT",))


def metrics_for_run(
    metrics: Sequence[MetricObservation], run_id: str
) -> tuple[MetricObservation, ...]:
    return tuple(item for item in metrics if item.run_id == run_id)


def _metric_name(plan: QueryPlan) -> str | None:
    for requirement in plan.evidence_requirements:
        if requirement.fact_key and requirement.fact_key.startswith("metric:"):
            return requirement.fact_key.split(":", 1)[1]
    return None
