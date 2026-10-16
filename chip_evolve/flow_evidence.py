"""Recover completed Flow facts while preserving a terminal search failure."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import Deployment, business_lock, read


def collect(
    deployment: Deployment, design_id: str, experiment: Path, objective: Path
) -> dict[str, Any]:
    from .professional import _collect_flow_candidates

    with business_lock(experiment):
        design = deployment.design(design_id)
        summary = read(
            experiment
            / "source/flow/backup_dir"
            / design["platform"]
            / design["nickname"]
            / "llm_usage_summary.json"
        )
        if summary["status"] != "failed" or summary["exit_code"] in (None, 0):
            raise ValueError("Completed evidence needs a terminal failed Flow campaign")
        campaign = read(experiment / "platform-state/campaign.json")
        if campaign["campaign_id"] != summary["campaign_id"]:
            raise ValueError("Flow campaign identity differs from its terminal summary")
        owner = campaign["owner"]
        try:
            fields = (
                Path(f"/proc/{owner['pid']}/stat").read_text().rsplit(")", 1)[1].split()
            )
        except FileNotFoundError:
            fields = []
        if fields and fields[0] != "Z" and fields[19] == owner["start_ticks"]:
            raise ValueError("Native Flow owner is still running; no evidence recovery")
        native = {
            key: summary.get(key)
            for key in ("campaign_id", "status", "exit_code", "completed_iterations")
        }
        return _collect_flow_candidates(
            deployment,
            design_id,
            experiment,
            objective,
            output=experiment / "completed-evidence",
            native_campaign=native,
        )
