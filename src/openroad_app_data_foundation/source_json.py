"""Project, filter and rank complete arrays in original JSON reports."""
import json
import re
import sqlite3
from pathlib import Path

from .artifacts import native_excerpt
from .metadata import metadata_view
from .queries import _limit, _offset, _page


def _field_path(field):
    if not isinstance(field, str) or not re.fullmatch(r'[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*', field):
        raise ValueError('JSON row fields must be dotted object field names')
    return '$.' + field


def _ranking_field(store, array, field, total):
    path = _field_path(field)
    if total and not store.connection.execute('SELECT 1 FROM json_each(?) WHERE json_type(value,?) IS NOT NULL LIMIT 1',
                                              (array, path)).fetchone():
        raise ValueError('original JSON ranking field does not exist: ' + field)
    return path


def source_json(store, snapshot_id, query, root):
    allowed = {'path', 'json_path', 'fields', 'filters', 'sort_field', 'order', 'tie_fields', 'limit', 'offset', 'detail'}
    if set(query) - allowed:
        raise ValueError('unknown original JSON query field')
    selector = query.get('json_path', '$')
    if not isinstance(selector, str) or not selector.startswith('$'):
        raise ValueError('json_path must be an absolute SQLite JSON path beginning with $')
    order = query.get('order', 'asc')
    if order not in ('asc', 'desc'):
        raise ValueError('original JSON order must be asc|desc')
    filters = json.loads(query.get('filters', '{}'))
    if not isinstance(filters, dict) or any(not isinstance(v, (str, int, float, bool)) and v is not None for v in filters.values()):
        raise ValueError('filters must be a JSON object of exact scalar row field values')
    source = native_excerpt(store, snapshot_id, {'path': query.get('path'), 'max_bytes': '1'}, Path(root))['source']
    document = Path(source['path']).read_text(encoding='utf-8')
    # Decode before SQL so malformed JSON is a named input error, never a database failure.
    json.loads(document)
    try:
        selected = store.connection.execute('SELECT json_type(?,?),json_extract(?,?)',
                                            (document, selector, document, selector)).fetchone()
    except sqlite3.OperationalError as exc:
        if 'JSON path error' not in str(exc):
            raise
        raise ValueError('invalid json_path: ' + selector) from exc
    if selected[0] != 'array':
        raise ValueError('json_path must select an existing array in the original file')
    array = selected[1]
    if store.connection.execute("SELECT COUNT(*) FROM json_each(?) WHERE type!='object'", (array,)).fetchone()[0]:
        raise ValueError('selected original array must contain object rows')
    clauses, params = [], [array]
    for field, value in filters.items():
        path = _field_path(field)
        clauses.append('json_type(payload,?)=json_type(?) AND json_extract(payload,?) IS json_extract(?,\'$\')')
        params.extend((path, json.dumps(value), path, json.dumps(value)))
    where = ' WHERE ' + ' AND '.join(clauses) if clauses else ''
    base = 'WITH rows AS (SELECT key AS ordinal,value AS payload FROM json_each(?)) '
    count = store.connection.execute(base + 'SELECT COUNT(*) FROM rows' + where, params).fetchone()[0]
    total = store.connection.execute('SELECT json_array_length(?)', (array,)).fetchone()[0]
    ordering, sort_params = [], []
    if query.get('sort_field'):
        path = _ranking_field(store, array, query['sort_field'], total)
        ordering.extend(['json_extract(payload,?) IS NULL', 'json_extract(payload,?) ' + order.upper()])
        sort_params.extend((path, path))
    for field in query.get('tie_fields', '').split(','):
        if field:
            ordering.append('json_extract(payload,?) ASC')
            sort_params.append(_ranking_field(store, array, field, total))
    ordering.append('ordinal ASC')
    limit, offset = _limit(query), _offset(query)
    page = store.connection.execute(base + 'SELECT ordinal,payload FROM rows' + where +
        ' ORDER BY ' + ','.join(ordering) + ' LIMIT ? OFFSET ?', [*params, *sort_params, limit, offset]).fetchall()
    values = [json.loads(row['payload']) for row in page]
    projected = metadata_view({'rows': values}, {**query, 'fields': ','.join('rows.' + f for f in query['fields'].split(','))}
                              if query.get('fields') else query,
                              '/snapshots/' + snapshot_id + '/artifacts/files/json')
    return {'snapshot_id': snapshot_id, 'source': source, 'json_path': selector, 'rows': projected['rows'],
            'original_array_count': total, 'source_array_indices': [row['ordinal'] for row in page],
            'filters': filters, 'sort_field': query.get('sort_field'), 'order': order,
            'tie_fields': query.get('tie_fields', '').split(',') if query.get('tie_fields') else [],
            'coverage_scope': 'every element of the selected original array; counts and ranking precede pagination',
            **_page(count, len(values), limit, offset), 'delivery': projected.get('delivery')}
