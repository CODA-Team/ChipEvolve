"""Two source references are not two independent experiments."""

from tests.fixtures.fake_execution import FakeExecutionClient
from tests.fixtures.fake_experiment import FakeExperimentContextProvider

from query_agent.adapters.run_evidence import (
    ExecutionFoundationExperimentContextProvider,
)
from query_agent.application.collection import EvidenceCollector
from query_agent.application.planning import KeywordIntentParser, QueryPlanner
from query_agent.application.service import QueryService
from query_agent.domain.experiment import ExperimentStatus
from query_agent.domain.query import (
    QueryContext,
    QueryRequest,
    QuerySource,
    QueryStatus,
)
from query_agent.ports.experiment_context import ExperimentContextProvider


def compare(provider: ExperimentContextProvider, runs: tuple[str, ...]):
    app = QueryService(
        intent_parser=KeywordIntentParser(),
        planner=QueryPlanner(),
        collector=EvidenceCollector(experiment_context_provider=provider),
    )
    return app.query(
        QueryRequest(
            query="Compare WNS",
            context=QueryContext(
                design_id="gcd", run_ids=runs, source=QuerySource.MANAGED_RUN
            ),
        )
    )


def test_public_adapter_reads_each_explicit_run_only_once() -> None:
    provider = ExecutionFoundationExperimentContextProvider(FakeExecutionClient())
    runs = provider.list_runs(run_ids=("run_02", "run_02"))
    assert len(runs) == 1


def test_repeated_cli_run_cannot_satisfy_two_run_comparison() -> None:
    answer = compare(
        ExecutionFoundationExperimentContextProvider(FakeExecutionClient()),
        ("run_02", "run_02"),
    )
    assert answer.status is QueryStatus.NEEDS_MORE_DATA
    assert answer.missing_evidence


def repeated_source_provider(include_other: bool) -> FakeExperimentContextProvider:
    provider = FakeExperimentContextProvider()
    provider.runs = (
        provider.runs[0],
        provider.runs[1].model_copy(
            update={
                "status": ExperimentStatus.SUCCEEDED,
                "created_at": provider.runs[0].created_at,
            }
        ),
        provider.runs[2],
    )
    first = provider.metrics[0]
    repeated = first.model_copy(
        update={"snapshot_id": "another-view", "revision_id": "r2"}
    )
    provider.metrics = (first, repeated)
    if include_other:
        provider.metrics = (
            *provider.metrics,
            first.model_copy(update={"run_id": "run_002", "value": -0.1}),
        )
    return provider


def test_two_snapshots_of_one_run_do_not_replace_the_missing_second_run() -> None:
    answer = compare(repeated_source_provider(False), ("run_001", "run_002"))
    assert answer.status is QueryStatus.NEEDS_MORE_DATA


def test_numeric_difference_uses_distinct_runs_and_retains_all_sources() -> None:
    answer = compare(repeated_source_provider(True), ("run_001", "run_002"))
    assert answer.status is QueryStatus.ANSWERED
    assert "run_002=-0.1" in (answer.answer or "")
    assert "difference=-0.1" in (answer.answer or "")
    assert len(answer.evidence) == 3
