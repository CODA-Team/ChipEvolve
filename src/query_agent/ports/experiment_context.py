"""Port for structured, read-only experiment state."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from query_agent.domain.capability import Capability
from query_agent.domain.experiment import (
    ArtifactRef,
    ExperimentRun,
    ExperimentStage,
    MetricObservation,
    ProvenanceRef,
)


class ExperimentContextProvider(Protocol):
    """Expose experiment state without exposing an external system's schema."""

    @property
    def capabilities(self) -> frozenset[Capability]:
        """Capabilities backed by the provider."""

        ...

    def list_runs(
        self,
        *,
        design_id: str | None = None,
        run_ids: Sequence[str] = (),
        limit: int = 100,
    ) -> Sequence[ExperimentRun]:
        """List newest runs in a bounded, deterministic order."""

        ...

    def get_run(self, run_id: str) -> ExperimentRun:
        """Return one run by stable identifier."""

        ...

    def get_stage_state(
        self, run_id: str, *, stage_key: str | None = None
    ) -> Sequence[ExperimentStage]:
        """Return stage state, optionally narrowed to one semantic stage."""

        ...

    def list_artifacts(
        self, run_id: str, *, stage_key: str | None = None
    ) -> Sequence[ArtifactRef]:
        """Return registered artifacts and their run/stage ownership."""

        ...

    def list_metrics(
        self,
        run_id: str,
        *,
        metric_name: str | None = None,
        stage_key: str | None = None,
    ) -> Sequence[MetricObservation]:
        """Return metric observations with artifact lineage preserved."""

        ...

    def get_provenance(self, run_id: str) -> Sequence[ProvenanceRef]:
        """Return bounded provenance pointers for a run."""

        ...
