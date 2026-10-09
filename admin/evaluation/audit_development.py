"""Audit only development traces against independent native artifacts.

Identity/source verification is deterministic. A separate, explicit reviewer
record is required for semantic success; answered status alone is never a grade.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time

from openroad_platform_client import KernelClient, KernelError


def sources(value, refs):
    if isinstance(value, dict):
        if all(isinstance(value.get(key), str) for key in ('run_id', 'artifact_id', 'sha256')):
            key = (value['run_id'], value['artifact_id'])
            refs.setdefault(key, set()).add(value['sha256'])
        for item in value.values():
            sources(item, refs)
    elif isinstance(value, list):
        for item in value:
            sources(item, refs)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sprint', type=Path, required=True)
    parser.add_argument('--runs', type=Path, nargs='+', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    bindings = {row['case_id']: row for row in json.loads((args.sprint / 'public-bindings-v1/diagnosis-bindings.json').read_text())
                if int(row['case_id'].split('-')[1]) <= 12}
    native_root = args.sprint / 'controlled-development-1/private'
    native = {}
    for alias in ('e00', 'e01', 'e02', 'e03', 'e04', 'e05', 'e06', 'e07', 'e10', 'e11'):
        facts = {}
        for kind in ('setup', 'hold'):
            path = native_root / alias / (kind + '.json')
            raw = path.read_bytes()
            rows = json.loads(raw)['checks']
            expected_type = 'max' if kind == 'setup' else 'min'
            matching = [row for row in rows if row['path_type'] == expected_type]
            worst = min(matching, key=lambda row: row['slack'])
            facts[kind] = {'rows': len(matching), 'worst': {key: worst[key] for key in ('startpoint', 'endpoint', 'slack', 'data_arrival_time', 'required_time')},
                           'source': str(path), 'sha256': hashlib.sha256(raw).hexdigest()}
        area = native_root / alias / 'area.rpt'
        facts['area'] = {'text': area.read_text(), 'source': str(area), 'sha256': hashlib.sha256(area.read_bytes()).hexdigest()}
        native[alias] = facts
    client = KernelClient('http://127.0.0.1:18700', timeout=10)
    cache = {}
    episodes = []
    for root in args.runs:
        for folder in sorted(root.iterdir()):
            if not folder.is_dir() or not folder.name.startswith('diag-'):
                continue
            case_id = folder.name[:7]
            assert case_id in bindings
            paths = list((folder / 'investigations').glob('*/state.json'))
            state = json.loads(paths[0].read_text()) if paths else None
            record = {'folder': str(folder), 'case_id': case_id, 'state': state.get('status') if state else 'needs_scope_or_no_state',
                      'automatic_checks': [], 'semantic_status': 'review_required'}
            if state:
                known = {e['evidence_id']: e for e in state['evidence']}
                claims = (state.get('answer') or {}).get('claims', [])
                record['automatic_checks'].append({'name': 'critical_citations_exist', 'passed': all(
                    claim['evidence_ids'] and all(eid in known for eid in claim['evidence_ids'])
                    for claim in claims if claim['kind'] in ('fact', 'comparison', 'causal'))})
                refs = {}
                for evidence in state['evidence']:
                    sources(evidence['content'], refs)
                verified = []
                for (run_id, artifact_id), expected in refs.items():
                    if (run_id, artifact_id) not in cache:
                        try:
                            location = client.artifact_locator(run_id, artifact_id)
                            original = hashlib.sha256(Path(location['path']).read_bytes()).hexdigest()
                            cache[(run_id, artifact_id)] = {'native_sha256': original, 'registered_sha256': location['sha256']}
                        except (KernelError, OSError) as error:
                            cache[(run_id, artifact_id)] = {'error': str(error)}
                    checked = cache[(run_id, artifact_id)]
                    passed = len(expected) == 1 and checked.get('native_sha256') == checked.get('registered_sha256') == next(iter(expected))
                    verified.append({'run_id': run_id, 'artifact_id': artifact_id, 'expected': sorted(expected), **checked, 'passed': passed})
                record['source_checks'] = verified
                record['automatic_checks'].append({'name': 'source_digests', 'passed': bool(verified) and all(row['passed'] for row in verified)})
                base_ids = bindings[case_id]['snapshots']
                allowed = set(base_ids)
                for ticket in state['pending_analyses']:
                    if ticket['parent_snapshot_id'] in allowed:
                        allowed.add(ticket['snapshot_id'])
                record['automatic_checks'].append({'name': 'evidence_scope', 'passed': all(e['scope'].get('snapshot_id') in allowed for e in state['evidence'])})
                record['answer'] = state.get('answer')
                record['seconds'] = state['active_seconds']
                record['checkpoint_sha256'] = hashlib.sha256(paths[0].read_bytes()).hexdigest()
            episodes.append(record)
    result = {'scope': 'development only; sealed references never read',
              'native_references': native, 'episodes': episodes,
              'grading': 'Automatic identity/source checks do not establish semantic success. Attach reviewer findings before claiming a pass.'}
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'episodes': len(episodes), 'source_failures': sum(not check['passed'] for row in episodes for check in row.get('source_checks', [])),
                      'semantic_status': 'review_required'}))


if __name__ == '__main__':
    main()
