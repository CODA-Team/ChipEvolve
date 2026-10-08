"""Private HTTP DTOs; public service schema never reaches application code."""

from pydantic import BaseModel, Field, ValidationError

from query_agent.domain.errors import DataBoundaryError, MissingDataError


class Header(BaseModel):
    status: str
    missing: list[str] = Field(default_factory=lambda: list[str]())
    data: object


class Scope(BaseModel):
    design_id: str
    snapshot_id: str
    revision_id: str | None = None
    run_id: str
    stage: str


class Source(BaseModel):
    artifact_id: str | None = None
    sha256: str | None = None
    source_hash: str | None = None
    resolution: str | None = None

    @property
    def registered(self) -> bool:
        digest = self.sha256 or self.source_hash
        return (
            bool(self.artifact_id)
            and digest is not None
            and len(digest) == 64
            and all(char in "0123456789abcdef" for char in digest)
            and self.resolution
            not in {"unverified", "unresolved", "hash_mismatch", "ambiguous"}
        )


class Envelope[T: BaseModel](BaseModel):
    contract_version: str
    status: str
    data: T
    scope: object | None = None
    missing: list[str] = Field(default_factory=list)
    evidence: list[Source] = Field(default_factory=lambda: list[Source]())


def read[T: BaseModel](raw: object, model: type[T]) -> Envelope[T]:
    try:
        header = Header.model_validate(raw)
    except ValidationError as exc:
        raise DataBoundaryError(f"invalid data envelope: {exc}") from exc
    if header.status in ("not_found", "unavailable") or (
        header.status == "partial"
        and any(item in ("unique_object", "unique_snapshot") for item in header.missing)
    ):
        raise MissingDataError(f"data status={header.status}: {header.data}")
    try:
        result = Envelope[model].model_validate(raw)
    except ValidationError as exc:
        raise DataBoundaryError(f"invalid data contract: {exc}") from exc
    if result.contract_version != "0.2":
        raise DataBoundaryError(f"unsupported data contract {result.contract_version}")
    if result.status not in ("available", "partial", "truncated"):
        raise DataBoundaryError(f"unknown data status {result.status}")
    return result


class Resolution(BaseModel):
    snapshot: Scope


class Entity(BaseModel):
    object_id: str
    kind: str
    name: str
    cell_type: str | None = None
    master: str | None = None
    direction: str | None = None


class Target(BaseModel):
    id: str


class Context(BaseModel):
    scope: Scope
    target: Target
    entities: list[Entity]


class Metric(BaseModel):
    name: str
    value: float | None = None
    unit: str | None = None
    stage: str
    snapshot_id: str
    corner: str | None = None
    status: str
    evidence: list[Source] = Field(default_factory=lambda: list[Source]())


class Metrics(BaseModel):
    metrics: list[Metric]


class Path(BaseModel):
    path_id: str
    startpoint: str
    endpoint: str
    slack: float | None = None
    unit: str | None = None
    corner: str | None = None
    delay: float | None = None
    evidence: list[Source] = Field(default_factory=lambda: list[Source]())


class Paths(BaseModel):
    timing_paths: list[Path]
    snapshot: Scope
    truncated: bool = False


class RegisteredSource(BaseModel):
    run_id: str
    artifact_id: str
    sha256: str
    category: str | None = None


class Snapshot(Scope):
    source_artifacts: list[RegisteredSource] = Field(
        default_factory=lambda: list[RegisteredSource]()
    )


class Summary(BaseModel):
    snapshot: Snapshot


class RunSummary(BaseModel):
    run_id: str
    snapshots: list[Summary]
