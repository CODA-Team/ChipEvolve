"""Export an actual final ODB and verify durable, repeatable HTTP import."""
import json
import socket
import subprocess
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from a2_feedback_snapshot import prepare_feedback
from flow_native_baseline import WORKSPACE, now, write_json
from openroad_platform_contracts import InputFile, ResourceRequest, TaskSpec


def request(base, path, payload=None):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    message = urllib.request.Request(base + path,
        data=None if payload is None else json.dumps(payload).encode(),
        headers={'Content-Type': 'application/json'})
    with opener.open(message, timeout=600) as response:
        return json.load(response)


def export_and_import(client, final_odb, physical_run, state, profile, threads, kernel_url, environment,
                      evaluation_run=None):
    output = state / 'physical-import.json'
    snapshot_id = 'p2-aes-final-' + state.name
    task = TaskSpec(task_id='a2-final-opendb-export', project_id='p2-a2-stage',
                    design_id='aes', experiment_id=state.name, plugin_id='openroad-data',
                    inputs={'adapter': 'opendb', 'odb_path': 'inputs/final.odb',
                            'openroad_bin': profile['openroad_bin'], 'threads': threads,
                            'snapshot_id': snapshot_id, 'design_id': 'aes',
                            'revision_id': state.name, 'run_id': physical_run,
                            'stage': 'finish', 'created_at': now()},
                    labels={'run_type': 'analysis', 'analysis_of_run_id': physical_run},
                    staged_inputs=(InputFile(artifact_id=final_odb['artifact_id'], destination='inputs/final.odb'),),
                    resources=ResourceRequest(cpu_cores=threads, memory_bytes=6 << 30, processes=64))
    key = state.name + ':final-opendb-export'
    record = {'accepted': False, 'started_at': now(), 'task': task.to_dict(),
              'idempotency_key': key, 'source_odb': final_odb}
    write_json(output, record)
    run = client.submit(task.to_dict(), idempotency_key=key)['run']
    run_id = run['run_id']
    record['producer_run_id'] = run_id
    write_json(output, record)
    deadline = time.monotonic() + 3600
    while run['status'] not in {'succeeded', 'failed', 'cancelled', 'timed_out', 'lost'}:
        if time.monotonic() > deadline:
            client.cancel(run_id)
            raise TimeoutError('Actual final ODB export exceeded its budget')
        time.sleep(.5)
        run = client.run(run_id)
    record['terminal_run'] = run
    artifacts = client.artifacts(run_id)
    record['artifacts'] = artifacts
    write_json(output, record)
    if run['status'] != 'succeeded':
        raise RuntimeError('Actual final ODB export failed; inspect ' + str(output))
    bundles = [artifact for artifact in artifacts if artifact['kind'] == 'data_snapshot']
    odbs = [artifact for artifact in artifacts if artifact['store_key'] == 'inputs/final.odb']
    if len(bundles) != 1 or len(odbs) != 1 or odbs[0]['sha256'] != final_odb['sha256']:
        raise RuntimeError('Export did not retain the exact final physical ODB')
    payload = {'run_id': run_id, 'artifact_id': bundles[0]['artifact_id']}
    record['import_request'] = payload
    feedback = prepare_feedback(client, state, physical_run, evaluation_run) if evaluation_run else None
    return verify_imports(record, state, kernel_url, environment, feedback=feedback)


def verify_imports(record, state, kernel_url, environment, *, feedback=None):
    """Verify existing real exports; no physical task is submitted here."""
    output = state / 'physical-import.json'
    payload = record['import_request']
    run_id = record['producer_run_id']
    physical_run = record['task']['labels']['analysis_of_run_id']
    snapshot_id = record['task']['inputs']['snapshot_id']
    data_root = state / 'data'
    data_root.mkdir()
    with socket.socket() as endpoint:
        endpoint.bind(('127.0.0.1', 0))
        port = endpoint.getsockname()[1]
    command = [str(WORKSPACE / 'data-foundation/.venv/bin/python'), '-m', 'openroad_app_data_foundation',
               '--host', '127.0.0.1', '--port', str(port), '--db', str(data_root / 'facts.sqlite'),
               '--kernel-url', kernel_url, '--no-auto-import', '--native-root', str(data_root / 'native')]
    record['data_command'] = command
    write_json(output, record)
    base = f'http://127.0.0.1:{port}'
    if feedback is not None:
        write_json(state / 'a2-feedback.json', feedback)
    for epoch in (1, 2):
        with (data_root / f'server-{epoch}.log').open('x') as log:
            server = subprocess.Popen(command, env=environment, stdout=log, stderr=log)
            try:
                deadline = time.monotonic() + 180
                while True:
                    if server.poll() is not None or time.monotonic() > deadline:
                        raise RuntimeError('Data service failed to start; inspect ' + str(data_root))
                    with socket.socket() as probe:
                        if probe.connect_ex(('127.0.0.1', port)) == 0:
                            break
                    time.sleep(.1)
                if epoch == 1:
                    with ThreadPoolExecutor(max_workers=2) as pool:
                        imports = list(pool.map(lambda _: request(base, '/snapshots/from-run', payload), range(2)))
                    record['initial_imports'] = imports
                    write_json(output, record)
                    if imports[0] != imports[1]:
                        raise RuntimeError('Concurrent duplicate import returned different snapshots')
                receipt = request(base, '/imports/' + payload['artifact_id'])['data']['import_receipt']
                summary = request(base, '/snapshots/' + snapshot_id + '/summary?detail=full')['data']
                record[f'epoch_{epoch}'] = {'import_receipt': receipt, 'summary': summary}
                write_json(output, record)
                if (receipt['status'] != 'imported' or receipt['attempts'] != 1
                        or summary['snapshot']['producer_run_id'] != run_id
                        or summary['snapshot']['run_id'] != physical_run
                        or summary['record_counts']['entities'] <= 0
                        or summary['record_counts']['relations'] <= 0
                        or summary['record_counts']['physical_context'] <= 0):
                    raise RuntimeError('Imported physical facts or producer lineage are incomplete')
                if epoch == 2:
                    repeated = request(base, '/snapshots/from-run', payload)
                    record['repeated_after_restart'] = repeated
                    if repeated['import_receipt'] != record['epoch_1']['import_receipt']:
                        raise RuntimeError('Restart changed a successful import receipt')
                if feedback is not None:
                    request(base, '/snapshots/from-run', feedback['import_request'])
                    subprocess.run([str(WORKSPACE / 'data-interface/.venv/bin/python'),
                                    str(WORKSPACE / 'admin/query_a2_feedback.py'),
                                    '--data-url', base, '--kernel-url', kernel_url,
                                    '--binding', str(state / 'a2-feedback.json'),
                                    '--output', str(state / f'feedback-query-epoch-{epoch}.json')],
                                   env=environment, check=True)
                    imported = request(base, '/imports/' + feedback['import_request']['artifact_id'])['data']['import_receipt']
                    if imported['status'] != 'imported' or imported['attempts'] != 1:
                        raise RuntimeError('CP0 feedback import is not durable and idempotent')
                    if epoch == 2 and imported != feedback['epoch_1']:
                        raise RuntimeError('Restart changed the successful CP0 feedback import receipt')
                    feedback[f'epoch_{epoch}'] = imported
                    feedback['accepted'] = epoch == 2
                    write_json(state / 'a2-feedback.json', feedback)
            finally:
                server.terminate()
                server.wait(timeout=120)
    record.update(accepted=True, finished_at=now())
    if feedback is not None:
        record['cp0_feedback'] = {'accepted': feedback['accepted'],
                                  'snapshot_id': feedback['snapshot_id']}
    write_json(output, record)
    return {'accepted': True, 'record': str(output), 'snapshot_id': snapshot_id,
            'producer_run_id': run_id, 'physical_run_id': physical_run,
            'import_receipt': record['epoch_2']['import_receipt'],
            'record_counts': record['epoch_2']['summary']['record_counts']}
