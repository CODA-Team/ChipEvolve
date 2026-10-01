"""Resolve parser source roles to execution-owned artifact identities."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


PLACEHOLDER_ARTIFACT_IDS = frozenset({"timing-report", "orfs-metadata"})


def original_paths(manifest, digest):
    """Only declared paths with an actual matching digest identify an original."""
    return sorted(path for path, entry in manifest.items()
                  if digest is not None and entry.get('sha256') == digest)


def object_provenance(store, snapshot_id, identifier, kind):
    """Join the native object locator to its exact input identities and producer."""
    from urllib.parse import quote
    from .engineering import _entity
    from .identity import snapshot_identity
    entity = _entity(store, snapshot_id, identifier, kind)
    snapshot = store.snapshot(snapshot_id)
    producer = snapshot.get('run_summary', {}).get('timing_context', {}).get('producer', {})
    manifest = producer.get('artifacts', {})
    sources = [{**ref, 'original_paths': original_paths(manifest, ref.get('sha256'))}
               for ref in entity.get('evidence', [])]
    record = '/snapshots/' + snapshot_id + '/records/entities/' + quote(entity['object_id'], safe='')
    return {'snapshot_id': snapshot_id, 'snapshot': snapshot_identity(snapshot),
        'object': {key: entity.get(key) for key in ('object_id', 'kind', 'name', 'identity', 'locator', 'source_ref')},
        'producer_identity': {key: producer.get(key) for key in ('design', 'platform', 'variant', 'native_run_id', 'toolchain')},
        'sources': sources, 'evidence': entity.get('evidence', []),
        'record_sources': {'evidence_path': record + '/evidence', 'fragments_path': record + '/fragments'},
        'basis': 'resolved original artifact digests/native locators and literal producer metadata; original_paths are producer declarations'}


def resolve_records(snapshot: Mapping[str, Any],
                   values: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    """Attach an artifact identity only when the registered catalogue proves it.

    Adapters may know a source role and staged logical path before the runtime
    assigns an artifact ID. Resolution is exact-path first, then unique
    role/stage. Multiple candidates stay explicitly unresolved.
    """
    refs = [item for item in snapshot.get("source_artifacts", [])
            if isinstance(item, dict)]
    return {
        record_type: [_resolve_row(row, refs) for row in rows]
        for record_type, rows in values.items()
    }


def _resolve_row(row: dict[str, Any], refs: list[dict[str, Any]]) -> dict[str, Any]:
    raw = row.get("evidence")
    if not isinstance(raw, list):
        return row
    return {**row, "evidence": [_resolve_item(item, refs) for item in raw]}


def _resolve_item(item: Any, refs: list[dict[str, Any]]) -> Any:
    if not isinstance(item, dict):
        return item
    explicit_id = item.get("artifact_id")
    if explicit_id in PLACEHOLDER_ARTIFACT_IDS:
        item = {key: value for key, value in item.items() if key != "artifact_id"}
        explicit_id = None
    if isinstance(explicit_id, str) and explicit_id:
        exact_id = [ref for ref in refs if ref.get("artifact_id") == explicit_id]
        if len(exact_id) == 1:
            return _resolved(item, exact_id[0], resolution="exact_artifact")
        return {**item, "resolution": "unverified"}
    nested = item.get("artifact")
    if isinstance(nested, dict) and nested.get("artifact_id"):
        return item
    kind = item.get("artifact_kind") or item.get("category")
    path = item.get("logical_path") or item.get("store_key")
    stage = item.get("stage")
    candidates = [ref for ref in refs if _same(ref.get("category"), kind)]
    exact = [ref for ref in candidates if path and ref.get("logical_path") == path]
    if len(exact) == 1:
        return _resolved(item, exact[0], resolution="exact_path")
    if len(exact) > 1:
        # two artifacts claim the same file: picking the first would be a silent
        # choice between them
        return {**item, "resolution": "ambiguous", "candidate_count": len(exact)}
    if path:
        # The reference names a file.  Two honest outcomes remain, and neither is
        # "the only artifact of this kind": the file may live inside the bundle
        # (bundle_member), or it is not registered anywhere (unresolved).  Quietly
        # attaching a same-role artifact used to make a wrong pointer look resolved.
        bundle_candidates = [ref for ref in refs
                             if ref.get("category") in {"data_snapshot", "runtime_bundle"}]
        if len(bundle_candidates) == 1:
            return _resolved({**item, "nested_path": path}, bundle_candidates[0],
                             resolution="bundle_member")
        return {**item, "resolution": "unresolved",
                "reason": f"no registered artifact at {path}"}
    if stage:
        staged = [ref for ref in candidates if ref.get("stage") == stage]
        if staged:
            candidates = staged
    if len(candidates) != 1:
        return {**item, "resolution": "ambiguous" if candidates else "unresolved",
                "candidate_count": len(candidates)}
    return _resolved(item, candidates[0], resolution="unique_role")


def materialize(row: Mapping[str, Any], snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """Resolve a record's compact source reference against its snapshot catalogue.

    Records are stored exactly as the adapter wrote them: a short ``source_ref``
    (or, for marker rows, a bare artifact descriptor) plus an optional ``locator``.
    The catalogue entry and the artifact identity are attached here, when a caller
    actually reads the row, instead of being copied into every row of the snapshot.
    The returned shape is identical to the one the old eager expansion produced, so
    the public contract does not change.
    """
    items = row.get("evidence")
    if not isinstance(items, list) or not items:
        reference = row.get("source_ref")
        if not isinstance(reference, str) or not reference:
            return dict(row)
        catalog = snapshot.get("source_catalog")
        entry = catalog.get(reference) if isinstance(catalog, Mapping) else None
        if not isinstance(entry, Mapping):
            # A reference this snapshot's catalogue does not know - a stale or
            # foreign one - must stay visible rather than disappear.
            return {**row, "evidence": [{
                "status": "unavailable",
                "source_ref": reference,
                "reason": f"source_ref {reference!r} is not in this snapshot's catalog",
            }]}
        item = dict(entry)
        item["source_ref"] = reference
        locator = row.get("locator")
        if isinstance(locator, Mapping) and locator:
            item["locator"] = dict(locator)
        items = [item]
    refs = [item for item in snapshot.get("source_artifacts", [])
            if isinstance(item, dict)]
    # A row written by the old eager-expansion ingest already carries resolved
    # entries.  Resolving those a second time is not a no-op: the first pass put an
    # ``artifact_id`` on the entry, so the second pass would relabel an
    # ``exact_path`` provenance as ``exact_artifact``.  Only unresolved entries are
    # resolved here.
    return {**row, "evidence": [
        item if (isinstance(item, Mapping) and item.get("resolution"))
        else _resolve_item(item, refs)
        for item in items]}


def _resolved(item: dict[str, Any], ref: Mapping[str, Any], *, resolution: str) -> dict[str, Any]:
    return {
        **item,
        "artifact_id": ref.get("artifact_id"),
        "run_id": ref.get("run_id"),
        "attempt_id": ref.get("attempt_id"),
        "sha256": ref.get("sha256"),
        "size_bytes": ref.get("size_bytes"),
        "category": ref.get("category"),
        "stage": ref.get("stage"),
        "logical_path": ref.get("logical_path") or item.get("logical_path"),
        "resolution": resolution,
    }


def _same(left: Any, right: Any) -> bool:
    return isinstance(left, str) and left and left == right
