"""Freeze the existing A2 tree and run P1 without editing its runtime source."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tarfile
from datetime import datetime, timezone

WORKSPACE = Path(__file__).resolve().parents[1]
ORIGINAL = Path('/home/wjyuan/flow-agent')
FORMAL = WORKSPACE / 'flow-agent'
RUN = WORKSPACE / 'var/flow-agent/p1-native-20261010'


def now():
    return datetime.now(timezone.utc).isoformat()


def call(args, cwd=None):
    return subprocess.check_output(args, cwd=cwd, text=True).strip()


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def write_json(path, value):
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    temp.replace(path)


def prepare():
    if FORMAL.exists() or RUN.exists():
        raise SystemExit('Baseline directories already exist; inspect receipts before continuing.')
    RUN.mkdir(parents=True)
    evidence = RUN / 'baseline'
    evidence.mkdir()
    names = subprocess.check_output(
        ['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], cwd=ORIGINAL,
    ).decode().split('\0')
    names = sorted(set(name for name in names if name))
    manifest = []
    for name in names:
        path = ORIGINAL / name
        if not path.is_file():
            raise RuntimeError(f'Cannot freeze source entry: {name}')
        manifest.append({'path': name, 'sha256': digest(path), 'mode': oct(path.stat().st_mode & 0o777)})
    (evidence / 'source.patch').write_bytes(subprocess.check_output(
        ['git', 'diff', '--binary', 'HEAD'], cwd=ORIGINAL))
    (evidence / 'worktree-status.txt').write_text(call(['git', 'status', '--short'], ORIGINAL) + '\n')
    requirements = call([str(ORIGINAL / '.venv/bin/python'), '-m', 'pip', 'freeze']) + '\n'
    (evidence / 'installed-requirements.txt').write_text(requirements)
    with tarfile.open(evidence / 'source.tar.gz', 'w:gz') as archive:
        for name in names:
            archive.add(ORIGINAL / name, arcname=name, recursive=False)
    subprocess.run(['git', 'clone', '--no-hardlinks', str(ORIGINAL), str(FORMAL)], check=True)
    subprocess.run(['git', 'remote', 'set-url', 'origin', 'https://github.com/yfz2024/A2-ORFO.git'], cwd=FORMAL, check=True)
    for name in names:
        target = FORMAL / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ORIGINAL / name, target)
    subprocess.run(['git', 'add', '--all'], cwd=FORMAL, check=True)
    subprocess.run(['git', 'commit', '-m', 'Freeze verified local A2 baseline for platform integration'], cwd=FORMAL, check=True)
    subprocess.run(['/usr/bin/python', '-m', 'venv', '--without-pip', str(FORMAL / '.venv')], check=True)
    source_packages = ORIGINAL / '.venv/lib/python3.12/site-packages'
    target_packages = FORMAL / '.venv/lib/python3.12/site-packages'
    subprocess.run(['cp', '-a', '--reflink=auto', str(source_packages) + '/.', str(target_packages)], check=True)
    subprocess.run([str(FORMAL / '.venv/bin/python'), '-m', 'pip', 'check'], check=True)
    observed = call([str(FORMAL / '.venv/bin/python'), '-m', 'pip', 'freeze']) + '\n'
    if observed != requirements:
        raise RuntimeError('Copied installed dependency inventory differs from the baseline.')
    source = RUN / 'source'
    subprocess.run(['git', 'clone', '--no-hardlinks', str(FORMAL), str(source)], check=True)
    # This server-local file names tool executables only. API credentials are excluded.
    shutil.copy2(ORIGINAL / 'config/env.local.sh', source / 'config/env.local.sh')
    tools = {}
    for name, path in {
        'openroad': '/opt/EDAs/OpenROAD-flow-scripts/versions/20260409/tools/install/OpenROAD/bin/openroad',
        'yosys': '/opt/EDAs/OpenROAD-flow-scripts/versions/20260409/tools/install/yosys/bin/yosys',
        'slang': '/opt/EDAs/OpenROAD-flow-scripts/versions/20260409/tools/install/yosys/share/yosys/plugins/slang.so',
    }.items():
        tools[name] = {'path': path, 'sha256': digest(Path(path))}
    tools['openroad']['version'] = call([tools['openroad']['path'], '-version'])
    tools['yosys']['version'] = call([tools['yosys']['path'], '-V'])
    tools['codex'] = {'path': shutil.which('codex'), 'version': call(['codex', '--version'])}
    write_json(evidence / 'manifest.json', {
        'created_at': now(), 'original': str(ORIGINAL),
        'upstream_commit': call(['git', 'rev-parse', 'HEAD'], ORIGINAL),
        'formal_commit': call(['git', 'rev-parse', 'HEAD'], FORMAL),
        'source_files': manifest, 'archive_sha256': digest(evidence / 'source.tar.gz'),
        'tools': tools, 'dependencies': 'installed-requirements.txt',
        'environment': {'python': call([str(FORMAL / '.venv/bin/python'), '--version']),
                        'make': call(['make', '--version']).splitlines()[0],
                        'allowed_cpus': sorted(os.sched_getaffinity(0))},
        'dependency_method': 'Independent venv with copied installed distributions; no sibling source imports.',
        'credential_files_archived': False,
    })
    print(json.dumps({'formal_source': str(FORMAL), 'run_source': str(source), 'baseline': str(evidence)}))


def supervise():
    source = RUN / 'source'
    receipt_path = RUN / 'receipt.json'
    if receipt_path.exists():
        raise SystemExit('Receipt exists; refusing to start another campaign in this directory.')
    env = os.environ.copy()
    env.update({'VIRTUAL_ENV': str(FORMAL / '.venv'),
                'PATH': str(FORMAL / '.venv/bin') + os.pathsep + env['PATH'],
                'PYTHONNOUSERSITE': '1', 'DRP_LLM_TRANSPORT': 'codex',
                'DRP_CODEX_AUDIT_DIR': str(RUN / 'model-audit'),
                'OMP_NUM_THREADS': '2', 'OPENBLAS_NUM_THREADS': '2', 'MKL_NUM_THREADS': '2'})
    env.pop('PYTHONPATH', None)
    command = ['./run.sh', '-p', 'nangate45', '-d', 'aes', '-o', 'TNS_EVAL',
               '-i', '2', '-r', '3', '-k', '1', '-s', 'elitist', '-A', '-P', '-F',
               '--seed', '42', '--cpus', '6', '--max-concurrent-runs', '1', '-t', '20m']
    source_hashes = {row['path']: row['sha256'] for row in json.loads(
        (RUN / 'baseline/manifest.json').read_text())['source_files']}
    # Verify the independent execution tree, including locally modified file content.
    changed = [name for name, sha in source_hashes.items() if digest(source / name) != sha]
    if changed:
        raise RuntimeError(f'Runtime tree differs from frozen source: {changed}')
    with (RUN / 'campaign.log').open('x') as log:
        process = subprocess.Popen(command, cwd=source, env=env, stdout=log,
                                   stderr=subprocess.STDOUT, start_new_session=True)
        receipt = {'started_at': now(), 'status': 'running', 'command': command,
                   'cwd': str(source), 'pid': process.pid, 'process_group': process.pid,
                   'proc_start_ticks': Path(f'/proc/{process.pid}/stat').read_text().split()[21],
                   'supervisor_pid': os.getpid(), 'wall_budget_seconds': 10800,
                   'physical_concurrency': 1, 'threads_per_candidate': 2,
                   'model_transport': 'codex', 'formal_commit': call(['git', 'rev-parse', 'HEAD'], FORMAL)}
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
            name for name, sha in source_hashes.items() if digest(source / name) != sha])
        write_json(receipt_path, receipt)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'supervise'])
    action = parser.parse_args().action
    prepare() if action == 'prepare' else supervise()
