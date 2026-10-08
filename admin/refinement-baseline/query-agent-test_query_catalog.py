import base64
import hashlib
from pathlib import Path

from tests.fixtures.fake_execution import FakeExecutionClient
from tests.fixtures.fake_experiment import FakeExperimentContextProvider

from query_agent.adapters.run_evidence import (
    ExecutionFoundationExperimentContextProvider,
    ExecutionFoundationRunEvidenceAdapter,
    HttpExecutionFoundationClient,
)
from query_agent.application.collection import EvidenceCollector
from query_agent.application.planning import KeywordIntentParser, QueryPlanner
from query_agent.application.service import QueryService
from query_agent.domain.evidence import EvidenceLevel
from query_agent.domain.experiment import MetricObservation
from query_agent.domain.query import (
    QueryContext,
    QueryRequest,
    QuerySource,
    QueryStatus,
)


def service(client=None, provider=None):
    provider = provider or (
        ExecutionFoundationExperimentContextProvider(client)
        if client is not None
        else FakeExperimentContextProvider()
    )
    collector = EvidenceCollector(
        experiment_context_provider=provider,
        run_evidence_provider=(
            ExecutionFoundationRunEvidenceAdapter(client) if client else None
        ),
    )
    return QueryService(
        intent_parser=KeywordIntentParser(), planner=QueryPlanner(), collector=collector
    )


def test_design_lists_all_runs_including_failed_and_running():
    response = service().query(
        QueryRequest(
            query="列出实验",
            context=QueryContext(design_id="gcd", source=QuerySource.MANAGED_RUN),
        )
    )
    assert response.status is QueryStatus.ANSWERED
    assert all(
        run_id in (response.answer or "")
        for run_id in ("run_001", "run_002", "run_003")
    )


def test_run_report_exposes_missing_key_result_without_hiding_known_values():
    response = service().query(
        QueryRequest(
            query="汇报设计状态和关键结果",
            context=QueryContext(
                design_id="gcd", run_id="run_001", source=QuerySource.MANAGED_RUN
            ),
        )
    )
    assert response.status is QueryStatus.PARTIAL
    assert "WNS: -0.2" in (response.answer or "")
    assert any(
        item.fact_key == "metric:DESIGN_AREA" for item in response.missing_evidence
    )


def test_run_report_reads_both_registered_key_results():
    provider = FakeExperimentContextProvider()
    provider.metrics += (
        MetricObservation(
            metric_name="DESIGN_AREA",
            value=48.3,
            run_id="run_001",
            design_id="gcd",
            stage_key="routing",
            artifact_id="route-report-001",
            source_hash="a" * 64,
        ),
    )
    response = service(provider=provider).query(
        QueryRequest(
            query="汇报设计状态和关键结果",
            context=QueryContext(
                design_id="gcd", run_id="run_001", source=QuerySource.MANAGED_RUN
            ),
        )
    )
    assert response.status is QueryStatus.ANSWERED
    assert "WNS: -0.2" in (response.answer or "") and "DESIGN_AREA: 48.3" in (
        response.answer or ""
    )
    assert {
        item.level
        for item in response.evidence
        if item.fact_key and item.fact_key.startswith("metric:")
    } == {EvidenceLevel.PARSED_METRIC}


def test_registered_file_can_be_found_and_excerpted():
    client = FakeExecutionClient()
    context = QueryContext(
        design_id="gcd",
        run_id="run_02",
        stage="routing",
        source=QuerySource.MANAGED_RUN,
    )
    found = service(client).query(
        QueryRequest(query="route.timing.rpt 文件在哪", context=context)
    )
    assert found.status is QueryStatus.ANSWERED
    assert "reports/route.timing.rpt" in (found.answer or "")
    assert "place.timing.rpt" not in (found.answer or "")
    excerpt = service(client).query(
        QueryRequest(query="摘取 route.timing.rpt 原文", context=context)
    )
    assert excerpt.status is QueryStatus.ANSWERED
    assert "WNS: -0.20" in (excerpt.answer or "")
    assert excerpt.evidence[0].provenance.source_hash == "a" * 64
    assert excerpt.evidence[1].level is EvidenceLevel.DIRECT_EXCERPT


def test_explicit_run_cannot_be_misattributed_to_another_design():
    response = service(FakeExecutionClient()).query(
        QueryRequest(
            query="汇报设计状态和关键结果",
            context=QueryContext(
                design_id="uart", run_id="run_02", source=QuerySource.MANAGED_RUN
            ),
        )
    )
    assert response.status is QueryStatus.NEEDS_MORE_DATA
    assert not response.evidence


def test_truncated_source_is_reported_as_partial():
    client = FakeExecutionClient()

    def excerpt(run_id, artifact_id, *, offset=0, max_bytes=65536):
        return {
            "artifact_id": artifact_id,
            "text": "first page",
            "bytes_read": 10,
            "truncated": True,
            "sha256": "a" * 64,
        }

    client.artifact_excerpt = excerpt
    context = QueryContext(
        design_id="gcd",
        run_id="run_02",
        stage="routing",
        source=QuerySource.MANAGED_RUN,
    )
    response = service(client).query(
        QueryRequest(query="摘取 route.timing.rpt 原文", context=context)
    )
    assert response.status is QueryStatus.PARTIAL
    assert "truncated excerpt" in (response.answer or "")


def test_binary_original_is_reassembled_and_verified(tmp_path: Path):
    data = bytes(range(256)) * 300
    digest = hashlib.sha256(data).hexdigest()
    client = HttpExecutionFoundationClient("http://localhost")

    def chunk(run_id, artifact_id, *, offset=0, max_bytes=8192):
        part = data[offset : offset + max_bytes]
        return {
            "artifact_id": artifact_id,
            "offset": offset,
            "sha256": digest,
            "size_bytes": len(data),
            "data_base64": base64.b64encode(part).decode(),
            "bytes_read": len(part),
            "truncated": offset + len(part) < len(data),
        }

    client.artifact_excerpt = chunk
    output = tmp_path / "original.bin"
    assert client.download_artifact("run", "artifact", output)["sha256"] == digest
    assert output.read_bytes() == data
