"""Typed, content-light query execution trace."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .capability import Capability
from .evidence import EvidenceStatus
from .experiment import Conflict, ContextSelection, FreshnessAssessment
from .query import (
    EvidenceRequirement,
    QueryIntent,
    QueryPlan,
    QueryRequest,
    QueryStatus,
)


class ProviderCall(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: str = Field(min_length=1)
    operation: str = Field(min_length=1)


class QueryTrace(BaseModel):
    """Trace identifiers and decisions without copying raw chip evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    request: QueryRequest
    intent: QueryIntent
    plan: QueryPlan
    provider_calls: tuple[ProviderCall, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    evidence_locators: tuple[str, ...] = ()
    source_hashes: tuple[str, ...] = ()
    evidence_status: EvidenceStatus
    missing_requirements: tuple[EvidenceRequirement, ...] = ()
    missing_capabilities: tuple[Capability, ...] = ()
    prompt_version: str | None = None
    model_name: str | None = None
    final_status: QueryStatus
    context_selection: ContextSelection | None = None
    conflicts: tuple[Conflict, ...] = ()
    freshness: tuple[FreshnessAssessment, ...] = ()
