"""Join stored pin identity with its actual native placement getters."""
import re

from .engineering import _entity
from .identity import snapshot_identity
from .native_queries import submit_native_query


def pin_engineering(store, client, snapshot_id, identifier, native_root):
    pin = _entity(store, snapshot_id, identifier, 'pin')
    snapshot = store.snapshot(snapshot_id)
    scale = snapshot['run_summary']['dbu_per_micron']
    kind = pin['object_id'].split(':', 1)[0]
    if kind not in ('iterm', 'bterm'):
        raise ValueError('pin must have an original OpenDB ITerm or BTerm identity')
    native_id = (pin.get('attributes') or {}).get('native_id')
    if not isinstance(native_id, str) or not native_id.isdecimal() or int(native_id) <= 0:
        raise ValueError('pin lacks a valid original native ID')
    cls, getter = ('dbITerm', 'getAvgXY') if kind == 'iterm' else ('dbBTerm', 'getFirstPinLocation')
    script = '\n'.join([
        'set b [[[ord::get_db] getChip] getBlock]',
        f'set p [odb::{cls}_get{cls[2:]} $b {native_id}]',
        f'puts "EDA_PIN_POSITION [$p {getter}]"',
        'set box [$p getBBox]',
        'puts "EDA_PIN_BBOX [$box xMin] [$box yMin] [$box xMax] [$box yMax]"'])
    outcome = submit_native_query(store, client, snapshot_id,
        {'script': script, 'with_timing': False, 'wait_seconds': 120, 'max_bytes': 4096}, native_root)
    result = {'snapshot_id': snapshot_id, 'snapshot': snapshot_identity(snapshot),
              'pin': {'object_id': pin['object_id'], 'name': pin['name'],
                      'native_name': pin['name'].replace('\\', ''), 'native_class': cls,
                      'parent_id': pin.get('parent_id'), 'dbu_per_micron': scale,
                      'position_basis': 'OpenDB ' + cls + '.' + getter},
              'native_query': {'run_id': outcome['run']['run_id'], 'status': outcome['status']}}
    if outcome['status'] != 'succeeded':
        result['native_query']['report'] = outcome
        result['availability'] = {'pin_geometry': {'status': 'unavailable',
            'reason': 'native query did not succeed; inspect its actual status/report'}}
        return result
    text = outcome['excerpt']['text']
    position = re.search(r'^EDA_PIN_POSITION ([01]) (-?\d+) (-?\d+)\s*$', text, re.M)
    box = re.search(r'^EDA_PIN_BBOX (-?\d+) (-?\d+) (-?\d+) (-?\d+)\s*$', text, re.M)
    if position is None or box is None or outcome['excerpt'].get('truncated'):
        raise ValueError('native pin geometry report is incomplete or malformed')
    coordinates = [int(v) for v in position.groups()[1:]] if position[1] == '1' else None
    bbox = [int(v) for v in box.groups()]
    if bbox[0] > bbox[2] or bbox[1] > bbox[3]:
        raise ValueError('native pin bounding box is invalid')
    result['pin'].update(position_success=coordinates is not None, position_dbu=coordinates,
        position_um=[v / scale for v in coordinates] if coordinates is not None else None,
        bbox_dbu=bbox, bbox_um=[v / scale for v in bbox])
    if coordinates is None:
        result['availability'] = {'pin_position': {'status': 'unavailable',
            'reason': 'native position getter returned success=false; zero coordinates are not substituted'}}
    result['evidence'] = [outcome['source'], *pin.get('evidence', [])]
    return result
