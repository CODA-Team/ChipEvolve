"""Bounded client supervision; EF retains ownership of every live process."""

from __future__ import annotations

import time
from http.client import HTTPException
from pathlib import Path
from typing import Any

from openroad_platform_client import KernelClient, KernelError, KernelUnavailable

from .config import write

TERMINAL = {"succeeded", "failed", "cancelled", "timed_out", "lost"}


class WorkPending(RuntimeError):
    """A durable task may still progress; reconnect instead of starting over."""

    def __init__(self, receipt: dict[str, Any]):
        self.receipt = receipt
        super().__init__(receipt["reason"])


def pending(path: Path, **value: Any) -> WorkPending:
    if "experiment" not in value and path.parent.parent.name == "jobs":
        value["experiment"] = str(path.parent.parent.parent)
    receipt = {"status": "pending", "receipt": str(path), **value}
    write(path, receipt)
    return WorkPending(receipt)


def transient(error: Exception) -> bool:
    return isinstance(error, (KernelUnavailable, OSError, HTTPException)) or (
        isinstance(error, KernelError)
        and error.status is not None
        and error.status >= 500
    )


def observe(
    client: KernelClient, run: dict[str, Any], *, worker_stale: float
) -> dict[str, Any]:
    health, resources = client.health(), client.resources(run["run_id"])
    fresh = [
        row
        for row in health.get("workers", [])
        if row.get("state") not in {"stopped", "stale"}
        and time.time() - row.get("last_seen_at", 0) < worker_stale
    ]
    reason = resources.get("waiting_for") or ""
    capacity = resources.get("capacity", {})
    need = resources.get("would_reserve", {})
    impossible = any(
        need.get(key, 0) > capacity.get("budget_" + key, float("inf"))
        for key in ("cpu_cores", "memory_bytes")
    )
    if run["status"] in TERMINAL:
        state = run["status"]
    elif run["status"] == "running":
        state = "running"  # EF lease/timeout owns execution health, not log silence.
    elif not fresh:
        state = "no_worker"
    elif impossible:
        state = "unsatisfiable_resources"
    elif reason.startswith("resource:"):
        state = "resource_wait"
    elif any(w.get("active_attempt_ids") or w.get("current_attempt_id") for w in fresh):
        state = "worker_busy"
    else:
        state = "awaiting_consumption"
    return {
        "state": state,
        "run_id": run["run_id"],
        "run_status": run["status"],
        "waiting_for": reason,
        "workers": health.get("workers", []),
        "queue": health.get("queue", {}),
        "resources": resources,
    }


def wait_run(
    client: KernelClient, run_id: str, folder: Path, policy: dict[str, Any]
) -> dict[str, Any]:
    """Healthy execution has no additional client deadline or cancellation."""
    path = folder / "lifecycle.json"
    poll = float(policy.get("poll_seconds", 1))
    interval = float(policy.get("diagnostic_seconds", 15))
    grace = float(policy.get("unconsumed_seconds", 300))
    outage = float(policy.get("unavailable_seconds", 120))
    queue_budget = float(policy.get("queue_seconds", 0))  # 0 = no healthy queue cap
    started = time.monotonic()
    last_diagnostic = -float("inf")
    previous, since = "", started
    disconnected: float | None = None
    view: dict[str, Any] = {}
    while True:
        try:
            run = client.run(run_id)
            now = time.monotonic()
            if run["status"] in TERMINAL:
                result = {
                    "run": run,
                    "artifacts": client.artifacts(run_id),
                    "resources": client.resources(run_id),
                    "wait_seconds": now - started,
                }
                write(
                    path,
                    {
                        "phase": "execution",
                        "status": run["status"],
                        "run_id": run_id,
                        "observed_at": time.time(),
                    },
                )
                return result
            if now - last_diagnostic >= interval or run["status"] != view.get(
                "run_status"
            ):
                last_diagnostic = now
                try:
                    view = observe(
                        client,
                        run,
                        worker_stale=float(policy.get("worker_stale_seconds", 120)),
                    )
                except Exception as error:
                    if not transient(error) or run["status"] != "running":
                        raise
                    # A successful running read remains authoritative. Missing
                    # diagnostics cannot establish worker loss or starvation.
                    view = {
                        "state": "running",
                        "run_id": run_id,
                        "run_status": run["status"],
                        "diagnostics_status": "unavailable",
                        "diagnostic_error": str(error),
                    }
                if view["state"] != previous:
                    previous, since = view["state"], now
                write(
                    path,
                    {
                        "phase": "execution",
                        "status": "waiting" if previous != "running" else "running",
                        **view,
                        "observed_at": time.time(),
                        "wait_seconds": now - started,
                    },
                )
            disconnected = None
        except Exception as error:
            if not transient(error):
                raise
            now = time.monotonic()
            disconnected = disconnected if disconnected is not None else now
            write(
                path,
                {
                    "phase": "execution",
                    "status": "reconnecting",
                    "run_id": run_id,
                    "error": str(error),
                    "observed_at": time.time(),
                },
            )
            if now - disconnected >= outage:
                raise pending(
                    path,
                    phase="execution",
                    run_id=run_id,
                    reason="execution_service_unavailable",
                    detail=str(error),
                ) from error
            time.sleep(poll)
            continue
        if (
            previous in {"no_worker", "awaiting_consumption", "unsatisfiable_resources"}
            and now - since >= grace
        ):
            raise pending(path, phase="execution", reason=previous, **view)
        if (
            queue_budget > 0
            and run["status"] in {"queued", "retry_wait"}
            and now - started >= queue_budget
        ):
            raise pending(path, phase="execution", reason="queue_wait_budget", **view)
        time.sleep(poll)
