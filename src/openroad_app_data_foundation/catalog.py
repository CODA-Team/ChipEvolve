"""Authoritative catalogs and exact scope/object resolution.

Resolution is a data concern. A caller must refine ambiguous scope; neither
creation time nor identifier spelling grants a candidate precedence.
"""
from __future__ import annotations

from typing import Any

from .context import net_context, object_context
from .identity import is_query_snapshot, snapshot_identity
from .queries import list_metrics_for_run
from .repository import DataStore


def design_catalog(store: DataStore) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in store.snapshots():
        groups.setdefault(row['design_id'], []).append(row)
    return {'designs': [
        {'design_id': key,
         'revisions': sorted({r['revision_id'] for r in rows if r.get('revision_id')}),
         'run_ids': sorted({r['run_id'] for r in rows if r.get('run_id')}),
         'snapshot_count': len(rows),
         'latest_snapshot_at': max((r['created_at'] for r in rows if r.get('created_at')), default=None)}
        for key, rows in sorted(groups.items())]}


def resolve_scope(store: DataStore, query: dict[str, str]) -> dict[str, Any]:
    allowed = {'snapshot_id', 'design_id', 'revision_id', 'run_id', 'stage', 'origin'}
    if set(query) - allowed:
        raise ValueError('unknown scope selector')
    if not any(query.get(key) for key in allowed - {'origin'}):
        raise ValueError('at least one scope selector is required')
    origin = query.get('origin', 'flow')
    if origin not in ('all', 'flow', 'query'):
        raise ValueError('origin must be all|flow|query')
    if query.get('snapshot_id'):
        rows = [store.snapshot(query['snapshot_id'])]
    else:
        rows = store.snapshots(design_id=query.get('design_id'), run_id=query.get('run_id'))
    rows = [row for row in rows if all(
        row.get(key) == value for key, value in query.items() if key != 'origin')
        and (origin == 'all' or is_query_snapshot(row) == (origin == 'query'))]
    candidates = sorted((snapshot_identity(r) for r in rows), key=lambda r: r['snapshot_id'])
    if len(rows) == 1:
        return {'snapshot': candidates[0], 'candidates': candidates}
    return {'resolution_status': 'partial' if rows else 'not_found',
            'missing_fields': ['unique_snapshot'], 'candidates': candidates,
            'reason': 'scope is ambiguous; refine selectors' if rows else 'no snapshot matches scope'}


def named_context(store: DataStore, snapshot_id: str, query: dict[str, str]) -> dict[str, Any]:
    kind = query.get('kind')
    if kind not in ('instance', 'net', 'pin'):
        raise ValueError('kind must be instance|net|pin')
    name, object_id = query.get('name'), query.get('object_id')
    if bool(name) == bool(object_id):
        raise ValueError('provide exactly one of name or object_id')
    snapshot = snapshot_identity(store.snapshot(snapshot_id))
    if object_id:
        row = store.object(snapshot_id, object_id)['entity']
        matches = [row] if row.get('kind') == kind else []
    else:
        matches = store.entities_named(snapshot_id, kind, name)
    if len(matches) != 1:
        return {'snapshot': snapshot, 'matches': matches,
                'resolution_status': 'partial' if matches else 'not_found',
                'missing_fields': ['unique_object'],
                'reason': 'object name is ambiguous' if matches else 'object not found'}
    target_id = matches[0]['object_id']
    context_fn = net_context if kind == 'net' else object_context
    return context_fn(store, snapshot_id, target_id, query.get('detail', 'summary'),
                      int(query.get('relation_limit', '200')))


def snapshot_metrics(store: DataStore, snapshot_id: str, query: dict[str, str]) -> dict[str, Any]:
    snapshot = store.snapshot(snapshot_id)
    if query.get('run_id') and query['run_id'] != snapshot['run_id']:
        raise ValueError('run_id conflicts with snapshot owner')
    payload = list_metrics_for_run(store, snapshot['run_id'], {**query, 'snapshot_id': snapshot_id})
    payload['scope'] = snapshot_identity(snapshot)
    return payload
