"""EF-managed work waits for its declared memory without changing EDA inputs."""

import json
import os
import selectors
import subprocess
import sys
from unittest.mock import Mock

import pytest

from eda_toolkits import environment
from eda_toolkits.openroad import adapter
from eda_toolkits.orfs import OrfsToolkit


GIB = 1024**3


def test_unmanaged_native_call_retains_previous_low_memory_error(monkeypatch):
    monkeypatch.delenv("EDA_TASK_MEMORY_BYTES", raising=False)
    monkeypatch.setattr(environment, "available_memory_bytes", lambda: 12 * GIB)
    with pytest.raises(RuntimeError, match="less than 16 GiB"):
        environment.require_eda_memory()


def test_managed_eight_gib_task_accepts_twelve_gib_available(monkeypatch):
    monkeypatch.setenv("EDA_TASK_MEMORY_BYTES", str(8 * GIB))
    monkeypatch.setattr(environment, "available_memory_bytes", lambda: 12 * GIB)
    sleep = Mock()
    monkeypatch.setattr(environment.time, "sleep", sleep)
    assert environment.require_eda_memory() == 12 * GIB
    sleep.assert_not_called()


def test_managed_task_waits_for_its_actual_memory_budget(monkeypatch, capsys):
    monkeypatch.setenv("EDA_TASK_MEMORY_BYTES", str(8 * GIB))
    values = iter([6 * GIB, 7 * GIB, 9 * GIB])
    monkeypatch.setattr(environment, "available_memory_bytes", lambda: next(values))
    sleep = Mock()
    monkeypatch.setattr(environment.time, "sleep", sleep)
    assert environment.require_eda_memory() == 9 * GIB
    assert sleep.call_count == 2
    assert "waiting for declared EF budget" in capsys.readouterr().out


def test_large_task_does_not_start_at_old_sixteen_gib_floor(monkeypatch):
    monkeypatch.setenv("EDA_TASK_MEMORY_BYTES", str(24 * GIB))
    values = iter([20 * GIB, 25 * GIB])
    monkeypatch.setattr(environment, "available_memory_bytes", lambda: next(values))
    sleep = Mock()
    monkeypatch.setattr(environment.time, "sleep", sleep)
    assert environment.require_eda_memory() == 25 * GIB
    sleep.assert_called_once_with(1)


@pytest.mark.parametrize("memory", [4 * GIB, 24 * GIB, None])
def test_adapter_uses_declared_task_memory_before_native_work(
    tmp_path, monkeypatch, memory
):
    class AdmissionReached(Exception):
        pass

    request = tmp_path / "request.json"
    request.write_text(
        json.dumps(
            {
                "task": {
                    "resources": {"memory_bytes": memory} if memory else None,
                    "inputs": {"adapter": "a2_stage"},
                }
            }
        )
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "adapter",
            "--request",
            str(request),
            "--result",
            str(tmp_path / "result.json"),
        ],
    )
    monkeypatch.setenv("EDA_TASK_MEMORY_BYTES", "stale-value")

    def check():
        assert os.environ["EDA_TASK_MEMORY_BYTES"] == str(memory or 16 * GIB)
        raise AdmissionReached

    monkeypatch.setattr(adapter, "require_eda_memory", check)
    with pytest.raises(AdmissionReached):
        adapter.main()
    assert not (tmp_path / "result.json").exists()


def test_orfs_submission_does_not_run_host_memory_admission_locally(
    tmp_path, monkeypatch
):
    monkeypatch.delenv("EDA_TASK_MEMORY_BYTES", raising=False)
    memory = Mock(return_value=1)
    monkeypatch.setattr(environment, "available_memory_bytes", memory)
    client = Mock()
    client.submit.return_value = {"run": {"status": "queued"}}
    toolkit = OrfsToolkit(client, {}, tmp_path)
    assert toolkit.submit_flow()["run"]["status"] == "queued"
    memory.assert_not_called()
    assert client.submit.call_args.args[0]["resources"]["memory_bytes"] == 24 * GIB


def test_wait_remains_cancellable_as_the_normal_adapter_process():
    script = (
        "from eda_toolkits import environment; "
        "environment.available_memory_bytes=lambda:0; "
        "environment.require_eda_memory(); print('NATIVE_WOULD_START',flush=True)"
    )
    process = subprocess.Popen(
        [sys.executable, "-u", "-c", script],
        env=dict(os.environ, EDA_TASK_MEMORY_BYTES=str(8 * GIB)),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert process.stdout is not None
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            assert selector.select(timeout=5), (
                "Memory wait must be visible in the execution log"
            )
        assert "waiting for declared EF budget" in process.stdout.readline()
        assert process.poll() is None
        process.terminate()
        stdout, _stderr = process.communicate(timeout=5)
        assert process.returncode == -15
        assert "NATIVE_WOULD_START" not in stdout
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
