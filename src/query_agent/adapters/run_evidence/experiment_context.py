"""Execution-foundation adapter for structured experiment context."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import cast

from query_agent.domain.capability import Capability
from query_agent.domain.errors import RunEvidenceError
from query_agent.domain.evidence import JsonValue
from query_agent.domain.experiment import (
    ArtifactRef,
    ExperimentRun,
    ExperimentStage,
    ExperimentStatus,
    MetricObservation,
    ProvenanceRef,
    StageStatus,
    canonical_stage_key,
)
from query_agent.ports.experiment_context import ExperimentContextProvider

from .execution_foundation import (
    PublicExecutionClient,
    mapping,
    parse_time,
    sequence,
    string,
    string_or_none,
    value,
)


class ExecutionFoundationExperimentContextProvider(ExperimentContextProvider):
    """Translate public run views without importing foundation internals."""

    _provider_name = "execution-foundation-public-api"

    def __init__(self, client: PublicExecutionClient, *, max_runs: int = 100):
        if not 1 <= max_runs <= 1000:
            raise ValueError("max_runs must be between 1 and 1000")
        self._client = client
        self._max_runs = max_runs

    @property
    def capabilities(self) -> frozenset[Capability]:
        return frozenset(
            {
                Capability.RUN_EVIDENCE,
                Capability.ARTIFACT_DISCOVERY,
                Capability.TEXT_SEARCH,
                Capability.EXPLICIT_METRIC,
            }
        )

    def list_runs(
        self,
        *,
        design_id: str | None = None,
        run_ids: Sequence[str] = (),
        limit: int = 100,
    ) -> Sequence[ExperimentRun]:
        bounded_limit = min(limit, self._max_runs)
        if limit < 1:
            raise ValueError("limit must be positive")
        if run_ids:
            return tuple(self.get_run(run_id) for run_id in run_ids[:bounded_limit])
        runs_method = getattr(self._client, "runs", None)
        if not callable(runs_method):
            raise RunEvidenceError("execution foundation client cannot list runs")
        typed_runs = cast(Callable[..., Sequence[Mapping[str, object]]], runs_method)
        raw_runs = typed_runs(design_id=design_id, limit=bounded_limit)
        return tuple(self._map_run(item) for item in raw_runs)

    def get_run(self, run_id: str) -> ExperimentRun:
        return self._map_run(self._client.run(run_id))

    def get_stage_state(
        self, run_id: str, *, stage_key: str | None = None
    ) -> Sequence[ExperimentStage]:
        stages = self.get_run(run_id).stages
        if stage_key is None:
            return stages
        wanted = canonical_stage_key(stage_key)
        return tuple(stage for stage in stages if stage.canonical_key == wanted)

    def list_artifacts(
        self, run_id: str, *, stage_key: str | None = None
    ) -> Sequence[ArtifactRef]:
        raw = self._client.artifacts(
            run_id,
            stage=canonical_stage_key(stage_key) if stage_key is not None else None,
        )
        return tuple(self._map_artifact(run_id, item) for item in raw)

    def list_metrics(
        self,
        run_id: str,
        *,
        metric_name: str | None = None,
        stage_key: str | None = None,
    ) -> Sequence[MetricObservation]:
        artifacts = self.list_artifacts(run_id)
        by_id = {item.artifact_id: item for item in artifacts}
        run = self.get_run(run_id)
        raw_metrics = self._client.metrics(run_id)
        result: list[MetricObservation] = []
        for raw in raw_metrics:
            name = string(value(raw, "name"))
            if metric_name is not None and name.upper() != metric_name.upper():
                continue
            artifact_data = mapping(value(raw, "artifact"))
            artifact_id = string_or_none(value(artifact_data, "artifact_id"))
            artifact = by_id.get(artifact_id or "")
            stage = artifact.stage_key if artifact else self._metric_stage(raw)
            if stage_key is not None and (
                stage is None
                or canonical_stage_key(stage) != canonical_stage_key(stage_key)
            ):
                continue
            context = mapping(value(raw, "context"))
            parser = mapping(value(raw, "parser"))
            source = (
                artifact.source_hash
                if artifact
                else string_or_none(value(artifact_data, "sha256"))
            )
            result.append(
                MetricObservation(
                    metric_name=name,
                    value=_json_value(value(raw, "value")),
                    unit=string_or_none(value(raw, "unit")),
                    run_id=run_id,
                    design_id=run.design_id,
                    stage_key=stage,
                    artifact_id=artifact_id,
                    source_hash=source,
                    complete=bool(value(raw, "complete")) and artifact is not None,
                    observed_at=(artifact.created_at if artifact else run.completed_at),
                    corner=string_or_none(value(context, "corner")),
                    parser_id=string_or_none(value(parser, "id")),
                    parser_version=string_or_none(value(parser, "version")),
                )
            )
        return tuple(result)

    def get_provenance(self, run_id: str) -> Sequence[ProvenanceRef]:
        result: list[ProvenanceRef] = []
        for event in self._client.timeline(run_id):
            event_type = string(value(event, "event_type")) or "event"
            result.append(
                ProvenanceRef(
                    run_id=run_id,
                    provider=self._provider_name,
                    locator=f"execution://runs/{run_id}/timeline#{event_type}",
                )
            )
        graph = self._client.graph([run_id])
        if graph:
            result.append(
                ProvenanceRef(
                    run_id=run_id,
                    provider=self._provider_name,
                    locator=f"execution://runs/{run_id}/graph",
                )
            )
        return tuple(result)

    @classmethod
    def _map_run(cls, raw: Mapping[str, object]) -> ExperimentRun:
        task = mapping(value(raw, "task"))
        design_id = string_or_none(value(raw, "design_id")) or string_or_none(
            value(task, "design_id")
        )
        stages = tuple(cls._map_stage(item) for item in sequence(value(raw, "stages")))
        return ExperimentRun(
            run_id=string(value(raw, "run_id")),
            design_id=design_id,
            status=ExperimentStatus.from_raw(value(raw, "status")),
            created_at=parse_time(value(raw, "created_at")),
            started_at=parse_time(value(raw, "started_at")),
            completed_at=parse_time(
                value(raw, "completed_at") or value(raw, "ended_at")
            ),
            stages=stages,
        )

    @staticmethod
    def _map_stage(raw: Mapping[str, object]) -> ExperimentStage:
        return ExperimentStage(
            stage_key=string(value(raw, "stage_key") or value(raw, "stage")),
            ordinal=_int_or_none(value(raw, "ordinal")),
            status=StageStatus.from_raw(value(raw, "status")),
            plugin_id=string_or_none(value(raw, "plugin_id")),
            plugin_version=string_or_none(value(raw, "plugin_version")),
        )

    @staticmethod
    def _map_artifact(run_id: str, raw: Mapping[str, object]) -> ArtifactRef:
        artifact_id = string(value(raw, "artifact_id"))
        return ArtifactRef(
            artifact_id=artifact_id,
            run_id=run_id,
            design_id=string_or_none(value(raw, "design_id")),
            stage_key=string_or_none(value(raw, "stage_key") or value(raw, "stage")),
            kind=string_or_none(value(raw, "kind")),
            locator=string(
                value(raw, "store_key")
                or f"execution://runs/{run_id}/artifacts/{artifact_id}"
            ),
            source_hash=string_or_none(value(raw, "sha256")),
            available=True,
            created_at=parse_time(value(raw, "created_at")),
        )

    @staticmethod
    def _metric_stage(raw: Mapping[str, object]) -> str | None:
        context = mapping(value(raw, "context"))
        return string_or_none(value(context, "stage") or value(raw, "stage_key"))


def _int_or_none(value: object) -> int | None:
    return value if isinstance(value, int) else None


def _json_value(value: object) -> JsonValue:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        typed = cast(Mapping[object, object], value)
        return {str(key): _json_value(item) for key, item in typed.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in cast(Sequence[object], value)]
    return str(value)
