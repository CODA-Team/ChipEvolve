"""Import the portable JSON snapshot produced by a parser capability."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Iterator, Sequence
from pathlib import Path
from typing import Any

from openroad_platform_contracts import ContractError, SCHEMA_VERSION


FILES = (
    "stages", "objects", "observations", "relations", "timing_paths",
    "timing_points", "markers",
)


#: Records handed over per batch.  One ariane136 stage is a 1.18 GB
#: objects.jsonl, a 1.47 GB relations.jsonl and a 1.53 GB markers.jsonl;
#: materialising those as lists is what made importing one stage need ~36 GiB of
#: RSS.  Reading them in batches is what makes the resident set track the batch
#: instead of the design, without changing one record that reaches the store.
BATCH_ROWS = 10000


class JsonlRows(Sequence):
    """The records of one ``*.jsonl`` member, read in bounded batches.

    The file is held open rather than re-opened per pass: a bundle is unpacked
    into a ``TemporaryDirectory`` that is removed as soon as the download
    returns, so an open descriptor is the one form of those bytes that outlives
    the directory the pack was read from.

    ``project`` maps a source record to the record that is stored, and drops it
    when it maps to ``None``.  The markers file needs that: it is the source of
    the physical records, and it holds 2.42 M of them on ariane136.
    """

    def __init__(self, path: Path, *,
                 project: Callable[[dict[str, Any]], dict[str, Any] | None] | None = None,
                 batch_rows: int = BATCH_ROWS) -> None:
        self._path = path
        self._project = project
        self._batch_rows = batch_rows
        self._handle = path.open(encoding="utf-8") if path.is_file() else None
        self._count: int | None = None

    def batches(self) -> Iterator[list[dict[str, Any]]]:
        if self._handle is None:
            return
        self._handle.seek(0)
        batch: list[dict[str, Any]] = []
        for line_number, line in enumerate(self._handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ContractError(f"{self._path.name}:{line_number} "
                                    f"must contain an object")
            if self._project is not None:
                value = self._project(value)
                if value is None:
                    continue
            batch.append(value)
            if len(batch) >= self._batch_rows:
                yield batch
                batch = []
        if batch:
            yield batch

    def __iter__(self) -> Iterator[dict[str, Any]]:
        for batch in self.batches():
            yield from batch

    def __len__(self) -> int:
        if self._count is None:
            self._count = sum(len(batch) for batch in self.batches())
        return self._count

    def __getitem__(self, index: int) -> dict[str, Any]:
        position = 0
        for batch in self.batches():
            if index < position + len(batch):
                return batch[index - position]
            position += len(batch)
        raise IndexError(index)


def load_snapshot_directory(directory: str | Path) -> dict[str, Any]:
    """Read a snapshot directory without reading any host design directory.

    Each record member comes back as a :class:`JsonlRows` the caller walks batch
    by batch, so a stage is never held in memory as one Python list.  The small
    members - manifest, catalog, coverage, the fragment sources - are still read
    whole, because each of them is a single whole-file fact.
    """
    root = Path(directory)
    manifest = _read_object(root / "manifest.json", required=True)
    summary = _read_object(root / "summary.json", required=False)
    artifacts = _read_lines(root / "artifacts.jsonl")
    snapshot = _snapshot(manifest, summary, artifacts)
    pack: dict[str, Any] = {"snapshot": snapshot, "run_summary": summary}
    # One catalog per snapshot holds the artifact descriptor; each record keeps
    # only a short reference to it.  The descriptor is NOT copied onto every
    # record: that cost 1.23 GB inside a 5.74 GB Ibex database (42% of all stored
    # payload text) and would cost ~11 GB on a design four times this size, for a
    # field set that is identical on every record of a snapshot.  The reference is
    # expanded when a caller reads the record - see evidence.materialize.
    catalog = _read_object(root / "source_catalog.json", required=False) or {}
    refs = catalog.get("refs") if isinstance(catalog.get("refs"), dict) else {}
    if refs:
        snapshot["source_catalog"] = refs
    for name in FILES:
        if name == "markers":
            # The markers are not stored as themselves; they are the source of
            # the physical records, projected as they are read (see below).
            continue
        pack["entities" if name == "objects" else name] = JsonlRows(root / f"{name}.jsonl")
    pack["coverage"] = _read_object(root / "coverage.json", required=False) or {}
    pack["physical_context"] = JsonlRows(root / "markers.jsonl", project=_physical_record)
    # Keep the JSON members a fragment read can slice.  They arrived with the bundle,
    # so no extra download is needed and the 4 MiB download cap never applies.
    pack["fragment_sources"] = {
        path: (root / Path(path).name).read_bytes()
        for path in FRAGMENT_PATHS
        if (root / Path(path).name).is_file()
    }
    return pack


#: bundle members worth keeping verbatim for fragment reads.  The binary database is
#: absent on purpose: its facts are already extracted, and it is neither parseable
#: here nor under the download cap.
FRAGMENT_PATHS = ("query-data/timing_report.json",
                  "query-data/timing_report_hold.json",
                  "query-data/dbnetwork_map.json")


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
        "attempt_id": item.get("attempt_id"),
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


def _physical_records(markers: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """The placement records of markers that are already in hand."""
    return [row for row in map(_physical_record, markers) if row is not None]


def _physical_record(marker: dict[str, Any]) -> dict[str, Any] | None:
    """One placement record, or ``None`` for a marker that places nothing."""
    object_id = marker.get("object_id") or marker.get("instance_id")
    if not object_id:
        return None
    return {
        "object_id": object_id,
        "snapshot_id": marker.get("snapshot_id"),
        "instance_name": marker.get("instance_name"),
        # the adapter emits the placement origin; the record used to drop it,
        # which left CONTRACT 4.11 promising x/y that no record carried.
        "x": marker.get("x"),
        "y": marker.get("y"),
        "bbox": marker.get("bbox"),
        "layer": marker.get("layer"),
        "geometry": marker.get("geometry", []),
        "routing": marker.get("routing", []),
        "evidence": marker.get("evidence", []),
    }
