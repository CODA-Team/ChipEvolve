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

from pathlib import Path

from .queries import _limit, _offset, _page

from eda_toolkits.openroad.spef import spef_index, _read_block, _parse_block

def _spef_artifacts(snapshot: dict) -> list[dict]:
    return [ref for ref in snapshot.get("source_artifacts", [])
            if isinstance(ref, dict) and ref.get("category") == "raw_parasitics"]


def _artifact_evidence(ref: dict, locator: dict | None = None) -> dict:
    return {key: ref.get(key) for key in
            ("artifact_id", "run_id", "attempt_id", "category", "stage",
             "logical_path", "sha256", "size_bytes")} | {"locator": locator or {}}


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
