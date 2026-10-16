"""Observers see committed state while durable writers are busy."""

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from openroad_platform_contracts import ResourceRequest, RuntimeStatus, TaskSpec
from openroad_platform_runtime import RuntimeStore, worker_presence


def running(store, root):
    run = store.submit_run(
        TaskSpec(task_id="observed", project_id="p", design_id="d", plugin_id="fake"),
        stage_key="main",
        plugin_version="1",
    )
    stage = store.list_stages(run.run_id)[0]
    attempt = store.start_attempt(
        stage.stage_run_id,
        worker_id="w",
        workspace=root / "attempt",
        lease_seconds=30,
        resources=ResourceRequest(cpu_cores=2, memory_bytes=1024),
        capacity_cpu_cores=4,
        capacity_memory_bytes=4096,
        platform_fraction=1,
    )
    worker_presence.touch(store, "w")
    return run, attempt


@pytest.mark.parametrize("settlement", ["COMMIT", "ROLLBACK"])
def test_observers_do_not_wait_for_uncommitted_writer(tmp_path, settlement):
    with RuntimeStore(tmp_path / "runtime.sqlite") as store:
        run, attempt = running(store, tmp_path)
        finished = Event()

        def observe():
            values = (
                store.get_run(run.run_id).status,
                store.resource_totals(),
                store._attempt_usage(attempt.attempt_id),
                worker_presence.snapshot(store)[0]["state"],
                worker_presence.queue(store)["waiting"],
            )
            finished.set()
            return values

        with ThreadPoolExecutor(max_workers=1) as pool:
            with store._lock:
                store._connection.execute("BEGIN IMMEDIATE")
                store._connection.execute("DELETE FROM runtime_resource_reservations")
                store._connection.execute(
                    "UPDATE runtime_runs SET status = 'cancel_requested'"
                )
                store._connection.execute("UPDATE runtime_workers SET state = 'idle'")
                store._connection.execute("UPDATE runtime_attempts SET cpu_seconds=12")
                future = pool.submit(observe)
                try:
                    responsive = finished.wait(0.5)
                finally:
                    store._connection.execute(settlement)
            values = future.result(timeout=5)
        assert responsive, "observation queued behind a durable write transaction"
        assert values == (RuntimeStatus.RUNNING, (2, 1024), None, "running", 0)
        assert store.resource_totals() == (
            (0, 0) if settlement == "COMMIT" else (2, 1024)
        )
        assert store.get_run(run.run_id).status is (
            RuntimeStatus.CANCEL_REQUESTED
            if settlement == "COMMIT"
            else RuntimeStatus.RUNNING
        )


def test_worker_presence_failure_rolls_back_lease_renewal(tmp_path):
    with RuntimeStore(tmp_path / "runtime.sqlite") as store:
        _, attempt = running(store, tmp_path)
        before = tuple(
            store._connection.execute(
                "SELECT heartbeat_at, lease_expires_at FROM runtime_attempts"
            ).fetchone()
        )
        store._connection.execute(
            "CREATE TRIGGER reject_presence BEFORE INSERT ON runtime_workers "
            "BEGIN SELECT RAISE(ABORT, 'presence persistence failed'); END"
        )
        with pytest.raises(sqlite3.IntegrityError, match="presence persistence failed"):
            store.heartbeat(attempt.attempt_id, worker_id="w", lease_seconds=30)
        assert (
            tuple(
                store._connection.execute(
                    "SELECT heartbeat_at, lease_expires_at FROM runtime_attempts"
                ).fetchone()
            )
            == before
        )
        assert not store._connection.in_transaction


def test_heartbeat_commits_presence_and_lease_together(tmp_path):
    with RuntimeStore(tmp_path / "runtime.sqlite") as store:
        _, attempt = running(store, tmp_path)
        store._connection.execute("DELETE FROM runtime_workers")
        store.heartbeat(attempt.attempt_id, worker_id="w", lease_seconds=30)
        with RuntimeStore(store.db_path) as observer:
            row = worker_presence.snapshot(observer)[0]
            assert row["worker_id"] == "w"
            assert row["current_attempt_id"] == attempt.attempt_id
            assert row["state"] == "running"
            assert observer._connection.execute("PRAGMA synchronous").fetchone()[0] == 2
