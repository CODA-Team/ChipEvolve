from pathlib import Path

import pytest

from query_agent.adapters.llm import FakeLanguageModel
from query_agent.application.llm_pipeline import (
    GroundedAnswerSynthesizer,
    LLMIntentParser,
)
from query_agent.domain.errors import LLMContractError
from query_agent.domain.evidence import EvidenceStatus
from query_agent.domain.query import QueryContext, QueryRequest, QueryStatus


def request() -> QueryRequest:
    return QueryRequest(
        query="What is CTS?", context=QueryContext(workspace=Path("/w"))
    )


def test_fake_model_returns_schema_validated_structured_output() -> None:
    model = FakeLanguageModel({"What is CTS?": {"intent": "DOMAIN_KNOWLEDGE"}})
    assert LLMIntentParser(model).parse(request()).value == "DOMAIN_KNOWLEDGE"


def test_fake_model_rejects_invalid_structured_output() -> None:
    model = FakeLanguageModel({"What is CTS?": {"intent": "not-an-intent"}})
    with pytest.raises(LLMContractError):
        LLMIntentParser(model).parse(request())


def test_synthesizer_does_not_ask_model_to_resolve_conflict() -> None:
    model = FakeLanguageModel({})
    result = GroundedAnswerSynthesizer(model).synthesize(
        request(), (), evidence_status=EvidenceStatus.CONFLICTING
    )
    assert result.status is QueryStatus.NEEDS_MORE_DATA
