"""Measure the deployed HTTP/worker path on fresh state under listing load."""
import argparse
import json
import os
import re
from pathlib import Path
import socket
import subprocess
import threading
import time

from openroad_platform_client import KernelClient
from openroad_platform_contracts import InputFile, ResourceRequest, TaskSpec
from openroad_platform_runtime.guardian import ProcessGuardian

ROOT = Path(__file__).resolve().parents[1]
OPENROAD = '/opt/EDAs/OpenROAD-flow-scripts/versions/20260409/tools/install/OpenROAD/bin/openroad'


def identity(pid):
    try:
        fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
        return {'state': fields[0], 'start_ticks': fields[19]}
    except FileNotFoundError:
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cases', type=int, default=3)
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
    script = args.state / 'cancel.tcl'
    script.write_text('puts "P2_HTTP_NATIVE_STARTED [pid]"\nexec sleep 90\n')
    with socket.socket() as endpoint:
        endpoint.bind(('127.0.0.1', 0))
        port = endpoint.getsockname()[1]
    command = [str(ROOT / 'execution-foundation/.venv/bin/python'), '-m',
               'openroad_platform_gateway', '--state-root', str(args.state / 'kernel'),
               '--plugins-root', str(plugins), '--admissions-root',
               str(ROOT / 'execution-foundation/admissions'), '--port', str(port),
               '--input-root', str(args.state)]
    rows = []
    with (args.state / 'server.log').open('w') as log:
        server = subprocess.Popen(command, env=environment, stdout=log, stderr=log)
        client = KernelClient(f'http://127.0.0.1:{port}', timeout=60)
        try:
            startup_started = time.monotonic()
            deadline = startup_started + 180
            while True:
                if server.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError('Gateway failed to start; inspect server.log')
                with socket.socket() as probe:
                    if probe.connect_ex(('127.0.0.1', port)) == 0:
                        break
                time.sleep(.1)
            startup_seconds = time.monotonic() - startup_started
            client.health()
            for number in range(args.cases):
                task = TaskSpec(task_id=f'http-cancel-{number}', project_id='p2-http',
                                design_id='native', plugin_id='openroad-data',
                                timeout_seconds=120, inputs={'adapter': 'command',
                                'extractor_command': [OPENROAD, '-no_init', '-exit',
                                                      'inputs/cancel.tcl']},
                                staged_inputs=(InputFile(source=str(script.resolve()),
                                                         destination='inputs/cancel.tcl'),),
                                resources=ResourceRequest(cpu_cores=1, memory_bytes=2 << 30,
                                                          processes=32))
                run_id = client.submit(task.to_dict())['run']['run_id']
                deadline = time.monotonic() + 60
                while True:
                    detail = client.run(run_id)
                    attempts = [a for stage in detail.get('stages', [])
                                for a in stage.get('attempts', [])]
                    attempt = attempts[-1] if attempts else None
                    if attempt:
                        adapter_log = Path(attempt['workspace']) / 'adapter.log'
                        if adapter_log.is_file():
                            marker = re.search(r'P2_HTTP_NATIVE_STARTED (\d+)', adapter_log.read_text())
                            if marker:
                                native_pid = int(marker.group(1))
                                fields = Path(f'/proc/{native_pid}/stat').read_text().rsplit(')', 1)[1].split()
                                adapter_pid = int(fields[1])
                                break
                    if time.monotonic() > deadline:
                        client.cancel(run_id)
                        raise RuntimeError('Native start handshake failed: ' + repr(detail))
                    time.sleep(.1)
                originals = {pid: identity(pid) for pid in
                             ProcessGuardian._process_tree(adapter_pid)}
                if len(originals) < 3 or any(v is None for v in originals.values()):
                    raise RuntimeError('Expected live adapter, OpenROAD and sleep processes')
                stop = threading.Event()
                listing = []
                errors = []

                def load():
                    try:
                        while not stop.is_set():
                            begin = time.monotonic()
                            client.runs(project_id='p2-http', limit=10)
                            listing.append(time.monotonic() - begin)
                            stop.wait(.05)
                    except Exception as error:
                        errors.append(repr(error))

                thread = threading.Thread(target=load)
                thread.start()
                timing = {}
                begin = time.monotonic()

                def observe():
                    while not stop.is_set():
                        present = [pid for pid, value in originals.items()
                                   if (current := identity(pid)) and
                                   current['start_ticks'] == value['start_ticks']]
                        if not present:
                            timing['all_pids_gone_seconds'] = time.monotonic() - begin
                            return
                        stop.wait(.025)

                observer = threading.Thread(target=observe)
                observer.start()
                client.cancel(run_id)
                timing['cancel_response_seconds'] = time.monotonic() - begin
                deadline = begin + 60
                while True:
                    detail = client.run(run_id)
                    if detail['status'] in {'cancelled', 'failed', 'lost', 'timed_out', 'succeeded'}:
                        timing['terminal_seconds'] = time.monotonic() - begin
                        break
                    if time.monotonic() > deadline:
                        raise RuntimeError('Cancellation did not settle in 60 seconds')
                    time.sleep(.1)
                observer.join(10)
                stop.set()
                observer.join()
                thread.join()
                row = {'number': number, 'run_id': run_id, 'identities': originals,
                       'times': timing, 'terminal_run': detail, 'listing_seconds': listing,
                       'errors': errors, 'passed': detail['status'] == 'cancelled' and not errors
                       and timing.get('all_pids_gone_seconds', float('inf')) <= 5
                       and timing['terminal_seconds'] <= 5}
                rows.append(row)
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(json.dumps({'state': str(args.state.resolve()),
                                                  'gateway_command': command,
                                                  'startup_seconds': startup_seconds, 'cases': rows,
                                                  'passed': all(r['passed'] for r in rows)},
                                                 indent=2) + '\n')
                print(json.dumps({'number': number, 'passed': row['passed'], **timing}), flush=True)
        finally:
            server.terminate()
            server.wait(timeout=120)
    return 0 if rows and all(row['passed'] for row in rows) else 1


if __name__ == '__main__':
    raise SystemExit(main())
