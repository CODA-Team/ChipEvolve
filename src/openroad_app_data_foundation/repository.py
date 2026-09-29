"""Storage for immutable design context snapshots.

The service stores derived facts, never the original run files. Every record
keeps the artifact evidence references supplied by its producer.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable, Iterator, Mapping, Sequence, Sequence
from pathlib import Path
from typing import Any

from openroad_platform_contracts import (
    ContractError,
    SCHEMA_VERSION,
    validate_identifier,
    validate_relative_path,
    validate_sha256,
)

from .identity import enrich_records
from .evidence import resolve_records


RECORD_TYPES = (
    "stages", "entities", "observations", "relations", "timing_paths",
    "timing_points", "physical_context",
)


class DataStore:
    """A local snapshot store owned by this application."""

    def __init__(self, path: str | Path):
        self.connection = sqlite3.connect(str(path), check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS snapshots (
                snapshot_id TEXT PRIMARY KEY,
                payload TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS records (
                snapshot_id TEXT NOT NULL,
                record_type TEXT NOT NULL,
                record_id TEXT NOT NULL,
                ordinal INTEGER NOT NULL,
                payload TEXT NOT NULL,
                PRIMARY KEY(snapshot_id, record_type, record_id),
                FOREIGN KEY(snapshot_id) REFERENCES snapshots(snapshot_id)
            );
            CREATE INDEX IF NOT EXISTS records_lookup
                ON records(snapshot_id, record_type, ordinal);
            CREATE TABLE IF NOT EXISTS imported_artifacts (
                artifact_id TEXT PRIMARY KEY
            );
            CREATE INDEX IF NOT EXISTS records_json_name
                ON records(snapshot_id, record_type,
                           json_extract(payload, '$.name'));
            CREATE INDEX IF NOT EXISTS records_json_subject
                ON records(snapshot_id, record_type,
                           json_extract(payload, '$.subject_id'));
            CREATE INDEX IF NOT EXISTS records_json_object
                ON records(snapshot_id, record_type,
                           json_extract(payload, '$.object_id'));
            CREATE INDEX IF NOT EXISTS records_json_parent
                ON records(snapshot_id, record_type,
                           json_extract(payload, '$.parent_id'));
            CREATE INDEX IF NOT EXISTS records_json_path
                ON records(snapshot_id, record_type,
                           json_extract(payload, '$.path_id'));
            CREATE INDEX IF NOT EXISTS records_json_hier_name
                ON records(snapshot_id, record_type,
                           json_extract(payload,
                                        '$.attributes.hierarchical_name'));
            """
        )
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def register(self, pack: Mapping[str, Any]) -> dict[str, Any]:
        snapshot = _object(pack.get("snapshot"), "snapshot")
        snapshot_id = _required(snapshot, "snapshot_id")
        for name in ("design_id", "revision_id", "run_id", "stage"):
            _required(snapshot, name)
        version = snapshot.get("schema_version", SCHEMA_VERSION)
        if version != SCHEMA_VERSION:
            raise ContractError(f"unsupported schema_version {version!r}")
        snapshot = _validate_snapshot({
            **snapshot,
            "coverage": dict(pack.get("coverage") or {}),
            "run_summary": dict(pack.get("run_summary") or {}),
        }, version)
        values_by_type: dict[str, list[dict[str, Any]]] = {}
        for record_type in RECORD_TYPES:
            values = pack.get(record_type, [])
            if not isinstance(values, list):
                raise ContractError(f"{record_type} must be a list")
            values_by_type[record_type] = [
                _object(value, f"{record_type}[{ordinal}]")
                for ordinal, value in enumerate(values)
            ]
        entity_rows = values_by_type.get("entities", [])
        values_by_type = {
            record_type: enrich_records(snapshot, record_type, rows, entity_rows)
            for record_type, rows in values_by_type.items()
        }
        values_by_type = resolve_records(snapshot, values_by_type)
        records: list[tuple[str, str, int, str]] = []
        seen: set[tuple[str, str]] = set()
        for record_type in RECORD_TYPES:
            values = values_by_type[record_type]
            for ordinal, value in enumerate(values):
                row = value
                record_id = _record_id(record_type, row, ordinal)
                key = (record_type, record_id)
                if key in seen:
                    raise ContractError(f"duplicate {record_type} identity: {record_id}")
                seen.add(key)
                records.append((record_type, record_id, ordinal, json.dumps(
                    row, ensure_ascii=False, sort_keys=True)))
        try:
            with self.connection:
                self.connection.execute(
                    "INSERT INTO snapshots(snapshot_id, payload) VALUES (?, ?)",
                    (snapshot_id, json.dumps(snapshot, ensure_ascii=False, sort_keys=True)),
                )
                self.connection.executemany(
                    "INSERT INTO records(snapshot_id, record_type, record_id, ordinal, payload) "
                    "VALUES (?, ?, ?, ?, ?)",
                    [(snapshot_id, kind, record_id, ordinal, payload)
                     for kind, record_id, ordinal, payload in records],
                )
        except sqlite3.IntegrityError as exc:
            raise ContractError(f"snapshot already exists: {snapshot_id}") from exc
        return {"snapshot": snapshot, "record_counts": _counts(records)}

    def imported(self, artifact_id: str) -> bool:
        return self.connection.execute(
            "SELECT 1 FROM imported_artifacts WHERE artifact_id = ?", (artifact_id,)
        ).fetchone() is not None

    def register_import(self, artifact_id: str, pack: Mapping[str, Any]) -> dict[str, Any]:
        result = self.register(pack)
        with self.connection:
            self.connection.execute(
                "INSERT INTO imported_artifacts(artifact_id) VALUES (?)", (artifact_id,)
            )
        return result

    def snapshots(self, *, design_id: str | None = None, run_id: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT payload FROM snapshots"
        values: list[str] = []
        clauses: list[str] = []
        if design_id:
            clauses.append("json_extract(payload, '$.design_id') = ?")
            values.append(design_id)
        if run_id:
            clauses.append("json_extract(payload, '$.run_id') = ?")
            values.append(run_id)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY json_extract(payload, '$.created_at') DESC"
        return [json.loads(row["payload"]) for row in self.connection.execute(query, values)]

    def snapshot(self, snapshot_id: str) -> dict[str, Any]:
        row = self.connection.execute(
            "SELECT payload FROM snapshots WHERE snapshot_id = ?", (snapshot_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"snapshot not found: {snapshot_id}")
        return json.loads(row["payload"])

    def run_summary(self, snapshot_id: str) -> dict[str, Any]:
        """Return the run/stage boundary and indexed record counts."""
        snapshot = self.snapshot(snapshot_id)
        counts = {
            record_type: self._count(snapshot_id, record_type)
            for record_type in RECORD_TYPES
        }
        return {"snapshot": snapshot,
                "run_summary": snapshot.get("run_summary", {}),
                "record_counts": counts,
                "coverage": snapshot.get("coverage", {})}

    def run_summary_for_run(self, run_id: str) -> dict[str, Any]:
        """Return all indexed stage snapshots belonging to one execution run."""
        snapshots = self.snapshots(run_id=run_id)
        return {"run_id": run_id, "snapshots": [
            self.run_summary(item["snapshot_id"]) for item in snapshots
        ]}

    def find_instance(self, snapshot_id: str, name: str) -> list[dict[str, Any]]:
        """Find instances by an exact canonical or hierarchical name."""
        return self.entities_named(snapshot_id, "instance", name)

    def find_net(self, snapshot_id: str, name: str) -> list[dict[str, Any]]:
        """Find nets by an exact indexed name, never by a path scan or guess."""
        return self.entities_named(snapshot_id, "net", name)

    def net(self, snapshot_id: str, net_id: str) -> dict[str, Any]:
        result = self._entity_context(snapshot_id, net_id, "net")
        physical = self.records(snapshot_id, "physical_context", record_id=net_id, limit=1)
        if physical:
            result["physical_context"] = physical[0]
        return result

    def expand_net(self, snapshot_id: str, net_id: str) -> dict[str, Any]:
        result = self._entity_context(snapshot_id, net_id, "net")
        result["connected_entities"] = [
            self._entity_by_id(snapshot_id, related_id)
            for related_id in self._related_ids(snapshot_id, net_id)
            if self._entity_exists(snapshot_id, related_id)
        ]
        result["physical_context"] = self._physical_for_ids(
            snapshot_id, [net_id, *[item["object_id"]
                                    for item in result["connected_entities"]]])
        return result

    def records(self, snapshot_id: str, record_type: str, *, record_id: str | None = None,
                limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        if record_type not in RECORD_TYPES:
            raise KeyError(f"unsupported record type: {record_type}")
        if not 1 <= limit <= 10000:
            raise ValueError("limit must be between 1 and 10000")
        if offset < 0:
            raise ValueError("offset must not be negative")
        self.snapshot(snapshot_id)
        query = "SELECT payload FROM records WHERE snapshot_id = ? AND record_type = ?"
        values: list[Any] = [snapshot_id, record_type]
        if record_id is not None:
            query += " AND record_id = ?"
            values.append(record_id)
        query += " ORDER BY ordinal LIMIT ? OFFSET ?"
        values.extend((limit, offset))
        return [json.loads(row["payload"]) for row in self.connection.execute(query, values)]

    def filtered(self, snapshot_id: str, record_type: str, *, where: str = "",
                 params: Sequence[Any] = (), limit: int | None = None,
                 offset: int = 0) -> list[dict[str, Any]]:
        """Select records with an explicit SQL predicate on their payload.

        Callers must pass a bounded ``limit`` unless they genuinely need every
        row; unbounded reads go through :meth:`fetch_all`, which pages instead
        of silently cutting the result at the 10000-row ceiling.
        """
        if record_type not in RECORD_TYPES:
            raise KeyError(f"unsupported record type: {record_type}")
        if limit is not None and not 1 <= limit <= 10000:
            raise ValueError("limit must be between 1 and 10000")
        if offset < 0:
            raise ValueError("offset must not be negative")
        self.snapshot(snapshot_id)
        query = "SELECT payload FROM records WHERE snapshot_id = ? AND record_type = ?"
        values: list[Any] = [snapshot_id, record_type]
        if where:
            query += " AND " + where
            values.extend(params)
        # Ordering by ordinal forces the (snapshot, type, ordinal) index, which
        # cannot also serve a predicate - SQLite then scans every row of the
        # snapshot.  A filtered lookup does not need snapshot ordering, and a
        # snapshot is immutable, so index order is stable for a given boundary.
        if not where:
            query += " ORDER BY ordinal"
        if limit is not None:
            query += " LIMIT ? OFFSET ?"
            values.extend((limit, offset))
        return [json.loads(row["payload"]) for row in self.connection.execute(query, values)]

    def count_records(self, snapshot_id: str, record_type: str, *, where: str = "",
                      params: Sequence[Any] = ()) -> int:
        """Count rows for one snapshot and optional predicate, without scanning."""
        if record_type not in RECORD_TYPES:
            raise KeyError(f"unsupported record type: {record_type}")
        query = ("SELECT COUNT(*) AS count FROM records "
                 "WHERE snapshot_id = ? AND record_type = ?")
        values: list[Any] = [snapshot_id, record_type]
        if where:
            query += " AND " + where
            values.extend(params)
        row = self.connection.execute(query, values).fetchone()
        return int(row["count"])

    def fetch_all(self, snapshot_id: str, record_type: str) -> list[dict[str, Any]]:
        """Read every record of one type through bounded pages.

        Every context query used to pass ``limit=10000`` and then filter in
        Python, which returned a *silently short* answer once a design carried
        more than 10000 records.  This helper removes the ceiling without
        loading unbounded SQL in one shot.
        """
        self.snapshot(snapshot_id)
        total = self._count(snapshot_id, record_type)
        rows: list[dict[str, Any]] = []
        while len(rows) < total:
            rows.extend(self.records(snapshot_id, record_type, limit=10000,
                                     offset=len(rows)))
        return rows

    def iter_records(self, snapshot_id: str, record_type: str,
                     page: int = 10000) -> Iterator[dict[str, Any]]:
        """Stream one record type in bounded pages.

        ``fetch_all`` is right when every row is needed.  This exists for
        callers that may stop early - a paged evidence index - so memory stays
        at one page instead of the whole record set.
        """
        if record_type not in RECORD_TYPES:
            raise KeyError(f"unsupported record type: {record_type}")
        self.snapshot(snapshot_id)
        offset = 0
        while True:
            rows = self.records(snapshot_id, record_type, limit=page, offset=offset)
            if not rows:
                return
            yield from rows
            offset += len(rows)
            if len(rows) < page:
                return

    def entities_named(self, snapshot_id: str, kind: str,
                       name: str) -> list[dict[str, Any]]:
        """Exact name lookup inside one snapshot, by name or hierarchical name.

        Two searches rather than one OR, for the same reason as
        :meth:`relations_touching`: an OR over a column with and a column
        without an index made SQLite scan every entity of the snapshot.  The
        second branch reads ``attributes.hierarchical_name``, which the
        identity derivation prefers over ``name`` (identity.py:65) but which the
        OpenDB extractor does not populate yet - so on the current dataset both
        branches answer the same question, and the index must exist for the pair
        to stay a search rather than a scan of every entity.
        """
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for where in ("json_extract(payload, '$.name') = ?",
                      "json_extract(payload, "
                      "'$.attributes.hierarchical_name') = ?"):
            for row in self.filtered(
                    snapshot_id, "entities",
                    where=f"json_extract(payload, '$.kind') = ? AND {where}",
                    params=(kind, name)):
                key = str(row.get("object_id"))
                if key not in seen:
                    seen.add(key)
                    rows.append(row)
        return rows

    def entities_by_ids(self, snapshot_id: str,
                        object_ids: Sequence[str]) -> list[dict[str, Any]]:
        ids = [str(item) for item in dict.fromkeys(object_ids)]
        if not ids:
            return []
        result: list[dict[str, Any]] = []
        # ponytail: chunk at 250 IDs to stay far below SQLite's variable limit.
        for start in range(0, len(ids), 250):
            chunk = ids[start:start + 250]
            marks = ", ".join("?" for _ in chunk)
            result.extend(self.filtered(snapshot_id, "entities",
                                        where=f"record_id IN ({marks})",
                                        params=chunk))
        return result

    def children_of(self, snapshot_id: str, parent_id: str) -> list[dict[str, Any]]:
        return self.filtered(snapshot_id, "entities",
                             where="json_extract(payload, '$.parent_id') = ?",
                             params=(parent_id,))

    def relations_touching(self, snapshot_id: str,
                           object_ids: Sequence[str]) -> list[dict[str, Any]]:
        """Relations whose subject or object is one of the supplied IDs."""
        ids = [str(item) for item in dict.fromkeys(object_ids)]
        if not ids:
            return []
        result: list[dict[str, Any]] = []
        seen: set[str] = set()
        # ponytail: chunk at 250 IDs to stay far below SQLite's variable limit.
        # A relation whose two ends land in different chunks would otherwise be
        # returned twice, so de-duplicate by relation_id.
        for start in range(0, len(ids), 250):
            chunk = ids[start:start + 250]
            marks = ", ".join("?" for _ in chunk)
            # Two index searches rather than one OR, for two measured reasons:
            #
            #  * without parentheses around the OR group SQLite parses
            #    `snapshot_id = ? AND record_type = ? AND subject IN (?) OR
            #    object IN (?)` as `(... AND subject IN (?)) OR object IN (?)`,
            #    so the right branch escapes both filters - entity and physical
            #    rows came back as if they were relations, and the plan became a
            #    full scan of every record (1,523 ms instead of 0.1 ms);
            #  * with parentheses it used only the object-side expression index
            #    and silently dropped subject-only relations (1 row returned
            #    where 2 exist).
            #
            # Each branch is an index search on its own expression index, so the
            # union is correct and cheap; relation_id de-duplicates rows that
            # match both.
            for column in ("subject_id", "object_id"):
                for row in self.filtered(
                        snapshot_id, "relations",
                        where=f"json_extract(payload, '$.{column}') IN ({marks})",
                        params=chunk):
                    key = str(row.get("relation_id"))
                    if key in seen:
                        continue
                    seen.add(key)
                    result.append(row)
        return result

    def records_for_object(self, snapshot_id: str, record_type: str,
                           object_id: str) -> list[dict[str, Any]]:
        return self.filtered(snapshot_id, record_type,
                             where="json_extract(payload, '$.object_id') = ?",
                             params=(object_id,))

    def object(self, snapshot_id: str, object_id: str, *, expansion: str = "summary") -> dict[str, Any]:
        if expansion not in {"summary", "children", "full"}:
            raise ValueError("expansion must be summary, children, or full")
        rows = self.records(snapshot_id, "entities", record_id=object_id, limit=1)
        if not rows:
            raise KeyError(f"object not found: {object_id}")
        result: dict[str, Any] = {"entity": rows[0], "expansion": expansion}
        if expansion in {"children", "full"}:
            result["children"] = self.children_of(snapshot_id, object_id)
        if expansion == "full":
            result["observations"] = self._by_object(snapshot_id, "observations", object_id)
            result["relations"] = self._related(snapshot_id, object_id)
        return result

    def physical(self, snapshot_id: str, object_id: str) -> dict[str, Any]:
        rows = self.records(snapshot_id, "physical_context", record_id=object_id, limit=1)
        if not rows:
            raise KeyError(f"physical context not found: {object_id}")
        return rows[0]

    def evidence(self, snapshot_id: str, artifact_id: str | None = None) -> list[dict[str, Any]]:
        """Return fact locations that cite one registered artifact."""
        result: list[dict[str, Any]] = []
        for record_type in RECORD_TYPES:
            for row in self.fetch_all(snapshot_id, record_type):
                for evidence in row.get("evidence", []):
                    if not isinstance(evidence, dict):
                        continue
                    if artifact_id is None or evidence.get("artifact_id") == artifact_id:
                        result.append({"record_type": record_type,
                                       "record_id": record_identifier(record_type, row),
                                       "evidence": evidence})
        return result

    def record_evidence(self, snapshot_id: str, record_type: str,
                        record_id: str) -> list[dict[str, Any]]:
        rows = self.records(snapshot_id, record_type, record_id=record_id, limit=1)
        if not rows:
            raise KeyError(f"{record_type} not found: {record_id}")
        return [{"record_type": record_type, "record_id": record_id,
                 "evidence": item} for item in rows[0].get("evidence", [])]

    def _by_object(self, snapshot_id: str, record_type: str, object_id: str) -> list[dict[str, Any]]:
        return self.records_for_object(snapshot_id, record_type, object_id)

    def _related(self, snapshot_id: str, object_id: str) -> list[dict[str, Any]]:
        return self.relations_touching(snapshot_id, [object_id])

    def _count(self, snapshot_id: str, record_type: str) -> int:
        row = self.connection.execute(
            "SELECT COUNT(*) AS count FROM records WHERE snapshot_id = ? AND record_type = ?",
            (snapshot_id, record_type),
        ).fetchone()
        return int(row["count"])

    def _entity_context(self, snapshot_id: str, object_id: str,
                        expected_kind: str | None = None) -> dict[str, Any]:
        entity = self._entity_by_id(snapshot_id, object_id)
        if expected_kind is not None and entity.get("kind") != expected_kind:
            raise KeyError(f"object is not a {expected_kind}: {object_id}")
        return {"entity": entity,
                "observations": self._by_object(snapshot_id, "observations", object_id),
                "relations": self._related(snapshot_id, object_id)}

    def _entity_by_id(self, snapshot_id: str, object_id: str) -> dict[str, Any]:
        rows = self.records(snapshot_id, "entities", record_id=object_id, limit=1)
        if not rows:
            raise KeyError(f"object not found: {object_id}")
        return rows[0]

    def _entity_exists(self, snapshot_id: str, object_id: str) -> bool:
        return bool(self.records(snapshot_id, "entities", record_id=object_id, limit=1))

    def _related_ids(self, snapshot_id: str, object_id: str) -> list[str]:
        ids: list[str] = []
        for relation in self.relations_touching(snapshot_id, [object_id]):
            if relation.get("subject_id") == object_id:
                ids.append(str(relation.get("object_id")))
            elif relation.get("object_id") == object_id:
                ids.append(str(relation.get("subject_id")))
        return list(dict.fromkeys(ids))

    def _physical_for_ids(self, snapshot_id: str,
                          object_ids: list[str]) -> list[dict[str, Any]]:
        return [row for object_id in object_ids
                for row in self.records(snapshot_id, "physical_context",
                                        record_id=object_id, limit=1)]

    get_object = object
    get_run_summary = run_summary
    get_run_summary_for_run = run_summary_for_run
    get_net = net
    get_evidence_for_record = record_evidence
    find_instances = find_instance
    find_nets = find_net
    expand_net_context = expand_net
    get_physical_context = physical
    get_evidence = evidence


def record_identifier(record_type: str, row: Mapping[str, Any],
                      ordinal: int = 0) -> str:
    """The stable per-record ID of one stored row (same rule as registration)."""
    return _record_id(record_type, row, ordinal)


def _object(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ContractError(f"{name} must be an object")
    return value


def _required(value: Mapping[str, Any], name: str) -> str:
    result = value.get(name)
    if not isinstance(result, str) or not result:
        raise ContractError(f"snapshot.{name} is required")
    return result


def _validate_snapshot(snapshot: dict[str, Any], version: int) -> dict[str, Any]:
    for name in ("snapshot_id", "design_id", "revision_id", "run_id", "stage"):
        validate_identifier(f"snapshot.{name}", snapshot[name])
    if not isinstance(snapshot.get("created_at"), str) or not snapshot["created_at"]:
        raise ContractError("snapshot.created_at is required")
    artifacts = snapshot.get("source_artifacts", [])
    if not isinstance(artifacts, list):
        raise ContractError("snapshot.source_artifacts must be a list")
    for index, artifact in enumerate(artifacts):
        if not isinstance(artifact, dict):
            raise ContractError(f"source_artifacts[{index}] must be an object")
        for name in ("artifact_id", "run_id", "category", "stage", "logical_path"):
            if not isinstance(artifact.get(name), str) or not artifact[name]:
                raise ContractError(f"source_artifacts[{index}].{name} is required")
        validate_identifier(f"source_artifacts[{index}].artifact_id", artifact["artifact_id"])
        validate_identifier(f"source_artifacts[{index}].run_id", artifact["run_id"])
        validate_identifier(f"source_artifacts[{index}].attempt_id",
                           artifact.get("attempt_id"), required=False)
        validate_sha256(f"source_artifacts[{index}].sha256", artifact.get("sha256"))
        validate_relative_path(f"source_artifacts[{index}].logical_path",
                               artifact["logical_path"], container="artifact store")
        if not isinstance(artifact.get("size_bytes", 0), int) or artifact.get("size_bytes", 0) < 0:
            raise ContractError(f"source_artifacts[{index}].size_bytes is invalid")
    return {**snapshot, "schema_version": version, "source_artifacts": artifacts}


def _record_id(record_type: str, row: Mapping[str, Any], ordinal: int) -> str:
    names = {
        "entities": "object_id", "observations": "observation_id",
        "relations": "relation_id", "timing_paths": "path_id",
        "timing_points": "point_id", "physical_context": "object_id",
        "stages": "stage_id",
    }
    key = names[record_type]
    value = row.get(key)
    if not isinstance(value, str) or not value:
        raise ContractError(f"{record_type}[{ordinal}].{key} is required")
    return value


def _counts(records: Iterable[tuple[str, str, int, str]]) -> dict[str, int]:
    result = {name: 0 for name in RECORD_TYPES}
    for record_type, _record_id, _ordinal, _payload in records:
        result[record_type] += 1
    return result
