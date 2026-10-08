"""Public HTTP pages must preserve coverage, native counts, scope and physical units."""

import json
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest
from eda_ai_client import EdaAiClient

from query_agent.adapters.data_foundation import DataFoundationProvider
from query_agent.domain.design import DesignRegion
from query_agent.domain.errors import DataBoundaryError, MissingDataError
from query_agent.domain.query import QueryContext, QuerySource

SCOPE = {
    "snapshot_id": "s",
    "design_id": "chip",
    "revision_id": "r",
    "run_id": "run",
    "stage": "route",
}
SOURCE = {"artifact_id": "odb", "sha256": "a" * 64}
PINS = [
    {
        "object_id": f"p{i}",
        "kind": "pin",
        "name": f"u{i}/A",
        "parent_id": "i",
        "attributes": {"direction": "INPUT"},
        "evidence": [SOURCE],
    }
    for i in range(3)
]
INSTANCE = {
    "object_id": "i",
    "kind": "instance",
    "name": "u",
    "attributes": {"master": "BUF_X1"},
    "evidence": [SOURCE],
}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        route = urlsplit(self.path)
        query = parse_qs(route.query)
        data: dict[str, Any]
        if route.path == "/scope":
            data = {"snapshot": SCOPE}
        elif route.path.endswith("/resolve-object"):
            kind, name = query["kind"][0], query["name"][0]
            entity = (
                INSTANCE
                if kind == "instance"
                else {
                    "object_id": "n-" + name,
                    "name": name,
                    "kind": kind,
                    "evidence": [SOURCE],
                }
            )
            data = {
                "scope": SCOPE,
                "target": {"id": entity["object_id"]},
                "entities": [entity],
            }
        elif route.path.endswith("/relationships"):
            offset = int(query["offset"][0])
            row = {
                "relation_id": str(offset),
                "subject_id": "i",
                "object_id": f"p{offset}",
                "predicate": "owns",
            }
            data = {
                "snapshot": SCOPE,
                "target": INSTANCE,
                "count": 3,
                "relations": [row],
                "entities": [INSTANCE, PINS[offset]],
                "coverage": {"missing_entity_ids": []},
                "next_offset": offset + 1 if offset < 2 else None,
            }
        elif route.path.endswith("/engineering"):
            data = {"snapshot": SCOPE, "load_count": 3}
            if "/n-incomplete/" in route.path:
                data["availability"] = {
                    "complete_connectivity": {"status": "unavailable"}
                }
            if "/n-mismatch/" in route.path:
                data["load_count"] = 4
        elif route.path.endswith("/objects"):
            if query["kind"] == ["instance"]:
                assert query["region_units"] == ["um"]
                data = {
                    "snapshot": SCOPE,
                    "count": 1,
                    "objects": [INSTANCE],
                    "next_offset": None,
                }
            else:
                offset = int(query["offset"][0])
                data = {
                    "snapshot": SCOPE,
                    "count": 3,
                    "objects": [PINS[offset]],
                    "next_offset": offset + 1 if offset < 2 else None,
                }
        elif "/physical/" in route.path:
            data = {"snapshot": SCOPE, "physical_context": {"location_um": [5.0, 6.0]}}
        else:
            self.send_error(404)
            return
        body = json.dumps(
            {
                "contract_version": "0.2",
                "status": "available",
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
    yield DataFoundationProvider(
        EdaAiClient(data_url=f"http://127.0.0.1:{server.server_port}")
    )
    server.shutdown()
    server.server_close()
    thread.join()


def test_complete_fanout_and_relations_traverse_every_page(
    provider: DataFoundationProvider,
) -> None:
    context = QueryContext(
        snapshot_id="s", run_id="run", source=QuerySource.MANAGED_RUN
    )
    net = provider.get_net(context, "n")
    instance = provider.get_instance(context, "u")
    assert net is not None and instance is not None
    assert instance.cell_type == "BUF_X1"
    assert [p.ref.name for p in provider.get_fanout(context, net.ref)] == [
        "u0/A",
        "u1/A",
        "u2/A",
    ]
    relations = provider.get_connections(context, instance.ref)
    assert len(relations) == 3 and relations[2].target.name == "u2/A"
    assert relations[2].predicate == "owns"
    assert relations[0].source.source_hash == "a" * 64


def test_native_count_disagreement_is_not_a_partial_fanout_answer(
    provider: DataFoundationProvider,
) -> None:
    context = QueryContext(
        snapshot_id="s", run_id="run", source=QuerySource.MANAGED_RUN
    )
    incomplete = provider.get_net(context, "incomplete")
    mismatch = provider.get_net(context, "mismatch")
    assert incomplete is not None and mismatch is not None
    with pytest.raises(MissingDataError, match="disagree"):
        provider.get_fanout(context, incomplete.ref)
    with pytest.raises(DataBoundaryError, match="complete load"):
        provider.get_fanout(context, mismatch.ref)


def test_foreign_reference_is_rejected_before_relationship_use(
    provider: DataFoundationProvider,
) -> None:
    context = QueryContext(
        snapshot_id="s", run_id="run", source=QuerySource.MANAGED_RUN
    )
    instance = provider.get_instance(context, "u")
    assert instance is not None
    foreign = instance.ref.model_copy(update={"run_id": "other"})
    with pytest.raises(DataBoundaryError, match="scope"):
        provider.get_connections(context, foreign)


def test_explicit_location_and_region_units(provider: DataFoundationProvider) -> None:
    context = QueryContext(
        snapshot_id="s", run_id="run", source=QuerySource.MANAGED_RUN
    )
    instance = provider.get_instance(context, "u")
    assert instance is not None
    location = provider.get_location(context, instance.ref)
    assert location is not None and (location.x, location.y, location.units) == (
        5.0,
        6.0,
        "um",
    )
    items = provider.get_instances_in_region(
        context, DesignRegion(x_min=0, y_min=0, x_max=10, y_max=10, units="um")
    )
    assert [item.ref.name for item in items] == ["u"]
    with pytest.raises(MissingDataError, match="explicit"):
        provider.get_instances_in_region(
            context, DesignRegion(x_min=0, y_min=0, x_max=10, y_max=10, units="mm")
        )
