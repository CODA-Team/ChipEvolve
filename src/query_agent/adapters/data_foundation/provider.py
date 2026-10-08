"""Installed SDK → typed design and analysis evidence; no service internals."""

from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from urllib.parse import quote

from eda_ai_client import EdaAiClient, EdaAiError

from query_agent.domain.analysis import (
    AnalysisProvenance,
    AnalysisScope,
    TimingMetricObservation,
    TimingPathObservation,
)
from query_agent.domain.capability import Capability
from query_agent.domain.design import (
    DesignConnection,
    DesignInstance,
    DesignLocation,
    DesignNet,
    DesignObjectKind,
    DesignObjectRef,
    DesignPin,
    DesignRegion,
)
from query_agent.domain.errors import DataBoundaryError, MissingDataError
from query_agent.domain.query import QueryContext

from .models import Context, Entity, Metrics, Paths, Resolution, Scope, Source, read


def call[T](operation: Callable[[], T]) -> T:
    try:
        return operation()
    except EdaAiError as exc:
        if exc.status == 404:
            raise MissingDataError(str(exc)) from exc
        raise DataBoundaryError(str(exc)) from exc


class DataFoundationProvider:
    """Truthful narrow provider: exact objects and indexed timing observations.

    Relations, region and location need unit/coverage-specific domain ports and
    are not advertised here. No empty result is interpreted as proof of absence.
    """

    def __init__(self, client: EdaAiClient) -> None:
        self.client = client

    @property
    def capabilities(self) -> frozenset[Capability]:
        return frozenset(
            {Capability.DESIGN_OBJECT_QUERY, Capability.SPECIALIZED_ANALYSIS}
        )

    def resolve(self, context: QueryContext) -> Scope:
        result = read(
            call(
                lambda: self.client.resolve_scope(
                    snapshot_id=context.snapshot_id,
                    design_id=context.design_id,
                    revision_id=context.revision_id,
                    run_id=context.run_id,
                    stage=context.stage,
                    origin="all" if context.snapshot_id else "flow",
                )
            ),
            Resolution,
        )
        return result.data.snapshot

    def _context(self, context: QueryContext, name: str, kind: str) -> Context:
        scope = self.resolve(context)
        result = read(
            call(
                lambda: self.client.get_object_context(
                    scope.snapshot_id,
                    name=name,
                    kind=kind,
                )
            ),
            Context,
        )
        if result.data.scope != scope:
            raise DataBoundaryError(
                "object response scope differs from resolved snapshot"
            )
        return result.data

    def _target(self, pack: Context) -> Entity:
        rows = [row for row in pack.entities if row.object_id == pack.target.id]
        if len(rows) != 1:
            raise DataBoundaryError("context lacks exactly one target entity")
        return rows[0]

    def _ref(self, row: Entity, scope: Scope) -> DesignObjectRef:
        return DesignObjectRef(
            design_id=scope.design_id,
            kind=DesignObjectKind(row.kind),
            name=row.name,
            locator=self.client.data_url
            + "/snapshots/"
            + quote(scope.snapshot_id, safe="")
            + "/objects/"
            + quote(row.object_id, safe=""),
            snapshot_id=scope.snapshot_id,
            revision_id=scope.revision_id,
            run_id=scope.run_id,
            stage=scope.stage,
        )

    def get_instance(self, context: QueryContext, name: str) -> DesignInstance | None:
        pack = self._context(context, name, "instance")
        row = self._target(pack)
        cell = row.cell_type or row.master
        if not cell:
            raise MissingDataError("instance exists but its cell type is not indexed")
        return DesignInstance(ref=self._ref(row, pack.scope), cell_type=cell)

    def get_net(self, context: QueryContext, name: str) -> DesignNet | None:
        pack = self._context(context, name, "net")
        return DesignNet(ref=self._ref(self._target(pack), pack.scope))

    def get_pin(self, context: QueryContext, name: str) -> DesignPin | None:
        pack = self._context(context, name, "pin")
        row = self._target(pack)
        return DesignPin(ref=self._ref(row, pack.scope), direction=row.direction)

    def get_connections(
        self, context: QueryContext, object_ref: DesignObjectRef
    ) -> Sequence[DesignConnection]:
        raise MissingDataError("typed relation coverage is not connected")

    def get_fanout(
        self, context: QueryContext, net_ref: DesignObjectRef
    ) -> Sequence[DesignPin]:
        raise MissingDataError("typed fanout coverage is not connected")

    def get_location(
        self, context: QueryContext, instance_ref: DesignObjectRef
    ) -> DesignLocation | None:
        raise MissingDataError("typed location units are not connected")

    def get_instances_in_region(
        self, context: QueryContext, region: DesignRegion
    ) -> Sequence[DesignInstance]:
        raise MissingDataError("typed region units are not connected")

    def get_timing_metrics(
        self, context: QueryContext, *, metric_name: str | None = None
    ) -> Sequence[TimingMetricObservation]:
        scope = self.resolve(context)
        result = read(
            call(
                lambda: self.client.get_metrics(
                    snapshot_id=scope.snapshot_id,
                    name=metric_name,
                )
            ),
            Metrics,
        )
        rows: list[TimingMetricObservation] = []
        for row in result.data.metrics:
            if row.name not in ("WNS", "TNS") or row.value is None:
                continue
            if row.snapshot_id != scope.snapshot_id or row.stage != scope.stage:
                raise DataBoundaryError("metric response crosses the requested scope")
            rows.append(
                TimingMetricObservation(
                    metric_name=row.name,
                    value=row.value,
                    unit=row.unit,
                    scope=AnalysisScope(**scope.model_dump(), corner=row.corner),
                    provenance=self._provenance(scope, "metrics", row.evidence),
                    complete=row.status == "available"
                    and bool(row.unit and row.corner)
                    and any(source.registered for source in row.evidence),
                )
            )
        return rows

    def get_timing_paths(
        self,
        context: QueryContext,
        *,
        limit: int = 10,
        slack_below: float | None = None,
    ) -> Sequence[TimingPathObservation]:
        scope = self.resolve(context)
        result = read(
            call(
                lambda: self.client.get_timing_paths(
                    scope.snapshot_id,
                    sort="slack",
                    order="worst",
                    limit=limit,
                    detail="full",
                )
            ),
            Paths,
        )
        if result.data.snapshot != scope:
            raise DataBoundaryError("timing path response crosses the requested scope")
        rows: list[TimingPathObservation] = []
        for row in result.data.timing_paths:
            if row.slack is None or row.unit is None:
                continue
            if slack_below is not None and row.slack >= slack_below:
                continue
            rows.append(
                TimingPathObservation(
                    path_id=row.path_id,
                    startpoint=row.startpoint,
                    endpoint=row.endpoint,
                    slack=row.slack,
                    unit=row.unit,
                    total_delay=row.delay,
                    scope=AnalysisScope(**scope.model_dump(), corner=row.corner),
                    provenance=self._provenance(
                        scope,
                        "timing-paths/" + quote(row.path_id, safe=""),
                        row.evidence,
                    ),
                    complete=bool(row.corner)
                    and any(source.registered for source in row.evidence),
                )
            )
        return rows

    def _provenance(
        self, scope: Scope, tail: str, sources: list[Source]
    ) -> AnalysisProvenance:
        source = next((item for item in sources if item.registered), None)
        digest = (source.sha256 or source.source_hash) if source else None
        snapshot = quote(scope.snapshot_id, safe="")
        locator = f"{self.client.data_url}/snapshots/{snapshot}/{tail}"
        if source and source.artifact_id and source.resolution != "bundle_member":
            locator = (
                f"{self.client.data_url}/snapshots/{snapshot}/sources/"
                f"{quote(source.artifact_id, safe='')}/excerpt"
            )
        return AnalysisProvenance(
            provider="data-foundation",
            source_hash=digest,
            locator=locator,
            observed_at=datetime.now(UTC),
        )
