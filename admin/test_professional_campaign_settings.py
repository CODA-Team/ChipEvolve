"""A native campaign shares its deadline and records explicit model choices."""

import os
from argparse import Namespace
from pathlib import Path
from typing import cast

import pytest
from openroad_platform_client import KernelClient

from chip_evolve import professional
from chip_evolve.config import read
from chip_evolve.jobs import Jobs


def test_native_phases_share_deadline_without_starting_work_after_expiry(
    tmp_path, monkeypatch
):
    current = [1000.0]
    calls = []

    class Process:
        def wait(self, timeout):
            calls.append(timeout)
            return 0

    monkeypatch.setattr(professional.time, "time", lambda: current[0])
    monkeypatch.setattr(professional.subprocess, "Popen", lambda *a, **kw: Process())
    env = {**os.environ, "EDA_PLATFORM_DEADLINE_EPOCH": "1100"}
    for index, now in enumerate((1000.0, 1075.0)):
        current[0] = now
        folder = tmp_path / str(index)
        folder.mkdir()
        professional.invoke(["native"], tmp_path, env, folder, 100)
    current[0] = 1101.0
    expired = tmp_path / "expired"
    expired.mkdir()
    with pytest.raises(professional.subprocess.TimeoutExpired):
        professional.invoke(["native"], tmp_path, env, expired, 100)
    assert calls == [100.0, 25.0]
    assert not (expired / "controller.log").exists()


def test_explicit_dpl_models_reach_original_teacher_student_cli():
    binding = {
        "model": "base-model",
        "reasoning_effort": "high",
        "teacher_model": "teacher-model",
        "teacher_reasoning_effort": "xhigh",
        "student_model": "student-model",
        "student_reasoning_effort": "medium",
    }
    args = Namespace(rounds=2, candidates=3)
    command = professional.dpl_search_command(
        binding, "/client/python", Path("/native"), args, "case", "run-key"
    )
    for name, value in binding.items():
        flag = "--" + name.replace("_", "-")
        assert command[command.index(flag) + 1] == value
    assert command[command.index("--children") + 1] == "3"
    assert command[command.index("--iterations") + 1] == "2"
    assert command[command.index("--max-parallel") + 1] == "2"
    assert "--reuse-baseline-preflight" in command and "--launch" in command


def test_unspecified_dpl_model_settings_preserve_original_cli_defaults():
    command = professional.dpl_search_command(
        {},
        "/client/python",
        Path("/native"),
        Namespace(rounds=1, candidates=3),
        "case",
        "run-key",
    )
    assert not any("model" in word or "reasoning" in word for word in command)


def test_timeout_cancellation_is_scoped_and_collects_before_mutating_pages(tmp_path):
    from types import SimpleNamespace

    jobs = object.__new__(Jobs)
    jobs.design_id, jobs.campaign, jobs.experiment = "jpeg", "jpeg-owned", tmp_path
    cancelled, reads = [], []

    def runs(**filters):
        assert not cancelled, "All pages must be read before cancellation"
        reads.append(filters)
        if filters["status"] != "queued":
            return []
        if filters["offset"] == 0:
            return [
                {"run_id": "own-1", "experiment_id": "jpeg-owned"},
                {"run_id": "other", "experiment_id": "jpeg-other"},
            ]
        if filters["offset"] == 2:
            return [{"run_id": "own-2", "experiment_id": "jpeg-owned"}]
        return []

    def cancel(run_id):
        cancelled.append(run_id)
        return {"status": "cancel_requested"}

    jobs.client = cast(KernelClient, SimpleNamespace(runs=runs, cancel=cancel))
    receipt = jobs.cancel_active()
    assert cancelled == ["own-1", "own-2"]
    assert all(r["design_id"] == "jpeg" for r in reads)
    assert not any(r["status"] == "succeeded" for r in reads)
    assert read(tmp_path / "native-job-cancellation.json") == receipt


@pytest.mark.parametrize("capability", ["dpl", "goal"])
def test_dispatcher_cancels_owned_jobs_and_preserves_native_timeout(
    tmp_path, monkeypatch, capability
):
    from admin.test_query_objective_handoff import inputs

    deployment, source, _ = inputs(tmp_path)
    frame = read(source)
    context = tmp_path / "context.json"
    context.write_text("{}")
    packet = {
        "confirmed_facts": ["fact"],
        "evidence": ["ref"],
        "context_id": "context",
        "scope": {"design_id": "gcd", "run_id": frame["run_id"]},
    }
    monkeypatch.setattr(professional, "load_context", lambda _: packet)
    monkeypatch.setattr("chip_evolve.design_facts.ensure", lambda *a: frame)
    monkeypatch.setattr("chip_evolve.handoff.input_contract", lambda *a: {})
    original = professional.subprocess.TimeoutExpired("native", 60)

    def timeout(*args):
        raise original

    target = (
        "chip_evolve.professional.run_dpl"
        if capability == "dpl"
        else "chip_evolve.native.run_goal"
    )
    monkeypatch.setattr(target, timeout)
    cancelled = []
    monkeypatch.setattr(
        Jobs, "cancel_active", lambda self: cancelled.append(self.campaign)
    )
    args = Namespace(
        source=source,
        design="gcd",
        objective=None,
        context=context,
        capability=capability,
        seconds=60,
        rounds=1,
        candidates=3,
        operation="evolve",
    )
    experiment = deployment.experiment("gcd", "owned-timeout")
    with pytest.raises(professional.subprocess.TimeoutExpired) as caught:
        professional.execute(deployment, args, experiment)
    assert caught.value is original
    assert cancelled == ["gcd-owned-timeout"]
