"""Complete a fresh bounded path query and its engineering joins in one operation."""
from .timing_queries import submit_timing_query, timing_query_status
from .engineering import timing_overview
from .identity import snapshot_identity


def resolved_timing_overview(store, write_store, client, snapshot_id, query):
    count = int(query.get('limit', '5'))
    wait = int(query.get('wait_seconds', '120'))
    endpoints = int(query.get('endpoint_path_count', '1'))
    if not 0 <= wait <= 120:
        raise ValueError('wait_seconds must be between 0 and 120')
    if query.get('check', 'setup') not in ('setup', 'hold', 'both'):
        raise ValueError('check must be setup|hold|both')
    unsupported = {'source_clock', 'target_clock', 'analysis', 'corner'} & query.keys()
    if unsupported:
        raise ValueError('fresh query uses its original timing context; unsupported filters: ' + ','.join(sorted(unsupported)))
    native = {'path_count': count, 'endpoint_path_count': endpoints}
    for public, field in [('startpoint', 'from_pin'), ('endpoint', 'to_pin'), ('group', 'path_group')]:
        if query.get(public):
            native[field] = query[public]
    submitted = submit_timing_query(write_store, client, snapshot_id, native)
    outcome = timing_query_status(write_store, client, submitted['run']['run_id'], wait)
    execution = {**outcome, 'parent_snapshot_id': snapshot_id,
                 'query_snapshot_id': submitted['snapshot_id'], 'request': native}
    if outcome['status'] != 'succeeded':
        return {'snapshot_id': snapshot_id, 'snapshot': snapshot_identity(store.snapshot(snapshot_id)),
                'query_execution': execution,
                'availability': {'fresh_path_facts': {'status': outcome['status'],
                    'reason': outcome.get('terminal_reason'),
                    'status_query': '/timing-queries/' + outcome['run_id'] + '?wait_seconds=120',
                    'engineering_query': '/snapshots/' + submitted['snapshot_id'] + '/timing-overview'}}}
    if outcome['snapshot_ids'] != [submitted['snapshot_id']]:
        raise ValueError('fresh query did not import its submitted snapshot')
    child = store.snapshot(submitted['snapshot_id'])
    if child.get('run_summary', {}).get('timing_context', {}).get('parent_snapshot_id') != snapshot_id:
        raise ValueError('fresh query imported a different parent snapshot')
    options = {key: value for key, value in query.items()
               if key not in ('resolve', 'wait_seconds', 'endpoint_path_count', 'fields')}
    options['check'] = query.get('check', 'setup')
    result = timing_overview(store, child['snapshot_id'], options)
    result['coverage_scope'] = 'fresh native bounded query over the original snapshot inputs; not a stored path sample'
    result['query_execution'] = execution
    return result
