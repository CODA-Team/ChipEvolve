"""Execution-platform handoff for a packaged run snapshot."""

from __future__ import annotations

import sys

import tempfile
import zipfile
from pathlib import Path
from typing import Any

from openroad_platform_client import KernelClient
from openroad_platform_contracts import ContractError

from .ingest import load_snapshot_directory
from .repository import DataStore


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
        refs = list(pack["snapshot"].get("source_artifacts", []))
        known = {item.get("artifact_id") for item in refs if isinstance(item, dict)}
        for item in (*_run_artifact_refs(client, run_id, excluded={artifact_id}), artifact):
            if item["artifact_id"] not in known:
                refs.append(item)
                known.add(item["artifact_id"])
        pack["snapshot"]["source_artifacts"] = refs
        return pack


def import_ready_bundles(store: DataStore, client: KernelClient) -> int:
    """Import each completed design snapshot artifact once."""
    imported = 0
    superseded = 0
    for run in client.runs(status="succeeded", limit=100):
        run_id = str(run["run_id"])
        for artifact in client.artifacts(run_id):
            artifact_id = artifact.get("artifact_id")
            if artifact.get("kind") != "data_snapshot" or not isinstance(artifact_id, str):
                continue
            if store.imported(artifact_id):
                continue
            try:
                store.register_import(artifact_id,
                                      load_run_bundle(client, run_id, artifact_id))
            except ContractError as exc:
                # A superseded bundle for a snapshot we already hold must not take
                # the interface down.  This importer runs on every GET, so one such
                # artifact made every request fail with "snapshot already exists" -
                # which is exactly what happened while re-extracting a snapshot: the
                # new bundle existed, the old snapshot row still did, and the whole
                # service answered errors until that artifact was marked.
                if "already exists" not in str(exc):
                    raise
                store.mark_imported(artifact_id)
                superseded += 1
                continue
            imported += 1
    if superseded:
        print(f"import_ready_bundles: skipped {superseded} superseded bundle(s)",
              file=sys.stderr)
    return imported


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
        "attempt_id": item.get("attempt_id"),
        "sha256": item["sha256"],
        "logical_path": item.get("store_key", artifact_id),
        "category": item.get("kind", "bundle"),
        "stage": item.get("stage_key", "run"),
        "format": "zip",
        "size_bytes": item.get("size_bytes", 0),
    }


def _run_artifact_refs(client: KernelClient, run_id: str,
                       *, excluded: set[str]) -> list[dict[str, Any]]:
    """Expose registered run artifacts as individual source references.

    A data snapshot is a portable index, not the only raw evidence.  The
    execution platform may also register the original report, database, or
    tool receipt separately.  Keeping those identities in the immutable
    snapshot lets a later query retrieve the exact bytes without unpacking a
    bundle or guessing a path.
    """
    result: list[dict[str, Any]] = []
    for item in client.artifacts(run_id):
        artifact_id = item.get("artifact_id")
        if not isinstance(artifact_id, str) or artifact_id in excluded:
            continue
        kind = item.get("kind")
        if (isinstance(kind, str)
                and (kind.startswith("runtime_")
                     or kind in {"extractor_log", "extractor_receipt"})):
            continue
        required = ("sha256", "store_key", "kind")
        if not all(isinstance(item.get(name), str) and item[name] for name in required):
            raise ContractError(f"run artifact is missing source identity: {artifact_id}")
        result.append({
            "schema_version": 3,
            "artifact_id": artifact_id,
            "run_id": run_id,
            "attempt_id": item.get("attempt_id"),
            "sha256": item["sha256"],
            "logical_path": item["store_key"],
            "category": kind,
            "stage": item.get("stage_key") or "run",
            "format": item.get("media_type") or (
                item.get("metadata", {}).get("format")
                if isinstance(item.get("metadata"), dict) else None
            ),
            "size_bytes": item.get("size_bytes", 0),
        })
    return result
