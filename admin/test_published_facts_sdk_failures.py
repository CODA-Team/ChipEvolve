"""Exercise the installed public SDK's real HTTP error wrapping at publication."""

from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import socket
from threading import Thread

from eda_ai_client import EdaAiClient, EdaAiError
import pytest

from admin.test_design_fact_materialization import publication
from chip_evolve.config import read
from chip_evolve.jobs import digest
from chip_evolve.lifecycle import WorkPending
from chip_evolve.physical import publish


@contextmanager
def data_server(responses):
    responses = iter(responses)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            status, body = next(responses)
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@pytest.mark.parametrize("status", [502, 503])
def test_real_sdk_http_unavailable_recovers_without_resubmitting_ef(
    tmp_path, monkeypatch, status
):
    deployment, source, frame, jobs, kernel, _ = publication(tmp_path, monkeypatch)
    monkeypatch.setattr("chip_evolve.physical.EdaAiClient", EdaAiClient)
    before = digest(source)
    with data_server(
        [(status, b'{"error":"temporary"}'), (200, b'{"scope":{"design_id":"gcd"}}')]
    ) as url:
        deployment.value["data_url"] = url
        with pytest.raises(WorkPending) as caught:
            publish(jobs, frame, result_path=source)
        assert isinstance(caught.value.__cause__, EdaAiError)
        assert caught.value.__cause__.status == status
        assert len(kernel.tasks) == 3
        assert digest(source) == before
        result = publish(jobs, frame, result_path=source)
        assert len(kernel.tasks) == 3
        assert result["run_id"] == frame["run_id"]
        assert result["metrics"] == frame["metrics"]
        assert (
            read(jobs.experiment / "published-facts-lifecycle.json")["status"]
            == "completed"
        )


@pytest.mark.parametrize(
    "status,body", [(400, b"{}"), (401, b"{}"), (404, b"{}"), (409, b"{}"), (200, b"{")]
)
def test_real_sdk_permanent_or_malformed_response_is_not_pending(
    tmp_path, monkeypatch, status, body
):
    deployment, source, frame, jobs, _, _ = publication(tmp_path, monkeypatch)
    monkeypatch.setattr("chip_evolve.physical.EdaAiClient", EdaAiClient)
    with data_server([(status, body)]) as url:
        deployment.value["data_url"] = url
        with pytest.raises(EdaAiError):
            publish(jobs, frame, result_path=source)
        assert not (jobs.experiment / "published-facts-lifecycle.json").exists()


def test_real_sdk_connection_refusal_is_pending(tmp_path, monkeypatch):
    deployment, source, frame, jobs, kernel, _ = publication(tmp_path, monkeypatch)
    monkeypatch.setattr("chip_evolve.physical.EdaAiClient", EdaAiClient)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    deployment.value["data_url"] = f"http://127.0.0.1:{port}"
    with pytest.raises(WorkPending) as caught:
        publish(jobs, frame, result_path=source)
    assert isinstance(caught.value.__cause__, EdaAiError)
    assert caught.value.__cause__.status is None
    assert len(kernel.tasks) == 3
