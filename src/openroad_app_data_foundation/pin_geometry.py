"""Join stored pin identity with its actual native placement getters."""
from eda_toolkits.openroad.pins import pin_geometry_script, parse_pin_geometry

from .engineering import _entity, instance_engineering
from .discovery import list_objects
from .identity import snapshot_identity
from .native_queries import submit_native_query


def pin_engineering(store, client, snapshot_id, identifier, native_root):
    pin = _entity(store, snapshot_id, identifier, 'pin')
    pin = list_objects(store, snapshot_id, {'kind': 'pin', 'ids': pin['object_id'],
                                         'limit': '1'})['objects'][0]
    snapshot = store.snapshot(snapshot_id)
    scale = snapshot['run_summary']['dbu_per_micron']
    kind = pin['object_id'].split(':', 1)[0]
    if kind not in ('iterm', 'bterm'):
        raise ValueError('pin must have an original OpenDB ITerm or BTerm identity')
    native_id = (pin.get('attributes') or {}).get('native_id')
    if not isinstance(native_id, str) or not native_id.isdecimal() or int(native_id) <= 0:
        raise ValueError('pin lacks a valid original native ID')
    cls, getter, script = pin_geometry_script(kind, native_id)
    outcome = submit_native_query(store, client, snapshot_id,
        {'script': script, 'with_timing': False, 'wait_seconds': 120, 'max_bytes': 4096}, native_root)
    result = {'snapshot_id': snapshot_id, 'snapshot': snapshot_identity(snapshot),
              'pin': {'object_id': pin['object_id'], 'name': pin['name'],
                      'native_name': pin['name'].replace('\\', ''), 'native_class': cls,
                      'parent_id': pin.get('parent_id'), 'dbu_per_micron': scale,
                      'position_basis': 'OpenDB ' + cls + '.' + getter},
              'native_query': {'run_id': outcome['run']['run_id'], 'status': outcome['status']}}
    attr = pin['attributes']
    result['native_connection'] = {key: attr.get(key) for key in
                                  ('net_id', 'net_name', 'signal_type', 'direction')}
    result['native_connection']['signal_type_basis'] = attr['signal_type_basis']
    result['instance'] = instance_engineering(store, snapshot_id, pin['parent_id'])['instance'] if pin.get('parent_id') else None
    if outcome['status'] != 'succeeded':
        result['native_query']['report'] = outcome
        result['availability'] = {'pin_geometry': {'status': 'unavailable',
            'reason': 'native query did not succeed; inspect its actual status/report'}}
        return result
    text = outcome['excerpt']['text']
    coordinates, bbox = parse_pin_geometry(text, outcome['excerpt'].get('truncated', False))
    result['pin'].update(position_success=coordinates is not None, position_dbu=coordinates,
        position_um=[v / scale for v in coordinates] if coordinates is not None else None,
        bbox_dbu=bbox, bbox_um=[v / scale for v in bbox])
    if coordinates is None:
        result['availability'] = {'pin_position': {'status': 'unavailable',
            'reason': 'native position getter returned success=false; zero coordinates are not substituted'}}
    result['evidence'] = [outcome['source'], *pin.get('evidence', [])]
    return result
