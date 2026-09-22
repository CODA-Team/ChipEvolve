"""Small deterministic timing-analysis adapter used for Phase III-B tests."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from query_agent.domain.analysis import (
    AnalysisProvenance,
    AnalysisScope,
    TimingMetricObservation,
    TimingPathObservation,
)
from query_agent.domain.capability import Capability
from query_agent.domain.query import QueryContext


class FixtureAnalysisProvider:
    """Provider-neutral fixture with scalar timing and bounded path evidence."""

    _source_hash = "b" * 64

    @property
    def capabilities(self) -> frozenset[Capability]:
        return frozenset({Capability.SPECIALIZED_ANALYSIS})

    def _scope(self, context: QueryContext) -> AnalysisScope | None:
        if context.design_id not in (None, "gcd"):
            return None
        return AnalysisScope(
            design_id=context.design_id or "gcd",
            run_id=context.run_id,
            stage=context.stage or "timing",
            corner="typical",
        )

    @classmethod
    def _provenance(cls, path: str) -> AnalysisProvenance:
        return AnalysisProvenance(
            provider="fixture-analysis-provider",
            locator=f"analysis://timing/{path}",
            source_hash=cls._source_hash,
            observed_at=datetime(2026, 9, 22, tzinfo=UTC),
        )

    def get_timing_metrics(
        self, context: QueryContext, *, metric_name: str | None = None
    ) -> Sequence[TimingMetricObservation]:
        scope = self._scope(context)
        if scope is None:
            return ()
        metrics = (
            TimingMetricObservation(
                metric_name="WNS",
                value=-0.2,
                unit="ns",
                scope=scope,
                provenance=self._provenance("summary/wns"),
            ),
            TimingMetricObservation(
                metric_name="TNS",
                value=-1.4,
                unit="ns",
                scope=scope,
                provenance=self._provenance("summary/tns"),
            ),
        )
        if metric_name is None:
            return metrics
        return tuple(
            item for item in metrics if item.metric_name.upper() == metric_name.upper()
        )

    def get_timing_paths(
        self,
        context: QueryContext,
        *,
        limit: int = 10,
        slack_below: float | None = None,
    ) -> Sequence[TimingPathObservation]:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        scope = self._scope(context)
        if scope is None:
            return ()
        paths = (
            TimingPathObservation(
                path_id="path-001",
                startpoint="u1/A",
                endpoint="u2/Y",
                slack=-0.2,
                unit="ns",
                total_delay=1.8,
                logic_depth=4,
                scope=scope,
                provenance=self._provenance("paths/path-001"),
            ),
            TimingPathObservation(
                path_id="path-002",
                startpoint="u2/A",
                endpoint="u3/Y",
                slack=0.1,
                unit="ns",
                total_delay=1.2,
                logic_depth=3,
                scope=scope,
                provenance=self._provenance("paths/path-002"),
            ),
        )
        filtered = (
            tuple(item for item in paths if item.slack < slack_below)
            if slack_below is not None
            else paths
        )
        return filtered[:limit]
