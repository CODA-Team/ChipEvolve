"""Presence refreshes must not generate a durable write on every poll."""

from threading import Event
from types import SimpleNamespace

from openroad_platform_runtime import RuntimeStore, RuntimeWorker, worker_presence


def test_serving_leaves_refresh_interval_after_a_slow_durable_touch(monkeypatch):
    clock, touches, cycles = [0.0], [], []
    stop = Event()

    def slow_touch(*args):
        touches.append(clock[0])
        clock[0] += 2.0  # Models a durable write slower than the refresh period.

    def cycle(report):
        cycles.append(report)
        clock[0] += worker_presence.PRESENCE_REFRESH_SECONDS / 10
        if len(cycles) == 20:
            stop.set()

    monkeypatch.setattr(
        "openroad_platform_runtime.worker.time.monotonic", lambda: clock[0]
    )
    monkeypatch.setattr("openroad_platform_runtime.worker.touch", slow_touch)
    worker = RuntimeWorker(
        SimpleNamespace(reclaim_expired_attempts=list),
        SimpleNamespace(config=SimpleNamespace(worker_id="w")),
        idle_seconds=0,
        on_cycle=cycle,
    )
    monkeypatch.setattr(worker, "_finish_abandoned_cancellations", lambda: 0)
    monkeypatch.setattr(worker, "_runnable_candidates", tuple)
    worker.serve_forever(stop)
    assert len(cycles) == 20  # Dispatch and cancellation maintenance remain live.
    assert len(touches) == 2
    assert touches[1] - touches[0] >= 2 + worker_presence.PRESENCE_REFRESH_SECONDS


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
        clock[0] = 100.0 + worker_presence.PRESENCE_REFRESH_SECONDS
        worker_presence.touch(store, "w")
        assert store._connection.total_changes == initial + 1
        assert (
            worker_presence.snapshot(store)[0]["last_seen_at"]
            == 100.0 + worker_presence.PRESENCE_REFRESH_SECONDS
        )
        clock[0] += 31.0
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
