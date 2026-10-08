"""Build pinned public wheels and provision four isolated development venvs."""
from pathlib import Path
import json
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
WHEELS = ROOT / 'wheelhouse'
EF = ROOT / 'execution-foundation'
TOOLS = ['setuptools==84.0.0', 'wheel==0.48.0', 'pytest==9.1.1',
         'ruff==0.16.8', 'pydantic==2.13.4', 'pyright==1.1.414', 'import-linter==2.15']
PACKAGES = ['contracts', 'core/client', 'core/runtime', 'core/registry',
            'core/evaluator', 'core/provenance', 'core/identity', 'gateway',
            'apps/plan_executor', 'apps/dse_lab', 'apps/evidence_console', 'apps/run_console']
ENV = dict(os.environ)
for key in ['PYTHONPATH', 'PYTHONHOME', 'VIRTUAL_ENV']:
    ENV.pop(key, None)
ENV.update(PYTHONNOUSERSITE='1', NO_PROXY='localhost,127.0.0.1,::1',
           no_proxy='localhost,127.0.0.1,::1', PIP_DISABLE_PIP_VERSION_CHECK='1')


def run(args, cwd=None):
    print(' '.join(map(str, args)), flush=True)
    subprocess.run(list(map(str, args)), cwd=cwd, env=ENV, check=True)


def pip(python, *args):
    run([python, '-m', 'pip', *args])


pip(sys.executable, 'download', '-d', WHEELS, *TOOLS)
for package in PACKAGES:
    pip(sys.executable, 'wheel', '--no-deps', '--no-build-isolation', '-w', WHEELS, EF / package)
for name in ['data-foundation', 'data-interface', 'query-agent']:
    pip(sys.executable, 'wheel', '--no-deps', '--no-build-isolation', '-w', WHEELS, ROOT / name)

for name in ['execution-foundation', 'data-foundation', 'data-interface', 'query-agent']:
    project = ROOT / name
    run([sys.executable, '-m', 'venv', project / '.venv'])
    python = project / '.venv/bin/python'
    pip(python, 'install', '--no-index', '--find-links', WHEELS,
        'setuptools==84.0.0', 'wheel==0.48.0', 'pytest==9.1.1', 'ruff==0.16.8')
    if name == 'execution-foundation':
        pip(python, 'install', '--no-index', '--find-links', WHEELS,
            *['openroad-platform-' + p for p in ['contracts', 'client', 'runtime', 'registry',
              'evaluator', 'provenance', 'identity', 'gateway']])
        for path in PACKAGES:
            pip(python, 'install', '--no-deps', '--no-build-isolation', '-e', project / path)
    elif name == 'query-agent':
        pip(python, 'install', '--no-index', '--find-links', WHEELS,
            'pydantic==2.13.4', 'pyright==1.1.414', 'import-linter==2.15')
        pip(python, 'install', '--no-deps', '--no-build-isolation', '-e', project)
    elif name == 'data-foundation':
        pip(python, 'install', '--no-index', '--find-links', WHEELS,
            'openroad-platform-contracts==0.1.0', 'openroad-platform-client==0.1.0',
            'openroad-platform-runtime==0.1.0')  # runtime is a test fixture dependency
        pip(python, 'install', '--no-deps', '--no-build-isolation', '-e', project)
    else:
        pip(python, 'install', '--no-deps', '--no-build-isolation', '-e', project)
    frozen = subprocess.check_output([str(python), '-m', 'pip', 'freeze', '--all'], env=ENV).decode()
    (project / 'environment.lock.txt').write_text(frozen)
    pip(python, 'check')

# This file makes the local artifact source auditable and detects accidental replacement.
import hashlib
manifest = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(WHEELS.glob('*.whl'))}
(WHEELS / 'sha256.json').write_text(json.dumps(manifest, indent=2) + '\n')
