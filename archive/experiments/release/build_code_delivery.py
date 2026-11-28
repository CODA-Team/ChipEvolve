"""Package local Git repositories, frozen wheels and offline dependencies.

This does not publish repositories or assign a release-candidate verdict. The
separate engineering and business report determines which acceptance passed.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess


PROJECTS = ('execution-foundation', 'data-foundation', 'data-interface', 'toolkits', 'query-agent')


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def git(folder, *args):
    return subprocess.check_output(['git', *args], cwd=folder, text=True).strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--sprint', type=Path, required=True)
    parser.add_argument('--dependencies', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = args.workspace.resolve()
    sprint = args.sprint.resolve()
    target = args.output.resolve()
    freeze = json.loads((sprint / 'implementation-freeze-v1.json').read_text())
    for name in (*PROJECTS, '.'):
        folder = root / name
        if git(folder, 'status', '--porcelain'):
            raise ValueError('Package only committed repositories: ' + name)
        if name != '.' and git(folder, 'rev-parse', 'HEAD') != freeze['repositories'][name]['commit']:
            raise ValueError('Product commit changed after evaluation freeze: ' + name)
    target.mkdir(parents=True, exist_ok=False)
    bundles = target / 'repositories'
    bundles.mkdir()
    repos = {}
    with (target / 'git-bundle.log').open('w') as log:
        for name in (*PROJECTS, '.'):
            label = name if name != '.' else 'workspace'
            folder = root / name
            path = bundles / (label + '.bundle')
            command = ['git', 'bundle', 'create', str(path), '--all']
            log.write(json.dumps(command) + '\n')
            log.flush()
            subprocess.run(command, cwd=folder, check=True, stdout=log, stderr=subprocess.STDOUT)
            subprocess.run(['git', 'bundle', 'verify', str(path)], cwd=folder, check=True, stdout=log, stderr=subprocess.STDOUT)
            repos[label] = {'source_commit': git(folder, 'rev-parse', 'HEAD'),
                            'frozen_model_commit': freeze['repositories'][name]['commit'],
                            'sha256': digest(path), 'size_bytes': path.stat().st_size,
                            'history_retained': True}
    packages = sprint / 'packages-freeze-v1'
    wheel_manifest = json.loads((packages / 'manifest.json').read_text())
    for name, expected in wheel_manifest['wheels'].items():
        if digest(packages / name) != expected:
            raise ValueError('Frozen wheel changed: ' + name)
    shutil.copytree(packages, target / 'packages')
    dependencies = target / 'dependencies'
    dependencies.mkdir()
    for source in sorted(args.dependencies.glob('*.whl')):
        shutil.copyfile(source, dependencies / source.name)
    if not list(dependencies.glob('*.whl')):
        raise ValueError('Offline dependency wheelhouse is empty')
    shutil.copyfile(sprint / 'implementation-freeze-v1.json', target / 'implementation-freeze-v1.json')
    files = {str(path.relative_to(target)): {'sha256': digest(path), 'size_bytes': path.stat().st_size}
             for path in sorted(target.rglob('*')) if path.is_file()}
    manifest = {'created_at': datetime.now(timezone.utc).isoformat(), 'repositories': repos, 'files': files,
                'builder_sha256': digest(Path(__file__)),
                'toolchain': freeze['toolchain'], 'toolchain_image_bundled': False,
                'models': freeze['models'], 'credentials_bundled': False,
                'label': 'Frozen code and reproducibility assets; release-candidate acceptance is reported separately.',
                'published_to_github': False,
                'workspace_commit_note': 'The workspace may add post-freeze scoring, audit and delivery programs; the frozen model implementation remains unchanged.'}
    (target / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'destination': str(target), 'repositories': len(repos),
                      'product_wheels': len(wheel_manifest['wheels']), 'dependency_wheels': len(list(dependencies.glob('*.whl'))),
                      'size_bytes': sum(row['size_bytes'] for row in files.values()), 'github_published': False}))


if __name__ == '__main__':
    main()
