"""SPEF native decoding, verified indexing and bounded net-record parsing."""
from __future__ import annotations
import hashlib
import threading
import time
from array import array
from collections import OrderedDict
from pathlib import Path

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


