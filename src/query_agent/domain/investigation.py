"""Durable investigation vocabulary, independent of tools and model vendors."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .evidence import Evidence, JsonValue
from .judgment import JudgmentAdvice


class InvestigationStatus(StrEnum):
    ACTIVE = "active"
    WAITING = "waiting"
    PAUSED = "paused"
    ANSWERED = "answered"
    STOPPED = "stopped"
    FAILED = "failed"


class FixedScope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    snapshot_id: str = Field(min_length=1)
    design_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    revision_id: str = Field(min_length=1)
    stage: str = Field(min_length=1)
    role: Literal["baseline", "candidate", "supplement", "subject"] = "subject"
    parent_snapshot_id: str | None = None


class InvestigationBudget(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    max_steps: int = Field(default=12, ge=1, le=100)
    max_tool_calls: int = Field(default=32, ge=1, le=1000)
    max_analyses: int = Field(default=2, ge=0, le=10)
    max_read_bytes: int = Field(default=262144, ge=1024, le=16777216)
    max_seconds: float = Field(default=180, gt=0, le=3600)


class OperationArgument(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    name: str = Field(min_length=1)
    value: str


class ReadOperation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    path: str = Field(min_length=1)
    arguments: list[OperationArgument] = Field(default_factory=list[OperationArgument])
    purpose: str = Field(min_length=1)


class AnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    snapshot_id: str = Field(min_length=1)
    request_id: str | None = None
    created_at: datetime | None = None
    question_to_verify: str = Field(min_length=1)
    hypothesis_id: str | None = None
    from_pin: str | None = None
    to_pin: str | None = None
    path_group: str | None = None
    check: Literal["setup", "hold", "both"] = "both"
    path_count: int = Field(default=5, ge=1, le=200)
    endpoint_path_count: int = Field(default=1, ge=1, le=200)
    timeout_seconds: int = Field(default=120, ge=1, le=180)
    expected_artifacts: list[str] = Field(default_factory=lambda: ["data_snapshot"])


class AnalysisTicket(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    run_id: str
    snapshot_id: str
    parent_snapshot_id: str
    request: AnalysisRequest
    status: str
    failure_evidence: Evidence | None = None


class Hypothesis(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    hypothesis_id: str = Field(min_length=1)
    explanation: str = Field(min_length=1)
    supports: list[str] = Field(default_factory=list[str])
    counterevidence: list[str] = Field(default_factory=list[str])
    status: Literal["unverified", "supported", "rejected", "not_distinguishable"] = (
        "unverified"
    )
    next_discriminating_observation: str | None = None


class AnswerClaim(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    text: str = Field(min_length=1, max_length=1400)
    evidence_ids: list[str] = Field(default_factory=list[str])
    kind: Literal["fact", "comparison", "hypothesis", "causal", "limitation"]
    certainty: Literal["observed", "supported", "possible", "unknown"]


class InvestigationAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    summary: str = Field(min_length=1, max_length=2400)
    claims: list[AnswerClaim] = Field(default_factory=list[AnswerClaim], max_length=8)
    missing_evidence: list[str] = Field(default_factory=list[str])
    next_steps: list[str] = Field(default_factory=list[str])
    outcome: Literal["answered", "partial", "insufficient", "ambiguous"]
    structured_answer_json: str | None = None


class HandoffRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    snapshot_id: str = Field(min_length=1)
    role: Literal["eco", "flow", "code"]
    objective: str = Field(min_length=1, max_length=1400)


class InvestigationDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    reasoning_summary: str = Field(min_length=1, max_length=1000)
    action: Literal[
        "read", "compare", "analyze", "wait", "answer", "pause", "stop", "handoff"
    ]
    reads: list[ReadOperation] = Field(
        default_factory=list[ReadOperation], max_length=8
    )
    analysis: AnalysisRequest | None = None
    handoff: HandoffRequest | None = None
    answer: InvestigationAnswer | None = None
    hypotheses: list[Hypothesis] = Field(
        default_factory=list[Hypothesis], max_length=12
    )
    confirmed_facts: list[AnswerClaim] = Field(default_factory=list[AnswerClaim])
    missing_evidence: list[str] = Field(default_factory=list[str])
    stop_reason: str | None = None

    @model_validator(mode="after")
    def action_has_its_payload(self) -> InvestigationDecision:
        if self.action in ("read", "compare") and not self.reads:
            raise ValueError("read/compare needs explicit operations")
        if self.action == "analyze" and self.analysis is None:
            raise ValueError(
                "analysis needs an explicit verification question and fixed inputs"
            )
        if self.action == "answer" and self.answer is None:
            raise ValueError("answer action needs claims and coverage outcome")
        if self.action == "handoff" and (self.handoff is None or self.answer is None):
            raise ValueError(
                "handoff needs a scoped request and evidence-backed answer"
            )
        if self.handoff is not None and self.action != "handoff":
            raise ValueError("handoff payload is only valid for a handoff action")
        if self.action in ("pause", "stop") and not self.stop_reason:
            raise ValueError("pause/stop needs a reason")
        if self.analysis is not None and self.action != "analyze":
            raise ValueError("analysis payload is only valid for an analyze action")
        return self


class OperationReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    operation_id: str
    kind: str
    request: dict[str, JsonValue]
    status: str
    seconds: float = Field(ge=0)
    evidence_id: str | None = None
    run_id: str | None = None
    error: str | None = None


class SkillRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    name: str
    version: str
    sha256: str = Field(min_length=64, max_length=64)
    content: str


class InvestigationState(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["1"] = "1"
    investigation_id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    scopes: list[FixedScope] = Field(min_length=1)
    status: InvestigationStatus = InvestigationStatus.ACTIVE
    budget: InvestigationBudget = Field(default_factory=InvestigationBudget)
    evidence: list[Evidence] = Field(default_factory=list[Evidence])
    confirmed_facts: list[AnswerClaim] = Field(default_factory=list[AnswerClaim])
    hypotheses: list[Hypothesis] = Field(default_factory=list[Hypothesis])
    missing_evidence: list[str] = Field(default_factory=list[str])
    operations: list[OperationReceipt] = Field(default_factory=list[OperationReceipt])
    pending_analyses: list[AnalysisTicket] = Field(default_factory=list[AnalysisTicket])
    skills: list[SkillRecord] = Field(default_factory=list[SkillRecord])
    judgments: list[JudgmentAdvice] = Field(default_factory=list[JudgmentAdvice])
    decisions: list[InvestigationDecision] = Field(
        default_factory=list[InvestigationDecision]
    )
    answer: InvestigationAnswer | None = None
    handoff_packages: list[dict[str, JsonValue]] = Field(
        default_factory=list[dict[str, JsonValue]]
    )
    draft_answer: InvestigationAnswer | None = None
    completion_review_done: bool = False
    steps_used: int = Field(default=0, ge=0)
    tool_calls_used: int = Field(default=0, ge=0)
    analyses_used: int = Field(default=0, ge=0)
    read_bytes_used: int = Field(default=0, ge=0)
    active_seconds: float = Field(default=0, ge=0)
    external_deadline: datetime | None = None
    stop_reason: str | None = None
    revision: int = Field(default=0, ge=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
