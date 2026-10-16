"""Native timeouts retire their frontend descendants, including new sessions."""

import os
from pathlib import Path
import signal
import subprocess
import sys

import pytest

from chip_evolve.professional import invoke


def live(pid):
    try:
        return (Path("/proc") / str(pid) / "stat").read_text().rsplit(")", 1)[
            1
        ].split()[0] != "Z"
    except FileNotFoundError:
        return False


def test_timeout_stops_native_descendant_without_touching_independent_process(tmp_path):
    independent = subprocess.Popen(
        [sys.executable, "-c", "import time;time.sleep(60)"], start_new_session=True
    )
    child_file = tmp_path / "child.pid"
    script = tmp_path / "native.py"
    script.write_text(
        "import subprocess,sys,time\nfrom pathlib import Path\n"
        + 'child=subprocess.Popen([sys.executable,"-c","import time;time.sleep(60)"],start_new_session=True)\n'
        + f"Path({str(child_file)!r}).write_text(str(child.pid))\n"
        + "time.sleep(60)\n"
    )
    child = None
    try:
        with pytest.raises(subprocess.TimeoutExpired):
            invoke(
                [sys.executable, str(script)], tmp_path, dict(os.environ), tmp_path, 2
            )
        assert child_file.exists(), "Native fixture did not start its descendant"
        child = int(child_file.read_text())
        assert not live(child), "Native timeout left its child alive"
        assert independent.poll() is None
    finally:
        if child_file.exists():
            child = int(child_file.read_text())
        if child is not None and live(child):
            os.kill(child, signal.SIGKILL)
        independent.kill()
        independent.wait()


def test_normal_completion_keeps_original_log_and_return_contract(tmp_path):
    assert (
        invoke(
            [sys.executable, "-c", 'print("complete")'],
            tmp_path,
            dict(os.environ),
            tmp_path,
            2,
        )
        is None
    )
    assert (tmp_path / "controller.log").read_text().strip() == "complete"
    assert not (tmp_path / "native-frontend-cleanup.json").exists()


def test_nonzero_native_exit_still_reports_original_controller_failure(tmp_path):
    with pytest.raises(RuntimeError, match="Native professional controller failed"):
        invoke(
            [sys.executable, "-c", "raise SystemExit(7)"],
            tmp_path,
            dict(os.environ),
            tmp_path,
            2,
        )


def test_keyboard_interrupt_keeps_frontend_cleanup_before_propagating(
    tmp_path, monkeypatch
):
    from chip_evolve import native_process

    class Interrupted:
        def wait(self, timeout):
            raise KeyboardInterrupt()

    process = Interrupted()
    stopped = []
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: process)
    monkeypatch.setattr(
        native_process,
        "stop",
        lambda value: stopped.append(value) or {"status": "completed"},
    )
    with pytest.raises(KeyboardInterrupt):
        invoke(["native"], tmp_path, dict(os.environ), tmp_path, 2)
    assert stopped == [process]
