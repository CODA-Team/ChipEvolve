"""Installed SDK → typed design and analysis evidence; no service internals."""

from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from typing import Literal
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

from .models import (
    Context,
    Entity,
    Metrics,
    NetEngineering,
    Objects,
    Paths,
    Physical,
    Relationships,
    Resolution,
    Scope,
    Source,
    read,
)


def call[T](operation: Callable[[], T]) -> T:
    try:
        return operation()
    except EdaAiError as exc:
        if exc.status == 404:
            raise MissingDataError(str(exc)) from exc
        raise DataBoundaryError(str(exc)) from exc


class DataFoundationProvider:
    """Scoped design facts with complete page traversal and explicit units."""

    def __init__(self, client: EdaAiClient) -> None:
        self.client = client

    @property
    def capabilities(self) -> frozenset[Capability]:
        return frozenset(
            {
                Capability.DESIGN_OBJECT_QUERY,
                Capability.DESIGN_RELATION_QUERY,
                Capability.SPECIALIZED_ANALYSIS,
            }
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
        for row in result.data.entities:
            row.evidence.extend(
                source
                for source in result.evidence
                if source.record_id == row.object_id and source.registered
            )
        return result.data

    def _target(self, pack: Context) -> Entity:
        rows = [row for row in pack.entities if row.object_id == pack.target.id]
        if len(rows) != 1:
            raise DataBoundaryError("context lacks exactly one target entity")
        return rows[0]

    def _ref(self, row: Entity, scope: Scope) -> DesignObjectRef:
        return DesignObjectRef(
            object_id=row.object_id,
            source_hash=next(
                (
                    item.sha256 or item.source_hash
                    for item in row.evidence
                    if item.registered
                ),
                None,
            ),
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
        cell = row.cell
        if not cell:
            raise MissingDataError("instance exists but its cell type is not indexed")
        return DesignInstance(ref=self._ref(row, pack.scope), cell_type=cell)

    def get_net(self, context: QueryContext, name: str) -> DesignNet | None:
        pack = self._context(context, name, "net")
        return DesignNet(ref=self._ref(self._target(pack), pack.scope))

    def get_pin(self, context: QueryContext, name: str) -> DesignPin | None:
        pack = self._context(context, name, "pin")
        row = self._target(pack)
        return DesignPin(ref=self._ref(row, pack.scope), direction=row.pin_direction)

    def _reference_context(
        self,
        context: QueryContext,
        ref: DesignObjectRef,
        kind: DesignObjectKind | None = None,
    ) -> Context:
        if kind is not None and ref.kind is not kind:
            raise DataBoundaryError("reference kind differs from operation target")
        pack = self._context(context, ref.name, ref.kind.value)
        for field in ("design_id", "snapshot_id", "revision_id", "run_id", "stage"):
            value = getattr(ref, field)
            if value is not None and value != getattr(pack.scope, field):
                raise DataBoundaryError("object reference crosses the requested scope")
        if ref.object_id is not None and ref.object_id != pack.target.id:
            raise DataBoundaryError("object reference identity changed")
        return pack

    def _objects(
        self, scope: Scope, **filters: str | int | float | bool
    ) -> list[Entity]:
        rows: list[Entity] = []
        offset, total = 0, None
        while True:
            result = read(
                call(
                    lambda offset=offset: self.client.query_objects(
                        scope.snapshot_id, **filters, limit=1000, offset=offset
                    )
                ),
                Objects,
            )
            page = result.data
            if page.snapshot != scope:
                raise DataBoundaryError("object page crosses the requested scope")
            if total is not None and page.count != total:
                raise DataBoundaryError("object count changed during page traversal")
            total = page.count
            if total > 100000:
                raise MissingDataError(
                    "complete result exceeds provider limit; use paged data API"
                )
            rows.extend(page.objects)
            if page.next_offset is None:
                break
            if page.next_offset != offset + len(page.objects) or not page.objects:
                raise DataBoundaryError("object pagination did not advance correctly")
            offset = page.next_offset
        if len(rows) != total or len({row.object_id for row in rows}) != total:
            raise DataBoundaryError(
                "object pages have incomplete or duplicate identities"
            )
        return rows

    def get_connections(
        self, context: QueryContext, object_ref: DesignObjectRef
    ) -> Sequence[DesignConnection]:
        pack = self._reference_context(context, object_ref)
        scope = pack.scope
        offset, total = 0, None
        connections: list[DesignConnection] = []
        seen: set[str] = set()
        while True:
            result = read(
                call(
                    lambda offset=offset: self.client.get_relationships(
                        scope.snapshot_id,
                        pack.target.id,
                        kind=object_ref.kind.value,
                        limit=1000,
                        offset=offset,
                    )
                ),
                Relationships,
            )
            page = result.data
            if page.snapshot != scope or page.target.object_id != pack.target.id:
                raise DataBoundaryError("relationship page crosses target or scope")
            if page.coverage.missing_entity_ids:
                raise MissingDataError(
                    "relationship endpoint identities are incomplete"
                )
            if total is not None and page.count != total:
                raise DataBoundaryError("relationship count changed during traversal")
            total = page.count
            if total > 100000:
                raise MissingDataError(
                    "relationships exceed provider limit; use paged data API"
                )
            entities = {row.object_id: row for row in page.entities}
            for row in page.relations:
                if row.relation_id in seen:
                    raise DataBoundaryError("duplicate relationship across pages")
                seen.add(row.relation_id)
                if row.subject_id not in entities or row.object_id not in entities:
                    raise MissingDataError("relationship references an absent endpoint")
                connections.append(
                    DesignConnection(
                        source=self._ref(entities[row.subject_id], scope),
                        target=self._ref(entities[row.object_id], scope),
                        predicate=row.predicate,
                    )
                )
            if page.next_offset is None:
                break
            if page.next_offset != offset + len(page.relations) or not page.relations:
                raise DataBoundaryError(
                    "relationship pagination did not advance correctly"
                )
            offset = page.next_offset
        if len(connections) != total:
            raise DataBoundaryError("relationship page coverage is incomplete")
        return connections

    def get_fanout(
        self, context: QueryContext, net_ref: DesignObjectRef
    ) -> Sequence[DesignPin]:
        pack = self._reference_context(context, net_ref, DesignObjectKind.NET)
        scope = pack.scope
        engineering = read(
            call(
                lambda: self.client.get_net_engineering(
                    scope.snapshot_id, pack.target.id, limit=1
                )
            ),
            NetEngineering,
        ).data
        if engineering.snapshot != scope:
            raise DataBoundaryError("net response crosses the requested scope")
        coverage = engineering.availability.get("complete_connectivity", {})
        if coverage.get("status") == "unavailable":
            raise MissingDataError("native and indexed connectivity counts disagree")
        pins = self._objects(
            scope, kind="pin", connected_to=pack.target.id, net_role="load"
        )
        if len(pins) != engineering.load_count or any(
            row.kind != "pin" for row in pins
        ):
            raise DataBoundaryError("fanout does not match complete load identities")
        return [
            DesignPin(ref=self._ref(row, scope), direction=row.pin_direction)
            for row in pins
        ]

    def get_location(
        self, context: QueryContext, instance_ref: DesignObjectRef
    ) -> DesignLocation | None:
        pack = self._reference_context(context, instance_ref, DesignObjectKind.INSTANCE)
        result = read(
            call(
                lambda: self.client.get_physical_context(
                    pack.scope.snapshot_id, pack.target.id
                )
            ),
            Physical,
        ).data
        if result.snapshot != pack.scope:
            raise DataBoundaryError("physical response crosses the requested scope")
        coordinates = result.physical_context.location_um
        if (
            coordinates is None
            or len(coordinates) != 2
            or any(v is None for v in coordinates)
        ):
            raise MissingDataError("placed location in micrometres is unavailable")
        x, y = coordinates
        assert x is not None and y is not None
        return DesignLocation(x=x, y=y, units="um")

    def get_instances_in_region(
        self, context: QueryContext, region: DesignRegion
    ) -> Sequence[DesignInstance]:
        if region.units not in ("um", "dbu"):
            raise MissingDataError("region requires explicit um or dbu units")
        scope = self.resolve(context)
        bounds = ",".join(
            str(v) for v in (region.x_min, region.y_min, region.x_max, region.y_max)
        )
        rows = self._objects(
            scope, kind="instance", region=bounds, region_units=region.units
        )
        if any(row.kind != "instance" or not row.cell for row in rows):
            raise MissingDataError("region contains instances without cell identity")
        return [
            DesignInstance(ref=self._ref(row, scope), cell_type=row.cell)
            for row in rows
            if row.cell
        ]

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
        check: Literal["setup", "hold"] = "setup",
    ) -> Sequence[TimingPathObservation]:
        scope = self.resolve(context)
        result = read(
            call(
                lambda: self.client.get_timing_paths(
                    scope.snapshot_id,
                    check=check,
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
            if row.check is not None and row.check != check:
                raise DataBoundaryError("timing path check differs from the request")
            if row.slack is None or row.unit is None:
                continue
            if slack_below is not None and row.slack >= slack_below:
                continue
            rows.append(
                TimingPathObservation(
                    path_id=row.path_id,
                    check=row.check,
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
                    and row.check == check
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
