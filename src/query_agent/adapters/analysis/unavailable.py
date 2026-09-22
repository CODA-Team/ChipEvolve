"""Explicit null implementation until a typed analysis service is available."""

from __future__ import annotations

from collections.abc import Sequence

from query_agent.domain.analysis import TimingMetricObservation, TimingPathObservation
from query_agent.domain.capability import Capability
from query_agent.domain.query import QueryContext


class UnavailableAnalysisProvider:
    """Truthful boundary that never fabricates timing results."""

    @property
    def capabilities(self) -> frozenset[Capability]:
        return frozenset()

    def get_timing_metrics(
        self, context: QueryContext, *, metric_name: str | None = None
    ) -> Sequence[TimingMetricObservation]:
        del context, metric_name
        return ()

    def get_timing_paths(
        self,
        context: QueryContext,
        *,
        limit: int = 10,
        slack_below: float | None = None,
    ) -> Sequence[TimingPathObservation]:
        del context, limit, slack_below
        return ()
