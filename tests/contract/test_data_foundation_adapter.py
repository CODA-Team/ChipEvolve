"""HTTP adapter refuses ambiguous scope, wrong scope and incomplete facts."""

import json
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from urllib.parse import parse_qs, urlsplit

import pytest
from eda_ai_client import EdaAiClient
from tests.fixtures.fake_experiment import FakeExperimentContextProvider

from query_agent.adapters.data_foundation import (
    DataExperimentProvider,
    DataFoundationProvider,
)
from query_agent.application.collection import EvidenceCollector
from query_agent.application.planning import KeywordIntentParser, QueryPlanner
from query_agent.application.service import QueryService
from query_agent.domain.errors import DataBoundaryError
from query_agent.domain.query import (
    QueryContext,
    QueryRequest,
    QueryResponse,
    QuerySource,
    QueryStatus,
)

SCOPE = {
    "snapshot_id": "s1",
    "design_id": "chip",
    "revision_id": "r1",
    "run_id": "run1",
    "stage": "route",
}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlsplit(self.path)
        query = parse_qs(parsed.query)
        scope = dict(SCOPE)
        data: object
        missing: list[str] = []
        status = "available"
        if parsed.path == "/scope":
            if query.get("run_id") == ["ambiguous"]:
                status, missing = "partial", ["unique_snapshot"]
                data = {"candidates": [{"snapshot_id": "s1"}, {"snapshot_id": "s2"}]}
            else:
                data = {"snapshot": scope}
        elif parsed.path == "/runs/ambiguous/summary":
            data = {
                "run_id": "ambiguous",
                "snapshots": [
                    {
                        "snapshot": {
                            **scope,
                            "run_id": "ambiguous",
                            "snapshot_id": sid,
                            "source_artifacts": [
                                {
                                    "artifact_id": sid + "-source",
                                    "run_id": "exporter",
                                    "sha256": "a" * 64,
                                }
                            ],
                        }
                    }
                    for sid in ("objects", "metrics")
                ],
            }
        elif parsed.path == "/runs/run1/summary":
            data = {
                "run_id": "run1",
                "snapshots": [
                    {
                        "snapshot": {
                            **scope,
                            "source_artifacts": [
                                {
                                    "artifact_id": "report",
                                    "run_id": "analysis-producer",
                                    "sha256": "a" * 64,
                                    "category": "timing_report",
                                }
                            ],
                        }
                    }
                ],
            }
        elif parsed.path.endswith("/resolve-object"):
            name = query["name"][0]
            if name == "missing":
                status, missing, data = (
                    "not_found",
                    ["unique_object"],
                    {"reason": "missing"},
                )
            else:
                if name == "wrong_scope":
                    scope["run_id"] = "other-run"
                data = {
                    "scope": scope,
                    "target": {"id": "i1"},
                    "entities": [
                        {
                            "object_id": "i1",
                            "name": name,
                            "kind": "instance",
                            "cell_type": "BUF_X1",
                        }
                    ],
                }
        elif parsed.path.endswith("/metrics"):
            data = {
                "metrics": [
                    {
                        "name": "WNS",
                        "value": -0.2,
                        "unit": "ns",
                        "corner": "slow",
                        "stage": "route",
                        "snapshot_id": "s1",
                        "status": "available",
                        "evidence": [{"artifact_id": "report", "sha256": "a" * 64}],
                    }
                ]
            }
            if query.get("name") == ["TNS"]:
                metric = data["metrics"][0]
                metric["name"] = "TNS"
                metric["evidence"] = [{"artifact_id": "unverified-report"}]
            if parsed.path == "/runs/ambiguous/metrics":
                metric = data["metrics"][0]
                metric["snapshot_id"] = "metrics"
                if query.get("name") == ["WRONG_SNAPSHOT"]:
                    metric["snapshot_id"] = "unrelated"
                if query.get("name") == ["WRONG_STAGE"]:
                    metric["stage"] = "finish"
        elif parsed.path.endswith("/summary"):
            data = {
                "snapshot": {
                    **scope,
                    "source_artifacts": [
                        {
                            "artifact_id": "report",
                            "run_id": "analysis-producer",
                            "sha256": "a" * 64,
                            "category": "timing_report",
                        }
                    ],
                }
            }
        elif parsed.path.endswith("/timing-paths"):
            path: dict[str, object] = {
                "path_id": "p1",
                "startpoint": "u1/A",
                "endpoint": "u2/Z",
                "slack": -0.2,
                "unit": "ns",
            }
            data = {
                "snapshot": scope,
                "timing_paths": [path],
            }
            if query.get("detail") == ["full"]:
                path["evidence"] = [{"artifact_id": "report", "sha256": "a" * 64}]
            if query.get("limit") == ["2"]:
                path["corner"] = "slow"
        else:
            self.send_error(503)
            return
        body = json.dumps(
            {
                "contract_version": "0.2",
                "status": status,
                "missing": missing,
                "scope": scope,
                "data": data,
                "evidence": [],
            }
        ).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        pass


@pytest.fixture
def provider() -> Iterator[DataFoundationProvider]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever)
    thread.start()
    provider = DataFoundationProvider(
        EdaAiClient(data_url=f"http://127.0.0.1:{server.server_port}")
    )
    yield provider
    server.shutdown()
    server.server_close()
    thread.join()


@pytest.fixture
def service(provider: DataFoundationProvider) -> QueryService:
    return QueryService(
        intent_parser=KeywordIntentParser(),
        planner=QueryPlanner(),
        collector=EvidenceCollector(
            design_data_provider=provider, analysis_provider=provider
        ),
    )


def ask(service: QueryService, question: str, run: str = "run1") -> QueryResponse:
    return service.query(
        QueryRequest(
            query=question,
            context=QueryContext(run_id=run, source=QuerySource.MANAGED_RUN),
        )
    )


def test_actual_http_objects_keep_snapshot_and_locator(service: QueryService) -> None:
    response = ask(service, "Which instance u1?")
    assert response.status is QueryStatus.ANSWERED
    assert response.evidence[0].scope.snapshot_id == "s1"
    assert "/snapshots/s1/objects/i1" in response.evidence_citations[0]


def test_ambiguous_scope_and_missing_target_request_more_data(
    service: QueryService,
) -> None:
    ambiguous = ask(service, "Which instance u1?", "ambiguous")
    assert ambiguous.status is QueryStatus.NEEDS_MORE_DATA
    assert "s2" in ambiguous.reasons[0]
    assert ask(service, "Which instance missing?").status is QueryStatus.NEEDS_MORE_DATA


def test_wrong_scope_is_failure_not_an_answer(service: QueryService) -> None:
    assert ask(service, "Which instance wrong_scope?").status is QueryStatus.FAILED


def test_timing_cites_source_and_refuses_missing_corner_and_source(
    service: QueryService,
) -> None:
    assert ask(service, "timing WNS").status is QueryStatus.ANSWERED
    paths = ask(service, "critical path")
    assert paths.status is QueryStatus.NEEDS_MORE_DATA
    assert paths.evidence and paths.evidence[0].status.value == "PARTIAL"


def test_root_cause_is_not_inferred_from_metrics(service: QueryService) -> None:
    response = ask(service, "Why did timing become worse?")
    assert response.status is QueryStatus.NEEDS_MORE_DATA
    assert not response.evidence
    assert response.answer is not None
    assert response.answer.startswith("NEEDS_MORE_DATA")


def test_unverified_metric_source_does_not_produce_a_complete_answer(
    service: QueryService,
) -> None:
    assert ask(service, "timing TNS").status is QueryStatus.NEEDS_MORE_DATA


def test_timing_path_fetches_per_record_sources_and_declared_corner(
    provider: DataFoundationProvider,
) -> None:
    paths = provider.get_timing_paths(
        QueryContext(run_id="run1", source=QuerySource.MANAGED_RUN), limit=2
    )
    assert paths[0].complete
    assert paths[0].provenance.source_hash == "a" * 64
    assert paths[0].provenance.locator.endswith("/sources/report/excerpt")


def test_data_stage_artifacts_follow_snapshot_sources_not_control_stages(
    provider: DataFoundationProvider,
) -> None:
    adapter = DataExperimentProvider(FakeExperimentContextProvider(), provider)
    sources = adapter.list_artifacts("run1", stage_key="route")
    assert len(sources) == 1
    source = sources[0]
    assert (source.artifact_id, source.run_id, source.stage_key) == (
        "report",
        "run1",
        "route",
    )
    assert source.source_hash == "a" * 64
    assert source.locator.endswith("/snapshots/s1/sources/report/excerpt")


def test_run_metrics_do_not_require_one_snapshot_for_all_fact_types(
    provider: DataFoundationProvider,
) -> None:
    adapter = DataExperimentProvider(FakeExperimentContextProvider(), provider)
    observations = adapter.list_metrics("ambiguous", stage_key="route")
    assert len(observations) == 1
    observation = observations[0]
    assert observation.run_id == "ambiguous"
    assert observation.stage_key == "route"
    assert observation.value == -0.2
    assert observation.complete
    assert observation.source_hash == "a" * 64
    artifacts = adapter.list_artifacts("ambiguous", stage_key="route")
    assert {item.artifact_id for item in artifacts} == {
        "objects-source",
        "metrics-source",
    }
    assert all(
        item.run_id == "ambiguous" and item.stage_key == "route" for item in artifacts
    )


@pytest.mark.parametrize("metric", ["WRONG_SNAPSHOT", "WRONG_STAGE"])
def test_run_metrics_still_check_the_indexed_snapshot_and_requested_stage(
    provider: DataFoundationProvider, metric: str
) -> None:
    adapter = DataExperimentProvider(FakeExperimentContextProvider(), provider)
    with pytest.raises(DataBoundaryError, match="metric response crosses"):
        adapter.list_metrics("ambiguous", stage_key="route", metric_name=metric)
