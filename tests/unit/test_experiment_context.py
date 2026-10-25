import hashlib

from tests.fixtures.fake_experiment import FakeExperimentContextProvider

from query_agent.application.collection import EvidenceCollector
from query_agent.application.context.comparison import ComparisonPolicy
from query_agent.application.context.conflicts import ConflictDetector
from query_agent.application.context.resolver import ExperimentContextResolver
from query_agent.application.context.stage_selection import stage_satisfies
from query_agent.application.planning import KeywordIntentParser, QueryPlanner
from query_agent.application.service import QueryService
from query_agent.domain.experiment import (
    ExperimentRun,
    ExperimentStage,
    ExperimentStatus,
    MetricObservation,
    StageStatus,
)
from query_agent.domain.query import (
    QueryContext,
    QueryIntent,
    QueryPlan,
    QueryRequest,
    QuerySource,
    QueryStatus,
    RunSelectionMode,
)


def managed_request(question: str, *, stage: str = "routing") -> QueryRequest:
    return QueryRequest(
        query=question,
        context=QueryContext(
            design_id="gcd", stage=stage, source=QuerySource.MANAGED_RUN
        ),
    )


def metric_plan(mode: RunSelectionMode) -> QueryPlan:
    from query_agent.domain.capability import Capability
    from query_agent.domain.evidence import EvidenceScope
    from query_agent.domain.query import EvidenceRequirement

    return QueryPlan(
        intent=QueryIntent.METRIC_QUERY,
        run_selection=mode,
        required_capabilities=(Capability.EXPLICIT_METRIC,),
        evidence_requirements=(
            EvidenceRequirement(
                description="routing WNS",
                required_capabilities=(Capability.EXPLICIT_METRIC,),
                fact_key="metric:WNS",
                scope=EvidenceScope(design_id="gcd", stage="routing"),
                requires_current=True,
            ),
        ),
    )


def test_latest_valid_rejects_failed_and_running_runs() -> None:
    provider = FakeExperimentContextProvider()
    resolved = ExperimentContextResolver(provider).resolve(
        managed_request("latest completed routing WNS"),
        metric_plan(RunSelectionMode.LATEST_VALID),
    )
    assert resolved.selection.selected_run_id == "run_001"
    assert {item.candidate_id for item in resolved.selection.rejected} == {
        "run_003",
        "run_002",
    }
    assert resolved.context.metrics[0].stage_key == "routing"


def test_current_does_not_reuse_an_older_run_while_newest_is_running() -> None:
    provider = FakeExperimentContextProvider()
    resolved = ExperimentContextResolver(provider).resolve(
        managed_request("current routing WNS"),
        metric_plan(RunSelectionMode.CURRENT),
    )
    assert resolved.selection.selected_run_id is None
    assert not resolved.context.metrics
    assert "CURRENT_RUN_NOT_COMPLETE" in resolved.selection.reason_codes


def test_stage_selection_is_canonical_and_wrong_stage_is_not_comparable() -> None:
    run = ExperimentRun(
        run_id="r",
        status=ExperimentStatus.SUCCEEDED,
        stages=(ExperimentStage(stage_key="place", status=StageStatus.SUCCEEDED),),
    )
    assert run.stage("placement") is not None
    metrics = (
        MetricObservation(
            metric_name="WNS",
            value=-0.1,
            run_id="r",
            stage_key="placement",
        ),
    )
    comparison = ComparisonPolicy().select(
        metrics, metric_name="WNS", stage_key="routing", design_id=None
    )
    assert not comparison.observations


def test_conflict_detector_retains_incompatible_authoritative_values() -> None:
    metrics = (
        MetricObservation(
            metric_name="WNS", value=-0.2, run_id="r", stage_key="routing"
        ),
        MetricObservation(
            metric_name="WNS", value=-0.3, run_id="r", stage_key="routing"
        ),
    )
    conflicts = ConflictDetector().detect(metrics)
    assert len(conflicts) == 1
    assert conflicts[0].kind.value == "value_mismatch"


def test_indexed_data_stage_is_distinct_from_execution_control_stage() -> None:
    run = ExperimentRun(
        run_id="extract-run",
        status=ExperimentStatus.SUCCEEDED,
        stages=(ExperimentStage(stage_key="package", status=StageStatus.SUCCEEDED),),
        indexed_data_stages=("route",),
    )
    assert stage_satisfies(run, "routing")
    assert not stage_satisfies(run, "placement")
    assert not stage_satisfies(
        run.model_copy(update={"status": ExperimentStatus.FAILED}), "routing"
    )
    failed = run.model_copy(
        update={
            "stages": (ExperimentStage(stage_key="route", status=StageStatus.FAILED),)
        }
    )
    assert not stage_satisfies(failed, "routing")


def test_explicit_snapshot_excludes_other_revision_before_conflict_checks() -> None:
    provider = FakeExperimentContextProvider()
    metric = provider.metrics[0]
    provider.metrics = (
        metric.model_copy(update={"snapshot_id": "selected", "revision_id": "r1"}),
        metric.model_copy(
            update={"snapshot_id": "other", "revision_id": "r2", "value": -0.8}
        ),
    )
    request = QueryRequest(
        query="WNS?",
        context=QueryContext(
            run_id="run_001",
            snapshot_id="selected",
            revision_id="r1",
            source=QuerySource.MANAGED_RUN,
        ),
    )
    resolved = ExperimentContextResolver(provider).resolve(
        request, metric_plan(RunSelectionMode.EXPLICIT)
    )
    assert resolved.context.metrics == (provider.metrics[0],)
    assert not resolved.conflicts


def test_same_artifact_in_two_snapshots_keeps_distinct_evidence_identity() -> None:
    provider = FakeExperimentContextProvider()
    metric = provider.metrics[0]
    provider.metrics = (
        metric.model_copy(update={"snapshot_id": "s1", "revision_id": "r1"}),
        metric.model_copy(update={"snapshot_id": "s2", "revision_id": "r1"}),
    )
    app = QueryService(
        intent_parser=KeywordIntentParser(),
        planner=QueryPlanner(),
        collector=EvidenceCollector(experiment_context_provider=provider),
    )
    response = app.query(
        QueryRequest(
            query="WNS?",
            context=QueryContext(run_id="run_001", source=QuerySource.MANAGED_RUN),
        )
    )
    assert response.status is QueryStatus.ANSWERED
    assert len({item.evidence_id for item in response.evidence}) == 2
    assert {item.scope.snapshot_id for item in response.evidence} == {"s1", "s2"}


def test_unscoped_legacy_metric_keeps_its_evidence_id() -> None:
    app = QueryService(
        intent_parser=KeywordIntentParser(),
        planner=QueryPlanner(),
        collector=EvidenceCollector(
            experiment_context_provider=FakeExperimentContextProvider()
        ),
    )
    response = app.query(
        QueryRequest(
            query="WNS?",
            context=QueryContext(run_id="run_001", source=QuerySource.MANAGED_RUN),
        )
    )
    assert response.status is QueryStatus.ANSWERED
    item = response.evidence[0]
    original_digest = hashlib.sha256(
        f"{item.locator.uri}:{item.content}".encode()
    ).hexdigest()
    assert item.evidence_id == "ev-" + original_digest[:24]
