#!/usr/bin/env python3
"""Project commands that do not inherit other projects' Python or local proxies."""
import argparse
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent
PROJECTS = ('execution-foundation', 'query-agent', 'data-foundation', 'data-interface')
parser = argparse.ArgumentParser()
parser.add_argument('project', choices=PROJECTS)
parser.add_argument('command', choices=('check', 'smoke', 'python', 'shell', 'serve'))
parser.add_argument('args', nargs=argparse.REMAINDER)
args = parser.parse_args()
project = ROOT / args.project
python = project / '.venv/bin/python'
env = dict(os.environ)
for key in ('PYTHONPATH', 'PYTHONHOME', 'VIRTUAL_ENV', 'CONDA_PREFIX'):
    env.pop(key, None)
env.update(PYTHONNOUSERSITE='1', NO_PROXY='localhost,127.0.0.1,::1',
           no_proxy='localhost,127.0.0.1,::1', VIRTUAL_ENV=str(project / '.venv'))
env['PATH'] = str(project / '.venv/bin') + os.pathsep + env.get('PATH', '')
if args.command == 'check':
    commands = [[str(python), '-m', 'pip', 'check'], [str(python), '-m', 'pytest', *args.args]]
elif args.command == 'smoke':
    commands = [[str(python), 'smoke.py', *args.args]] if args.project == 'data-foundation' else \
               [[str(python), '-m', 'pytest', *(['tests/test_app_smokes.py'] if args.project == 'execution-foundation' else ['tests']), *args.args]]
elif args.command == 'python':
    commands = [[str(python), *args.args]]
elif args.command == 'shell':
    commands = [['bash', '--noprofile', '--norc', *args.args]]
elif args.project == 'data-foundation':
    state = ROOT / 'var/data-foundation'
    state.mkdir(parents=True, exist_ok=True)
    commands = [[str(python), '-m', 'openroad_app_data_foundation', '--host', '127.0.0.1',
                 '--port', '18924', '--db', str(state / 'snapshots.sqlite'),
                 '--no-auto-import', '--native-root', str(state / 'native-flow'), *args.args]]
elif args.project == 'execution-foundation':
    state = ROOT / 'var/execution-foundation'
    state.mkdir(parents=True, exist_ok=True)
    commands = [[str(python), '-m', 'openroad_platform_gateway', '--host', '127.0.0.1',
                 '--port', '18700', '--state-root', str(state), '--no-auth',
                 '--plugins-root', str(project / 'plugins'),
                 '--admissions-root', str(project / 'admissions'), *args.args]]
else:
    parser.error('此项目没有独立 HTTP 服务；Query Agent 使用 CLI，Data Interface 是 SDK。')
for command in commands:
    result = subprocess.run(command, cwd=project, env=env)
    if result.returncode:
        raise SystemExit(result.returncode)
