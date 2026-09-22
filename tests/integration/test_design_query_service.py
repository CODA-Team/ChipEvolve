from pathlib import Path

from query_agent.adapters.design_data import FixtureDesignDataProvider
from query_agent.application.collection import EvidenceCollector
from query_agent.application.planning import KeywordIntentParser, QueryPlanner
from query_agent.application.service import QueryService
from query_agent.domain.query import QueryContext, QueryRequest, QueryStatus


def service() -> QueryService:
    provider = FixtureDesignDataProvider()
    return QueryService(
        intent_parser=KeywordIntentParser(),
        planner=QueryPlanner(),
        collector=EvidenceCollector(design_data_provider=provider),
    )


def test_location_query_uses_typed_design_data() -> None:
    response = service().query(
        QueryRequest(
            query="Where is instance u1?",
            context=QueryContext(workspace=Path("/workspace"), design_id="gcd"),
        )
    )
    assert response.status is QueryStatus.ANSWERED
    assert "10.0" in (response.answer or "")
    assert response.evidence[0].source_kind.value == "design_data"


def test_fanout_query_is_relationship_evidence() -> None:
    query_service = service()
    response = query_service.query(
        QueryRequest(
            query="What is the fanout of net n1?",
            context=QueryContext(workspace=Path("/workspace"), design_id="gcd"),
        )
    )
    assert response.status is QueryStatus.ANSWERED
    assert "u2/A" in (response.answer or "")
    assert query_service.last_trace is not None
    assert query_service.last_trace.provider_calls[0].provider == "design-data-provider"


def test_region_query_returns_only_scoped_instances() -> None:
    response = service().query(
        QueryRequest(
            query="Which instances are in region 0,0,20,30?",
            context=QueryContext(workspace=Path("/workspace"), design_id="gcd"),
        )
    )
    assert response.status is QueryStatus.ANSWERED
    assert "u1" in (response.answer or "")
    assert "u2" not in (response.answer or "")
