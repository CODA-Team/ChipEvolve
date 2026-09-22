"""Port for bounded, read-only specialized analysis evidence."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from query_agent.domain.analysis import TimingMetricObservation, TimingPathObservation
from query_agent.domain.capability import Capability
from query_agent.domain.query import QueryContext


class AnalysisProvider(Protocol):
    """Expose authoritative analysis results without exposing an analyzer API."""

    @property
    def capabilities(self) -> frozenset[Capability]:
        """Capabilities backed by the connected analysis service."""

        ...

    def get_timing_metrics(
        self, context: QueryContext, *, metric_name: str | None = None
    ) -> Sequence[TimingMetricObservation]:
        """Return scoped scalar timing metrics."""

        ...

    def get_timing_paths(
        self,
        context: QueryContext,
        *,
        limit: int = 10,
        slack_below: float | None = None,
    ) -> Sequence[TimingPathObservation]:
        """Return a bounded set of scoped timing paths."""

        ...
