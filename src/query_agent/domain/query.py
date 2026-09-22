"""Query request, planning and response models."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .capability import Capability
from .evidence import Evidence, EvidenceScope, EvidenceStatus
from .experiment import Conflict, ContextSelection


class QuerySource(StrEnum):
    """Authoritative source selected for a query."""

    LOCAL_WORKSPACE = "LOCAL_WORKSPACE"
    MANAGED_RUN = "MANAGED_RUN"


class QueryContext(BaseModel):
    """The deliberately small Phase I query scope."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    workspace: Path | None = None
    design_id: str | None = Field(default=None, min_length=1)
    run_id: str | None = Field(default=None, min_length=1)
    run_ids: tuple[str, ...] = ()
    stage: str | None = Field(default=None, min_length=1)
    source: QuerySource = QuerySource.LOCAL_WORKSPACE

    @model_validator(mode="after")
    def source_has_required_scope(self) -> QueryContext:
        if self.source is QuerySource.LOCAL_WORKSPACE and self.workspace is None:
            raise ValueError("workspace is required for a local workspace query")
        if self.source is QuerySource.MANAGED_RUN:
            if self.run_id is None and not self.run_ids and self.design_id is None:
                raise ValueError(
                    "managed run queries need a run_id, run_ids, or design_id"
                )
            if self.workspace is not None:
                raise ValueError(
                    "managed run queries must not provide an attempt workspace"
                )
            if (
                self.run_id is not None
                and self.run_ids
                and self.run_id not in self.run_ids
            ):
                raise ValueError("run_id must be included in run_ids when both are set")
        return self


class QueryRequest(BaseModel):
    """A user question plus its bounded execution/design context."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    query: str = Field(min_length=1)
    context: QueryContext

    @field_validator("query")
    @classmethod
    def query_is_not_whitespace(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("query must not be blank")
        return value.strip()


class QueryIntent(StrEnum):
    """Question type, independent of whether it is answerable."""

    DOMAIN_KNOWLEDGE = "DOMAIN_KNOWLEDGE"
    HOW_TO = "HOW_TO"
    ARTIFACT_DISCOVERY = "ARTIFACT_DISCOVERY"
    EXPLICIT_FACT = "EXPLICIT_FACT"
    FLOW_STATUS = "FLOW_STATUS"
    LOG_DIAGNOSIS = "LOG_DIAGNOSIS"
    METRIC_QUERY = "METRIC_QUERY"
    CROSS_RUN_COMPARE = "CROSS_RUN_COMPARE"
    ROOT_CAUSE = "ROOT_CAUSE"
    RECOMMENDATION = "RECOMMENDATION"
    DESIGN_OBJECT_QUERY = "DESIGN_OBJECT_QUERY"
    ANALYSIS_QUERY = "ANALYSIS_QUERY"
    UNKNOWN = "UNKNOWN"


class RunSelectionMode(StrEnum):
    """Application policy for resolving an implicit experiment context."""

    AUTO = "AUTO"
    EXPLICIT = "EXPLICIT"
    LATEST = "LATEST"
    LATEST_VALID = "LATEST_VALID"
    CURRENT = "CURRENT"
    COMPARISON = "COMPARISON"


class EvidenceRequirement(BaseModel):
    """A precise statement of evidence needed by a plan."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    description: str = Field(min_length=1)
    required_capabilities: tuple[Capability, ...] = ()
    minimum_items: int = Field(default=1, ge=1)
    scope: EvidenceScope | None = None
    fact_key: str | None = Field(default=None, min_length=1)
    requires_current: bool = False


class QueryPlan(BaseModel):
    """Typed plan produced before any provider is touched."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    intent: QueryIntent
    evidence_requirements: tuple[EvidenceRequirement, ...] = ()
    required_capabilities: tuple[Capability, ...] = ()
    run_selection: RunSelectionMode = RunSelectionMode.AUTO


class QueryStatus(StrEnum):
    """Normal business outcomes of a query."""

    ANSWERED = "ANSWERED"
    PARTIAL = "PARTIAL"
    NEEDS_MORE_DATA = "NEEDS_MORE_DATA"
    UNSUPPORTED = "UNSUPPORTED"
    FAILED = "FAILED"


class QueryResponse(BaseModel):
    """Response that can explicitly report missing evidence/capabilities."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: QueryStatus
    answer: str | None = None
    evidence_citations: tuple[str, ...] = ()
    evidence_status: EvidenceStatus = EvidenceStatus.SUFFICIENT
    reasons: tuple[str, ...] = ()
    missing_evidence: tuple[EvidenceRequirement, ...] = ()
    missing_capabilities: tuple[Capability, ...] = ()
    next_steps: tuple[str, ...] = ()
    evidence: tuple[Evidence, ...] = ()
    context_selection: ContextSelection | None = None
    conflicts: tuple[Conflict, ...] = ()
