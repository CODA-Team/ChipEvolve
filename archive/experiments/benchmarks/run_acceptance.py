"""Independent released-wheel, real OpenROAD, four-project acceptance.

Run from an unrelated directory with the isolated acceptance-env interpreter.
All state/logs/artifacts are under the output directory. No production DB read.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
import urllib.request

from eda_ai_client import EdaAiClient
from openroad_platform_client import KernelClient

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser()
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--openroad', default='/home/wjyuan/projects/eda-ai-formal-20261002/openroad_exec')
args = parser.parse_args()
out = args.output.resolve()
out.mkdir(parents=True, exist_ok=False)
http = urllib.request.build_opener(urllib.request.ProxyHandler({}))
env = dict(os.environ, PYTHONNOUSERSITE='1', NO_PROXY='localhost,127.0.0.1,::1')
for key in ('PYTHONPATH', 'PYTHONHOME'):
    env.pop(key, None)


def call(url, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    with http.open(urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'}), timeout=20) as response:
        return json.load(response)


def port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def wait(url):
    deadline = time.monotonic() + 20
    while True:
        try:
            return call(url)
        except OSError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.05)


kernel_port, data_port = port(), port()
kernel_url, data_url = f'http://127.0.0.1:{kernel_port}', f'http://127.0.0.1:{data_port}'
processes, logs = [], []
results = {'method': 'released wheels + actual OpenROAD STA on a 3-buffer Nangate45 chain; ideal nets',
           'production_state_used': False, 'web_apps': False, 'cases': [], 'data_url': data_url, 'kernel_url': kernel_url}
started = time.monotonic()
try:
    commands = [
        [sys.executable, '-m', 'openroad_platform_gateway', '--host', '127.0.0.1', '--port', str(kernel_port),
         '--state-root', str(out / 'kernel'), '--plugins-root', str(ROOT / 'execution-foundation/plugins'),
         '--admissions-root', str(ROOT / 'execution-foundation/admissions')],
        [sys.executable, '-m', 'openroad_app_data_foundation', '--host', '127.0.0.1', '--port', str(data_port),
         '--db', str(out / 'data.sqlite'), '--kernel-url', kernel_url, '--no-auto-import',
         '--native-root', str(out / 'native')],
    ]
    for name, command in zip(('execution', 'data'), commands):
        handle = (out / (name + '.log')).open('w')
        logs.append(handle)
        processes.append(subprocess.Popen(command, cwd=out, env=env, stdout=handle, stderr=subprocess.STDOUT))
    wait(kernel_url + '/health')
    wait(data_url + '/health')
    client = KernelClient(kernel_url)
    sdk = EdaAiClient(data_url=data_url, kernel_url=kernel_url)
    source = out / 'inputs'
    source.mkdir()
    for name in ('extract_timing.py', 'design.v'):
        shutil.copyfile(ROOT / 'admin/benchmarks' / name, source / name)
    uploads = {name: client.upload_input((source / name).read_bytes())['input_id']
               for name in ('extract_timing.py', 'design.v')}
    run_ids = []
    for label, period, mode in [('baseline', 1.0, 'ok'), ('regression', 0.2, 'ok'), ('invalid', 1.0, 'missing-tech')]:
        begin = time.monotonic()
        direct = out / ('direct-' + label)
        direct.mkdir()
        for name in ('extract_timing.py', 'design.v'):
            shutil.copyfile(source / name, direct / name)
        direct_result = subprocess.run([sys.executable, 'extract_timing.py', '--openroad', args.openroad,
                                        '--period', str(period), '--mode', mode], cwd=direct, env=env,
                                       capture_output=True, text=True, check=False, timeout=60)
        (direct / 'stdout.txt').write_text(direct_result.stdout + direct_result.stderr)
        direct_seconds = time.monotonic() - begin
        task = {'schema_version': 3, 'task_id': 'acceptance-' + label, 'project_id': 'acceptance',
                'design_id': 'buffer-chain', 'design_revision_id': 'same-netlist', 'plugin_id': 'openroad-data',
                'timeout_seconds': 60, 'inputs': {'adapter': 'command', 'extractor_command': [
                    'python3', 'extract_timing.py', '--openroad', args.openroad, '--period', str(period), '--mode', mode],
                    'netlist_path': 'design.v', 'rc_script_path': 'analysis.tcl', 'timing_report_path': 'report.rpt'},
                'staged_inputs': [{'input_id': ident, 'destination': name} for name, ident in uploads.items()]}
        begin = time.monotonic()
        run = client.submit(task, idempotency_key=label)['run']
        assert client.submit(task, idempotency_key=label)['run']['run_id'] == run['run_id']
        deadline = time.monotonic() + 70
        while True:
            detail = client.run(run['run_id'])
            if detail['status'] in ('succeeded', 'failed', 'cancelled', 'timed_out', 'lost'):
                break
            if time.monotonic() >= deadline:
                raise TimeoutError(run['run_id'])
            time.sleep(0.05)
        seconds = time.monotonic() - begin
        artifacts = client.artifacts(run['run_id'])
        (out / (label + '-run.json')).write_text(json.dumps(detail, indent=2))
        (out / (label + '-resources.json')).write_text(json.dumps(client.resources(run['run_id']), indent=2))
        assert detail['status'] == ('failed' if mode == 'missing-tech' else 'succeeded'), detail
        row = {'label': label, 'run_id': run['run_id'], 'execution_status': detail['status'],
               'direct_seconds': direct_seconds, 'infra_seconds': seconds,
               'direct_exit_code': direct_result.returncode, 'artifact_count': len(artifacts)}
        if mode == 'ok':
            assert direct_result.returncode == 0
            artifact = next(row for row in artifacts if row['kind'] == 'data_snapshot')
            import_start = time.monotonic()
            imported = call(data_url + '/snapshots/from-run', {'run_id': run['run_id'], 'artifact_id': artifact['artifact_id']})
            row['data_import_seconds'] = time.monotonic() - import_start
            scope = sdk.resolve_scope(run_id=run['run_id'], stage='timing')
            assert scope['status'] == 'available', scope
            snapshot_id = scope['data']['snapshot']['snapshot_id']
            row['snapshot_id'] = snapshot_id
            facts = sdk.get_metrics(snapshot_id=snapshot_id, name='WNS')
            (out / (label + '-metrics.json')).write_text(json.dumps(facts, indent=2))
            assert facts['data']['metrics'][0]['status'] == 'available', facts
            paths = sdk.get_timing_paths(snapshot_id)['data']['timing_paths']
            assert paths and paths[0]['unit'] == 'ns'
            assert paths[0]['slack_ns'] == paths[0]['slack']
            row['declared_time_units'] = 'passed'
            assert sdk.get_instance(snapshot_id, 'u1')['data']['target']['id'] == 'instance:u1'
            question = subprocess.run([sys.executable, '-m', 'query_agent.interfaces.cli', 'ask', 'timing WNS',
                                       '--data-url', data_url, '--run', run['run_id'], '--stage', 'timing'], cwd=out,
                                      env=env, capture_output=True, text=True, check=False, timeout=20)
            (out / (label + '-query.json')).write_text(question.stdout)
            (out / (label + '-query-stderr.txt')).write_text(question.stderr)
            assert question.returncode == 0, question.stderr
            response = json.loads(question.stdout)
            row['query_status'] = response['status']
            assert response['status'] == 'ANSWERED', response
            assert response['evidence_citations']
            path_answer = subprocess.run([sys.executable, '-m', 'query_agent.interfaces.cli',
                                          'ask', 'critical path', '--data-url', data_url,
                                          '--run', run['run_id'], '--stage', 'timing'],
                                         cwd=out, env=env, capture_output=True, text=True,
                                         check=False, timeout=20)
            (out / (label + '-path-query.json')).write_text(path_answer.stdout)
            assert path_answer.returncode == 0, path_answer.stderr
            assert json.loads(path_answer.stdout)['status'] == 'ANSWERED', path_answer.stdout
            row['timing_path_query'] = 'passed'
            run_ids.append(run['run_id'])
        else:
            assert direct_result.returncode != 0
            assert any(attempt.get('failure') for stage in detail['stages'] for attempt in stage['attempts'])
        results['cases'].append(row)
    compare = subprocess.run([sys.executable, '-m', 'query_agent.interfaces.cli', 'ask', 'Compare WNS difference',
                              '--kernel-url', kernel_url, '--data-url', data_url, '--design', 'buffer-chain',
                              '--stage', 'timing', '--compare-runs', *run_ids], cwd=out, env=env,
                             capture_output=True, text=True, check=False, timeout=20)
    (out / 'comparison.json').write_text(compare.stdout)
    assert compare.returncode == 0, compare.stderr
    assert json.loads(compare.stdout)['status'] == 'ANSWERED', compare.stdout
    results['comparison'] = 'passed'
    # A canonical metric must identify the real registered report, not its ZIP.
    fact = sdk.get_metrics(run_id=run_ids[1], name='WNS')['data']['metrics'][0]
    ref = fact['evidence'][0]
    report = next(row for row in client.artifacts(run_ids[1]) if row['store_key'] == 'report.rpt')
    assert (ref['artifact_id'], ref['sha256']) == (report['artifact_id'], report['sha256'])
    excerpt = call(data_url + '/snapshots/' + results['cases'][1]['snapshot_id']
                   + '/sources/' + ref['artifact_id'] + '/excerpt')
    assert 'WS_NS=' in excerpt['data']['excerpt']['text']
    results['registered_source_excerpt'] = 'passed'
    # Cancel after the actual tool has emitted its report. The wait is deliberate.
    cancel_task = {**task, 'task_id': 'acceptance-running-cancel',
                   'inputs': {**task['inputs'], 'extractor_command': [
                       'python3', 'extract_timing.py', '--openroad', args.openroad,
                       '--period', '1.0', '--mode', 'wait']}}
    cancel_id = client.submit(cancel_task)['run']['run_id']
    deadline = time.monotonic() + 15
    while True:
        running = client.run(cancel_id)
        reports = list((out / 'kernel/runtime-workspaces' / cancel_id).rglob('report.rpt'))
        if running['status'] == 'running' and reports and 'WS_NS=' in reports[0].read_text():
            break
        if time.monotonic() >= deadline:
            raise TimeoutError('real STA did not reach cancellation checkpoint')
        time.sleep(0.05)
    cancel_start = time.monotonic()
    client.cancel(cancel_id)
    while client.run(cancel_id)['status'] not in ('cancelled', 'failed', 'timed_out'):
        if time.monotonic() - cancel_start > 15:
            raise TimeoutError('running task did not cancel')
        time.sleep(0.05)
    assert client.run(cancel_id)['status'] == 'cancelled'
    results['running_cancel'] = {'status': 'passed', 'run_id': cancel_id,
                                 'seconds': time.monotonic() - cancel_start,
                                 'resources': client.resources(cancel_id)}
    # Stop both processes and reopen the same state through installed wheels.
    before = {row['artifact_id']: row['sha256'] for row in client.artifacts(run_ids[0])}
    for process in processes:
        process.terminate()
    for process in processes:
        process.wait(timeout=20)
    for name, command in zip(('execution-restart', 'data-restart'), commands):
        handle = (out / (name + '.log')).open('w')
        logs.append(handle)
        processes.append(subprocess.Popen(command, cwd=out, env=env, stdout=handle, stderr=subprocess.STDOUT))
    wait(kernel_url + '/health')
    wait(data_url + '/health')
    assert client.run(run_ids[0])['status'] == 'succeeded'
    assert client.run(cancel_id)['status'] == 'cancelled'
    assert before == {row['artifact_id']: row['sha256'] for row in client.artifacts(run_ids[0])}
    assert sdk.resolve_scope(run_id=run_ids[1], stage='timing')['status'] == 'available'
    results['restart_durability'] = 'passed'
    results['clean_wheels'] = not bool(list(Path(sys.prefix).rglob('__editable__*')))
    results['identity_db_exists'] = (out / 'kernel/identity.db').exists()
    results['elapsed_seconds'] = time.monotonic() - started
    results['status'] = 'passed'
finally:
    for process in processes:
        process.terminate()
    for process in processes:
        try:
            process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
    for handle in logs:
        handle.close()
    (out / 'results.json').write_text(json.dumps(results, indent=2))
print(json.dumps(results, indent=2))
