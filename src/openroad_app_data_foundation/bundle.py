"""Execution-platform handoff for a packaged run snapshot."""

from __future__ import annotations

import tempfile
import zipfile
from pathlib import Path
from typing import Any

from openroad_platform_client import KernelClient
from openroad_platform_contracts import ContractError

from .ingest import load_snapshot_directory


def load_run_bundle(client: KernelClient, run_id: str, artifact_id: str) -> dict[str, Any]:
    """Download one registered bundle, verify it through the client, then import it."""
    with tempfile.TemporaryDirectory(prefix="context-import-") as directory:
        archive = Path(directory) / "run.zip"
        client.download_artifact_to(run_id, artifact_id, str(archive))
        with zipfile.ZipFile(archive) as source:
            _check_members(source)
            source.extractall(directory)
        for nested in sorted(Path(directory).rglob("*.zip")):
            if nested == archive:
                continue
            with zipfile.ZipFile(nested) as source:
                _check_members(source)
                target = nested.with_suffix("")
                target.mkdir(exist_ok=True)
                source.extractall(target)
        manifests = sorted(Path(directory).rglob("manifest.json"))
        if len(manifests) != 1:
            raise ContractError("run bundle must contain exactly one data manifest")
        pack = load_snapshot_directory(manifests[0].parent)
        artifact = _bundle_ref(client, run_id, artifact_id)
        pack["snapshot"]["source_artifacts"] = [
            *pack["snapshot"].get("source_artifacts", []), artifact,
        ]
        return pack


def _check_members(source: zipfile.ZipFile) -> None:
    for member in source.infolist():
        path = Path(member.filename)
        if path.is_absolute() or ".." in path.parts:
            raise ContractError(f"bundle member escapes extraction root: {member.filename}")


def _bundle_ref(client: KernelClient, run_id: str, artifact_id: str) -> dict[str, Any]:
    matches = [item for item in client.artifacts(run_id) if item.get("artifact_id") == artifact_id]
    if len(matches) != 1:
        raise ContractError(f"bundle artifact not found: {artifact_id}")
    item = matches[0]
    return {
        "schema_version": 3,
        "artifact_id": artifact_id,
        "run_id": run_id,
        "sha256": item["sha256"],
        "logical_path": item.get("store_key", artifact_id),
        "category": item.get("kind", "bundle"),
        "stage": item.get("stage_key", "run"),
        "format": "zip",
        "size_bytes": item.get("size_bytes", 0),
    }
