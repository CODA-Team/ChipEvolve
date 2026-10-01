"""Compact engineering joins over the existing facts, with complete aggregations."""
from collections import Counter

from .identity import snapshot_identity
from .queries import _limit, _offset, _page, list_timing_paths, timing_path
from .discovery import object_filter


def object_statistics(store, snapshot_id, query):
    """Count all objects by a declared engineering property without shipping rows."""
    dimensions = {'kind': '$.kind', 'master': '$.attributes.master',
                  'master_type': '$.attributes.master_type',
                  'signal_type': '$.attributes.signal_type',
                  'driver_count': '$.attributes.driver_count',
                  'direction': '$.attributes.direction'}
    group = query.get('group_by', 'kind')
    if group not in dimensions:
        raise ValueError('group_by must be kind|master|master_type|signal_type|driver_count|direction')
    store.snapshot(snapshot_id)
    filters, values = ['snapshot_id = ?', "record_type = 'entities'"], [snapshot_id]
    where, params = object_filter(snapshot_id, query)
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
    rows = store.connection.execute(
        f'SELECT {expression} AS value, COUNT(*) AS count FROM records '
        f"WHERE {' AND '.join(filters)} GROUP BY {expression} ORDER BY count DESC, value",
        values).fetchall()
    limit, offset = _limit(query), _offset(query)
    groups = [dict(row) for row in rows]
    return {'snapshot_id': snapshot_id, 'snapshot': snapshot_identity(store.snapshot(snapshot_id)),
            'group_by': group, 'object_count': sum(row['count'] for row in groups),
            'groups': groups[offset:offset + limit],
            **_page(len(groups), len(groups[offset:offset + limit]), limit, offset)}


def _bbox_union(boxes):
    if not boxes:
        return None
    return {key: fn(box[key] for box in boxes) for key, fn in
            [('x_min', min), ('y_min', min), ('x_max', max), ('y_max', max)]}


def point_extrema(points):
    """Complete maxima and ties from numeric data points, preserving source units."""
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
        selected = tied[names[-1]]
        result[field] = {'status': 'available', 'max_value': maximum, 'unit': unit,
                         'pin_names': names, 'tie_count': len(names),
                         'selection_rule': 'greatest full pin name among exact numeric ties',
                         'selected_point': {key: selected.get(key) for key in
                                            ('pin_name', 'instance_id', 'instance_name', 'net_id',
                                             'net_name', 'cell_name', 'slew', 'load', 'arrival')}}
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


def path_engineering(store, snapshot_id, path_id, query):
    """Data-side pins, instances and nets, separate from the two clock trees."""
    detail = timing_path(store, snapshot_id, path_id, points_limit=0)
    path = detail['timing_path']
    points = [p for p in detail['timing_points'] if p.get('path_section') == 'source_path']
    ids = list(dict.fromkeys(p['instance_id'] for p in points if p.get('instance_id')))
    instances, unmapped = [], []
    entities = {row['object_id']: row for row in store.entities_by_ids(snapshot_id, ids)}
    for oid in ids:
        entity = entities.get(oid)
        if entity is None:
            unmapped.append(oid)
            continue
        physical = store.physical(snapshot_id, oid, routing_limit=1)
        attr = entity.get('attributes') or {}
        instances.append({'object_id': oid, 'name': entity['name'], 'master': attr.get('master'),
                          'is_macro': attr.get('is_macro'), 'bbox': physical.get('bbox'),
                          'placement': {'x': physical.get('x'), 'y': physical.get('y'),
                                        'orientation': attr.get('orientation')}})
    net_ids = list(dict.fromkeys(p['net_id'] for p in points if p.get('net_id')))
    nets = []
    for entity in store.entities_by_ids(snapshot_id, net_ids):
        attr = entity.get('attributes') or {}
        nets.append({'net_id': entity['object_id'], 'name': entity['name'],
                     'fanout': attr.get('fanout'), 'driver_count': attr.get('driver_count'),
                     'signal_type': attr.get('signal_type')})
    nets.sort(key=lambda n: (-(n['fanout'] if n['fanout'] is not None else -1), n['name']))
    compact_points = [{key: p.get(key) for key in
                       ('pin_name', 'instance_id', 'instance_name', 'cell_name', 'net_id', 'net_name', 'slew', 'load', 'arrival')}
                      for p in points]
    masters = Counter(item['master'] for item in instances)
    snapshot = store.snapshot(snapshot_id)
    result = {'snapshot_id': snapshot_id, 'snapshot': snapshot_identity(snapshot),
              'path': {key: path.get(key) for key in
                       ('path_id', 'startpoint', 'endpoint', 'check', 'group', 'slack',
                        'required_time', 'source_clock', 'target_clock', 'unit')},
              'data_path_pin_count': len(points), 'instance_count': len(instances),
              'net_count': len(nets), 'master_counts': dict(sorted(masters.items())),
              'instance_bbox_union': _bbox_union([r['bbox'] for r in instances if r['bbox']]),
              'dbu_per_micron': snapshot.get('run_summary', {}).get('dbu_per_micron'),
              'unmapped_instance_ids': unmapped,
              'evidence': path.get('evidence', []),
              'units': {'slack': path.get('unit'), 'slew': 's', 'load': 'F'},
              'data_point_extrema': point_extrema(points),
              'clock_points_excluded': True}
    limit, offset = _limit(query), _offset(query)
    for name, rows in [('points', compact_points), ('instances', instances), ('nets', nets)]:
        result[name] = rows[offset:offset + limit]
        result[name + '_page'] = _page(len(rows), len(result[name]), limit, offset)
    result['truncated'] = any(result[name + '_page']['truncated']
                              for name in ('points', 'instances', 'nets'))
    if query.get('include_routing') == '1':
        result['routing_layers_crossed'] = routing_layers(store, snapshot_id, net_ids)
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
    options = {**query, 'sort': 'slack', 'order': 'worst', 'offset': '0'}
    rows = list_timing_paths(store, snapshot_id, options)
    instance_paths, master_occurrences, net_ids = Counter(), Counter(), set()
    paths, data_points = [], []
    for path in rows['timing_paths']:
        detail = path_engineering(store, snapshot_id, path['path_id'], {'limit': '10000'})
        instance_paths.update(item['name'] for item in detail['instances'])
        master_occurrences.update(detail['master_counts'])
        net_ids.update(item['net_id'] for item in detail['nets'])
        data_points.extend(detail['points'])
        paths.append(detail['path'])
    nets = []
    for item in store.entities_by_ids(snapshot_id, sorted(net_ids)):
        attr = item.get('attributes') or {}
        if query.get('signal_type') and attr.get('signal_type') != query['signal_type']:
            continue
        nets.append({'net_id': item['object_id'], 'name': item['name'],
                     'fanout': attr.get('fanout'), 'driver_count': attr.get('driver_count')})
    nets.sort(key=lambda n: (-(n['fanout'] if n['fanout'] is not None else -1), n['name']))
    limit = _limit(query)
    return {'snapshot_id': snapshot_id, 'snapshot': rows['snapshot'], 'paths': paths,
            'coverage_scope': 'ranked stored paths; use timing-queries for other endpoints',
            'selected_path_count': len(paths), 'stored_matching_paths': rows['count'],
            'instance_union_count': len(instance_paths),
            'instance_names': sorted(instance_paths),
            'common_instances': sorted(name for name, count in instance_paths.items()
                                       if count == len(paths)),
            'repeated_instances': [{'name': name, 'path_count': count} for name, count in
                                   sorted(instance_paths.items(), key=lambda x: (-x[1], x[0]))[:limit]],
            'master_occurrences': dict(sorted(master_occurrences.items())),
            'data_point_extrema': point_extrema(data_points),
            'net_union_count': len(nets), 'nets': nets[:limit],
            'nets_truncated': len(nets) > limit,
            'net_names': sorted(n['name'] for n in nets)}
