from tests.fixtures.fake_experiment import FakeExperimentContextProvider

from query_agent.application.context.comparison import ComparisonPolicy
from query_agent.application.context.conflicts import ConflictDetector
from query_agent.application.context.resolver import ExperimentContextResolver
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
