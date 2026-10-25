from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import pytest

from query_agent.adapters.analysis import (
    FixtureAnalysisProvider,
    UnavailableAnalysisProvider,
)
from query_agent.application.collection import EvidenceCollector
from query_agent.application.planning import KeywordIntentParser, QueryPlanner
from query_agent.application.service import QueryService
from query_agent.domain.analysis import (
    AnalysisProvenance,
    AnalysisScope,
    TimingMetricObservation,
    TimingPathObservation,
)
from query_agent.domain.capability import Capability
from query_agent.domain.evidence import EvidenceSourceKind, EvidenceStatus
from query_agent.domain.query import QueryContext, QueryRequest, QueryStatus
from query_agent.ports.analysis import AnalysisProvider


def service(provider: AnalysisProvider) -> QueryService:
    return QueryService(
        intent_parser=KeywordIntentParser(),
        planner=QueryPlanner(),
        collector=EvidenceCollector(analysis_provider=provider),
    )


def test_analysis_contract_rejects_unscoped_or_unsupported_results() -> None:
    with pytest.raises(ValueError):
        AnalysisScope()
    with pytest.raises(ValueError):
        TimingMetricObservation(
            metric_name="DENSITY",
            value=0.5,
            scope=AnalysisScope(design_id="gcd"),
            provenance=AnalysisProvenance(
                provider="fixture",
                locator="analysis://metric",
                observed_at=datetime(2026, 9, 22, tzinfo=UTC),
            ),
        )


def test_fixture_analysis_returns_scoped_timing_path_evidence() -> None:
    query_service = service(FixtureAnalysisProvider())
    response = query_service.query(
        QueryRequest(
            query="What is the critical path slack?",
            context=QueryContext(
                workspace=Path("/workspace"), design_id="gcd", run_id="run-1"
            ),
        )
    )
    assert response.status is QueryStatus.ANSWERED
    assert response.evidence[0].source_kind is EvidenceSourceKind.SPECIALIZED_ANALYSIS
    assert response.evidence[0].scope.run_id == "run-1"
    assert response.evidence[0].provenance.source_hash == "b" * 64
    assert "u1/A -> u2/Y" in (response.answer or "")


def test_incomplete_analysis_evidence_is_not_answerable() -> None:
    class IncompleteProvider(FixtureAnalysisProvider):
        def get_timing_paths(
            self,
            context: QueryContext,
            *,
            limit: int = 10,
            slack_below: float | None = None,
            check: Literal["setup", "hold"] = "setup",
        ) -> Sequence[TimingPathObservation]:
            item = super().get_timing_paths(
                context, limit=limit, slack_below=slack_below, check=check
            )[0]
            return (item.model_copy(update={"complete": False}),)

    provider = IncompleteProvider()
    response = service(provider).query(
        QueryRequest(
            query="What is the critical path slack?",
            context=QueryContext(workspace=Path("/workspace"), design_id="gcd"),
        )
    )
    assert response.status is QueryStatus.NEEDS_MORE_DATA
    assert response.evidence_status is EvidenceStatus.PARTIAL


def test_unavailable_analysis_provider_is_truthful() -> None:
    provider = UnavailableAnalysisProvider()
    assert Capability.SPECIALIZED_ANALYSIS not in provider.capabilities
    response = service(provider).query(
        QueryRequest(
            query="What is the critical path slack?",
            context=QueryContext(workspace=Path("/workspace"), design_id="gcd"),
        )
    )
    assert response.status is QueryStatus.NEEDS_MORE_DATA
    assert Capability.SPECIALIZED_ANALYSIS in response.missing_capabilities


def test_setup_only_fixture_does_not_supply_a_hold_answer() -> None:
    response = service(FixtureAnalysisProvider()).query(
        QueryRequest(
            query="hold critical path",
            context=QueryContext(workspace=Path("/workspace"), design_id="gcd"),
        )
    )
    assert response.status is QueryStatus.NEEDS_MORE_DATA
    assert not response.evidence
