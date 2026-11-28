"""Capacity evidence and submission/recovery are independent from EF queuing."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from chip_evolve.core import jobs, resources
from chip_evolve.core.config import write
from chip_evolve.core.contracts import BusinessInputError
from tests.test_runtime_profile import bound_profile as bound_profile


class Kernel:
    def __init__(self, *, rows=None, cpu=8, memory=64 << 30):
        self.rows = rows if rows is not None else [{"run_id": "run-existing"}]
        self.cpu, self.memory = cpu, memory
        self.submits = 0

    def health(self):
        return {
            "service": "kernel",
            "status": "ok",
            "workers": [{"worker_id": "unit", "state": "idle"}],
        }

    def runs(self, **kwargs):
        return self.rows if kwargs.get("offset", 0) == 0 else []

    def resources(self, run_id):
        return {
            "run": run_id,
            "capacity": {
                "budget_cpu_cores": self.cpu,
                "budget_memory_bytes": self.memory,
            },
            "reserved": {"cpu_cores": self.cpu, "memory_bytes": self.memory},
        }

    def submit(self, *args, **kwargs):
        self.submits += 1
        pytest.fail("This test must not submit an EF task")


def test_public_busy_capacity_uses_total_budget_without_probe():
    kernel = Kernel()
    deployment = SimpleNamespace(value={"kernel_url": "https://ef.example.invalid"})
    capacity = resources.read_capacity(deployment, kernel)
    resources.require_capacity(resources.resolve_budget("code-build"), capacity)
    assert capacity.source == "public_resources"
    assert kernel.submits == 0


def test_empty_remote_capacity_is_unknown_and_never_probed():
    kernel = Kernel(rows=[])
    deployment = SimpleNamespace(value={"kernel_url": "https://ef.example.invalid"})
    with pytest.raises(BusinessInputError, match="capacity_unverified"):
        resources.read_capacity(deployment, kernel)
    assert kernel.submits == 0


def job_fixture(bound_profile, monkeypatch, tmp_path):
    deployment, _, _ = bound_profile
    deployment.state = tmp_path
    deployment.value.update(kernel_url="http://unit", client_python="/unit/python")
    kernel = Kernel(cpu=4, memory=8 << 30)
    monkeypatch.setattr(jobs, "KernelClient", lambda *a, **kw: kernel)
    return jobs.Jobs(deployment, "gcd", tmp_path / "experiments/gcd/unit"), kernel


@pytest.mark.parametrize("cpu,memory", [(8, 4), (4, 16)])
def test_jobs_refuse_over_capacity_before_ef_submit(
    bound_profile, monkeypatch, tmp_path, cpu, memory
):
    owner, kernel = job_fixture(bound_profile, monkeypatch, tmp_path)
    with pytest.raises(BusinessInputError, match="capacity_exceeded"):
        owner.submit("unit", {"adapter": "command"}, [], cpu=cpu, memory_gib=memory)
    assert kernel.submits == 0
    assert not (owner.experiment / "jobs/unit/submission.json").exists()


@pytest.mark.parametrize("unknown_response", [False, True])
def test_existing_run_recovery_skips_new_admission_and_never_resubmits(
    bound_profile, monkeypatch, tmp_path, unknown_response
):
    owner, kernel = job_fixture(bound_profile, monkeypatch, tmp_path)
    with pytest.raises(BusinessInputError, match="capacity_exceeded"):
        owner.submit("unit", {"adapter": "command"}, [], cpu=8, memory_gib=24)
    folder = owner.experiment / "jobs/unit"
    row = {
        "run_id": "run-original",
        "task_id": owner.campaign + "-unit",
        "experiment_id": owner.campaign,
        "status": "succeeded",
    }
    if unknown_response:
        write(folder / "lifecycle.json", {"status": "pending"})
        kernel.rows = [row]
    else:
        write(folder / "submission.json", {"run": row})
    monkeypatch.setattr(
        jobs,
        "admit_task",
        lambda *a: pytest.fail("existing run must not be readmitted"),
    )
    expected = {"run": row, "artifacts": []}
    monkeypatch.setattr(jobs, "wait_run", lambda *a: expected)
    actual = owner.submit("unit", {"adapter": "command"}, [], cpu=8, memory_gib=24)
    assert actual == expected
    assert actual["run"]["run_id"] == "run-original"
    assert kernel.submits == 0


def test_dpl_effective_threads_are_admitted_before_frontend():
    profile = {
        "resources": {
            name: {"cpu_cores": 8, "memory_bytes": 64 << 30, "processes": 2048}
            for name in ["build", "variant_build", "physical"]
        }
    }
    budgets = resources.native_budgets("dpl", profile, 300, threads=12)
    assert all(b.limits.cpu_cores == 12 for b in budgets)
    capacity = resources.CapacitySnapshot(
        "http://unit", 8, 128 << 30, "public_resources", None, "unit"
    )
    with pytest.raises(BusinessInputError, match="capacity_exceeded"):
        for budget in budgets:
            resources.require_capacity(budget, capacity)


def test_goal_unqualified_variant_refused_and_flow_stage_overrides_checked():
    profile = {
        "resources": {
            name: {"cpu_cores": 8, "memory_bytes": 64 << 30, "processes": 2048}
            for name in ["build", "variant_build", "physical", "analysis"]
        }
    }
    profile["resources"]["variant_build"]["memory_bytes"] = 24 << 30
    with pytest.raises(BusinessInputError, match="unqualified_build_budget"):
        resources.native_budgets("goal", profile, 300)
    flow = {
        "threads": 4,
        "stage_timeout_seconds": 180,
        "resources": {"memory_bytes": 4 << 30, "processes": 2048},
        "stage_resources": {"route": {"memory_bytes": 16 << 30}},
    }
    budgets = resources.native_budgets("flow", flow, 300)
    assert len(budgets) == 2
    capacity = resources.CapacitySnapshot(
        "http://unit", 4, 8 << 30, "public_resources", None, "unit"
    )
    resources.require_capacity(budgets[0], capacity)
    with pytest.raises(BusinessInputError, match="capacity_exceeded"):
        resources.require_capacity(budgets[1], capacity)


def test_explicit_budget_conflict_does_not_submit(bound_profile, monkeypatch, tmp_path):
    owner, kernel = job_fixture(bound_profile, monkeypatch, tmp_path)
    with pytest.raises(ValueError, match="conflicts"):
        owner.submit(
            "unit",
            {"adapter": "command"},
            [],
            budget=resources.resolve_budget("orfs"),
            cpu=2,
        )
    assert kernel.submits == 0


def test_owned_receipt_separates_business_instance_and_execution_root(
    bound_profile, monkeypatch, tmp_path
):
    deployment, _, _ = bound_profile
    deployment.state = tmp_path
    deployment.value.update(
        kernel_url="http://127.0.0.1:19770",
        capacity_receipt=str(tmp_path / "capacity-receipt.json"),
    )
    command = [
        "/owned/python",
        "-I",
        "-m",
        "openroad_platform_gateway",
        "--port",
        "19770",
        "--state-root",
        str(tmp_path / "execution"),
        "--capacity-cpu-cores",
        "4",
        "--capacity-memory-bytes",
        str(12 << 30),
        "--platform-fraction",
        "1.0",
    ]
    record = {"pid": 12345, "birth": "unit-birth", "command": command}
    health = {
        "service": "kernel",
        "status": "ok",
        "workers": [{"worker_id": "unit", "pid": 12345, "state": "idle"}],
    }
    monkeypatch.setattr(
        resources, "process_identity", lambda pid: ("unit-birth", command)
    )
    monkeypatch.setattr(
        resources, "worker_is_owned", lambda pid, owner: pid == owner == 12345
    )
    installed = tmp_path / "installed-ef.py"
    installed.write_text("# synthetic wheel code\n")
    from chip_evolve.core.toolchain import file_ref, ref_payload

    monkeypatch.setattr(
        resources,
        "installed_identity",
        lambda python, name: {
            "distribution": name,
            "version": "unit",
            "files": [ref_payload(file_ref(installed))],
        },
    )
    resources.startup_receipt(
        tmp_path,
        {
            "state_root": str(tmp_path),
            "cpu_cores": 4,
            "memory_gib": 12,
            "kernel_port": 19770,
        },
        record,
        health,
    )
    capacity = resources.owned_capacity(deployment, health)
    assert capacity.budget_cpu_cores == 4 and capacity.budget_memory_bytes == 12 << 30
    import json

    path = tmp_path / "capacity-receipt.json"
    wire = json.loads(path.read_text())
    assert wire["instance_root"] == str(tmp_path) and wire["state_root"] == str(
        tmp_path / "execution"
    )
    wire["state_root"] = str(tmp_path)
    write(path, wire)
    with pytest.raises(BusinessInputError, match="port or state root differs"):
        resources.owned_capacity(deployment, health)
