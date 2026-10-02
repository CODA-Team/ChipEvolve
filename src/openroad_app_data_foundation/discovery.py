"""Bounded object discovery over the same immutable snapshot records."""
import math
from decimal import Decimal
from .identity import snapshot_identity
from .metadata import clock_context
from .queries import _limit, _offset, _page


#: Ids one ``?ids=`` call accepts.  Beyond this the answer stops fitting an
#: envelope that is bounded by construction, so the caller is told to split.
BATCH_ID_LIMIT = 100


def query_boolean(query, key):
    value = str(query[key]).lower()
    values = {'0': 0, '1': 1, 'false': 0, 'true': 1}
    if value not in values:
        raise ValueError(key + ' must be 0|1 or false|true')
    return values[value]


def object_filter(store, snapshot_id, query):
    """Shared complete filter semantics for pages and server-side aggregation."""
    allowed = {'kind', 'parent_id', 'parent_instance', 'master', 'driver_count', 'signal_type', 'direction', 'name',
               'name_contains', 'name_prefix', 'driver_min', 'driver_max', 'port_driven',
               'port', 'is_macro', 'region', 'region_units', 'intersection', 'ids', 'connected_to',
               'net_role', 'sort', 'order', 'limit', 'offset', 'fields', 'format', 'group_by', 'include_physical', 'include_engineering'}
    unknown = set(query) - allowed
    if unknown:
        raise ValueError('unknown object query fields: ' + ','.join(sorted(unknown)))
    roles = {'driver': 'driven_by', 'load': 'loads'}
    if query.get('net_role'):
        if query['net_role'] not in roles or not query.get('connected_to'):
            raise ValueError('net_role must be driver|load with connected_to=<net name or id>')
        from .engineering import _entity
        query = {**query, 'connected_to': _entity(store, snapshot_id, query['connected_to'], 'net')['object_id']}
    elif query.get('connected_to') and query.get('kind') == 'instance':
        from .engineering import _entity
        query = {**query, 'connected_to': _entity(store, snapshot_id, query['connected_to'], 'net')['object_id']}
    filters, params = [], []
    fields = {'kind': '$.kind', 'parent_id': '$.parent_id', 'master': '$.attributes.master', 'driver_count': '$.attributes.driver_count', 'signal_type': '$.attributes.signal_type', 'direction': '$.attributes.direction'}
    #: Query parameters arrive as text.  ``driver_count`` is a JSON *number* in the
    #: payload, so comparing it with the string "1" matched nothing at all - a
    #: caller filtering driver_count=1 got an empty page on a snapshot whose first
    #: nets all have driver_count 1, which reads as "no such net".
    numeric = {'driver_count'}
    for key, path in fields.items():
        if query.get(key):
            if key == 'signal_type' and query.get('kind') == 'pin':
                # Unary + removes TEXT affinity so SQLite can use full subject index equality.
                filters.append("""EXISTS (SELECT 1
                    FROM records r JOIN records n
                    ON n.snapshot_id = r.snapshot_id AND n.record_type = 'entities'
                    AND n.record_id = json_extract(r.payload, '$.object_id')
                    WHERE r.snapshot_id = ? AND r.record_type = 'relations'
                    AND json_extract(r.payload, '$.subject_id') IS NOT NULL
                    AND json_extract(r.payload, '$.subject_id') = +records.record_id
                    AND json_extract(r.payload, '$.predicate') = 'connected_to'
                    AND json_extract(n.payload, '$.attributes.signal_type') = ?)""")
                params.extend([snapshot_id, query[key]])
                continue
            # An exact name/parent/id is much narrower than an entire object
            # kind. Without statistics, SQLite picked the new kind index and
            # scanned millions of pins for two names or seven children.
            prefix = '+' if key == 'kind' and any(query.get(k) for k in ('name', 'parent_id', 'parent_instance', 'ids', 'connected_to')) else ''
            filters.append(f"{prefix}json_extract(payload, '{path}') = ?")
            value = query[key]
            params.append(int(value) if key in numeric else value)
    if query.get('name'):
        variants = store.name_candidates(snapshot_id, query['name'], query.get('kind'))
        filters.append("json_extract(payload, '$.name') IN (" + ','.join('?' for _ in variants) + ')')
        params.extend(variants)
    if query.get('parent_instance'):
        if query.get('kind') != 'pin' or query.get('parent_id'):
            raise ValueError('parent_instance requires kind=pin and no parent_id')
        from .engineering import _entity
        parent = _entity(store, snapshot_id, query['parent_instance'], 'instance')
        filters.append("json_extract(payload, '$.parent_id') = ?")
        params.append(parent['object_id'])
    if query.get('name_contains'):
        filters.append("instr(replace(json_extract(payload, '$.name'), char(92), ''), ?) > 0")
        params.append(query['name_contains'].replace('\\', ''))
    if query.get('name_prefix'):
        prefix = query['name_prefix'].replace('\\', '')
        filters.append("substr(replace(json_extract(payload, '$.name'), char(92), ''), 1, ?) = ?")
        params.extend([len(prefix), prefix])
    for key, operator in [('driver_min', '>='), ('driver_max', '<=')]:
        if query.get(key) is not None:
            filters.append(f"json_extract(payload, '$.attributes.driver_count') {operator} ?")
            params.append(int(query[key]))
    if query.get('port_driven') is not None:
        filters.append(('' if query_boolean(query, 'port_driven') else 'NOT ') + """EXISTS (
            SELECT 1 FROM json_each(json_extract(payload, '$.attributes.driver_ids'))
            WHERE value LIKE 'bterm:%')""")
    if query.get('port') is not None:
        filters.append("record_id " + ("LIKE" if query_boolean(query, 'port') else "NOT LIKE") + " 'bterm:%'")
    if query.get('is_macro') is not None:
        filters.append("json_extract(payload, '$.attributes.is_macro') = ?")
        params.append(query_boolean(query, 'is_macro'))
    if query.get('region'):
        box = [float(x) for x in query['region'].split(',')]
        if len(box) != 4 or not all(math.isfinite(x) for x in box) or box[0] > box[2] or box[1] > box[3]:
            raise ValueError('region must be finite xmin,ymin,xmax,ymax in the selected region_units')
        unit = query.get('region_units', 'dbu')
        if unit not in ('dbu', 'um'):
            raise ValueError('region_units must be dbu|um')
        if unit == 'um':
            scale = store.snapshot(snapshot_id)['run_summary']['dbu_per_micron']
            box = [float(Decimal(value) * scale) for value in query['region'].split(',')]
        mode = query.get('intersection', 'touching')
        if mode not in ('touching', 'positive_area'):
            raise ValueError('intersection must be touching|positive_area')
        if mode == 'positive_area' and (box[0] == box[2] or box[1] == box[3]):
            filters.append('0')
        greater, less = ('>', '<') if mode == 'positive_area' else ('>=', '<=')
        # Read geometry only for the candidate objects. A global physical scan
        # parses huge unrelated routed-net payloads before counting instances.
        filters.append(f"""EXISTS (SELECT 1 FROM records p INDEXED BY records_physical_bbox
            WHERE p.snapshot_id = records.snapshot_id AND p.record_type = 'physical_context'
            AND p.record_id = records.record_id
            AND json_extract(p.payload, '$.bbox.x_max') {greater} ?
            AND json_extract(p.payload, '$.bbox.y_max') {greater} ?
            AND json_extract(p.payload, '$.bbox.x_min') {less} ?
            AND json_extract(p.payload, '$.bbox.y_min') {less} ?)""")
        params.extend(box)
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
    if query.get('connected_to') and query.get('kind') == 'instance':
        predicates = [roles[query['net_role']]] if query.get('net_role') else ['loads', 'driven_by']
        marks = ','.join('?' for _ in predicates)
        filters.append(f"""record_id IN (SELECT json_extract(p.payload, '$.parent_id')
            FROM records r JOIN records p ON p.snapshot_id=r.snapshot_id
            AND p.record_type='entities' AND p.record_id=json_extract(r.payload,'$.object_id')
            WHERE r.snapshot_id=? AND r.record_type='relations'
            AND json_extract(r.payload,'$.subject_id')=?
            AND json_extract(r.payload,'$.predicate') IN ({marks})
            AND json_extract(p.payload,'$.parent_id') IS NOT NULL)""")
        params.extend([snapshot_id, query['connected_to'], *predicates])
    elif query.get('connected_to'):
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
    if query.get('net_role') and query.get('kind') != 'instance':
        filters.append("""record_id IN (SELECT json_extract(payload, '$.object_id') FROM records
            WHERE snapshot_id = ? AND record_type = 'relations'
            AND json_extract(payload, '$.subject_id') = ?
            AND json_extract(payload, '$.predicate') = ?)""")
        params.extend([snapshot_id, query['connected_to'], roles[query['net_role']]])
    return ' AND '.join(filters), params


def list_objects(store, snapshot_id, query):
    where, params = object_filter(store, snapshot_id, query)
    representation = query.get('format', 'rows')
    if representation not in ('rows', 'columns'):
        raise ValueError('object format must be rows|columns')
    if representation == 'columns' and not query.get('fields'):
        raise ValueError('column format requires explicit fields')
    if query.get('ids'):
        wanted = [item for item in query['ids'].split(',') if item]
    # The default is the stored order, which `records_lookup`
    # (snapshot_id, record_type, ordinal) serves directly: a page costs
    # O(offset + limit).  Ordering by name by default re-sorted the whole kind on
    # *every* page - on ariane136 a single page of 10,000 instances did not return
    # in 190 s, while the same page over the store's own ordinal index takes
    # 0.17 s.  A caller that needs a ranking still asks for one explicitly.
    # Connected neighbours are small sets: return their natural name order.
    # Whole-design inventories retain indexed stored order to avoid a full sort.
    sort = query.get('sort', 'name' if query.get('connected_to') or query.get('parent_id') or query.get('parent_instance') else None)
    if sort is not None and sort not in ('name', 'fanout', 'bbox_area'):
        raise ValueError('sort must be name|fanout|bbox_area')
    if sort is None:
        clause = ''
    else:
        order = query.get('order', 'desc' if sort == 'fanout' else 'asc')
        if order not in ('asc', 'desc'):
            raise ValueError('order must be asc|desc')
        native_name = "replace(json_extract(payload, '$.name'), char(92), '')"
        if sort == 'bbox_area':
            expression = """(SELECT (json_extract(p.payload,'$.bbox.x_max')-json_extract(p.payload,'$.bbox.x_min'))
                * (json_extract(p.payload,'$.bbox.y_max')-json_extract(p.payload,'$.bbox.y_min'))
                FROM records p WHERE p.snapshot_id=records.snapshot_id AND p.record_type='physical_context'
                AND p.record_id=records.record_id LIMIT 1)"""
        else:
            expression = "json_extract(payload, '$.attributes.fanout')" if sort == 'fanout' else native_name
        tie_order = order if sort == 'bbox_area' else 'asc'
        clause = f" ORDER BY {expression} IS NULL, {expression} {order}, {native_name} {tie_order}, record_id"
    total = store.count_records(snapshot_id, 'entities', where=where, params=params)
    limit, offset = _limit(query), _offset(query)
    if query.get('ids'):
        # Answer the batch whole: a page of it would make every id past the page
        # look like it does not exist.
        limit, offset = len(wanted), 0
    rows = store.filtered(snapshot_id, 'entities', where=where, params=params,
                          order_by=clause, limit=limit, offset=offset)
    _pin_details(store, snapshot_id, rows)
    if query.get('include_engineering') is not None:
        if query.get('kind') != 'instance':
            raise ValueError('include_engineering must be 0|1 with kind=instance')
        if query_boolean(query, 'include_engineering'):
            from .engineering import instance_engineering
            for row in rows:
                row['engineering'] = instance_engineering(store, snapshot_id, row['object_id'])['instance']
    if query.get('include_physical') is not None:
        if query_boolean(query, 'include_physical'):
            _object_geometry(store, snapshot_id, rows)
    found = {str(row.get('object_id')) for row in rows}
    columns = query.get('fields')
    if columns:
        columns = columns.split(',')
        allowed = {'object_id', 'name', 'kind', 'parent_id', 'attributes', 'identity', 'evidence', 'physical', 'engineering'}
        if any(key not in allowed and not (key.partition('.')[0] in ('attributes', 'physical', 'engineering') and
                key.partition('.')[2].isidentifier()) for key in columns):
            raise ValueError('unknown object projection field')
        projected = []
        for row in rows:
            item = {key: row.get(key) for key in columns if '.' not in key}
            for section in ('attributes', 'physical', 'engineering'):
                prefix = section + '.'
                if section not in item and any(key.startswith(prefix) for key in columns):
                    item[section] = {key[len(prefix):]: (row.get(section) or {}).get(key[len(prefix):])
                                     for key in columns if key.startswith(prefix)}
            projected.append(item)
        rows = projected
    result = {'snapshot_id': snapshot_id, 'objects': rows, 'filters': query,
              'order': sort or 'stored',
              # Snapshot identity travels with the rows so the envelope's scope can
              # name design/revision/run/stage instead of leaving a caller to parse
              # the snapshot_id.  ibex already has two revisions whose final ODB is
              # byte-identical, so "which run is this number from" is a real
              # question, and `snapshot()` is cached - this costs no query.
              'snapshot': snapshot_identity(store.snapshot(snapshot_id)),
              'evidence': [ref for ref in store.snapshot(snapshot_id).get('source_artifacts', [])
                           if ref.get('category') == 'raw_design_database'],
              **_page(total, len(rows), limit, offset)}
    if query.get('ids'):
        # Distinguish an id that does not exist from one this call did not return:
        # the batch is answered in full, so anything absent is genuinely absent.
        result['found'] = len(found)
        result['missing_ids'] = [item for item in wanted if item not in found]
    if sort in ('bbox_area', 'fanout'):
        conditions = ['snapshot_id=?', "record_type='entities'"] + ([where] if where else [])
        ranked = store.connection.execute(f"""SELECT value, COUNT(*) AS tie_count FROM
            (SELECT {expression} AS value FROM records WHERE {' AND '.join(conditions)})
            GROUP BY value ORDER BY value IS NULL, value {order} LIMIT 1""",
            [snapshot_id, *params]).fetchone()
        result['ranking'] = {'candidate_count': total, 'scope': 'all objects matching filters before pagination',
            'value_basis': 'integer native bbox width times height' if sort == 'bbox_area' else 'stored native fanout',
            'unit': 'dbu^2' if sort == 'bbox_area' else 'count',
            'leading_value': ranked['value'] if ranked else None,
            'leading_tie_count': ranked['tie_count'] if ranked and ranked['value'] is not None else 0,
            'tie_rule': 'native name ' + tie_order + ', then object ID',
            'missing_value_count': store.connection.execute(
                f"SELECT COUNT(*) FROM records WHERE {' AND '.join(conditions)} AND ({expression}) IS NULL",
                [snapshot_id, *params]).fetchone()[0]}
    if representation == 'columns':
        def value(row, field):
            section, dot, key = field.partition('.')
            return (row.get(section) or {}).get(key) if dot else row.get(section)
        result['object_columns'] = columns
        result['object_rows'] = [[value(row, field) for field in columns] for row in rows]
        del result['objects']
        result['row_format'] = 'each object_rows item follows object_columns order; pagination and values unchanged'
    return result


def _object_geometry(store, snapshot_id, rows):
    """Join compact placed geometry for a whole object page; never ship wire shapes."""
    from .metadata import placement_geometry
    scale = store.snapshot(snapshot_id)['run_summary']['dbu_per_micron']
    ids = [r['object_id'] for r in rows]
    if not ids:
        return
    marks = ','.join('?' for _ in ids)
    facts = store.filtered(snapshot_id, 'physical_context',
                           where=f'record_id IN ({marks})', params=ids)
    by_id = {r['object_id']: r for r in facts}
    for row in rows:
        fact = by_id.get(row['object_id'])
        if fact is None:
            row['physical'] = {'status': 'not_extracted'}
            continue
        row['physical'] = {'status': 'available',
                           **placement_geometry(fact, scale, (row.get('attributes') or {}).get('orientation')),
                           'origin_dbu': [fact.get('x'), fact.get('y')],
                           'origin_basis': 'placement location from dbInst.getLocation; not dbInst.getOrigin',
                           'evidence': fact.get('evidence', [])}


def _pin_details(store, snapshot_id, rows):
    """Attach connected-net classification/name to just the pins on this page."""
    pins = {r['object_id']: r for r in rows if r.get('kind') == 'pin'}
    if not pins:
        return
    connections = {r['subject_id']: r['object_id'] for r in store.relations_touching(snapshot_id, list(pins))
                   if r['subject_id'] in pins and r['predicate'] == 'connected_to'}
    nets = {r['object_id']: r for r in store.entities_by_ids(snapshot_id, list(connections.values()))}
    for oid, row in pins.items():
        net = nets.get(connections.get(oid))
        attrs = dict(row.get('attributes') or {})
        attrs.update(pin_name=row['name'].rsplit('/', 1)[-1].replace('\\', ''),
                     native_name=row['name'].replace('\\', ''),
                     net_id=net['object_id'] if net else None,
                     net_name=net['name'].replace('\\', '') if net else None,
                     signal_type=(net.get('attributes') or {}).get('signal_type') if net else None,
                     signal_type_basis='connected native OpenDB net; CLOCK/POWER/GROUND are separate from SIGNAL')
        row['attributes'] = attrs


def timing_context(store, snapshot_id):
    snapshot = store.snapshot(snapshot_id)
    context = snapshot.get('run_summary', {}).get('timing_context')
    return {'snapshot_id': snapshot_id, 'snapshot': snapshot_identity(snapshot),
            'timing_context': clock_context(context),
            'evidence': snapshot.get('source_artifacts', []),
            'availability': {'timing_context': {'status': 'available' if context else 'unavailable'}}}


def routing_summary(store, snapshot_id, object_id):
    from .engineering import _entity
    object_id = _entity(store, snapshot_id, object_id, 'net')['object_id']
    # Every shape, deliberately: this counts segments per layer and vias by name, so
    # a paged list would produce a confidently wrong total rather than a short one.
    physical = store.physical(snapshot_id, object_id, routing_limit=0)
    layers, vias, via_layers = {}, {}, {}
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
            for layer in (shape.get('bottom_layer'), shape.get('top_layer')):
                if layer:
                    via_layers[layer] = via_layers.get(layer, 0) + 1
    return {'snapshot_id': snapshot_id, 'snapshot': snapshot_identity(store.snapshot(snapshot_id)),
            'object_id': object_id, 'layers': layers, 'vias': vias,
            'segment_layers': sorted(layers), 'via_layers': sorted(via_layers),
            'routing_layers_used': sorted(set(layers) | set(via_layers)),
            'via_distribution_by_layer': via_layers,
            'via_layer_basis': 'each via contributes once to its bottom layer and once to its top layer',
            'wirelength_um': sum(x['centerline_length_dbu'] for x in layers.values()) /
                             store.snapshot(snapshot_id)['run_summary']['dbu_per_micron'],
            'segment_count': sum(x['segments'] for x in layers.values()),
            'via_count': sum(vias.values()), 'unit': 'database_units',
            'length_basis': 'Manhattan distance between native dbWirePath iterator points, excludes rectangle endcaps',
            'evidence': physical.get('evidence', [])}
