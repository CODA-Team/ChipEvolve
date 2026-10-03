"""General native engineering queries, scoped to original snapshot inputs."""
import uuid
from pathlib import Path
from urllib.parse import urlencode
from .excerpts import excerpt_view
from .artifacts import DEFAULT_NATIVE_ROOT, native_excerpt
from .query_inputs import snapshot_inputs
from .timing_queries import wait_query_run


def submit_native_query(store, client, snapshot_id, query, native_root=DEFAULT_NATIVE_ROOT, *, detail='full'):
    _validate_detail(detail)
    if set(query) - {'script', 'with_timing', 'extra_files', 'odb_file', 'wait_seconds', 'max_bytes', 'format'}:
        raise ValueError('native query accepts script, with_timing, extra_files, odb_file, wait_seconds, max_bytes and format')
    script = query.get('script')
    if not isinstance(script, str) or not script.strip() or len(script.encode()) > 65536:
        raise ValueError('script must be nonempty Tcl of at most64 KiB')
    with_timing = query.get('with_timing', False)
    if type(with_timing) is not bool:
        raise ValueError('with_timing must be boolean')
    wait = query.get('wait_seconds', 0)
    maximum = query.get('max_bytes', 8192)
    if type(wait) is not int or not 0 <= wait <= 120:
        raise ValueError('wait_seconds must be an integer between 0 and 120')
    if type(maximum) is not int or not 1 <= maximum <= 65536:
        raise ValueError('max_bytes must be an integer between 1 and 65536')
    representation = query.get('format', 'text')
    if representation not in ('text', 'base64', 'full'):
        raise ValueError('excerpt format must be text|base64|full')
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
    run = client.submit(task)['run']
    result = {'run': run, 'parent_snapshot_id': snapshot_id}
    if wait:
        result.update(native_query_result(client, run['run_id'],
                      {'wait_seconds': str(wait), 'max_bytes': str(maximum), 'format': representation}))
    return native_query_view(result, detail, query)


def native_query_result(client, run_id, query, *, detail='full'):
    _validate_detail(detail)
    run = wait_query_run(client, run_id, int(query.get('wait_seconds', 0)))
    if run['project_id'] != 'eda-ai-native-query':
        raise KeyError('run is not a native engineering query')
    result = {'run_id': run_id, 'status': run['status'], 'terminal_reason': run.get('terminal_reason')}
    if run['status'] not in ('succeeded', 'failed', 'timed_out', 'cancelled', 'lost'):
        return native_query_view(result, detail, query)
    if run['status'] != 'succeeded':
        result['failure_details'] = [attempt['failure'] for stage in run.get('stages', [])
            for attempt in stage.get('attempts', []) if attempt.get('failure')]
    artifacts = client.artifacts(run_id)
    refs = [r for r in artifacts if r['kind'] == 'analysis_report' and
            (r.get('metadata') or {}).get('report') == 'native']
    if not refs and run['status'] != 'succeeded':
        return native_query_view(result, detail, query)
    if len(refs) != 1:
        raise ValueError('native query must produce exactly one original report')
    ref = refs[0]
    offset, max_bytes = int(query.get('offset', 0)), int(query.get('max_bytes', 8192))
    if offset < 0 or not 1 <= max_bytes <= 65536:
        raise ValueError('offset must be nonnegative; max_bytes must be1..65536')
    excerpt = client.artifact_excerpt(run_id, ref['artifact_id'], offset=offset, max_bytes=max_bytes)
    result = {**result, 'source': ref, 'excerpt': excerpt_view(excerpt, query),
            'parent_snapshot_id': (run.get('labels') or {}).get('parent_snapshot_id'),
            'original_input_artifacts': [r for r in artifacts
                                         if r['kind'].startswith('raw_') or
                                         (r.get('metadata') or {}).get('source_field')]}
    return native_query_view(result, detail, query)


def _validate_detail(detail):
    if detail not in ('summary', 'full'):
        raise ValueError('native query detail must be summary|full')


def native_query_view(payload, detail, query):
    """Keep actual output/status intact; move lengthy execution metadata to a read."""
    if detail == 'full':
        return payload
    result = {k: v for k, v in payload.items() if k not in ('run', 'original_input_artifacts')}
    run = payload.get('run', {})
    run_id = payload.get('run_id', run.get('run_id'))
    status = payload.get('status', run.get('status'))
    result.update(run_id=run_id, status=status)
    if run:
        result['run'] = {'run_id': run_id, 'status': status}
    options = {k: query[k] for k in ('offset', 'max_bytes', 'format') if k in query}
    result['delivery'] = {'detail': 'summary',
        'full_details': '/native-queries/' + run_id + '?' + urlencode({**options, 'detail': 'full'}),
        'retained': 'actual excerpt, report source, status, failure details and continuation offsets',
        'original_input_artifact_count': len(payload['original_input_artifacts']) if 'original_input_artifacts' in payload else None}
    return result


def complete_native_text(client, outcome):
    """Read every original report chunk for deterministic engineering extraction."""
    page, chunks = outcome, [outcome['excerpt']['text']]
    while page['excerpt']['truncated']:
        page = native_query_result(client, outcome['run']['run_id'],
            {'offset': str(page['excerpt']['next_offset']), 'max_bytes': '65536'})
        chunks.append(page['excerpt']['text'])
    return ''.join(chunks)
