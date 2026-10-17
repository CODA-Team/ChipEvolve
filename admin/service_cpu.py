"""Read named local-service CPU counters for an isolated experiment interval."""

from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path
from typing import Any


def snapshot(processes: dict[str, int]) -> dict[str, dict[str, Any]]:
    """Observe owned services; unavailable counters remain explicitly unknown."""
    rows = {}
    ticks = os.sysconf("SC_CLK_TCK")
    for name, pid in processes.items():
        row: dict[str, Any] = {"pid": pid, "observed_at": time.time()}
        try:
            proc = Path("/proc") / str(pid)
            if proc.stat().st_uid != os.getuid():
                raise PermissionError("Service does not belong to the current user")
            fields = (proc / "stat").read_text().rsplit(") ", 1)[1].split()
            if fields[0] == "Z":
                raise ProcessLookupError("Service has exited")
            row.update(
                status="observed",
                start_ticks=int(fields[19]),
                command_sha256=hashlib.sha256(
                    (proc / "cmdline").read_bytes()
                ).hexdigest(),
                ticks_per_second=ticks,
                self_ticks=int(fields[11]) + int(fields[12]),
                waited_children_ticks=int(fields[13]) + int(fields[14]),
            )
        except (OSError, ValueError, IndexError) as error:
            row.update(status="unavailable", error=str(error))
        rows[name] = row
    return rows


def difference(
    before: dict[str, dict[str, Any]], after: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """Keep each service separate; never silently sum overlapping process trees."""
    rows = {}
    identity = ("pid", "start_ticks", "command_sha256", "ticks_per_second")
    for name in sorted(before.keys() | after.keys()):
        first, last = before.get(name, {}), after.get(name, {})
        row: dict[str, Any] = {
            "status": "unknown",
            "cpu_seconds": None,
            "before": first,
            "after": last,
        }
        if first.get("status") == last.get("status") == "observed":
            if all(first[key] == last[key] for key in identity):
                own = last["self_ticks"] - first["self_ticks"]
                children = (
                    last["waited_children_ticks"] - first["waited_children_ticks"]
                )
                if own >= 0 and children >= 0:
                    tick_rate = first["ticks_per_second"]
                    row.update(
                        status="observed",
                        self_cpu_seconds=own / tick_rate,
                        waited_children_cpu_seconds=children / tick_rate,
                        cpu_seconds=(own + children) / tick_rate,
                    )
                else:
                    row["reason"] = "counter_decreased"
            else:
                row["reason"] = "service_identity_changed"
        else:
            row["reason"] = "boundary_counter_unavailable"
        rows[name] = row
    return {
        "services": rows,
        "scope": (
            "Named owned service processes and their already-waited children only. "
            "A trial must independently verify idle boundaries and no unrelated "
            "service work; work crossing a boundary invalidates whole-trial attribution. "
            "Live/unwaited children, remote model compute and unobserved processes "
            "are outside this scope, not zero. Per-attempt sampled CPU is a separate "
            "overlapping view and must not be added to these counters."
        ),
    }
