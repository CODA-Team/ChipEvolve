"""Release all service/client wheels without cross-checkout editable installs."""
import os
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
paths = ['contracts', 'core/runtime', 'core/registry', 'core/evaluator', 'core/provenance', 'core/client', 'gateway']
packages = [root / 'execution-foundation' / p for p in paths]
packages += [root / p for p in ('data-foundation', 'data-interface', 'query-agent')]
env = dict(os.environ, PYTHONNOUSERSITE='1')
for key in ('PYTHONPATH', 'PYTHONHOME'):
    env.pop(key, None)
subprocess.run([str(root / "execution-foundation/.venv/bin/python"), '-m', 'pip', 'wheel', '--no-deps', '--no-build-isolation',
                '-w', str(root / 'wheelhouse'), *map(str, packages)], env=env, check=True)
