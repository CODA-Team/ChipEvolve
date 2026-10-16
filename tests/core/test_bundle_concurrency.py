"""Slow evidence custody must not stop unrelated attempt leases."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from openroad_platform_contracts import TaskSpec
from openroad_platform_runtime import RuntimeStore, export_run_bundle
from openroad_platform_runtime.bundle import _register_bytes


def start(store, root, name):
    run = store.submit_run(
        TaskSpec(task_id=name, project_id="p", design_id="d", plugin_id="fake"),
        stage_key="main",
        plugin_version="1",
    )
    stage = store.list_stages(run.run_id)[0]
    attempt = store.start_attempt(
        stage.stage_run_id,
        worker_id=name,
        workspace=root / name,
        lease_seconds=30,
    )
    return run, attempt


@pytest.mark.parametrize("custody", ["file", "bytes"])
def test_bundle_custody_does_not_block_other_heartbeat(tmp_path, monkeypatch, custody):
    with RuntimeStore(tmp_path / "runtime.sqlite") as store:
        publisher, owner = start(store, tmp_path, "publisher")
        _, other = start(store, tmp_path, "other")
        entered, release, renewed = Event(), Event(), Event()
        method = "_store_object" if custody == "file" else "_store_bytes"
        original = getattr(store, method)

        def slow(*args):
            entered.set()
            assert release.wait(5)
            return original(*args)

        def publish():
            if custody == "file":
                return export_run_bundle(store, publisher.run_id)
            return _register_bytes(
                store,
                owner.attempt_id,
                store_key="evidence.bin",
                kind="report",
                content=b"original evidence",
                metadata={"producer": "runtime"},
            )

        def heartbeat():
            store.heartbeat(other.attempt_id, worker_id="other", lease_seconds=30)
            renewed.set()

        monkeypatch.setattr(store, method, slow)
        with ThreadPoolExecutor(max_workers=2) as pool:
            copying = pool.submit(publish)
            assert entered.wait(2)
            pulse = pool.submit(heartbeat)
            try:
                responsive = renewed.wait(1)
            finally:
                release.set()
            artifact = copying.result(timeout=5)
            pulse.result(timeout=5)
        assert responsive, "bundle file custody blocked another attempt's renewal"
        identity = (
            artifact["artifact_id"] if custody == "file" else artifact.artifact_id
        )
        assert store.artifact_path(identity).is_file()


def test_concurrent_bundle_exports_keep_one_registered_identity(tmp_path):
    with RuntimeStore(tmp_path / "runtime.sqlite") as store:
        run, _ = start(store, tmp_path, "publisher")
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [
                pool.submit(export_run_bundle, store, run.run_id) for _ in range(4)
            ]
            results = [future.result(timeout=5) for future in futures]
        assert len({row["artifact_id"] for row in results}) == 1
        artifacts = store.describe_run(run.run_id)["stages"][0]["attempts"][0][
            "artifacts"
        ]
        assert sum(row["kind"] == "runtime_bundle" for row in artifacts) == 1


def test_failed_bundle_custody_does_not_register_artifact(tmp_path, monkeypatch):
    with RuntimeStore(tmp_path / "runtime.sqlite") as store:
        run, _ = start(store, tmp_path, "publisher")

        def fail(*args):
            raise OSError("custody write failed")

        monkeypatch.setattr(store, "_store_object", fail)
        with pytest.raises(OSError, match="custody write failed"):
            export_run_bundle(store, run.run_id)
        assert not store.describe_run(run.run_id)["stages"][0]["attempts"][0][
            "artifacts"
        ]
