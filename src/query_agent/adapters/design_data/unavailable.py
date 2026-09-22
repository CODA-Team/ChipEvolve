"""Explicit null implementation until the data foundation is available."""

from __future__ import annotations

from collections.abc import Sequence

from query_agent.domain.capability import Capability
from query_agent.domain.evidence import Evidence
from query_agent.domain.query import QueryContext


class UnavailableDesignDataProvider:
    """A truthful provider with no design-data capability.

    Returning no evidence lets the application produce ``NEEDS_MORE_DATA`` or
    ``UNSUPPORTED`` as a normal business result. It never invents a parsed
    design object and it never raises for ordinary unavailability.
    """

    @property
    def capabilities(self) -> frozenset[Capability]:
        return frozenset()

    def query(self, request: str, context: QueryContext) -> Sequence[Evidence]:
        del request, context
        return ()
