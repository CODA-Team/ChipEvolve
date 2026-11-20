"""Start and stop a named local EF/DF instance using installed wheels.

Every instance has explicit ports and state. Stop requires the recorded PID,
Linux process birth identity and exact command to match, and refuses active EDA.
No process discovery, old-service adoption or broad process kill is performed.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import subprocess
import time
import urllib.request


def write(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(path)


def env_for(python):
    env = dict(os.environ)
    for key in ('PYTHONPATH', 'PYTHONHOME', 'VIRTUAL_ENV', 'CONDA_PREFIX'):
        env.pop(key, None)
    env.update(PYTHONNOUSERSITE='1', NO_PROXY='localhost,127.0.0.1,::1', no_proxy='localhost,127.0.0.1,::1')
    env['PATH'] = str(python.parent) + os.pathsep + env.get('PATH', '')
    return env


def get(url):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(url, timeout=3) as response:
        return json.load(response)


def birth(pid):
    raw = Path('/proc', str(pid), 'stat').read_text().rsplit(')', 1)[1].split()
    if raw[0] == 'Z':
        raise ProcessLookupError('recorded process is a zombie')
    return raw[19]


def identity_matches(record):
    try:
        command = [arg.decode() for arg in Path('/proc', str(record['pid']), 'cmdline').read_bytes().split(b'\0') if arg]
        return birth(record['pid']) == record['birth'] and command == record['command']
    except (OSError, ProcessLookupError):
        return False


def configuration(path):
    value = json.loads(path.read_text())
    for name in ('workspace', 'state_root', 'orfs_image', 'activity_lock'):
        if not Path(value[name]).is_absolute():
            raise ValueError(name + ' must be absolute')
    ports = [value['kernel_port'], value['data_port']]
    if len(set(ports)) != 2 or any(not isinstance(port, int) or not 1024 <= port <= 65535 for port in ports):
        raise ValueError('Two distinct unprivileged ports are required')
    return value


def commands(config):
    root = Path(config['workspace'])
    state = Path(config['state_root'])
    ef = root / 'execution-foundation/.venv/bin/python'
    df = root / 'data-foundation/.venv/bin/python'
    return {
        'execution': [str(ef), '-I', '-m', 'openroad_platform_gateway', '--host', '127.0.0.1',
                      '--port', str(config['kernel_port']), '--state-root', str(state / 'execution'),
                      '--plugins-root', str(state / 'plugins'), '--admissions-root', str(root / 'execution-foundation/admissions'),
                      '--input-root', str(root / 'var'), '--capacity-cpu-cores', '8',
                      '--capacity-memory-bytes', str(24 * 1024**3), '--platform-fraction', '1.0', '--worker-concurrency', '1'],
        'data': [str(df), '-I', '-m', 'openroad_app_data_foundation', '--host', '127.0.0.1',
                 '--port', str(config['data_port']), '--db', str(state / 'data/snapshots.sqlite'),
                 '--kernel-url', 'http://127.0.0.1:' + str(config['kernel_port']),
                 '--native-root', str(state / 'native-flow'), '--no-auto-import'],
    }


def status(config):
    state = Path(config['state_root'])
    path = state / 'processes.json'
    records = json.loads(path.read_text()) if path.is_file() else {}
    result = {}
    for name, port in (('execution', config['kernel_port']), ('data', config['data_port'])):
        row = records.get(name)
        result[name] = {'registered_pid': row.get('pid') if row else None,
                        'owned_process_alive': identity_matches(row) if row else False,
                        'url': 'http://127.0.0.1:' + str(port)}
        try:
            result[name]['health'] = get(result[name]['url'] + ('/kernel/health' if name == 'execution' else '/health'))
        except Exception as error:
            result[name]['health_error'] = str(error)
    return result


def stop(config):
    path = Path(config['state_root']) / 'processes.json'
    if not path.is_file():
        return {'stopped': [], 'reason': 'No owned processes are registered.'}
    records = json.loads(path.read_text())
    live = {name: row for name, row in records.items() if identity_matches(row)}
    if 'execution' in live:
        runs = []
        offset = 0
        while True:
            response = get('http://127.0.0.1:' + str(config['kernel_port'])
                           + '/kernel/runs?limit=200&offset=' + str(offset))
            page = response['runs']
            runs.extend(page)
            if len(page) < 200:
                break
            offset += len(page)
        active = [row['run_id'] for row in runs if row['status'] not in ('succeeded', 'failed', 'cancelled', 'timed_out', 'lost')]
        if active:
            raise RuntimeError('Active EDA must finish or be explicitly cancelled before stop: ' + ', '.join(active))
    stopped = []
    for name in ('data', 'execution'):
        row = live.get(name)
        if row is None:
            continue
        os.kill(row['pid'], signal.SIGTERM)
        deadline = time.monotonic() + 8
        while identity_matches(row) and time.monotonic() < deadline:
            time.sleep(0.1)
        if identity_matches(row):
            raise RuntimeError('Owned process did not stop gracefully: ' + name)
        stopped.append(name)
    history = path.with_name('processes-stopped-' + str(time.time_ns()) + '.json')
    path.replace(history)
    return {'stopped': stopped, 'record': str(history)}


def start(config):
    root = Path(config['workspace'])
    state = Path(config['state_root'])
    state.mkdir(parents=True, exist_ok=True)
    records_path = state / 'processes.json'
    if records_path.exists():
        current = status(config)
        if all(row['owned_process_alive'] and 'health' in row for row in current.values()):
            return {'already_started': True, 'status': current}
        raise RuntimeError('Existing instance record needs an explicit stop before a new start.')
    for port in (config['kernel_port'], config['data_port']):
        with socket.socket() as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(('127.0.0.1', port))
    toolkit = root / 'toolkits/.venv/bin/python'
    configure = [str(toolkit), '-I', '-m', 'eda_toolkits', 'configure', '--output', str(state / 'plugins'),
                 '--image', config['orfs_image'], '--activity-lock', config['activity_lock']]
    with (state / 'configure.log').open('a') as stream:
        subprocess.run(configure, cwd='/tmp', env=env_for(toolkit), stdout=stream, stderr=subprocess.STDOUT, check=True)
    (state / 'data').mkdir(exist_ok=True)
    records = {}
    for name, command in commands(config).items():
        with (state / (name + '-service.log')).open('a') as stream:
            process = subprocess.Popen(command, cwd='/tmp', env=env_for(Path(command[0])),
                                       stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
        row = {'pid': process.pid, 'birth': birth(process.pid), 'command': command,
               'started_at': datetime.now(timezone.utc).isoformat()}
        records[name] = row
        write(records_path, records)
        url = 'http://127.0.0.1:' + str(config['kernel_port'] if name == 'execution' else config['data_port'])
        route = '/kernel/health' if name == 'execution' else '/health'
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(name + ' exited; inspect its registered service log.')
            try:
                get(url + route)
                break
            except Exception:
                time.sleep(0.2)
        else:
            raise RuntimeError(name + ' health deadline expired; explicit stop and logs are available.')
    return {'started': True, 'status': status(config)}


def prepare_gcd(config, eco_python=None):
    """Prepare a standalone GCD deployment from the supplied ORFS image."""
    root = Path(config['workspace'])
    state = Path(config['state_root'])
    destination = state / 'local.json'
    if destination.exists():
        raise FileExistsError(destination)
    runtime = shutil.which('apptainer')
    if runtime is None:
        raise RuntimeError('Install Apptainer before preparing the GCD example')
    flow = '/OpenROAD-flow-scripts/flow/'
    inputs = state / 'inputs'
    inputs.mkdir(exist_ok=True)
    library = inputs / 'NangateOpenCellLibrary_typical.lib'
    sdc = inputs / 'gcd.sdc'
    command = [runtime, 'exec', '--cleanenv', '--no-home', config['orfs_image'], 'cat']
    with library.open('wb') as handle:
        subprocess.run(command + [flow + 'platforms/nangate45/lib/' + library.name],
                       stdout=handle, check=True)
    constraints = subprocess.check_output(
        command + [flow + 'designs/nangate45/gcd/constraint.sdc'], text=True)
    constraints, changes = re.subn(r'(?m)^set clk_period \S+$', 'set clk_period 0.5', constraints)
    if changes != 1:
        raise ValueError('The image GCD constraints do not declare one clk_period')
    sdc.write_text('set_cmd_units -time ns\n' + constraints)
    with Path(config['orfs_image']).open('rb') as handle:
        image_digest = hashlib.file_digest(handle, 'sha256').hexdigest()
    value = {
        'schema_version': 'chip-evolve.local.v1',
        'state_root': str(state),
        'client_python': str(root / 'agent/query-agent/.venv/bin/python'),
        'query_python': str(root / 'agent/query-agent/.venv/bin/python'),
        'openroad_launcher': str(root / 'toolkits/.venv/bin/eda-openroad'),
        'kernel_url': f"http://127.0.0.1:{config['kernel_port']}",
        'data_url': f"http://127.0.0.1:{config['data_port']}",
        'runtime': {'image': config['orfs_image'], 'executable': runtime,
                    'bind_roots': [str(state)]},
        'tools': {'openroad': '/OpenROAD-flow-scripts/tools/install/OpenROAD/bin/openroad'},
        'toolchain': {'image_sha256': image_digest},
        'designs': {'gcd': {
            'top': 'gcd', 'nickname': 'gcd', 'platform': 'nangate45',
            'orfs_config': 'designs/nangate45/gcd/config.mk', 'sdc': str(sdc),
            'corner': 'typical', 'clock_period_ns': 0.5,
            'libraries': [{'path': str(library), 'sha256': hashlib.sha256(library.read_bytes()).hexdigest()}],
            'orfs_execution': {'memory_gib': 4},
            'fact_execution': {'memory_gib': 4},
        }},
    }
    if eco_python is not None:
        eco_python = eco_python.absolute()
        if not eco_python.is_file():
            raise FileNotFoundError(eco_python)
        pdk = inputs / 'nangate45'
        pdk.mkdir(exist_ok=True)
        for name in ('setRC.tcl', 'rcx_patterns.rules'):
            with (pdk / name).open('wb') as handle:
                subprocess.run(command + [flow + 'platforms/nangate45/' + name],
                               stdout=handle, check=True)
        value['professional'] = {'eco': {
            'source': str(root / 'agent/timing-eco-agent'),
            'python': str(eco_python),
            'pdk_template': str(pdk),
            'session_memory_gib': 8,
        }}
        value['designs']['gcd'].update(signal_layers='metal2-metal10',
                                       clock_layers='metal4-metal10')
    write(destination, value)
    return {'deployment': str(destination)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=('init', 'prepare-gcd', 'start', 'status', 'stop'))
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--workspace', type=Path)
    parser.add_argument('--instance', default='demo')
    parser.add_argument('--image', type=Path)
    parser.add_argument('--kernel-port', type=int, default=19700)
    parser.add_argument('--data-port', type=int, default=19924)
    parser.add_argument('--activity-lock', type=Path)
    parser.add_argument('--eco-python', type=Path,
                        help='prepare-gcd also binds an installed TimingECOAgent environment')
    args = parser.parse_args()
    if args.mode == 'init':
        if args.config.exists() or args.workspace is None or args.image is None:
            parser.error('init needs a new config path, --workspace and --image')
        if not re.fullmatch('[A-Za-z0-9_-]+', args.instance):
            parser.error('instance name must use letters, numbers, dash or underscore')
        root = args.workspace.resolve()
        if not args.image.is_file() or not (root / 'toolkits/.venv/bin/python').exists():
            parser.error('installed workspace and existing ORFS image are required')
        state = root / 'var/instances' / args.instance
        toolchain_path = state / 'toolchain.json'
        value = {'workspace': str(root), 'state_root': str(state), 'orfs_image': str(args.image.resolve()),
                 'kernel_port': args.kernel_port, 'data_port': args.data_port,
                 'activity_lock': str(args.activity_lock.resolve() if args.activity_lock else root / 'var/eda-activity.lock'),
                 'toolchain_config': str(toolchain_path)}
        args.config.parent.mkdir(parents=True, exist_ok=True)
        write(args.config, value)
        configuration(args.config)
        state.mkdir(parents=True, exist_ok=True)
        write(toolchain_path, {'orfs_image': value['orfs_image'], 'container_runtime': 'apptainer',
                               'openroad_bin': str(root / 'toolkits/.venv/bin/eda-openroad')})
        result = value
    elif args.mode == 'prepare-gcd':
        result = prepare_gcd(configuration(args.config), args.eco_python)
    else:
        config = configuration(args.config)
        result = {'start': start, 'status': status, 'stop': stop}[args.mode](config)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
