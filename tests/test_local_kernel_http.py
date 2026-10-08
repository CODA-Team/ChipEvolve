"""Single-machine HTTP surface preserves lifecycle and evidence, without accounts."""
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

import pytest
from http.server import ThreadingHTTPServer
from openroad_platform_client import KernelClient, KernelError
from openroad_platform_gateway import build_router, make_handler
from openroad_platform_gateway.bootstrap import build_kernel, KernelPaths
from openroad_platform_runtime import RuntimeWorker

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def local(tmp_path, request):
    kernel = build_kernel(KernelPaths.of(tmp_path / 'state', ROOT / 'plugins', ROOT / 'admissions'))
    server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(build_router(kernel)))
    http_thread = threading.Thread(target=server.serve_forever)
    http_thread.start()
    stop = threading.Event()
    worker = RuntimeWorker(kernel.store, kernel.runtime, idle_seconds=0.02)
    worker_thread = threading.Thread(target=worker.serve_forever, args=(stop,))
    running = getattr(request, "param", True)
    if running:
        worker_thread.start()
    yield KernelClient(f'http://127.0.0.1:{server.server_port}'), kernel
    stop.set()
    if running:
        worker_thread.join(timeout=20)
    assert not worker_thread.is_alive()
    server.shutdown()
    server.server_close()
    http_thread.join()
    kernel.store.close()


def task(task_id='t1'):
    return {'schema_version': 3, 'task_id': task_id, 'project_id': 'test', 'design_id': 'chip',
            'plugin_id': 'example-reporter', 'inputs': {'records': [1, 2, 3, 4]},
            'timeout_seconds': 30}


def terminal(client, run_id):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        run = client.run(run_id)
        if run['status'] in ('succeeded', 'failed', 'cancelled', 'timed_out', 'lost'):
            return run
        time.sleep(0.03)
    raise AssertionError('run never reached a terminal state')


def test_http_runs_progress_resources_artifacts_and_durable_store(local, tmp_path):
    client, kernel = local
    assert client.health()['status'] == 'ok'
    run = client.submit(task(), idempotency_key='one')
    assert client.submit(task(), idempotency_key='one')['run_id'] == run['run_id']
    detail = terminal(client, run['run_id'])
    assert detail['status'] == 'succeeded'
    assert detail['stages'] and detail['stages'][0]['attempts']
    artifacts = client.artifacts(run['run_id'])
    assert {row['kind'] for row in artifacts} == {'summary', 'log'}
    report = next(row for row in artifacts if row['kind'] == 'summary')
    assert client.artifact_excerpt(run['run_id'], report['artifact_id'])['sha256'] == report['sha256']
    assert client.resources(run['run_id'])
    assert kernel.store.list_events(run['run_id'])
    assert not (tmp_path / 'state/identity.db').exists()
    assert client.runs(design_id='chip', status='succeeded')[0]['run_id'] == run['run_id']


@pytest.mark.parametrize("local", [False], indirect=True)
def test_queued_cancel_and_invalid_input_have_real_outcomes(local):
    client, kernel = local
    # Stop execution before submission so cancellation tests the queued boundary.
    run = kernel.runtime.submit(__import__('openroad_platform_contracts').TaskSpec.from_dict(task('cancel')))
    cancelled = client.cancel(run.run_id)
    assert terminal(client, run.run_id)['status'] == 'cancelled'
    assert cancelled['run_id'] == run.run_id
    with pytest.raises(KernelError) as error:
        client.submit({**task('invalid'), 'plugin_id': 'missing-plugin'})
    assert error.value.status == 400


def test_old_accounts_and_proxy_routes_are_removed(local):
    client, _ = local
    for route in ('/kernel/auth/session', '/apps', '/app/plan_executor/health'):
        with pytest.raises(KernelError) as error:
            client._call('GET', route)
        assert error.value.status == 404


def test_remote_bind_is_refused_and_worker_cli_needs_no_source_injection(tmp_path):
    base = [sys.executable, '-m', 'openroad_platform_gateway', '--state-root', str(tmp_path / 'state'),
            '--plugins-root', str(ROOT / 'plugins'), '--admissions-root', str(ROOT / 'admissions')]
    result = subprocess.run([*base, '--host', '0.0.0.0'], capture_output=True, text=True, timeout=10)
    assert result.returncode == 2 and 'loopback' in result.stderr
    env = dict(os.environ)
    env.pop('PYTHONPATH', None)
    result = subprocess.run([sys.executable, '-m', 'openroad_platform_gateway.worker',
                             *base[3:], '--once', '--quiet'], cwd=tmp_path, env=env,
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout.splitlines()[-1])['advanced'] == 0
