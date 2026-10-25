"""Comparisons infer one actual stage and preserve complete semantic anchors."""

import pytest
from tests.fixtures.fake_experiment import FakeExperimentContextProvider

from query_agent.application.collection import EvidenceCollector
from query_agent.application.context.comparison import ComparisonPolicy
from query_agent.application.planning import KeywordIntentParser, QueryPlanner
from query_agent.application.service import QueryService
from query_agent.domain.errors import MissingDataError
from query_agent.domain.experiment import ExperimentStatus, MetricObservation
from query_agent.domain.query import (
    QueryContext,
    QueryRequest,
    QuerySource,
    QueryStatus,
)


def metric(run: str, stage: str = "routing") -> MetricObservation:
    return MetricObservation(
        metric_name="WNS",
        value=-0.1,
        unit="ns",
        corner="typical",
        run_id=run,
        stage_key=stage,
        design_id="gcd",
        artifact_id=run + "-source",
        source_hash="a" * 64,
    )


def test_unstated_stage_uses_the_single_actual_comparison_stage() -> None:
    values = (metric("one"), metric("two", "route"))
    result = ComparisonPolicy().select(
        values, metric_name="WNS", stage_key=None, design_id="gcd"
    )
    assert result.scope.stage_key == "routing"
    assert result.observations == values


def test_multiple_complete_stages_require_an_explicit_stage() -> None:
    with pytest.raises(MissingDataError, match="multiple.*stages"):
        ComparisonPolicy().select(
            (metric("one"), metric("two", "placement")),
            metric_name="WNS",
            stage_key=None,
            design_id="gcd",
        )


@pytest.mark.parametrize("stage", [None, "routing"])
def test_partial_first_record_does_not_define_comparison_unit_or_corner(
    stage: str | None,
) -> None:
    incomplete = metric("partial").model_copy(
        update={
            "unit": None,
            "corner": None,
            "complete": False,
            "incomplete_reason": "unit and corner missing",
        }
    )
    complete = (metric("one"), metric("two"))
    result = ComparisonPolicy().select(
        (incomplete, *complete), metric_name="WNS", stage_key=stage, design_id="gcd"
    )
    assert result.observations == complete
    assert result.rejected[0].reason_code == "PARTIAL_METRIC"
    assert result.rejected[0].detail == incomplete.incomplete_reason


def test_unrelated_design_does_not_make_the_stage_ambiguous() -> None:
    original = metric("one")
    other = metric("different", "placement").model_copy(update={"design_id": "other"})
    result = ComparisonPolicy().select(
        (original, other), metric_name="WNS", stage_key=None, design_id="gcd"
    )
    assert result.observations == (original,)


def test_ordinary_two_run_query_without_stage_returns_both_metrics() -> None:
    provider = FakeExperimentContextProvider()
    provider.runs = (
        provider.runs[0],
        provider.runs[1].model_copy(update={"status": ExperimentStatus.SUCCEEDED}),
        provider.runs[2],
    )
    provider.metrics = (metric("run_001"), metric("run_002"))
    app = QueryService(
        intent_parser=KeywordIntentParser(),
        planner=QueryPlanner(),
        collector=EvidenceCollector(experiment_context_provider=provider),
    )
    answer = app.query(
        QueryRequest(
            query="Compare WNS",
            context=QueryContext(
                design_id="gcd",
                run_ids=("run_001", "run_002"),
                source=QuerySource.MANAGED_RUN,
            ),
        )
    )
    assert answer.status is QueryStatus.ANSWERED
    assert {e.scope.run_id for e in answer.evidence} == {"run_001", "run_002"}
