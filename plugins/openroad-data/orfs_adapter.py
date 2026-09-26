"""ORFS metadata adapter.

ORFS already writes structured metadata. This adapter reads that metadata and
does not scrape values back out of logs.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def convert(inputs: dict[str, Any], workspace: Path) -> str:
    metadata_path = _relative(inputs, "metadata_path")
    source = workspace / metadata_path
    if not source.is_file():
        raise ValueError(f"ORFS metadata file is missing: {metadata_path}")
    metadata = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(metadata, dict):
        raise ValueError("ORFS metadata must be a JSON object")
    output_name = _relative(inputs, "output_directory", default="query-data")
    output = workspace / output_name
    output.mkdir(parents=True, exist_ok=True)
    snapshot = _snapshot(inputs)
    snapshot["source_artifacts"] = inputs.get("source_artifacts", [])
    _write(output / "manifest.json", {"snapshot": snapshot, "schema_version": 3})
    _write(output / "summary.json", {"snapshot": snapshot,
                                      "metadata": metadata})
    _write_lines(output / "observations.jsonl", _observations(metadata, inputs))
    _write_lines(output / "stages.jsonl", _stages(metadata, snapshot))
    _write(output / "coverage.json", {"source": "orfs_metadata", "metrics": "parsed"})
    return output_name


def _snapshot(inputs: dict[str, Any]) -> dict[str, str]:
    result = {key: inputs.get(key) for key in (
        "snapshot_id", "design_id", "revision_id", "run_id", "created_at")}
    result["stage"] = inputs.get("stage", "flow")
    missing = [key for key, value in result.items() if not isinstance(value, str) or not value]
    if missing:
        raise ValueError(f"inputs missing snapshot fields: {', '.join(missing)}")
    return {key: str(value) for key, value in result.items()}


def _observations(metadata: dict[str, Any], inputs: dict[str, Any]) -> list[dict[str, Any]]:
    values = metadata.get("metrics", metadata)
    if not isinstance(values, dict):
        raise ValueError("ORFS metadata metrics must be an object")
    artifact_id = inputs.get("metrics_artifact_id", "orfs-metadata")
    result: list[dict[str, Any]] = []
    for index, (name, value) in enumerate(sorted(values.items())):
        if not isinstance(value, (int, float, str, bool)):
            continue
        result.append({
            "observation_id": f"metric:{name}",
            "snapshot_id": inputs["snapshot_id"],
            "object_id": f"run:{inputs['run_id']}",
            "kind": "metric",
            "value": value,
            "status": "parsed",
            "evidence": [{"artifact_id": artifact_id, "source_type": "json",
                          "detail": {"field": f"metrics.{name}", "ordinal": index}}],
        })
    return result


def _stages(metadata: dict[str, Any], snapshot: dict[str, str]) -> list[dict[str, Any]]:
    stages = metadata.get("stages", [])
    if isinstance(stages, dict):
        stages = [{"stage_id": key, **value} if isinstance(value, dict)
                  else {"stage_id": key, "value": value}
                  for key, value in stages.items()]
    if not isinstance(stages, list):
        return []
    return [{"stage_id": str(row.get("stage_id") or row.get("name") or index),
             "snapshot_id": snapshot["snapshot_id"], **row}
            for index, row in enumerate(stages) if isinstance(row, dict)]


def _relative(inputs: dict[str, Any], name: str, *, default: str | None = None) -> str:
    value = inputs.get(name, default)
    if not isinstance(value, str) or not value or value.startswith("/") \
            or ".." in Path(value).parts:
        raise ValueError(f"inputs.{name} must be a relative staged path")
    return value


def _write(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_lines(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
                    encoding="utf-8")
