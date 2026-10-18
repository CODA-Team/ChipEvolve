"""Validation retry status must describe this owner, preserving old failures."""

import json
from unittest.mock import patch

import pytest

from admin.test_adoption_consistency import frame_at
from admin.test_local_business import deployment
from chip_evolve import validation
from chip_evolve.cli import main
from chip_evolve.config import business_lock, read, write
from chip_evolve.jobs import digest
from chip_evolve.lifecycle import WorkPending


def fixture(tmp_path):
    config = deployment(tmp_path)
    reference = frame_at(tmp_path, "reference")
    candidate = frame_at(tmp_path, "candidate", 0.9)
    folder = config.state / "experiments/gcd/current-validation"
    return config, reference, candidate, folder


@pytest.mark.parametrize("retry", [False, True])
def test_actual_validation_operation_observes_running_before_work(
    tmp_path, monkeypatch, retry
):
    config, reference, candidate, folder = fixture(tmp_path)
    if retry:

        def old_error(*args):
            raise ValueError("old configured strategy rejected before proof")

        monkeypatch.setattr(validation, "_validate", old_error)
        with pytest.raises(ValueError, match="old configured"):
            validation.validate(config, candidate, reference, folder.name)
        prior = read(folder / "status.json")

    def work(*args):
        assert read(folder / "status.json") == {
            "status": "running",
            "kind": "validation",
        }
        history = folder / "validation-status-history.jsonl"
        if retry:
            lines = [json.loads(line) for line in history.read_text().splitlines()]
            assert lines[-1]["previous"] == prior
            assert lines[-1]["replaced_at"] > 0
        else:
            assert not history.exists()
        return {"passed": True}

    monkeypatch.setattr(validation, "_validate", work)
    assert validation.validate(config, candidate, reference, folder.name)["passed"]


def test_actual_CLI_pending_is_scoped_to_validation_not_failed_source(
    tmp_path, monkeypatch, capsys
):
    config, reference, candidate, folder = fixture(tmp_path)
    upstream = config.state / "experiments/gcd/old-native-search"
    write(
        upstream / "status.json", {"status": "failed", "native_search_completed": False}
    )
    before = (upstream / "status.json").read_bytes()
    pending = {
        "status": "pending",
        "phase": "delivery",
        "experiment": str(upstream),
        "run_id": "same-active-EF-run",
        "snapshot_ids": {"orfs": "same-snapshot"},
        "reason": "published_facts_read_unavailable",
    }

    def work(*args):
        raise WorkPending(pending)

    monkeypatch.setattr(validation, "_validate", work)
    with patch(
        "sys.argv",
        [
            "chip-evolve",
            "--config",
            str(config.path),
            "validate",
            "--result",
            str(candidate),
            "--against",
            str(reference),
            "--key",
            folder.name,
        ],
    ):
        assert main() == 3
    result = json.loads(capsys.readouterr().out)
    assert result["experiment"] == str(folder)
    assert result["upstream_experiment"] == str(upstream)
    assert (
        result["run_id"] == pending["run_id"]
        and result["snapshot_ids"] == pending["snapshot_ids"]
    )
    assert read(folder / "status.json")["status"] == "pending"
    assert (upstream / "status.json").read_bytes() == before
    assert pending["experiment"] == str(upstream), (
        "Do not mutate the upstream receipt object"
    )


def test_real_validation_error_remains_failed_and_frozen_request_unchanged(
    tmp_path, monkeypatch
):
    config, reference, candidate, folder = fixture(tmp_path)

    def work(*args):
        raise ValueError("real invalid data")

    monkeypatch.setattr(validation, "_validate", work)
    with pytest.raises(ValueError, match="real invalid data"):
        validation.validate(config, candidate, reference, folder.name)
    assert read(folder / "status.json") == {
        "status": "failed",
        "kind": "validation",
        "error_type": "ValueError",
        "detail": "real invalid data",
    }
    assert read(folder / "validation-request.json")["result_sha256"] == digest(
        candidate
    )


def test_changed_result_is_rejected_without_rewriting_previous_status(
    tmp_path, monkeypatch
):
    config, reference, candidate, folder = fixture(tmp_path)
    monkeypatch.setattr(validation, "_validate", lambda *args: {"passed": True})
    validation.validate(config, candidate, reference, folder.name)
    before = (folder / "status.json").read_bytes()
    candidate.write_text(candidate.read_text() + "\n")
    with pytest.raises(ValueError, match="cannot change"):
        validation.validate(config, candidate, reference, folder.name)
    assert (folder / "status.json").read_bytes() == before
    assert not (folder / "validation-status-history.jsonl").exists()


def test_another_active_validation_owner_is_not_overwritten(tmp_path, monkeypatch):
    config, reference, candidate, folder = fixture(tmp_path)
    monkeypatch.setattr(validation, "_validate", lambda *args: {"passed": True})
    validation.validate(config, candidate, reference, folder.name)
    before = (folder / "status.json").read_bytes()
    with (
        business_lock(folder),
        pytest.raises(RuntimeError, match="active business driver"),
    ):
        validation.validate(config, candidate, reference, folder.name)
    assert (folder / "status.json").read_bytes() == before
    assert not (folder / "validation-status-history.jsonl").exists()
