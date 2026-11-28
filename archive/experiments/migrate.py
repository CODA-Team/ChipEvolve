"""Extract independent development repositories; never mutate live sources."""
from pathlib import Path
import ast
import hashlib
import json
import os
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path('/home/wjyuan/execution foundation')
QUERY = Path('/home/wjyuan/query-agent')
FILTER = ROOT / 'admin/.venv/bin/git-filter-repo'


def run(*args, cwd=None):
    return subprocess.run(list(map(str, args)), cwd=cwd, check=True,
                          capture_output=True).stdout


def clone(source, name):
    dest = ROOT / name
    if dest.exists():
        raise FileExistsError(dest)
    run('git', 'clone', '--local', '--no-hardlinks', '--single-branch', source, dest)
    run('git', 'remote', 'remove', 'origin', cwd=dest)
    return dest


def extract(name, paths, renames=()):
    dest = clone(SOURCE, name)
    args = [FILTER, '--force']
    for path in paths:
        args += ['--path', path]
    for old, new in renames:
        args += ['--path-rename', f'{old}:{new}']
    run(*args, cwd=dest)
    return dest


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value)


tracked = [p for p in run('git', 'ls-files', '-z', cwd=SOURCE).decode().split('\0') if p]
data_tests = [p for p in tracked if p.startswith('tests/') and p.endswith('.py')
              and 'openroad_app_data_foundation' in (SOURCE / p).read_text()
              and 'openroad_app_query_agent' not in (SOURCE / p).read_text()]
interface_tests = ['tests/test_eda_ai_client.py']
integration_tests = []
for p in tracked:
    if not p.startswith('tests/') or not p.endswith('.py') or p in data_tests + interface_tests:
        continue
    content = (SOURCE / p).read_text()
    if ('qualification' in content or 'openroad_app_query_agent' in content
            or 'evidence/' in content or 'openroad_app_data_foundation' in content):
        integration_tests.append(p)

# Historical integration tests remain recoverable and are explicitly inventoried.
archive = ROOT / 'admin/legacy-integration'
for p in integration_tests:
    write(archive / p, (SOURCE / p).read_text())
write(archive / 'README.md', '这些是拆分前跨项目/论文验收测试的原始副本，不是新的默认测试集。\n'
      '完整源码、fixture、运行结果和历史仍在迁移来源仓库；请在原基线执行。\n')

df = extract('data-foundation', ['apps/data_foundation/'] + data_tests,
             [('apps/data_foundation/', '')])
sdk = extract('data-interface', ['clients/eda_ai_client/', 'CONTRACT.md'] + interface_tests,
              [('clients/eda_ai_client/', '')])
ef = clone(SOURCE, 'execution-foundation')
excluded = ['apps/data_foundation/', 'apps/query_agent/', 'clients/eda_ai_client/',
            'qualification/', 'evidence/', 'outputs/'] + data_tests + interface_tests + integration_tests
root_reports = [p for p in tracked if '/' not in p and
                (p.endswith('_REPORT.md') or p.startswith('EDA_AI_') or p in
                 ['STATUS.md', 'NEXT.md', 'BASELINE_QUALIFICATION.md', 'CONTRACT.md'])]
excluded += root_reports
args = [FILTER, '--force', '--invert-paths']
for p in excluded:
    args += ['--path', p]
run(*args, cwd=ef)

query = clone(QUERY, 'query-agent')
patch = run('git', 'diff', '--binary', 'HEAD', cwd=QUERY)
(ROOT / 'admin/query-agent-working-tree.patch').write_bytes(patch)
if patch:
    subprocess.run(['git', 'apply', '--binary', '-'], input=patch, cwd=query, check=True)
for p in run('git', 'ls-files', '--others', '--exclude-standard', '-z', cwd=QUERY).decode().split('\0'):
    if p:
        dest = query / p
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(QUERY / p, dest)

# All edits below are in the newly extracted repositories.
for dest in [df, sdk]:
    write(dest / '.gitignore', '.venv/\n__pycache__/\n.pytest_cache/\n.ruff_cache/\n*.egg-info/\nbuild/\ndist/\n*.sqlite*\n*.db\n')
    (dest / 'tests').mkdir(exist_ok=True)
    write(dest / 'tests/__init__.py', '')
    pp = dest / 'pyproject.toml'
    content = pp.read_text()
    content += '\n[tool.pytest.ini_options]\ntestpaths = ["tests"' + (', "test_data_foundation.py"' if dest == df else '') + ']\naddopts = "-ra --strict-markers"\n'
    write(pp, content)

# Fingerprints must work from an installed wheel and never inspect a sibling checkout.
init = df / 'src/openroad_app_data_foundation/__init__.py'
write(init, '''"""Deterministic design-data indexing and query service."""
from .repository import DataStore

__all__ = ("DataStore",)


def source_fingerprint() -> str:
    """Hash this deployment's service and installed public contract/client code.

    External producer provenance belongs to imported snapshot artifacts, not
    to an assumed sibling source directory on the service host.
    """
    import hashlib
    from importlib.util import find_spec
    from pathlib import Path

    digest = hashlib.sha256()
    for name in ("openroad_app_data_foundation", "openroad_platform_contracts",
                 "openroad_platform_client"):
        spec = find_spec(name)
        if spec is None or not spec.submodule_search_locations:
            raise ImportError(name)
        for directory in spec.submodule_search_locations:
            base = Path(directory)
            for path in sorted(base.rglob("*.py")):
                if path.name.startswith("test_") or "__pycache__" in path.parts:
                    continue
                digest.update((name + "/" + path.relative_to(base).as_posix()).encode())
                digest.update(path.read_bytes())
    return digest.hexdigest()
''')
artifacts = df / 'src/openroad_app_data_foundation/artifacts.py'
content = artifacts.read_text().replace('or "/home/wjyuan/projects/orfs-current/OpenROAD-flow-scripts/flow"',
                                        'or "var/native-flow"')
write(artifacts, content)
smoke = df / 'smoke.py'
content = smoke.read_text()
content = content.replace('SRC_DIR = APP_DIR / "src"\nCONTRACTS_DIR = APP_DIR.parents[1] / "contracts" / "src"\nCLIENT_DIR = APP_DIR.parents[1] / "core" / "client" / "src"\n', '')
start = content.index('        env["PYTHONPATH"] =')
end = content.index('        proc =', start)
content = content[:start] + '        env.pop("PYTHONPATH", None)\n' + content[end:]
write(smoke, content)

ini = ef / 'pytest.ini'
content = ini.read_text()
for line in ['    apps/query_agent/src\n', '    apps/data_foundation/src\n', '    clients/eda_ai_client/src\n']:
    content = content.replace(line, '')
write(ini, content)
install = ef / 'tools/install-local.sh'
content = install.read_text().replace('  -e "$platform_root/apps/plan_executor" \\\n  -e "$platform_root/apps/data_foundation" \\\n  -e "$platform_root/apps/query_agent"', '  -e "$platform_root/apps/plan_executor"')
write(install, content)
for path in ['apps.json', 'examples/gateway-agent.json']:
    conf = json.loads((ef / path).read_text())
    conf['apps'] = [x for x in conf['apps'] if x['name'] not in ['query_agent', 'data_foundation']]
    write(ef / path, json.dumps(conf, ensure_ascii=False, indent=2) + '\n')
smokes = ef / 'tests/test_app_smokes.py'
write(smokes, smokes.read_text().replace('    "query_agent",\n', '').replace('    "data_foundation",\n', ''))
packaging = ef / 'tests/test_packaging.py'
write(packaging, packaging.read_text().replace('    (REPO_ROOT / "apps" / "query_agent", "src"),\n', ''))

projects = {'execution-foundation': ef, 'query-agent': query,
            'data-foundation': df, 'data-interface': sdk}
sources = {}
for name, dest in projects.items():
    source = QUERY if name == 'query-agent' else SOURCE
    sources[name] = {'original_path': str(source),
                     'original_head': run('git', 'rev-parse', 'HEAD', cwd=source).decode().strip(),
                     'filtered_head': run('git', 'rev-parse', 'HEAD', cwd=dest).decode().strip(),
                     'history': 'preserved; see .git/filter-repo/commit-map for extracted repositories'}
    write(dest / 'MIGRATION_SOURCE.json', json.dumps(sources[name], indent=2) + '\n')
write(ROOT / 'admin/migration-manifest.json', json.dumps({
    'projects': sources, 'data_tests': data_tests, 'interface_tests': interface_tests,
    'legacy_integration_tests': integration_tests, 'excluded_execution_paths': excluded,
    'query_uncommitted_changes_preserved': True,
}, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'projects': list(projects), 'data_test_files': len(data_tests),
                  'legacy_integration_files': len(integration_tests)}, indent=2))
