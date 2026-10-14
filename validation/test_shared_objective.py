"""Exercise the actual runner entry, keeping native prompt and artifacts intact."""

import json
from types import SimpleNamespace

import pytest
from scripts.codex_exec import runner


def test_shared_objective_is_saved_before_actual_codex_invocation(
    tmp_path, monkeypatch
):
    from eda_toolkits.objectives import SCHEMA, objective_id

    value = {
        "schema_version": SCHEMA,
        "design_id": "example",
        "reference_run_id": "reference",
        "conditions": {"libraries": [{"sha256": "lib"}], "sdc": {"sha256": "sdc"}},
        "constraints": {"die_area_um2_max": 100},
    }
    value["objective_id"] = objective_id(value)
    path = tmp_path / "objective.json"
    path.write_text(json.dumps(value))
    monkeypatch.setenv("DPL_EVOLVE_PLATFORM_PROFILE", "explicit-platform")
    monkeypatch.setenv("EDA_PLATFORM_OBJECTIVE", str(path))
    args = SimpleNamespace(
        cwd=tmp_path,
        operations_dir=tmp_path / "operations",
        operation_id="turn",
        prompt="original Student prompt",
        prompt_file=None,
        session_state=None,
    )
    monkeypatch.setattr(runner, "parse_args", lambda argv: args)
    monkeypatch.setattr(
        runner,
        "runtime_paths",
        lambda: SimpleNamespace(
            agent_root=tmp_path, orfs_root=tmp_path, state_root=tmp_path
        ),
    )
    monkeypatch.setattr(runner, "default_codex_home", lambda *a: (tmp_path, "test"))
    monkeypatch.setattr(runner, "state_resume_thread_id", lambda *a: (None, "test"))

    def boundary(*args):
        prompt = (tmp_path / "operations/turn/codex_prompt.md").read_text()
        assert prompt.startswith("original Student prompt")
        assert value["objective_id"] in prompt
        raise RuntimeError("verified actual command boundary")

    monkeypatch.setattr(runner, "build_command", boundary)
    with pytest.raises(RuntimeError, match="verified actual command boundary"):
        runner.main([])
