"""Record actual commits, source bytes, task matrix and runtime dependencies."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess


PROJECTS = ('execution-foundation', 'data-foundation', 'data-interface', 'toolkits', 'query-agent')


def digest(path):
    hasher = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1048576), b''):
            hasher.update(block)
    return hasher.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sprint', type=Path, required=True)
    parser.add_argument('--packages', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    sprint = args.sprint.resolve()
    files, repos = {}, {}
    for name in (*PROJECTS, '.'):
        folder = (root / name).resolve()
        status = subprocess.check_output(['git', 'status', '--porcelain'], cwd=folder, text=True)
        if status:
            raise ValueError('freeze requires committed work: ' + name + '\n' + status)
        repos[name] = {'root': str(folder), 'commit': subprocess.check_output(
            ['git', 'rev-parse', 'HEAD'], cwd=folder, text=True).strip()}
        tracked = subprocess.check_output(['git', 'ls-files', '-z'], cwd=folder).decode().split('\0')
        for relative in tracked:
            path = folder / relative
            if relative and path.is_file():
                files[str(path)] = digest(path)
    for folder in (sprint / 'evaluation-v1', sprint / 'public-bindings-v1', args.packages.resolve()):
        for path in sorted(folder.rglob('*')):
            if path.is_file():
                files[str(path.resolve())] = digest(path)
    settings = ('flash-low-settings.json', 'toolchain-settings.json', 'jev-pricing.json')
    for name in settings:
        files[str(sprint / name)] = digest(sprint / name)
    launcher = Path('/home/wjyuan/plugins/jev-decision/scripts/start-jev-mcp')
    files[str(launcher)] = digest(launcher)
    for path in launcher.parent.parent.rglob('package-lock.json'):
        if 'node_modules' not in str(path):
            files[str(path)] = digest(path)
    toolchain = json.loads((sprint / 'toolchain-settings.json').read_text())
    image = Path(toolchain['orfs_image'])
    image_sha = digest(image)
    expected = json.loads((sprint / 'shared-toolchain-orfs-2/summary.json').read_text())['image_sha256']
    if image_sha != expected:
        raise ValueError('toolchain image differs from the validated toolchain')
    files[str(image)] = image_sha
    # Baseline preparation is immutable; native sessions write only in episodes.
    for folder in (sprint / 'direct-baseline-v1').iterdir():
        if not folder.is_dir():
            continue
        for name in ('native.json', 'index.sqlite', 'preparation-v2.json'):
            path = folder / name
            if path.is_file():
                files[str(path)] = digest(path)
        native_path = folder / 'native.json'
        if native_path.is_file():
            native = json.loads(native_path.read_text())
            for ref in native['files']:
                path = folder / ref['path']
                actual = digest(path)
                if actual != ref['sha256']:
                    raise ValueError('baseline source differs from registered native bytes: ' + str(path))
                files[str(path)] = actual
    matrix = json.loads((sprint / 'evaluation-v1/public/matrix.json').read_text())
    assert len(matrix) == len({row['episode_id'] for row in matrix}) == 528
    result = {
        'frozen_at': datetime.now(timezone.utc).isoformat(), 'repositories': repos,
        'files': files, 'flash_config_sha256': digest(sprint / 'flash-low-settings.json'),
        'matrix_count': 528,
        'models': {'codex': {'model': 'gpt-6.1-sol', 'reasoning_effort': 'medium', 'billing': 'subscription'},
                   'flash': {'model': 'deepseek-flash', 'settings_sha256': digest(sprint / 'flash-low-settings.json')},
                   'jev': {'package': 'jev-mcp', 'version': '0.14.1', 'provider': 'openrouter',
                           'model': 'typesafe/jev-1.13', 'routing_threshold': 0.85, 'routing_margin': 0.5}},
        'concurrency': {'codex': 2, 'flash': 2, 'active_eda': 1},
        'toolchain': {'image': str(image), 'sha256': image_sha,
                      'runtime_version': subprocess.check_output(['apptainer', '--version'], text=True).strip()},
        'sealed_diagnosis_opened_before_freeze': False,
        'routing_sealed_opened_before_freeze': True,
        'policy': 'No implementation or threshold tuning from sealed diagnosis; retain first failures and denominator.',
    }
    with args.output.open('x') as output:
        output.write(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'files': len(files), 'matrix_count': 528, 'output': str(args.output)}))


if __name__ == '__main__':
    main()
