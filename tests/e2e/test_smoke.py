from pathlib import Path

from query_agent.adapters.artifacts import LocalArtifactProvider
from query_agent.application.collection import EvidenceCollector
from query_agent.application.planning import KeywordIntentParser, QueryPlanner
from query_agent.application.service import QueryService
from query_agent.domain.query import QueryContext, QueryRequest, QueryStatus


def test_phase_i_smoke() -> None:
    workspace = Path(__file__).parents[1] / "fixtures" / "sample_workspace"
    service = QueryService(
        intent_parser=KeywordIntentParser(),
        planner=QueryPlanner(),
        collector=EvidenceCollector(
            artifact_provider=LocalArtifactProvider(workspace),
        ),
    )
    response = service.query(
        QueryRequest(
            query="where is the placement log?",
            context=QueryContext(workspace=workspace),
        )
    )
    assert response.status is QueryStatus.ANSWERED
    assert response.evidence_citations
