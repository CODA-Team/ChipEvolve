"""Read the opt-in experiment profile without changing native defaults."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def load_platform_profile() -> dict[str, Any] | None:
    path = os.environ.get("GOALEVOLVE_PLATFORM_PROFILE")
    if not path:
        return None
    value = json.loads(Path(path).read_text())
    if not isinstance(value, dict):
        raise TypeError("GoalEvolve platform profile must be an object")
    return value


def source_seed(native: Path) -> Path:
    profile = load_platform_profile()
    return Path(profile["source_seed"]).resolve() if profile else native


def existing_codex() -> dict[str, Any] | None:
    profile = load_platform_profile()
    if not profile:
        return None
    codex = profile["codex"]
    if codex["auth_mode"] == "project_api":
        return None
    if codex["auth_mode"] != "existing_codex":
        raise ValueError("Unsupported explicit GoalEvolve Codex authentication mode")
    return codex
