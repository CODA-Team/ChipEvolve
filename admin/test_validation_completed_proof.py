"""A completed EF proof survives interrupted physical/fact delivery."""

from unittest.mock import Mock

import pytest

from admin.test_adoption_consistency import frame_at
from admin.test_local_business import deployment
from chip_evolve import validation
from chip_evolve.config import read, write
from chip_evolve.jobs import digest
from chip_evolve.lifecycle import WorkPending


@pytest.fixture
def completed(tmp_path, monkeypatch):
    config = deployment(tmp_path)
    reference = frame_at(tmp_path, "reference")
    candidate = frame_at(tmp_path, "candidate", 0.9)
    lib = tmp_path / "fixed.lib"
    lib.write_text("fixed Liberty model")
    config.value["designs"]["gcd"]["libraries"] = [
        {"path": str(lib), "sha256": digest(lib)}
    ]
    folder = config.state / "experiments/gcd/validation"
    proof = {
        "engine": "eqy",
        "strategy": "abc-pdr",
        "run_id": "original-successful-proof",
        "reference_result": str(reference),
        "candidate_result": str(candidate),
        "proven_points": 1,
        "top_output_bits": 1,
        "unproven_points": 0,
        "input_hashes": {
            read(reference)["files"]["v"]: digest(reference.parent / "design.v"),
            str(lib): digest(lib),
        },
    }
    client = Mock()
    client.run.return_value = {"status": "succeeded"}
    monkeypatch.setattr(validation, "Jobs", lambda *args: Mock(client=client))
    write(
        folder / "validation-request.json",
        {
            "result": str(candidate),
            "reference": str(reference),
            "result_sha256": digest(candidate),
            "reference_sha256": digest(reference),
        },
    )
    write(folder / "logic/logical-equivalence.json", proof)
    return config, reference, candidate, folder, proof, client


def test_completed_proof_preserves_original_producer_without_new_proof(
    completed, monkeypatch
):
    config, reference, candidate, folder, proof, client = completed
    generate = Mock(side_effect=AssertionError("must not rerun proof"))
    monkeypatch.setattr(validation, "verify_outputs", generate)
    assert (
        validation.completed_proof(config, reference, candidate, folder / "logic")
        == proof
    )
    client.run.assert_called_once_with("original-successful-proof")
    generate.assert_not_called()


@pytest.mark.parametrize(
    "field,value,message",
    [
        ("candidate_result", "/another/result.json", "different result pair"),
        ("unproven_points", 1, "all output obligations"),
        ("proven_points", 0, "all output obligations"),
        ("top_output_bits", 2, "all output obligations"),
        ("strategy", "sat", "Legacy EQY SAT"),
    ],
)
def test_incomplete_or_misbound_proof_is_not_resumed(completed, field, value, message):
    config, reference, candidate, folder, proof, _ = completed
    proof[field] = value
    write(folder / "logic/logical-equivalence.json", proof)
    with pytest.raises(ValueError, match=message):
        validation.completed_proof(config, reference, candidate, folder / "logic")


def test_success_receipt_does_not_hide_failed_EF_registration(completed):
    config, reference, candidate, folder, _, client = completed
    client.run.return_value = {"status": "failed"}
    with pytest.raises(ValueError, match="successful EF"):
        validation.completed_proof(config, reference, candidate, folder / "logic")


def test_missing_or_changed_models_reject_proof_reuse(completed):
    config, reference, candidate, folder, proof, _ = completed
    lib = config.design("gcd")["libraries"][0]
    del proof["input_hashes"][lib["path"]]
    write(folder / "logic/logical-equivalence.json", proof)
    with pytest.raises(ValueError, match="lacks frozen"):
        validation.completed_proof(config, reference, candidate, folder / "logic")
    proof["input_hashes"][lib["path"]] = lib["sha256"]
    write(folder / "logic/logical-equivalence.json", proof)
    from pathlib import Path

    Path(lib["path"]).write_text("changed model")
    with pytest.raises(ValueError, match="input changed"):
        validation.completed_proof(config, reference, candidate, folder / "logic")


def test_validation_resume_after_replay_pending_reuses_completed_proof(
    completed, monkeypatch
):
    config, reference, candidate, folder, proof, _ = completed
    monkeypatch.setattr("chip_evolve.design_facts.ensure", lambda d, p, f: f)
    monkeypatch.setattr(validation, "query_facts", lambda *args: {"verified": True})
    monkeypatch.setattr(
        validation,
        "compare",
        lambda *args: {"deltas": {"power": {"delta": 0}}, "constraint_violations": []},
    )
    generate = Mock(side_effect=AssertionError("must not rerun proof"))
    monkeypatch.setattr(validation, "verify_outputs", generate)
    replay = Mock(
        side_effect=[
            WorkPending({"status": "pending", "reason": "replay_running"}),
            read(candidate),
        ]
    )
    monkeypatch.setattr(validation, "replay", replay)
    with pytest.raises(WorkPending):
        validation.validate(config, candidate, reference, folder.name)
    assert read(folder / "status.json")["status"] == "pending"
    receipt = validation.validate(config, candidate, reference, folder.name)
    assert receipt["passed"] and receipt["logic"] == proof
    generate.assert_not_called()
    assert read(folder / "status.json")["status"] == "succeeded"
