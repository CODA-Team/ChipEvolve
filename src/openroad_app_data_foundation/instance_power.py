"""Fresh per-instance power from the original native clock/RC analysis."""
import base64
import json
import math
import re

from .engineering import _entity
from .identity import snapshot_identity
from .native_queries import submit_native_query
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
    script = '''set b [ord::get_db_block]
set i [odb::dbInst_getInst $b NATIVE_ID]
if {$i eq "NULL"} {error "original instance not found"}
set native_name [$i getName]
set cell [get_cells -quiet [list $native_name]]
if {[llength $cell] != 1} {error "original instance must resolve to exactly one STA cell"}
puts "EDA_INSTANCE_POWER_BEGIN"
report_power -instances $cell -format json -digits 9 SCENE
puts "EDA_INSTANCE_POWER_END"
'''.replace('NATIVE_ID', native_id)
    scene_argument = ''
    if scene is not None:
        encoded = base64.b64encode(scene.encode()).decode()
        scene_argument = '-scene [binary decode base64 {' + encoded + '}]'
    script = script.replace('SCENE', scene_argument)
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
    text = outcome['excerpt']['text']
    blocks = re.findall(r'^EDA_INSTANCE_POWER_BEGIN\s*\n(.*?)\nEDA_INSTANCE_POWER_END\s*$', text, re.M | re.S)
    if len(blocks) != 1 or outcome['excerpt'].get('truncated'):
        raise ValueError('native instance power report is incomplete or malformed; run ' + outcome['run']['run_id'])
    reports = json.loads(blocks[0])
    if (not isinstance(reports, list) or len(reports) != 1 or not isinstance(reports[0], dict)
            or not isinstance(reports[0].get('name'), str)
            or reports[0]['name'].replace('\\', '') != instance['name'].replace('\\', '')):
        raise ValueError('native instance power report is not the requested original instance; run ' + outcome['run']['run_id'])
    report = reports[0]
    keys = ('internal', 'switching', 'leakage', 'total')
    if any(not isinstance(report.get(k), (float, int)) or isinstance(report[k], bool)
           or not math.isfinite(report[k]) for k in keys):
        raise ValueError('native instance power report lacks finite original values; run ' + outcome['run']['run_id'])
    result.update(reported_name=report['name'], power_w={k: report[k] for k in keys},
                  evidence=[outcome['source']])
    return result
