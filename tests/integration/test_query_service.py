from pathlib import Path

from tests.fixtures.fake_experiment import FakeExperimentContextProvider

from query_agent.adapters.artifacts import LocalArtifactProvider
from query_agent.adapters.design_data import UnavailableDesignDataProvider
from query_agent.adapters.knowledge import EDACorpusKnowledgeProvider
from query_agent.application.collection import EvidenceCollector
from query_agent.application.planning import KeywordIntentParser, QueryPlanner
from query_agent.application.service import QueryService
from query_agent.domain.query import (
    QueryContext,
    QueryRequest,
    QuerySource,
    QueryStatus,
)


def make_service(workspace: Path) -> QueryService:
    artifacts = LocalArtifactProvider(workspace)
    collector = EvidenceCollector(
        artifact_provider=artifacts,
        design_data_provider=UnavailableDesignDataProvider(),
    )
    return QueryService(
        intent_parser=KeywordIntentParser(),
        planner=QueryPlanner(),
        collector=collector,
    )


def test_artifact_query_returns_cited_evidence() -> None:
    workspace = Path(__file__).parents[1] / "fixtures" / "sample_workspace"
    response = make_service(workspace).query(
        QueryRequest(
            query="where is the final artifact file?",
            context=QueryContext(workspace=workspace, run_id="run-1"),
        )
    )
    assert response.status is QueryStatus.ANSWERED
    answer = response.answer or ""
    assert "results/final.def" in answer or "results/final.odb" in answer
    assert response.evidence_citations


def test_root_cause_without_design_data_is_needs_more_data() -> None:
    workspace = Path(__file__).parents[1] / "fixtures" / "sample_workspace"
    response = make_service(workspace).query(
        QueryRequest(
            query="why did routing stop?",
            context=QueryContext(workspace=workspace, run_id="run-1"),
        )
    )
    assert response.status is QueryStatus.NEEDS_MORE_DATA
    assert response.missing_capabilities
    assert "NEEDS_MORE_DATA" in (response.answer or "")


def test_knowledge_query_uses_corpus_evidence(tmp_path: Path) -> None:
    dataset = tmp_path / "Non-Augmented_Data" / "Question-Answer"
    dataset.mkdir(parents=True)
    (dataset / "Question-Answer_Dataset.csv").write_text(
        "Prompts,Answers\nWhat is global routing?,It assigns routes.\n",
        encoding="utf-8",
    )
    service = QueryService(
        intent_parser=KeywordIntentParser(),
        planner=QueryPlanner(),
        collector=EvidenceCollector(
            knowledge_provider=EDACorpusKnowledgeProvider(tmp_path),
        ),
    )

    response = service.query(
        QueryRequest(
            query="What is global routing?",
            context=QueryContext(workspace=tmp_path),
        )
    )

    assert response.status is QueryStatus.ANSWERED
    assert response.evidence[0].source_kind.value == "knowledge"
    assert "It assigns routes." in (response.answer or "")


def test_knowledge_evidence_is_not_artificially_run_scoped(tmp_path: Path) -> None:
    dataset = tmp_path / "Non-Augmented_Data" / "Question-Answer"
    dataset.mkdir(parents=True)
    (dataset / "Question-Answer_Dataset.csv").write_text(
        "Prompts,Answers\nWhat is CTS?,Clock tree synthesis.\n",
        encoding="utf-8",
    )
    service = QueryService(
        intent_parser=KeywordIntentParser(),
        planner=QueryPlanner(),
        collector=EvidenceCollector(
            knowledge_provider=EDACorpusKnowledgeProvider(tmp_path),
        ),
    )

    response = service.query(
        QueryRequest(
            query="What is CTS?",
            context=QueryContext(workspace=tmp_path, run_id="run-1"),
        )
    )

    assert response.status is QueryStatus.ANSWERED


def test_context_provider_selects_latest_valid_run_without_adapter_knowledge() -> None:
    provider = FakeExperimentContextProvider()
    service = QueryService(
        intent_parser=KeywordIntentParser(),
        planner=QueryPlanner(),
        collector=EvidenceCollector(experiment_context_provider=provider),
        experiment_context_provider=provider,
    )
    response = service.query(
        QueryRequest(
            query="latest completed routing WNS",
            context=QueryContext(
                design_id="gcd",
                stage="routing",
                source=QuerySource.MANAGED_RUN,
            ),
        )
    )
    assert response.status is QueryStatus.ANSWERED
    assert response.context_selection is not None
    assert response.context_selection.selected_run_id == "run_001"
    assert response.evidence[0].scope.stage == "routing"


def test_current_context_refuses_to_reuse_previous_metric() -> None:
    provider = FakeExperimentContextProvider()
    service = QueryService(
        intent_parser=KeywordIntentParser(),
        planner=QueryPlanner(),
        collector=EvidenceCollector(experiment_context_provider=provider),
        experiment_context_provider=provider,
    )
    response = service.query(
        QueryRequest(
            query="current routing WNS",
            context=QueryContext(
                design_id="gcd",
                stage="routing",
                source=QuerySource.MANAGED_RUN,
            ),
        )
    )
    assert response.status is QueryStatus.NEEDS_MORE_DATA
    assert response.context_selection is not None
    assert response.context_selection.selected_run_id is None
    assert response.missing_evidence
