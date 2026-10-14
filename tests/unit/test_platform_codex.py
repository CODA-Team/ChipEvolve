"""Opt-in login and common-source routing; native API isolation remains explicit."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest
from goalevolve.agents.codex_runtime import CodexRuntimeConfig, PersistentCodexRunner
from goalevolve.planning.repository_graph import RepositoryGraphIndex
from goalevolve.platform.profile import (
    existing_codex,
    load_platform_profile,
    source_seed,
)


def test_native_has_no_platform_dependency(monkeypatch):
    monkeypatch.delenv("GOALEVOLVE_PLATFORM_PROFILE", raising=False)
    assert load_platform_profile() is None
    assert existing_codex() is None
    assert source_seed(Path("native")) == Path("native")


def profile(tmp_path, monkeypatch, **overrides):
    home = tmp_path / "existing"
    home.mkdir()
    (home / "auth.json").write_text('"sentinel-auth"')
    (home / "config.toml").write_text("# sentinel existing configuration\n")
    value = {
        "source_seed": str(tmp_path / "common/source"),
        "codex": {"auth_mode": "existing_codex", "home": str(home)},
        **overrides,
    }
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(value))
    monkeypatch.setenv("GOALEVOLVE_PLATFORM_PROFILE", str(path))
    return value, home


@pytest.mark.parametrize("identity", ["teacher", "student_1", "narrator"])
def test_existing_home_preserves_auth_and_host_home(tmp_path, monkeypatch, identity):
    _, home = profile(tmp_path, monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "inherited-do-not-use")
    before = {p.name: p.read_bytes() for p in home.iterdir()}
    runner = PersistentCodexRunner(CodexRuntimeConfig())
    with patch.object(
        runner,
        "_project_credentials",
        side_effect=AssertionError("must not use API credentials"),
    ):
        assert runner._ensure_home(tmp_path, identity) == home
        env = runner._environment(home=home, cwd=tmp_path / "workspace")
    assert env["CODEX_HOME"] == str(home)
    assert env["HOME"] == os.environ["HOME"]
    assert "OPENAI_API_KEY" not in env
    assert before == {p.name: p.read_bytes() for p in home.iterdir()}


def test_project_api_does_not_inherit_personal_login(tmp_path, monkeypatch):
    profile(tmp_path, monkeypatch, codex={"auth_mode": "project_api"})
    assert existing_codex() is None
    runner = PersistentCodexRunner(
        CodexRuntimeConfig(credential_env=tmp_path / "absent.env")
    )
    with pytest.raises(FileNotFoundError, match="credential"):
        runner._ensure_home(tmp_path, "teacher")


def test_explicit_source_routes_ast_to_matching_cache(tmp_path, monkeypatch):
    value, _ = profile(tmp_path, monkeypatch)
    seed = Path(value["source_seed"])
    assert source_seed(Path("native")) == seed
    graph = RepositoryGraphIndex(state_root=tmp_path / "campaign")
    assert graph.p0_source_root == seed
    assert graph.p0_artifact_root == seed.parent / "repository_graph"


def test_invalid_profile_fails_closed(tmp_path, monkeypatch):
    profile(tmp_path, monkeypatch, codex={"auth_mode": "automatic"})
    with pytest.raises(ValueError, match="authentication"):
        existing_codex()


def test_version_query_uses_ef_in_platform_mode(tmp_path, monkeypatch):
    from goalevolve.execution.execution import ExecutionReport
    from goalevolve.platform.execution import toolchain_evidence

    value, _ = profile(
        tmp_path,
        monkeypatch,
        state_root=str(tmp_path),
        toolchain={"image_sha256": "frozen"},
        cmake_args=[],
    )
    seed = Path(value["source_seed"])
    binary = seed / "build/bin/openroad"
    binary.parent.mkdir(parents=True)
    binary.write_bytes(b"binary")
    with (
        patch(
            "goalevolve.execution.execution.ResilientCommandRunner.run",
            return_value=ExecutionReport(True, 1, 0, "common-version", ""),
        ) as run,
        patch("subprocess.run") as git,
    ):
        git.return_value.returncode = 0
        git.return_value.stdout = "common-source-commit\n"
        result = toolchain_evidence(seed)
    assert result["openroad_version"] == "common-version"
    assert result["source_git_commit"] == "common-source-commit"
    assert run.call_args.kwargs["command"] == [str(binary), "-version"]


def test_shared_objective_reaches_real_turn_boundary_and_session_identity(
    tmp_path, monkeypatch
):
    import json
    import subprocess

    from eda_toolkits.objectives import SCHEMA, objective_id

    profile(tmp_path, monkeypatch)
    value = {
        "schema_version": SCHEMA,
        "design_id": "example",
        "reference_run_id": "reference",
        "conditions": {"libraries": [{"sha256": "lib"}], "sdc": {"sha256": "sdc"}},
        "constraints": {"power_total_w_max": 0.01},
    }
    value["objective_id"] = objective_id(value)
    objective = tmp_path / "objective.json"
    objective.write_text(json.dumps(value))
    monkeypatch.setenv("EDA_PLATFORM_OBJECTIVE", str(objective))
    import hashlib

    packet = {
        "schema_version": "chip-evolve.design-context.v1",
        "scope": {"design_id": "example"},
        "summary": "supported diagnosis from current design",
    }
    packet["context_id"] = hashlib.sha256(
        json.dumps(packet, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    context = tmp_path / "context.json"
    context.write_text(json.dumps(packet))
    monkeypatch.setenv("EDA_PLATFORM_CONTEXT", str(context))
    runner = PersistentCodexRunner(CodexRuntimeConfig(retries=1))

    def invoke(**kwargs):
        assert kwargs["prompt"].startswith("native Teacher/Student prompt")
        assert value["objective_id"] in kwargs["prompt"]
        assert packet["summary"] in kwargs["prompt"]
        kwargs["events"].write_text(
            '{"type":"thread.started","thread_id":"thread"}\n{"type":"turn.completed","usage":{}}\n'
        )
        kwargs["stderr"].write_text("")
        return subprocess.CompletedProcess([], 0)

    with patch.object(runner, "_invoke", side_effect=invoke):
        result = runner.run(
            state_root=tmp_path,
            identity="teacher",
            operation_id="round_01",
            cwd=tmp_path,
            artifact_root=tmp_path / "turn",
            prompt="native Teacher/Student prompt",
        )
    assert result.ok
    saved = json.loads((tmp_path / "codex_sessions/teacher.json").read_text())
    assert saved["runtime"]["objective_id"] == value["objective_id"]
    assert saved["runtime"]["context_id"] == packet["context_id"]
    assert value["objective_id"] in (tmp_path / "turn/prompt.md").read_text()
