"""Deterministic query operations exposed by the data service."""

from __future__ import annotations

import hashlib

import json
from functools import lru_cache

from typing import Any
from urllib.parse import quote

from .analysis_context import (
    build_analysis_context, context_availability, context_differences,
)
from .identity import canonical_key, snapshot_identity
from .metrics import CANONICAL_METRICS, project_run
from .repository import RECORD_TYPES, DataStore, record_identifier


#: Rows a timing-points page returns when the caller did not ask for a size.
#: A raw point measures ~2.2 KB on ariane, so the shared default of 100 made a
#: 312 KB response and even 20 rows is 44 KB - both over the harness's 32 KiB
#: clip and therefore unparseable to the model.  10 rows is ~22 KB plus the
#: envelope, which fits.  A context pack's points are trimmed by identity first
#: and are small enough to show 20, which is why the two limits differ.
POINTS_PAGE = 10


#: Which field a ranking reads, and which direction "worst" means for it.
#:
#: Wrong for one round: "worst" was always ascending.  Slack is a budget, so the
#: worst path has the smallest (most negative) slack - ascending.  Slew and load are
#: magnitudes, so the worst point has the *largest* value - descending.  Assuming one
#: direction made the worst-slew query return the zero-slew clock roots.
RANKINGS = {
    "timing_paths": {"slack": ("$.slack", "asc"), "arrival": ("$.arrival", "desc")},
    "timing_points": {"slew": ("$.slew", "desc"), "load": ("$.load", "desc"),
                      "arrival": ("$.arrival", "desc")},
}


def _order(record_type: str, query: dict[str, str]) -> tuple[str, dict[str, Any]]:
    """``ORDER BY`` for a ranked question - "the five worst setup paths" is one call.

    Ranking by reading every row and sorting in the caller is how a model spends
    2,500 calls and 52 MB; and asking it to be frugal instead loses the ranking
    entirely (V2, round 34).  So the ranking lives here: worst means ascending, and
    rows without the field sort last in both directions.
    """
    sort = (query.get("sort") or "").lower()
    order = (query.get("order") or "worst").lower()
    if order not in {"worst", "best"}:
        # validated even when nothing is sorted, so a caller cannot believe an order
        # was applied when the parameter was silently ignored
        raise ValueError("order must be worst|best")
    if not sort:
        return "", {}
    ranking = RANKINGS.get(record_type, {}).get(sort)
    if ranking is None:
        raise ValueError(f"cannot sort {record_type} by {sort!r}; "
                         f"known: {sorted(RANKINGS.get(record_type, {}))}")
    expression, worst_direction = ranking
    # "worst" is not one direction: it is the metric's own worst
    ascending = worst_direction == "asc"
    if order == "best":
        ascending = not ascending
    direction = "ASC" if ascending else "DESC"
    # NULLs last in both directions: a path without a slack is not the worst path
    # A deterministic tie-break, by the bundle's own order: several points can share
    # the extreme value (ibex has a five-way tie in slew), and an arbitrary member of
    # the tie is not reproducible.  Ordering by ordinal keeps the page stable and in
    # the order the artifact lists, which is also what a gold derived from it expects.
    clause = f" ORDER BY json_extract(payload, '{expression}') IS NULL, " \
             f"json_extract(payload, '{expression}') {direction}, ordinal ASC"
    return clause, {"sorted_by": sort, "order": order,
                    "ordered": "ascending" if ascending else "descending",
                    "worst_means": f"{worst_direction}ending"}


def list_timing_paths(store: DataStore, snapshot_id: str, query: dict[str, str]) -> dict[str, Any]:
    filters = {key: query[key] for key in ("analysis", "check", "group", "startpoint", "endpoint", "corner") if query.get(key)}
    where = " AND ".join(f"json_extract(payload, '$.{key}') = ?" for key in filters)
    params = list(filters.values())
    total = store.count_records(snapshot_id, "timing_paths", where=where, params=params)
    limit, offset = _limit(query), _offset(query)
    clause, ranking = _order("timing_paths", query)
    rows = store.filtered(snapshot_id, "timing_paths", where=where, params=params,
                          limit=limit, offset=offset, order_by=clause)
    rows = [_path_fields(store, snapshot_id, row) for row in rows]
    clock_filters = {key: query[key] for key in ('source_clock', 'target_clock') if query.get(key)}
    if clock_filters:
        candidates = [_path_fields(store, snapshot_id, row) for row in store.filtered(
            snapshot_id, 'timing_paths', where=where, params=params, order_by=clause)]
        candidates = [row for row in candidates if all(row.get(k) == v for k, v in clock_filters.items())]
        total, rows = len(candidates), candidates[offset:offset + limit]
        filters.update(clock_filters)
    if query.get('fields'):
        columns = query['fields'].split(',')
        allowed = {'path_id', 'startpoint', 'endpoint', 'group', 'check', 'slack', 'required_time',
                   'data_arrival_time', 'source_clock', 'target_clock', 'unit', 'corner', 'evidence'}
        if not set(columns) <= allowed:
            raise ValueError('unknown timing path projection field')
        rows = [{key: row.get(key) for key in columns} for row in rows]
    return {"snapshot_id": snapshot_id, "snapshot": snapshot_identity(store.snapshot(snapshot_id)),
            "timing_paths": rows, **ranking,
            **_page(total, len(rows), limit, offset), "filters": filters}


def list_timing_points(store: DataStore, snapshot_id: str,
                       query: dict[str, str]) -> dict[str, Any]:
    """Timing points across the snapshot, rankable - worst slew in one call.

    Points were only reachable through their path, so "which point has the worst
    slew" meant all 776 points of ibex, path by path.
    """
    names = ('path_id', 'path_section', 'pin_name', 'instance_id', 'net_id')
    allowed = {*names, 'check', 'sort', 'order', 'fields', 'limit', 'offset'}
    if set(query) - allowed:
        raise ValueError('unknown timing point query fields: ' + ','.join(sorted(set(query) - allowed)))
    filters = {key: query[key] for key in names if query.get(key)}
    where = " AND ".join(f"json_extract(payload, '$.{key}') = ?" for key in filters)
    params = list(filters.values())
    if query.get('check'):
        if query['check'] not in ('setup', 'hold'):
            raise ValueError('check must be setup|hold')
        where += (' AND ' if where else '') + """json_extract(payload, '$.path_id') IN (
            SELECT record_id FROM records WHERE snapshot_id=? AND record_type='timing_paths'
            AND json_extract(payload, '$.check')=?)"""
        params.extend([snapshot_id, query['check']])
        filters['check'] = query['check']
    total = store.count_records(snapshot_id, "timing_points", where=where, params=params)
    limit, offset = _point_limit(query), _offset(query)
    clause, ranking = _order("timing_points", query)
    rows = store.filtered(snapshot_id, "timing_points", where=where, params=params,
                          limit=limit, offset=offset, order_by=clause)
    return {"snapshot_id": snapshot_id, "snapshot": snapshot_identity(store.snapshot(snapshot_id)),
            "timing_points": _point_projection(rows, query), **ranking,
            **_page(total, len(rows), limit, offset), "filters": filters}


def list_observations(store: DataStore, snapshot_id: str,
                      query: dict[str, str]) -> dict[str, Any]:
    """List structured facts without exposing the records table.

    ``name``/``scene`` resolve through the observation payload fallback chain,
    so this filter stays in Python over the complete set (observations are
    small); the pagination envelope is still exact.
    """
    rows = store.fetch_all(snapshot_id, "observations")
    filters = {key: query[key] for key in ("name", "kind", "object_id", "status", "scene")
               if query.get(key)}
    rows = [row for row in rows if all(
        _observation_value(row, key) == value for key, value in filters.items())]
    limit, offset = _limit(query), _offset(query)
    page = rows[offset:offset + limit]
    snapshot = snapshot_identity(store.snapshot(snapshot_id))
    return {"snapshot_id": snapshot_id, "design_id": snapshot["design_id"],
            "revision_id": snapshot["revision_id"], "run_id": snapshot["run_id"],
            "stage": snapshot["stage"], "observations": page,
            **_page(len(rows), len(page), limit, offset), "filters": filters}


def list_metrics_for_run(store: DataStore, run_id: str,
                         query: dict[str, str]) -> dict[str, Any]:
    """Canonical metrics for one run, plus raw keys on request.

    CONTRACT section 4.6: ``metrics`` holds only the declared canonical set,
    each with its authoritative source; everything else stays available under
    its original key in ``raw_metrics`` (``include_raw=1``) so the response
    stays small by default.
    """
    snapshots = store.snapshots(run_id=run_id)
    if not snapshots:
        # Same signal as /runs/{run}/summary, for the same reason: a long list of
        # `unavailable` metrics under `status: available` says "this run exists and
        # its metrics are missing", which is the one thing that is not true.  A run
        # this store has never imported is not found here, whatever the execution
        # service knows about it.
        raise KeyError(
            f"run not found: {run_id} has no snapshot in this store "
            f"(it may exist in the execution service but was never imported)")
    projection = project_run(store, snapshots)
    filters = {key: query[key]
               for key in ("stage", "name", "scene", "snapshot_id")
               if query.get(key)}
    rows = [row for row in projection["metrics"] if _metric_matches(row, filters)]
    limit, offset = _limit(query), _offset(query)
    page = rows[offset:offset + limit]
    result: dict[str, Any] = {
        "run_id": run_id, "metrics": page,
        # A metric key is the same string on every design - `WNS`,
        # `globalroute__timing__setup__ws` - and the numbers look plausible in
        # both, so the response must say whose numbers these are.  The scope is
        # read from the run's own snapshots, and a run covering more than one
        # design or stage reports the list rather than picking one.
        "design_id": _one_or_all({item["design_id"] for item in snapshots}),
        "revision_id": _one_or_all({item["revision_id"] for item in snapshots}),
        "stage": filters.get("stage") or _one_or_all(
            {item["stage"] for item in snapshots}),
        **_page(len(rows), len(page), limit, offset),
        "canonical_names": sorted(CANONICAL_METRICS),
        # Scope this to the rows the response actually covers.  Reporting the
        # run-wide list here meant a snapshot-scoped request advertised WNS for a
        # stage whose report never declares it (cold audit finding).
        "canonical_names_available": sorted({row["name"] for row in rows
                                             if row.get("status") == "available"}),
        "units_declared": projection["units_declared"],
        "filters": filters,
    }
    if str(query.get("include_raw", "")).lower() in {"1", "true", "yes"}:
        raw = [row for row in projection["raw_metrics"] if _metric_matches(row, filters)]
        raw_page = raw[offset:offset + limit]
        result["raw_metrics"] = raw_page
        result["raw_metric_count"] = len(raw)
        result["raw_metrics_page"] = _page(len(raw), len(raw_page), limit, offset)
        result["truncated"] = result["truncated"] or result["raw_metrics_page"]["truncated"]
        if result["next_offset"] is None:
            result["next_offset"] = result["raw_metrics_page"]["next_offset"]
    return result


def _one_or_all(values: set[str]) -> Any:
    """The single value, or every value when the run itself does not agree."""
    ordered = sorted(values)
    return ordered[0] if len(ordered) == 1 else (ordered or None)


def _metric_matches(row: dict[str, Any], filters: dict[str, str]) -> bool:
    for key, value in filters.items():
        if key == "name":
            if row.get("name") != value and row.get("raw_key") != value:
                return False
        elif row.get(key) != value:
            return False
    return True


def _observation_value(row: dict[str, Any], name: str) -> Any:
    if name == "name":
        value = row.get("name") or row.get("metric")
        if value is not None:
            return value
        observation_id = row.get("observation_id")
        return observation_id.removeprefix("metric:") if isinstance(observation_id, str) else None
    if name == "scene":
        context = row.get("context")
        return context.get("scene") if isinstance(context, dict) else row.get(name)
    return row.get(name)


def list_evidence(store: DataStore, snapshot_id: str,
                 query: dict[str, str]) -> dict[str, Any]:
    """Paged evidence index (CONTRACT section 5).

    The index is large - ibex has about 190k entries, which used to be one
    95 MB response - so records are streamed and the scan stops as soon as one
    page plus one item is collected.  ``count`` is the exact total only when the
    scan finished; otherwise it is reported as not computed instead of letting
    the page size masquerade as the total.
    """
    artifact_id = query.get("artifact_id")
    # A caller that asks for one record type should not pay for the whole index,
    # and must not silently receive every type when the filter is unreadable.
    requested = query.get("record_type")
    limit, offset = _limit(query), _offset(query)
    if requested is not None and requested not in RECORD_TYPES:
        return {"snapshot_id": snapshot_id, "evidence": [], "count": 0,
                "count_status": "available", "returned": 0, "limit": limit,
                "offset": offset, "truncated": False,
                "filters": {"record_type": requested},
                "missing": ["record_type"],
                "note": f"unknown record type {requested!r}"}
    matched = 0
    page: list[dict[str, Any]] = []
    complete = True
    for record_type in ([requested] if requested else RECORD_TYPES):
        for row in store.iter_records(snapshot_id, record_type):
            for item in row.get("evidence", []):
                if not isinstance(item, dict):
                    continue
                if artifact_id is not None and item.get("artifact_id") != artifact_id:
                    continue
                if matched < offset:
                    matched += 1
                    continue
                if len(page) >= limit:
                    complete = False
                    break
                page.append({"record_type": record_type,
                             "record_id": record_identifier(record_type, row),
                             "evidence": item})
                matched += 1
            if not complete:
                break
        if not complete:
            break
    result: dict[str, Any] = {"snapshot_id": snapshot_id, "evidence": page,
                              "snapshot": snapshot_identity(store.snapshot(snapshot_id)),
                              "filters": ({"record_type": requested}
                                          if requested else {})}
    if complete:
        result.update(_page(matched, len(page), limit, offset))
    else:
        result.update({"count": None, "count_status": "unavailable",
                       "count_reason": ("the index is larger than one page; the "
                                        "total is not computed"),
                       "returned": len(page), "limit": limit, "offset": offset,
                       "truncated": True, "next_offset": offset + len(page)})
    return result


@lru_cache(maxsize=4)
def _timing_document(payload: bytes):
    return json.loads(payload)


def _path_fields(store, snapshot_id, row):
    """Expose the native clock and arrival facts the stored row's own evidence names."""
    fields = ('data_arrival_time', 'crpr', 'source_clock', 'target_clock',
              'source_clock_edge', 'target_clock_edge')
    if all(key in row for key in fields):
        return row
    for ref in row.get('evidence', []):
        index = (ref.get('detail') or {}).get('path_index')
        if not isinstance(index, int):
            continue
        source = store.fragment_source(snapshot_id, ref.get('logical_path'))
        if source is not None:
            document = _timing_document(source['payload'])
            paths = document.get('checks', [])
            if index < len(paths):
                return {**row, **{key: paths[index].get(key) for key in fields}}
    return row


def timing_path(store: DataStore, snapshot_id: str, path_id: str,
                points_limit: int | None = POINTS_PAGE) -> dict[str, Any]:
    """One path and its points, bounded by default.

    A path on ariane carries 190 points at ~2 KB each and this returned every one
    of them: 605,179 B for the path record and 312,262 B for a default page of 100
    points, which is where all 70 of the pilot's over-32 KiB steps came from.  The
    path header itself is 5 KB and stays whole; only the point list is a page, and
    ``points_total`` plus the already-paged ``/timing-paths/{id}/points`` route say
    how to walk the rest.  Internal callers that need every point (the comparison,
    the context pack) pass ``points_limit=0``.
    """
    rows = store.records(snapshot_id, "timing_paths", record_id=path_id, limit=1)
    if not rows:
        raise KeyError(f"timing path not found: {path_id}")
    path = _path_fields(store, snapshot_id, rows[0])
    selected = store.filtered(snapshot_id, "timing_points",
                              where="json_extract(payload, '$.path_id') = ?",
                              params=(path_id,))
    selected.sort(key=lambda row: row.get("ordinal", 0))
    result: dict[str, Any] = {"snapshot_id": snapshot_id, "snapshot": snapshot_identity(store.snapshot(snapshot_id)),
                              "timing_path": path,
                              "analysis_context": build_analysis_context(
                                  store.snapshot(snapshot_id), path)}
    if points_limit:
        result["timing_points"] = selected[:points_limit]
        result["points_returned"] = min(points_limit, len(selected))
        result["points_total"] = len(selected)
        if len(selected) > points_limit:
            result["points_truncated"] = True
            result["next"] = (f"/snapshots/{snapshot_id}/timing-paths/"
                              f"{quote(path_id, safe='')}/points?limit={points_limit}"
                              f"&offset={points_limit}")
    else:
        result["timing_points"] = selected
    return result


def _point_projection(rows, query):
    if not query.get('fields'):
        return rows
    fields = query['fields'].split(',')
    allowed = {'point_id', 'path_id', 'ordinal', 'pin_name', 'instance_id', 'instance_name',
               'net_id', 'net_name', 'cell_name', 'path_section', 'arrival', 'load', 'slew', 'evidence'}
    if not set(fields) <= allowed:
        raise ValueError('unknown timing point projection field')
    return [{key: row.get(key) for key in fields} for row in rows]


def path_points(store: DataStore, snapshot_id: str, path_id: str, query: dict[str, str]) -> dict[str, Any]:
    result = timing_path(store, snapshot_id, path_id, points_limit=0)
    points = result["timing_points"]
    if query.get('path_section'):
        points = [p for p in points if p.get('path_section') == query['path_section']]
    limit = _point_limit(query)
    offset = _offset(query)
    page = points[offset:offset + limit]
    return {"snapshot_id": snapshot_id, "snapshot": snapshot_identity(store.snapshot(snapshot_id)),
            "path_id": path_id,
            "timing_points": _point_projection(page, query), **_page(len(points), len(page), limit, offset)}


def path_nets(store: DataStore, snapshot_id: str, path_id: str,
              query: dict[str, str]) -> dict[str, Any]:
    """The nets one timing path touches, deduplicated, busiest first.

    "Which net on this path has the most fanout" is a fact about the path, but
    answering it used to cost every point (190 on an ariane path, ~280 KB) plus a
    lookup per distinct net (337 calls on the design's busiest net).  The points
    still name their nets and that is where this reads them, but what comes back
    is the answer's inputs - net, fanout, driver - not the raw rows.  Sorted by
    fanout descending, so the first row is the one the question asks for and a
    page of 20 settles it.
    """
    detail = timing_path(store, snapshot_id, path_id, points_limit=0)
    net_ids: list[str] = []
    for point in detail["timing_points"]:
        net_id = point.get("net_id")
        if isinstance(net_id, str) and net_id not in net_ids:
            net_ids.append(net_id)
    by_id = {row.get("object_id"): row
             for row in store.entities_by_ids(snapshot_id, net_ids)}
    nets = []
    for net_id in net_ids:
        entity = by_id.get(net_id)
        if entity is None:
            continue
        attributes = entity.get("attributes") or {}
        nets.append({"net_id": net_id, "name": entity.get("name"),
                     "fanout": attributes.get("fanout"),
                     "driver_id": attributes.get("driver_id"),
                     "driver_count": attributes.get("driver_count")})
    nets.sort(key=lambda row: (row["fanout"] is None, -(row["fanout"] or 0),
                               str(row["net_id"])))
    limit, offset = _limit(query), _offset(query)
    page = nets[offset:offset + limit]
    return {"snapshot_id": snapshot_id, "snapshot": snapshot_identity(store.snapshot(snapshot_id)),
            "path_id": path_id, "nets": page, "count": len(nets),
            "ordered_by": "fanout descending, then net_id",
            **_page(len(nets), len(page), limit, offset)}


def compare_timing_path(store: DataStore, from_snapshot_id: str,
                        to_snapshot_id: str, path_id: str,
                        to_path_id: str | None = None) -> dict[str, Any]:
    """Compare paths only after proving their semantic prerequisites."""
    from_snapshot = store.snapshot(from_snapshot_id)
    to_snapshot = store.snapshot(to_snapshot_id)
    before = timing_path(store, from_snapshot_id, path_id, points_limit=0)
    target_path_id = to_path_id or path_id
    after = timing_path(store, to_snapshot_id, target_path_id, points_limit=0)
    before_path, after_path = before["timing_path"], after["timing_path"]
    before_context = before["analysis_context"]
    after_context = after["analysis_context"]
    reasons = _comparison_reasons(
        before_context, after_context, before_path, after_path)
    path_basis, path_detail = _path_match(before_path, after_path)
    evidence = {"from": _path_evidence(store, from_snapshot_id, path_id, before_path),
                "to": _path_evidence(store, to_snapshot_id, target_path_id, after_path)}
    if reasons or path_basis == "unresolved":
        if path_basis == "unresolved":
            reasons.append({"field": "path_identity", "reason": "unresolved"})
        return _incomparable(
            from_snapshot_id, to_snapshot_id, path_id, target_path_id,
            before_context, after_context, before_path, after_path,
            reasons, path_detail, evidence,
        )

    matched, unresolved = _match_objects(
        store, from_snapshot_id, to_snapshot_id,
        before["timing_points"], after["timing_points"],
    )
    physical = _physical_changes(store, from_snapshot_id, to_snapshot_id, matched)
    return {
        "status": "COMPARABLE",
        "from_snapshot_id": from_snapshot_id,
        "to_snapshot_id": to_snapshot_id,
        "matching": {"basis": path_basis,
                     "path_id": {"from": path_id, "to": target_path_id,
                                 "scope": "snapshot-local"},
                     "path_identity": path_detail,
                     "conditions": {"analysis_context": "available and equal",
                                    "endpoints": "equal", "path_identity": path_basis}},
        "analysis_context": {"from": before_context, "to": after_context},
        "timing": {name: _change(before_path.get(name), after_path.get(name))
                   for name in ("slack", "delay")},
        "connections": _net_changes(before["timing_points"], after["timing_points"]),
        "physical": physical,
        "matched_objects": _matched_relations(matched),
        "unmatched_objects": unresolved,
        "relations": _matched_relations(matched),
        "availability": context_availability(before_context),
        "evidence": evidence,
    }


def _comparison_reasons(left: dict[str, Any], right: dict[str, Any],
                        left_path: dict[str, Any], right_path: dict[str, Any]
                        ) -> list[dict[str, Any]]:
    reasons = context_differences(left, right)
    for field in ("startpoint", "endpoint", "group"):
        left_value, right_value = left_path.get(field), right_path.get(field)
        if not _present(left_value) or not _present(right_value):
            reasons.append({"field": field, "reason": "missing",
                            "from": left_value, "to": right_value})
        elif left_value != right_value:
            reasons.append({"field": field, "reason": "mismatch",
                            "from": left_value, "to": right_value})
    return reasons


def _path_match(left: dict[str, Any], right: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    native_left = _path_identity_value(left, "native_path_id")
    native_right = _path_identity_value(right, "native_path_id")
    if native_left and native_right and native_left == native_right:
        return "native_exact", {"native_path_id": native_left}
    structural_left = _path_identity_value(left, "structural_fingerprint")
    structural_right = _path_identity_value(right, "structural_fingerprint")
    if structural_left and structural_right and structural_left == structural_right:
        return "structural_verified", {"structural_fingerprint": structural_left}
    fields = ("startpoint", "endpoint", "analysis", "check", "corner", "unit", "group")
    if all(_present(left.get(field)) and left.get(field) == right.get(field)
           for field in fields):
        return "scoped_name", {field: left.get(field) for field in fields}
    return "unresolved", {"from_path_id": left.get("path_id"),
                           "to_path_id": right.get("path_id")}


def _path_identity_value(path: dict[str, Any], name: str) -> str | None:
    value = path.get(name)
    if isinstance(value, str) and value:
        return value
    identity = path.get("path_identity")
    if isinstance(identity, dict):
        value = identity.get(name)
        return value if isinstance(value, str) and value else None
    return None


def _net_changes(before: list[dict[str, Any]], after: list[dict[str, Any]]) -> dict[str, list[str]]:
    before_nets = {str(point["net_id"]) for point in before if point.get("net_id")}
    after_nets = {str(point["net_id"]) for point in after if point.get("net_id")}
    return {"shared": sorted(before_nets & after_nets),
            "only_from": sorted(before_nets - after_nets),
            "only_to": sorted(after_nets - before_nets),
            "basis": "snapshot-local point references; not cross-stage identity"}


def _physical_changes(store: DataStore, from_snapshot_id: str, to_snapshot_id: str,
                      matched: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    instances, nets = [], []
    for item in matched:
        from_id = item["from_object_id"]
        to_id = item["to_object_id"]
        before = _physical(store, from_snapshot_id, from_id)
        after = _physical(store, to_snapshot_id, to_id)
        if before is None or after is None:
            continue
        if item.get("kind") == "instance" and all(
                isinstance(value.get(name), (int, float))
                for value in (before, after) for name in ("x", "y")):
            instances.append({"from_object_id": from_id, "to_object_id": to_id,
                              "matching_basis": item["matching_basis"],
                              "evidence": item["evidence"],
                              "from": {name: before[name] for name in ("x", "y")},
                              "to": {name: after[name] for name in ("x", "y")},
                              "delta": {name: after[name] - before[name] for name in ("x", "y")}})
        if item.get("kind") == "net":
            nets.append({"from_object_id": from_id, "to_object_id": to_id,
                         "matching_basis": item["matching_basis"],
                         "evidence": item["evidence"],
                         "wire_length": _change(_wire_length(before), _wire_length(after))})
    return {"instances": instances, "nets": nets}


def _matched_relations(matched: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{
        "predicate": "same_design_object_as",
        "from_object_id": item["from_object_id"],
        "to_object_id": item["to_object_id"],
        "identity": item["identity"],
        "matching_basis": item["matching_basis"],
        "evidence": item["evidence"],
    } for item in matched]


def _incomparable(from_snapshot_id: str, to_snapshot_id: str,
                  from_path_id: str, to_path_id: str,
                  from_context: dict[str, Any], to_context: dict[str, Any],
                  from_path: dict[str, Any], to_path: dict[str, Any],
                  reasons: list[dict[str, Any]], path_detail: dict[str, Any],
                  evidence: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    return {
        "status": "INCOMPARABLE",
        "from_snapshot_id": from_snapshot_id,
        "to_snapshot_id": to_snapshot_id,
        "matching": {"basis": "unresolved",
                     "path_id": {"from": from_path_id, "to": to_path_id,
                                 "scope": "snapshot-local"},
                     "path_identity": path_detail,
                     "reasons": reasons},
        "analysis_context": {"from": from_context, "to": to_context},
        "path_identity": {"from": _path_view(from_path),
                          "to": _path_view(to_path)},
        "availability": context_availability(from_context),
        "limitations": [{"status": "incomparable", "reasons": reasons}],
        "evidence": evidence,
    }


def _match_objects(store: DataStore, from_snapshot_id: str, to_snapshot_id: str,
                   from_points: list[dict[str, Any]],
                   to_points: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    from_objects = _path_objects(store, from_snapshot_id, from_points)
    to_objects = _path_objects(store, to_snapshot_id, to_points)
    by_native = _identity_candidates(to_objects, "native_id")
    by_structural = _identity_candidates(to_objects, "structural_fingerprint")
    by_canonical = _canonical_candidates(to_objects)
    matched: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    for source in from_objects:
        identity = source.get("identity") or {}
        candidates: list[dict[str, Any]] = []
        basis = "unresolved"
        native_id = identity.get("native_id")
        if isinstance(native_id, str) and native_id:
            candidates = by_native.get((source.get("kind"), native_id), [])
            basis = "native_exact"
        if not candidates:
            fingerprint = identity.get("structural_fingerprint")
            if isinstance(fingerprint, str) and fingerprint:
                candidates = by_structural.get((source.get("kind"), fingerprint), [])
                basis = "structural_verified"
        if not candidates:
            key = _canonical_tuple(identity)
            if key is not None:
                candidates = by_canonical.get(key, [])
                basis = "scoped_name"
        if len(candidates) == 1:
            target = candidates[0]
            item = {
                "from_object_id": source["object_id"],
                "to_object_id": target["object_id"],
                "kind": source.get("kind"),
                "matching_basis": basis,
                "identity": {"from": source.get("identity"),
                             "to": target.get("identity")},
            }
            item["evidence"] = {
                "from": _object_evidence(store, from_snapshot_id, source["object_id"]),
                "to": _object_evidence(store, to_snapshot_id, target["object_id"]),
            }
            matched.append(item)
            continue
        unresolved.append({
            "status": "ambiguous" if len(candidates) > 1 else "unresolved",
            "from_object_id": source["object_id"],
            "identity": source.get("identity"),
            "matching_basis": basis,
            "candidate_object_ids": [item["object_id"] for item in candidates],
            "evidence": {"from": _object_evidence(
                store, from_snapshot_id, source["object_id"])},
        })
    return matched, unresolved


def _path_objects(store: DataStore, snapshot_id: str,
                  points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    wanted: list[str] = []
    for point in points:
        for field in ("pin_id", "instance_id", "net_id", "object_id"):
            value = point.get(field)
            if isinstance(value, str) and value:
                wanted.append(value)
    entities = {row.get("object_id"): row
                for row in store.entities_by_ids(snapshot_id, wanted)}
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for point in points:
        for field in ("pin_id", "instance_id", "net_id", "object_id"):
            object_id = point.get(field)
            if not isinstance(object_id, str) or object_id in seen:
                continue
            seen.add(object_id)
            entity = entities.get(object_id)
            result.append({"object_id": object_id,
                           "kind": entity.get("kind") if entity else None,
                           "identity": entity.get("identity") if entity else None})
    return result


def _identity_candidates(objects: list[dict[str, Any]], field: str
                         ) -> dict[tuple[Any, Any], list[dict[str, Any]]]:
    result: dict[tuple[Any, Any], list[dict[str, Any]]] = {}
    for item in objects:
        value = (item.get("identity") or {}).get(field)
        if isinstance(value, str) and value:
            result.setdefault((item.get("kind"), value), []).append(item)
    return result


def _canonical_candidates(objects: list[dict[str, Any]]) -> dict[tuple[Any, ...], list[dict[str, Any]]]:
    result: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for item in objects:
        key = _canonical_tuple(item.get("identity"))
        if key is not None:
            result.setdefault(key, []).append(item)
    return result


def _canonical_tuple(identity: dict[str, Any] | None) -> tuple[Any, ...] | None:
    if not isinstance(identity, dict):
        return None
    canonical = identity.get("canonical")
    if not isinstance(canonical, dict) or identity.get("matching_status") == "ambiguous":
        return None
    return canonical_key(identity)


def _object_evidence(store: DataStore, snapshot_id: str,
                     object_id: str) -> list[dict[str, Any]]:
    entity = store.records(snapshot_id, "entities", record_id=object_id, limit=1)
    physical = store.records(snapshot_id, "physical_context", record_id=object_id, limit=1)
    result = [{"record_type": "entities", "record_id": object_id,
               "evidence": item}
              for item in (entity[0].get("evidence", []) if entity else [])
              if isinstance(item, dict)]
    result.extend({"record_type": "physical_context", "record_id": object_id,
                   "evidence": item}
                  for item in (physical[0].get("evidence", []) if physical else [])
                  if isinstance(item, dict))
    return result or [{"status": "unavailable", "reason": "no evidence reference",
                      "record_id": object_id}]


def _path_evidence(store: DataStore, snapshot_id: str, path_id: str,
                   path: dict[str, Any]) -> list[dict[str, Any]]:
    result = [{"record_type": "timing_paths", "record_id": path_id,
               "evidence": item}
              for item in path.get("evidence", []) if isinstance(item, dict)]
    if not result:
        result.append({"record_type": "timing_paths", "record_id": path_id,
                       "evidence": {"status": "unavailable",
                                    "reason": "no evidence reference"}})
    return result + [{"record_type": "snapshot", "record_id": snapshot_id,
                      "artifact": item}
                     for item in store.snapshot(snapshot_id).get("source_artifacts", [])
                     if isinstance(item, dict)]


def _path_view(path: dict[str, Any]) -> dict[str, Any]:
    return {name: path.get(name) for name in (
        "path_id", "startpoint", "endpoint", "analysis", "check", "corner", "unit")}


def _present(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def _physical(store: DataStore, snapshot_id: str, object_id: str) -> dict[str, Any] | None:
    rows = store.records(snapshot_id, "physical_context", record_id=object_id, limit=1)
    return rows[0] if rows else None


def _wire_length(physical: dict[str, Any]) -> int:
    return sum(abs(item["x_max"] - item["x_min"]) + abs(item["y_max"] - item["y_min"])
               for item in physical.get("routing", [])
               if item.get("routing_type") == "segment"
               and all(isinstance(item.get(name), (int, float))
                       for name in ("x_min", "x_max", "y_min", "y_max")))


def _change(before: Any, after: Any) -> dict[str, Any]:
    result = {"from": before, "to": after}
    if isinstance(before, (int, float)) and isinstance(after, (int, float)):
        result["delta"] = after - before
    return result


def _point_limit(query: dict[str, str]) -> int:
    """A points page that survives the harness clip unless the caller says otherwise.

    An explicit ``limit`` is still honoured in full.
    """
    return _limit(query) if "limit" in query else POINTS_PAGE


def _page(total: int, returned: int, limit: int, offset: int) -> dict[str, Any]:
    """Pagination envelope shared by every list tool (CONTRACT section 5)."""
    truncated = offset + returned < total
    return {"count": total, "returned": returned, "limit": limit, "offset": offset,
            "truncated": truncated,
            "next_offset": offset + returned if truncated else None}


def _limit(query: dict[str, str]) -> int:
    value = int(query.get("limit", "100"))
    if not 1 <= value <= 10000:
        raise ValueError("limit must be between 1 and 10000")
    return value


def _offset(query: dict[str, str]) -> int:
    value = int(query.get("offset", "0"))
    if value < 0:
        raise ValueError("offset must not be negative")
    return value


def read_evidence(store: DataStore, snapshot_id: str, record_type: str,
                  record_id: str) -> dict[str, Any]:
    """The raw fragment a record's evidence points at, not the whole file.

    Whole-artifact download is capped at 4 MiB by the execution foundation, and
    copying a 25 MB database for one fact is the wrong answer even when it fits.
    The bundle already carries the JSON the facts were parsed from, so this slices
    the piece the evidence names: a timing check by its file-local path index, a
    timing point by that index and its ordinal, a mapping row by its pin name.

    A source that cannot be sliced is reported as unavailable with the reason - a
    binary database is never silently substituted with something else.
    """
    # record_evidence wraps each reference as {"record_type", "record_id", "evidence"}
    entries = [row["evidence"] for row in
               store.record_evidence(snapshot_id, record_type, record_id)
               if isinstance(row, dict) and isinstance(row.get("evidence"), dict)]
    fragments: list[dict[str, Any]] = []
    for entry in entries:
        logical_path = entry.get("logical_path")
        source = (store.fragment_source(snapshot_id, logical_path)
                  if isinstance(logical_path, str) else None)
        common = {
            "artifact_id": entry.get("artifact_id"),
            "logical_path": logical_path,
            "sha256": entry.get("sha256"),
            "locator": entry.get("locator"),
            "detail": entry.get("detail"),
        }
        if source is not None and hashlib.sha256(source["payload"]).hexdigest() != source["sha256"]:
            # the stored digest is a claim about the bytes; check the bytes
            fragments.append({**common, "status": "unavailable",
                              "reason": "the stored fragment does not match its own "
                                        "sha256 - refusing to serve it"})
            continue
        if source is None:
            fragments.append({**common, "status": "unavailable",
                              "reason": (f"{logical_path!r} is not a JSON fragment source; "
                                         "it is a binary database whose facts the adapter "
                                         "already extracted, and it exceeds the download cap")})
            continue
        try:
            document = json.loads(source["payload"])
            pointer, fragment = _fragment(document, record_type, entry)
        except (json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
            fragments.append({**common, "status": "unavailable",
                              "reason": f"cannot slice the source: {type(exc).__name__}: {exc}"})
            continue
        fragments.append({**common, "status": "available", "fragment_path": pointer,
                          "fragment": fragment,
                          "source_sha256": source["sha256"]})
    available = sum(1 for item in fragments if item["status"] == "available")
    result: dict[str, Any] = {
        "snapshot_id": snapshot_id, "record_type": record_type, "record_id": record_id,
        "fragments": fragments, "available": available, "returned": len(fragments),
    }
    if not fragments:
        raise KeyError(f"no evidence for {record_type}/{record_id}")
    return result


def _fragment(document: Any, record_type: str,
              entry: Mapping[str, Any]) -> tuple[str, Any]:
    """Locate the named slice.  Every path here mirrors how the adapter wrote it."""
    detail = entry.get("detail") if isinstance(entry.get("detail"), dict) else {}
    locator = entry.get("locator") if isinstance(entry.get("locator"), dict) else {}
    # A timing point carries two references: the report it came from and the
    # mapping row that names its ids.  The mapping entry names the pin in `detail`
    # (it is a property of the reference), while an entity/relation carries its
    # `locator` on the record; both are accepted, and the mapping table is keyed by
    # pin *name*.
    pin = detail.get("pin_name") or locator.get("pin_name")
    if isinstance(pin, str) and pin:
        return f"/{pin}", document[pin]
    if record_type in {"timing_paths", "timing_points"}:
        index = detail.get("path_index")
        if not isinstance(index, int):
            raise KeyError("evidence does not name a path_index")
        check = document["checks"][index]
        if record_type == "timing_paths":
            return f"/checks/{index}", check
        section = detail.get("section")
        section_index = detail.get("section_index")
        if not isinstance(section, str) or not isinstance(section_index, int):
            # The point's own location, not a reassembled ordering: slicing by an
            # index the adapter and this function both have to keep in step is how
            # a fragment silently becomes the wrong point.
            raise KeyError("evidence does not name the point's section and index")
        rows = check.get(section) or []
        return f"/checks/{index}/{section}/{section_index}", rows[section_index]
    raise KeyError("no fragment rule for this locator")
