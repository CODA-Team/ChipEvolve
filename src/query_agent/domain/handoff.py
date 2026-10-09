"""Bounded downstream tasks carry fixed inputs and reviewable permissions."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .evidence import EvidenceLocator, EvidenceScope, EvidenceStatus
from .investigation import AnswerClaim, FixedScope, Hypothesis


class FixedInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    role: str
    logical_path: str = Field(min_length=1)
    artifact_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=0)


class EvidenceReference(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    evidence_id: str
    scope: EvidenceScope
    locator: EvidenceLocator
    source_hash: str | None
    status: EvidenceStatus


class BufferPermission(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    instance: str = Field(min_length=1)
    original_master: str = Field(min_length=1)
    allowed_masters: list[str] = Field(min_length=1, max_length=8)
    operation: Literal["buffer_resize"] = "buffer_resize"

    @model_validator(mode="after")
    def unique_targets(self) -> BufferPermission:
        if len(set(self.allowed_masters)) != len(self.allowed_masters):
            raise ValueError("allowed buffer masters must be unique")
        return self


class HandoffBudget(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    max_experiments: int = Field(default=1, ge=1, le=2)
    max_seconds: int = Field(default=300, ge=1, le=1800)
    cpu_cores: int = Field(default=2, ge=1, le=8)
    memory_bytes: int = Field(default=6 * 1024**3, ge=1, le=24 * 1024**3)


class HandoffPackage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["1"] = "1"
    handoff_id: str
    investigation_id: str
    role: Literal["eco", "flow", "code"]
    objective: str = Field(min_length=1)
    scope: FixedScope
    fixed_inputs: list[FixedInput] = Field(min_length=1)
    confirmed_facts: list[AnswerClaim]
    hypotheses: list[Hypothesis]
    evidence: list[EvidenceReference]
    buffer_permissions: list[BufferPermission] = Field(
        default_factory=list[BufferPermission]
    )
    budget: HandoffBudget = Field(default_factory=HandoffBudget)
    evaluation_conditions: list[str]
    success_conditions: list[str] = Field(min_length=1)
    refusal_conditions: list[str] = Field(min_length=1)
    consumer_status: Literal["ready", "contract_only"]
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def validate_scope_and_permissions(self) -> HandoffPackage:
        references = {item.evidence_id for item in self.evidence}
        if any(set(claim.evidence_ids) - references for claim in self.confirmed_facts):
            raise ValueError("confirmed facts must cite packaged evidence")
        if self.role == "eco" and not self.buffer_permissions:
            raise ValueError("ECO needs explicit allowed buffer instances and masters")
        if self.role != "eco" and self.buffer_permissions:
            raise ValueError("buffer resize permissions belong only to an ECO task")
        if self.role != "eco" and self.consumer_status != "contract_only":
            raise ValueError(
                "Flow and Code consumers are contract-only in this release"
            )
        roles = {item.role for item in self.fixed_inputs}
        if (
            self.role == "eco"
            and not {"raw_design_database", "raw_constraints", "raw_library"} <= roles
        ):
            raise ValueError("ECO needs original database, constraints and libraries")
        paths = [item.logical_path for item in self.fixed_inputs]
        if len(set(paths)) != len(paths):
            raise ValueError("fixed input destinations must be unique")
        return self
