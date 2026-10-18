"""Recover completed Flow facts while preserving a terminal search failure."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import Deployment, business_lock, read
from .jobs import digest


def collect(
    deployment: Deployment, design_id: str, experiment: Path, objective: Path
) -> dict[str, Any]:
    from .professional import _collect_flow_candidates

    with business_lock(experiment):
        design = deployment.design(design_id)
        summary_path = (
            experiment
            / "source/flow/backup_dir"
            / design["platform"]
            / design["nickname"]
            / "llm_usage_summary.json"
        )
        summary = read(summary_path)
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
        if summary["status"] != "failed" or summary["exit_code"] in (None, 0):
            status_path = experiment / "status.json"
            cleanup_path = experiment / "native-frontend-cleanup.json"
            if (
                summary["status"] != "running"
                or summary["exit_code"] is not None
                or not status_path.is_file()
                or not cleanup_path.is_file()
            ):
                raise ValueError(
                    "Completed evidence needs a terminal failed Flow campaign"
                )
            status, cleanup = read(status_path), read(cleanup_path)
            if (
                status.get("status") != "failed"
                or status.get("error_type") != "TimeoutExpired"
                or cleanup.get("status") != "completed"
                or cleanup.get("reason") != "TimeoutExpired"
                or cleanup.get("owner_pid") != owner["pid"]
            ):
                raise ValueError(
                    "Flow timeout lacks matching completed cleanup evidence"
                )
            native.update(
                status="timed_out",
                terminal_evidence={
                    "reported_native_status": summary["status"],
                    "source": "business-supervisor",
                    "files": {
                        str(path.resolve()): digest(path)
                        for path in (summary_path, status_path, cleanup_path)
                    },
                },
            )
        return _collect_flow_candidates(
            deployment,
            design_id,
            experiment,
            objective,
            output=experiment / "completed-evidence",
            native_campaign=native,
        )
