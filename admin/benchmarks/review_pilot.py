"""Audit pilot scoring and actual tool use without overwriting original results."""
import argparse
import json
from pathlib import Path
import shutil
from urllib.parse import unquote

parser = argparse.ArgumentParser()
parser.add_argument('pilot', type=Path)
args = parser.parse_args()
pilot = args.pilot.resolve()
original = json.loads((pilot / 'results.json').read_text())
reviewed = []
for result in original['results']:
    record = pilot / f"{result['case']}-{result['arm']}-{result['repeat']}"
    answer = json.loads((record / 'answer.json').read_text())
    checks = dict(result['checks'])
    changes = []
    if result['case'] == 'interface':
        cited = unquote(answer['notes'] + '\n' + '\n'.join(answer['evidence']))
        checks['instance'] = 'core/u1+test%1' in cited and 'available' in cited
        if checks['instance'] != result['checks']['instance']:
            changes.append('Original grader inspected notes only; the correct exact-name lookup was in evidence.')
    if result['case'] == 'query' and result['arm'] == 'infra':
        events = [json.loads(line) for line in (record / 'events.jsonl').read_text().splitlines()]
        checks['query_agent_used'] = any(
            event.get('type') == 'item.completed'
            and event.get('item', {}).get('type') == 'command_execution'
            and 'query_agent.interfaces.cli' in event['item'].get('command', '')
            for event in events
        )
        if not checks['query_agent_used']:
            changes.append('SDK-only comparison is not a Query Agent measurement; exclude this observation from its comparison.')
    workspace = Path((record / 'workspace.txt').read_text().strip())
    if workspace.is_dir() and not (record / 'workspace').exists():
        shutil.copytree(workspace, record / 'workspace')
    reviewed.append({**result, 'checks': checks,
                     'passed': all(checks.values()) and result['exit_code'] == 0,
                     'audit_changes': changes})
(pilot / 'reviewed-results.json').write_text(json.dumps({
    'original_results_preserved': True,
    'method': 'Same grader for both arms; inspect notes and evidence and actual completed command events.',
    'results': reviewed,
}, indent=2) + '\n')
print(json.dumps({'total': len(reviewed), 'passed': sum(row['passed'] for row in reviewed),
                  'changed': sum(bool(row['audit_changes']) for row in reviewed)}))
