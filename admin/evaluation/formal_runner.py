"""Run the fixed public matrix; no gold or diagnosis mechanism is read here.

Preparation and development can use --prepare-only/--pilot. Formal execution
requires an implementation freeze and exact hashes. Failed/missing episodes keep
their original matrix identity and denominator. Resumption never replaces a run.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
import urllib.request

from query_agent.domain.investigation import InvestigationAnswer
from openroad_platform_client import KernelClient
from direct_native import cleanup_owned


def digest(path):
    hasher = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1048576), b''):
            hasher.update(block)
    return hasher.hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(path)


def read_public(base, path):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(base + path, timeout=30) as response:
        return json.load(response)


def cleanup_episode(folder, kernel_url):
    records = {'native': cleanup_owned(folder), 'execution': []}
    runs = set()
    state_path = folder / 'state.json'
    if state_path.is_file():
        try:
            runs.update(json.loads(state_path.read_text()).get('owned_runs', []))
        except ValueError:
            pass
    for path in (folder / 'investigations').glob('*/state.json'):
        try:
            runs.update(ticket['run_id'] for ticket in json.loads(path.read_text()).get('pending_analyses', []))
        except (ValueError, KeyError):
            continue
    kernel = KernelClient(kernel_url, timeout=5)
    for run_id in sorted(runs):
        try:
            state = kernel.run(run_id)
            if state['status'] not in ('succeeded', 'failed', 'cancelled', 'timed_out', 'lost'):
                result = kernel.cancel(run_id)
                records['execution'].append({'run_id': run_id, 'cancel': result})
        except Exception as error:
            records['execution'].append({'run_id': run_id, 'error': str(error)})
    return records


def schedule(matrix):
    """Alternate capability order within each fixed case/model/repeat block."""
    groups = {}
    for row in matrix:
        key = (row['case_id'], row['repeat'], row['ablation'])
        groups.setdefault(key, []).append(row)
    result = []
    for index, rows in enumerate(groups.values()):
        arms = ['A', 'B', 'C', 'D', 'E']
        offset = index % len(arms)
        order = arms[offset:] + arms[:offset]
        result.extend(sorted(rows, key=lambda row: (order.index(row['arm']), row['model'])))
    return result


def prepare(args, matrix):
    public = args.sprint / 'evaluation-v1/public'
    facts = {row['case_id']: row for row in json.loads((public / 'facts.json').read_text())}
    diagnosis = {row['case_id']: row for row in json.loads((public / 'diagnosis.json').read_text())}
    binding_root = args.sprint / 'public-bindings-v1'
    bindings = {row['case_id']: row for name in ('fact-bindings.json', 'diagnosis-bindings.json')
                for row in json.loads((binding_root / name).read_text())}
    preparations = []
    for case_id in sorted({row['case_id'] for row in matrix}):
        case = facts.get(case_id, diagnosis.get(case_id))
        binding = bindings[case_id]
        config = {
            'case_id': case_id,
            'snapshots': binding['snapshots'],
            'baseline_root': str(args.sprint / 'direct-baseline-v1'),
            'data_url': args.data_url, 'kernel_url': args.kernel_url,
            'orfs_image': json.loads((args.sprint / 'toolchain-settings.json').read_text())['orfs_image'],
            'activity_lock': str(args.sprint / 'coordination/eda-activity.lock'),
            'max_seconds': 120 if case_id in facts else 180,
            'question': case['question'] + ' ' + binding.get('public_context', ''),
            'answer_schema': case.get('answer_schema', InvestigationAnswer.model_json_schema()),
            'flash_config': str(args.flash_config),
            'cost_ledger': str(args.sprint / 'cost-ledger.json'),
            'scope_selectors': binding.get('scope_selectors') or [],
            'handoff_permissions': binding.get('handoff_permissions', {}),
            'allowed_execution_ids': binding.get('allowed_execution_ids', []),
            'api_help': {}, 'allowed_run_ids': [],
        }
        for sid in binding['snapshots']:
            info_path = args.sprint / 'direct-baseline-v1' / sid / 'native.json'
            info = json.loads(info_path.read_text())
            config['allowed_run_ids'].append(info['run_id'])
        if case_id in facts:
            topic_names = ('objects', 'timing', 'physical', 'sources', 'native')
        else:
            topic_names = ('objects', 'timing', 'sources', 'native')
        for topic in topic_names:
            sid = binding['snapshots'][-1]
            response = read_public(args.data_url, '/snapshots/' + sid + '/help?topic=' + topic)
            config['api_help'][topic] = response['data']['guide']
        path = args.output / 'configs' / (case_id.replace(':', '_') + '.json')
        write(path, config)
        preparations.append({'case_id': case_id, 'path': str(path), 'sha256': digest(path)})
    write(args.output / 'preparation.json', {
        'prepared_at': datetime.now(timezone.utc).isoformat(),
        'gold_read': False, 'configs': preparations,
        'public_files': {str(path.relative_to(args.sprint)): digest(path)
                         for root in (public, binding_root) for path in root.glob('*.json')},
    })


def command_for(args, row, folder):
    config_path = args.output / 'configs' / (row['case_id'].replace(':', '_') + '.json')
    config = json.loads(config_path.read_text())
    model = 'flash' if row['model'] == 'deepseek-flash' else 'codex'
    if row['arm'] in ('A', 'B', 'C'):
        config['arm'] = row['arm']
        invocation_config = args.output / 'episode-configs' / (folder.name + '.json')
        write(invocation_config, config)
        return [sys.executable, str(Path(__file__).parent / 'generic_agent.py'), 'run',
                '--episode', str(folder), '--config', str(invocation_config), '--model', model]
    folder.mkdir(parents=True, exist_ok=False)
    command = [sys.executable, '-m', 'query_agent', 'investigate', config['question'],
               '--state-root', str(folder), '--data-url', args.data_url,
               '--kernel-url', args.kernel_url, '--model', model,
               '--max-seconds', str(row['wall_seconds'])]
    if config['scope_selectors']:
        write(folder / 'scope-request.json', config['scope_selectors'])
        command.extend(['--scope-request', str(folder / 'scope-request.json')])
    else:
        for sid in config['snapshots']:
            command.extend(['--snapshot', sid])
    if config['handoff_permissions']:
        write(folder / 'handoff-permissions.json', config['handoff_permissions'])
        command.extend(['--handoff-permissions', str(folder / 'handoff-permissions.json')])
    if model == 'codex':
        command.extend(['--codex-mode', 'hosted'])
    else:
        command.extend(['--flash-config', str(args.flash_config), '--cost-ledger',
                        str(args.sprint / 'cost-ledger.json')])
    if row['arm'] == 'E':
        command.extend(['--jev', '--jev-launcher', str(args.jev_launcher),
                        '--jev-pricing', str(args.sprint / 'jev-pricing.json'),
                        '--cost-ledger', str(args.sprint / 'cost-ledger.json')])
    if row['ablation'] == 'no-skills':
        command.append('--no-skills')
    if row['ablation'] == 'no-supplement':
        command.extend(['--max-analyses', '0'])
    return command


def run_episode(args, row):
    episode_key = hashlib.sha256(row['episode_id'].encode()).hexdigest()[:20]
    folder = args.output / 'episodes' / episode_key
    receipt = args.output / 'receipts' / (episode_key + '.json')
    if receipt.exists():
        return json.loads(receipt.read_text())
    if folder.exists():
        # A crashed first attempt is not silently overwritten or rerun.
        record = {**row, 'status': 'incomplete_prior_attempt', 'folder': str(folder),
                  'cleanup': cleanup_episode(folder, args.kernel_url),
                  'reason': 'prior episode directory exists without final receipt'}
        write(receipt, record)
        return record
    command = command_for(args, row, folder)
    log_root = args.output / 'terminal'
    log_root.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    record = {**row, 'status': 'running', 'folder': str(folder), 'invocation': command,
              'started_at': datetime.now(timezone.utc).isoformat()}
    write(args.output / 'started' / (episode_key + '.json'), record)
    with (log_root / (episode_key + '.stdout')).open('w') as output, \
         (log_root / (episode_key + '.stderr')).open('w') as errors:
        process = subprocess.Popen(command, stdout=output, stderr=errors, start_new_session=True)
        timed_out = False
        try:
            process.wait(timeout=row['wall_seconds'])
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
    finished = time.monotonic()
    record.update(status='timed_out' if timed_out else 'completed' if process.returncode == 0 else 'failed',
                  exit_code=process.returncode, wall_seconds_used=finished - started,
                  timed_out=timed_out)
    if row['arm'] in ('D', 'E'):
        output = log_root / (episode_key + '.stdout')
        if output.is_file():
            try:
                write(folder / 'result.json', json.loads(output.read_text()))
            except ValueError:
                pass
    record['cleanup'] = cleanup_episode(folder, args.kernel_url)
    record['cleanup_seconds'] = time.monotonic() - finished
    record['evidence_files'] = {str(path.relative_to(folder)): digest(path)
                               for path in folder.rglob('*.json') if path.is_file()}
    write(receipt, record)
    print(json.dumps({key: record[key] for key in ('episode_id', 'status', 'wall_seconds_used')}, ensure_ascii=False), flush=True)
    return record


def verify_freeze(args):
    freeze = json.loads(args.implementation_freeze.read_text())
    for filename, expected in freeze['files'].items():
        if digest(Path(filename)) != expected:
            raise ValueError('implementation freeze changed: ' + filename)
    if freeze['flash_config_sha256'] != digest(args.flash_config):
        raise ValueError('Flash settings changed after implementation freeze')
    write(args.output / 'implementation-freeze.json', freeze)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sprint', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--flash-config', type=Path, required=True)
    parser.add_argument('--data-url', default='http://127.0.0.1:18924')
    parser.add_argument('--kernel-url', default='http://127.0.0.1:18700')
    parser.add_argument('--jev-launcher', type=Path, default=Path('/home/wjyuan/plugins/jev-decision/scripts/start-jev-mcp'))
    parser.add_argument('--implementation-freeze', type=Path)
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--pilot', action='store_true')
    parser.add_argument('--cases', nargs='+')
    parser.add_argument('--arms', nargs='+')
    parser.add_argument('--models', nargs='+')
    args = parser.parse_args()
    args.sprint, args.output, args.flash_config = args.sprint.resolve(), args.output.resolve(), args.flash_config.resolve()
    matrix = json.loads((args.sprint / 'evaluation-v1/public/matrix.json').read_text())
    assert len(matrix) == 528 and len({row['episode_id'] for row in matrix}) == 528
    args.output.mkdir(parents=True, exist_ok=True)
    if args.pilot:
        # Public development tasks are allowed only outside the formal denominator.
        public = json.loads((args.sprint / 'evaluation-v1/public/diagnosis.json').read_text())
        matrix = [{'episode_id': 'pilot:' + row['case_id'] + ':' + model + ':' + arm,
                   'case_id': row['case_id'], 'kind': 'diagnosis', 'model': model,
                   'arm': arm, 'repeat': 0, 'ablation': None, 'status': 'not_run', 'wall_seconds': 180}
                  for row in public if row['split'] == 'development'
                  for model in ('codex', 'deepseek-flash') for arm in ('A', 'B', 'C', 'D', 'E')]
    full_matrix = matrix
    if args.cases:
        matrix = [row for row in matrix if row['case_id'] in args.cases]
    if args.arms:
        matrix = [row for row in matrix if row['arm'] in args.arms]
    if args.models:
        matrix = [row for row in matrix if row['model'] in args.models]
    if not (args.output / 'preparation.json').exists():
        prepare(args, matrix)
    if args.prepare_only:
        print(json.dumps({'prepared': len(matrix), 'formal_started': False, 'gold_read': False}))
        return
    if not args.pilot:
        if args.implementation_freeze is None:
            raise ValueError('formal runs require a concrete implementation freeze')
        verify_freeze(args)
    semaphores = {model: threading.Semaphore(2) for model in ('codex', 'deepseek-flash')}
    def bounded(row):
        with semaphores[row['model']]:
            try:
                return run_episode(args, row)
            except Exception as error:
                episode_key = hashlib.sha256(row['episode_id'].encode()).hexdigest()[:20]
                folder = args.output / 'episodes' / episode_key
                record = {**row, 'status': 'runner_failed', 'folder': str(folder),
                          'error': type(error).__name__ + ': ' + str(error),
                          'cleanup': cleanup_episode(folder, args.kernel_url)}
                write(args.output / 'receipts' / (episode_key + '.json'), record)
                print(json.dumps({'episode_id': row['episode_id'], 'status': 'runner_failed',
                                  'error': record['error']}), flush=True)
                return record
    results = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(bounded, row) for row in schedule(matrix)]
        for future in as_completed(futures):
            results.append(future.result())
            existing = {row['episode_id']: row for row in results}
            for path in (args.output / 'receipts').glob('*.json'):
                row = json.loads(path.read_text());existing[row['episode_id']] = row
            write(args.output / 'matrix-status.json', [existing.get(row['episode_id'], row) for row in full_matrix])
    print(json.dumps({'selected': len(matrix), 'retained_denominator': len(full_matrix), 'gold_read': False}))


if __name__ == '__main__':
    main()
