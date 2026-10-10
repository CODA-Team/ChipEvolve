"""Verify HTTP paging on 150 genuine submissions, without starting their tools."""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import time

from openroad_platform_client import KernelClient
from openroad_platform_contracts import TaskSpec

from measure_http_cancellation import OPENROAD, ROOT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.state.exists() or args.output.exists():
        raise SystemExit('Use fresh state and output paths.')
    args.state.mkdir(parents=True)
    plugins = args.state / 'plugins'
    environment = dict(os.environ)
    environment.pop('PYTHONPATH', None)
    environment['NO_PROXY'] = environment['no_proxy'] = '127.0.0.1,localhost'
    subprocess.run([str(ROOT / 'toolkits/.venv/bin/python'), '-m', 'eda_toolkits',
                    'configure', '--output', str(plugins)], env=environment, check=True)
    with socket.socket() as endpoint:
        endpoint.bind(('127.0.0.1', 0))
        port = endpoint.getsockname()[1]
    command = [str(ROOT / 'execution-foundation/.venv/bin/python'), '-m',
               'openroad_platform_gateway', '--state-root', str(args.state / 'kernel'),
               '--plugins-root', str(plugins), '--admissions-root',
               str(ROOT / 'execution-foundation/admissions'), '--port', str(port), '--api-only']
    with (args.state / 'server.log').open('x') as log:
        server = subprocess.Popen(command, env=environment, stdout=log, stderr=log)
        client = KernelClient(f'http://127.0.0.1:{port}', timeout=60)
        try:
            deadline = time.monotonic() + 180
            while True:
                if server.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError('Gateway failed to start; inspect server.log')
                with socket.socket() as probe:
                    if probe.connect_ex(('127.0.0.1', port)) == 0:
                        break
                time.sleep(.1)
            ids = set()
            begin = time.monotonic()
            for number in range(150):
                task = TaskSpec(task_id=f'listing-{number}', project_id='p2-http-listing',
                                design_id='aes', plugin_id='openroad-data',
                                inputs={'adapter': 'command', 'extractor_command':
                                        [OPENROAD, '-version']})
                ids.add(client.submit(task.to_dict())['run']['run_id'])
            submission_seconds = time.monotonic() - begin
            observations = []
            pages = []
            for offset in (0, 50, 100, 150):
                begin = time.monotonic()
                rows = client.runs(project_id='p2-http-listing', status='queued',
                                   offset=offset, limit=50)
                observations.append({'offset': offset, 'count': len(rows),
                                     'seconds': time.monotonic() - begin})
                pages.extend(row['run_id'] for row in rows)
            missing = client.runs(project_id='missing-project', limit=50)
            passed = len(pages) == 150 and len(set(pages)) == 150 and set(pages) == ids and not missing
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps({'passed': passed, 'gateway_command': command,
                                              'submissions': 150, 'tools_executed': 0,
                                              'submission_seconds': submission_seconds,
                                              'pages': observations,
                                              'note': 'API-only listing acceptance; no physical-design results claimed.'},
                                             indent=2) + '\n')
            print(args.output, flush=True)
        finally:
            server.terminate()
            server.wait(timeout=120)
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
