"""Handoff and role identities belong to actual inputs, not Query prose."""

from admin.test_adoption_consistency import frame_at
from admin.test_local_business import deployment
from chip_evolve.config import read, write
from chip_evolve.diagnosis import identity_bindings
from chip_evolve.handoff import input_contract
from chip_evolve.jobs import digest


def test_handoff_records_native_transformations_and_actual_source_bytes(tmp_path):
    source = frame_at(tmp_path, "reference")
    frame = read(source)
    for capability, meaning in [
        ("dpl", "pre-CTS"),
        ("goal", "remove fillers"),
        ("eco", "local primitives"),
    ]:
        contract = input_contract(frame, capability)
        assert meaning in contract["transformations"]
        assert contract["source_run_id"] == frame["run_id"]
        assert contract["source_files"]["v"]["sha256"] == digest(
            tmp_path / "reference/design.v"
        )
        assert contract["objective_id"] == frame["objective_id"]


def test_roles_use_explicit_reference_and_verified_retained_record(tmp_path):
    d = deployment(tmp_path)
    reference = read(frame_at(tmp_path, "reference"))
    candidate = read(frame_at(tmp_path, "candidate", 0.9))
    roles = identity_bindings(d, candidate, reference)
    assert roles["reference"]["run_id"] == "reference"
    assert roles["source"]["run_id"] == "candidate"
    assert roles["retained"] is None
    write(
        tmp_path / "designs/gcd/incumbent.json",
        {
            "run_id": "actual-goal",
            "result": str(tmp_path / "candidate/result.json"),
            "result_sha256": digest(tmp_path / "candidate/result.json"),
            "objective_id": candidate["objective_id"],
            "condition_id": candidate["condition_id"],
        },
    )
    roles = identity_bindings(d, candidate, reference)
    assert roles["retained"]["run_id"] == "actual-goal"
    assert roles["reference"]["run_id"] != roles["retained"]["run_id"]
