"""Complete two-instance connection intersections and placed bbox comparisons."""
from .engineering import _entity
from .identity import snapshot_identity
from .metadata import placement_geometry
from .queries import _limit, _offset, _page


def instance_pair(store, snapshot_id, identifier, query):
    allowed = {'with_instance', 'signal_type', 'order', 'limit', 'offset', 'fields', 'format', 'detail'}
    if set(query) - allowed or not query.get('with_instance'):
        raise ValueError('instance pair requires with_instance and accepts signal_type,order,limit,offset,fields,format,detail')
    if query.get('order', 'asc') not in ('asc', 'desc'):
        raise ValueError('instance pair order must be asc|desc')
    if 'signal_type' in query and not query['signal_type']:
        raise ValueError('signal_type must name a native net type; omit it for every type')
    limit, offset = _limit(query), _offset(query)
    entities = [_entity(store, snapshot_id, name, 'instance')
                for name in (identifier, query['with_instance'])]
    snapshot = store.snapshot(snapshot_id)
    parents = {entity['object_id'] for entity in entities}
    shared = """WITH connections AS (
        SELECT json_extract(r.payload,'$.object_id') AS net_id
        FROM records p CROSS JOIN records r ON r.snapshot_id=p.snapshot_id
        AND r.record_type='relations' AND json_extract(r.payload,'$.subject_id')=+p.record_id
        AND json_extract(r.payload,'$.subject_id') IS NOT NULL
        AND json_extract(r.payload,'$.predicate')='connected_to'
        WHERE p.snapshot_id=? AND p.record_type='entities'
        AND json_extract(p.payload,'$.parent_id') IN (?,?)
        AND +json_extract(p.payload,'$.kind')='pin'
        GROUP BY net_id HAVING COUNT(DISTINCT json_extract(p.payload,'$.parent_id'))=?
    ) SELECT n.record_id AS object_id, json_extract(n.payload,'$.name') AS native_name,
        replace(json_extract(n.payload,'$.name'),char(92),'') AS name,
        json_extract(n.payload,'$.attributes.signal_type') AS signal_type
        FROM connections c CROSS JOIN records n ON n.snapshot_id=?
        AND n.record_type='entities' AND n.record_id=c.net_id
        WHERE +json_extract(n.payload,'$.kind')='net'"""
    params = [snapshot_id, entities[0]['object_id'], entities[1]['object_id'], len(parents), snapshot_id]
    if 'signal_type' in query:
        shared += " AND json_extract(n.payload,'$.attributes.signal_type')=?"
        params.append(query['signal_type'])
    total = store.connection.execute('SELECT COUNT(*) FROM (' + shared + ')', params).fetchone()[0]
    order = query.get('order', 'asc').upper()
    rows = store.connection.execute(shared + ' ORDER BY name ' + order +
        ', native_name ' + order + ', object_id ' + order + ' LIMIT ? OFFSET ?',
        [*params, limit, offset]).fetchall()
    page = _page(total, len(rows), limit, offset)
    sides, boxes, evidence = [], [], []
    for entity in entities:
        physical = store.records(snapshot_id, 'physical_context', record_id=entity['object_id'], limit=1)
        fact = physical[0] if physical else {}
        geometry = placement_geometry(fact, snapshot['run_summary']['dbu_per_micron'],
                                      (entity.get('attributes') or {}).get('orientation'))
        boxes.append(geometry['bbox_um_array'])
        sides.append({'object_id': entity['object_id'], 'name': entity['name'].replace('\\', ''),
                      'native_name': entity['name'], 'bbox_um': geometry['bbox_um_array'],
                      'orientation': geometry['orientation']})
        evidence.extend(entity.get('evidence', []) + fact.get('evidence', []))
    delta = None
    if all(box is not None for box in boxes):
        delta = [(boxes[1][axis] + boxes[1][axis + 2] - boxes[0][axis] - boxes[0][axis + 2]) / 2
                 for axis in (0, 1)]
    return {'snapshot_id': snapshot_id, 'snapshot': snapshot_identity(snapshot),
            'left': sides[0], 'right': sides[1],
            'geometry': {'bbox_center_delta_um': delta,
                         'bbox_center_manhattan_um': sum(abs(v) for v in delta) if delta is not None else None,
                         'availability': 'complete' if delta is not None else 'missing_bbox',
                         'basis': 'transformed native placed instance bboxes in this original state'},
            'shared_nets': {'items': [dict(row) for row in rows], 'signal_type_filter': query.get('signal_type'),
                            'order': query.get('order', 'asc'),
                            **page,
                            'count_basis': 'distinct original net IDs directly connected to pins on both instances; net-own SigType filter; all pins included regardless of direction or native pin type'},
            'meaning': 'Direct shared nets and geometry do not establish a timed path or engineering causality.',
            'truncated': page['truncated'], 'evidence': evidence}
