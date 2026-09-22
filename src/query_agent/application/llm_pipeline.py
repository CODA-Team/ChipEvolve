"""Optional typed LLM edges; deterministic retrieval remains authoritative."""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from query_agent.domain.capability import Capability
from query_agent.domain.evidence import Evidence, EvidenceStatus
from query_agent.domain.query import (
    EvidenceRequirement,
    QueryIntent,
    QueryPlan,
    QueryRequest,
    QueryStatus,
)
from query_agent.ports.llm import LanguageModel


class IntentOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    intent: QueryIntent


class PlanOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    evidence_requirements: tuple[EvidenceRequirement, ...] = ()
    required_capabilities: tuple[Capability, ...] = ()


class SynthesisOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: QueryStatus
    answer: str | None = None
    citations: tuple[str, ...] = ()


class LLMIntentParser:
    """Use a LanguageModel only for semantic intent classification."""

    def __init__(self, model: LanguageModel, *, prompt_version: str = "intent_v1"):
        self._model = model
        self.prompt_version = prompt_version

    def parse(self, request: QueryRequest) -> QueryIntent:
        output = self._model.complete(request.query, IntentOutput)
        return output.intent


class LLMQueryPlanner:
    """Use a LanguageModel for plan proposals, still schema validated."""

    def __init__(self, model: LanguageModel, *, prompt_version: str = "planner_v1"):
        self._model = model
        self.prompt_version = prompt_version

    def plan(self, request: QueryRequest, intent: QueryIntent) -> QueryPlan:
        del request
        output = self._model.complete(intent.value, PlanOutput)
        return QueryPlan(
            intent=intent,
            evidence_requirements=output.evidence_requirements,
            required_capabilities=output.required_capabilities,
        )


class GroundedAnswerSynthesizer:
    """Optional synthesis that refuses conflict/insufficiency before the model."""

    def __init__(self, model: LanguageModel, *, prompt_version: str = "synthesis_v1"):
        self._model = model
        self.prompt_version = prompt_version

    def synthesize(
        self,
        request: QueryRequest,
        evidence: Sequence[Evidence],
        *,
        evidence_status: EvidenceStatus,
    ) -> SynthesisOutput:
        if evidence_status is not EvidenceStatus.SUFFICIENT:
            return SynthesisOutput(
                status=QueryStatus.NEEDS_MORE_DATA,
                answer="evidence is insufficient or conflicting",
                citations=tuple(item.locator.uri for item in evidence),
            )
        prompt = f"{request.query}\n" + "\n".join(
            f"{item.evidence_id}: {item.content}" for item in evidence
        )
        return self._model.complete(prompt, SynthesisOutput)
