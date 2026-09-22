"""Domain knowledge port."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from query_agent.domain.capability import Capability
from query_agent.domain.evidence import Evidence
from query_agent.domain.query import QueryContext


class KnowledgeProvider(Protocol):
    """Searchable EDA/tool knowledge without prescribing a retrieval stack."""

    @property
    def capabilities(self) -> frozenset[Capability]:
        """Capabilities currently available from this provider."""

        ...

    def search(self, query: str, context: QueryContext) -> Sequence[Evidence]:
        """Return typed, cited evidence; never an untraceable answer string."""

        ...
