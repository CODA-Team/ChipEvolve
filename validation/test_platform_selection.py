"""Completed native round evidence must not be mistaken for absent evidence."""

import json
import subprocess
import sys
from types import SimpleNamespace

from runtime_paths import RuntimePaths
from scripts.platform import selection
from scripts.teacher_loop import evidence


def test_selection_reads_actual_round_operations_and_keeps_native_gates(
    tmp_path, monkeypatch
):
    state = tmp_path / "state"
    root = state / "round/teacher_rounds/students/student_01"
    artifacts = root / "iter_01/artifacts"
    artifacts.mkdir(parents=True)
    repo = root / "workspace/variant/dpl_evolve"
    repo.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    (repo / "candidate.cc").write_text("measured source")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "-qm",
            "candidate",
        ],
        check=True,
    )
    (artifacts / "source_commit.json").write_text(json.dumps({"source_commit": "HEAD"}))
    (artifacts / "implementation.diff").write_text("actual source delta")
    binary = root / "workspace/variant/install/OpenROAD/bin/openroad"
    binary.parent.mkdir(parents=True)
    binary.touch()
    metrics = tmp_path / "metrics.json"
    metrics.write_text("{}")
    candidate = SimpleNamespace(
        tag="round_iter_01_student_01_gcd_asap7",
        violations="",
        hpwl_after=9.0,
        runtime_seconds=1.0,
        metrics_path=metrics,
    )
    baseline = SimpleNamespace(violations="", hpwl_after=10.0, runtime_seconds=1.0)
    monkeypatch.setattr(
        selection,
        "resolve_runtime_paths",
        lambda **_: RuntimePaths(tmp_path / "orfs", tmp_path / "agent", state),
    )
    monkeypatch.setattr(
        selection, "discover_case_metrics", lambda **_: {"openroad_dpl_flow": baseline}
    )
    monkeypatch.setattr(
        evidence, "discover_round_candidate_metrics", lambda **_: [candidate]
    )
    output = tmp_path / "choice.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "selection",
            "--case",
            "gcd_asap7",
            "--flow-variant",
            "variant",
            "--round-id",
            "round",
            "--output",
            str(output),
        ],
    )
    operation = state / "round/checkpoints/operations/round_iter_01_student_01"
    operation.mkdir(parents=True)
    usage = operation / "codex_usage_summary.json"
    usage.write_text(
        json.dumps(
            {
                "returncode": 0,
                "agent_message_count": 1,
                "last_agent_message": "completed native candidate",
            }
        )
    )
    assert not (state / "checkpoints/operations").exists()
    selection.main()
    receipt = json.loads(output.read_text())
    assert receipt["accepted"] and receipt["candidate"] == candidate.tag
    assert receipt["source_repo"] == str(repo)
    candidate.hpwl_after = 11.0
    selection.main()
    assert not json.loads(output.read_text())["accepted"]
    candidate.hpwl_after = 9.0
    usage.unlink()
    selection.main()
    assert not json.loads(output.read_text())["accepted"]
