"""A transient read after committed exports must not rerun native experiments."""

from copy import deepcopy
from http.client import RemoteDisconnected
from types import SimpleNamespace
from urllib.error import HTTPError

import pytest

from admin.test_design_fact_materialization import publication
from chip_evolve.config import read
from chip_evolve.jobs import digest
from chip_evolve.lifecycle import WorkPending
from chip_evolve.physical import publish


@pytest.mark.parametrize(
    "error",
    [
        TimeoutError("timed out"),
        RemoteDisconnected("closed"),
        HTTPError("http://local", 503, "unavailable", {}, None),
    ],
)
def test_committed_exports_resume_without_new_ef_tasks(tmp_path, monkeypatch, error):
    _, source, frame, jobs, kernel, imported = publication(tmp_path, monkeypatch)
    before = deepcopy(frame)
    original_result = digest(source)
    responses = iter([error, {"scope": {"design_id": "gcd"}}])

    def metrics(**_):
        response = next(responses)
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr(
        "chip_evolve.physical.EdaAiClient",
        lambda **_: SimpleNamespace(get_metrics=metrics),
    )
    with pytest.raises(WorkPending) as caught:
        publish(jobs, frame, result_path=source)
    pending = caught.value.receipt
    assert pending["reason"] == "published_facts_read_unavailable"
    assert pending["experiment"] == str(jobs.experiment)
    assert pending["run_id"] == frame["run_id"]
    assert set(pending["snapshot_ids"]) == {"opendb", "orfs", "opensta"}
    assert len(imported) == len(kernel.tasks) == 3
    assert digest(source) == original_result
    assert frame == before
    tasks = deepcopy(kernel.tasks)
    result = publish(jobs, frame, result_path=source)
    assert kernel.tasks == tasks
    assert result["run_id"] == frame["run_id"]
    assert result["metrics"] == frame["metrics"]
    assert (
        read(jobs.experiment / "published-facts-lifecycle.json")["status"]
        == "completed"
    )


@pytest.mark.parametrize("code", [400, 401, 403, 404, 409])
def test_permanent_http_errors_remain_hard_failures(tmp_path, monkeypatch, code):
    _, source, frame, jobs, _, _ = publication(tmp_path, monkeypatch)
    error = HTTPError("http://local", code, "permanent", {}, None)

    def metrics(**_):
        raise error

    monkeypatch.setattr(
        "chip_evolve.physical.EdaAiClient",
        lambda **_: SimpleNamespace(get_metrics=metrics),
    )
    with pytest.raises(HTTPError) as caught:
        publish(jobs, frame, result_path=source)
    assert caught.value is error
    assert not (jobs.experiment / "published-facts-lifecycle.json").exists()


def test_wrong_design_is_not_a_transient_read(tmp_path, monkeypatch):
    _, source, frame, jobs, _, _ = publication(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "chip_evolve.physical.EdaAiClient",
        lambda **_: SimpleNamespace(
            get_metrics=lambda **_: {"scope": {"design_id": "aes"}}
        ),
    )
    with pytest.raises(ValueError, match="another design"):
        publish(jobs, frame, result_path=source)
    assert not (jobs.experiment / "published-facts-lifecycle.json").exists()
