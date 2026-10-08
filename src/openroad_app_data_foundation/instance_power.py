"""Fresh per-instance power from the original native clock/RC analysis."""
from eda_toolkits.openroad.power import instance_power_script, parse_instance_power

from .engineering import _entity
from .identity import snapshot_identity
from .native_queries import submit_native_query, complete_native_text
from .timing_facts import timing_fact_snapshot, fact_source


def instance_power(store, client, snapshot_id, identifier, query, native_root):
    if set(query) - {'fields', 'detail', 'scene'}:
        raise ValueError('instance power accepts fields,detail,scene')
    if query.get('detail', 'summary') not in ('summary', 'full'):
        raise ValueError('instance power detail must be summary|full')
    scene = query.get('scene')
    if scene is not None and (not isinstance(scene, str) or not scene.strip() or len(scene.encode()) > 256):
        raise ValueError('scene must be a nonempty native scene name of at most256 bytes')
    facts = timing_fact_snapshot(store, store.snapshot(snapshot_id))
    original_id = facts['snapshot_id']
    instance = _entity(store, original_id, identifier, 'instance')
    native_id = instance.get('attributes', {}).get('native_id')
    if not isinstance(native_id, str) or not native_id.isdecimal() or int(native_id) <= 0:
        raise ValueError('instance lacks a valid original native ID')
    script = instance_power_script(native_id, scene)
    outcome = submit_native_query(store, client, original_id,
        {'script': script, 'with_timing': True, 'wait_seconds': 120, 'max_bytes': 65536}, native_root)
    result = {'snapshot_id': snapshot_id, 'snapshot': snapshot_identity(store.snapshot(snapshot_id)),
        'object_facts_source': fact_source(facts),
        'instance': {'object_id': instance['object_id'], 'name': instance['name']},
        'unit': 'W', 'analysis': {'basis': 'original snapshot libraries, clocks and RC inputs',
                                 'requested_native_scene': scene},
        'native_query': {'run_id': outcome['run']['run_id'], 'status': outcome['status'],
                         'result_path': '/native-queries/' + outcome['run']['run_id'] + '?wait_seconds=120'},
        'basis': 'fresh native report_power -instances -format json -digits 9; no stored power values substituted'}
    if outcome['status'] != 'succeeded':
        result['native_query']['report'] = outcome
        return result
    text = complete_native_text(client, outcome)
    report = parse_instance_power(text, instance['name'], outcome['run']['run_id'])
    keys = ('internal', 'switching', 'leakage', 'total')
    result.update(reported_name=report['name'], power_w={k: report[k] for k in keys},
                  evidence=[outcome['source']])
    return result
