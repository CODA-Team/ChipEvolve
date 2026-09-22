from pathlib import Path

from query_agent.adapters.analysis import FixtureAnalysisProvider
from query_agent.application.collection import EvidenceCollector
from query_agent.application.planning import KeywordIntentParser, QueryPlanner
from query_agent.application.service import QueryService
from query_agent.domain.capability import Capability
from query_agent.domain.query import QueryContext, QueryRequest, QueryStatus


def test_analysis_query_uses_only_typed_analysis_provider() -> None:
    service = QueryService(
        intent_parser=KeywordIntentParser(),
        planner=QueryPlanner(),
        collector=EvidenceCollector(analysis_provider=FixtureAnalysisProvider()),
    )
    response = service.query(
        QueryRequest(
            query="What is timing WNS?",
            context=QueryContext(workspace=Path("/workspace"), design_id="gcd"),
        )
    )
    assert response.status is QueryStatus.ANSWERED
    assert response.evidence[0].fact_key == "analysis:metric:WNS"
    assert response.evidence[0].provenance.provider == "fixture-analysis-provider"
    assert Capability.SPECIALIZED_ANALYSIS not in response.missing_capabilities
