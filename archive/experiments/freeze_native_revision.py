"""Freeze an audited native source correction against the original P1 archive."""
import argparse
import json
import shutil
import subprocess
from pathlib import Path

from flow_native_baseline import FORMAL, call, digest, now, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    reference = args.reference.resolve()
    output = args.output.resolve()
    if output.exists():
        raise SystemExit('Use a fresh source baseline directory.')
    if call(['git', 'status', '--porcelain'], FORMAL):
        raise RuntimeError('Commit the audited native correction before freezing it.')
    prior = json.loads((reference / 'baseline/manifest.json').read_text())
    observed = call([str(FORMAL / '.venv/bin/python'), '-m', 'pip', 'freeze']) + '\n'
    if observed != (reference / 'baseline/installed-requirements.txt').read_text():
        raise RuntimeError('Native installed dependencies differ from the original reference.')
    for name in ('openroad', 'yosys', 'slang'):
        if digest(Path(prior['tools'][name]['path'])) != prior['tools'][name]['sha256']:
            raise RuntimeError('A native tool differs from the original reference: ' + name)
    baseline = output / 'baseline'
    baseline.mkdir(parents=True)
    names = call(['git', 'ls-files'], FORMAL).splitlines()
    files = [{'path': name, 'sha256': digest(FORMAL / name),
              'mode': oct((FORMAL / name).stat().st_mode & 0o777)} for name in names]
    patch = baseline / 'source-delta.patch'
    patch.write_bytes(subprocess.check_output(['git', 'diff', '--binary',
                      prior['formal_commit'], 'HEAD'], cwd=FORMAL))
    shutil.copy2(reference / 'baseline/installed-requirements.txt', baseline / 'installed-requirements.txt')
    local = output / 'source/config/env.local.sh'
    local.parent.mkdir(parents=True)
    shutil.copy2(reference / 'source/config/env.local.sh', local)
    write_json(baseline / 'manifest.json', {
        'created_at': now(), 'formal_commit': call(['git', 'rev-parse', 'HEAD'], FORMAL),
        'upstream_commit': prior['upstream_commit'], 'source_files': files,
        'tools': prior['tools'], 'dependencies': 'installed-requirements.txt',
        'source_snapshot': {'reference_manifest': str(reference / 'baseline/manifest.json'),
                            'reference_manifest_sha256': digest(reference / 'baseline/manifest.json'),
                            'original_source_archive': str(reference / 'baseline/source.tar.gz'),
                            'original_source_archive_sha256': prior['archive_sha256'],
                            'delta': patch.name, 'delta_sha256': digest(patch)},
        'correction': 'Nangate45 AES consumes independently scoped floorplan and post-CTS routing parameters; baseline layer capacities remain 0.5/0.25.',
        'native_algorithms_changed': False, 'dependencies_changed': False})
    print(json.dumps({'baseline': str(output), 'files': len(files)}))


if __name__ == '__main__':
    main()
