"""Compatibility exports for the public Goal/ECO names; use their owners."""

from chip_evolve.workflow.eco import run_eco as run_eco
from chip_evolve.workflow.goal import (
    goal_checkpoint_origin as goal_checkpoint_origin,
    goal_producer as goal_producer,
    latest_producer as latest_producer,
    restore_goal_checkpoint as restore_goal_checkpoint,
    run_goal as run_goal,
)

__all__ = [
    "run_goal",
    "run_eco",
    "restore_goal_checkpoint",
    "goal_checkpoint_origin",
    "goal_producer",
    "latest_producer",
]
