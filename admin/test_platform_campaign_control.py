"""Exercise actual timeout groups and inherited locks without running EDA."""

import fcntl
import os
import signal
import subprocess
import time

from run_platform_campaign import process_identity, stop_controller


def test_interrupt_stops_timeout_publishers_but_preserves_independent_worker(tmp_path):
    lock = tmp_path / "controller.lock"
    worker_pid = tmp_path / "publisher.pid"
    script = tmp_path / "controller.sh"
    script.write_text(
        'exec 9>"$1"\n'
        "flock -n 9 || exit 1\n"
        'timeout 60s bash -c \'echo "$$" > "$1"; sleep 60\' publisher "$2"\n'
    )
    independent = subprocess.Popen(["sleep", "60"], start_new_session=True)
    controller = subprocess.Popen(
        ["bash", str(script), str(lock), str(worker_pid)], start_new_session=True
    )
    try:
        deadline = time.monotonic() + 5
        while not worker_pid.exists() and time.monotonic() < deadline:
            assert controller.poll() is None
            time.sleep(0.02)
        assert worker_pid.exists()
        publisher = process_identity(int(worker_pid.read_text()))
        assert publisher["session_id"] == controller.pid
        assert publisher["process_group"] != controller.pid
        with lock.open("w") as probe:
            try:
                fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                pass
            else:
                raise AssertionError("Publisher fixture did not inherit the lock.")
            stopped = stop_controller(controller)
            assert (
                len({row["process_group"] for row in stopped["publishers_before"]}) >= 2
            )
            assert stopped["publishers_after"] == []
            fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert independent.poll() is None
        assert process_identity(independent.pid)["session_id"] == independent.pid
    finally:
        if controller.poll() is None:
            stop_controller(controller)
        # The fixture may have left a timeout group if an assertion failed early.
        if worker_pid.exists():
            identity = process_identity(int(worker_pid.read_text()))
            if identity and identity["session_id"] == controller.pid:
                try:
                    os.killpg(identity["process_group"], signal.SIGKILL)
                except ProcessLookupError:
                    pass
        independent.terminate()
        independent.wait(timeout=5)
