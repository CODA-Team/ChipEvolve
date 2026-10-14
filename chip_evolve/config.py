"""Explicit local deployment and design bindings, separate from business requests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def read(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text())


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


class Deployment:
    def __init__(self, path: Path):
        self.path = path.resolve()
        self.value = read(self.path)
        if self.value["schema_version"] != "chip-evolve.local.v1":
            raise ValueError("Unsupported local deployment schema")
        self.state = Path(self.value["state_root"])
        self.state.mkdir(parents=True, exist_ok=True)

    def design(self, design_id: str) -> dict[str, Any]:
        return self.value["designs"][design_id]

    def experiment(self, design_id: str, key: str) -> Path:
        if Path(key).name != key or key in {".", ".."}:
            raise ValueError("Experiment key must name one local directory")
        path = self.state / "experiments" / design_id / key
        path.mkdir(parents=True, exist_ok=False)
        return path
