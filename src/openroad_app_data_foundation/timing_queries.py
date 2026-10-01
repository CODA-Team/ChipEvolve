"""Submit a bounded STA query using only artifacts attached to its snapshot."""
import uuid
import time
from datetime import datetime, timezone
from .bundle import load_run_bundle
from .query_inputs import snapshot_inputs


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
    original, staged = snapshot_inputs(snapshot)
    inputs = {**original, 'adapter': 'opensta', 'snapshot_id': snapshot_id + '-query-' + uuid.uuid4().hex[:12],
              'design_id': snapshot['design_id'], 'revision_id': snapshot['revision_id'],
              'run_id': snapshot['run_id'], 'stage': snapshot['stage'],
              'created_at': datetime.now(timezone.utc).isoformat(), 'parent_snapshot_id': snapshot_id,
              'output_directory': 'query-data', 'analysis': snapshot['run_summary']['timing_context'].get('analysis'),
              'corner': snapshot['run_summary']['timing_context'].get('corner'), 'unit': 's', **query}
    task = {'schema_version': 3, 'task_id': inputs['snapshot_id'],
            'project_id': 'eda-ai-timing-query', 'design_id': snapshot['design_id'],
            'plugin_id': 'openroad-data', 'inputs': inputs, 'staged_inputs': staged,
            'resources': {'cpu_cores': 2, 'memory_bytes': 6 * 1024**3, 'processes': 128},
            'timeout_seconds': 180, 'max_attempts': 1, 'expected_artifacts': ['data_snapshot']}
    result = client.submit(task)["run"]
    return {'run': result, 'snapshot_id': inputs['snapshot_id'], 'parent_snapshot_id': snapshot_id}


def timing_query_status(store, client, run_id, wait_seconds=0):
    run = wait_query_run(client, run_id, wait_seconds)
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


def wait_query_run(client, run_id, wait_seconds):
    if not 0 <= wait_seconds <= 120:
        raise ValueError('wait_seconds must be between 0 and 120')
    deadline = time.monotonic() + wait_seconds
    run = client.run(run_id)
    while run['status'] not in ('succeeded', 'failed', 'timed_out', 'cancelled', 'lost'):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(1, remaining))
        run = client.run(run_id)
    return run
