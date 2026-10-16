"""Materialize selected design objects through the original EF/DF delivery path."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import Deployment
from .jobs import Jobs
from .physical import publish


def ensure(
    deployment: Deployment, source: Path, frame: dict[str, Any]
) -> dict[str, Any]:
    deferred = frame.get("deferred_facts", {}).get("opendb")
    if deferred is None:
        return frame
    jobs = Jobs(deployment, frame["design_id"], Path(deferred["publication_root"]))
    return publish(
        jobs,
        frame,
        result_path=source.parent / "materialized-result.json",
        modes=("opendb",),
    )
