"""Port for existing, registered execution evidence."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from query_agent.domain.capability import Capability
from query_agent.domain.evidence import Evidence
from query_agent.domain.query import QueryContext


class RunEvidenceProvider(Protocol):
    """Read-only experiment evidence for a managed run.

    This port deliberately describes evidence use-cases rather than mirroring
    the execution foundation's HTTP client. Concrete protocol types remain in
    the adapter package.
    """

    @property
    def capabilities(self) -> frozenset[Capability]:
        """Capabilities available from registered run evidence."""

        ...

    def get_run_summary(self, context: QueryContext) -> Sequence[Evidence]:
        """Return the run state and identity evidence."""

        ...

    def get_stage_evidence(self, context: QueryContext) -> Sequence[Evidence]:
        """Return status evidence for the requested stage or all stages."""

        ...

    def get_metrics(
        self, context: QueryContext, *, metric_name: str | None = None
    ) -> Sequence[Evidence]:
        """Return explicitly registered metrics and their lineage."""

        ...

    def get_artifacts(self, context: QueryContext) -> Sequence[Evidence]:
        """Return registered artifact metadata, not workspace scans."""

        ...

    def get_logs(
        self, context: QueryContext, *, query: str | None = None
    ) -> Sequence[Evidence]:
        """Return bounded registered run logs."""

        ...

    def get_artifact_excerpt(
        self, context: QueryContext, artifact_id: str, *, max_bytes: int = 8192
    ) -> Sequence[Evidence]:
        """Return a bounded excerpt through the public run API."""

        ...

    def get_provenance(self, context: QueryContext) -> Sequence[Evidence]:
        """Return timeline/graph provenance evidence."""

        ...
