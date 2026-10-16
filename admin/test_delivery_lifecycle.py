"""Task supervision and uncertain HTTP delivery preserve producer identity."""

import json
import socket
import threading
import time
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from openroad_platform_client import KernelError, KernelUnavailable

from admin.test_local_business import deployment
from chip_evolve.config import read
from chip_evolve.delivery import import_snapshot
from chip_evolve.jobs import Jobs
from chip_evolve.lifecycle import WorkPending, wait_run


class Clock:
    now = 0.0

    def sleep(self, seconds):
        self.now += seconds

    def install(self, monkeypatch):
        monkeypatch.setattr("chip_evolve.lifecycle.time.monotonic", lambda: self.now)
        monkeypatch.setattr("chip_evolve.lifecycle.time.time", lambda: 10000 + self.now)
        monkeypatch.setattr("chip_evolve.lifecycle.time.sleep", self.sleep)


class Kernel:
    def __init__(self, clock, mode):
        self.clock, self.mode, self.run_ids = clock, mode, []

    def run(self, run_id):
        self.run_ids.append(run_id)
        if self.mode == "outage" and self.clock.now < 4:
            raise KernelUnavailable("connection interrupted")
        if self.mode in {"resource", "outage", "busy"}:
            state = (
                "queued"
                if self.clock.now < 10
                else "running"
                if self.clock.now < 1000
                else "succeeded"
            )
        else:
            state = "queued"
        return {"run_id": run_id, "status": state}

    def health(self):
        workers = (
            []
            if self.mode == "none"
            else [
                {
                    "state": "idle",
                    "last_seen_at": time.time() - (999 if self.mode == "stale" else 0),
                    "active_attempt_ids": ["other-task"] if self.mode == "busy" else [],
                }
            ]
        )
        return {"workers": workers, "queue": {"queued": 1}}

    def resources(self, run_id):
        return {
            "waiting_for": "resource: busy"
            if self.mode in {"resource", "outage", "impossible"}
            else "claimable: waiting",
            "capacity": {"budget_cpu_cores": 8, "budget_memory_bytes": 100},
            "would_reserve": {"cpu_cores": 16 if self.mode == "impossible" else 8},
        }

    def artifacts(self, run_id):
        return [{"artifact_id": "retained"}]


@pytest.mark.parametrize(
    "mode,reason",
    [
        ("none", "no_worker"),
        ("stale", "no_worker"),
        ("idle", "awaiting_consumption"),
        ("impossible", "unsatisfiable_resources"),
    ],
)
def test_unconsumable_task_returns_pending_without_cancelling(
    tmp_path, monkeypatch, mode, reason
):
    clock = Clock()
    clock.install(monkeypatch)
    client = Kernel(clock, mode)
    folder = tmp_path / "jobs" / "task"
    with pytest.raises(WorkPending) as error:
        wait_run(
            client,
            "original",
            folder,
            {"unconsumed_seconds": 3, "diagnostic_seconds": 1},
        )
    assert error.value.receipt["reason"] == reason
    assert error.value.receipt["experiment"] == str(tmp_path)
    assert set(client.run_ids) == {"original"}
    assert read(folder / "lifecycle.json")["status"] == "pending"


@pytest.mark.parametrize("mode", ["resource", "outage", "busy"])
def test_resource_queue_and_long_execution_survive_without_log_heuristic(
    tmp_path, monkeypatch, mode
):
    clock = Clock()
    clock.install(monkeypatch)
    client = Kernel(clock, mode)
    result = wait_run(
        client,
        "original",
        tmp_path,
        {"unconsumed_seconds": 2, "unavailable_seconds": 6},
    )
    assert result["run"]["status"] == "succeeded"
    assert clock.now >= 1000
    assert set(client.run_ids) == {"original"}


def test_service_outage_is_bounded_without_cancelling_run(tmp_path, monkeypatch):
    clock = Clock()
    clock.install(monkeypatch)
    client = Kernel(clock, "outage")
    with pytest.raises(WorkPending, match="execution_service_unavailable"):
        wait_run(client, "original", tmp_path, {"unavailable_seconds": 2})
    assert clock.now == 2


def test_queue_budget_is_optional_and_preserves_resource_wait(tmp_path, monkeypatch):
    clock = Clock()
    clock.install(monkeypatch)
    with pytest.raises(WorkPending) as error:
        wait_run(Kernel(clock, "resource"), "original", tmp_path, {"queue_seconds": 3})
    assert error.value.receipt["reason"] == "queue_wait_budget"
    assert error.value.receipt["state"] == "resource_wait"


def test_lost_submit_response_and_reentry_use_one_eda_identity(tmp_path, monkeypatch):
    class Service:
        def __init__(self):
            self.calls = 0
            self.keys = []

        def submit(self, task, **kwargs):
            self.calls += 1
            self.keys.append(kwargs["idempotency_key"])
            if self.calls == 1:
                raise KernelUnavailable("created but response lost")
            return {"run": {"run_id": "one-run"}}

        def run(self, run_id):
            return {"run_id": run_id, "status": "succeeded"}

        def artifacts(self, run_id):
            return []

        def resources(self, run_id):
            return {}

    service = Service()
    monkeypatch.setattr("chip_evolve.jobs.KernelClient", lambda *a, **k: service)
    jobs = Jobs(deployment(tmp_path), "gcd", tmp_path / "experiment")
    with pytest.raises(WorkPending, match="submission_response_unknown"):
        jobs.submit("route", {"adapter": "command"}, [])
    assert (
        jobs.submit("route", {"adapter": "command"}, [])["run"]["run_id"] == "one-run"
    )
    assert (
        jobs.submit("route", {"adapter": "command"}, [])["run"]["run_id"] == "one-run"
    )
    assert service.calls == 2
    assert len(set(service.keys)) == 1


def test_real_execution_failure_is_saved_not_disguised_as_pending(
    tmp_path, monkeypatch
):
    class Service:
        def submit(self, *a, **k):
            return {"run": {"run_id": "failure"}}

        def run(self, run_id):
            return {
                "run_id": run_id,
                "status": "lost",
                "failure": {"message": "worker died"},
            }

        def artifacts(self, run_id):
            return [{"artifact_id": "failure-log"}]

        def resources(self, run_id):
            return {}

    monkeypatch.setattr("chip_evolve.jobs.KernelClient", lambda *a, **k: Service())
    jobs = Jobs(deployment(tmp_path), "gcd", tmp_path / "experiment")
    with pytest.raises(RuntimeError, match="EDA job failed"):
        jobs.submit("route", {}, [])
    receipt = read(jobs.experiment / "jobs/route/execution.json")
    assert receipt["run"]["status"] == "lost"
    assert receipt["artifacts"][0]["artifact_id"] == "failure-log"


def test_kernel_contract_rejection_is_not_retried(tmp_path):
    class Service:
        def run(self, run_id):
            raise KernelError("no permission", status=403)

    with pytest.raises(KernelError, match="no permission"):
        wait_run(Service(), "original", tmp_path, {})


@contextmanager
def data_server(mode):
    state = {"posts": 0, "commits": 0, "ready_at": None}
    receipt = {
        "artifact_id": "art",
        "run_id": "producer",
        "snapshot_id": "snap",
        "status": "imported",
        "attempts": 1,
    }
    snapshot = {
        "snapshot_id": "snap",
        "run_id": "subject",
        "design_id": "gcd",
        "record_counts": {"instances": 5},
    }

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def reply(self, code, data):
            content = json.dumps(data).encode()
            self.send_response(code)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def do_GET(self):
            if self.path == "/imports/art":
                if state["ready_at"] is None or time.monotonic() < state["ready_at"]:
                    self.reply(404, {"error": "not yet imported"})
                else:
                    value = dict(receipt)
                    if mode == "wrong":
                        value["run_id"] = "unrelated"
                    if mode == "failed":
                        value.update(status="failed", error="bad snapshot data")
                    self.reply(200, {"data": {"import_receipt": value}})
            elif self.path == "/snapshots/snap":
                self.reply(200, {"snapshot": snapshot})
            else:
                self.reply(404, {})

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            assert body == {"run_id": "producer", "artifact_id": "art"}
            state["posts"] += 1
            if mode == "reject":
                self.reply(400, {"error": "invalid artifact"})
                return
            if state["ready_at"] is None and mode != "unknown":
                state["commits"] += 1
                state["ready_at"] = time.monotonic() + (
                    0.06 if mode in {"delayed", "timeout"} else 0
                )
            if mode == "timeout":
                time.sleep(0.08)
            self.connection.shutdown(socket.SHUT_RDWR)
            self.connection.close()  # Server accepted input; response deliberately lost.

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", state
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def import_jobs(tmp_path, url):
    d = deployment(tmp_path)
    d.value.update(
        data_url=url,
        lifecycle={
            "poll_seconds": 0.01,
            "data_read_seconds": 1,
            "import_request_seconds": 0.03,
            "import_reconcile_seconds": 0.15,
        },
    )
    return Jobs(d, "gcd", tmp_path / "experiment")


@pytest.mark.parametrize("mode", ["committed", "delayed", "timeout"])
def test_actual_http_response_loss_recovers_receipt_without_repost(tmp_path, mode):
    with data_server(mode) as (url, state):
        jobs = import_jobs(tmp_path, url)
        result = import_snapshot(jobs, "producer", "art", "snap", "subject")
        assert result["import_receipt"]["status"] == "imported"
        assert import_snapshot(jobs, "producer", "art", "snap", "subject") == result
        assert state["posts"] == state["commits"] == 1
        assert read(jobs.experiment / "imports/art.json")["status"] == "completed"


def test_unknown_http_outcome_is_pending_and_explicit_recovery_keeps_identity(tmp_path):
    with data_server("unknown") as (url, state):
        jobs = import_jobs(tmp_path, url)
        with pytest.raises(WorkPending) as error:
            import_snapshot(jobs, "producer", "art", "snap", "subject")
        assert error.value.receipt["reason"] == "import_outcome_unknown"
        assert state["posts"] == 1
        state["ready_at"] = time.monotonic()
        state["commits"] = 1
        assert (
            import_snapshot(jobs, "producer", "art", "snap", "subject")["snapshot"][
                "snapshot_id"
            ]
            == "snap"
        )
        assert state["posts"] == 1
        with pytest.raises(ValueError, match="identity changed"):
            import_snapshot(jobs, "different", "art", "snap", "subject")


@pytest.mark.parametrize(
    "mode,exception",
    [("wrong", ValueError), ("failed", RuntimeError), ("reject", Exception)],
)
def test_receipt_mismatch_and_real_import_failure_remain_failures(
    tmp_path, mode, exception
):
    with data_server(mode) as (url, state):
        jobs = import_jobs(tmp_path, url)
        with pytest.raises(exception) as error:
            import_snapshot(jobs, "producer", "art", "snap", "subject")
        assert not isinstance(error.value, WorkPending)
        assert state["posts"] == 1
        assert read(jobs.experiment / "imports/art.json")["status"] == "failed"


@pytest.mark.parametrize("command", ["run", "resume"])
def test_cli_returns_pending_status_and_recovery_receipt(
    tmp_path, monkeypatch, capsys, command
):
    from chip_evolve.cli import main

    d = deployment(tmp_path)
    experiment = tmp_path / "experiments/gcd/original"
    if command == "resume":
        experiment.mkdir(parents=True)

    def delayed(*args, **kwargs):
        raise WorkPending(
            {
                "status": "pending",
                "phase": "delivery",
                "reason": "import_outcome_unknown",
                "experiment": str(experiment),
                "run_id": "original-eda",
            }
        )

    monkeypatch.setattr("chip_evolve.physical.baseline", delayed)
    monkeypatch.setattr("chip_evolve.delivery.recover", delayed)
    argv = [
        "chip-evolve",
        "--config",
        str(d.path),
        command,
        "--design",
        "gcd",
        "--key",
        "original",
    ]
    if command == "run":
        argv += ["--capability", "orfs"]
    monkeypatch.setattr("sys.argv", argv)
    assert main() == 3
    assert json.loads(capsys.readouterr().out)["run_id"] == "original-eda"
    assert read(experiment / "status.json")["status"] == "pending"
