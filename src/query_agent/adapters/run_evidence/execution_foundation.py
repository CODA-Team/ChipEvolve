"""Map the execution foundation's public read API into Query Agent evidence."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Protocol, cast

from query_agent.domain.capability import Capability
from query_agent.domain.errors import RunEvidenceError
from query_agent.domain.evidence import (
    Evidence,
    EvidenceLevel,
    EvidenceLocator,
    EvidenceProvenance,
    EvidenceScope,
    EvidenceSourceKind,
    EvidenceStatus,
    JsonValue,
)
from query_agent.domain.query import QueryContext, QuerySource
from query_agent.ports.run_evidence import RunEvidenceProvider


class PublicExecutionClient(Protocol):
    """The narrow public-client surface used by this adapter.

    The actual execution-foundation client can be injected by a composition
    root. Keeping this protocol here prevents its package types from entering
    Query Agent domain or application code and makes mapping tests deterministic.
    """

    def run(self, run_id: str) -> Mapping[str, object]: ...

    def metrics(
        self, run_id: str, *, complete_only: bool = False
    ) -> Sequence[Mapping[str, object]]: ...

    def artifacts(
        self,
        run_id: str,
        *,
        category: str | None = None,
        format: str | None = None,
        stage: str | None = None,
    ) -> Sequence[Mapping[str, object]]: ...

    def logs(
        self, run_id: str, *, offset: int = 0, max_bytes: int | None = None
    ) -> Mapping[str, object]: ...

    def artifact_excerpt(
        self, run_id: str, artifact_id: str, *, offset: int = 0, max_bytes: int = 8192
    ) -> Mapping[str, object]: ...

    def timeline(self, run_id: str) -> Sequence[Mapping[str, object]]: ...

    def graph(self, run_ids: Sequence[str]) -> Mapping[str, object]: ...


class ExecutionFoundationRunEvidenceAdapter(RunEvidenceProvider):
    """Read registered run evidence without opening the foundation state root."""

    _provider_name = "execution-foundation-public-api"

    def __init__(
        self, client: PublicExecutionClient, *, max_log_bytes: int = 64 * 1024
    ):
        if max_log_bytes <= 0:
            raise ValueError("max_log_bytes must be positive")
        self._client = client
        self._max_log_bytes = max_log_bytes

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

    def get_run_summary(self, context: QueryContext) -> Sequence[Evidence]:
        run_id = self._run_id(context)
        run = self._client.run(run_id)
        return (
            self._evidence(
                context=context,
                content={
                    "run_id": run_id,
                    "status": _value(run, "status"),
                    "task_id": _value(run, "task_id"),
                    "created_at": _value(run, "created_at"),
                    "started_at": _value(run, "started_at"),
                    "ended_at": _value(run, "ended_at"),
                    "terminal_reason": _value(run, "terminal_reason"),
                },
                locator=f"execution://runs/{run_id}/summary",
                fact_key="run:status",
                source_mtime=_parse_time(_value(run, "ended_at")),
            ),
        )

    def get_stage_evidence(self, context: QueryContext) -> Sequence[Evidence]:
        run_id = self._run_id(context)
        run = self._client.run(run_id)
        stages = _sequence(_value(run, "stages"))
        evidence: list[Evidence] = []
        for stage in stages:
            stage_key = _string(_value(stage, "stage_key"))
            if context.stage is not None and stage_key != context.stage:
                continue
            stage_content = {
                key: _json_value(_value(stage, key))
                for key in (
                    "stage_key",
                    "ordinal",
                    "plugin_id",
                    "plugin_version",
                    "status",
                )
            }
            evidence.append(
                self._evidence(
                    context=context,
                    stage=stage_key,
                    content=stage_content,
                    locator=f"execution://runs/{run_id}/stages/{stage_key}",
                    fact_key=f"stage:{stage_key}:status",
                )
            )
        return tuple(evidence)

    def get_metrics(
        self, context: QueryContext, *, metric_name: str | None = None
    ) -> Sequence[Evidence]:
        run_id = self._run_id(context)
        artifact_index = self._artifact_index(run_id)
        metrics = self._client.metrics(run_id)
        result: list[Evidence] = []
        for metric in metrics:
            name = _string(_value(metric, "name"))
            if metric_name is not None and name.upper() != metric_name.upper():
                continue
            artifact = _mapping(_value(metric, "artifact"))
            artifact_id = _string_or_none(_value(artifact, "artifact_id"))
            registered = artifact_index.get(artifact_id or "")
            stage = self._metric_stage(metric, registered)
            if context.stage is not None and stage != context.stage:
                continue
            source_hash = _string_or_none(_value(registered or artifact, "sha256"))
            source_mtime = _parse_time(_value(registered or artifact, "created_at"))
            complete = bool(_value(metric, "complete")) and registered is not None
            status = EvidenceStatus.SUFFICIENT if complete else EvidenceStatus.PARTIAL
            reason = None if complete else "metric source artifact is missing"
            result.append(
                self._evidence(
                    context=context,
                    stage=stage,
                    content={
                        "metric": name,
                        "value": _json_value(_value(metric, "value")),
                        "unit": _json_value(_value(metric, "unit")),
                        "parser": _json_value(_value(metric, "parser")),
                        "artifact_id": artifact_id,
                    },
                    locator=(
                        f"execution://runs/{run_id}/metrics/{name}"
                        + (f"/artifacts/{artifact_id}" if artifact_id else "")
                    ),
                    fact_key=f"metric:{name.upper()}",
                    source_hash=source_hash,
                    source_mtime=source_mtime,
                    status=status,
                    reason=reason,
                    level=EvidenceLevel.PARSED_METRIC,
                )
            )
        return tuple(result)

    def get_artifacts(self, context: QueryContext) -> Sequence[Evidence]:
        run_id = self._run_id(context)
        result: list[Evidence] = []
        for artifact in self._client.artifacts(run_id, stage=context.stage):
            artifact_id = _string(_value(artifact, "artifact_id"))
            stage = _string_or_none(_value(artifact, "stage_key"))
            result.append(
                self._evidence(
                    context=context,
                    stage=stage,
                    content=_json_object(artifact),
                    locator=f"execution://runs/{run_id}/artifacts/{artifact_id}",
                    fact_key=f"artifact:{artifact_id}",
                    source_hash=_string_or_none(_value(artifact, "sha256")),
                    source_mtime=_parse_time(_value(artifact, "created_at")),
                    level=EvidenceLevel.REGISTERED_FILE,
                )
            )
        return tuple(result)

    def get_logs(
        self, context: QueryContext, *, query: str | None = None
    ) -> Sequence[Evidence]:
        run_id = self._run_id(context)
        raw = self._client.logs(run_id, max_bytes=self._max_log_bytes)
        content = _string(_value(raw, "content"))
        if query is not None:
            lines = tuple(line for line in content.splitlines() if query in line)
            if not lines:
                return ()
            content = "\n".join(lines)
        if not content:
            return ()
        return (
            self._evidence(
                context=context,
                content={"text": content, "bytes": len(content.encode())},
                locator=f"execution://runs/{run_id}/logs",
                fact_key="run:logs",
                level=EvidenceLevel.DIRECT_EXCERPT,
            ),
        )

    def get_artifact_excerpt(
        self, context: QueryContext, artifact_id: str, *, max_bytes: int = 65536
    ) -> Sequence[Evidence]:
        run_id = self._run_id(context)
        raw = self._client.artifact_excerpt(run_id, artifact_id, max_bytes=max_bytes)
        offset = _integer(raw, "offset")
        bytes_read = _integer(raw, "bytes_read")
        return (
            self._evidence(
                context=context,
                content={
                    "artifact_id": artifact_id,
                    "text": _value(raw, "text"),
                    "offset": _value(raw, "offset"),
                    "bytes_read": _value(raw, "bytes_read"),
                    "truncated": _value(raw, "truncated"),
                },
                locator=(
                    f"execution://runs/{run_id}/artifacts/{artifact_id}/excerpt"
                    f"#bytes={offset}-{offset + bytes_read}"
                ),
                fact_key=f"artifact:{artifact_id}:excerpt",
                source_hash=_string_or_none(_value(raw, "sha256")),
                status=(
                    EvidenceStatus.PARTIAL
                    if _value(raw, "truncated")
                    else EvidenceStatus.SUFFICIENT
                ),
                reason="source excerpt is truncated"
                if _value(raw, "truncated")
                else None,
                level=EvidenceLevel.DIRECT_EXCERPT,
            ),
        )

    def get_provenance(self, context: QueryContext) -> Sequence[Evidence]:
        run_id = self._run_id(context)
        timeline = self._client.timeline(run_id)
        graph = self._client.graph([run_id])
        result: list[Evidence] = []
        if timeline:
            result.append(
                self._evidence(
                    context=context,
                    content={"timeline": _json_value(list(timeline))},
                    locator=f"execution://runs/{run_id}/timeline",
                    fact_key="run:timeline",
                )
            )
        if graph:
            result.append(
                self._evidence(
                    context=context,
                    content=_json_object(graph),
                    locator=f"execution://runs/{run_id}/graph",
                    fact_key="run:graph",
                )
            )
        return tuple(result)

    def _artifact_index(self, run_id: str) -> dict[str, Mapping[str, object]]:
        return {
            _string(_value(item, "artifact_id")): item
            for item in self._client.artifacts(run_id)
        }

    @staticmethod
    def _metric_stage(
        metric: Mapping[str, object], artifact: Mapping[str, object] | None
    ) -> str | None:
        if artifact is not None:
            stage = _string_or_none(_value(artifact, "stage_key"))
            if stage is not None:
                return stage
        context = _mapping(_value(metric, "context"))
        return _string_or_none(_value(context, "stage"))

    def _evidence(
        self,
        *,
        context: QueryContext,
        content: Mapping[str, object] | JsonValue,
        locator: str,
        fact_key: str,
        stage: str | None = None,
        source_hash: str | None = None,
        source_mtime: datetime | None = None,
        status: EvidenceStatus = EvidenceStatus.SUFFICIENT,
        reason: str | None = None,
        level: EvidenceLevel = EvidenceLevel.RUN_RECORD,
    ) -> Evidence:
        scope = EvidenceScope(
            design_id=context.design_id,
            run_id=context.run_id,
            stage=stage if stage is not None else context.stage,
        )
        retrieved_at = datetime.now(UTC)
        serialized = json.dumps(_json_value(content), sort_keys=True, default=str)
        digest = hashlib.sha256(f"{locator}:{serialized}".encode()).hexdigest()
        return Evidence(
            evidence_id=f"ev-{digest[:24]}",
            source_kind=EvidenceSourceKind.EXECUTION_RUN,
            level=level,
            content=_json_value(content),
            scope=scope,
            locator=EvidenceLocator(uri=locator),
            provenance=EvidenceProvenance(
                provider=self._provider_name,
                source_hash=source_hash,
                source_mtime=source_mtime,
                retrieved_at=retrieved_at,
            ),
            status=status,
            fact_key=fact_key,
            reason=reason,
        )

    @staticmethod
    def _run_id(context: QueryContext) -> str:
        if context.source is not QuerySource.MANAGED_RUN or context.run_id is None:
            raise RunEvidenceError(
                "ExecutionFoundationRunEvidenceAdapter requires a managed run context"
            )
        return context.run_id


def _value(mapping: Mapping[str, object] | None, key: str) -> object:
    return mapping.get(key) if mapping is not None else None


def _mapping(value: object) -> Mapping[str, object] | None:
    return cast(Mapping[str, object], value) if isinstance(value, Mapping) else None


def _sequence(value: object) -> Sequence[Mapping[str, object]]:
    if not isinstance(value, (list, tuple)):
        return ()
    values = cast(Sequence[object], value)
    return tuple(
        cast(Mapping[str, object], item) for item in values if isinstance(item, Mapping)
    )


def _string(value: object) -> str:
    return str(value) if value is not None else ""


def _string_or_none(value: object) -> str | None:
    return None if value is None else str(value)


def _parse_time(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _json_object(value: Mapping[str, object] | None) -> dict[str, JsonValue]:
    if value is None:
        return {}
    return {str(key): _json_value(item) for key, item in value.items()}


def _json_value(value: object) -> JsonValue:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Mapping):
        typed = cast(Mapping[str, object], value)
        return {str(key): _json_value(item) for key, item in typed.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in cast(Sequence[object], value)]
    return str(value)


def mapping(value: object) -> Mapping[str, object] | None:
    """Normalize an optional mapping for sibling adapter modules."""

    return _mapping(value)


def parse_time(value: object) -> datetime | None:
    """Parse provider timestamps consistently across adapters."""

    return _parse_time(value)


def sequence(value: object) -> Sequence[Mapping[str, object]]:
    """Normalize a provider sequence of objects."""

    return _sequence(value)


def string(value: object) -> str:
    """Convert a provider scalar to a bounded string."""

    return _string(value)


def string_or_none(value: object) -> str | None:
    """Convert an optional provider scalar."""

    return _string_or_none(value)


def value(mapping_value: Mapping[str, object] | None, key: str) -> object:
    """Read one optional field from a provider object."""

    return _value(mapping_value, key)


def _integer(raw: Mapping[str, object], key: str) -> int:
    value = _value(raw, key)
    if value is None:
        return 0
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise RunEvidenceError(f"{key} must be a nonnegative integer")
    return value
