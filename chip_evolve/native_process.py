"""Stop only the timed-out native frontend tree, identified before its owner exits."""

from __future__ import annotations

import os
from pathlib import Path
import signal
import subprocess
import time
from typing import Any


def _identity(pid: int) -> dict[str, Any] | None:
    path = Path("/proc") / str(pid)
    try:
        if path.stat().st_uid != os.getuid():
            return None
        fields = (path / "stat").read_text().rsplit(")", 1)[1].split()
    except (FileNotFoundError, ProcessLookupError):
        return None
    if fields[0] == "Z":
        return None
    return {
        "pid": pid,
        "parent": int(fields[1]),
        "session": int(fields[3]),
        "start_ticks": fields[19],
    }


def _owned(owner: int) -> list[dict[str, Any]]:
    rows = {
        int(path.name): value
        for path in Path("/proc").iterdir()
        if path.name.isdigit() and (value := _identity(int(path.name))) is not None
    }
    selected = {owner}
    while True:
        children = {
            pid
            for pid, value in rows.items()
            if value["parent"] in selected or value["session"] == owner
        }
        if children.issubset(selected):
            break
        selected |= children
    return [rows[pid] for pid in selected if pid in rows]


def stop(process: subprocess.Popen[Any]) -> dict[str, Any]:
    """Capture descendants before terminating the native parent; leave EF separate."""
    owned = _owned(process.pid)

    def live():
        result = []
        for saved in owned:
            current = _identity(saved["pid"])
            if current is not None and current["start_ticks"] == saved["start_ticks"]:
                result.append(saved)
        return result

    for signum in (signal.SIGTERM, signal.SIGKILL):
        for value in live():
            try:
                os.kill(value["pid"], signum)
            except ProcessLookupError:
                pass
        deadline = time.monotonic() + 5
        while live() and time.monotonic() < deadline:
            process.poll()
            time.sleep(0.05)
        if not live():
            break
    remaining = live()
    if remaining:
        raise RuntimeError(
            "Native timeout cleanup left live frontends: " + str(remaining)
        )
    process.wait(timeout=5)
    return {
        "status": "completed",
        "owner_pid": process.pid,
        "processes": owned,
        "scope": "Owned native frontend descendants; independent EF processes are outside this tree",
    }
