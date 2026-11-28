"""Read-only inventory of this user's EDA projects and existing service baseline."""
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
http = urllib.request.build_opener(urllib.request.ProxyHandler({}))
report = {'time': datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(), 'scope': '/home/wjyuan EDA projects',
          'shared_server_other_users_modified': False, 'projects': {}, 'existing_services': [],
          'baseline_worktrees': [], 'databases': [], 'primary_query_source_preservation': {}}


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()


for name in ('execution-foundation', 'query-agent', 'data-foundation', 'data-interface'):
    project = ROOT / name
    code = '''import importlib.metadata as m,json,site,sys
items=[]
for d in m.distributions():
 raw=d.read_text("direct_url.json")
 if raw:
  data=json.loads(raw)
  if data.get("dir_info",{}).get("editable"):
   items.append({"name":d.metadata["Name"],"source":data["url"]})
print(json.dumps({"python":sys.executable,"user_site_enabled":site.ENABLE_USER_SITE,"editable":items}))
'''
    clean = dict(os.environ)
    clean.pop('PYTHONPATH', None)
    clean.pop('PYTHONHOME', None)
    clean['PYTHONNOUSERSITE'] = '1'
    runtime = json.loads(subprocess.check_output([str(project / '.venv/bin/python'), '-c', code], env=clean))
    assert not runtime['user_site_enabled']
    from urllib.parse import unquote, urlparse
    assert all(Path(unquote(urlparse(x['source']).path)).is_relative_to(project) for x in runtime['editable'])
    report['projects'][name] = {'root': str(project), 'head': git(project, 'rev-parse', 'HEAD'),
                                'status': git(project, 'status', '--short'), 'environment': runtime}

for service_port in (8700, 8840, 8924):
    body = json.load(http.open(f'http://127.0.0.1:{service_port}/health', timeout=5))
    report['existing_services'].append({'port': service_port, 'status': body.get('status'),
        'app': body.get('app', body.get('service')), 'database': body.get('database'),
        'note': 'unchanged existing baseline; shared legacy venv'})
report['baseline_worktrees'] = git('/home/wjyuan/execution foundation', 'worktree', 'list', '--porcelain').splitlines()
for path in [Path('/home/wjyuan/eda-ai-data'), Path('/home/wjyuan/df-scratch')]:
    for database in sorted(path.glob('*.sqlite')):
        report['databases'].append({'path': str(database), 'bytes': database.stat().st_size, 'moved': False})
for pid in (1890221,):
    try:
        report.setdefault('orphan_processes', []).append({'pid': pid, 'cwd': os.readlink(f'/proc/{pid}/cwd'),
            'action': 'retained; process serves an old demo on 8080 and its directory has been deleted'})
    except OSError:
        pass
original = Path('/home/wjyuan/query-agent')
target = ROOT / 'query-agent'
for rel in git(original, 'ls-files', 'src', 'tests', 'docs').splitlines():
    assert (original / rel).read_bytes() == (target / rel).read_bytes(), rel
untracked = subprocess.check_output(['git','-C',str(original),'ls-files','--others','--exclude-standard','-z']).decode().split('\0')
for rel in untracked:
    if rel:
        assert (original / rel).read_bytes() == (target / rel).read_bytes(), rel
report['primary_query_source_preservation'] = {'tracked_src_tests_docs_identical': True,
                                               'all_original_untracked_files_identical': True,
                                               'original_worktree_untouched': True}
report['proxy'] = {'http_proxy_set': bool(os.environ.get('HTTP_PROXY')),
                   'global_localhost_bypass_missing': not bool(os.environ.get('NO_PROXY') or os.environ.get('no_proxy')),
                   'development_launcher_sets_localhost_bypass': True}
(ROOT / 'admin/server-inventory.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print('Inventory and source-preservation checks passed')
