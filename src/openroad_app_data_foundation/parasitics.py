"""Per-net R/C from the flow's own SPEF, indexed on demand.

A routed Ariane-class design has 168,026 ``*D_NET`` records and 12.2 million
capacitor/resistor lines in a 265 MB file.  None of those numbers are in the
indexed store, and copying them into SQLite would be a second copy of the same
file for facts that are already on disk in a format that is trivial to slice.

So this module keeps a *small resident index* instead: the ``*NAME_MAP`` entries
and, for every net, the byte offset of its ``*D_NET`` header.  One query reads
its own record out of the artifact the kernel already holds; the response says
which bytes it read so the caller can re-read them through the existing
``/snapshots/{s}/sources/{a}/excerpt`` route.

SPEF escapes DEF-special characters (``.``, ``[``, ``]``, ``$``) with a
backslash and the ODB/DEF side does not, so every name on both sides of the join
is compared with backslashes stripped - the same normalisation
``qualification/v3/verify_ariane_native.py::_unescape_def`` uses.
"""

from __future__ import annotations

import hashlib
import threading
import time
from array import array
from collections import OrderedDict
from pathlib import Path

from .queries import _limit, _offset, _page

#: Cap on one ``*D_NET`` record.  The largest record seen on ibex/ariane is a
#: few hundred kilobytes; a record that runs past this is reported as truncated
#: rather than silently cut.
MAX_BLOCK_BYTES = 32 * 1024 * 1024
_READ_CHUNK = 1 << 16
_SCAN_CHUNK = 1 << 23
#: Indexes are tens of megabytes each (Ariane: ~40 MB).  Two is enough for the
#: route+finish pair a caller compares, and bounded is better than unbounded.
_MAX_CACHED_INDEXES = 2

_CACHE_LOCK = threading.Lock()
_INDEXES: "OrderedDict[str, SpefIndex]" = OrderedDict()


def _unescape(name: bytes) -> bytes:
    return name.replace(b"\\", b"")


class SpefIndex:
    """``net name -> byte offset`` plus the unit facts a reader must quote."""

    __slots__ = ("path", "sha256", "header", "offsets", "blob", "blob_offsets",
                 "name_map_entries", "resolved_lines", "literal_lines",
                 "duplicate_names", "bytes_scanned", "build_seconds")

    def __init__(self, path, sha256, header, offsets, blob, blob_offsets,
                 name_map_entries, resolved_lines, literal_lines, duplicate_names,
                 bytes_scanned, build_seconds):
        self.path = path
        self.sha256 = sha256
        self.header = header
        self.offsets = offsets
        self.blob = blob
        self.blob_offsets = blob_offsets
        self.name_map_entries = name_map_entries
        self.resolved_lines = resolved_lines
        self.literal_lines = literal_lines
        self.duplicate_names = duplicate_names
        self.bytes_scanned = bytes_scanned
        self.build_seconds = build_seconds

    def node_name(self, token: str) -> str:
        """``*200435:A`` -> ``_10862_:A``; a literal token is returned as-is."""
        if not token.startswith("*"):
            return token
        head, _, pin = token.partition(":")
        if not head[1:].isdigit():
            return token
        slot = int(head[1:]) - 1
        if not 0 <= slot < len(self.blob_offsets) - 1:
            return token
        name = self.blob[self.blob_offsets[slot]:self.blob_offsets[slot + 1]].decode(
            "utf-8", "replace")
        return f"{name}:{pin}" if pin else name

    def stats(self) -> dict:
        return {
            "net_count": len(self.offsets),
            "name_map_entries": self.name_map_entries,
            "name_map_resolved_lines": self.resolved_lines,
            "name_map_literal_lines": self.literal_lines,
            "duplicate_net_names": self.duplicate_names,
            "bytes_scanned": self.bytes_scanned,
            "build_seconds": round(self.build_seconds, 3),
            "sha256": self.sha256,
            "index": "net name -> byte offset of its *D_NET header; the record is "
                     "parsed per query",
        }


def _scan(path: Path, expected_sha256: str | None) -> SpefIndex:
    started = time.monotonic()
    header: dict[str, str] = {}
    blob = bytearray()
    blob_offsets = array("i", [0])
    offsets: dict[str, int] = {}
    resolved = literal = duplicates = 0
    in_map = False
    digest = hashlib.sha256()
    scanned = 0
    base = 0
    tail = b""
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(_SCAN_CHUNK)
            if not chunk:
                break
            digest.update(chunk)
            scanned += len(chunk)
            data = tail + chunk
            start = 0
            while True:
                end = data.find(b"\n", start)
                if end < 0:
                    break
                line = data[start:end]
                line_offset = base + start
                start = end + 1
                if in_map:
                    parts = line.split()
                    if len(parts) == 2 and parts[0][:1] == b"*" and parts[0][1:].isdigit():
                        blob += _unescape(parts[1])
                        blob_offsets.append(len(blob))
                        continue
                    in_map = False
                if line == b"*NAME_MAP":
                    in_map = True
                elif line.startswith(b"*D_NET "):
                    parts = line.split()
                    if len(parts) < 3:
                        continue
                    token = parts[1]
                    slot = (int(token[1:]) - 1
                            if (token[:1] == b"*" and token[1:].isdigit()) else -1)
                    if 0 <= slot < len(blob_offsets) - 1:
                        name = bytes(blob[blob_offsets[slot]:blob_offsets[slot + 1]])
                        resolved += 1
                    else:
                        # A record whose name is not in the map keeps its own
                        # token; the counts in `stats` say how often that happened.
                        name = _unescape(token)
                        literal += 1
                    key = name.decode("utf-8", "replace")
                    if key in offsets:
                        duplicates += 1
                    else:
                        offsets[key] = line_offset
                elif line[:7] in (b"*C_UNIT", b"*R_UNIT", b"*T_UNIT"):
                    parts = line.split()
                    if len(parts) >= 3:
                        header[parts[0][1:].decode()] = f"{parts[1].decode()} {parts[2].decode()}"
                elif line.startswith(b"*DESIGN "):
                    header["design"] = (line.split(b'"')[1].decode("utf-8", "replace")
                                        if b'"' in line else line.split()[1].decode())
            tail = data[start:]
            base += start
    value = digest.hexdigest()
    if expected_sha256 and value != expected_sha256:
        raise ValueError(
            f"SPEF bytes changed after registration: {value} != {expected_sha256}")
    return SpefIndex(path, value, header, offsets, bytes(blob), blob_offsets,
                     len(blob_offsets) - 1, resolved, literal, duplicates, scanned,
                     time.monotonic() - started)


def spef_index(path: Path, expected_sha256: str | None) -> SpefIndex:
    """The resident index for one SPEF file, built once per (path, hash)."""
    key = f"{path}:{expected_sha256}"
    with _CACHE_LOCK:
        cached = _INDEXES.get(key)
        if cached is not None:
            _INDEXES.move_to_end(key)
            return cached
    index = _scan(path, expected_sha256)     # built outside the lock, once
    with _CACHE_LOCK:
        _INDEXES[key] = index
        _INDEXES.move_to_end(key)
        while len(_INDEXES) > _MAX_CACHED_INDEXES:
            _INDEXES.popitem(last=False)
    return index


def _spef_artifacts(snapshot: dict) -> list[dict]:
    return [ref for ref in snapshot.get("source_artifacts", [])
            if isinstance(ref, dict) and ref.get("category") == "raw_parasitics"]


def _artifact_evidence(ref: dict, locator: dict | None = None) -> dict:
    return {key: ref.get(key) for key in
            ("artifact_id", "run_id", "attempt_id", "category", "stage",
             "logical_path", "sha256", "size_bytes")} | {"locator": locator or {}}


def _read_block(path: Path, offset: int) -> tuple[bytes, bool]:
    """The bytes of one ``*D_NET`` record, stopping after its ``*END``."""
    buffer = bytearray()
    with path.open("rb") as stream:
        stream.seek(offset)
        while True:
            chunk = stream.read(_READ_CHUNK)
            if not chunk:
                break
            buffer += chunk
            if b"\n*END" in buffer:
                break
            if len(buffer) >= MAX_BLOCK_BYTES:
                break
    data = bytes(buffer)
    end = data.find(b"\n*END")
    if end < 0:
        return data, True
    return data[:end + len(b"\n*END") + 1], False


def _parse_block(data: bytes) -> dict:
    total = None
    pins, capacitors, resistors = [], [], []
    section = None
    malformed = 0
    for line in data.split(b"\n"):
        if not line:
            continue
        if line.startswith(b"*D_NET"):
            parts = line.split()
            if len(parts) >= 3:
                total = float(parts[2])
            section = None
        elif line == b"*CONN":
            section = "conn"
        elif line == b"*CAP":
            section = "cap"
        elif line == b"*RES":
            section = "res"
        elif line.startswith(b"*END"):
            break
        elif section == "cap":
            parts = line.split()
            if len(parts) == 3:
                capacitors.append((int(parts[0]), parts[1].decode(), None, float(parts[2])))
            elif len(parts) == 4:
                capacitors.append((int(parts[0]), parts[1].decode(), parts[2].decode(),
                                   float(parts[3])))
            else:
                malformed += 1
        elif section == "res":
            parts = line.split()
            if len(parts) == 4:
                resistors.append((int(parts[0]), parts[1].decode(), parts[2].decode(),
                                  float(parts[3])))
            else:
                malformed += 1
        elif section == "conn":
            parts = line.split()
            if len(parts) >= 3:
                pins.append({"node": parts[1].decode(), "direction": parts[2].decode(),
                             "cell_type": parts[4].decode() if len(parts) > 4 else None})
            else:
                malformed += 1
    return {"total_capacitance": total, "pins": pins, "capacitors": capacitors,
            "resistors": resistors, "malformed_lines": malformed}


def _paged(items: list, limit: int, offset: int) -> dict:
    page = items[offset:offset + limit]
    counts = _page(len(items), len(page), limit, offset)
    return {**counts, "total": counts["count"], "items": page}


def net_parasitics(store, client, snapshot_id: str, name: str, query: dict) -> dict:
    """R/C for one net from the SPEF attached to ``snapshot_id``.

    Never answers "unavailable" for a fact that exists on disk: a snapshot with
    no SPEF names the stages of the same design that do have one, and a net that
    is not in the SPEF is reported together with the store's own view of it.
    """
    snapshot = store.snapshot(snapshot_id)
    limit, offset = _limit(query), _offset(query)
    indexed = store.find_net(snapshot_id, name)
    if not indexed:
        indexed = [row for row in store.records(snapshot_id, 'entities', record_id=name, limit=1)
                   if row.get('kind') == 'net']
    requested = name
    if indexed:
        name = indexed[0]['name'].replace('\\', '')
    base = {"snapshot_id": snapshot_id, "net": name,
            "requested_net": requested,
            "indexed_net": bool(indexed),
            "indexed_net_record": indexed[0] if indexed else None,
            "design_id": snapshot["design_id"], "stage": snapshot["stage"]}
    refs = _spef_artifacts(snapshot)
    if len(refs) != 1:
        siblings = [{"snapshot_id": item["snapshot_id"], "stage": item["stage"],
                     "artifact_ids": [ref["artifact_id"] for ref in _spef_artifacts(item)],
                     "logical_paths": [ref["logical_path"] for ref in _spef_artifacts(item)]}
                    for item in store.snapshots(design_id=snapshot["design_id"])
                    if _spef_artifacts(item)]
        return {**base, "parasitics": None,
                "reason": ("snapshot_has_no_parasitics_artifact" if not refs
                           else "multiple_parasitics_artifacts"),
                "searched": {"category": "raw_parasitics",
                             "attached_categories": sorted(
                                 {r.get("category") for r in snapshot.get("source_artifacts", [])})},
                "snapshots_with_parasitics": siblings,
                "truncated": False}
    ref = refs[0]
    if client is None:
        raise ValueError("execution service is not configured")
    locator = client.artifact_locator(ref["run_id"], ref["artifact_id"])
    path = Path(locator["path"])
    index = spef_index(path, ref.get("sha256"))
    stats = index.stats()
    offset_in_file = index.offsets.get(name)
    if offset_in_file is None:
        # A backslash-bearing query name normalises the same way the index key does.
        offset_in_file = index.offsets.get(name.replace("\\", ""))
    if offset_in_file is None:
        return {**base, "parasitics": None, "reason": "net_not_in_spef",
                "spef": _artifact_evidence(ref),
                "spef_index": stats,
                "searched": {"net": name, "compared_as": "DEF-unescaped on both sides"},
                "truncated": False}
    data, block_truncated = _read_block(path, offset_in_file)
    parsed = _parse_block(data)
    capacitors = [{"id": cid, "node": index.node_name(node),
                   "coupled_node": index.node_name(coupled) if coupled else None,
                   "value": value, "coupling": coupled is not None}
                  for cid, node, coupled, value in parsed["capacitors"]]
    resistors = [{"id": rid, "node": index.node_name(node1),
                  "other_node": index.node_name(node2), "value": value}
                 for rid, node1, node2, value in parsed["resistors"]]
    pins = [{**pin, "node": index.node_name(pin["node"])} for pin in parsed["pins"]]
    ground = sum(item["value"] for item in capacitors if not item["coupling"])
    coupling = sum(item["value"] for item in capacitors if item["coupling"])
    values = [item["value"] for item in resistors]
    capacitors_page = _paged(capacitors, limit, offset)
    resistors_page = _paged(resistors, limit, offset)
    pins_page = _paged(pins, limit, offset)
    return {**base,
            "parasitics": {
                "present": True,
                "artifact": _artifact_evidence(ref),
                "units": {"capacitance": index.header.get("C_UNIT"),
                          "resistance": index.header.get("R_UNIT"),
                          "time": index.header.get("T_UNIT")},
                "summary": {
                    "total_capacitance": parsed["total_capacitance"],
                    "ground_capacitance": ground,
                    "coupling_capacitance": coupling,
                    "capacitance_sum": ground + coupling,
                    "resistance_sum": sum(values),
                    "resistance_min": min(values) if values else None,
                    "resistance_max": max(values) if values else None,
                    "capacitor_count": len(capacitors),
                    "ground_capacitor_count": sum(1 for item in capacitors
                                                  if not item["coupling"]),
                    "coupling_capacitor_count": sum(1 for item in capacitors
                                                    if item["coupling"]),
                    "resistor_count": len(resistors),
                    "pin_count": len(pins),
                    "internal_node_count": len({item["node"] for item in capacitors}
                                               | {item["coupled_node"] for item in capacitors
                                                  if item["coupled_node"]} - set(
                                                      pin["node"] for pin in pins)),
                    "resistance_basis": "sum of the SPEF *RES branch resistances, not an "
                                        "equivalent resistance between two terminals",
                    "capacitance_basis": "SPEF *D_NET header total; ground + coupling is "
                                         "the sum of the record's own *CAP lines",
                    "malformed_lines": parsed["malformed_lines"]},
                "pins": pins_page,
                "capacitors": capacitors_page,
                "resistors": resistors_page,
                "record": {"offset": offset_in_file, "bytes": len(data),
                           "block_truncated": block_truncated},
            },
            "spef": _artifact_evidence(ref, {
                "kind": "spef_record", "offset": offset_in_file, "bytes": len(data),
                "path": str(path),
                "excerpt_route": f"/snapshots/{snapshot_id}/sources/"
                                 f"{ref['artifact_id']}/excerpt"}),
            "spef_index": stats,
            "evidence": [_artifact_evidence(ref, {
                "kind": "spef_record", "offset": offset_in_file, "bytes": len(data),
                "excerpt_route": f"/snapshots/{snapshot_id}/sources/"
                                 f"{ref['artifact_id']}/excerpt"})],
            "truncated": bool(block_truncated or capacitors_page["truncated"]
                              or resistors_page["truncated"] or pins_page["truncated"])}
