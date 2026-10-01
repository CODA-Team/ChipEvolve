"""Native files the flow wrote that no bundle ever carried.

The snapshot catalogue answers "what did the interface stage"; the flow's own
tree answers "what did the tool actually write".  Those differ, and the
difference is where the answers to the DRC/congestion and final-artifact
identity questions live:

* ``reports/nangate45/<design>/<variant>/5_route_drc.rpt`` - 101 violations at
  detailed-route iteration 5, and an empty final report because iteration 64
  routed clean.  Both are facts; the aggregate count keeps neither.
* ``reports/.../congestion-5.rpt`` + ``congestion-10.rpt`` - 14 violations with
  their nets, layers and bboxes.
* ``results/.../6_final.def|gds|v`` - identity and SHA-256 for the final
  artifacts, which the OpenROAD adapter never staged (it stages the ODB).

The flow root is deployment configuration (``--native-root``), and the
directory for a snapshot is found by the ORFS layout itself -
``<root>/<results|reports|logs>/*/<design_id>/<revision_id>`` - so nothing here
knows a design, a platform or a tool name.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from functools import lru_cache
from pathlib import Path

from .queries import _limit, _offset, _page

#: Where an ORFS flow tree lives on this host.  Override with
#: ``--native-root`` or ``OPENROAD_NATIVE_ROOT``; a different deployment has a
#: different path, which is why it is configuration and not a constant.
DEFAULT_NATIVE_ROOT = Path(
    os.environ.get("OPENROAD_NATIVE_ROOT")
    or "/home/wjyuan/projects/orfs-current/OpenROAD-flow-scripts/flow")

#: The three subtrees a flow run writes into, in the order a caller reads them.
NATIVE_KINDS = ("results", "reports", "logs")


def _receipt_files(snapshot, root):
    directory = root.parent.parent / 'experiments' / snapshot['revision_id']
    names = (snapshot['design_id'] + '.flow.log', snapshot['design_id'] + '.native_manifest.json',
             'toolchain.json', 'status.txt')
    return {f'receipts/{name}': directory / name for name in names if (directory / name).is_file()}

#: Report families the flow emits per run.  ``prefix`` matches the file name
#: the tool writes; ``final`` is the file ORFS leaves in place when it finishes.
REPORT_FAMILIES = {
    "drc": {"prefix": "5_route_drc", "final": "5_route_drc.rpt",
            "tool": "detailed_route -output_drc"},
    "congestion": {"prefix": "congestion", "final": None,
                   "tool": "global_route -congestion_report_file"},
    "antenna": {"prefix": "drt_antennas", "final": None,
                "tool": "detailed_route antenna check"},
}

_BBOX = re.compile(
    r"bbox = \(\s*(-?[\d.]+),\s*(-?[\d.]+)\)\s*-\s*\((-?[\d.]+),\s*(-?[\d.]+)\)"
    r"\s*(?:on Layer (\S+))?")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _run_dirs(snapshot: dict, root: Path) -> dict:
    """``<root>/<kind>/*/<design_id>/<revision_id>`` for one snapshot."""
    design, revision = snapshot["design_id"], snapshot["revision_id"]
    directories = {}
    for kind in NATIVE_KINDS:
        candidates = sorted(
            str(path) for path in (root / kind).glob(f"*/{design}/{revision}") if path.is_dir())
        directories[kind] = {"path": candidates[0] if candidates else None,
                             "candidate_count": len(candidates), "candidates": candidates}
    return directories


def _native_file(path: Path, relative: str) -> dict:
    stat = path.stat()
    return {"relative_path": relative, "size_bytes": stat.st_size,
            "modified": int(stat.st_mtime)}


def _metric_inventory(store, snapshot_id, path, root, manifest, metric_names=()):
    relative = path.relative_to(root).as_posix()
    text, offset = [], 0
    while True:
        page = native_excerpt(store, snapshot_id,
            {'path': relative, 'offset': str(offset), 'max_bytes': '65536'}, Path(root))
        text.append(page['text'])
        if page['next_offset'] is None:
            break
        offset = page['next_offset']
    metrics = json.loads(''.join(text))
    if not isinstance(metrics, dict):
        raise ValueError('original metric JSON must be an object')
    result = {'relative_path': relative, 'size_bytes': path.stat().st_size,
            **manifest.get(relative, {}), 'source': page['source'], 'key_count': len(metrics),
            'has_timing': any('timing__' in key for key in metrics),
            'has_area': any('instance__area' in key for key in metrics),
            'has_wirelength': any('wirelength' in key for key in metrics)}
    if metric_names:
        result['metric_values'] = [{'raw_key': key, 'value': value, 'source': relative}
            for key, value in metrics.items()
            if any(key == name or '__' + name + '__' in '__' + key + '__' for name in metric_names)]
        result['value_basis'] = 'literal original report values; substage identity is preserved'
        result['metric_selector_basis'] = 'exact raw key or consecutive namespace components; all matching corners retained'
        result['unit_declarations'] = {key: value for key, value in metrics.items()
                                       if '__flow__platform__' in key and key.endswith('_units')}
        log = path.with_suffix('.log')
        if any('timing__' in item['raw_key'] for item in result['metric_values']) and log.is_file():
            from .source_search import search_source
            result['analysis_command_excerpt'] = search_source(store, snapshot_id,
                {'path': log.relative_to(root).as_posix(),
                 'pattern': r'^\s*(estimate_parasitics|read_spef|read_liberty|read_sdc|read_db)\b',
                 'limit': '10000'}, root)
    return result


def run_inventory(store, snapshot_id, root, *, stage=None, metric_names=()):
    """Original flow outputs and metric availability, separately from indexed snapshots."""
    snapshot = store.snapshot(snapshot_id)
    directories = _run_dirs(snapshot, Path(root))
    indexed = store.snapshots(run_id=snapshot['run_id'])
    query_ids = {s['snapshot_id'] for s in indexed
                 if s.get('run_summary', {}).get('timing_context', {}).get('parent_snapshot_id')
                 or re.search(r'-query-[0-9a-f]{12}$', s['snapshot_id'])}
    query_count = len(query_ids)
    indexed = [s for s in indexed if s['snapshot_id'] not in query_ids]
    stages = []
    outputs = [('synth', '1_synth.odb', '1_synth.json'),
               ('floorplan', '2_floorplan.odb', '2_1_floorplan.json'),
               ('place', '3_place.odb', '3_5_place_dp.json'),
               ('cts', '4_cts.odb', '4_1_cts.json'),
               ('route', '5_route.odb', '5_2_route.json'),
               ('finish', '6_final.odb', '6_report.json')]
    if stage is not None and stage not in {row[0] for row in outputs}:
        raise ValueError('unknown original flow stage')
    producer = snapshot.get('run_summary', {}).get('timing_context', {}).get('producer', {})
    manifest = producer.get('artifacts', {})
    for stage_name, odb, metric in outputs:
        if stage is not None and stage_name != stage:
            continue
        item = {'stage': stage_name, 'original_database': None, 'original_metrics': None,
                'indexed_snapshots': [s['snapshot_id'] for s in indexed if s['stage'] == stage_name]}
        for category, name, field in [('results', odb, 'original_database'),
                                       ('logs', metric, 'original_metrics')]:
            directory = directories[category]['path']
            path = Path(directory) / name if directory else None
            if path is None or not path.is_file():
                continue
            relative = path.relative_to(root).as_posix()
            item[field] = {'relative_path': relative, 'size_bytes': path.stat().st_size,
                           **manifest.get(relative, {})}
            if category == 'logs':
                item[field] = _metric_inventory(store, snapshot_id, path, root, manifest, metric_names)
        directory = directories['logs']['path']
        item['metric_reports'] = []
        if directory is not None:
            for path in sorted(Path(directory).glob(odb.split('_', 1)[0] + '_*.json')):
                if path.name == metric and item['original_metrics'] is not None:
                    entry = item['original_metrics']
                else:
                    entry = _metric_inventory(store, snapshot_id, path, root, manifest, metric_names)
                item['metric_reports'].append(entry)
        item['availability'] = 'available' if item['original_database'] else 'not_produced'
        stages.append(item)
    return {'snapshot_id': snapshot_id, 'run_id': snapshot['run_id'], 'stages': stages,
            'additional_query_snapshot_count': query_count,
            'additional_query_snapshots_path': '/snapshots?run_id=' + snapshot['run_id'],
            'indexed_snapshot_scope': 'original stage indexes; separately created timing queries are counted above and remain in the snapshot catalog',
            'evidence': [report['source'] for item in stages for report in item['metric_reports']],
            'original_stage_count': sum(s['availability'] == 'available' for s in stages),
            'coverage_rule': 'original files determine availability; missing index does not mean missing original',
            'metric_report_rule': 'all original stage JSON reports are listed separately; earlier substage values do not replace the representative stage report',
            'native_manifest': {'native_run_id': producer.get('native_run_id'),
                                'toolchain': producer.get('toolchain')}}


@lru_cache(maxsize=64)
def _file_digest(path: str, size: int, modified_ns: int) -> str:
    return _sha256(Path(path))


def native_excerpt(store, snapshot_id: str, query: dict, root: Path) -> dict:
    """Read any original file of this run, including files never staged by an adapter."""
    snapshot = store.snapshot(snapshot_id)
    requested = query.get('path')
    if not requested:
        raise ValueError('path must name a file returned by artifacts/files')
    root = root.resolve()
    receipts = _receipt_files(snapshot, root)
    path = (receipts[requested] if requested in receipts else root / requested).resolve()
    directories = _run_dirs(snapshot, root)
    allowed = [Path(row['path']).resolve() for row in directories.values() if row['path']]
    producer = snapshot.get('run_summary', {}).get('timing_context', {}).get('producer', {})
    declared = producer.get('artifacts', {}).get(requested)
    if requested not in receipts and (not path.is_relative_to(root) or
            (declared is None and not any(path.is_relative_to(directory) for directory in allowed))):
        raise ValueError('path must belong to this design and revision')
    if not path.is_file():
        raise KeyError(f'original file not found: {requested}')
    offset, maximum = _offset(query), int(query.get('max_bytes', 8192))
    if not 1 <= maximum <= 65536:
        raise ValueError('max_bytes must be between 1 and 65536')
    stat = path.stat()
    digest = _file_digest(str(path), stat.st_size, stat.st_mtime_ns)
    if declared is not None and digest != declared['sha256']:
        raise ValueError('producer input changed after this run')
    with path.open('rb') as stream:
        stream.seek(offset)
        chunk = stream.read(maximum)
    next_offset = offset + len(chunk)
    return {'snapshot_id': snapshot_id, 'source': {
                'design_id': snapshot['design_id'], 'revision_id': snapshot['revision_id'],
                'run_id': snapshot['run_id'], 'relative_path': requested,
                'path': str(path),
                'sha256': digest,
                'size_bytes': stat.st_size},
            'text': chunk.decode('utf-8', errors='replace'), 'offset': offset,
            'returned_bytes': len(chunk), 'truncated': next_offset < stat.st_size,
            'next_offset': next_offset if next_offset < stat.st_size else None}


def native_files(store, snapshot_id: str, query: dict, root: Path) -> dict:
    """Every file the flow wrote for this run, paged, with its size."""
    snapshot = store.snapshot(snapshot_id)
    directories = _run_dirs(snapshot, root)
    wanted = query.get("kind")
    if wanted and wanted not in (*NATIVE_KINDS, 'receipts'):
        raise ValueError(f"kind must be one of {', '.join(NATIVE_KINDS)}")
    contains = query.get("name_contains")
    entries = []
    for kind in NATIVE_KINDS:
        directory = directories[kind]["path"]
        if directory is None or (wanted and wanted != kind):
            continue
        for path in sorted(Path(directory).rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(root).as_posix()
            if contains and contains not in path.name:
                continue
            entries.append({"category": kind, **_native_file(path, relative)})
    if wanted in (None, 'receipts'):
        for relative, path in _receipt_files(snapshot, root).items():
            if not contains or contains in path.name:
                entries.append({'category': 'receipts', **_native_file(path, relative)})
    limit, offset = _limit(query), _offset(query)
    page = entries[offset:offset + limit]
    manifest = snapshot.get('run_summary', {}).get('timing_context', {}).get('producer', {}).get('artifacts', {})
    for entry in page:
        entry['producer_manifest_entry'] = manifest.get(entry['relative_path'])
    counts = _page(len(entries), len(page), limit, offset)
    return {"snapshot_id": snapshot_id, "native_root": str(root),
            'evidence': [ref for ref in snapshot.get('source_artifacts', []) if ref.get('category') == 'raw_flow_metadata'],
            "design_id": snapshot["design_id"], "revision_id": snapshot["revision_id"],
            "directories": directories, "filters": query,
            "files": {**counts, "total": counts["count"], "items": page},
            "counts_by_category": {kind: sum(1 for item in entries
                                             if item["category"] == kind)
                                   for kind in NATIVE_KINDS},
            "truncated": counts["truncated"],
            "digest_basis": "producer_manifest_entry is the literal original producer declaration; excerpt reads verify current bytes"}


def _parse_report(path: Path, relative: str) -> list[dict]:
    """One record per ``violation type:`` block; the format is 3-4 lines each."""
    records = []
    current = None
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("violation type:"):
            if current:
                records.append(current)
            current = {"file": relative, "index": len(records),
                       "type": line.split(":", 1)[1].strip(),
                       "sources": [], "comment": "", "bbox": None, "layer": None}
            continue
        if current is None:
            continue
        stripped = line.strip()
        if stripped.startswith("srcs:"):
            current["sources"] = stripped.split(":", 1)[1].split()
        elif stripped.startswith("comment:"):
            current["comment"] = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("bbox"):
            match = _BBOX.search(stripped)
            if match:
                x_min, y_min, x_max, y_max, layer = match.groups()
                current["bbox"] = {"x_min": float(x_min), "y_min": float(y_min),
                                   "x_max": float(x_max), "y_max": float(y_max)}
                current["layer"] = layer
    if current:
        records.append(current)
    return records


def violations(store, snapshot_id: str, query: dict, root: Path) -> dict:
    """Per-violation records from the flow's own DRC / congestion reports.

    The family's *final* report and every iteration report it left behind are
    read together, because they disagree: the final DRC report is empty after a
    clean last iteration while ``5_route_drc.rpt-5.rpt`` still holds the 101
    violations the router was reporting at that step.
    """
    snapshot = store.snapshot(snapshot_id)
    name = query.get("report", "drc")
    family = REPORT_FAMILIES.get(name)
    if family is None:
        raise ValueError(f"report must be one of {', '.join(REPORT_FAMILIES)}")
    directories = _run_dirs(snapshot, root)
    reports_dir = directories["reports"]["path"]
    if reports_dir is None:
        return {"snapshot_id": snapshot_id, "report": name, "files": [], "records": None,
                "reason": "flow_reports_directory_not_found", "native_root": str(root),
                "directories": directories, "truncated": False}
    chosen = query.get("file")
    if chosen:
        path = (Path(reports_dir) / chosen).resolve()
        if not str(path).startswith(str(Path(reports_dir).resolve()) + os.sep) or not path.is_file():
            raise ValueError("file must name a report of this run")
        paths = [path]
    else:
        paths = sorted(path for path in Path(reports_dir).glob(f"{family['prefix']}*")
                       if path.is_file())
    files, records = [], []
    for path in paths:
        parsed = _parse_report(path, path.relative_to(root).as_posix())
        types: dict[str, int] = {}
        for record in parsed:
            types[record["type"]] = types.get(record["type"], 0) + 1
            record["index"] = len(records)
            records.append(record)
        files.append({"relative_path": path.relative_to(root).as_posix(),
                      "name": path.name, "size_bytes": path.stat().st_size,
                      "modified": int(path.stat().st_mtime), "sha256": _sha256(path),
                      "violation_count": len(parsed), "type_counts": types,
                      "is_final_report": path.name == family["final"]})
    wanted_type = query.get("type")
    if wanted_type:
        records = [record for record in records if record["type"] == wanted_type]
        for position, record in enumerate(records):
            record["index"] = position
    limit, offset = _limit(query), _offset(query)
    page = records[offset:offset + limit]
    net_objects = {}
    for record in page:
        record['nets'] = [source[4:].replace('\\', '') for source in record['sources']
                          if source.startswith('net:')]
        record['net_objects'] = []
        for name in record['nets']:
            if name not in net_objects:
                matches = store.find_net(snapshot_id, name)
                net_objects[name] = {'name': name,
                    'status': 'available' if matches else 'not_present_in_snapshot',
                    'matches': [{'object_id': row['object_id'], 'name': row['name']}
                                for row in matches]}
            record['net_objects'].append(net_objects[name])
    counts = _page(len(records), len(page), limit, offset)
    return {"snapshot_id": snapshot_id, "report": name, "tool": family["tool"],
            "coordinate_unit": "um",
            "native_root": str(root), "directories": directories,
            "files": files, "violation_count": len(records),
            "type_counts": {record_type: sum(1 for record in records
                                             if record["type"] == record_type)
                            for record_type in sorted({r["type"] for r in records})},
            "records": {**counts, "total": counts["count"], "items": page},
            "evidence": [{"kind": "flow_report", "relative_path": item["relative_path"],
                          "sha256": item["sha256"], "size_bytes": item["size_bytes"],
                          "path": str(Path(root) / item["relative_path"])}
                         for item in files],
            "truncated": counts["truncated"]}


def artifact_manifest(store, client, snapshot_id: str, query: dict) -> dict:
    """The registered catalogue *and* the producer manifest it points at.

    ``scope-02`` asks for the identity and SHA-256 of the final GDS, ODB, DEF,
    Verilog, SDC and SPEF.  Two of those six are staged artifacts; the other
    four exist only inside the producer manifest the adapter attached, so both
    sides are returned from the one place a caller would look.
    """
    snapshot = store.snapshot(snapshot_id)
    refs = [ref for ref in snapshot.get("source_artifacts", []) if isinstance(ref, dict)]
    limit, offset = _limit(query), _offset(query)
    page = refs[offset:offset + limit]
    counts = _page(len(refs), len(page), limit, offset)
    result = {"snapshot_id": snapshot_id, "registered_artifacts":
              {**counts, "total": counts["count"], "items": page},
              "native_manifest": None, "truncated": counts["truncated"]}
    producers = [ref for ref in refs if ref.get("category") == "raw_flow_metadata"]
    if len(producers) != 1:
        result["native_manifest"] = {
            "reason": "snapshot_has_no_producer_manifest" if not producers
                      else "multiple_producer_manifests",
            "candidates": [ref.get("logical_path") for ref in producers]}
        return result
    ref = producers[0]
    if client is None:
        raise ValueError("execution service is not configured")
    excerpt = client.artifact_excerpt(ref["run_id"], ref["artifact_id"],
                                      offset=0, max_bytes=64 * 1024)
    if excerpt.get("truncated"):
        raise ValueError("producer manifest is larger than the excerpt limit")
    manifest = json.loads(excerpt["text"])
    contains = query.get("name_contains")
    entries = [{"relative_path": path, **value}
               for path, value in sorted(manifest.get("artifacts", {}).items())
               if not contains or contains in path]
    manifest_page = entries[offset:offset + limit]
    manifest_counts = _page(len(entries), len(manifest_page), limit, offset)
    result["native_manifest"] = {
        "artifact": {key: ref.get(key) for key in
                     ("artifact_id", "run_id", "category", "logical_path",
                      "sha256", "size_bytes")},
        "design": manifest.get("design"), "platform": manifest.get("platform"),
        "variant": manifest.get("variant"), "native_run_id": manifest.get("native_run_id"),
        "toolchain": manifest.get("toolchain"), "status_log": manifest.get("status_log"),
        "artifact_count": len(manifest.get("artifacts", {})),
        "artifacts": {**manifest_counts, "total": manifest_counts["count"],
                      "items": manifest_page},
        "derived_artifacts": manifest.get("derived_artifacts", {}),
    }
    result["truncated"] = bool(counts["truncated"] or manifest_counts["truncated"])
    return result
