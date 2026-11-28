"""Intentional profile/budget/capacity errors for the supplemental typing gate."""

from chip_evolve.core.config import Deployment
from chip_evolve.core.resources import (
    CapacitySnapshot,
    TaskBudget,
    require_capacity,
    resolve_budget,
)
from chip_evolve.core.toolchain import load_runtime_profile


def incorrect_profile() -> None:
    load_runtime_profile("untyped deployment")


def incorrect_budget() -> None:
    resolve_budget("orfs", memory_gib="64 GiB")


def incorrect_capacity(deployment: Deployment, budget: TaskBudget) -> None:
    require_capacity(budget, {"budget_cpu_cores": 8})


def incorrect_snapshot() -> CapacitySnapshot:
    return {"budget_cpu_cores": 8}
