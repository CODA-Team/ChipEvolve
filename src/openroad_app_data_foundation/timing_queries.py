"""Submit a bounded STA query using only artifacts attached to its snapshot."""
import time
from .bundle import load_run_bundle
from eda_toolkits.jobs import timing_task, validate_timing_query
from .timing_facts import timing_fact_snapshot


def submit_timing_query(store, client, snapshot_id, query):
    validate_timing_query(query)
    snapshot = store.snapshot(snapshot_id)
    facts = timing_fact_snapshot(store, snapshot)
    task = timing_task(snapshot, query, facts_snapshot_id=facts["snapshot_id"])
    inputs = task["inputs"]
    result = client.submit(task)["run"]
    return {'run': result, 'snapshot_id': inputs['snapshot_id'], 'parent_snapshot_id': snapshot_id}


def timing_query_status(store, client, run_id, wait_seconds=0, *, import_results=True):
    run = wait_query_run(client, run_id, wait_seconds)
    if run['project_id'] != 'eda-ai-timing-query':
        raise KeyError('run is not a timing query')
    snapshots = []
    if run['status'] == 'succeeded':
        for artifact in client.artifacts(run_id):
            if artifact['kind'] != 'data_snapshot': continue
            if import_results and not store.imported(artifact['artifact_id']):
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
