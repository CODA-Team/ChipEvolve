"""Retire explicitly registered native workers outside the frontend tree."""

from __future__ import annotations

import os
import signal
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from chip_evolve.config import read
from chip_evolve.native_process import _identity, _owned


@dataclass
class WorkerPlan:
    state_root: Path
    registry: Path
    settle_seconds: float


def prepare(spec: dict[str, Any]) -> WorkerPlan | None:
    value = spec.get("native_worker_cleanup")
    if value is None:
        return None
    root = Path(value["state_root"]).resolve()
    registry = Path(value["registry"]).resolve()
    settle = float(value.get("settle_seconds", 5))
    if root.exists():
        raise ValueError("Native worker cleanup requires fresh episode state")
    if registry == root or not registry.is_relative_to(root) or settle <= 0:
        raise ValueError("Native worker registry must be inside fresh episode state")
    return WorkerPlan(root, registry, settle)


def retire(plan: WorkerPlan) -> dict[str, Any]:
    started = time.monotonic()
    processes: dict[int, dict[str, Any]] = {}
    gone, errors = [], []
    try:
        if plan.state_root.resolve() != plan.state_root:
            raise ValueError("Native worker state changed its canonical location")
        if plan.state_root.exists():
            if not plan.registry.resolve().is_relative_to(plan.state_root):
                raise ValueError("Native worker registry escaped its episode")
            workers = read(plan.registry)["workers"]
            if not isinstance(workers, list):
                raise ValueError("Native worker registry needs a workers list")
            for saved in workers:
                pid, ticks = saved["pid"], saved["start_ticks"]
                if type(pid) is not int or pid <= 0 or not isinstance(ticks, str):
                    raise ValueError("Native worker needs actual PID and start ticks")
                current = _identity(pid)
                if current is None:
                    gone.append(saved)
                    continue
                if current["start_ticks"] != ticks:
                    errors.append({"pid": pid, "reason": "worker_identity_changed"})
                    continue
                cwd = (Path("/proc") / str(pid) / "cwd").resolve()
                if not cwd.is_relative_to(plan.state_root):
                    errors.append({"pid": pid, "reason": "worker_outside_owned_state"})
                    continue
                children = _owned(pid)
                if not any(
                    row["pid"] == pid and row["start_ticks"] == ticks
                    for row in children
                ):
                    errors.append(
                        {"pid": pid, "reason": "worker_changed_during_capture"}
                    )
                    continue
                processes.update({row["pid"]: row for row in children})
    except (OSError, ValueError, KeyError, TypeError) as error:
        errors.append({"error_type": type(error).__name__, "reason": str(error)})

    def live() -> list[dict[str, Any]]:
        return [
            saved
            for saved in processes.values()
            if (current := _identity(saved["pid"])) is not None
            and current["start_ticks"] == saved["start_ticks"]
        ]

    for signum in (signal.SIGTERM, signal.SIGKILL):
        for saved in live():
            try:
                os.kill(saved["pid"], signum)
            except ProcessLookupError:
                pass
            except OSError as error:
                errors.append({"pid": saved["pid"], "reason": str(error)})
        deadline = time.monotonic() + plan.settle_seconds
        while live() and time.monotonic() < deadline:
            time.sleep(0.025)
        if not live():
            break
    remaining = live()
    return {
        "status": "completed" if not remaining and not errors else "incomplete",
        "processes": list(processes.values()),
        "already_not_live": gone,
        "not_confirmed_terminal": remaining,
        "errors": errors,
        "wall_seconds": time.monotonic() - started,
        "scope": "Explicit PID/start-tick workers with cwd in fresh owned state and captured descendants; not an enumeration of unregistered workers or other host jobs.",
    }
