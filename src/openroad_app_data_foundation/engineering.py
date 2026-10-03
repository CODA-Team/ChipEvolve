"""Compact engineering joins over the existing facts, with complete aggregations."""
from collections import Counter
from urllib.parse import urlencode

from .identity import snapshot_identity
from .queries import _limit, _offset, _page, list_timing_paths, timing_path
from .discovery import BATCH_ID_LIMIT, object_filter, list_objects, query_boolean
from .metadata import placement_geometry, timing_values
from .timing_facts import timing_fact_snapshot, fact_source
from .pin_summary import pin_type_summary
from .path_increments import data_path_increments


def _entity(store, snapshot_id, identifier, kind):
    rows = store.entities_by_ids(snapshot_id, [identifier])
    if not rows:
        rows = store.entities_named(snapshot_id, kind, identifier)
    if not rows:
        raise KeyError(kind + ' not found: ' + identifier)
    if len(rows) != 1 or rows[0].get('kind') != kind:
        raise ValueError('identifier must resolve to one ' + kind)
    return rows[0]


def net_engineering(store, snapshot_id, identifier, query):
    """Named connectivity with complete counts and bounded, ordered pin lists."""
    entity = _entity(store, snapshot_id, identifier, 'net')
    if query.get('traverse', '0') not in ('0', '1'):
        raise ValueError('traverse must be 0|1')
    include_instances = query_boolean(query, 'include_instances') if 'include_instances' in query else False
    include_physical = query_boolean(query, 'include_physical') if 'include_physical' in query else False
    if include_physical and not include_instances:
        raise ValueError('include_physical requires include_instances=1')
    if not include_instances and any(key in query for key in ('instance_is_macro', 'instance_limit', 'instance_offset', 'instance_order')):
        raise ValueError('instance filters and paging require include_instances=1')
    result = {'snapshot_id': snapshot_id, 'snapshot': snapshot_identity(store.snapshot(snapshot_id)),
              'net': {'object_id': entity['object_id'], 'name': entity['name'],
                      **{key: (entity.get('attributes') or {}).get(key) for key in
                         ('signal_type', 'fanout', 'fanout_basis', 'inout_pin_count')}},
              'evidence': entity.get('evidence', []), 'order': 'bytewise native name ascending'}
    for role in ('driver', 'load'):
        page = list_objects(store, snapshot_id, {'kind': 'pin', 'connected_to': entity['object_id'],
            'net_role': role, 'sort': 'name', 'fields': 'object_id,name',
            'limit': query.get('limit', '50'), 'offset': query.get('offset', '0')})
        result[role + '_pins'] = [row['name'].replace('\\', '') for row in page['objects']]
        result[role + '_count'] = page['count']
        result[role + '_page'] = {key: page[key] for key in
                               ('count', 'returned', 'limit', 'offset', 'truncated', 'next_offset')}
        if query.get('traverse') == '1':
            result[role + '_traversal'] = _connection_traversal(store, snapshot_id, entity['object_id'], role, _limit(query))
        if include_instances:
            options = {'kind': 'instance', 'connected_to': entity['object_id'], 'net_role': role,
                'sort': 'name', 'order': query.get('instance_order', 'asc'), 'fields': 'name',
                'limit': query.get('instance_limit', query.get('limit', '50')),
                'offset': query.get('instance_offset', query.get('offset', '0'))}
            if 'instance_is_macro' in query:
                options['is_macro'] = query['instance_is_macro']
            instances = list_objects(store, snapshot_id, options)
            result[role + '_instances'] = {'names': [row['name'].replace('\\', '') for row in instances['objects']],
                'is_macro_filter': query_boolean(query, 'instance_is_macro') if 'instance_is_macro' in query else None,
                'order': query.get('instance_order', 'asc'),
                'count_basis': 'distinct owning instance IDs across all matching native pin relations; ports excluded; shared pin parents count once',
                **{key: instances[key] for key in ('count', 'returned', 'limit', 'offset', 'truncated', 'next_offset')}}
            if include_physical:
                statistics = object_statistics(store, snapshot_id, {**options, 'group_by': 'is_macro',
                    'include_physical': '1', 'limit': '3', 'offset': '0'})
                result[role + '_instances'].update(geometry=statistics['geometry'],
                    groups=statistics['groups'], group_by='is_macro',
                    aggregation_scope='all matching distinct owning instances; independent of instance or pin pages')
    result['state'] = ('no_driver' if result['driver_count'] == 0 else
                       'single_driver' if result['driver_count'] == 1 else 'multi_driver')
    result['truncated'] = any(result[role + '_page']['truncated'] for role in ('driver', 'load'))
    if include_instances:
        result['truncated'] = result['truncated'] or any(result[role + '_instances']['truncated'] for role in ('driver', 'load'))
    expected = entity.get('attributes') or {}
    if (expected.get('fanout') is not None and result['load_count'] != expected['fanout']) or (
            expected.get('driver_count') is not None and result['driver_count'] != expected['driver_count']):
        result['availability'] = {'complete_connectivity': {'status': 'unavailable',
            'reason': 'stored native counts and resolved pin relations disagree; use native query to complete connectivity'}}
    return result


def _connection_traversal(store, snapshot_id, net_id, role, page_size):
    """Walk the actual paged query and verify complete identity/order coverage."""
    rows, pages, offset, total = [], [], 0, None
    while True:
        page = list_objects(store, snapshot_id, {'kind': 'pin', 'connected_to': net_id,
            'net_role': role, 'sort': 'name', 'fields': 'object_id,name,parent_id',
            'limit': str(page_size), 'offset': str(offset)})
        if total is not None and page['count'] != total:
            raise ValueError('connectivity changed during traversal')
        total = page['count']
        current = [{'object_id': row['object_id'], 'name': row['name'].replace('\\', ''),
                    'parent_id': row['parent_id']} for row in page['objects']]
        rows.extend(current)
        pages.append({'offset': offset, 'returned': len(current), 'next_offset': page['next_offset'],
                      'first_name': current[0]['name'] if current else None,
                      'last_name': current[-1]['name'] if current else None})
        if page['next_offset'] is None:
            break
        offset = page['next_offset']
    names = [row['name'] for row in rows]
    ids = [row['object_id'] for row in rows]
    first = names[:page_size]
    last_offset = pages[-1]['offset']
    unique_count = len(set(ids))
    ordered = names == sorted(names)
    return {'page_size': page_size, 'pages_read': len(pages), 'total_count': total,
            'returned_count': len(rows), 'unique_object_count': unique_count,
            'unique_name_count': len(set(names)), 'duplicate_object_count': len(ids) - unique_count,
            'internal_instance_count': len({row['parent_id'] for row in rows if row['parent_id'] is not None}),
            'internal_instance_count_basis': 'distinct non-null pin parent IDs across every traversed page; ports excluded',
            'missing_object_count': total - unique_count, 'ordering_verified': ordered,
            'completed': len(rows) == total == unique_count and ordered,
            'first_page': first, 'last_page': names[last_offset:],
            'pin_names': names, 'pages': pages,
            'basis': 'actual successive paged queries from offset zero; counts/identities/order verified over every returned row'}


def instance_engineering(store, snapshot_id, identifier):
    """Instance identity, placed geometry and complete pin counts in one read."""
    entity = _entity(store, snapshot_id, identifier, 'instance')
    attr = entity.get('attributes') or {}
    snapshot = store.snapshot(snapshot_id)
    physical = store.physical(snapshot_id, entity['object_id'], routing_limit=1)
    counts = object_statistics(store, snapshot_id, {'kind': 'pin',
        'parent_id': entity['object_id'], 'group_by': 'signal_type', 'limit': '100'})
    groups = {row['value']: row['count'] for row in counts['groups']}
    connections = store.connection.execute("""SELECT
        json_extract(n.payload,'$.attributes.signal_type') AS signal_type,
        COUNT(DISTINCT n.record_id) AS count
        FROM records p CROSS JOIN records r ON r.snapshot_id=p.snapshot_id
        AND r.record_type='relations' AND json_extract(r.payload,'$.subject_id')=+p.record_id
        AND json_extract(r.payload,'$.subject_id') IS NOT NULL
        AND json_extract(r.payload,'$.predicate')='connected_to'
        CROSS JOIN records n ON n.snapshot_id=r.snapshot_id AND n.record_type='entities'
        AND n.record_id=json_extract(r.payload,'$.object_id')
        WHERE p.snapshot_id=? AND p.record_type='entities'
        AND json_extract(p.payload,'$.parent_id')=?
        AND +json_extract(p.payload,'$.kind')='pin'
        GROUP BY signal_type""", (snapshot_id, entity['object_id'])).fetchall()
    net_counts = {row['signal_type']: row['count'] for row in connections}
    native_pins = store.connection.execute("""SELECT
        json_extract(p.payload,'$.attributes.native_pin_signal_type') AS native_pin_signal_type,
        json_extract(n.payload,'$.name') AS net_name
        FROM records p LEFT JOIN records r ON r.snapshot_id=p.snapshot_id
        AND r.record_type='relations' AND json_extract(r.payload,'$.subject_id')=+p.record_id
        AND json_extract(r.payload,'$.subject_id') IS NOT NULL
        AND json_extract(r.payload,'$.predicate')='connected_to'
        LEFT JOIN records n ON n.snapshot_id=r.snapshot_id AND n.record_type='entities'
        AND n.record_id=json_extract(r.payload,'$.object_id')
        WHERE p.snapshot_id=? AND p.record_type='entities'
        AND json_extract(p.payload,'$.parent_id')=?
        AND +json_extract(p.payload,'$.kind')='pin'""", (snapshot_id, entity['object_id'])).fetchall()
    return {'snapshot_id': snapshot_id, 'snapshot': snapshot_identity(snapshot),
            'instance': {'object_id': entity['object_id'], 'name': entity['name'],
                         'native_name': entity['name'].replace('\\', ''),
                         'master': attr.get('master'), 'master_type': attr.get('master_type'),
                         'is_macro': attr.get('is_macro'),
                         **placement_geometry(physical, snapshot['run_summary']['dbu_per_micron'], attr.get('orientation')),
                         'total_pin_count': counts['object_count'],
                         'signal_pin_count': groups.get('SIGNAL', 0),
                         'distinct_connected_net_count': sum(net_counts.values()),
                         'distinct_signal_net_count': net_counts.get('SIGNAL', 0),
                         'distinct_net_counts_by_signal_type': [dict(row) for row in connections],
                         'net_count_basis': 'distinct native net IDs connected to this instance; shared pin connections counted once',
                         'pin_counts_by_connected_net_type': [{'signal_type': key, 'count': value}
                             for key, value in groups.items()],
                         'unclassified_pin_count': groups.get(None, 0),
                         'pin_type_basis': 'connected native OpenDB net SigType; unconnected pins are explicitly unclassified'},
            'native_pin_classification': pin_type_summary([dict(row) for row in native_pins]),
            'evidence': physical.get('evidence', [])}


def compare_inventory(store, left_id, right_id, query, root, client=None):
    """Compare native inventories and separately identified original stage reports."""
    from .artifacts import run_inventory
    include_area = query.get('include_native_area', '0')
    if include_area not in ('0', '1'):
        raise ValueError('include_native_area must be 0|1')
    if include_area == '1' and client is None:
        raise ValueError('native area comparison requires an execution service')
    metric_names = tuple(query.get('metrics', '').split(',')) if query.get('metrics') else ()
    sides = []
    for sid in (left_id, right_id):
        snapshot = store.snapshot(sid)
        instances = object_statistics(store, sid, {'kind': 'instance', 'group_by': 'kind'})
        nets = object_statistics(store, sid, {'kind': 'net', 'group_by': 'signal_type'})
        groups = {row['value']: row['count'] for row in nets['groups']}
        side = {'snapshot': snapshot_identity(snapshot), 'instance_count': instances['object_count'],
                'net_count': nets['object_count'], 'signal_net_count': groups.get('SIGNAL', 0),
                'count_basis': 'complete native object inventory; instances include fillers; SIGNAL excludes CLOCK/POWER/GROUND',
                'evidence': [ref for ref in snapshot.get('source_artifacts', [])
                             if ref.get('category') == 'raw_design_database']}
        if metric_names:
            inventory = run_inventory(store, sid, root, stage=snapshot['stage'], metric_names=metric_names)
            side['original_metric_reports'] = [{'source': report['relative_path'],
                 'metric_values': report['metric_values'], 'value_basis': report['value_basis']}
                 for stage in inventory['stages'] for report in stage['metric_reports']]
        if include_area == '1':
            from .native_inventory import design_area
            side['native_area'] = design_area(store, client, sid, root)
        sides.append(side)
    result = {'from': sides[0], 'to': sides[1],
            'deltas': {key: sides[1][key] - sides[0][key] for key in
                       ('instance_count', 'net_count', 'signal_net_count')},
            'metric_basis': 'original reports retain substage/source identity; no earlier report is silently relabeled as final',
            'evidence': sides[0]['evidence'] + sides[1]['evidence']}
    if include_area == '1':
        if all(side['native_area']['status'] == 'succeeded' for side in sides):
            result['deltas']['native_area_um2'] = sides[1]['native_area']['value'] - sides[0]['native_area']['value']
        else:
            result['availability'] = {'native_area_delta': {'status': 'unavailable',
                'reason': 'one or both actual native area queries did not succeed; inspect their reports'}}
    return result


def _geometry_groups(store, filters, values, expression):
    """Aggregate every matched instance's placed bbox using integer DBU areas."""
    return store.connection.execute(f"""
        WITH candidates AS (
            SELECT snapshot_id, record_id, {expression} AS value FROM records
            WHERE {' AND '.join(filters)} LIMIT -1
        ), boxes AS (
            SELECT c.value,
                json_extract(p.payload,'$.bbox.x_min') AS xmin,
                json_extract(p.payload,'$.bbox.y_min') AS ymin,
                json_extract(p.payload,'$.bbox.x_max') AS xmax,
                json_extract(p.payload,'$.bbox.y_max') AS ymax
            FROM candidates c LEFT JOIN records p
              ON p.snapshot_id=c.snapshot_id AND p.record_type='physical_context'
              AND p.record_id=c.record_id
        ), measured AS (
            SELECT *, CASE WHEN xmin IS NOT NULL AND ymin IS NOT NULL
                AND xmax>=xmin AND ymax>=ymin THEN (xmax-xmin)*(ymax-ymin) END AS area
            FROM boxes
        )
        SELECT value, COUNT(*) AS count, COUNT(area) AS geometry_count,
            COALESCE(SUM(area),0) AS available_bbox_area_dbu2,
            MIN(CASE WHEN area IS NOT NULL THEN xmin END) AS x_min,
            MIN(CASE WHEN area IS NOT NULL THEN ymin END) AS y_min,
            MAX(CASE WHEN area IS NOT NULL THEN xmax END) AS x_max,
            MAX(CASE WHEN area IS NOT NULL THEN ymax END) AS y_max
        FROM measured GROUP BY value ORDER BY count DESC, value
        """, values).fetchall()


def _geometry_summary(groups, snapshot):
    scale = snapshot['run_summary'].get('dbu_per_micron')
    if not isinstance(scale, (int, float)) or scale <= 0:
        raise ValueError('physical statistics require a positive dbu_per_micron')
    core = snapshot['run_summary'].get('core_bbox')
    core_area = (core['x_max']-core['x_min'])*(core['y_max']-core['y_min']) / scale**2 if core else None
    for row in groups:
        matched, known = row['count'], row.pop('geometry_count')
        area = row.pop('available_bbox_area_dbu2')
        bbox = {key: row.pop(key) for key in ('x_min', 'y_min', 'x_max', 'y_max')}
        complete = known == matched
        row['geometry'] = {'status': 'complete' if complete else 'partial',
            'matched_count': matched, 'geometry_count': known, 'missing_geometry_count': matched-known,
            'available_bbox_area_dbu2': area, 'available_bbox_area_um2': area / scale**2,
            'total_bbox_area_um2': area / scale**2 if complete else None,
            'bbox_union_um': {key: value / scale for key, value in bbox.items()} if known else None}
    details = [row['geometry'] for row in groups]
    matched = sum(row['matched_count'] for row in details)
    known = sum(row['geometry_count'] for row in details)
    area = sum(row['available_bbox_area_dbu2'] for row in details)
    complete = matched == known
    total = area / scale**2 if complete else None
    return {'status': 'complete' if complete else 'partial', 'matched_count': matched,
        'geometry_count': known, 'missing_geometry_count': matched-known,
        'available_bbox_area_dbu2': area, 'available_bbox_area_um2': area / scale**2,
        'total_bbox_area_um2': total, 'core_bbox_um': {k: v / scale for k, v in core.items()} if core else None,
        'core_area_um2': core_area,
        'percent_of_core_area': 100*total/core_area if total is not None and core_area and core_area > 0 else None,
        'bbox_union_um': _bbox_union([row['bbox_union_um'] for row in details if row['bbox_union_um']]),
        'dbu_per_micron': scale,
        'area_basis': 'sum of complete placed object bounding-box areas; overlaps counted for each object; regional filters select whole objects, not clipped pieces',
        'aggregation_scope': 'all matching objects and groups, independent of result pagination'}


def object_statistics(store, snapshot_id, query):
    """Count all objects by a declared engineering property without shipping rows."""
    dimensions = {'kind': '$.kind', 'master': '$.attributes.master',
                  'master_type': '$.attributes.master_type',
                  'signal_type': '$.attributes.signal_type',
                  'driver_count': '$.attributes.driver_count',
                  'direction': '$.attributes.direction', 'is_macro': '$.attributes.is_macro'}
    group = query.get('group_by', 'kind')
    if group not in dimensions:
        raise ValueError('group_by must be kind|master|master_type|signal_type|driver_count|direction|is_macro')
    names = query_boolean(query, 'include_names') if 'include_names' in query else False
    if not names and any(key in query for key in ('names_limit', 'names_offset')):
        raise ValueError('names paging requires include_names=1')
    store.snapshot(snapshot_id)
    filters, values = ['snapshot_id = ?', "record_type = 'entities'"], [snapshot_id]
    where, params = object_filter(store, snapshot_id, {k: v for k, v in query.items()
        if k not in ('include_names', 'names_limit', 'names_offset')})
    if where:
        filters.append(where)
        values.extend(params)
    expression = f"json_extract(payload, '{dimensions[group]}')"
    if group == 'signal_type' and query.get('kind') == 'pin':
        expression = """(SELECT json_extract(n.payload,'$.attributes.signal_type')
            FROM records r JOIN records n ON n.snapshot_id=r.snapshot_id
            AND n.record_type='entities' AND n.record_id=json_extract(r.payload,'$.object_id')
            WHERE r.snapshot_id=records.snapshot_id AND r.record_type='relations'
            AND json_extract(r.payload,'$.subject_id') = +records.record_id
            AND json_extract(r.payload,'$.predicate')='connected_to' LIMIT 1)"""
    # Group ordering must not force a whole-kind scan for an exact, small
    # connected/name/parent/id set. Unary + preserves values while permitting
    # the existing identity/macro indexes to select the actual candidates first.
    grouping = '+' + expression if any(query.get(key) for key in
        ('name', 'parent_id', 'parent_instance', 'ids', 'connected_to', 'region')) else expression
    geometry = None
    physical = query_boolean(query, 'include_physical') if 'include_physical' in query else False
    if physical:
        if query.get('kind') != 'instance':
            raise ValueError('physical statistics require kind=instance')
        rows = _geometry_groups(store, filters, values, expression)
    else:
        rows = store.connection.execute(
            f'SELECT {expression} AS value, COUNT(*) AS count FROM records '
            f"WHERE {' AND '.join(filters)} GROUP BY {grouping} ORDER BY count DESC, value",
            values).fetchall()
    limit, offset = _limit(query), _offset(query)
    groups = [dict(row) for row in rows]
    if physical:
        geometry = _geometry_summary(groups, store.snapshot(snapshot_id))
    result = {'snapshot_id': snapshot_id, 'snapshot': snapshot_identity(store.snapshot(snapshot_id)),
            'group_by': group, 'object_count': sum(row['count'] for row in groups),
            'groups': groups[offset:offset + limit],
            'evidence': [ref for ref in store.snapshot(snapshot_id).get('source_artifacts', [])
                         if ref.get('category') == 'raw_design_database'],
            **_page(len(groups), len(groups[offset:offset + limit]), limit, offset)}
    if geometry is not None:
        result['geometry'] = geometry
    if names:
        size = _limit({'limit': query.get('names_limit', '20')})
        start = _offset({'offset': query.get('names_offset', '0')})
        for item in result['groups']:
            selected = store.connection.execute(
                "SELECT json_extract(payload, '$.name') AS name FROM records WHERE " +
                ' AND '.join(filters) + f' AND (+{expression}) IS ? ORDER BY name, record_id LIMIT ? OFFSET ?',
                [*values, item['value'], size, start]).fetchall()
            page = _page(item['count'], len(selected), size, start)
            item['names'] = {'items': [r['name'] for r in selected], **page,
                'order': 'bytewise stored name ascending, then object ID',
                'count_basis': 'all objects in this exact filtered group; page size never changes count'}
            if page['next_offset'] is not None:
                item['names']['continuation'] = '/snapshots/' + snapshot_id + '/objects/statistics?' + urlencode(
                    {**{k: v for k, v in query.items() if k != 'fields'}, 'names_offset': page['next_offset']})
    if group == 'signal_type' and query.get('kind') == 'net':
        result['counts_by_signal_type'] = {row['value']: row['count'] for row in groups if row['value'] is not None}
        result['unclassified_net_count'] = sum(row['count'] for row in groups if row['value'] is None)
        result['power_ground_net_count'] = sum(row['count'] for row in groups if row['value'] in ('POWER', 'GROUND'))
        result['power_ground_count_basis'] = 'native SigType POWER + GROUND over all matching nets; distinct from OpenDB isSpecial flag'
    return result


def _bbox_union(boxes):
    if not boxes:
        return None
    return {key: fn(box[key] for box in boxes) for key, fn in
            [('x_min', min), ('y_min', min), ('x_max', max), ('y_max', max)]}


def point_extrema(points, tie_rule='name_desc'):
    """Complete maxima and ties from numeric data points, preserving source units."""
    rules = {'name_desc': 'greatest full pin name among exact numeric ties',
             'name_asc': 'smallest full pin name among exact numeric ties',
             'source_order': 'first data point in report order among exact numeric ties'}
    if tie_rule not in rules:
        raise ValueError('point tie_rule must be name_desc|name_asc|source_order')
    result = {}
    for field, unit in [('slew', 's'), ('load', 'F')]:
        values = [p for p in points if isinstance(p.get(field), (int, float))]
        if not values:
            result[field] = {'status': 'not_extracted', 'max_value': None, 'unit': unit,
                             'pin_names': [], 'selected_point': None}
            continue
        maximum = max(p[field] for p in values)
        tied = {p['pin_name']: p for p in values if p[field] == maximum}
        names = sorted(tied)
        selected = next(p for p in values if p[field] == maximum) if tie_rule == 'source_order' else tied[names[-1 if tie_rule == 'name_desc' else 0]]
        suffix = 'ns' if unit == 's' else 'ff'
        result[field] = {'status': 'available', 'max_value': maximum, 'unit': unit,
                         'max_value_' + suffix: timing_values({field: maximum})[field + '_' + suffix],
                         'pin_names': names, 'tie_count': len(names),
                         'selection_rule': rules[tie_rule],
                         'selected_point': timing_values({key: selected.get(key) for key in
                                            ('point_id', 'path_id', 'pin_id', 'pin_name', 'instance_id',
                                             'instance_name', 'net_id', 'net_name', 'cell_name', 'slew', 'load', 'arrival', 'evidence')})}
    return result


def routing_totals(store, snapshot_id):
    """Compute full-design geometry from every stored native wire shape."""
    snapshot = store.snapshot(snapshot_id)
    rows = store.connection.execute("""SELECT
        json_extract(shape.value, '$.routing_type') AS kind,
        COUNT(*) AS count,
        SUM(json_extract(shape.value, '$.centerline_length_dbu')) AS length_dbu,
        SUM(CASE WHEN json_extract(shape.value, '$.routing_type') = 'segment'
            AND json_extract(shape.value, '$.centerline_length_dbu') IS NULL THEN 1 ELSE 0 END) AS missing
        FROM records r, json_each(r.payload, '$.routing') shape
        WHERE r.snapshot_id = ? AND r.record_type = 'physical_context'
        AND r.record_id LIKE 'net:%' GROUP BY kind""", (snapshot_id,)).fetchall()
    if any(row['missing'] for row in rows):
        raise ValueError('wire shapes lack native centerline lengths; re-extract the database')
    kinds = {row['kind']: row for row in rows}
    length = kinds['segment']['length_dbu'] if 'segment' in kinds else 0
    scale = snapshot['run_summary']['dbu_per_micron']
    return {'snapshot_id': snapshot_id, 'snapshot': snapshot_identity(snapshot),
            'segment_count': kinds['segment']['count'] if 'segment' in kinds else 0,
            'via_count': kinds['via']['count'] if 'via' in kinds else 0,
            'centerline_length_dbu': length, 'wirelength_um': length / scale,
            'dbu_per_micron': scale, 'coverage_scope': 'all stored native wire shapes',
            'length_basis': 'native iterator centreline in dbu; excludes rectangle endcaps',
            'evidence': [r for r in snapshot.get('source_artifacts', [])
                         if r.get('category') == 'raw_design_database']}


def _path_instance_classification(store, snapshot_id, ids, incomplete):
    counts, matched = Counter(), 0
    for offset in range(0, len(ids), BATCH_ID_LIMIT):
        statistics = object_statistics(store, snapshot_id, {'kind': 'instance',
            'ids': ','.join(ids[offset:offset+BATCH_ID_LIMIT]), 'group_by': 'is_macro', 'limit': '10000'})
        counts.update({row['value']: row['count'] for row in statistics['groups']})
        matched += statistics['object_count']
    missing = len(ids) - matched
    unknown = sum(count for value, count in counts.items() if value not in (0, 1))
    complete = not (incomplete or missing or unknown)
    return {'macro_count': counts.get(1, 0) if complete else None,
            'standard_cell_count': counts.get(0, 0) if complete else None,
            'instance_classification_coverage': {'status': 'complete' if complete else 'partial',
                'classified_instance_count': counts.get(0, 0) + counts.get(1, 0),
                'unclassified_instance_count': unknown, 'missing_instance_count': missing}}


def path_engineering(store, snapshot_id, path_id, query):
    """Data-side pins, instances and nets, separate from the two clock trees."""
    snapshot = store.snapshot(snapshot_id)
    facts = timing_fact_snapshot(store, snapshot)
    facts_id = facts['snapshot_id']
    detail = timing_path(store, snapshot_id, path_id, points_limit=0)
    path = detail['timing_path']
    points = [p for p in detail['timing_points'] if p.get('path_section') == 'source_path']
    ids = list(dict.fromkeys(p['instance_id'] for p in points if p.get('instance_id')))
    instances, unmapped = [], []
    entities = {row['object_id']: row for row in store.entities_by_ids(facts_id, ids)}
    for oid in ids:
        entity = entities.get(oid)
        if entity is None:
            unmapped.append(oid)
            continue
        physical = store.physical(facts_id, oid, routing_limit=1)
        attr = entity.get('attributes') or {}
        instances.append({'object_id': oid, 'name': entity['name'], 'master': attr.get('master'),
                          'is_macro': attr.get('is_macro'), 'bbox': physical.get('bbox'),
                          'placement': {'x': physical.get('x'), 'y': physical.get('y'),
                                        'orientation': attr.get('orientation')}})
    net_ids = list(dict.fromkeys(p['net_id'] for p in points if p.get('net_id')))
    nets = []
    for entity in store.entities_by_ids(facts_id, net_ids):
        attr = entity.get('attributes') or {}
        nets.append({'net_id': entity['object_id'], 'name': entity['name'],
                     'fanout': attr.get('fanout'), 'driver_count': attr.get('driver_count'),
                     'signal_type': attr.get('signal_type')})
    found_nets = {n['net_id'] for n in nets}
    if query.get('signal_type'):
        nets = [n for n in nets if n['signal_type'] == query['signal_type']]
    nets.sort(key=lambda n: (-(n['fanout'] if n['fanout'] is not None else -1), n['name']))
    unresolved_points = [p.get('point_id') or p.get('pin_name') for p in points
                         if p.get('mapping_status') == 'unmapped'
                         or (p.get('net_name') and not p.get('net_id'))
                         or (p.get('instance_name') and not p.get('instance_id'))]
    unresolved_nets = [oid for oid in net_ids if oid not in found_nets]
    incomplete = bool(unresolved_points or unresolved_nets or unmapped)
    compact_points = [timing_values({key: p.get(key) for key in
                       ('point_id', 'path_id', 'pin_id', 'pin_name', 'instance_id', 'instance_name', 'cell_name', 'net_id', 'net_name', 'slew', 'load', 'arrival')})
                      for p in points]
    masters = Counter(item['master'] for item in instances)
    snapshot = store.snapshot(snapshot_id)
    result = {'snapshot_id': snapshot_id, 'snapshot': snapshot_identity(snapshot),
              'path': timing_values({key: path.get(key) for key in
                       ('path_id', 'startpoint', 'endpoint', 'check', 'group', 'slack',
                        'data_arrival_time', 'required_time', 'margin', 'crpr', 'path_type',
                        'analysis', 'corner', 'source_clock', 'target_clock',
                        'source_clock_edge', 'target_clock_edge', 'unit')}),
              'data_path_pin_count': len(points), 'instance_count': len(instances),
              'instance_names': sorted(item['name'].replace('\\', '') for item in instances),
              'data_pin_names': [p.get('pin_name') for p in points],
              'data_pin_names_scope': 'complete source_path sequence in report order, preserving repeated pins; independent of point pagination',
              'net_count': len(nets), 'net_names': sorted(n['name'].replace('\\', '') for n in nets),
              'net_signal_type_filter': query.get('signal_type'),
              'object_facts_source': fact_source(facts), 'master_counts': dict(sorted(masters.items())),
              'instance_bbox_union': _bbox_union([r['bbox'] for r in instances if r['bbox']]),
              'dbu_per_micron': facts.get('run_summary', {}).get('dbu_per_micron'),
              'unmapped_instance_ids': unmapped,
              'association_coverage': {'status': 'partial' if incomplete else 'complete',
                                       'unresolved_point_ids': unresolved_points,
                                       'unresolved_net_ids': unresolved_nets,
                                       'candidate_domain': 'all data points of this selected stored path',
                                       'ranking_scope': 'resolved nets only' if incomplete else 'all associated nets'},
              'evidence': path.get('evidence', []),
              'units': {'slack': path.get('unit'), 'slew': 's', 'load': 'F'},
              'data_point_extrema': point_extrema(points, query.get('tie_rule', 'name_desc')),
              'data_path_increments': data_path_increments(points),
              'clock_points_excluded': True}
    scale = facts.get('run_summary', {}).get('dbu_per_micron')
    result['instance_bbox_union_um'] = placement_geometry(
        {'bbox': result['instance_bbox_union']}, scale)['bbox_um'] if scale else None
    result.update(_path_instance_classification(store, facts_id, ids, incomplete))
    if incomplete:
        result['availability'] = {'complete_association_aggregates': {'status': 'unavailable',
            'reason': 'some point/object associations are missing; resolved-subset counts and rankings are not full-domain results',
            'native_completion': f'/snapshots/{snapshot_id}/native-queries'}}
    limit, offset = _limit(query), _offset(query)
    for name, rows in [('points', compact_points), ('instances', instances), ('nets', nets)]:
        result[name] = rows[offset:offset + limit]
        result[name + '_page'] = _page(len(rows), len(result[name]), limit, offset)
    result['truncated'] = any(result[name + '_page']['truncated']
                              for name in ('points', 'instances', 'nets'))
    if query.get('include_routing') == '1':
        result['routing_layers_crossed'] = routing_layers(store, facts_id, [n['net_id'] for n in nets])
    return result


def routing_layers(store, snapshot_id, net_ids):
    """Distinct layers of every segment and both sides of every via on selected nets."""
    if not net_ids:
        return []
    marks = ','.join('?' for _ in net_ids)
    rows = store.connection.execute(f"""SELECT DISTINCT
        json_extract(shape.value,'$.layer') AS layer,
        json_extract(shape.value,'$.bottom_layer') AS bottom_layer,
        json_extract(shape.value,'$.top_layer') AS top_layer
        FROM records r, json_each(r.payload,'$.routing') shape
        WHERE r.snapshot_id=? AND r.record_type='physical_context'
        AND r.record_id IN ({marks})""", [snapshot_id, *net_ids]).fetchall()
    return sorted({v for row in rows for v in row if v})


def timing_overview(store, snapshot_id, query):
    """Worst paths and repeated instances/masters, over the declared sample."""
    if query.get('check') == 'both':
        views = {check: timing_overview(store, snapshot_id, {**query, 'check': check})
                 for check in ('setup', 'hold')}
        incomplete = [check for check, view in views.items()
                      if view['association_coverage']['status'] != 'complete']
        result = {'snapshot_id': snapshot_id, 'snapshot': snapshot_identity(store.snapshot(snapshot_id)),
                'coverage_scope': 'separate setup and hold domains; limit applies to each check',
                'checks': views, 'object_facts_source': views['setup']['object_facts_source'],
                'association_coverage': {'status': 'partial' if incomplete else 'complete',
                                         'incomplete_checks': incomplete}}
        if incomplete:
            result['availability'] = {'complete_association_aggregates': {'status': 'unavailable',
                'reason': 'some selected checks have unresolved associations; inspect each check coverage'}}
        return result
    options = {**{key: value for key, value in query.items() if key not in ('fields', 'include_physical', 'tie_rule')},
               'sort': 'slack', 'order': 'worst', 'offset': '0'}
    rows = list_timing_paths(store, snapshot_id, options)
    facts = timing_fact_snapshot(store, store.snapshot(snapshot_id))
    facts_id = facts['snapshot_id']
    instance_paths, master_occurrences, net_ids = Counter(), Counter(), set()
    paths, data_points, extrema_sources, incomplete_paths = [], [], {}, []
    path_details, instance_details = [], {}
    for path in rows['timing_paths']:
        detail = path_engineering(store, snapshot_id, path['path_id'],
                                  {'limit': '10000', 'tie_rule': query.get('tie_rule', 'name_desc'), **({'signal_type': query['signal_type']} if query.get('signal_type') else {})})
        path_details.append(detail)
        instance_details.update((item['object_id'], item) for item in detail['instances'])
        instance_paths.update(item['name'] for item in detail['instances'])
        master_occurrences.update(detail['master_counts'])
        net_ids.update(item['net_id'] for item in detail['nets'])
        data_points.extend(detail['points'])
        for value in detail['data_point_extrema'].values():
            point = value.get('selected_point')
            if point:
                extrema_sources[point.get('point_id')] = point.get('evidence')
        if detail['association_coverage']['status'] != 'complete':
            incomplete_paths.append(path['path_id'])
        paths.append(detail['path'])
    nets = []
    for item in store.entities_by_ids(facts_id, sorted(net_ids)):
        attr = item.get('attributes') or {}
        if query.get('signal_type') and attr.get('signal_type') != query['signal_type']:
            continue
        nets.append({'net_id': item['object_id'], 'name': item['name'],
                     'fanout': attr.get('fanout'), 'driver_count': attr.get('driver_count')})
    nets.sort(key=lambda n: (-(n['fanout'] if n['fanout'] is not None else -1), n['name']))
    limit = _limit({'limit': query.get('net_limit', query.get('limit', '50'))})
    extrema = point_extrema(data_points, query.get('tie_rule', 'name_desc'))
    for value in extrema.values():
        point = value.get('selected_point')
        if point:
            point['evidence'] = extrema_sources.get(point.get('point_id'))
    if query.get('include_physical') == '1':
        joined = {}
        for value in extrema.values():
            point = value.get('selected_point') or {}
            instance_id = point.get('instance_id')
            if instance_id:
                if instance_id not in joined:
                    joined[instance_id] = instance_engineering(store, facts_id, instance_id)['instance']
                point['instance'] = joined[instance_id]
    result = {'snapshot_id': snapshot_id, 'snapshot': rows['snapshot'], 'paths': paths,
            'coverage_scope': 'ranked stored paths; use timing-queries for other endpoints',
            'selected_path_count': len(paths), 'stored_matching_paths': rows['count'],
            'instance_union_count': len(instance_paths),
            'instance_names': sorted(instance_paths),
            'common_instances': sorted(name for name, count in instance_paths.items()
                                       if count == len(paths)),
            'repeated_instances': [{'name': name, 'path_count': count} for name, count in
                                   sorted(instance_paths.items(), key=lambda x: (-x[1], x[0]))[:limit]],
            'master_occurrences': dict(sorted(master_occurrences.items())),
            'data_point_extrema': extrema,
            'net_union_count': len(nets), 'nets': nets[:limit],
            'nets_truncated': len(nets) > limit,
            'net_names': sorted(n['name'].replace('\\', '') for n in nets),
            'object_facts_source': fact_source(facts),
            'association_coverage': {'status': 'partial' if incomplete_paths else 'complete',
                                     'incomplete_path_ids': incomplete_paths}}
    if query.get('include_path_details') == '1':
        result['path_details'] = path_details
    result.update(_path_instance_classification(store, facts_id, list(instance_details), bool(incomplete_paths)))
    if query.get('include_physical') == '1':
        result['instances'] = sorted(instance_details.values(), key=lambda item: item['name'])
        result['instance_bbox_union'] = _bbox_union([item['bbox'] for item in instance_details.values() if item['bbox']])
        result['dbu_per_micron'] = facts.get('run_summary', {}).get('dbu_per_micron')
        result['instance_bbox_union_um'] = placement_geometry(
            {'bbox': result['instance_bbox_union']}, result['dbu_per_micron'])['bbox_um']
    if query.get('include_connectivity') == '1':
        for net in result['nets']:
            net['connectivity'] = net_engineering(store, facts_id, net['net_id'],
                {'limit': query.get('connectivity_pin_limit', '5')})
    if incomplete_paths:
        result['availability'] = {'complete_association_aggregates': {'status': 'unavailable',
            'reason': 'some selected paths have unresolved associations; do not report subset rankings as complete'}}
    return result
