from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from query_agent.domain.capability import Capability
from query_agent.domain.evidence import (
    Evidence,
    EvidenceLocator,
    EvidenceProvenance,
    EvidenceScope,
    EvidenceSourceKind,
    EvidenceStatus,
)
from query_agent.domain.query import (
    EvidenceRequirement,
    QueryContext,
    QueryIntent,
    QueryPlan,
    QueryRequest,
    QueryResponse,
    QueryStatus,
)


def context() -> QueryContext:
    return QueryContext(workspace=Path("/workspace"), run_id="run-1")


def evidence() -> Evidence:
    return Evidence(
        evidence_id="ev-1",
        source_kind=EvidenceSourceKind.WORKSPACE_ARTIFACT,
        content={"wns": -0.12},
        scope=EvidenceScope(run_id="run-1"),
        locator=EvidenceLocator(uri="reports/timing.rpt", line_start=1),
        provenance=EvidenceProvenance(
            provider="fixture",
            retrieved_at=datetime(2026, 9, 21, tzinfo=UTC),
        ),
    )


def test_query_request_rejects_blank_query() -> None:
    with pytest.raises(ValidationError):
        QueryRequest(query="  ", context=context())


def test_intent_is_not_answerability() -> None:
    plan = QueryPlan(
        intent=QueryIntent.ROOT_CAUSE,
        evidence_requirements=(
            EvidenceRequirement(
                description="structured relationships",
                required_capabilities=(Capability.DESIGN_RELATION_QUERY,),
            ),
        ),
        required_capabilities=(Capability.DESIGN_RELATION_QUERY,),
    )
    assert plan.intent is QueryIntent.ROOT_CAUSE
    response = QueryResponse(
        status=QueryStatus.NEEDS_MORE_DATA,
        missing_evidence=plan.evidence_requirements,
        missing_capabilities=(Capability.DESIGN_RELATION_QUERY,),
    )
    assert response.status is QueryStatus.NEEDS_MORE_DATA


def test_evidence_requires_traceability_and_scope() -> None:
    item = evidence()
    assert item.status is EvidenceStatus.SUFFICIENT
    assert item.scope.run_id == "run-1"
    assert item.locator.uri == "reports/timing.rpt"


def test_invalid_evidence_line_range_is_rejected() -> None:
    with pytest.raises(ValidationError):
        EvidenceLocator(uri="x", line_start=4, line_end=2)


def test_capability_phase_semantics_are_explicit() -> None:
    assert Capability.TEXT_SEARCH.available_in_phase_i
    assert Capability.RUN_EVIDENCE.available_in_phase_i
    assert not Capability.DESIGN_RELATION_QUERY.available_in_phase_i


@pytest.mark.parametrize(
    "status",
    list(QueryStatus),
)
def test_query_response_supports_all_business_states(status: QueryStatus) -> None:
    response = QueryResponse(status=status, evidence=(evidence(),))
    assert response.status is status
