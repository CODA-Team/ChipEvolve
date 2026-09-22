from pathlib import Path

from query_agent.adapters.diagnosis import FixtureDiagnosisProvider
from query_agent.application.collection import EvidenceCollector
from query_agent.application.planning import KeywordIntentParser, QueryPlanner
from query_agent.application.service import QueryService
from query_agent.domain.query import QueryContext, QueryRequest, QueryStatus


def test_root_cause_query_requires_and_cites_diagnosis_provider() -> None:
    query_service = QueryService(
        intent_parser=KeywordIntentParser(),
        planner=QueryPlanner(),
        collector=EvidenceCollector(diagnosis_provider=FixtureDiagnosisProvider()),
    )
    response = query_service.query(
        QueryRequest(
            query="Why did timing become worse?",
            context=QueryContext(workspace=Path("/workspace"), design_id="gcd"),
        )
    )
    assert response.status is QueryStatus.ANSWERED
    assert response.evidence_citations == ("diagnosis://timing/finding-001",)
    assert response.evidence[0].provenance.provider == "fixture-diagnosis-provider"
