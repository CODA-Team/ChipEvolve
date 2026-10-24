"""The shared check entrypoint uses Flow's native module working directory."""

import runpy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest


@pytest.mark.parametrize("project", ["flow-agent", "query-agent"])
def test_check_uses_project_native_import_directory(project, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.setattr("sys.argv", ["dev.py", project, "check"])
    with patch("subprocess.run", return_value=SimpleNamespace(returncode=0)) as run:
        runpy.run_path(str(root / "dev.py"), run_name="__main__")
    calls = run.call_args_list
    expected = root / project / "flow" if project == "flow-agent" else root / project
    assert all(call.kwargs["cwd"] == expected for call in calls)
    tests = calls[-1].args[0]
    assert tests[:3] == [str(root / project / ".venv/bin/python"), "-m", "pytest"]
    if project == "flow-agent":
        assert tests[3:] == ["test"]
    assert all("PYTHONPATH" not in call.kwargs["env"] for call in calls)
