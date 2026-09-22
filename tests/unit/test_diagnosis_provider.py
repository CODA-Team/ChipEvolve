from datetime import UTC, datetime
from pathlib import Path

import pytest

from query_agent.adapters.diagnosis import (
    FixtureDiagnosisProvider,
    UnavailableDiagnosisProvider,
)
from query_agent.application.collection import EvidenceCollector
from query_agent.application.planning import KeywordIntentParser, QueryPlanner
from query_agent.application.service import QueryService
from query_agent.domain.diagnosis import (
    DiagnosisFinding,
    DiagnosisProvenance,
    DiagnosisScope,
)
from query_agent.domain.evidence import EvidenceSourceKind, EvidenceStatus
from query_agent.domain.query import QueryContext, QueryRequest, QueryStatus
from query_agent.ports.diagnosis import DiagnosisProvider


def service(provider: DiagnosisProvider) -> QueryService:
    return QueryService(
        intent_parser=KeywordIntentParser(),
        planner=QueryPlanner(),
        collector=EvidenceCollector(diagnosis_provider=provider),
    )


def test_diagnosis_contract_requires_scope_and_support() -> None:
    with pytest.raises(ValueError):
        DiagnosisScope()
    with pytest.raises(ValueError):
        DiagnosisFinding(
            finding_id="missing-support",
            claim="unsupported claim",
            scope=DiagnosisScope(design_id="gcd"),
            provenance=DiagnosisProvenance(
                provider="fixture",
                locator="diagnosis://finding",
                observed_at=datetime(2026, 9, 22, tzinfo=UTC),
            ),
            support=(),
        )


def test_fixture_diagnosis_returns_cited_supported_finding() -> None:
    response = service(FixtureDiagnosisProvider()).query(
        QueryRequest(
            query="Why did timing become worse?",
            context=QueryContext(workspace=Path("/workspace"), design_id="gcd"),
        )
    )
    assert response.status is QueryStatus.ANSWERED
    assert response.evidence[0].source_kind is EvidenceSourceKind.DIAGNOSIS
    assert response.evidence[0].fact_key == "diagnosis:finding"
    assert len(response.evidence[0].content["support"]) == 2  # type: ignore[index]
    assert "net n1" in (response.answer or "")


def test_incomplete_finding_is_not_answerable() -> None:
    class IncompleteProvider(FixtureDiagnosisProvider):
        def get_findings(
            self, context: QueryContext, *, symptom: str, limit: int = 10
        ) -> tuple[DiagnosisFinding, ...]:
            finding = super().get_findings(context, symptom=symptom, limit=limit)[0]
            return (finding.model_copy(update={"complete": False}),)

    response = service(IncompleteProvider()).query(
        QueryRequest(
            query="Why did timing become worse?",
            context=QueryContext(workspace=Path("/workspace"), design_id="gcd"),
        )
    )
    assert response.status is QueryStatus.NEEDS_MORE_DATA
    assert response.evidence_status is EvidenceStatus.PARTIAL


def test_unavailable_diagnosis_provider_is_truthful() -> None:
    response = service(UnavailableDiagnosisProvider()).query(
        QueryRequest(
            query="Why did timing become worse?",
            context=QueryContext(workspace=Path("/workspace"), design_id="gcd"),
        )
    )
    assert response.status is QueryStatus.NEEDS_MORE_DATA
    assert response.missing_capabilities
