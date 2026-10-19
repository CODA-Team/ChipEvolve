"""Read-only complete native evidence, with quality verdicts kept distinct."""

import hashlib
import json

import pytest

from goalevolve.platform.candidate_evidence import export


def candidate(tmp_path, *, state="refuted", integrity=True, complete=True):
    root = tmp_path / "campaign/rounds/round_001"
    artifacts = root / "students/student_1/artifacts"
    artifacts.mkdir(parents=True)
    if complete:
        (root / "round.json").write_text("{}")
    odb = artifacts / "post_route.odb"
    odb.write_bytes(b"real fixture checkpoint")
    (artifacts / "candidate.json").write_text(
        json.dumps(
            {
                "student_id": "student_1",
                "source_commit": "source-id",
                "legacy": False,
                "evaluation_error": None,
                "hypothesis": {
                    "evaluation_mode": "power_only",
                    "timing_recipe_id": "legacy_setup",
                },
                "checks": [
                    {"name": n, "passed": True}
                    for n in ["build", "flow", "metrics", "lec"]
                ],
                "metrics": {"tns_abs_ns": 1},
                "artifacts": {"checkpoint_post_route_db": str(odb)},
            }
        )
    )
    (artifacts / "evidence.json").write_text(
        json.dumps(
            {
                "state": state,
                "integrity_ok": integrity,
                "reasons": ["power_residual_not_improved:0"],
            }
        )
    )
    return {
        "state_root": str(tmp_path),
        "design_id": "design",
        "design": "design_top",
    }, artifacts


def test_completed_refuted_quality_is_exported_with_original_verdict(tmp_path):
    profile, artifacts = candidate(tmp_path)
    before = {
        p: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in tmp_path.rglob("*")
        if p.is_file()
    }
    result = export(profile)
    row = result["candidates"][0]
    assert row["eligible_for_common_measurement"]
    assert row["native_verdict"]["state"] == "refuted"
    assert row["native_verdict"]["reasons"] == ["power_residual_not_improved:0"]
    assert row["checkpoint"] == str(artifacts / "post_route.odb")
    assert all(
        hashlib.sha256(p.read_bytes()).hexdigest() == sha for p, sha in before.items()
    )


@pytest.mark.parametrize("failure", ["integrity", "missing_checkpoint"])
def test_invalid_or_incomplete_candidate_is_not_measurable(tmp_path, failure):
    profile, artifacts = candidate(tmp_path, integrity=failure != "integrity")
    if failure == "missing_checkpoint":
        (artifacts / "post_route.odb").unlink()
    assert not export(profile)["candidates"][0]["eligible_for_common_measurement"]


def test_active_round_is_rejected_before_any_export(tmp_path):
    profile, _ = candidate(tmp_path, complete=False)
    with pytest.raises(ValueError, match="completed native round"):
        export(profile)


def test_epd_trace_round_zero_does_not_hide_completed_candidates(tmp_path):
    profile, _ = candidate(tmp_path)
    before = export(profile)
    trace = tmp_path / "campaign/rounds/round_000/teacher_epd_retrieval_trace.jsonl"
    trace.parent.mkdir()
    trace.write_text('{"accepted": true}\n')
    assert export(profile) == before
    assert trace.read_text() == '{"accepted": true}\n'


@pytest.mark.parametrize("name", ["round_000", "round_002"])
def test_unfinished_student_work_is_still_rejected(tmp_path, name):
    profile, _ = candidate(tmp_path)
    partial = tmp_path / "campaign/rounds" / name / "students/student_1/artifacts"
    partial.mkdir(parents=True)
    (partial / "candidate.json").write_text("{}")
    with pytest.raises(ValueError, match="completed native round"):
        export(profile)
