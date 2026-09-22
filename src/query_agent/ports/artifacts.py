"""Read-only artifact port."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from query_agent.domain.capability import Capability
from query_agent.domain.evidence import ArtifactExcerpt, ArtifactMetadata, TextMatch
from query_agent.domain.query import QueryContext


class ArtifactProvider(Protocol):
    """Provider contract for bounded, read-only workspace access."""

    @property
    def capabilities(self) -> frozenset[Capability]:
        """Capabilities this provider actually implements."""

        ...

    def list_artifacts(self, context: QueryContext) -> Sequence[ArtifactMetadata]:
        """List metadata for files in the scoped workspace."""

        ...

    def find_artifacts(
        self, context: QueryContext, pattern: str
    ) -> Sequence[ArtifactMetadata]:
        """Find files by a deterministic glob-like pattern."""

        ...

    def search_text(
        self, context: QueryContext, query: str, *, max_results: int = 50
    ) -> Sequence[TextMatch]:
        """Search bounded text excerpts, never execute a shell command."""

        ...

    def read_excerpt(
        self,
        context: QueryContext,
        path: str,
        *,
        offset: int = 0,
        max_bytes: int | None = None,
    ) -> ArtifactExcerpt:
        """Read a bounded text excerpt."""

        ...

    def stat(self, context: QueryContext, path: str) -> ArtifactMetadata:
        """Read metadata for one scoped artifact."""

        ...
