"""Import the portable JSON snapshot produced by a parser capability."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from openroad_platform_contracts import ContractError, SCHEMA_VERSION


FILES = (
    "stages", "objects", "observations", "relations", "timing_paths",
    "timing_points", "markers",
)


def load_snapshot_directory(directory: str | Path) -> dict[str, Any]:
    """Read a snapshot directory without reading any host design directory."""
    root = Path(directory)
    manifest = _read_object(root / "manifest.json", required=True)
    summary = _read_object(root / "summary.json", required=False)
    artifacts = _read_lines(root / "artifacts.jsonl")
    snapshot = _snapshot(manifest, summary, artifacts)
    pack: dict[str, Any] = {"snapshot": snapshot, "run_summary": summary}
    marker_rows: list[dict[str, Any]] = []
    for name in FILES:
        values = _read_lines(root / f"{name}.jsonl")
        if name == "markers":
            marker_rows = [{"marker_id": row.get("marker_id", str(index)), **row}
                           for index, row in enumerate(values)]
            continue
        pack["entities" if name == "objects" else name] = values
    pack["coverage"] = _read_object(root / "coverage.json", required=False) or {}
    pack["physical_context"] = _physical_records(marker_rows)
    return pack


def _snapshot(manifest: dict[str, Any], summary: dict[str, Any],
              artifacts: list[dict[str, Any]]) -> dict[str, Any]:
    source = manifest.get("snapshot") if isinstance(manifest.get("snapshot"), dict) else manifest
    declared_artifacts = source.get("source_artifacts", [])
    artifact_rows = artifacts or declared_artifacts
    result = {
        "schema_version": source.get("schema_version", SCHEMA_VERSION),
        "snapshot_id": source.get("snapshot_id") or source.get("id"),
        "design_id": source.get("design_id"),
        "revision_id": source.get("revision_id") or source.get("design_revision_id"),
        "run_id": source.get("run_id"),
        "stage": source.get("stage") or source.get("stage_key"),
        "created_at": source.get("created_at") or manifest.get("created_at", ""),
        "source_artifacts": [_artifact_ref(item, source) for item in artifact_rows],
    }
    if not result["snapshot_id"] and summary:
        result["snapshot_id"] = summary.get("snapshot_id")
    missing = [key for key in ("snapshot_id", "design_id", "revision_id", "run_id", "stage")
               if not result[key]]
    if missing:
        raise ContractError(f"manifest is missing snapshot fields: {', '.join(missing)}")
    return result


def _artifact_ref(item: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_id": item.get("artifact_id") or item.get("id"),
        "run_id": item.get("run_id") or snapshot.get("run_id"),
        "sha256": item.get("sha256"),
        "logical_path": item.get("logical_path") or item.get("store_key") or item.get("path"),
        "category": item.get("category") or metadata.get("category") or item.get("kind"),
        "stage": item.get("stage") or metadata.get("stage") or snapshot.get("stage"),
        "format": item.get("format") or item.get("media_type") or metadata.get("format"),
        "size_bytes": item.get("size_bytes", 0),
    }


def _read_object(path: Path, *, required: bool) -> dict[str, Any]:
    if not path.exists():
        if required:
            raise ContractError(f"required snapshot file is missing: {path.name}")
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ContractError(f"snapshot file must contain an object: {path.name}")
    return value


def _read_lines(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    result = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ContractError(f"{path.name}:{line_number} must contain an object")
        result.append(value)
    return result


def _physical_records(markers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records = []
    for marker in markers:
        object_id = marker.get("object_id") or marker.get("instance_id")
        if not object_id:
            continue
        records.append({
            "object_id": object_id,
            "snapshot_id": marker.get("snapshot_id"),
            "instance_name": marker.get("instance_name"),
            "bbox": marker.get("bbox"),
            "layer": marker.get("layer"),
            "geometry": marker.get("geometry", []),
            "routing": marker.get("routing", []),
            "evidence": marker.get("evidence", []),
        })
    return records
