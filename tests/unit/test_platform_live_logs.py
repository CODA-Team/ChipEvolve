"""The EF bridge forwards live native output without changing original files."""

import sys
import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from goalevolve.platform.execution import leaf


def request(tmp_path: Path, body: str):
    return {
        "command": [sys.executable, "-c", body],
        "operation": "analysis",
        "cwd": str(tmp_path),
        "receipt_root": str(tmp_path),
        "environment": {},
        "policy": {"timeout_s": 3},
        "output_log": str(tmp_path / "native.log"),
        "build": None,
    }


def test_native_stdout_visible_before_operation_finishes(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    results = []
    release = tmp_path / "release-native"
    value = request(
        tmp_path,
        'import time;from pathlib import Path;print("native phase entered",flush=True)\n'
        'while not Path("release-native").exists(): time.sleep(0.01)',
    )

    def run():
        results.append(leaf({"agent_python": sys.executable}, value))

    with patch("goalevolve.platform.execution.validate_request"):
        thread = threading.Thread(target=run)
        thread.start()
        deadline = time.monotonic() + 2
        visible = ""
        try:
            while time.monotonic() < deadline:
                visible += capsys.readouterr().out
                if "native phase entered" in visible:
                    break
                time.sleep(0.01)
            was_live = thread.is_alive()
        finally:
            release.touch()
            thread.join(timeout=5)
    assert not thread.is_alive()
    assert "native phase entered" in visible and was_live
    assert results == [0]


@pytest.mark.parametrize("code", [0, 7])
def test_live_forwarding_preserves_exact_separate_streams_and_native_result(
    tmp_path, monkeypatch, capsys, code
):
    monkeypatch.chdir(tmp_path)
    value = request(
        tmp_path,
        'import sys;print("native stdout",flush=True);print("native stderr",file=sys.stderr,flush=True);raise SystemExit('
        + str(code)
        + ")",
    )
    with patch("goalevolve.platform.execution.validate_request"):
        assert leaf({"agent_python": sys.executable}, value) == code
    assert (tmp_path / "stdout.log").read_bytes() == b"native stdout\n"
    assert (tmp_path / "stderr.log").read_bytes() == b"native stderr\n"
    assert (tmp_path / "native.log").read_bytes() == b"native stdout\nnative stderr\n"
    visible = capsys.readouterr().out
    assert "native stdout" in visible and "native stderr" in visible
