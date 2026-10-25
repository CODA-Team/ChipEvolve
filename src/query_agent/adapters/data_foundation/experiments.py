"""Execution owns lifecycle; Data Foundation owns canonical design metrics."""

from collections.abc import Sequence
from urllib.parse import quote

from eda_ai_client import EdaAiError

from query_agent.domain.capability import Capability
from query_agent.domain.errors import DataBoundaryError
from query_agent.domain.experiment import (
    ArtifactRef,
    ExperimentRun,
    ExperimentStage,
    MetricObservation,
    ProvenanceRef,
)
from query_agent.ports.experiment_context import ExperimentContextProvider

from .models import Metrics, RunSummary, Snapshot, read
from .provider import DataFoundationProvider, call


class DataExperimentProvider:
    """Compose public providers without reopening either service's database."""

    def __init__(
        self, execution: ExperimentContextProvider, data: DataFoundationProvider
    ) -> None:
        self.execution, self.data = execution, data

    @property
    def capabilities(self) -> frozenset[Capability]:
        return self.execution.capabilities | {Capability.EXPLICIT_METRIC}

    def list_runs(
        self,
        *,
        design_id: str | None = None,
        run_ids: Sequence[str] = (),
        limit: int = 100,
    ) -> Sequence[ExperimentRun]:
        return tuple(
            self._with_data_stages(run)
            for run in self.execution.list_runs(
                design_id=design_id, run_ids=run_ids, limit=limit
            )
        )

    def get_run(self, run_id: str) -> ExperimentRun:
        return self._with_data_stages(self.execution.get_run(run_id))

    def _with_data_stages(self, run: ExperimentRun) -> ExperimentRun:
        try:
            raw = self.data.client.get_run_summary(run.run_id)
        except EdaAiError as exc:
            if exc.status == 404:
                # Execution exists but has no imported design data yet.
                return run
            raise DataBoundaryError(str(exc)) from exc
        summary = read(raw, RunSummary).data
        if summary.run_id != run.run_id or any(
            row.snapshot.run_id != run.run_id or row.snapshot.design_id != run.design_id
            for row in summary.snapshots
        ):
            raise DataBoundaryError("indexed run summary crosses execution ownership")
        return run.model_copy(
            update={
                "indexed_data_stages": tuple(
                    sorted({row.snapshot.stage for row in summary.snapshots})
                )
            }
        )

    def get_stage_state(
        self, run_id: str, *, stage_key: str | None = None
    ) -> Sequence[ExperimentStage]:
        return self.execution.get_stage_state(run_id, stage_key=stage_key)

    def list_artifacts(
        self, run_id: str, *, stage_key: str | None = None
    ) -> Sequence[ArtifactRef]:
        if stage_key is None:
            return self.execution.list_artifacts(run_id)
        artifacts: dict[str, ArtifactRef] = {}
        for snapshot in self._run_snapshots(run_id):
            if snapshot.stage != stage_key:
                continue
            for source in snapshot.source_artifacts:
                reference = ArtifactRef(
                    artifact_id=source.artifact_id,
                    run_id=snapshot.run_id,
                    design_id=snapshot.design_id,
                    stage_key=snapshot.stage,
                    kind=source.category,
                    source_hash=source.sha256,
                    locator=(
                        f"{self.data.client.data_url}/snapshots/"
                        f"{quote(snapshot.snapshot_id, safe='')}/sources/"
                        f"{quote(source.artifact_id, safe='')}/excerpt"
                    ),
                )
                previous = artifacts.get(source.artifact_id)
                if (
                    previous is not None
                    and previous.source_hash != reference.source_hash
                ):
                    raise DataBoundaryError(
                        "indexed artifact identity has conflicting hashes"
                    )
                artifacts.setdefault(source.artifact_id, reference)
        return tuple(artifacts.values())

    def get_provenance(self, run_id: str) -> Sequence[ProvenanceRef]:
        return self.execution.get_provenance(run_id)

    def _run_snapshots(self, run_id: str) -> tuple[Snapshot, ...]:
        summary = read(
            call(lambda: self.data.client.get_run_summary(run_id)), RunSummary
        ).data
        if (
            summary.run_id != run_id
            or any(row.snapshot.run_id != run_id for row in summary.snapshots)
            or len({row.snapshot.design_id for row in summary.snapshots}) > 1
        ):
            raise DataBoundaryError("data catalog crosses requested run ownership")
        return tuple(row.snapshot for row in summary.snapshots)

    def list_metrics(
        self,
        run_id: str,
        *,
        metric_name: str | None = None,
        stage_key: str | None = None,
    ) -> Sequence[MetricObservation]:
        scopes = {
            snapshot.snapshot_id: snapshot for snapshot in self._run_snapshots(run_id)
        }
        result = read(
            call(
                lambda: self.data.client.get_metrics(
                    run_id=run_id, stage=stage_key, name=metric_name
                )
            ),
            Metrics,
        )
        observations: list[MetricObservation] = []
        for row in result.data.metrics:
            scope = scopes.get(row.snapshot_id)
            if (
                scope is None
                or row.stage != scope.stage
                or (stage_key is not None and row.stage != stage_key)
            ):
                raise DataBoundaryError(
                    "metric response crosses resolved snapshot scope"
                )
            if row.value is None:
                continue
            source = next(
                (source for source in row.evidence if source.registered), None
            )
            observations.append(
                MetricObservation(
                    metric_name=row.name,
                    value=row.value,
                    unit=row.unit,
                    design_id=scope.design_id,
                    run_id=scope.run_id,
                    stage_key=scope.stage,
                    snapshot_id=scope.snapshot_id,
                    revision_id=scope.revision_id,
                    corner=row.corner,
                    artifact_id=source.artifact_id if source else None,
                    source_hash=(source.sha256 or source.source_hash)
                    if source
                    else None,
                    complete=row.status == "available"
                    and source is not None
                    and row.unit is not None
                    and row.corner is not None,
                    parser_id="data-foundation.canonical",
                    parser_version="0.2",
                )
            )
        return observations
