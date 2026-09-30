"""Bounded object discovery over the same immutable snapshot records."""
import math
from .queries import _limit, _offset, _page


def list_objects(store, snapshot_id, query):
    filters, params = [], []
    fields = {'kind': '$.kind', 'parent_id': '$.parent_id', 'master': '$.attributes.master', 'driver_count': '$.attributes.driver_count', 'signal_type': '$.attributes.signal_type'}
    for key, path in fields.items():
        if query.get(key):
            filters.append(f"json_extract(payload, '{path}') = ?")
            params.append(query[key])
    if query.get('name_contains'):
        filters.append("instr(json_extract(payload, '$.name'), ?) > 0")
        params.append(query['name_contains'])
    if query.get('is_macro') is not None:
        if query['is_macro'] not in ('0', '1'):
            raise ValueError('is_macro must be 0|1')
        filters.append("json_extract(payload, '$.attributes.is_macro') = ?")
        params.append(int(query['is_macro']))
    if query.get('region'):
        box = [float(x) for x in query['region'].split(',')]
        if len(box) != 4 or not all(math.isfinite(x) for x in box) or box[0] > box[2] or box[1] > box[3]:
            raise ValueError('region must be xmin,ymin,xmax,ymax in database units')
        filters.append("""record_id IN (SELECT record_id FROM records
            WHERE snapshot_id = ? AND record_type = 'physical_context'
            AND json_extract(payload, '$.bbox.x_max') >= ?
            AND json_extract(payload, '$.bbox.y_max') >= ?
            AND json_extract(payload, '$.bbox.x_min') <= ?
            AND json_extract(payload, '$.bbox.y_min') <= ?)""")
        params.extend([snapshot_id, *box])
    where = ' AND '.join(filters)
    # The default is the stored order, which `records_lookup`
    # (snapshot_id, record_type, ordinal) serves directly: a page costs
    # O(offset + limit).  Ordering by name by default re-sorted the whole kind on
    # *every* page - on ariane136 a single page of 10,000 instances did not return
    # in 190 s, while the same page over the store's own ordinal index takes
    # 0.17 s.  A caller that needs a ranking still asks for one explicitly.
    sort = query.get('sort')
    if sort is not None and sort not in ('name', 'fanout'):
        raise ValueError('sort must be name|fanout')
    if sort is None:
        clause = ''
    else:
        order = query.get('order', 'desc' if sort == 'fanout' else 'asc')
        if order not in ('asc', 'desc'):
            raise ValueError('order must be asc|desc')
        path = '$.attributes.fanout' if sort == 'fanout' else '$.name'
        clause = (f" ORDER BY json_extract(payload, '{path}') IS NULL, "
                  f"json_extract(payload, '{path}') {order}, record_id")
    total = store.count_records(snapshot_id, 'entities', where=where, params=params)
    limit, offset = _limit(query), _offset(query)
    rows = store.filtered(snapshot_id, 'entities', where=where, params=params,
                          order_by=clause, limit=limit, offset=offset)
    columns = query.get('fields')
    if columns:
        columns = columns.split(',')
        allowed = {'object_id', 'name', 'kind', 'parent_id', 'attributes', 'identity', 'evidence'}
        if not set(columns) <= allowed:
            raise ValueError('unknown object projection field')
        rows = [{key: row.get(key) for key in columns} for row in rows]
    return {'snapshot_id': snapshot_id, 'objects': rows, 'filters': query,
            'order': sort or 'stored',
            **_page(total, len(rows), limit, offset)}


def timing_context(store, snapshot_id):
    snapshot = store.snapshot(snapshot_id)
    context = snapshot.get('run_summary', {}).get('timing_context')
    return {'snapshot_id': snapshot_id, 'timing_context': context,
            'evidence': snapshot.get('source_artifacts', []),
            'availability': {'timing_context': {'status': 'available' if context else 'unavailable'}}}


def routing_summary(store, snapshot_id, object_id):
    physical = store.physical(snapshot_id, object_id)
    layers, vias = {}, {}
    for shape in physical.get('routing', []):
        if shape.get('routing_type') == 'segment':
            width, height = shape['x_max'] - shape['x_min'], shape['y_max'] - shape['y_min']
            layer = shape['layer']
            value = layers.setdefault(layer, {'segments': 0, 'centerline_length_dbu': 0})
            value['segments'] += 1
            if 'centerline_length_dbu' not in shape:
                raise ValueError('snapshot does not contain centerline lengths; re-extract its ODB')
            value['centerline_length_dbu'] += shape['centerline_length_dbu']
        elif shape.get('routing_type') == 'via':
            name = shape['via']; vias[name] = vias.get(name, 0) + 1
    return {'snapshot_id': snapshot_id, 'object_id': object_id, 'layers': layers, 'vias': vias,
            'segment_count': sum(x['segments'] for x in layers.values()),
            'via_count': sum(vias.values()), 'unit': 'database_units',
            'length_basis': 'Manhattan distance between native dbWirePath iterator points, excludes rectangle endcaps',
            'evidence': physical.get('evidence', [])}
