"""Repeat a frozen native campaign in a fresh isolated directory."""
import argparse
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess

from flow_native_baseline import FORMAL, WORKSPACE, call, digest, now, write_json


def prepare(run, baseline):
    if run.exists():
        raise SystemExit('Run directory exists; preserve it and choose a fresh directory.')
    manifest = json.loads((baseline / 'baseline/manifest.json').read_text())
    run.mkdir(parents=True)
    source = run / 'source'
    subprocess.run(['git', 'clone', '--no-hardlinks', str(FORMAL), str(source)], check=True)
    subprocess.run(['git', 'checkout', '--detach', manifest['formal_commit']],
                   cwd=source, check=True)
    shutil.copy2(baseline / 'source/config/env.local.sh', source / 'config/env.local.sh')
    write_json(run / 'baseline-reference.json', {
        'baseline': str(baseline), 'manifest_sha256': digest(baseline / 'baseline/manifest.json'),
        'formal_commit': manifest['formal_commit'], 'prepared_at': now()})


def supervise(run, baseline, threads, stage_timeout):
    receipt_path = run / 'receipt.json'
    if receipt_path.exists():
        raise SystemExit('Receipt exists; never start a second campaign in the same directory.')
    source = run / 'source'
    manifest = json.loads((baseline / 'baseline/manifest.json').read_text())
    hashes = {row['path']: row['sha256'] for row in manifest['source_files']}
    changed = [name for name, sha in hashes.items() if digest(source / name) != sha]
    if changed:
        raise RuntimeError('Source differs from frozen baseline: ' + repr(changed))
    environment = dict(os.environ)
    environment.pop('PYTHONPATH', None)
    environment.update(VIRTUAL_ENV=str(FORMAL / '.venv'),
                       PATH=str(FORMAL / '.venv/bin') + os.pathsep + environment['PATH'],
                       PYTHONNOUSERSITE='1', DRP_LLM_TRANSPORT='codex',
                       DRP_CODEX_AUDIT_DIR=str(run / 'model-audit'),
                       OMP_NUM_THREADS=str(threads), OPENBLAS_NUM_THREADS=str(threads),
                       MKL_NUM_THREADS=str(threads))
    command = ['./run.sh', '-p', 'nangate45', '-d', 'aes', '-o', 'TNS_EVAL',
               '-i', '2', '-r', '3', '-k', '1', '-s', 'elitist', '-A', '-P', '-F',
               '--seed', '42', '--cpus', str(3 * threads), '--max-concurrent-runs', '1',
               '-t', stage_timeout]
    with (run / 'campaign.log').open('x') as log:
        process = subprocess.Popen(command, cwd=source, env=environment, stdout=log,
                                   stderr=subprocess.STDOUT, start_new_session=True)
        receipt = {'started_at': now(), 'status': 'running', 'command': command,
                   'cwd': str(source), 'pid': process.pid, 'process_group': process.pid,
                   'proc_start_ticks': Path(f'/proc/{process.pid}/stat').read_text().split()[21],
                   'supervisor_pid': os.getpid(), 'wall_budget_seconds': 10800,
                   'physical_concurrency': 1, 'threads_per_candidate': threads,
                   'model_transport': 'codex', 'formal_commit': call(['git', 'rev-parse', 'HEAD'], source),
                   'baseline': str(baseline), 'stage_timeout': stage_timeout}
        write_json(receipt_path, receipt)
        with (run / 'capture.log').open('x') as capture_log:
            watcher = subprocess.Popen(['/usr/bin/python', str(WORKSPACE / 'admin/capture_native_iterations.py'),
                                        '--run-root', str(run)], stdout=capture_log,
                                       stderr=subprocess.STDOUT, start_new_session=True)
        receipt['capture_pid'] = watcher.pid
        write_json(receipt_path, receipt)
        try:
            result = process.wait(timeout=receipt['wall_budget_seconds'])
            receipt.update(status='completed' if result == 0 else 'failed', exit_code=result)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                result = process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                result = process.wait()
            receipt.update(status='budget_exhausted', exit_code=result)
        receipt.update(finished_at=now(), source_changed=[
            name for name, sha in hashes.items() if digest(source / name) != sha])
        write_json(receipt_path, receipt)
        receipt['capture_exit_code'] = watcher.wait(timeout=30)
        write_json(receipt_path, receipt)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'supervise'])
    parser.add_argument('--run-root', type=Path, required=True)
    parser.add_argument('--baseline', type=Path, default=WORKSPACE / 'var/flow-agent/p1-native-20261010')
    parser.add_argument('--threads', type=int, default=8)
    parser.add_argument('--stage-timeout', default='90m')
    args = parser.parse_args()
    run_root = args.run_root.resolve()
    baseline_root = args.baseline.resolve()
    if args.threads < 1:
        parser.error('--threads must be positive')
    if args.action == 'prepare':
        prepare(run_root, baseline_root)
    else:
        supervise(run_root, baseline_root, args.threads, args.stage_timeout)
