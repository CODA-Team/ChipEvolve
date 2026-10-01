"""Actual native analysis scenes, explicitly defined corners, libraries and UI units."""
import re

from .identity import snapshot_identity
from .native_queries import submit_native_query


def analysis_setup(store, client, snapshot_id, native_root):
    snapshot = store.snapshot(snapshot_id)
    context = snapshot.get('run_summary', {}).get('timing_context', {})
    script = '''puts "EDA_SETUP_UNITS_BEGIN"
report_units
puts "EDA_SETUP_UNITS_END"
foreach scene [get_scenes *] {puts "EDA_SETUP_SCENE [get_full_name $scene]"}
foreach corner [get_analysis_corners *] {puts "EDA_SETUP_CORNER [sta::analysis_corner_name $corner]"}
foreach library [get_libs *] {puts "EDA_SETUP_LIBRARY [get_full_name $library]"}
puts "EDA_SETUP_COMMAND_CORNER [sta::cmd_analysis_corner]"
puts "EDA_SETUP_COMPLETE"
'''
    outcome = submit_native_query(store, client, snapshot_id,
        {'script': script, 'with_timing': True, 'wait_seconds': 120, 'max_bytes': 8192}, native_root)
    result = {'snapshot_id': snapshot_id, 'snapshot': snapshot_identity(snapshot),
        'native_query': {'run_id': outcome['run']['run_id'], 'status': outcome['status']},
        'snapshot_analysis_labels': {key: context.get(key) for key in ('corner', 'analysis', 'parasitic_mode')},
        'basis': 'fresh native getters with this snapshot original ODB, libraries, SDC and parasitic inputs',
        'scene_corner_distinction': 'scene names and explicitly defined analysis corners are separately reported; snapshot labels are separate metadata'}
    if outcome['status'] != 'succeeded':
        result['native_query']['report'] = outcome
        result['availability'] = {'analysis_setup': {'status': 'unavailable',
            'reason': 'native analysis setup query did not succeed; inspect actual process report'}}
        return result
    text = outcome['excerpt']['text']
    units = re.findall(r'^EDA_SETUP_UNITS_BEGIN\n(.*?)^EDA_SETUP_UNITS_END\s*$', text, re.M | re.S)
    command = re.findall(r'^EDA_SETUP_COMMAND_CORNER (.+)$', text, re.M)
    if len(units) != 1 or len(command) != 1 or not re.search(r'^EDA_SETUP_COMPLETE\s*$', text, re.M) or outcome['excerpt'].get('truncated'):
        raise ValueError('native analysis setup report is incomplete or malformed')
    unit_rows = re.findall(r'^\s*(time|capacitance|resistance|voltage|current|power|distance)\s+(\S+)\s*$', units[0], re.M)
    if len(unit_rows) != 7 or len(dict(unit_rows)) != 7:
        raise ValueError('native report_units must declare all seven original UI unit families')
    result.update(native_ui_units=dict(unit_rows),
        scene_names=re.findall(r'^EDA_SETUP_SCENE (.+)$', text, re.M),
        explicit_analysis_corner_names=re.findall(r'^EDA_SETUP_CORNER (.+)$', text, re.M),
        loaded_liberty_names=re.findall(r'^EDA_SETUP_LIBRARY (.+)$', text, re.M),
        command_analysis_corner=command[0],
        evidence=[outcome['source']], original_input_artifacts=outcome['original_input_artifacts'])
    return result
