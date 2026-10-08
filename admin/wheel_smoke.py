"""Verify released wheels and HTTP boundaries from an unrelated directory."""
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
env = dict(os.environ)
for key in ('PYTHONPATH', 'PYTHONHOME', 'VIRTUAL_ENV'):
    env.pop(key, None)
env.update(PYTHONNOUSERSITE='1', NO_PROXY='127.0.0.1,localhost,::1',
           no_proxy='127.0.0.1,localhost,::1', PIP_DISABLE_PIP_VERSION_CHECK='1')
http = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def call(url, value=None):
    body = None if value is None else json.dumps(value).encode()
    req = urllib.request.Request(url, data=body, headers={'Content-Type': 'application/json'})
    with http.open(req, timeout=3) as response:
        return json.load(response)


def port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


with tempfile.TemporaryDirectory(prefix='eda-wheel-smoke-') as directory:
    temp = Path(directory)
    subprocess.run([sys.executable, '-m', 'venv', str(temp / '.venv')], env=env, check=True)
    python = temp / '.venv/bin/python'
    subprocess.run([str(python), '-m', 'pip', 'install', '--no-index', '--find-links',
                    str(ROOT / 'wheelhouse'), 'openroad-app-data_foundation==0.1.0',
                    'openroad-platform-gateway==0.1.0', 'openroad-platform-client==0.1.0',
                    'eda-ai-client==0.1.0'], env=env, check=True)
    assert not list((temp / '.venv').rglob('__editable__*'))
    fingerprint_code = 'from openroad_app_data_foundation import source_fingerprint; print(source_fingerprint())'
    wheel_hash = subprocess.check_output([str(python), '-c', fingerprint_code], env=env, cwd=temp).decode().strip()
    dev_hash = subprocess.check_output([str(ROOT / 'data-foundation/.venv/bin/python'),
                                       '-c', fingerprint_code], env=env, cwd=temp).decode().strip()
    assert wheel_hash == dev_hash, (wheel_hash, dev_hash)
    data_port, kernel_port = port(), port()
    commands = [
        [python, '-m', 'openroad_platform_gateway', '--host', '127.0.0.1',
         '--port', str(kernel_port), '--no-auth', '--state-root', str(temp / 'kernel'),
         '--plugins-root', str(ROOT / 'execution-foundation/plugins'),
         '--admissions-root', str(ROOT / 'execution-foundation/admissions')],
        [python, '-m', 'openroad_app_data_foundation', '--host', '127.0.0.1',
         '--port', str(data_port), '--db', str(temp / 'data.sqlite'), '--no-auto-import',
         '--native-root', str(temp / 'native-flow')],
    ]
    processes = []
    try:
        for command in commands:
            processes.append(subprocess.Popen(list(map(str, command)), cwd=temp, env=env,
                                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        for service_port in [kernel_port, data_port]:
            deadline = time.monotonic() + 20
            while True:
                try:
                    assert call(f'http://127.0.0.1:{service_port}/health')['status'] == 'ok'
                    break
                except (OSError, AssertionError):
                    if time.monotonic() >= deadline:
                        raise
                    time.sleep(0.1)
        snapshot = {'snapshot': {'snapshot_id': 'split-smoke', 'design_id': 'gcd',
                    'revision_id': 'dev', 'run_id': 'smoke-run', 'stage': 'route',
                    'created_at': '2026-10-08T08:00:00Z'},
                    'entities': [{'object_id': 'i', 'kind': 'instance', 'name': 'u1'}]}
        call(f'http://127.0.0.1:{data_port}/snapshots', snapshot)
        sdk_code = '''from eda_ai_client import EdaAiClient
import sys
with EdaAiClient(data_url=sys.argv[1], kernel_url=sys.argv[2]) as client:
    assert client.get_stage_summary("split-smoke")["status"] == "available"
    assert client.get_instance("split-smoke", "u1")["instance"]["object_id"] == "i"
    assert isinstance(client.list_runs(), list)
'''
        subprocess.run([str(python), '-c', sdk_code, f'http://127.0.0.1:{data_port}',
                        f'http://127.0.0.1:{kernel_port}'], cwd=temp, env=env, check=True)
        query_code = '''from query_agent.adapters.run_evidence.http_client import HttpExecutionFoundationClient
import sys
assert list(HttpExecutionFoundationClient(sys.argv[1]).runs()) == []
'''
        subprocess.run([str(ROOT / 'query-agent/.venv/bin/python'), '-c', query_code,
                        f'http://127.0.0.1:{kernel_port}'], cwd=temp, env=env, check=True)
    finally:
        for proc in processes:
            proc.terminate()
        for proc in processes:
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
result = {'wheel_install': 'passed', 'no_editable_dependencies': True,
          'fingerprint_independent_of_checkout_path': True,
          'data_interface_to_data_foundation_http': 'passed',
          'data_interface_to_execution_foundation_http': 'passed',
          'primary_query_agent_to_execution_foundation_http': 'passed',
          'old_runtime_data_used': False}
(ROOT / 'admin/wheel-smoke-results.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
