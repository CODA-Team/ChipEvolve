"""All completed native candidates survive export without changing promotion."""

import hashlib
import json
from types import SimpleNamespace

from scripts.platform import candidate_evidence as exporting


def test_export_keeps_nonwinning_clean_candidates_and_original_rejections(
    tmp_path, monkeypatch
):
    profile = {
        "case": "case",
        "flow_variant": "trial",
        "agent_root": str(tmp_path),
        "orfs_root": str(tmp_path / "orfs"),
        "state_root": str(tmp_path / "state"),
    }
    runtime = SimpleNamespace(
        agent_root=tmp_path, state_root=tmp_path / "state", orfs_root=tmp_path / "orfs"
    )
    monkeypatch.setattr(exporting, "resolve_runtime_paths", lambda **kwargs: runtime)
    monkeypatch.setattr(
        exporting, "runtime_with_round_outputs", lambda runtime, path: runtime
    )
    monkeypatch.setattr(
        exporting,
        "get_case",
        lambda case: SimpleNamespace(platform="pdk", design="design"),
    )
    candidates = []
    for tag in ["clean-not-promoted", "invalid"]:
        metrics = tmp_path / (tag + ".json")
        metrics.write_text(json.dumps({"hpwl": 3, "status": "ok"}))
        odb = (
            tmp_path
            / "orfs/flow/results/pdk/design/trial/dpl_evolve_baseline"
            / tag
            / "legalized.odb"
        )
        odb.parent.mkdir(parents=True)
        odb.write_bytes(tag.encode())
        candidates.append(SimpleNamespace(tag=tag, metrics_path=metrics))
    monkeypatch.setattr(
        exporting, "discover_round_candidate_metrics", lambda **kwargs: candidates
    )
    monkeypatch.setattr(
        exporting,
        "candidate_artifact_problems",
        lambda **kwargs: (
            []
            if kwargs["candidate"].tag == "clean-not-promoted"
            else ["placement_not_clean"]
        ),
    )
    monkeypatch.setattr(
        exporting,
        "source_repo_ref_for_candidate",
        lambda **kwargs: (tmp_path / "source", "original-source-ref"),
    )
    before = {
        p: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in tmp_path.rglob("*")
        if p.is_file()
    }
    result = exporting.export(profile, "trial")
    assert [row["candidate_id"] for row in result["candidates"]] == [
        c.tag for c in candidates
    ]
    clean, invalid = result["candidates"]
    assert clean["eligible_for_common_measurement"]
    assert clean["source_ref"] == "original-source-ref"
    assert invalid["native_artifact_problems"] == ["placement_not_clean"]
    assert not invalid["eligible_for_common_measurement"]
    assert all(
        hashlib.sha256(p.read_bytes()).hexdigest() == sha for p, sha in before.items()
    )
    assert "promotion" not in result


def test_missing_completed_checkpoint_is_not_a_source_only_candidate(
    tmp_path, monkeypatch
):
    profile = {
        "case": "case",
        "flow_variant": "trial",
        "agent_root": str(tmp_path),
        "orfs_root": str(tmp_path),
        "state_root": str(tmp_path),
    }
    runtime = SimpleNamespace(state_root=tmp_path, orfs_root=tmp_path)
    monkeypatch.setattr(exporting, "resolve_runtime_paths", lambda **kwargs: runtime)
    monkeypatch.setattr(
        exporting, "runtime_with_round_outputs", lambda runtime, path: runtime
    )
    monkeypatch.setattr(
        exporting,
        "get_case",
        lambda case: SimpleNamespace(platform="pdk", design="design"),
    )
    metrics = tmp_path / "metrics.json"
    metrics.write_text("{}")
    monkeypatch.setattr(
        exporting,
        "discover_round_candidate_metrics",
        lambda **kwargs: [SimpleNamespace(tag="source-only", metrics_path=metrics)],
    )
    monkeypatch.setattr(exporting, "candidate_artifact_problems", lambda **kwargs: [])
    monkeypatch.setattr(
        exporting, "source_repo_ref_for_candidate", lambda **kwargs: (tmp_path, "ref")
    )
    row = exporting.export(profile, "trial")["candidates"][0]
    assert not row["eligible_for_common_measurement"]
    assert "missing_completed_checkpoint" in row["native_artifact_problems"]
