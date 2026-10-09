"""Receiver dispatch, retries and interruption cannot exceed one handed-off job."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from tests.unit.test_handoff import package

from query_agent.adapters.handoff.eco import EcoReceiver
from query_agent.domain.handoff import HandoffPackage
from query_agent.interfaces.cli import main


def test_cli_receiver_does_not_require_an_investigation_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "package.json"
    path.write_text(package().model_dump_json())
    proposal = tmp_path / "proposal.json"
    proposal.write_text('{"changes": [], "reason": "test dispatch"}')
    run = MagicMock(return_value={"handoff_id": "actual", "status": "checked"})
    monkeypatch.setattr(EcoReceiver, "run", run)
    args = [
        "receive-handoff",
        "--package",
        str(path),
        "--package-sha256",
        hashlib.sha256(path.read_bytes()).hexdigest(),
        "--proposal",
        str(proposal),
        "--receiver-output",
        str(tmp_path / "receipt"),
    ]
    assert main(args) == 0
    assert json.loads(capsys.readouterr().out)["handoff_id"] == "actual"
    run.assert_called_once()
    run.reset_mock()
    path.write_text(path.read_text() + "\n")
    with pytest.raises(ValueError, match="bytes changed"):
        main(args)
    run.assert_not_called()


@pytest.mark.parametrize("role", ["flow", "code"])
def test_unconnected_consumers_never_query_or_execute(
    tmp_path: Path, role: str
) -> None:
    data, execution = MagicMock(), MagicMock()
    receiver = EcoReceiver(data, execution, tmp_path)
    with pytest.raises(ValueError, match="no connected"):
        receiver.run(package(role), {})
    data.read_query.assert_not_called()
    execution.submit.assert_not_called()


def test_failure_cancels_owned_job_and_preserves_dispatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data, execution = MagicMock(), MagicMock()
    data.read_query.return_value = {"data": {"snapshot": {}}}
    execution.submit.return_value = {"run": {"run_id": "owned-run"}}
    execution.run.side_effect = OSError("connection lost")
    monkeypatch.setattr(
        "query_agent.adapters.handoff.eco.buffer_eco_task", MagicMock(return_value={})
    )
    receiver = EcoReceiver(data, execution, tmp_path)
    with pytest.raises(OSError, match="connection lost"):
        receiver.run(package(), {"reason": "bounded"})
    execution.cancel.assert_called_once_with("owned-run")
    assert (
        json.loads((tmp_path / "outstanding.json").read_text())["run_id"] == "owned-run"
    )
    assert (tmp_path / "identity.json").is_file()
    execution.submit.reset_mock()
    with pytest.raises(ValueError, match="changed after acceptance"):
        receiver.run(package(), {"reason": "different experiment"})
    execution.submit.assert_not_called()


def test_completed_receipt_replay_does_not_submit_again(tmp_path: Path) -> None:
    data, execution = MagicMock(), MagicMock()
    receiver = EcoReceiver(data, execution, tmp_path)
    task: HandoffPackage = package()
    proposal = {"reason": "original"}
    (tmp_path / "identity.json").write_text(
        json.dumps(
            {
                "package_sha256": hashlib.sha256(
                    task.model_dump_json().encode()
                ).hexdigest(),
                "proposal": proposal,
            }
        )
    )
    (tmp_path / "receipt.json").write_text('{"snapshot_id": "new-snapshot"}')
    assert receiver.run(task, proposal)["snapshot_id"] == "new-snapshot"
    execution.submit.assert_not_called()
