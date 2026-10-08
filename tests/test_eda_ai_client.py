"""Client-level checks that need no live service.

The clean-environment demo proves the package installs and answers real HTTP.
These tests pin the parts that are easy to get silently wrong: the URL quoting
of IDs like ``path:0``, the snapshot-scoped metric filter, the three distinct
outcomes of a name lookup, and that the published schemas stay in step with the
client's tools.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs
from typing import Any

import pytest

from eda_ai_client import TOOL_SCHEMAS, TOOL_NAMES, EdaAiClient, EdaAiError
from eda_ai_client.client import _segment

REQUESTS: list[str] = []


class _Stub(BaseHTTPRequestHandler):
    """Answers the handful of shapes these tests exercise."""

    def do_GET(self) -> None:  # noqa: N802
        REQUESTS.append(self.path)
        data = self._route(self.path)
        body = data if self.path.startswith('/kernel/') else self._envelope(data, self.path)
        payload = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    @staticmethod
    def _envelope(data: dict[str, Any], path: str) -> dict[str, Any]:
        """The real service answers with a CONTRACT 1 envelope; so does the stub."""
        scope = {}
        if "snap-1" in path:
            scope["snapshot_id"] = "snap-1"
        return {"contract_version": "0.2", "tool": "stub", "scope": scope,
                "status": data.pop("resolution_status", "available"), "missing": [], "data": data,
                "evidence": [], "limitations": []}

    def _route(self, path: str) -> dict[str, Any]:
        route, _, query = path.partition("?")
        if route.endswith("/designs"):
            return {"designs": [{"design_id": "chip", "snapshot_count": 17}]}
        if route.endswith("/artifacts"):
            return {"artifacts": [{"artifact_id": "a1", "kind": "report"}]}
        if route.endswith("/scope"):
            return {"resolution_status": "partial", "candidates": [{"snapshot_id": "one"}, {"snapshot_id": "two"}]}
        if route.endswith("/snapshots/snap-1/metrics"):
            return {"run_id": "run-1", "count": 1, "returned": 1,
                    "metrics": [{"name": "WNS", "snapshot_id": "snap-1", "status": "available"}]}
        if route.endswith("/resolve-object"):
            name = parse_qs(query).get("name", [""])[0]
            if name == "none":
                return {"resolution_status": "not_found", "matches": []}
            if name == "many":
                return {"resolution_status": "partial", "matches": [{"object_id": "inst:1"}, {"object_id": "inst:2"}]}
            return {"target": {"id": "inst:7"}, "entities": [{"object_id": "inst:7"}],
                    "relations": [{"relation_id": "r1"}], "physical_context": []}
        if "/timing-paths/path%3A0" in route:
            return {"snapshot_id": "snap-1",
                    "timing_path": {"path_id": "path:0", "check": "setup"}}
        if route.endswith('/timing-paths'):
            return {'timing_paths': [{'path_id': 'path:0', 'evidence': [{'artifact_id': 'source'}]}]}
        raise AssertionError(f"unexpected stub route: {path}")

    def log_message(self, *args: Any) -> None:
        pass


@pytest.fixture()
def client() -> Any:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Stub)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    REQUESTS.clear()
    yield EdaAiClient(data_url=f"http://127.0.0.1:{server.server_address[1]}")
    server.shutdown()
    server.server_close()


def test_ids_with_colons_are_url_quoted(client: EdaAiClient) -> None:
    client.get_timing_path("snap-1", "path:0")
    assert any("/timing-paths/path%3A0" in path for path in REQUESTS), REQUESTS
    assert _segment("path:0") == "path%3A0"


def test_artifact_filter_is_forwarded_in_one_request(client: EdaAiClient) -> None:
    client.kernel_url = client.data_url
    assert client.list_artifacts("run:1", kind="report")[0]["artifact_id"] == "a1"
    assert REQUESTS == ["/kernel/runs/run%3A1/artifacts?kind=report"]


def test_full_timing_evidence_request_stays_bounded(client: EdaAiClient) -> None:
    paths = client.get_timing_paths('s1', detail='full', limit=3)
    assert paths['data']['timing_paths'][0]['evidence'][0]['artifact_id'] == 'source'
    assert len(REQUESTS) == 1
    params = parse_qs(REQUESTS[0].split('?')[1])
    assert params['detail'] == ['full'] and params['limit'] == ['3']


def test_snapshot_scoped_metrics_keep_only_that_snapshot(client: EdaAiClient) -> None:
    result = client.get_metrics(snapshot_id="snap-1")
    # CONTRACT 1: the tool's own structure lives under `data`, the fact boundary
    # under `scope`, and the page counts describe what was actually returned.
    assert [row["name"] for row in result["data"]["metrics"]] == ["WNS"]
    assert result["data"]["count"] == 1 and result["data"]["returned"] == 1
    assert result["scope"]["snapshot_id"] == "snap-1"
    assert len(REQUESTS) == 1
    assert REQUESTS[0].startswith("/snapshots/snap-1/metrics?")


def test_name_lookup_separates_zero_one_and_many(client: EdaAiClient) -> None:
    assert client.get_instance("snap-1", "none")["status"] == "not_found"
    partial = client.get_instance("snap-1", "many")
    assert partial["status"] == "partial" and len(partial["data"]["matches"]) == 2
    found = client.get_instance("snap-1", "unique")
    assert found["status"] == "available"
    assert found["data"]["entities"][0]["object_id"] == "inst:7"
    assert found["data"]["relations"] == [{"relation_id": "r1"}]


def test_kernel_tools_refuse_without_a_kernel_url(client: EdaAiClient) -> None:
    with pytest.raises(EdaAiError, match="kernel_url"):
        client.list_runs()


def test_published_schemas_match_the_client(client: EdaAiClient) -> None:
    # frozen on purpose: adding a tool must be a deliberate contract change, and the
    # published list in CONTRACT.md section 4 must be updated with it
    assert len(TOOL_SCHEMAS) == 15
    for name in TOOL_NAMES:
        assert callable(getattr(client, name)), f"{name} has a schema but no method"
    for schema in TOOL_SCHEMAS:
        assert schema["type"] == "function"
        parameters = schema["function"]["parameters"]
        assert parameters["type"] == "object"
        assert set(parameters["required"]) <= set(parameters["properties"])
    assert len(set(TOOL_NAMES)) == len(TOOL_NAMES), "duplicate tool names"


def test_schemas_are_json_serialisable(tmp_path: Path) -> None:
    target = tmp_path / "tools.json"
    target.write_text(json.dumps(TOOL_SCHEMAS), encoding="utf-8")
    assert json.loads(target.read_text())[0]["function"]["name"] == "list_designs"


def test_catalog_and_scope_are_not_reinterpreted(client: EdaAiClient) -> None:
    assert client.list_designs()["data"]["designs"][0]["snapshot_count"] == 17
    result = client.resolve_scope(run_id="run-1")
    assert result["status"] == "partial" and len(result["data"]["candidates"]) == 2
    assert len(REQUESTS) == 2


def test_net_selection_does_not_guess_from_identifier_prefix(client: EdaAiClient) -> None:
    client.get_net_context("snap-1", "net:literal/name")
    assert "name=net%3Aliteral%2Fname" in REQUESTS[-1]
    client.get_net_context("snap-1", "net:7", by="object_id")
    assert "object_id=net%3A7" in REQUESTS[-1]
    with pytest.raises(ValueError, match="by must"):
        client.get_net_context("snap-1", "n1", by="guess")
