"""Real subprocess checks for the bounded GoalEvolve reproduction recorder."""

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest
from run_dplevolve_native import session_groups
from run_goalevolve_native import run_step


@pytest.fixture
def native_run(tmp_path: Path) -> Path:
    source = tmp_path / "source"
    source.mkdir()
    (source / "Makefile").write_text("frozen\n")
    subprocess.run(["git", "init", "-q", str(source)], check=True)
    subprocess.run(["git", "add", "Makefile"], cwd=source, check=True)
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
            {
                "source": str(source),
                "environment": {},
                "path_prefixes": [],
                "budget_seconds": 60,
            }
        )
    )
    return run


def test_failure_retained_and_cannot_overwrite(native_run: Path) -> None:
    command = [sys.executable, "-c", "print('failure'); raise SystemExit(7)"]
    receipt = run_step(native_run, "failure", command, timeout=10)
    assert receipt["status"] == "failed" and receipt["exit_code"] == 7
    assert "failure" in (native_run / "steps/failure/output.log").read_text()
    with pytest.raises(FileExistsError):
        run_step(native_run, "failure", command, timeout=10)


def test_control_change_blocks_continuation(native_run: Path) -> None:
    receipt = run_step(
        native_run,
        "mutation",
        [
            sys.executable,
            "-c",
            "from pathlib import Path; Path('Makefile').write_text('changed')",
        ],
        timeout=10,
    )
    assert receipt["status"] == "source_changed"
    assert receipt["source_changed"] == ["Makefile"]
    with pytest.raises(RuntimeError, match="Frozen controls"):
        run_step(native_run, "next", [sys.executable, "-c", "pass"], timeout=10)


def test_total_budget_kills_process_tree(native_run: Path) -> None:
    (native_run / "budget.json").write_text(
        json.dumps(
            {
                "started_epoch": time.time(),
                "seconds": 0.3,
            }
        )
    )
    receipt = run_step(
        native_run, "timeout", ["timeout", "60", "sleep", "60"], timeout=20
    )
    assert receipt["status"] == "budget_exhausted"
    assert session_groups(receipt["session_id"]) == set()
    with pytest.raises(RuntimeError, match="Total reproduction budget"):
        run_step(native_run, "next", ["true"], timeout=10)


def test_config_change_and_missing_executable(native_run: Path) -> None:
    receipt = run_step(native_run, "missing", ["/no/such/executable"], timeout=10)
    assert receipt["status"] == "launch_failed"
    config_path = native_run / "config.json"
    config = json.loads(config_path.read_text())
    config["budget_seconds"] = 100
    config_path.write_text(json.dumps(config))
    with pytest.raises(RuntimeError, match="Frozen controls"):
        run_step(native_run, "next", ["true"], timeout=10)


def test_budget_stops_children_in_separate_native_sessions(native_run: Path) -> None:
    child_record = native_run / "child.pid"
    code = (
        "import subprocess,time; from pathlib import Path; "
        "child=subprocess.Popen(['sleep','60'],start_new_session=True); "
        f"Path({str(child_record)!r}).write_text(str(child.pid)); time.sleep(60)"
    )
    receipt = run_step(
        native_run, "escaped-session", [sys.executable, "-c", code], timeout=0.5
    )
    assert receipt["status"] == "budget_exhausted"
    assert session_groups(int(child_record.read_text())) == set()
