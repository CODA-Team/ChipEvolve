"""Health sees committed catalog state while a real import transaction is open."""

import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer

import pytest
from openroad_app_data_foundation.connections import ReadPool
from openroad_app_data_foundation.repository import DataStore
from openroad_app_data_foundation.server import Handler


def snapshot(identifier):
    return {
        "snapshot_id": identifier,
        "design_id": "chip",
        "revision_id": "r",
        "run_id": "run-" + identifier,
        "stage": "finish",
        "created_at": "2026-10-19",
    }


@pytest.mark.parametrize("commit", [False, True])
def test_health_reads_committed_identity_during_open_writer_transaction(
    tmp_path, commit
):
    path = tmp_path / "facts.sqlite"
    store = DataStore(path)
    store.connection.execute("PRAGMA journal_mode=WAL")
    store.connection.execute("PRAGMA synchronous=FULL")
    store.register({"snapshot": snapshot("old")})
    pool = ReadPool(path, size=1)
    handler = type("HealthHandler", (Handler,), {"store": store, "read_pool": pool})
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    writer_started, release_writer = threading.Event(), threading.Event()

    def writer():
        try:
            with store.connection:
                store.connection.execute(
                    "INSERT INTO snapshots(snapshot_id,payload) VALUES (?,?)",
                    ("new", json.dumps(snapshot("new"))),
                )
                writer_started.set()
                assert release_writer.wait(10)
                if not commit:
                    raise ValueError("rollback this incomplete import")
        except ValueError:
            pass

    worker = threading.Thread(target=writer)
    worker.start()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def health():
        with opener.open(
            f"http://127.0.0.1:{server.server_port}/health", timeout=1
        ) as response:
            return json.load(response)

    try:
        assert writer_started.wait(2)
        during = health()
        assert not release_writer.is_set()
        assert during["status"] == "ok"
        assert during["database"]["snapshots"] == 1
        assert during["database"]["runs"] == ["run-old"]
        assert during["database"]["read_only"] is False
        assert during["database"]["path"] == str(path.resolve())
        release_writer.set()
        worker.join(timeout=2)
        assert not worker.is_alive()
        after = health()
        assert after["database"]["snapshots"] == (2 if commit else 1)
        assert (
            after["database"]["manifest_sha256"]
            != during["database"]["manifest_sha256"]
        ) is commit
        assert after["source_fingerprint"] == during["source_fingerprint"]
    finally:
        release_writer.set()
        worker.join(timeout=2)
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        pool.close()
        store.close()


@pytest.mark.parametrize("read_only", [False, True])
def test_health_keeps_actual_service_write_mode_with_read_pool(tmp_path, read_only):
    path = tmp_path / "mode.sqlite"
    store = DataStore(path)
    store.register({"snapshot": snapshot("old")})
    store.close()
    store = DataStore(path, read_only=read_only)
    pool = ReadPool(path, size=1)
    try:
        handler = object.__new__(Handler)
        handler.store = store
        with pool.connection() as reader:
            result = handler._get("/health", {}, reader)
        assert result["database"]["read_only"] is read_only
        assert result["database"]["snapshots"] == 1
    finally:
        pool.close()
        store.close()
