"""Presence refreshes must not generate a durable write on every poll."""

from openroad_platform_runtime import RuntimeStore, worker_presence


def test_unchanged_presence_is_coalesced_but_stays_fresh(tmp_path, monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(worker_presence.time, "time", lambda: clock[0])
    with RuntimeStore(tmp_path / "runtime.sqlite") as store:
        worker_presence.touch(store, "w")
        initial = store._connection.total_changes
        for index in range(1, 20):
            clock[0] = 100.0 + index * 0.05
            worker_presence.touch(store, "w")
        assert store._connection.total_changes == initial
        assert worker_presence.snapshot(store)[0]["state"] == "idle"
        clock[0] = 101.0
        worker_presence.touch(store, "w")
        assert store._connection.total_changes == initial + 1
        assert worker_presence.snapshot(store)[0]["last_seen_at"] == 101.0
        clock[0] = 132.0
        assert worker_presence.snapshot(store)[0]["state"] == "stale"


def test_presence_records_state_attempt_and_pid_changes_immediately(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(worker_presence.time, "time", lambda: 100.0)
    with RuntimeStore(tmp_path / "runtime.sqlite") as store:
        worker_presence.touch(store, "w")
        initial = store._connection.total_changes
        worker_presence.touch(store, "w", attempt_id="first")
        assert worker_presence.snapshot(store)[0]["current_attempt_id"] == "first"
        worker_presence.touch(store, "w", attempt_id="second")
        assert worker_presence.snapshot(store)[0]["current_attempt_id"] == "second"
        worker_presence.touch(store, "w")
        assert worker_presence.snapshot(store)[0]["state"] == "idle"
        monkeypatch.setattr(worker_presence.os, "getpid", lambda: 12345)
        worker_presence.touch(store, "w")
        assert worker_presence.snapshot(store)[0]["pid"] == 12345
        assert store._connection.total_changes == initial + 4
