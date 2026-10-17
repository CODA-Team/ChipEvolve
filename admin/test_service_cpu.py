"""Real process accounting includes reaped work and never invents missing CPU."""

import copy
import select
import subprocess
import sys

from admin.service_cpu import difference, snapshot


def ready_line(process):
    assert select.select([process.stdout], [], [], 30)[0], "Service handshake expired"
    return process.stdout.readline().strip()


def test_reaped_short_child_cpu_is_visible_without_per_task_sampling():
    burn = "import time;end=time.process_time()+0.2\nwhile time.process_time()<end:pass"
    code = (
        "import subprocess,sys\nprint('ready',flush=True)\n"
        "for line in sys.stdin:\n"
        f" subprocess.run([sys.executable,'-c',{burn!r}],check=True)\n"
        " print('done',flush=True)\n"
    )
    process = subprocess.Popen(
        [sys.executable, "-u", "-c", code],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert ready_line(process) == "ready"
        before = snapshot({"worker": process.pid})
        process.stdin.write("work\n")
        process.stdin.flush()
        assert ready_line(process) == "done"
        after = snapshot({"worker": process.pid})
        row = difference(before, after)["services"]["worker"]
        assert row["status"] == "observed"
        assert row["waited_children_cpu_seconds"] >= 0.18
        assert row["cpu_seconds"] >= row["waited_children_cpu_seconds"]
    finally:
        process.terminate()
        process.communicate(timeout=10)


def test_terminated_service_counter_is_unknown_instead_of_zero():
    process = subprocess.Popen([sys.executable, "-c", "import time;time.sleep(30)"])
    try:
        before = snapshot({"worker": process.pid})
    finally:
        process.terminate()
        process.wait(timeout=10)
    after = snapshot({"worker": process.pid})
    row = difference(before, after)["services"]["worker"]
    assert row["status"] == "unknown" and row["cpu_seconds"] is None


def test_reused_pid_identity_cannot_create_a_plausible_cpu_delta():
    import os

    before = snapshot({"worker": os.getpid()})
    after = copy.deepcopy(before)
    after["worker"]["start_ticks"] += 1
    row = difference(before, after)["services"]["worker"]
    assert row["status"] == "unknown" and row["cpu_seconds"] is None
    assert row["reason"] == "service_identity_changed"
