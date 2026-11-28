"""Complete P2 data checks from preserved physical runs without rerunning them."""
import argparse
import json
import os
import socket
import subprocess
import time
from pathlib import Path

from a2_physical_import import verify_imports
from flow_native_baseline import WORKSPACE, digest, now, write_json
from openroad_platform_client import KernelClient
from run_a2_stage_acceptance import capture_environment


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--physical-state', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    original, output = args.physical_state.resolve(), args.output.resolve()
    if output.exists():
        raise SystemExit('Preserve existing evidence and use a fresh data acceptance directory.')
    prior = json.loads((original / 'receipt.json').read_text())
    if any(prior['jobs'][stage]['status'] != 'succeeded'
           for stage in ('place', 'cts', 'route_finish', 'eval_final')):
        raise SystemExit('All original physical and evaluation stages must have succeeded.')
    cancellation = json.loads((original / 'routing-cancellation.json').read_text())
    if cancellation['accepted'] is not True:
        raise SystemExit('The original actual routing cancellation did not pass.')
    output.mkdir(parents=True)
    environment = dict(os.environ)
    environment.pop('PYTHONPATH', None)
    environment['NO_PROXY'] = environment['no_proxy'] = '127.0.0.1,localhost'
    current = capture_environment(output / 'environment-start', environment)
    previous = json.loads((original / 'environment-start/manifest.json').read_text())
    physical_unchanged = all(current[name]['files'] == previous[name]['files']
                             and current[name]['packages'] == previous[name]['packages']
                             for name in ('execution-foundation', 'toolkits', 'data-foundation', 'data-interface'))
    if not physical_unchanged:
        raise RuntimeError('Executing components differ from the original real-stage environment.')
    with socket.socket() as endpoint:
        endpoint.bind(('127.0.0.1', 0))
        port = endpoint.getsockname()[1]
    command = list(prior['gateway_command']) + ['--api-only']
    command[command.index('--port') + 1] = str(port)
    url = f'http://127.0.0.1:{port}'
    record = {'accepted': False, 'status': 'starting', 'started_at': now(),
              'physical_state': str(original), 'original_failure': prior.get('error'),
              'execution_components_unchanged': physical_unchanged,
              'harness_repair': {'reason': 'POST /snapshots/from-run returns a direct import result, not a data envelope.',
                                 'previous_hash': previous['acceptance']['files']['a2_physical_import.py'],
                                 'repaired_hash': digest(WORKSPACE / 'admin/a2_physical_import.py'),
                                 'continuation_hash': digest(Path(__file__))},
              'gateway_command': command}
    receipt = output / 'receipt.json'
    write_json(receipt, record)
    client = KernelClient(url, timeout=60)
    with (output / 'kernel-api.log').open('x') as log:
        server = subprocess.Popen(command, env=environment, stdout=log, stderr=log)
        try:
            deadline = time.monotonic() + 180
            while True:
                if server.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError('API-only kernel failed to open the preserved state.')
                with socket.socket() as probe:
                    if probe.connect_ex(('127.0.0.1', port)) == 0:
                        break
                time.sleep(.1)
            before = client.runs(project_id='p2-a2-stage', limit=100)
            for stage, job in prior['jobs'].items():
                actual = client.run(job['run_id'])
                artifacts = client.artifacts(job['run_id'])
                if (actual['status'] != 'succeeded' or not any(
                        row['artifact_id'] == job['archive']['artifact_id']
                        and row['sha256'] == job['archive']['sha256'] for row in artifacts)):
                    raise RuntimeError('Preserved successful stage or archive changed: ' + stage)
            physical = json.loads((original / 'physical-import.json').read_text())
            feedback = json.loads((original / 'a2-feedback.json').read_text())
            record['status'] = 'verifying_data'
            write_json(receipt, record)
            record['data_acceptance'] = verify_imports(physical, output, url, environment, feedback=feedback)
            after = client.runs(project_id='p2-a2-stage', limit=100)
            record['no_tasks_resubmitted'] = {row['run_id'] for row in before} == {row['run_id'] for row in after}
            finished = capture_environment(output / 'environment-finish', environment)
            record['environment_unchanged_during_data_checks'] = all(
                current[name]['files'] == finished[name]['files']
                and current[name]['packages'] == finished[name]['packages'] for name in current)
            if not record['no_tasks_resubmitted'] or not record['environment_unchanged_during_data_checks']:
                raise RuntimeError('Data continuation resubmitted work or changed its execution environment.')
            record.update(status='completed', accepted=True, finished_at=now(),
                          physical_jobs={stage: job['run_id'] for stage, job in prior['jobs'].items()},
                          cancellation=cancellation['times'],
                          native_baseline_comparison=prior['native_baseline_comparison'])
            write_json(receipt, record)
            write_json(original / 'p2-acceptance.json', record)
            print(json.dumps({'accepted': True, 'physical_tasks_repeated': False}), flush=True)
        except Exception as error:
            record.update(status='failed', finished_at=now(), error=type(error).__name__ + ': ' + str(error))
            write_json(receipt, record)
            raise
        finally:
            server.terminate()
            server.wait(timeout=120)


if __name__ == '__main__':
    main()
