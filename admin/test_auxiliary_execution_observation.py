"""Auxiliary diagnostics must not turn a known live task into a false outage."""

import pytest
from openroad_platform_client import KernelUnavailable

from admin.test_delivery_lifecycle import Clock
from chip_evolve.config import read
from chip_evolve.lifecycle import WorkPending, wait_run


class DiagnosticFaultKernel:
    def __init__(self, clock, endpoint, state):
        self.clock = clock
        self.endpoint = endpoint
        self.state = state
        self.run_ids = []
        self.health_calls = 0

    def run(self, run_id):
        self.run_ids.append(run_id)
        self.current = self.state if self.clock.now < 5 else "succeeded"
        return {"run_id": run_id, "status": self.current}

    def health(self):
        self.health_calls += 1
        if self.endpoint == "health":
            raise KernelUnavailable("health read timed out")
        return {"workers": [], "queue": {}}

    def resources(self, run_id):
        if self.endpoint == "resources" and self.current != "succeeded":
            raise KernelUnavailable("resource diagnostic timed out")
        return {"waiting_for": "", "capacity": {}, "would_reserve": {}}

    def artifacts(self, run_id):
        return [{"artifact_id": "original-evidence"}]


@pytest.mark.parametrize("endpoint", ["health", "resources"])
@pytest.mark.parametrize("state", ["running", "queued"])
def test_live_status_survives_auxiliary_diagnostic_outage(
    tmp_path, monkeypatch, endpoint, state
):
    clock = Clock()
    clock.install(monkeypatch)
    client = DiagnosticFaultKernel(clock, endpoint, state)
    policy = {
        "unavailable_seconds": 2,
        "unconsumed_seconds": 2,
        "diagnostic_seconds": 1,
    }
    if state == "queued":
        # A visible queue alone does not establish a healthy worker. Retain
        # bounded reconnection when diagnostics cannot establish consumption.
        with pytest.raises(WorkPending, match="execution_service_unavailable"):
            wait_run(client, "same-registered-run", tmp_path, policy)
        assert clock.now == 2
    else:
        result = wait_run(client, "same-registered-run", tmp_path, policy)
        assert result["run"]["status"] == "succeeded"
        assert result["artifacts"] == [{"artifact_id": "original-evidence"}]
        assert clock.now == 5
        assert read(tmp_path / "lifecycle.json")["status"] == "succeeded"
    assert set(client.run_ids) == {"same-registered-run"}


def test_failed_diagnostic_keeps_the_original_observation_interval(
    tmp_path, monkeypatch
):
    clock = Clock()
    clock.install(monkeypatch)
    client = DiagnosticFaultKernel(clock, "health", "running")
    result = wait_run(
        client,
        "same-registered-run",
        tmp_path,
        {"unavailable_seconds": 2, "diagnostic_seconds": 15},
    )
    assert result["run"]["status"] == "succeeded"
    assert client.health_calls == 1


def test_diagnostic_programming_error_is_not_hidden(tmp_path, monkeypatch):
    clock = Clock()
    clock.install(monkeypatch)
    client = DiagnosticFaultKernel(clock, "health", "running")

    def invalid_health():
        raise ValueError("invalid diagnostic payload")

    client.health = invalid_health
    with pytest.raises(ValueError, match="invalid diagnostic payload"):
        wait_run(client, "same-registered-run", tmp_path, {})
