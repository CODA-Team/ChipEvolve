"""Real resource claims must not starve work behind blocked queue heads."""

import threading
import time
from dataclasses import replace

import pytest
from openroad_platform_contracts import ResourceRequest, RuntimeStatus

from test_worker import task, worker  # noqa: F401 -- shared real runtime fixture


@pytest.mark.parametrize("submit_late", [False, True])
def test_async_worker_reaches_small_work_behind_resource_blocked_runs(
    request, monkeypatch, submit_late
):
    """A retrying queue head cannot consume every free attempt slot forever."""
    w, store, runtime = request.getfixturevalue("worker")
    runtime.config.capacity_cpu_cores = 4
    runtime.config.capacity_memory_bytes = 4 << 30
    runtime.config.default_task_memory_bytes = 1 << 30
    runtime.config.platform_fraction = 1.0
    w.batch = 2

    def make_task(name, gib):
        return replace(
            task(name),
            labels={"memory_approval": "manual"},
            resources=ResourceRequest(cpu_cores=1, memory_bytes=int(gib * (1 << 30))),
        )

    holder = runtime.submit(make_task("already-running", 3))
    store.start_attempt(
        store.list_stages(holder.run_id)[0].stage_run_id,
        worker_id="other-worker",
        workspace=runtime.config.workspace_root / "held",
        lease_seconds=30,
        resources=holder.task_spec.resources,
        capacity_cpu_cores=4,
        capacity_memory_bytes=4 << 30,
        platform_fraction=1.0,
    )
    blocked = [runtime.submit(make_task(f"large-{n}", 2)) for n in range(2)]
    small = [] if submit_late else [runtime.submit(make_task("small", 0.5))]
    claim = store.start_attempt

    def slow_blocked_claim(*args, **kwargs):
        attempt = claim(*args, **kwargs)
        if attempt is None:
            time.sleep(0.06)  # A refused real reservation still consumes thread time.
        return attempt

    monkeypatch.setattr(store, "start_attempt", slow_blocked_claim)
    stop = threading.Event()
    cycles = []

    def observe(report):
        cycles.append(report)
        if submit_late and len(cycles) == 5:
            small.append(runtime.submit(make_task("small", 0.5)))
        if small and store.get_run(small[0].run_id).status is RuntimeStatus.SUCCEEDED:
            stop.set()

    w.on_cycle = observe
    timer = threading.Timer(1.5, stop.set)
    timer.start()
    try:
        w.serve_forever(stop)
    finally:
        timer.cancel()
        timer.join()
    assert small and store.get_run(small[0].run_id).status is RuntimeStatus.SUCCEEDED
    assert store.get_run(holder.run_id).status is RuntimeStatus.RUNNING
    assert store.resource_totals() == (1, 3 << 30)
    assert all(
        store.get_run(run.run_id).status is RuntimeStatus.QUEUED for run in blocked
    )
    assert all(
        not store.list_attempts(store.list_stages(run.run_id)[0].stage_run_id)
        for run in blocked
    )
