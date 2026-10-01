"""Bounded object discovery over the same immutable snapshot records."""
import math
from .identity import snapshot_identity
from .queries import _limit, _offset, _page


#: Ids one ``?ids=`` call accepts.  Beyond this the answer stops fitting an
#: envelope that is bounded by construction, so the caller is told to split.
BATCH_ID_LIMIT = 100


def list_objects(store, snapshot_id, query):
    filters, params = [], []
    fields = {'kind': '$.kind', 'parent_id': '$.parent_id', 'master': '$.attributes.master', 'driver_count': '$.attributes.driver_count', 'signal_type': '$.attributes.signal_type'}
    #: Query parameters arrive as text.  ``driver_count`` is a JSON *number* in the
    #: payload, so comparing it with the string "1" matched nothing at all - a
    #: caller filtering driver_count=1 got an empty page on a snapshot whose first
    #: nets all have driver_count 1, which reads as "no such net".
    numeric = {'driver_count'}
    for key, path in fields.items():
        if query.get(key):
            filters.append(f"json_extract(payload, '{path}') = ?")
            value = query[key]
            params.append(int(value) if key in numeric else value)
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
    if query.get('ids'):
        # One call for many objects, because the alternative costs a call per id and
        # each call carries ~2.3 KB of envelope: ariane cross_domain-01 spends 105
        # steps to find the busiest net among the nets on five paths, almost all of
        # them "fetch one net to read its fanout".
        wanted = [item for item in query['ids'].split(',') if item]
        if len(wanted) > BATCH_ID_LIMIT:
            raise ValueError(
                f'ids accepts at most {BATCH_ID_LIMIT} ids in one call, got {len(wanted)}; '
                f'send the rest in another call, or page a filter with limit/offset')
        marks = ', '.join('?' for _ in wanted)
        filters.append(f'record_id IN ({marks})')
        params.extend(wanted)
    if query.get('connected_to'):
        # The other end of every relation touching this object - the set
        # `expand_net` stops at CONNECTED_ENTITY_LIMIT, but pageable, so a
        # caller told `entities_total: 675` can walk all of it instead of being
        # handed a sample with no way forward.  Each branch is one index search
        # (`records_json_subject` / `records_json_object`); the same two-branch
        # union is what `relations_touching` uses, for the same reasons.
        other = """record_id IN (
            SELECT json_extract(payload, '$.object_id') FROM records
              WHERE snapshot_id = ? AND record_type = 'relations'
              AND json_extract(payload, '$.subject_id') = ?
            UNION
            SELECT json_extract(payload, '$.subject_id') FROM records
              WHERE snapshot_id = ? AND record_type = 'relations'
              AND json_extract(payload, '$.object_id') = ?)"""
        filters.append(other)
        params.extend([snapshot_id, query['connected_to'],
                       snapshot_id, query['connected_to']])
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
    if query.get('ids'):
        # Answer the batch whole: a page of it would make every id past the page
        # look like it does not exist.
        limit, offset = len(wanted), 0
    rows = store.filtered(snapshot_id, 'entities', where=where, params=params,
                          order_by=clause, limit=limit, offset=offset)
    columns = query.get('fields')
    if columns:
        columns = columns.split(',')
        allowed = {'object_id', 'name', 'kind', 'parent_id', 'attributes', 'identity', 'evidence'}
        if not set(columns) <= allowed:
            raise ValueError('unknown object projection field')
        rows = [{key: row.get(key) for key in columns} for row in rows]
    result = {'snapshot_id': snapshot_id, 'objects': rows, 'filters': query,
              'order': sort or 'stored',
              # Snapshot identity travels with the rows so the envelope's scope can
              # name design/revision/run/stage instead of leaving a caller to parse
              # the snapshot_id.  ibex already has two revisions whose final ODB is
              # byte-identical, so "which run is this number from" is a real
              # question, and `snapshot()` is cached - this costs no query.
              'snapshot': snapshot_identity(store.snapshot(snapshot_id)),
              **_page(total, len(rows), limit, offset)}
    if query.get('ids'):
        # Distinguish an id that does not exist from one this call did not return:
        # the batch is answered in full, so anything absent is genuinely absent.
        found = {str(row.get('object_id')) for row in rows}
        result['found'] = len(found)
        result['missing_ids'] = [item for item in wanted if item not in found]
    return result


def timing_context(store, snapshot_id):
    snapshot = store.snapshot(snapshot_id)
    context = snapshot.get('run_summary', {}).get('timing_context')
    return {'snapshot_id': snapshot_id, 'snapshot': snapshot_identity(snapshot),
            'timing_context': context,
            'evidence': snapshot.get('source_artifacts', []),
            'availability': {'timing_context': {'status': 'available' if context else 'unavailable'}}}


def routing_summary(store, snapshot_id, object_id):
    # Every shape, deliberately: this counts segments per layer and vias by name, so
    # a paged list would produce a confidently wrong total rather than a short one.
    physical = store.physical(snapshot_id, object_id, routing_limit=0)
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
    return {'snapshot_id': snapshot_id, 'snapshot': snapshot_identity(store.snapshot(snapshot_id)),
            'object_id': object_id, 'layers': layers, 'vias': vias,
            'segment_count': sum(x['segments'] for x in layers.values()),
            'via_count': sum(vias.values()), 'unit': 'database_units',
            'length_basis': 'Manhattan distance between native dbWirePath iterator points, excludes rectangle endcaps',
            'evidence': physical.get('evidence', [])}
