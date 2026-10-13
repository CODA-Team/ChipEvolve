from unittest.mock import MagicMock

from query_agent.adapters.analysis import FixtureAnalysisProvider
from query_agent.application.collection import EvidenceCollector
from query_agent.application.planning import KeywordIntentParser, QueryPlanner
from query_agent.application.service import QueryService
from query_agent.domain.errors import MissingDataError
from query_agent.domain.query import QueryContext, QueryRequest, QuerySource


def test_exact_fact_snapshot_does_not_reselect_ambiguous_run_stage() -> None:
    resolver = MagicMock()
    resolver.resolve.side_effect = MissingDataError("two snapshots at the same stage")
    provider = MagicMock(wraps=FixtureAnalysisProvider())
    provider.capabilities = FixtureAnalysisProvider().capabilities
    service = QueryService(
        intent_parser=KeywordIntentParser(),
        planner=QueryPlanner(),
        collector=EvidenceCollector(analysis_provider=provider),
        context_resolver=resolver,
    )
    context = QueryContext(
        source=QuerySource.MANAGED_RUN,
        design_id="gcd",
        run_id="run-one",
        snapshot_id="snapshot-exact",
        stage="timing",
    )
    service.query(QueryRequest(query="What is timing WNS?", context=context))
    resolver.resolve.assert_not_called()
    assert provider.get_timing_metrics.call_args.args[0].snapshot_id == "snapshot-exact"


def test_run_state_queries_still_use_experiment_resolver() -> None:
    resolver = MagicMock()
    resolver.resolve.side_effect = MissingDataError("missing execution status")
    service = QueryService(
        intent_parser=KeywordIntentParser(),
        planner=QueryPlanner(),
        collector=EvidenceCollector(),
        context_resolver=resolver,
    )
    context = QueryContext(
        source=QuerySource.MANAGED_RUN, run_id="run-one", snapshot_id="snapshot-exact"
    )
    response = service.query(QueryRequest(query="run status", context=context))
    resolver.resolve.assert_called_once()
    assert response.answer is not None
    assert "missing execution status" in response.answer
