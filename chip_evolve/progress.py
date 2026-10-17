"""Read native stage barriers alongside their actual public EF task states."""

from __future__ import annotations

import re
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from openroad_platform_client import KernelClient

from .config import read
from .lifecycle import TERMINAL


def flow_progress(client: KernelClient, experiment: Path) -> dict[str, Any] | None:
    journal_path = experiment / "platform-state/campaign.json"
    if not journal_path.exists():
        return None
    journal = read(journal_path)
    if "iteration" not in journal:
        return {
            "campaign_id": journal["campaign_id"],
            "native_design_id": journal["design"],
            "progress_available": False,
            "iteration": None,
            "last_completed_phase": None,
            "planned_candidates": None,
            "stages": {},
            "reason": "No native iteration barrier has been committed",
            "observed_at": time.time(),
        }
    campaign, design, iteration = (
        journal[key] for key in ("campaign_id", "design", "iteration")
    )
    paths = sorted((journal_path.parent / f"iteration-{iteration}").glob("slot-*.json"))
    records = [
        read(path)
        for path in paths
        if re.fullmatch(
            r"slot-\d+-(?:place|cts|route_finish|eval_place|eval_cts|eval_final)\.json",
            path.name,
        )
    ]
    if any(
        record["campaign_id"] != campaign
        or record["design"] != design
        or record["iteration"] != iteration
        for record in records
    ):
        raise ValueError("Native progress ledger belongs to a different campaign")
    active: dict[str, dict[str, Any]] = {}
    if any(r.get("run_id") and r["status"] not in TERMINAL for r in records):
        for status in ("queued", "running"):
            offset = 0
            while batch := client.runs(
                project_id="a2-flow",
                design_id=design,
                status=status,
                limit=100,
                offset=offset,
            ):
                active.update({r["run_id"]: r for r in batch})
                if len(batch) < 100:
                    break
                offset += len(batch)
    stages: dict[str, Counter[str]] = defaultdict(Counter)
    submitted: Counter[str] = Counter()
    for record in records:
        status = "prepared"
        if record.get("run_id"):
            submitted[record["stage"]] += 1
            run = (
                record.get("terminal_run")
                if record["status"] in TERMINAL
                else active.get(record["run_id"])
            )
            # A task may finish between the public list and its native receipt.
            # Resolve that exact handle without submitting or changing anything.
            if run is None:
                run = client.run(record["run_id"])
            if (
                run["run_id"] != record["run_id"]
                or run["project_id"] != "a2-flow"
                or run["design_id"] != design
                or run["experiment_id"] != campaign
                or run["labels"].get("stage") != record["stage"]
                or run["labels"].get("iteration") != str(iteration)
                or run["labels"].get("candidate_slot") != str(record["candidate_slot"])
                or run["labels"].get("candidate_id") != record["candidate_id"]
            ):
                raise ValueError("Public EF task differs from the native campaign")
            status = run["status"]
        stages[record["stage"]][status] += 1
    return {
        "campaign_id": campaign,
        "native_design_id": design,
        "progress_available": True,
        "iteration": iteration,
        "last_completed_phase": journal["phase"],
        "planned_candidates": journal["runs"],
        "stages": {
            stage: {
                "recorded": sum(counts.values()),
                "submitted": submitted[stage],
                "counts": dict(sorted(counts.items())),
            }
            for stage, counts in sorted(stages.items())
        },
        "observed_at": time.time(),
        "semantics": "EF task states for the current native iteration; the phase is the last completed barrier, and task success is not PPA acceptance or delivered experiment success",
    }
