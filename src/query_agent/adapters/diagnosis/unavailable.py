"""Explicit null implementation until an authoritative diagnosis service exists."""

from __future__ import annotations

from collections.abc import Sequence

from query_agent.domain.capability import Capability
from query_agent.domain.diagnosis import DiagnosisFinding
from query_agent.domain.query import QueryContext


class UnavailableDiagnosisProvider:
    """Truthful boundary that never invents a root cause."""

    @property
    def capabilities(self) -> frozenset[Capability]:
        return frozenset()

    def get_findings(
        self, context: QueryContext, *, symptom: str, limit: int = 10
    ) -> Sequence[DiagnosisFinding]:
        del context, symptom, limit
        return ()
