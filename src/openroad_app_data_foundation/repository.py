"""Storage for immutable design context snapshots.

The service stores derived facts, never the original run files. Every record
keeps the artifact evidence references supplied by its producer.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from functools import partial
from pathlib import Path
from typing import Any

from openroad_platform_contracts import (
    ContractError,
    SCHEMA_VERSION,
    validate_identifier,
    validate_relative_path,
    validate_sha256,
)

from .ingest import PairedRows
from .identity import (
    _entity_rows,
    ambiguous_keys,
    enrich_records,
    entity_row,
    physical_row,
    point_reference_ids,
    row_identity,
)
from .evidence import materialize


#: Rows written per statement during import.  Large enough that the
#: per-statement overhead disappears, small enough that a 189k-instance
#: routing stage never holds its whole serialised form in memory.
IMPORT_BATCH_ROWS = 20000


#: How many neighbours one net context expands.  Power nets in a large design have
#: hundreds of thousands of loads; the bound is reported, never applied silently.
CONNECTED_ENTITY_LIMIT = 2000

RECORD_TYPES = (
    "stages", "entities", "observations", "relations", "timing_paths",
    "timing_points", "physical_context",
)


class _MaterialisedCursor:
    """Rows that were fetched while the connection lock was held.

    Handing back a live sqlite3 cursor would leave a race: the lock is released
    when ``execute`` returns, and another request thread running a statement on
    the shared connection invalidates the first cursor's results.  That is not
    theoretical - it surfaced as ``row["payload"]`` being None and as a snapshot
    that exists answering "snapshot not found" under concurrent callers.
    """

    def __init__(self, rows: list[Any], rowcount: int, lastrowid: int | None) -> None:
        self._rows = rows
        self.rowcount = rowcount
        self.lastrowid = lastrowid

    def fetchone(self) -> Any:
        return self._rows[0] if self._rows else None

    def fetchall(self) -> list[Any]:
        return list(self._rows)

    def __iter__(self) -> Any:
        return iter(self._rows)

    def __len__(self) -> int:
        return len(self._rows)


class _LockedConnection:
    """A sqlite3 connection shared by ThreadingHTTPServer request threads.

    ``check_same_thread=False`` permits cross-thread use but not *simultaneous*
    use: two request threads touching the connection at once raise
    ``sqlite3.InterfaceError: bad parameter or other API misuse``.  That is how a
    net-context request died mid-flight and answered a misleading error, and it is
    reachable by any two callers that overlap - this interface is a local service
    with a threaded server, so overlap is normal.  Statements take the lock;
    cursors are consumed immediately by every call site, so serialising statements
    is enough, and the transaction context manager holds it for the whole block.
    """

    def __init__(self, connection: sqlite3.Connection, lock: "threading.RLock") -> None:
        object.__setattr__(self, "_connection", connection)
        object.__setattr__(self, "_lock", lock)

    def execute(self, *args: Any, **kwargs: Any) -> _MaterialisedCursor:
        with self._lock:
            cursor = self._connection.execute(*args, **kwargs)
            # read the rows out while nothing else can touch the connection
            rows = cursor.fetchall()
            return _MaterialisedCursor(rows, cursor.rowcount, cursor.lastrowid)

    def executemany(self, *args: Any, **kwargs: Any) -> sqlite3.Cursor:
        with self._lock:
            return self._connection.executemany(*args, **kwargs)

    def executescript(self, *args: Any, **kwargs: Any) -> Any:
        with self._lock:
            return self._connection.executescript(*args, **kwargs)

    def __enter__(self) -> "_LockedConnection":
        self._lock.acquire()
        try:
            self._connection.__enter__()
        except BaseException:
            self._lock.release()
            raise
        return self

    def __exit__(self, *exc_info: Any) -> Any:
        try:
            return self._connection.__exit__(*exc_info)
        finally:
            self._lock.release()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._connection, name)

    def __setattr__(self, name: str, value: Any) -> None:
        setattr(self._connection, name, value)


class DataStore:
    """A local snapshot store owned by this application."""

    def __init__(self, path: str | Path, *, read_only: bool = False):
        """Open the store.  ``read_only`` is for serving threads only.

        A read-only connection is opened through SQLite's URI form, which refuses
        every write at the driver level, and skips the schema script: creating
        tables is a write, and N serving threads doing it on every connection
        would reintroduce the serialisation they exist to remove.
        """
        self._lock = threading.RLock()
        self.read_only = read_only
        #: Kept so a server can hand the same file to a pool of reader connections.
        self.path = str(path)
        if read_only:
            target = f"file:{path}?mode=ro"
        else:
            target = str(path)
        connection = sqlite3.connect(target, check_same_thread=False, uri=read_only)
        if not read_only:
            # The default is 5 s.  With several read-only services on the same file
            # under a rollback journal, a writer's COMMIT can wait longer than that
            # and fail - which is how an import lost its fragment payloads.  Waiting
            # for the readers is the correct behaviour; the alternative is a
            # half-written snapshot.
            connection.execute("PRAGMA busy_timeout = 600000")
        self.connection = _LockedConnection(connection, self._lock)
        self.connection.row_factory = sqlite3.Row
        # A large design is tens of gigabytes, and the default page cache is 2 MiB:
        # a two-line query could wait on a cold read of a file the kernel had long
        # since evicted.  These are per-connection settings, not a schema change.
        # One statement each, not executescript: a script opens a transaction and
        # a read-only connection cannot take the write lock it wants, so under
        # concurrent readers it failed with "database is locked" and the service
        # dropped the connection instead of answering.
        for pragma in ("PRAGMA cache_size = -262144",      # 256 MiB page cache
                       "PRAGMA mmap_size = 8589934592",     # let the kernel page it in
                       "PRAGMA temp_store = MEMORY"):
            self.connection.execute(pragma)
        #: A snapshot is immutable once registered, so its catalogue and artifact
        #: list - the two things a record's evidence resolves against - are read
        #: once per process instead of once per row.
        self._snapshot_cache: dict[str, dict[str, Any]] = {}
        #: Counts for an immutable snapshot cannot change; paging re-asked for the
        #: same one on every page.
        self._count_cache: dict[tuple[Any, ...], int] = {}
        if read_only:
            return
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
            -- JSON members the bundle already carries, kept so a caller can read
            -- the *fragment* a fact came from.  The execution foundation refuses
            -- artifacts over 4 MiB, so reading a whole file is not always possible;
            -- a fragment usually is, and it is what a verifier actually needs.
            CREATE TABLE IF NOT EXISTS fragment_sources (
                snapshot_id TEXT NOT NULL,
                logical_path TEXT NOT NULL,
                sha256 TEXT,
                payload BLOB NOT NULL,
                PRIMARY KEY(snapshot_id, logical_path),
                FOREIGN KEY(snapshot_id) REFERENCES snapshots(snapshot_id)
            );
            -- Every one of these indexes used to carry an entry for *every* record
            -- in the table, because SQLite stores a NULL key like any other.  On
            -- Ibex that was 1.76 GB of index for 2.95 GB of payload, and
            -- records_json_hier_name (206 MB) indexed a field that exactly one row
            -- out of 2.37 M populates.  A partial index keeps the entry only where
            -- the field exists, and `json_extract(...) = ?` provably implies
            -- `json_extract(...) IS NOT NULL`, so the planner still uses them.
            CREATE INDEX IF NOT EXISTS records_json_name
                ON records(snapshot_id, record_type,
                           json_extract(payload, '$.name'))
                WHERE json_extract(payload, '$.name') IS NOT NULL;
            CREATE INDEX IF NOT EXISTS records_json_subject
                ON records(snapshot_id, record_type,
                           json_extract(payload, '$.subject_id'))
                WHERE json_extract(payload, '$.subject_id') IS NOT NULL;
            CREATE INDEX IF NOT EXISTS records_json_object
                ON records(snapshot_id, record_type,
                           json_extract(payload, '$.object_id'))
                WHERE json_extract(payload, '$.object_id') IS NOT NULL;
            CREATE INDEX IF NOT EXISTS records_json_parent
                ON records(snapshot_id, record_type,
                           json_extract(payload, '$.parent_id'))
                WHERE json_extract(payload, '$.parent_id') IS NOT NULL;
            CREATE INDEX IF NOT EXISTS records_json_path
                ON records(snapshot_id, record_type,
                           json_extract(payload, '$.path_id'))
                WHERE json_extract(payload, '$.path_id') IS NOT NULL;
            -- Object filters must not parse every pin/net payload to find
            -- instances, or every instance to find a small macro inventory.
            CREATE INDEX IF NOT EXISTS records_entity_kind
                ON records(snapshot_id, record_type,
                           json_extract(payload, '$.kind'), ordinal)
                WHERE record_type = 'entities';
            CREATE INDEX IF NOT EXISTS records_entity_macro
                ON records(snapshot_id, record_type,
                           json_extract(payload, '$.attributes.is_macro'), ordinal)
                WHERE record_type = 'entities'
                  AND json_extract(payload, '$.attributes.is_macro') IS NOT NULL;
            CREATE INDEX IF NOT EXISTS records_instance_statistics
                ON records(snapshot_id, json_extract(payload, '$.attributes.is_macro'))
                WHERE record_type = 'entities' AND json_extract(payload, '$.kind') = 'instance';
            CREATE INDEX IF NOT EXISTS records_net_statistics
                ON records(snapshot_id, json_extract(payload, '$.attributes.signal_type'))
                WHERE record_type = 'entities' AND json_extract(payload, '$.kind') = 'net';
            CREATE INDEX IF NOT EXISTS records_physical_bbox
                ON records(snapshot_id, record_type, record_id,
                           json_extract(payload, '$.bbox.x_max'),
                           json_extract(payload, '$.bbox.y_max'),
                           json_extract(payload, '$.bbox.x_min'),
                           json_extract(payload, '$.bbox.y_min'))
                WHERE record_type = 'physical_context'
                  AND json_extract(payload, '$.bbox.x_min') IS NOT NULL;
            -- Not dead code: an adapter that starts populating
            -- attributes.hierarchical_name needs this index to exist, and the
            -- name lookup below reads it.  Today it holds a single entry.
            -- A ranking is a scan without this.  Measured on ariane136 before it
            -- existed: `?kind=net&sort=fanout&order=desc&limit=5` took **5.2 s**
            -- every time, because SQLite had to evaluate fanout on every row and
            -- sort.  Only nets carry a fanout, so the partial index stays small.
            CREATE INDEX IF NOT EXISTS records_json_fanout
                ON records(snapshot_id, record_type,
                           json_extract(payload, '$.attributes.fanout') DESC)
                WHERE json_extract(payload, '$.attributes.fanout') IS NOT NULL;
            CREATE INDEX IF NOT EXISTS records_json_hier_name
                ON records(snapshot_id, record_type,
                           json_extract(payload,
                                        '$.attributes.hierarchical_name'))
                WHERE json_extract(payload,
                                   '$.attributes.hierarchical_name') IS NOT NULL;
            """
        )
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def register(self, pack: Mapping[str, Any], *,
                 artifact_id: str | None = None) -> dict[str, Any]:
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
        streams: dict[str, Sequence[dict[str, Any]]] = {}
        for record_type in RECORD_TYPES:
            values = pack.get(record_type, [])
            if not isinstance(values, Sequence):
                raise ContractError(f"{record_type} must be a list")
            streams[record_type] = values
        # Evidence is stored compact (source_ref + locator) and resolved on read;
        # see evidence.materialize.  Resolving it here is what inflated every row.
        #
        # A bundle read by ingest hands its physical records over paired with the
        # entities they belong to, and its timing points are enriched from a map
        # of the ids they actually reference.  That leaves the import holding the
        # keys an ambiguous identity needs (0.73 GiB on ariane136) instead of every
        # identity of the snapshot (2.63 GiB) - the difference between a peak of
        # 3.87 GiB and one near the native extraction's own 0.94 GiB.  A snapshot
        # posted as plain lists has no file to walk beside it and keeps the whole
        # index, which is what it always did.
        paired = isinstance(streams["physical_context"], PairedRows)
        identity_index: dict[str, dict[str, Any]] = {}
        ambiguous: dict[tuple[Any, ...], list[str]] = {}
        wanted: set[str] = set()
        entity_map: dict[str, dict[str, Any]] = {}
        if paired:
            ambiguous = ambiguous_keys(snapshot, streams["entities"])
            wanted = point_reference_ids(streams["timing_points"])
        else:
            identity_index = _entity_rows(snapshot, streams["entities"])

        def enrich(record_type: str, batch: list[dict[str, Any]]) -> Iterable[dict[str, Any]]:
            """Enrich one batch of one record type, reusing identity.py's rules."""
            if record_type == "entities" and paired:
                for row in batch:
                    identity = row_identity(snapshot, row, ambiguous)
                    if identity is not None and row.get("object_id") in wanted:
                        entity_map[row["object_id"]] = identity
                    yield entity_row(row, identity)
                return
            index = entity_map if record_type == "timing_points" and paired else identity_index
            yield from enrich_records(snapshot, record_type, batch, None, identity_index=index)

        # Every record type is read, enriched, serialised and written in bounded
        # batches, and released before the next one is read.  Holding the whole
        # stage - as parsed rows, as enriched rows, or as one list of every
        # serialised row - is what made an ariane136 stage need ~36 GB of RSS:
        # memory proportional to the design rather than to the batch.
        #
        # A duplicate identity used to be caught by a set holding every
        # (record_type, record_id) of the snapshot.  The primary key of `records`
        # is the same constraint, so the writer relies on it instead of keeping a
        # second copy of every identity in memory to re-check it.
        #
        # A snapshot is immutable, so its record counts are computed once and
        # stored with it.  Recomputing them per request turned a run summary into 70
        # COUNT scans over tens of millions of rows - and because one request holds
        # the service lock, asking for a run summary blocked every other caller.
        # A streamed import only knows the counts once every row has been written,
        # so they are folded into the snapshot row at the end of the transaction.
        counts = {name: 0 for name in RECORD_TYPES}
        insert = ("INSERT INTO records(snapshot_id, record_type, record_id, ordinal, "
                  "payload) VALUES (?, ?, ?, ?, ?)")
        try:
            with self.connection:
                self.connection.execute(
                    "INSERT INTO snapshots(snapshot_id, payload) VALUES (?, ?)",
                    (snapshot_id, json.dumps(snapshot, ensure_ascii=False, sort_keys=True)),
                )
                for record_type in RECORD_TYPES:
                    if record_type == "physical_context" and paired:
                        counts[record_type] = self._write_pairs(
                            snapshot_id, snapshot, streams[record_type], ambiguous, insert)
                        continue
                    counts[record_type] = self._write_records(
                        snapshot_id, record_type, streams[record_type],
                        partial(enrich, record_type), insert)
                snapshot = {**snapshot, "record_counts": counts}
                self.connection.execute(
                    "UPDATE snapshots SET payload = ? WHERE snapshot_id = ?",
                    (json.dumps(snapshot, ensure_ascii=False, sort_keys=True), snapshot_id))
                if artifact_id is not None:
                    # Same transaction as the snapshot: either both are visible or
                    # neither is, so a retry after a crash is always well defined.
                    self.connection.execute(
                        "INSERT INTO imported_artifacts(artifact_id) VALUES (?)",
                        (artifact_id,))
                # Inside the transaction, not after it.  This used to run on its
                # own afterwards, and an import that hit "database is locked" on
                # that second write left a snapshot that was complete, an artifact
                # marked imported and fragment_sources empty - and the next run
                # skipped it silently because imported() was already true.
                self._write_fragment_rows(snapshot_id, pack)
        except sqlite3.IntegrityError as exc:
            # Since the snapshot, its records and its artifact identity share one
            # transaction, an integrity error can come from any of them; naming the
            # wrong one sends whoever is on call to the wrong table.
            detail = str(exc)
            if "imported_artifacts" in detail:
                raise ContractError(f"artifact already imported: {artifact_id}") from exc
            if "records" in detail:
                raise ContractError(
                    f"duplicate record identity in {snapshot_id}") from exc
            raise ContractError(f"snapshot already exists: {snapshot_id}") from exc
        return {"snapshot": snapshot, "record_counts": counts}

    def _write_records(self, snapshot_id: str, record_type: str,
                       values: Sequence[dict[str, Any]],
                       enrich: Callable[[list[dict[str, Any]]], Iterable[dict[str, Any]]],
                       insert: str) -> int:
        """Read, enrich, write and release one record type in bounded batches.

        ``values`` is a list or a stream (:class:`ingest.JsonlRows`); both are
        walked one batch at a time, so what is resident is the batch, never the
        stage.  Returns the number of rows written.
        """
        written = 0
        batch: list[dict[str, Any]] = []
        for ordinal, value in enumerate(values):
            batch.append(_object(value, f"{record_type}[{ordinal}]"))
            if len(batch) >= IMPORT_BATCH_ROWS:
                written = self._write_batch(snapshot_id, record_type, batch, written,
                                            enrich, insert)
                batch = []
        if batch:
            written = self._write_batch(snapshot_id, record_type, batch, written,
                                        enrich, insert)
        return written

    def _write_pairs(self, snapshot_id: str, snapshot: Mapping[str, Any],
                     pairs: Iterable[tuple[dict[str, Any], dict[str, Any]]],
                     ambiguous: Mapping[tuple[Any, ...], list[str]],
                     insert: str) -> int:
        """Write physical records whose entities are read beside them.

        The identity of a physical record is the identity of the entity at the
        same position in the objects file, so it never needs a map of the whole
        snapshot - only the keys an ambiguous identity would have to be marked
        with, which is what `ambiguous` holds.
        """
        written = 0
        batch: list[dict[str, Any]] = []
        for entity, physical in pairs:
            batch.append(physical_row(physical, row_identity(snapshot, entity, ambiguous)))
            if len(batch) >= IMPORT_BATCH_ROWS:
                written = self._write_batch(snapshot_id, "physical_context", batch,
                                            written, _as_given, insert)
                batch = []
        if batch:
            written = self._write_batch(snapshot_id, "physical_context", batch,
                                        written, _as_given, insert)
        return written

    def _write_batch(self, snapshot_id: str, record_type: str,
                     batch: list[dict[str, Any]], ordinal: int,
                     enrich: Callable[[list[dict[str, Any]]], Iterable[dict[str, Any]]],
                     insert: str) -> int:
        """Enrich, serialise and insert one batch; returns the next ordinal."""
        rows = list(enrich(batch))
        self.connection.executemany(insert, [
            (snapshot_id, record_type, _record_id(record_type, row, ordinal + offset),
             ordinal + offset, json.dumps(row, ensure_ascii=False, sort_keys=True))
            for offset, row in enumerate(rows)
        ])
        return ordinal + len(rows)

    #: members worth keeping for fragment reads: parseable JSON that evidence
    #: points into.  The binary database is deliberately absent - the adapter
    #: already extracted its facts, and the file itself is both unparseable here
    #: and over the download cap.
    FRAGMENT_PATHS = ("query-data/timing_report.json",
                      "query-data/timing_report_hold.json",
                      "query-data/dbnetwork_map.json")

    def store_fragments(self, snapshot_id: str, values: Mapping[str, Any]) -> int:
        stored = 0
        with self.connection:
            for logical_path in self.FRAGMENT_PATHS:
                payload = values.get(logical_path)
                if not isinstance(payload, bytes):
                    continue
                self.connection.execute(
                    "INSERT OR REPLACE INTO fragment_sources"
                    "(snapshot_id, logical_path, sha256, payload) VALUES (?, ?, ?, ?)",
                    (snapshot_id, logical_path, hashlib.sha256(payload).hexdigest(),
                     sqlite3.Binary(payload)))
                stored += 1
        return stored

    def fragment_source(self, snapshot_id: str,
                        logical_path: str) -> dict[str, Any] | None:
        self.snapshot(snapshot_id)
        row = self.connection.execute(
            "SELECT sha256, payload FROM fragment_sources"
            " WHERE snapshot_id = ? AND logical_path = ?",
            (snapshot_id, logical_path)).fetchone()
        if row is None:
            return None
        return {"sha256": row["sha256"], "payload": bytes(row["payload"])}

    def _write_fragment_rows(self, snapshot_id: str,
                             pack: Mapping[str, Any]) -> None:
        """Insert fragment payloads on the caller's connection and transaction."""
        values = pack.get("fragment_sources")
        if not isinstance(values, dict) or not values:
            return
        for logical_path in self.FRAGMENT_PATHS:
            payload = values.get(logical_path)
            if not isinstance(payload, bytes):
                continue
            self.connection.execute(
                "INSERT OR REPLACE INTO fragment_sources"
                "(snapshot_id, logical_path, sha256, payload) VALUES (?, ?, ?, ?)",
                (snapshot_id, logical_path, hashlib.sha256(payload).hexdigest(),
                 sqlite3.Binary(payload)))

    def imported(self, artifact_id: str) -> bool:
        return self.connection.execute(
            "SELECT 1 FROM imported_artifacts WHERE artifact_id = ?", (artifact_id,)
        ).fetchone() is not None

    def mark_imported(self, artifact_id: str) -> None:
        """Record an artifact as seen without importing it (a superseded bundle)."""
        with self.connection:
            self.connection.execute(
                "INSERT OR IGNORE INTO imported_artifacts(artifact_id) VALUES (?)",
                (artifact_id,))

    def register_import(self, artifact_id: str, pack: Mapping[str, Any]) -> dict[str, Any]:
        """Register a snapshot and its artifact identity in one transaction.

        These used to be two: the snapshot committed first, then the artifact id.
        A crash in between leaves a snapshot that exists while `imported()` still
        says no, and every later attempt fails with "snapshot already exists" -
        the artifact can never be imported again.  Fault injection found that; a
        normal run never will.
        """
        return self.register(pack, artifact_id=artifact_id)

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

    def manifest_fingerprint(self) -> dict[str, Any]:
        """A hash over what this store contains, independent of how it is stored.

        The file's sha256 pins exactly which bytes a run read, but it moves when
        nothing anyone would call the data moved: a VACUUM, a page-layout change, an
        appended query snapshot.  This hash covers the snapshots themselves - design,
        revision, run, stage, record counts and artifact digests - ordered so it does
        not depend on row order or insertion sequence.  Both are worth keeping, and
        they answer different questions.
        """
        entries = []
        for snapshot in self.snapshots():
            artifacts = sorted(
                (str(a.get("logical_path")), str(a.get("sha256")), str(a.get("artifact_id")))
                for a in (snapshot.get("source_artifacts") or [])
                if isinstance(a, dict))
            counts = snapshot.get("record_counts") or {}
            entries.append({
                "snapshot_id": snapshot.get("snapshot_id"),
                "design_id": snapshot.get("design_id"),
                "revision_id": snapshot.get("revision_id"),
                "run_id": snapshot.get("run_id"),
                "stage": snapshot.get("stage"),
                "record_counts": {k: counts[k] for k in sorted(counts)} if counts else {},
                "artifacts": artifacts,
            })
        entries.sort(key=lambda e: (e["design_id"] or "", e["revision_id"] or "",
                                    e["stage"] or "", e["snapshot_id"] or ""))
        canonical = json.dumps(entries, sort_keys=True, separators=(",", ":"),
                               ensure_ascii=False).encode()
        return {
            "snapshots": len(entries),
            "designs": sorted({e["design_id"] for e in entries if e["design_id"]}),
            "runs": sorted({e["run_id"] for e in entries if e["run_id"]}),
            "manifest_sha256": hashlib.sha256(canonical).hexdigest(),
        }

    def identity(self) -> dict[str, Any]:
        """What this process is actually serving, for a caller to verify.

        A fingerprint says which build is running.  It does not say which file that
        build opened - and a service restarted against the wrong path answers every
        request perfectly while reading the wrong store.  That is the failure this
        exists to make visible.
        """
        path = Path(self.path)
        stat = path.stat() if path.exists() else None
        return {
            "path": str(path.resolve()) if path.exists() else str(path),
            "bytes": stat.st_size if stat else None,
            "mtime_ns": stat.st_mtime_ns if stat else None,
            "read_only": self.read_only,
            **self.manifest_fingerprint(),
        }

    def run_summary(self, snapshot_id: str) -> dict[str, Any]:
        """Return the run/stage boundary and indexed record counts."""
        snapshot = self.snapshot(snapshot_id)
        # Stored at registration; older snapshots predate the field and still count.
        counts = snapshot.get("record_counts")
        if not isinstance(counts, dict):
            counts = {
                record_type: self._count(snapshot_id, record_type)
                for record_type in RECORD_TYPES
            }
        return {"snapshot": snapshot,
                "run_summary": snapshot.get("run_summary", {}),
                "record_counts": counts,
                "coverage": snapshot.get("coverage", {})}

    def require_run(self, run_id: str) -> list[dict[str, Any]]:
        """The snapshots of a run, or a KeyError if this store never saw it.

        One implementation, called by every run-scoped endpoint.  Two copies of
        this guard drifted apart once already: `/runs/<unknown>/summary` and
        `/runs/<unknown>/metrics` both answered `status: available` with nothing
        in it, which reads like a run whose stages were all skipped rather than a
        run that is not here.
        """
        snapshots = self.snapshots(run_id=run_id)
        if not snapshots:
            raise KeyError(
                f"run not found: {run_id} has no snapshot in this store "
                f"(it may exist in the execution service but was never imported)")
        return snapshots

    def run_summary_for_run(self, run_id: str) -> dict[str, Any]:
        """Return all indexed stage snapshots belonging to one execution run.

        A run this store has never seen used to answer ``status: available`` with an
        empty snapshot list, which reads exactly like a run whose stages were all
        skipped.  An agent asking "what is in run X" could not tell "X does not
        exist here" from "X is empty", and the question bank has cases where the
        right answer is to refuse attribution to another run rather than return
        the nearest thing.  The caller now gets ``run_found`` plus the designs the
        run covers, so attribution is checkable and absence is explicit.
        """
        snapshots = self.require_run(run_id)
        designs: list[str] = []
        revisions: list[str] = []
        for item in snapshots:
            if item.get("design_id") and item["design_id"] not in designs:
                designs.append(item["design_id"])
            if item.get("revision_id") and item["revision_id"] not in revisions:
                revisions.append(item["revision_id"])
        return {"run_id": run_id,
                "run_found": True,
                "design_id": designs[0] if len(designs) == 1 else designs,
                "revision_id": revisions[0] if len(revisions) == 1 else revisions,
                "snapshots": [
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
        """One net plus its connected objects.

        Measured before this bound existed: the power net VDD on ariane136 has
        538,185 loads, and expanding it two indexed queries per neighbour took
        **260 s and 10.7 GiB of RSS**.  A request holds the service lock, so that
        single call stalled every other caller and could not be cancelled.  The
        neighbours are now fetched in batches (one query per 250 ids instead of
        two per id) and bounded, with the bound and the true total stated in the
        payload so a caller can page or ask for one object instead.
        """
        result = self._entity_context(snapshot_id, net_id, "net")
        related_ids = self._related_ids(snapshot_id, net_id)
        result["connected_total"] = len(related_ids)
        if len(related_ids) > CONNECTED_ENTITY_LIMIT:
            result["connected_truncated"] = True
            result["connected_limit"] = CONNECTED_ENTITY_LIMIT
            related_ids = related_ids[:CONNECTED_ENTITY_LIMIT]
        connected = self.entities_by_ids(snapshot_id, related_ids)
        result["connected_entities"] = connected
        result["physical_context"] = self._physical_for_ids(
            snapshot_id, [net_id, *[item["object_id"] for item in connected]])
        return result

    def _catalog_snapshot(self, snapshot_id: str) -> dict[str, Any]:
        cached = self._snapshot_cache.get(snapshot_id)
        if cached is None:
            cached = self.snapshot(snapshot_id)
            self._snapshot_cache[snapshot_id] = cached
        return cached

    def _decode(self, payload: str, snapshot_id: str) -> dict[str, Any]:
        """Read one stored row and restore its full evidence entry."""
        row = materialize(json.loads(payload), self._catalog_snapshot(snapshot_id))
        if row.get('snapshot_id') and row['snapshot_id'] != snapshot_id:
            row['source_snapshot_id'] = row['snapshot_id']
            row['snapshot_id'] = snapshot_id
        return row

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
        return [self._decode(row["payload"], snapshot_id)
                for row in self.connection.execute(query, values)]

    def filtered(self, snapshot_id: str, record_type: str, *, where: str = "",
                 params: Sequence[Any] = (), limit: int | None = None,
                 offset: int = 0, order_by: str = "") -> list[dict[str, Any]]:
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
        if order_by:
            # a ranked question orders by a payload field; the index cannot serve
            # both that and the predicate, so this is a scan of one snapshot's rows
            query += order_by
        elif not where:
            query += " ORDER BY ordinal"
        if limit is not None:
            query += " LIMIT ? OFFSET ?"
            values.extend((limit, offset))
        return [self._decode(row["payload"], snapshot_id)
                for row in self.connection.execute(query, values)]

    def count_records(self, snapshot_id: str, record_type: str, *, where: str = "",
                      params: Sequence[Any] = ()) -> int:
        """Count rows for one snapshot and optional predicate, without scanning.

        The result is cached: a snapshot is immutable, so the count for a given
        predicate cannot change.  Paging the same filter paid the count again on
        every page, and on ariane136 a single ``kind`` count scans 2.4 M rows -
        5 s of every page.  The cache is keyed by the exact SQL and its bound
        parameters, so it can never serve a count for a different filter.
        """
        if record_type not in RECORD_TYPES:
            raise KeyError(f"unsupported record type: {record_type}")
        cache_key = (snapshot_id, record_type, where, tuple(params))
        cached = self._count_cache.get(cache_key)
        if cached is not None:
            return cached
        query = ("SELECT COUNT(*) AS count FROM records "
                 "WHERE snapshot_id = ? AND record_type = ?")
        values: list[Any] = [snapshot_id, record_type]
        if where:
            query += " AND " + where
            values.extend(params)
        row = self.connection.execute(query, values).fetchone()
        result = int(row["count"])
        self._count_cache[cache_key] = result
        return result

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

    def name_candidates(self, snapshot_id: str, name: str, kind: str | None = None) -> list[str]:
        """Use the actual parent spelling for pins with independently escaped local names."""
        variants = name_variants(name)
        if kind in (None, 'pin') and '/' in name:
            parent, _, local = name.rpartition('/')
            for instance in self.entities_named(snapshot_id, 'instance', parent):
                variants.extend(instance['name'] + '/' + value for value in name_variants(local))
        return list(dict.fromkeys(variants))

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
        variants = self.name_candidates(snapshot_id, name, kind)
        marks = ", ".join("?" for _ in variants)
        for where in (f"json_extract(payload, '$.name') IN ({marks})",
                      f"json_extract(payload, "
                      f"'$.attributes.hierarchical_name') IN ({marks})"):
            for row in self.filtered(
                    snapshot_id, "entities",
                    where=f"+json_extract(payload, '$.kind') = ? AND {where}",
                    params=(kind, *variants)):
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

    #: A net's routing list is the whole response: ariane136's worst net carries
    #: 1,970 segments = 310,603 B of 311,733 B, so `/physical/{id}` went past the
    #: caller's 32 KiB read cap and arrived as unreadable JSON.  The first page is
    #: enough to see the shape, and `/nets/{id}/routing-summary` answers "which
    #: layers, how much" from the aggregate rather than from raw shapes.
    ROUTING_PAGE = 100

    def physical(self, snapshot_id: str, object_id: str, *,
                 routing_limit: int | None = None,
                 routing_offset: int = 0) -> dict[str, Any]:
        """One object's physical context, with the routing list paged by default.

        ``routing_limit=0`` means every shape, for callers that aggregate over the
        whole list (``discovery.routing_summary`` counts per layer and per via, so a
        silently shortened list would give a wrong answer rather than a short one).
        """
        rows = self.records(snapshot_id, "physical_context", record_id=object_id, limit=1)
        if not rows:
            raise KeyError(f"physical context not found: {object_id}")
        result = dict(rows[0])
        routing = result.get("routing")
        if not isinstance(routing, list):
            return result
        total = len(routing)
        limit = self.ROUTING_PAGE if routing_limit is None else routing_limit
        result["routing_total"] = total
        if not limit:
            result["routing_returned"] = total - routing_offset
            result["routing"] = routing[routing_offset:]
            return result
        window = routing[routing_offset:routing_offset + limit]
        result["routing"] = window
        result["routing_returned"] = len(window)
        result["routing_offset"] = routing_offset
        if routing_offset + len(window) < total:
            result["routing_truncated"] = True
            result["next_offset"] = routing_offset + len(window)
        result["routing_note"] = (
            "page with ?routing_limit=&routing_offset=; /nets/{id}/routing-summary "
            "gives per-layer totals without the raw shapes")
        return result

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
        """Physical rows for many objects, in batches rather than one query each.

        A net context asks for the physical row of every neighbour.  Issued one at
        a time that was 2,001 point queries for a bounded ariane net context and
        42 s of the request; as 250-id batches it is nine queries.
        """
        ids = [str(item) for item in dict.fromkeys(object_ids)]
        result: list[dict[str, Any]] = []
        for start in range(0, len(ids), 250):
            chunk = ids[start:start + 250]
            marks = ", ".join("?" for _ in chunk)
            result.extend(self.filtered(snapshot_id, "physical_context",
                                        where=f"record_id IN ({marks})", params=chunk))
        return result

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


#: OpenDB reports one name in two legal spellings.  ``getName`` escapes the
#: brackets of a bus bit (``mcountinhibit_q\\[0\\]$_DFFE_PN0P_``) while ``findInst``,
#: the SDC and the independent STA gold use the plain one
#: (``mcountinhibit_q[0]$_DFFE_PN0P_``).  They are the same object, so a lookup
#: accepts the legal spellings instead of making the caller guess the escaping.
#: Only the brackets are escaped in this data - escaping ``$`` as well produced a
#: name that matches nothing.
NAME_ESCAPES = (("[", "\\["), ("]", "\\]"))


def name_variants(name: str) -> list[str]:
    """The given spelling of a name plus the other legal spellings."""
    variants = [name]
    escaped = name
    for plain, quoted in NAME_ESCAPES:
        escaped = escaped.replace(plain, quoted)
    candidates = [escaped, escaped.replace("$", "\\$"), name.replace("\\", "")]
    for candidate in candidates:
        if candidate and candidate not in variants:
            variants.append(candidate)
    return variants


def record_identifier(record_type: str, row: Mapping[str, Any],
                      ordinal: int = 0) -> str:
    """The stable per-record ID of one stored row (same rule as registration)."""
    return _record_id(record_type, row, ordinal)


def _object(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ContractError(f"{name} must be an object")
    return value


def _as_given(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rows that are already final: the paired writer enriches as it reads."""
    return rows


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
