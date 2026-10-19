"""Explicit episode worker identities survive frontend reparenting."""

import os
import signal
import subprocess
import sys
from pathlib import Path

import pytest

from admin.native_worker_cleanup import prepare, retire
from admin.run_native_codex_episode import run
from admin.test_native_codex_episode import episode
from chip_evolve.config import read, write


def live(pid):
    path = Path("/proc") / str(pid) / "stat"
    return path.exists() and path.read_text().rsplit(")", 1)[1].split()[0] != "Z"


def configure(spec, root):
    value = read(spec)
    value["native_worker_cleanup"] = {
        "state_root": str(root),
        "registry": str(root / "workers.json"),
        "settle_seconds": 0.3,
    }
    write(spec, value)


def detached_body(root):
    # The launcher exits before the outer frontend times out: the worker no
    # longer belongs to the frontend's descendant tree or session.
    launcher = (
        "import subprocess,sys,json,time;from pathlib import Path;"
        "p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'],"
        "start_new_session=True,stdin=subprocess.DEVNULL,"
        "stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);"
        "fields=Path('/proc',str(p.pid),'stat').read_text().rsplit(')',1)[1].split();"
        "Path('workers.json').write_text(json.dumps({'workers':["
        "{'pid':p.pid,'start_ticks':fields[19]}]}))"
    )
    return (
        "import subprocess,sys\n"
        f"root=Path({str(root)!r});root.mkdir()\n"
        f"subprocess.run([sys.executable,'-c',{launcher!r}],cwd=root,check=True)\n"
    )


def test_timeout_stops_registered_reparented_worker_not_independent_process(tmp_path):
    root = tmp_path / "owned-native-state"
    independent = subprocess.Popen(
        [sys.executable, "-c", "import time;time.sleep(60)"],
        start_new_session=True,
    )
    try:
        spec, output = episode(tmp_path, detached_body(root) + "time.sleep(60)\n", 1)
        configure(spec, root)
        result = run(spec, output)
        worker = read(root / "workers.json")["workers"][0]
        assert not live(worker["pid"]), "Detached registered worker survived timeout"
        assert independent.poll() is None
        assert result["status"] == "timed_out"
        cleanup = result["native_worker_cleanup"]
        assert cleanup["status"] == "completed"
        assert worker["pid"] in {row["pid"] for row in cleanup["processes"]}
    finally:
        if (root / "workers.json").exists():
            worker = read(root / "workers.json")["workers"][0]
            if live(worker["pid"]):
                os.kill(worker["pid"], signal.SIGKILL)
        independent.kill()
        independent.wait()


def test_normal_answer_with_unfinished_registered_work_is_failed_and_cleaned(tmp_path):
    root = tmp_path / "owned-native-state"
    spec, output = episode(tmp_path, detached_body(root))
    configure(spec, root)
    try:
        result = run(spec, output)
        worker = read(root / "workers.json")["workers"][0]
        assert not live(worker["pid"])
        assert result["status"] == "failed"
        assert result["business_correctness"] == "native_workers_not_finished_cleanly"
        assert result["native_worker_cleanup"]["status"] == "completed"
        assert read(output / "receipt.json")["status"] == "failed"
    finally:
        if (root / "workers.json").exists():
            worker = read(root / "workers.json")["workers"][0]
            if live(worker["pid"]):
                os.kill(worker["pid"], signal.SIGKILL)


def test_finished_registered_worker_retains_normal_success(tmp_path):
    root = tmp_path / "owned-native-state"
    body = (
        f"root=Path({str(root)!r});root.mkdir()\n"
        "fields=Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()\n"
        "(root/'workers.json').write_text(json.dumps({'workers':["
        "{'pid':__import__('os').getpid(),'start_ticks':fields[19]}]}))\n"
    )
    spec, output = episode(tmp_path, body)
    configure(spec, root)
    result = run(spec, output)
    assert result["status"] == "native_completed"
    assert result["native_worker_cleanup"]["status"] == "completed"
    assert len(result["native_worker_cleanup"]["already_not_live"]) == 1


@pytest.mark.parametrize("case", ["existing", "escape", "zero_settle"])
def test_invalid_fresh_scope_rejected_before_dispatch(tmp_path, case):
    root = tmp_path / "owned-native-state"
    spec, output = episode(tmp_path)
    configure(spec, root)
    value = read(spec)
    if case == "existing":
        root.mkdir()
    elif case == "escape":
        value["native_worker_cleanup"]["registry"] = str(tmp_path / "other.json")
    else:
        value["native_worker_cleanup"]["settle_seconds"] = 0
    write(spec, value)
    with pytest.raises(ValueError):
        run(spec, output)
    assert not output.exists()


@pytest.mark.parametrize("case", ["stale_ticks", "outside_state"])
def test_unrelated_or_reused_identity_is_not_signalled(tmp_path, case):
    root = tmp_path / "owned-native-state"
    spec, _ = episode(tmp_path)
    configure(spec, root)
    plan = prepare(read(spec))
    assert plan is not None
    root.mkdir()
    process = subprocess.Popen(
        [sys.executable, "-c", "import time;time.sleep(60)"],
        cwd=root if case == "stale_ticks" else tmp_path,
        start_new_session=True,
    )
    try:
        ticks = (
            (Path("/proc") / str(process.pid) / "stat")
            .read_text()
            .rsplit(")", 1)[1]
            .split()[19]
        )
        write(
            root / "workers.json",
            {
                "workers": [
                    {
                        "pid": process.pid,
                        "start_ticks": str(int(ticks) + 1)
                        if case == "stale_ticks"
                        else ticks,
                    }
                ]
            },
        )
        result = retire(plan)
        assert result["status"] == "incomplete" and result["errors"]
        assert not result["processes"]
        assert process.poll() is None
    finally:
        process.kill()
        process.wait()


def test_missing_registry_does_not_claim_completed_cleanup(tmp_path):
    root = tmp_path / "owned-native-state"
    spec, _ = episode(tmp_path)
    configure(spec, root)
    plan = prepare(read(spec))
    assert plan is not None
    root.mkdir()
    result = retire(plan)
    assert result["status"] == "incomplete" and result["errors"]
    assert not result["processes"]


def test_cleanup_failure_preserves_original_timeout_and_its_receipt(tmp_path):
    root = tmp_path / "owned-native-state"
    body = f"Path({str(root)!r}).mkdir()\ntime.sleep(60)\n"
    spec, output = episode(tmp_path, body, 0.5)
    configure(spec, root)
    result = run(spec, output)
    assert result["status"] == "timed_out"
    assert result["native_worker_cleanup"]["status"] == "incomplete"
    assert result["business_correctness"] == "native_workers_not_finished_cleanly"
    assert read(output / "receipt.json")["status"] == "timed_out"
