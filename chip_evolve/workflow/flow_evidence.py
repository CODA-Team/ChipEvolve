"""Compatibility entry for guarded completed evidence from a failed Flow search."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from chip_evolve.core.config import Deployment
from chip_evolve.workflow.flow_delivery import collect_failed_evidence
from chip_evolve.core.result_io import load_objective_ref, wire_object


def collect(
    deployment: Deployment, design_id: str, experiment: Path, objective: Path
) -> dict[str, Any]:
    return wire_object(
        collect_failed_evidence(
            deployment, design_id, experiment, load_objective_ref(objective)
        ).wire
    )
