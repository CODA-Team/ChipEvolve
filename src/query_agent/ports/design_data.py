"""Future design-data port."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from query_agent.domain.capability import Capability
from query_agent.domain.evidence import Evidence
from query_agent.domain.query import QueryContext


class DesignDataProvider(Protocol):
    """Port for the future structured design-data foundation."""

    @property
    def capabilities(self) -> frozenset[Capability]:
        """Capabilities supported by the connected data foundation."""

        ...

    def query(self, request: str, context: QueryContext) -> Sequence[Evidence]:
        """Query structured design state; no DEF/SPEF/ODB parsing here."""

        ...
