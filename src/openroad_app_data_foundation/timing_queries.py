"""Submit a bounded STA query using only artifacts attached to its snapshot."""
import uuid
from datetime import datetime, timezone
from .bundle import load_run_bundle


def submit_timing_query(store, client, snapshot_id, query):
    fields = {'from_pin', 'to_pin', 'path_group', 'path_count', 'endpoint_path_count'}
    if set(query) - fields:
        raise ValueError('unknown timing query field')
    count = query.get('path_count', 5)
    if type(count) is not int or not 1 <= count <= 200:
        raise ValueError('path_count must be between 1 and 200')
    # OpenSTA's -endpoint_path_count: how many paths one endpoint may contribute.
    # The default equals path_count (N variants of one endpoint, the historical
    # behaviour); 1 makes the N reported paths N distinct endpoints, which is
    # what "the N worst paths" means when the reference flow reports one path per
    # endpoint.  Without it the sampler is the only place that distinction could
    # live, and it does not exist there.
    endpoints = query.get('endpoint_path_count')
    if endpoints is not None and (type(endpoints) is not int or not 1 <= endpoints <= 200):
        raise ValueError('endpoint_path_count must be between 1 and 200')
    for key in ('from_pin', 'to_pin', 'path_group'):
        if key in query and (not isinstance(query[key], str) or not query[key] or len(query[key]) > 4096):
            raise ValueError(f'{key} must be a native name')
    snapshot = store.snapshot(snapshot_id)
    context = snapshot.get('run_summary', {}).get('timing_context')
    if not context or not context.get('executor'):
        raise ValueError('snapshot lacks its executable timing context')
    refs = snapshot.get('source_artifacts', [])
    roles = {'raw_design_database': 'odb_path'}
    inputs = {'adapter': 'opensta', 'snapshot_id': snapshot_id + '-query-' + uuid.uuid4().hex[:12],
              'design_id': snapshot['design_id'], 'revision_id': snapshot['revision_id'],
              'run_id': snapshot['run_id'], 'stage': snapshot['stage'],
              'created_at': datetime.now(timezone.utc).isoformat(), 'parent_snapshot_id': snapshot_id,
              'output_directory': 'query-data', 'openroad_bin': context['executor'],
              'analysis': context.get('analysis'), 'corner': context.get('corner'), 'unit': 's',
              'parasitic_mode': context['parasitic_mode'], **query}
    paths = {context['constraints']: 'sdc_path', **{path: 'library' for path in context['libraries']}}
    if context.get('rc_script'): paths[context['rc_script']] = 'rc_script_path'
    if context.get('parasitics'): paths[context['parasitics']] = 'spef_path'
    staged, libraries = [], []
    for ref in refs:
        key = roles.get(ref.get('category')) or paths.get(ref.get('logical_path'))
        if not key: continue
        path = ref['logical_path']
        staged.append({'destination': path, 'artifact_id': ref['artifact_id']})
        if key == 'library': libraries.append(path)
        else: inputs[key] = path
    if 'odb_path' not in inputs or set(libraries) != set(context['libraries']):
        raise ValueError('snapshot lacks the original database or library artifacts')
    inputs['liberty_paths'] = libraries
    task = {'schema_version': 3, 'task_id': inputs['snapshot_id'],
            'project_id': 'eda-ai-timing-query', 'design_id': snapshot['design_id'],
            'plugin_id': 'openroad-data', 'inputs': inputs, 'staged_inputs': staged,
            'resources': {'cpu_cores': 2, 'memory_bytes': 6 * 1024**3, 'processes': 128},
            'timeout_seconds': 180, 'max_attempts': 1, 'expected_artifacts': ['data_snapshot']}
    result = client.submit(task)["run"]
    return {'run': result, 'snapshot_id': inputs['snapshot_id'], 'parent_snapshot_id': snapshot_id}


def timing_query_status(store, client, run_id):
    run = client.run(run_id)
    if run['project_id'] != 'eda-ai-timing-query':
        raise KeyError('run is not a timing query')
    snapshots = []
    if run['status'] == 'succeeded':
        for artifact in client.artifacts(run_id):
            if artifact['kind'] != 'data_snapshot': continue
            if not store.imported(artifact['artifact_id']):
                store.register_import(artifact['artifact_id'], load_run_bundle(client, run_id, artifact['artifact_id']))
            snapshots = [s['snapshot_id'] for s in store.snapshots(design_id=run['design_id'])
                         if any(r.get('artifact_id') == artifact['artifact_id'] for r in s['source_artifacts'])]
    return {'run_id': run_id, 'status': run['status'], 'snapshot_ids': snapshots,
            'terminal_reason': run.get('terminal_reason')}
