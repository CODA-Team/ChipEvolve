"""Container command construction and timestamps shared by physical workflows."""

from __future__ import annotations

from datetime import UTC, datetime

from .config import Deployment


def now() -> str:
    return datetime.now(UTC).isoformat()


def container(deployment: Deployment, command: list[str]) -> list[str]:
    runtime = deployment.value["runtime"]
    result = [runtime["executable"], "exec", "--cleanenv", "--no-home"]
    for path in runtime["bind_roots"]:
        result += ["--bind", path + ":" + path]
    return [*result, runtime["image"], *command]
