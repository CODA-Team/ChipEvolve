"""Current business failures survive old successful delivery records."""

import json
from unittest.mock import Mock, patch

import pytest

from admin.test_local_business import deployment
from chip_evolve.cli import main
from chip_evolve.config import read, write
from chip_evolve.progress import experiment_status


@pytest.mark.parametrize("state", ["failed", "running", "pending", "succeeded"])
def test_recovery_does_not_relabel_explicit_current_status(tmp_path, state):
    current = {"status": state, "detail": "current owner outcome"}
    write(tmp_path / "status.json", current)
    write(tmp_path / "result.json", {"run_id": "original-measured-run"})
    write(
        tmp_path / "delivery-recovery.json",
        {"status": "succeeded", "result": str(tmp_path / "result.json")},
    )
    assert experiment_status(tmp_path) == {**current, "delivery_recovered": True}
    assert read(tmp_path / "status.json") == current


@pytest.mark.parametrize("result_exists,record_matches", [(False, True), (True, False)])
def test_unrelated_or_missing_result_is_not_a_recovery(
    tmp_path, result_exists, record_matches
):
    if result_exists:
        write(tmp_path / "result.json", {"run_id": "measured"})
    write(
        tmp_path / "delivery-recovery.json",
        {
            "status": "succeeded",
            "result": str(
                tmp_path / ("result.json" if record_matches else "other.json")
            ),
        },
    )
    assert experiment_status(tmp_path) == {"status": "in_progress"}


def test_delivered_result_without_owner_status_remains_visible(tmp_path):
    write(tmp_path / "result.json", {"run_id": "measured"})
    write(
        tmp_path / "delivery-recovery.json",
        {"status": "succeeded", "result": str(tmp_path / "result.json")},
    )
    assert experiment_status(tmp_path) == {
        "status": "succeeded",
        "delivery_recovered": True,
    }


def test_actual_status_cli_keeps_failure_and_no_active_EDA(
    tmp_path, monkeypatch, capsys
):
    config = deployment(tmp_path)
    folder = config.state / "experiments/gcd/recovered-then-failed"
    write(folder / "request.json", {"design": "gcd", "capability": "goal"})
    write(folder / "result.json", {"run_id": "measured"})
    write(
        folder / "status.json", {"status": "failed", "detail": "new validation failed"}
    )
    write(
        folder / "delivery-recovery.json",
        {"status": "succeeded", "result": str(folder / "result.json")},
    )
    client = Mock()
    client.runs.return_value = []
    monkeypatch.setattr("chip_evolve.jobs.Jobs", lambda *args: Mock(client=client))
    with patch(
        "sys.argv",
        ["chip-evolve", "--config", str(config.path), "status", "--design", "gcd"],
    ):
        assert main() == 0
    result = json.loads(capsys.readouterr().out)
    assert result["active_eda_jobs"] == []
    assert result["experiments"][0]["status"] == {
        "status": "failed",
        "detail": "new validation failed",
        "delivery_recovered": True,
    }
