from pathlib import Path

from tests.fixtures.fake_execution import FakeExecutionClient

from query_agent.adapters.artifacts import LocalArtifactProvider
from query_agent.adapters.run_evidence import (
    ExecutionFoundationExperimentContextProvider,
    ExecutionFoundationRunEvidenceAdapter,
)
from query_agent.application.collection import EvidenceCollector
from query_agent.application.planning import KeywordIntentParser, QueryPlanner
from query_agent.application.service import QueryService
from query_agent.domain.errors import ArtifactPathError
from query_agent.domain.query import (
    QueryContext,
    QueryRequest,
    QuerySource,
    QueryStatus,
)


def managed_context() -> QueryContext:
    return QueryContext(
        design_id="gcd",
        run_id="run_02",
        stage="routing",
        source=QuerySource.MANAGED_RUN,
    )


def test_adapter_maps_metric_scope_and_lineage() -> None:
    adapter = ExecutionFoundationRunEvidenceAdapter(FakeExecutionClient())
    evidence = adapter.get_metrics(managed_context(), metric_name="WNS")
    assert len(evidence) == 1
    item = evidence[0]
    assert item.scope.run_id == "run_02"
    assert item.scope.stage == "routing"
    assert item.fact_key == "metric:WNS"
    assert item.provenance.source_hash == "a" * 64
    assert "art-route-timing" in item.locator.uri
    assert item.provenance.provider == "execution-foundation-public-api"


def test_managed_metric_query_uses_registered_run_evidence() -> None:
    adapter = ExecutionFoundationRunEvidenceAdapter(FakeExecutionClient())
    collector = EvidenceCollector(run_evidence_provider=adapter)
    service = QueryService(
        intent_parser=KeywordIntentParser(),
        planner=QueryPlanner(),
        collector=collector,
    )
    response = service.query(
        QueryRequest(
            query="What is the routing WNS for run_02?",
            context=managed_context(),
        )
    )
    assert response.status is QueryStatus.ANSWERED
    assert response.evidence[0].scope.run_id == "run_02"
    assert response.evidence[0].scope.stage == "routing"
    assert "-0.2" in (response.answer or "")
    trace = service.last_trace
    assert trace is not None
    assert trace.evidence_ids
    assert trace.provider_calls[0].provider == "execution-foundation-public-api"


def test_local_provider_cannot_read_managed_run(tmp_path: Path) -> None:
    provider = LocalArtifactProvider(tmp_path)
    context = QueryContext(run_id="run_02", source=QuerySource.MANAGED_RUN)
    try:
        provider.list_artifacts(context)
    except ArtifactPathError:
        pass
    else:
        raise AssertionError("managed runs must not use LocalArtifactProvider")


def test_context_adapter_maps_run_stage_artifact_and_metric_lineage() -> None:
    provider = ExecutionFoundationExperimentContextProvider(FakeExecutionClient())
    run = provider.get_run("run_02")
    assert run.status.value == "succeeded"
    assert run.stage("routing") is not None
    artifacts = provider.list_artifacts("run_02", stage_key="routing")
    assert artifacts[0].artifact_id == "art-route-timing"
    metric = provider.list_metrics("run_02", metric_name="WNS")[0]
    assert metric.stage_key == "routing"
    assert metric.artifact_id == "art-route-timing"
