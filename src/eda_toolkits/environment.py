"""Explicit tool discovery and deployment checks."""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess


def available_memory_bytes():
    for line in Path('/proc/meminfo').read_text().splitlines():
        if line.startswith('MemAvailable:'):
            return int(line.split()[1]) * 1024
    raise RuntimeError('host cannot report MemAvailable')


def require_eda_memory():
    available = available_memory_bytes()
    if available < 16 * 1024**3:
        raise RuntimeError('new EDA work paused: less than 16 GiB available memory')
    return available


def doctor(config):
    image = Path(config['orfs_image']).resolve()
    runtime = shutil.which(config.get('container_runtime', 'apptainer'))
    binary = Path(config['openroad_bin']).resolve()
    if not runtime or not image.is_file() or not os.access(binary, os.X_OK):
        raise ValueError('tool configuration requires executable runtime/OpenROAD and an existing ORFS image')
    checked = {}
    for name, command in {
        'openroad': [str(binary), '-version'],
        'yosys': [runtime, 'exec', '--cleanenv', '--containall', str(image),
                  '/OpenROAD-flow-scripts/tools/install/yosys/bin/yosys', '-V'],
        'klayout': [runtime, 'exec', '--cleanenv', '--containall', str(image), 'klayout', '-v'],
    }.items():
        result = subprocess.run(command, capture_output=True, text=True, timeout=30,
                                env={**os.environ,'EDA_ORFS_IMAGE':str(image)})
        checked[name] = {'command': command, 'exit_code': result.returncode,
                         'version_output': result.stdout + result.stderr}
    with image.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    return {'tools': checked, 'image': str(image), 'image_sha256': digest,
            'available_memory_bytes': available_memory_bytes(),
            'passed': all(row['exit_code'] == 0 for row in checked.values())}
