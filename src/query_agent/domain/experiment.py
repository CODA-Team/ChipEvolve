"""Stable vocabulary for experiment state and evidence ownership."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from .evidence import EvidenceScope, EvidenceStatus, JsonValue


class ExperimentStatus(StrEnum):
    """Run lifecycle states understood by context policies."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    LOST = "lost"
    UNKNOWN = "unknown"

    @property
    def completed(self) -> bool:
        """Whether the run has a terminal result suitable for comparison."""

        return self in {
            ExperimentStatus.SUCCEEDED,
            ExperimentStatus.FAILED,
            ExperimentStatus.CANCELLED,
            ExperimentStatus.TIMED_OUT,
            ExperimentStatus.LOST,
        }

    @property
    def valid(self) -> bool:
        """Whether the run completed successfully."""

        return self is ExperimentStatus.SUCCEEDED

    @classmethod
    def from_raw(cls, value: object) -> ExperimentStatus:
        normalized = str(value or "unknown").strip().lower().replace("-", "_")
        if normalized in {"complete", "completed", "success", "succeeded"}:
            return cls.SUCCEEDED
        try:
            return cls(normalized)
        except ValueError:
            return cls.UNKNOWN


class StageStatus(StrEnum):
    """Lifecycle state for one named stage inside an experiment run."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"

    @property
    def completed(self) -> bool:
        return self in {
            StageStatus.SUCCEEDED,
            StageStatus.FAILED,
            StageStatus.CANCELLED,
        }

    @classmethod
    def from_raw(cls, value: object) -> StageStatus:
        normalized = str(value or "unknown").strip().lower().replace("-", "_")
        if normalized in {"complete", "completed", "success", "succeeded"}:
            return cls.SUCCEEDED
        try:
            return cls(normalized)
        except ValueError:
            return cls.UNKNOWN


class ExperimentStage(BaseModel):
    """A stage owned by a run, with canonical comparison semantics."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    stage_key: str = Field(min_length=1)
    ordinal: int | None = None
    status: StageStatus = StageStatus.UNKNOWN
    plugin_id: str | None = None
    plugin_version: str | None = None

    @property
    def canonical_key(self) -> str:
        return canonical_stage_key(self.stage_key)


class ExperimentRun(BaseModel):
    """Run identity and lifecycle information needed by selection policy."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str = Field(min_length=1)
    design_id: str | None = None
    status: ExperimentStatus = ExperimentStatus.UNKNOWN
    created_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    stages: tuple[ExperimentStage, ...] = ()

    def stage(self, stage_key: str | None) -> ExperimentStage | None:
        """Find a stage using one canonicalized semantic key."""

        if stage_key is None:
            return None
        wanted = canonical_stage_key(stage_key)
        return next(
            (item for item in self.stages if item.canonical_key == wanted), None
        )


class ProvenanceRef(BaseModel):
    """Bounded provenance pointer without copying a raw provider response."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    locator: str = Field(min_length=1)
    source_hash: str | None = Field(default=None, min_length=64, max_length=64)
    authoritative: bool = True
    observed_at: datetime | None = None


class ArtifactRef(BaseModel):
    """Registered artifact and its run/stage ownership."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    artifact_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    design_id: str | None = None
    stage_key: str | None = None
    kind: str | None = None
    locator: str = Field(min_length=1)
    source_hash: str | None = Field(default=None, min_length=64, max_length=64)
    available: bool = True
    created_at: datetime | None = None

    @property
    def canonical_stage(self) -> str | None:
        return canonical_stage_key(self.stage_key) if self.stage_key else None


class MetricObservation(BaseModel):
    """A metric value with explicit semantic and artifact ownership."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    metric_name: str = Field(min_length=1)
    value: JsonValue
    unit: str | None = None
    run_id: str = Field(min_length=1)
    design_id: str | None = None
    stage_key: str | None = None
    artifact_id: str | None = None
    source_hash: str | None = Field(default=None, min_length=64, max_length=64)
    complete: bool = True
    observed_at: datetime | None = None
    corner: str | None = None
    parser_id: str | None = None
    parser_version: str | None = None

    @property
    def fact_key(self) -> str:
        return f"metric:{self.metric_name.upper()}"

    @property
    def canonical_stage(self) -> str | None:
        return canonical_stage_key(self.stage_key) if self.stage_key else None

    @property
    def scope(self) -> EvidenceScope:
        return EvidenceScope(
            design_id=self.design_id,
            run_id=self.run_id,
            stage=self.stage_key,
        )

    @property
    def evidence_status(self) -> EvidenceStatus:
        return EvidenceStatus.SUFFICIENT if self.complete else EvidenceStatus.PARTIAL


class ExperimentContext(BaseModel):
    """A bounded snapshot assembled from one or more provider reads."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    design_id: str | None = None
    runs: tuple[ExperimentRun, ...] = ()
    artifacts: tuple[ArtifactRef, ...] = ()
    metrics: tuple[MetricObservation, ...] = ()
    provenance: tuple[ProvenanceRef, ...] = ()


class CandidateRejection(BaseModel):
    """Why a run or stage was not eligible for a context."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_id: str = Field(min_length=1)
    reason_code: str = Field(min_length=1)
    detail: str = Field(min_length=1)


class ContextSelection(BaseModel):
    """Deterministic selection result retained for traceability."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    selected_run_id: str | None = None
    selected_stage_key: str | None = None
    candidate_run_ids: tuple[str, ...] = ()
    rejected: tuple[CandidateRejection, ...] = ()
    reason_codes: tuple[str, ...] = ()


class ComparisonScope(BaseModel):
    """Semantic dimensions that must align before comparing observations."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    design_id: str | None = None
    stage_key: str | None = None
    metric_name: str = Field(min_length=1)
    unit: str | None = None
    corner: str | None = None


class ComparisonSet(BaseModel):
    """Comparable observations and explicit exclusions."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    scope: ComparisonScope
    observations: tuple[MetricObservation, ...] = ()
    rejected: tuple[CandidateRejection, ...] = ()


class ConflictKind(StrEnum):
    VALUE_MISMATCH = "value_mismatch"
    PROVENANCE_MISMATCH = "provenance_mismatch"
    MISSING_ARTIFACT = "missing_artifact"
    SCOPE_MISMATCH = "scope_mismatch"


class Conflict(BaseModel):
    """Unresolved disagreement retained instead of choosing a winner."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: ConflictKind
    fact_key: str = Field(min_length=1)
    scope: EvidenceScope
    evidence_ids: tuple[str, ...] = ()
    values: tuple[JsonValue, ...] = ()
    reason: str = Field(min_length=1)


class FreshnessState(StrEnum):
    CURRENT = "current"
    STALE = "stale"
    UNKNOWN = "unknown"


class FreshnessAssessment(BaseModel):
    """Explainable current/stale assessment for one run-scoped fact."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    state: FreshnessState
    evidence_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class ResolvedExperimentContext(BaseModel):
    """Context plus policy outputs consumed by collection and tracing."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    context: ExperimentContext
    selection: ContextSelection
    comparison: ComparisonSet | None = None
    conflicts: tuple[Conflict, ...] = ()
    freshness: tuple[FreshnessAssessment, ...] = ()


def canonical_stage_key(stage_key: str) -> str:
    """Normalize only known stage aliases; preserve unknown stage names."""

    normalized = stage_key.strip().lower().replace("-", "_").replace(" ", "_")
    return {
        "place": "placement",
        "placement": "placement",
        "route": "routing",
        "routing": "routing",
        "clock_tree": "cts",
        "clock_tree_synthesis": "cts",
        "cts": "cts",
    }.get(normalized, normalized)
