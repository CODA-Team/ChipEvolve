"""Join path endpoint mappings, native connectivity, placement and source witnesses."""
from urllib.parse import quote

from .discovery import list_objects
from .engineering import instance_engineering
from .identity import snapshot_identity
from .queries import timing_path, read_evidence
from .metadata import timing_values
from .timing_facts import timing_fact_snapshot, fact_source


def path_endpoints(store, snapshot_id, path_id):
    facts = timing_fact_snapshot(store, store.snapshot(snapshot_id))
    facts_id = facts['snapshot_id']
    detail = timing_path(store, snapshot_id, path_id, points_limit=0)
    path = detail['timing_path']
    points = [p for p in detail['timing_points'] if p.get('path_section') == 'source_path']
    result = {'snapshot_id': snapshot_id, 'snapshot': snapshot_identity(store.snapshot(snapshot_id)),
        'path': timing_values({key: path.get(key) for key in ('path_id', 'startpoint', 'endpoint', 'check',
            'group', 'slack', 'unit', 'source_clock', 'target_clock', 'corner')}),
        'evidence': path.get('evidence', []), 'endpoints': {},
        'object_facts_source': fact_source(facts),
        'basis': 'exact path pin names and native connectivity; report values remain separately identified'}
    for role in ('startpoint', 'endpoint'):
        name = path.get(role)
        if not name:
            result['endpoints'][role] = {'status': 'unavailable', 'reason': 'path does not declare this pin'}
            continue
        matching = [p for p in points if (p.get('pin_name') or '').replace('\\', '') == name.replace('\\', '')]
        point = (matching[0] if role == 'startpoint' else matching[-1]) if matching else None
        item = {'name': name, 'timing_point': timing_values({key: point.get(key) for key in
            ('point_id', 'path_id', 'ordinal', 'pin_name', 'instance_name', 'cell_name', 'net_name',
             'arrival', 'slew', 'load', 'mapping_status')}, default_time_unit='s') if point else None,
            'timing_units': {'arrival': 's', 'slew': 's', 'load': 'F'}}
        if point:
            item['original_point'] = read_evidence(store, snapshot_id, 'timing_points', point['point_id'])
            item['point_fragments_path'] = '/snapshots/' + snapshot_id + '/records/timing_points/' + quote(point['point_id'], safe='') + '/fragments'
        pins = list_objects(store, facts_id, {'kind': 'pin', 'name': name, 'limit': '2'})
        if pins['count'] > 1:
            raise ValueError('path endpoint name resolves to more than one native pin')
        if not pins['objects']:
            item.update(status='unavailable', reason='native endpoint pin is absent; report facts remain available')
            result['endpoints'][role] = item
            continue
        pin = pins['objects'][0]
        attr = pin.get('attributes') or {}
        item['native_pin'] = {key: pin.get(key) for key in ('object_id', 'name', 'parent_id')}
        item['native_pin']['native_name'] = pin['name'].replace('\\', '')
        item['native_connection'] = {key: attr.get(key) for key in ('net_id', 'net_name', 'signal_type', 'direction')}
        item['evidence'] = pin.get('evidence', [])
        if pin.get('parent_id'):
            instance = instance_engineering(store, facts_id, pin['parent_id'])
            item['instance'] = instance['instance']
            item['evidence'] += instance['evidence']
        else:
            item['instance'] = None  # A top-level port has no owning instance.
        item['status'] = 'available'
        result['endpoints'][role] = item
    missing = [role for role, item in result['endpoints'].items() if item['status'] != 'available']
    if missing:
        result['availability'] = {role: {'status': 'unavailable', 'reason': result['endpoints'][role]['reason']}
                                  for role in missing}
    return result
