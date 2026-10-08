"""Actual native analysis scenes, explicitly defined corners, libraries and UI units."""
from eda_toolkits.openroad.setup import analysis_setup_script, parse_analysis_setup

from .identity import snapshot_identity
from .native_queries import submit_native_query


def analysis_setup(store, client, snapshot_id, native_root):
    snapshot = store.snapshot(snapshot_id)
    context = snapshot.get('run_summary', {}).get('timing_context', {})
    script = analysis_setup_script()
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
    result.update(**parse_analysis_setup(text, outcome['excerpt'].get('truncated', False)),
                  evidence=[outcome['source']], original_input_artifacts=outcome['original_input_artifacts'])
    return result
