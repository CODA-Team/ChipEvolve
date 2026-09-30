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
from typing import Any

import pytest

from eda_ai_client import TOOL_SCHEMAS, TOOL_NAMES, EdaAiClient, EdaAiError
from eda_ai_client.client import _segment

REQUESTS: list[str] = []


class _Stub(BaseHTTPRequestHandler):
    """Answers the handful of shapes these tests exercise."""

    def do_GET(self) -> None:  # noqa: N802
        REQUESTS.append(self.path)
        body = self._envelope(self._route(self.path), self.path)
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
        return {"contract_version": "0.1", "tool": "stub", "scope": scope,
                "status": "available", "missing": [], "data": data,
                "evidence": [], "limitations": []}

    def _route(self, path: str) -> dict[str, Any]:
        route, _, query = path.partition("?")
        if route.endswith("/snapshots/snap-1"):
            return {"snapshot": {"snapshot_id": "snap-1", "run_id": "run-1"}}
        if route.endswith("/runs/run-1/metrics"):
            rows = [{"name": "WNS", "snapshot_id": "snap-1", "status": "available"},
                    {"name": "TNS", "snapshot_id": "snap-2", "status": "available"}]
            # the server filters, so the stub must too
            if "snapshot_id=snap-1" in query:
                rows = [row for row in rows if row["snapshot_id"] == "snap-1"]
            return {"run_id": "run-1", "count": len(rows), "returned": len(rows),
                    "metrics": rows}
        if route.endswith("/instances"):
            name = query.split("name=")[-1]
            if name == "none":
                return {"instances": []}
            if name == "many":
                return {"instances": [{"object_id": "inst:1"}, {"object_id": "inst:2"}]}
            return {"instances": [{"object_id": "inst:7"}]}
        if "/timing-paths/path%3A0" in route:
            return {"snapshot_id": "snap-1",
                    "timing_path": {"path_id": "path:0", "check": "setup"}}
        if "/objects/inst%3A7/context" in route:
            return {"entities": [{"object_id": "inst:7"}], "relations": [{"relation_id": "r1"}],
                    "physical_context": [{"object_id": "inst:7"}], "evidence": []}
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


def test_snapshot_scoped_metrics_keep_only_that_snapshot(client: EdaAiClient) -> None:
    result = client.get_metrics(snapshot_id="snap-1")
    # CONTRACT 1: the tool's own structure lives under `data`, the fact boundary
    # under `scope`, and the page counts describe what was actually returned.
    assert [row["name"] for row in result["data"]["metrics"]] == ["WNS"]
    assert result["data"]["count"] == 1 and result["data"]["returned"] == 1
    assert result["scope"]["snapshot_id"] == "snap-1"
    assert "snapshot_id=snap-1" in REQUESTS[-1]


def test_name_lookup_separates_zero_one_and_many(client: EdaAiClient) -> None:
    assert client.get_instance("snap-1", "none")["status"] == "not_found"
    partial = client.get_instance("snap-1", "many")
    assert partial["status"] == "partial" and len(partial["instances"]) == 2
    found = client.get_instance("snap-1", "unique")
    assert found["status"] == "available"
    assert found["instance"]["object_id"] == "inst:7"
    assert found["relations"] == [{"relation_id": "r1"}]


def test_kernel_tools_refuse_without_a_kernel_url(client: EdaAiClient) -> None:
    with pytest.raises(EdaAiError, match="kernel_url"):
        client.list_runs()


def test_published_schemas_match_the_client(client: EdaAiClient) -> None:
    # frozen on purpose: adding a tool must be a deliberate contract change, and the
    # published list in CONTRACT.md section 4 must be updated with it
    assert len(TOOL_SCHEMAS) == 13
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
