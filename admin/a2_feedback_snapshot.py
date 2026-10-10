"""Turn measured CP0 feedback into a portable snapshot through public tasks."""
import json
import time

from flow_native_baseline import now, write_json
from openroad_platform_contracts import InputFile, ResourceRequest, TaskSpec


def prepare_feedback(client, state, physical_run, evaluation_run):
    metadata = next(row for row in client.artifacts(evaluation_run)
                    if row['store_key'] == 'a2-evaluation.json')
    measured = json.loads(client.artifact_bytes(evaluation_run, metadata['artifact_id']))
    snapshot_id = 'a2-cp0-' + state.name
    task = TaskSpec(task_id='a2-cp0-feedback-snapshot', project_id='p2-a2-stage',
                    design_id='aes', experiment_id=state.name, plugin_id='openroad-data',
                    inputs={'adapter': 'orfs', 'metadata_path': 'inputs/a2-evaluation.json',
                            'snapshot_id': snapshot_id, 'design_id': 'aes',
                            'revision_id': state.name, 'run_id': physical_run,
                            'stage': 'eval_final', 'created_at': now()},
                    labels={'run_type': 'analysis', 'analysis_of_run_id': physical_run},
                    staged_inputs=(InputFile(artifact_id=metadata['artifact_id'],
                                            destination='inputs/a2-evaluation.json'),),
                    resources=ResourceRequest(cpu_cores=1, memory_bytes=512 << 20, processes=8))
    record = {'accepted': False, 'snapshot_id': snapshot_id, 'task': task.to_dict(),
              'evaluation_run_id': evaluation_run, 'physical_run_id': physical_run,
              'measured': measured, 'metadata': metadata}
    output = state / 'a2-feedback.json'
    write_json(output, record)
    run = client.submit(task.to_dict(), idempotency_key=state.name + ':cp0-snapshot')['run']
    record['producer_run_id'] = run['run_id']
    write_json(output, record)
    deadline = time.monotonic() + 180
    while run['status'] not in {'succeeded', 'failed', 'cancelled', 'timed_out', 'lost'}:
        if time.monotonic() > deadline:
            client.cancel(run['run_id'])
            raise TimeoutError('CP0 feedback snapshot exceeded its budget')
        time.sleep(.2)
        run = client.run(run['run_id'])
    record['terminal_run'] = run
    record['artifacts'] = client.artifacts(run['run_id'])
    write_json(output, record)
    if run['status'] != 'succeeded':
        raise RuntimeError('CP0 feedback snapshot failed; inspect ' + str(output))
    bundle = next(row for row in record['artifacts'] if row['kind'] == 'data_snapshot')
    copied = next(row for row in record['artifacts']
                  if row['store_key'] == 'inputs/a2-evaluation.json')
    if copied['sha256'] != metadata['sha256']:
        raise RuntimeError('Metric snapshot did not retain the exact evaluation metadata')
    record['import_request'] = {'run_id': run['run_id'], 'artifact_id': bundle['artifact_id']}
    record['metadata_copy'] = copied
    write_json(output, record)
    return record
