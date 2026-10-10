"""Run a real AES stage chain through a fresh HTTP kernel after P1 acceptance."""
import argparse
import json
import math
import os
import re
import socket
import subprocess
import time
from pathlib import Path

from a2_physical_import import export_and_import
from a2_stage_cancellation import measure_routing_cancel
from flow_native_baseline import WORKSPACE, digest, now, write_json
from openroad_platform_client import KernelClient
from openroad_platform_contracts import InputFile, ResourceRequest, TaskSpec

TERMINAL = {'succeeded', 'failed', 'cancelled', 'timed_out', 'lost'}


def capture_environment(destination, environment):
    destination.mkdir()
    records = {}
    package_code = ('import importlib.metadata as m,json; '
                    'print(json.dumps(sorted([(d.metadata["Name"],d.version) '
                    'for d in m.distributions()])))')
    for name in ('execution-foundation', 'toolkits', 'data-foundation', 'data-interface'):
        project = WORKSPACE / name
        names = subprocess.check_output(['git', 'ls-files', '-z', '--', 'src', 'contracts',
                                         'core', 'gateway', 'pyproject.toml'], cwd=project).decode().split('\0')
        files = {path: digest(project / path) for path in names if path
                 and (path.startswith('src/') or '/src/' in path or path.endswith('pyproject.toml'))
                 and (project / path).is_file()}
        patch = destination / (name + '.patch')
        patch.write_bytes(subprocess.check_output(['git', 'diff', '--binary', 'HEAD', '--',
                          'src', 'contracts', 'core', 'gateway', 'pyproject.toml'], cwd=project))
        records[name] = {'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'],
                            cwd=project, text=True).strip(), 'files': files,
                         'patch_sha256': digest(patch), 'packages': json.loads(subprocess.check_output(
                             [str(project / '.venv/bin/python'), '-c', package_code], env=environment))}
    records['acceptance'] = {'files': {
        name: digest(WORKSPACE / 'admin' / name) for name in (
            'run_a2_stage_acceptance.py', 'prepare_a2_stage_inputs.py',
            'a2_stage_cancellation.py', 'measure_http_cancellation.py',
            'a2_physical_import.py', 'a2_feedback_snapshot.py', 'query_a2_feedback.py',
            'flow_native_baseline.py')}, 'packages': []}
    write_json(destination / 'manifest.json', records)
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native-run', type=Path, required=True)
    parser.add_argument('--state', type=Path, required=True)
    args = parser.parse_args()
    native = args.native_run.resolve()
    acceptance = json.loads((native / 'p1-acceptance.json').read_text())
    if acceptance['accepted'] is not True:
        raise SystemExit('The referenced native campaign has not passed P1.')
    state = args.state.resolve()
    if state.exists():
        raise SystemExit('Use a fresh acceptance state directory.')
    state.mkdir(parents=True)
    inputs_root = state / 'inputs'
    subprocess.run(['/usr/bin/python', str(WORKSPACE / 'admin/prepare_a2_stage_inputs.py'),
                    '--native-run', str(native), '--output', str(inputs_root),
                    '--config-iteration', '1'], check=True)
    profile = json.loads((inputs_root / 'profile.json').read_text())
    threads = json.loads((native / 'receipt.json').read_text())['threads_per_candidate']
    cp0 = float((native / 'source/flow/designs/nangate45/aes/cp0.txt').read_text())
    plugins = state / 'plugins'
    environment = dict(os.environ)
    environment.pop('PYTHONPATH', None)
    environment['NO_PROXY'] = environment['no_proxy'] = '127.0.0.1,localhost'
    initial_environment = capture_environment(state / 'environment-start', environment)
    baseline = json.loads((Path(acceptance['receipt']['baseline']) / 'baseline/manifest.json').read_text())
    for tool in ('openroad', 'yosys'):
        if digest(Path(profile[tool + '_bin'])) != baseline['tools'][tool]['sha256']:
            raise RuntimeError('A physical tool differs from the frozen P1 environment: ' + tool)
    subprocess.run([str(WORKSPACE / 'toolkits/.venv/bin/python'), '-m', 'eda_toolkits',
                    'configure', '--output', str(plugins)], env=environment, check=True)
    with socket.socket() as endpoint:
        endpoint.bind(('127.0.0.1', 0))
        port = endpoint.getsockname()[1]
    command = [str(WORKSPACE / 'execution-foundation/.venv/bin/python'), '-m',
               'openroad_platform_gateway', '--state-root', str(state / 'kernel'),
               '--plugins-root', str(plugins), '--admissions-root',
               str(WORKSPACE / 'execution-foundation/admissions'), '--port', str(port),
               '--input-root', str(state)]
    receipt_path = state / 'receipt.json'
    receipt = {'status': 'preparing', 'started_at': now(), 'native_p1': str(native),
               'threads': threads, 'cp0_ns': cp0, 'jobs': {}, 'wall_budget_seconds': 10800,
               'gateway_command': command}
    write_json(receipt_path, receipt)
    client = KernelClient(f'http://127.0.0.1:{port}', timeout=60)
    last_run = None
    last_status = None
    with (state / 'server.log').open('x') as log:
        server = subprocess.Popen(command, env=environment, stdout=log, stderr=log)
        receipt['gateway_pid'] = server.pid
        write_json(receipt_path, receipt)
        try:
            deadline = time.monotonic() + 180
            while True:
                if server.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError('Gateway failed to start; inspect server.log')
                with socket.socket() as probe:
                    if probe.connect_ex(('127.0.0.1', port)) == 0:
                        break
                time.sleep(.1)
            receipt['status'] = 'running'
            budget_deadline = time.monotonic() + receipt['wall_budget_seconds']
            checkpoint = None
            anchors = {}
            for stage in ('place', 'cts', 'route_finish', 'eval_final'):
                inputs = {'adapter': 'a2_stage', 'stage': stage, 'threads': threads,
                          'profile_path': 'inputs/profile.json'}
                staged = [InputFile(source=str(inputs_root / 'profile.json'), destination='inputs/profile.json')]
                if not stage.startswith('eval_'):
                    inputs.update(config_path='inputs/candidate.mk', sdc_path='inputs/candidate.sdc')
                    staged.extend(InputFile(source=str(inputs_root / name), destination='inputs/' + name)
                                  for name in ('candidate.mk', 'candidate.sdc'))
                if checkpoint is not None:
                    inputs['checkpoint_path'] = 'inputs/checkpoint.zip'
                    staged.append(InputFile(artifact_id=checkpoint['artifact_id'], destination='inputs/checkpoint.zip'))
                if stage == 'eval_final':
                    library_root = profile['flow_dir'] + '/platforms/nangate45/lib/'
                    inputs['evaluation'] = {'cp0_ns': cp0, 'clock_port': 'clk',
                                            'library_patterns': [library_root + 'NangateOpenCellLibrary_typical.lib',
                                                                 library_root + 'fakeram45_*.lib']}
                task = TaskSpec(task_id='a2-stage-' + stage, project_id='p2-a2-stage',
                                design_id='aes', experiment_id=state.name, plugin_id='openroad-data',
                                timeout_seconds=3600, staged_inputs=tuple(staged), inputs=inputs,
                                labels=({'run_type': 'analysis', 'analysis_of_run_id':
                                         receipt['jobs']['route_finish']['run_id']}
                                        if stage == 'eval_final' else {}),
                                resources=ResourceRequest(cpu_cores=threads, memory_bytes=6 << 30, processes=256))
                key = state.name + ':' + stage
                job = {'task': task.to_dict(), 'idempotency_key': key, 'status': 'submitting'}
                receipt['jobs'][stage] = job
                write_json(receipt_path, receipt)
                run = client.submit(task.to_dict(), idempotency_key=key)['run']
                last_run, last_status = run['run_id'], run['status']
                job.update(run_id=last_run, status=last_status)
                write_json(receipt_path, receipt)
                while last_status not in TERMINAL:
                    if time.monotonic() > budget_deadline:
                        raise TimeoutError('Stage acceptance wall budget exhausted')
                    run = client.run(last_run)
                    last_status = run['status']
                    time.sleep(.5)
                job.update(status=last_status, terminal_run=run)
                write_json(receipt_path, receipt)
                if last_status != 'succeeded':
                    raise RuntimeError(f'{stage} failed; preserved run {last_run}')
                artifacts = client.artifacts(last_run)
                by_path = {artifact['store_key']: artifact for artifact in artifacts}
                for path, sha in anchors.items():
                    if path not in by_path or by_path[path]['sha256'] != sha:
                        raise RuntimeError('An upstream checkpoint changed during ' + stage + ': ' + path)
                if not stage.startswith('eval_'):
                    stem = {'place': '3_place', 'cts': '4_cts', 'route_finish': '6_final'}[stage]
                    suffixes = ('odb', 'sdc', 'def', 'v', 'spef', 'gds') if stage == 'route_finish' else ('odb', 'sdc')
                    for suffix in suffixes:
                        path = f'flow/results/{stem}.{suffix}'
                        if path not in by_path or by_path[path]['size_bytes'] == 0:
                            raise RuntimeError('Required native output is missing: ' + path)
                        anchors[path] = by_path[path]['sha256']
                    tool_logs = [artifact for artifact in artifacts if artifact['kind'] == 'extractor_log']
                    content = client.artifact_bytes(last_run, tool_logs[0]['artifact_id']).decode()
                    observed_stages = set(re.findall(r'Running \S+\.tcl, stage ([1-6])_', content))
                    allowed = {'1', '2', '3'} if stage == 'place' else ({'4'} if stage == 'cts' else {'5', '6'})
                    if not observed_stages or not observed_stages <= allowed:
                        raise RuntimeError('Unexpected native build stages: ' + repr(observed_stages))
                    job['observed_native_stages'] = sorted(observed_stages)
                checkpoints = [artifact for artifact in artifacts if artifact['kind'] == 'flow_archive']
                if len(checkpoints) != 1:
                    raise RuntimeError('Expected exactly one native stage archive')
                checkpoint = checkpoints[0]
                receipts = [artifact for artifact in artifacts if artifact['kind'] == 'extractor_receipt']
                if len(receipts) != 1:
                    raise RuntimeError('Expected exactly one native command receipt')
                command_receipt = json.loads(client.artifact_bytes(last_run, receipts[0]['artifact_id']))
                if stage == 'eval_final':
                    observations = command_receipt['observations']
                    if (command_receipt['parasitic_mode'] != 'spef'
                            or command_receipt['evaluation']['cp0_ns'] != cp0
                            or any(not math.isfinite(observations[name]['value'])
                                   or observations[name]['unit'] != unit
                                   for name, unit in (('tns', 'ns'), ('wns', 'ns'), ('power', 'W')))):
                        raise RuntimeError('Final evaluation did not use the actual SPEF and fixed CP0')
                    baseline_result = acceptance['baseline']
                    receipt['native_baseline_comparison'] = {
                        'native_signed_tns_ns': baseline_result['tns'],
                        'native_power_W': baseline_result['power'],
                        'platform_signed_tns_ns': observations['tns']['value'],
                        'platform_power_W': observations['power']['value'],
                        'signed_tns_delta_ns': observations['tns']['value'] - baseline_result['tns'],
                        'power_delta_W': observations['power']['value'] - baseline_result['power'],
                        'same_reported_values': (
                            observations['tns']['value'] == baseline_result['tns']
                            and observations['power']['value'] == baseline_result['power']),
                        'note': 'One repeated baseline checks the execution seam; it is not a fair benefit evaluation.'}
                job.update(archive=checkpoint, command_receipt=command_receipt)
                write_json(receipt_path, receipt)
                print(json.dumps({'stage': stage, 'status': last_status, 'run_id': last_run}), flush=True)
            cancel_task = json.loads(json.dumps(receipt['jobs']['route_finish']['task']))
            cancel_task['task_id'] = 'a2-stage-routing-cancellation'
            receipt['cancellation'] = measure_routing_cancel(client, cancel_task, state / 'routing-cancellation.json')
            physical_run = receipt['jobs']['route_finish']['run_id']
            final_odb = next(artifact for artifact in client.artifacts(physical_run)
                             if artifact['store_key'] == 'flow/results/6_final.odb')
            receipt['physical_import'] = export_and_import(client, final_odb, physical_run, state,
                profile, threads, f'http://127.0.0.1:{port}', environment,
                evaluation_run=receipt['jobs']['eval_final']['run_id'])
            final_environment = capture_environment(state / 'environment-finish', environment)
            receipt['environment_unchanged'] = all(
                initial_environment[name]['files'] == final_environment[name]['files']
                and initial_environment[name]['packages'] == final_environment[name]['packages']
                for name in initial_environment)
            if not receipt['environment_unchanged']:
                raise RuntimeError('An executing project changed during physical acceptance; both manifests retained')
            receipt.update(status='completed', finished_at=now(), accepted=True)
            write_json(receipt_path, receipt)
        except Exception as error:
            receipt.update(status='failed', finished_at=now(), accepted=False,
                           error=type(error).__name__ + ': ' + str(error))
            write_json(receipt_path, receipt)
            raise
        finally:
            if last_run is not None and last_status not in TERMINAL:
                client.cancel(last_run)
            server.terminate()
            server.wait(timeout=120)


if __name__ == '__main__':
    main()
