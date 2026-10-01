"""General native engineering queries, scoped to original snapshot inputs."""
import uuid
from pathlib import Path
from .artifacts import DEFAULT_NATIVE_ROOT, native_excerpt
from .query_inputs import snapshot_inputs
from .timing_queries import wait_query_run


def submit_native_query(store, client, snapshot_id, query, native_root=DEFAULT_NATIVE_ROOT):
    if set(query) - {'script', 'with_timing', 'extra_files', 'odb_file'}:
        raise ValueError('native query accepts script, with_timing, extra_files and odb_file')
    script = query.get('script')
    if not isinstance(script, str) or not script.strip() or len(script.encode()) > 65536:
        raise ValueError('script must be nonempty Tcl of at most64 KiB')
    with_timing = query.get('with_timing', False)
    if type(with_timing) is not bool:
        raise ValueError('with_timing must be boolean')
    snapshot = store.snapshot(snapshot_id)
    original, staged = snapshot_inputs(snapshot, with_timing)
    extras = query.get('extra_files', [])
    if not isinstance(extras, list) or len(extras) > 32 or any(not isinstance(p, str) for p in extras):
        raise ValueError('extra_files must be up to32 original flow-relative paths')
    for path in extras:
        excerpt = native_excerpt(store, snapshot_id, {'path': path, 'max_bytes': '1'}, Path(native_root))
        if path not in {p['destination'] for p in staged}:
            staged.append({'destination': path, 'source': excerpt['source']['path']})
    if extras:
        original['native_extra_paths'] = list(dict.fromkeys(extras))
    odb_file = query.get('odb_file')
    if odb_file is not None:
        if not isinstance(odb_file, str) or odb_file not in extras or not odb_file.endswith('.odb'):
            raise ValueError('odb_file must be an original .odb declared in extra_files')
        if with_timing:
            raise ValueError('alternate ODB needs its own timing inputs; load these in script using extra_files')
        original['odb_path'] = odb_file
    task_id = snapshot_id + '-native-' + uuid.uuid4().hex[:12]
    task = {'schema_version': 3, 'task_id': task_id, 'project_id': 'eda-ai-native-query',
            'design_id': snapshot['design_id'], 'plugin_id': 'openroad-data',
            'labels': {'parent_snapshot_id': snapshot_id},
            'inputs': {**original, 'adapter': 'report', 'report': 'native',
                       'script': script, 'output_directory': 'reports',
                       'parent_snapshot_id': snapshot_id}, 'staged_inputs': staged,
            'resources': {'cpu_cores': 2, 'memory_bytes': 6 * 1024**3, 'processes': 128},
            'timeout_seconds': 180, 'max_attempts': 1, 'expected_artifacts': ['analysis_report']}
    return {'run': client.submit(task)['run'], 'parent_snapshot_id': snapshot_id}


def native_query_result(client, run_id, query):
    run = wait_query_run(client, run_id, int(query.get('wait_seconds', 0)))
    if run['project_id'] != 'eda-ai-native-query':
        raise KeyError('run is not a native engineering query')
    result = {'run_id': run_id, 'status': run['status'], 'terminal_reason': run.get('terminal_reason')}
    if run['status'] != 'succeeded':
        return result
    artifacts = client.artifacts(run_id)
    refs = [r for r in artifacts if r['kind'] == 'analysis_report' and
            (r.get('metadata') or {}).get('report') == 'native']
    if len(refs) != 1:
        raise ValueError('native query must produce exactly one original report')
    ref = refs[0]
    offset, max_bytes = int(query.get('offset', 0)), int(query.get('max_bytes', 8192))
    if offset < 0 or not 1 <= max_bytes <= 65536:
        raise ValueError('offset must be nonnegative; max_bytes must be1..65536')
    excerpt = client.artifact_excerpt(run_id, ref['artifact_id'], offset=offset, max_bytes=max_bytes)
    return {**result, 'source': ref, 'excerpt': excerpt,
            'parent_snapshot_id': (run.get('labels') or {}).get('parent_snapshot_id'),
            'original_input_artifacts': [r for r in artifacts
                                         if r['kind'].startswith('raw_') or
                                         (r.get('metadata') or {}).get('source_field')]}
