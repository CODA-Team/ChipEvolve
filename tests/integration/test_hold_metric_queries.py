"""Hold questions must never consume an available setup scalar as their answer."""

import pytest
from tests.fixtures.fake_experiment import FakeExperimentContextProvider

from query_agent.adapters.analysis import FixtureAnalysisProvider
from query_agent.application.collection import EvidenceCollector
from query_agent.application.planning import KeywordIntentParser, QueryPlanner
from query_agent.application.service import QueryService
from query_agent.domain.experiment import (
    ExperimentStatus,
    MetricObservation,
    StageStatus,
)
from query_agent.domain.query import (
    QueryContext,
    QueryRequest,
    QueryResponse,
    QuerySource,
    QueryStatus,
)


def provider(*, include_hold: bool = True) -> FakeExperimentContextProvider:
    result = FakeExperimentContextProvider()
    result.runs = (
        result.runs[0],
        result.runs[1].model_copy(
            update={
                "status": ExperimentStatus.SUCCEEDED,
                "stages": tuple(
                    stage.model_copy(update={"status": StageStatus.SUCCEEDED})
                    for stage in result.runs[1].stages
                ),
            }
        ),
        result.runs[2],
    )
    values = (("TNS", -509.0), ("WNS", -0.44), ("WS", -0.44))
    if include_hold:
        values += (("HOLD_TNS", -98.0), ("HOLD_WNS", -0.12), ("HOLD_WS", 0.02))
    result.metrics = tuple(
        MetricObservation(
            metric_name=name,
            value=value + index,
            unit="ns",
            corner="FF",
            run_id=run,
            design_id="gcd",
            stage_key="routing",
            artifact_id=run + "-source",
            source_hash="a" * 64,
        )
        for index, run in enumerate(("run_001", "run_002"))
        for name, value in values
    )
    return result


def ask(
    query: str, *, include_hold: bool = True, compare: bool = False
) -> QueryResponse:
    service = QueryService(
        intent_parser=KeywordIntentParser(),
        planner=QueryPlanner(),
        collector=EvidenceCollector(
            experiment_context_provider=provider(include_hold=include_hold),
            analysis_provider=FixtureAnalysisProvider(),
        ),
    )
    return service.query(
        QueryRequest(
            query=query,
            context=QueryContext(
                design_id="gcd",
                run_id=None if compare else "run_001",
                run_ids=("run_001", "run_002") if compare else (),
                stage="routing",
                source=QuerySource.MANAGED_RUN,
            ),
        )
    )


@pytest.mark.parametrize(
    ("query", "name", "value"),
    [
        ("HOLD_TNS?", "HOLD_TNS", -98.0),
        ("globalroute__timing__hold__tns?", "HOLD_TNS", -98.0),
        ("Hold TNS?", "HOLD_TNS", -98.0),
        ("Hold timing TNS?", "HOLD_TNS", -98.0),
        ("timing HOLD_TNS?", "HOLD_TNS", -98.0),
        ("TNS (hold)?", "HOLD_TNS", -98.0),
        ("HOLD_WNS?", "HOLD_WNS", -0.12),
        ("hold WNS?", "HOLD_WNS", -0.12),
        ("hold timing WNS?", "HOLD_WNS", -0.12),
        ("hold WS?", "HOLD_WS", 0.02),
        ("HOLD_WS?", "HOLD_WS", 0.02),
    ],
)
def test_hold_metric_is_distinct_from_available_setup_and_analysis_metrics(
    query: str, name: str, value: float
) -> None:
    answer = ask(query)
    assert answer.status is QueryStatus.ANSWERED
    assert answer.evidence
    assert all(ev.fact_key == "metric:" + name for ev in answer.evidence)
    for ev in answer.evidence:
        assert isinstance(ev.content, dict)
        assert ev.content.get("value") == value


@pytest.mark.parametrize("query", ["Hold TNS?", "hold timing WNS?"])
def test_missing_hold_metric_never_falls_back_to_setup(query: str) -> None:
    answer = ask(query, include_hold=False)
    assert answer.status is QueryStatus.NEEDS_MORE_DATA
    assert not any(
        ev.fact_key in {"metric:TNS", "metric:WNS", "analysis:metric:WNS"}
        for ev in answer.evidence
    )


def test_comparison_uses_hold_values_instead_of_setup_values() -> None:
    answer = ask("Compare hold TNS", compare=True)
    assert answer.status is QueryStatus.ANSWERED
    assert {ev.fact_key for ev in answer.evidence} == {"metric:HOLD_TNS"}
    values: set[float] = set()
    for ev in answer.evidence:
        assert isinstance(ev.content, dict)
        value = ev.content.get("value")
        assert isinstance(value, int | float)
        values.add(value)
    assert values == {-98.0, -97.0}
    assert "difference=1.0" in (answer.answer or "")


def test_unqualified_tns_question_keeps_setup_semantics() -> None:
    answer = ask("TNS?")
    assert answer.status is QueryStatus.ANSWERED
    assert answer.evidence[0].fact_key == "metric:TNS"
    content = answer.evidence[0].content
    assert isinstance(content, dict)
    assert content.get("value") == -509.0
