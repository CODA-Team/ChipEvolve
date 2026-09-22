"""Port for read-only, evidence-grounded diagnostic findings."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from query_agent.domain.capability import Capability
from query_agent.domain.diagnosis import DiagnosisFinding
from query_agent.domain.query import QueryContext


class DiagnosisProvider(Protocol):
    """Expose findings only when the provider can retain their support facts."""

    @property
    def capabilities(self) -> frozenset[Capability]:
        """Capabilities backed by the connected diagnosis service."""

        ...

    def get_findings(
        self, context: QueryContext, *, symptom: str, limit: int = 10
    ) -> Sequence[DiagnosisFinding]:
        """Return a bounded set of findings for one user-reported symptom."""

        ...
