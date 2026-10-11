"""Native verification must not replay successful work or mask source changes."""

import json
import subprocess
import sys
from pathlib import Path

import pytest
from run_dplevolve_native import run_step, session_groups


@pytest.fixture
def native_run(tmp_path: Path) -> Path:
    source = tmp_path / "source"
    source.mkdir()
    (source / "tracked.txt").write_text("frozen\n")
    subprocess.run(["git", "init", "-q", str(source)], check=True)
    subprocess.run(["git", "add", "tracked.txt"], cwd=source, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "-qm",
            "freeze",
        ],
        cwd=source,
        check=True,
    )
    run = tmp_path / "run"
    run.mkdir()
    (run / "config.json").write_text(
        json.dumps(
            {"environment": {"DPL_EVOLVE_AGENT_ROOT": str(source)}, "path_prefixes": []}
        )
    )
    return run


def test_preserves_failed_commands_and_prevents_replay(native_run: Path) -> None:
    command = [sys.executable, "-c", "print('real failure'); raise SystemExit(7)"]
    receipt = run_step(native_run, "failure", command, timeout=10)
    assert receipt["status"] == "failed"
    assert receipt["exit_code"] == 7
    assert "real failure" in (native_run / "steps/failure/output.log").read_text()
    with pytest.raises(FileExistsError):
        run_step(native_run, "failure", command, timeout=10)


def test_source_changes_never_count_as_success(native_run: Path) -> None:
    command = [
        sys.executable,
        "-c",
        "from pathlib import Path; Path('tracked.txt').write_text('changed')",
    ]
    receipt = run_step(native_run, "mutation", command, timeout=10)
    assert receipt["status"] == "source_changed"
    assert receipt["source_changed"] == ["tracked.txt"]
    with pytest.raises(RuntimeError, match="Frozen control source changed"):
        run_step(native_run, "another", [sys.executable, "-c", "pass"], timeout=10)


def test_budget_stops_timeout_child_process_groups(native_run: Path) -> None:
    receipt = run_step(
        native_run, "timeout", ["timeout", "60", "sleep", "60"], timeout=0.25
    )
    assert receipt["status"] == "budget_exhausted"
    assert session_groups(receipt["session_id"]) == set()
