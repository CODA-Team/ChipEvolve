"""Prepare independent diagnosis review dossiers after predictions are committed.

This post-evaluation program is never called by the model runner. It extracts
reference timing directly from native OpenSTA JSON, retaining input identities,
raw files and all candidate predictions for a separate per-condition review.
It does not infer success from an answered state or prescribe a causal answer.
"""
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from score_formal import load_state


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def native_reference(sprint, snapshot):
    """Follow prepared public identity to independent raw oracle, without DF."""
    bindings = []
    for path in sprint.glob('controlled-*/public/*/binding.json'):
        value = json.loads(path.read_text())
        if value.get('snapshot_id') == snapshot:
            bindings.append((path, value))
    for path in (sprint / 'availability-v1').glob('*/binding.json'):
        value = json.loads(path.read_text())
        if value.get('snapshot_id') == snapshot:
            return {'snapshot_id': snapshot, 'availability_binding': value, 'binding_path': str(path),
                    'binding_sha256': digest(path),
                    'source_reference': native_reference(sprint, value['source_snapshot_id'])}
    if len(bindings) != 1:
        return {'snapshot_id': snapshot, 'native_reference_status': 'not_uniquely_located',
                'matches': [str(path) for path, _ in bindings]}
    path, binding = bindings[0]
    private = path.parents[2] / 'private' / binding['case_experiment']
    facts = {'snapshot_id': snapshot, 'binding_path': str(path), 'binding_sha256': digest(path),
             'physical_run_id': binding['physical_run_id'], 'input_identities': binding['native_inputs'],
             'native_reference_status': 'raw_oracle_files_located', 'checks': {}, 'files': {}}
    gold_path = private / 'gold.json'
    gold = json.loads(gold_path.read_text())
    facts['reference_manifest'] = {'path': str(gold_path), 'sha256': digest(gold_path)}
    for name, registered in gold['files'].items():
        raw = private / Path(name).name
        actual = digest(raw)
        facts['files'][name] = {'path': str(raw), 'actual_sha256': actual,
                               'registered_sha256': registered['sha256'], 'actual_size_bytes': raw.stat().st_size,
                               'registered_size_bytes': registered['bytes'],
                               'passed': actual == registered['sha256'] and raw.stat().st_size == registered['bytes']}
    for check, kind in (('setup', 'max'), ('hold', 'min')):
        raw = private / (check + '.json')
        values = json.loads(raw.read_text())['checks']
        matching = [row for row in values if row['path_type'] == kind]
        # Native OpenSTA JSON stores seconds, independently of the DF response unit.
        projected = [{**{key: row.get(key) for key in ('startpoint', 'endpoint', 'path_type', 'path_group')},
                      **{key + '_ns': row.get(key) * 1e9 if row.get(key) is not None else None
                         for key in ('slack', 'data_arrival_time', 'required_time')}} for row in matching]
        facts['checks'][check] = {'reported_count': len(matching), 'time_unit': 'ns',
                                 'worst_reported': min(projected, key=lambda row: row['slack_ns']) if projected else None,
                                 'reported_paths': projected,
                                 'coverage': 'Native -group_path_count 200/-endpoint_path_count 1 report; not exhaustive closure.'}
    return facts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sprint', type=Path, required=True)
    parser.add_argument('--formal', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--case', action='append', default=[])
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit('Review dossiers are immutable; choose a new output directory')
    matrix = json.loads((args.sprint / 'evaluation-v1/public/matrix.json').read_text())
    diagnosis = [row for row in matrix if row['kind'] == 'diagnosis']
    specs = {row['case_id']: row for row in json.loads((args.sprint / 'evaluation-v1/private/diagnosis-specs.json').read_text())}
    bindings = {row['case_id']: row for row in json.loads((args.sprint / 'public-bindings-v1/diagnosis-bindings.json').read_text())}
    receipts = {row['episode_id']: row for path in (args.formal / 'receipts').glob('*.json')
                for row in [json.loads(path.read_text())]}
    grouped = defaultdict(list)
    for row in diagnosis:
        if not args.case or row['case_id'] in args.case:
            grouped[row['case_id']].append(row)
    args.output.mkdir(parents=True)
    result = {'prepared_at': datetime.now(timezone.utc).isoformat(), 'program_sha256': digest(Path(__file__)),
              'ready': [], 'not_ready': [], 'policy': 'Native references opened only after the initial B/C/D/E predictions for both models have receipts. No implementation tuning.'}
    for case_id, planned in sorted(grouped.items()):
        initial = [row for row in planned if row['repeat'] == 0 and row['ablation'] is None]
        expected = {(model, arm) for model in ('codex', 'deepseek-flash') for arm in ('B', 'C', 'D', 'E')}
        if len(initial) != 8 or {(row['model'], row['arm']) for row in initial} != expected:
            raise ValueError('Initial prediction group must contain exactly two models and four arms: ' + case_id)
        missing = [row['episode_id'] for row in initial if row['episode_id'] not in receipts]
        if missing:
            result['not_ready'].append({'case_id': case_id, 'missing_initial_predictions': missing})
            continue
        snapshots = bindings[case_id]['snapshots']
        dossier = {'case_id': case_id, 'frozen_specification': specs[case_id], 'public_binding': bindings[case_id],
                   'native_references': [native_reference(args.sprint, sid) for sid in snapshots], 'episodes': [],
                   'semantic_grade': 'review_required', 'rubric': json.loads((args.sprint / 'evaluation-v1/public/scoring-rules.json').read_text())['diagnosis_rules']}
        for row in planned:
            receipt = receipts.get(row['episode_id'])
            if receipt is None:
                dossier['episodes'].append({**row, 'measurement_status': 'not_run'})
                continue
            folder = Path(receipt['folder'])
            state = load_state(folder, row['arm'])
            episode = {**row, 'receipt': receipt, 'state_status': state.get('status') if state else None,
                       'answer': state.get('answer') if state else None, 'evidence_summary': []}
            if state:
                for field in ('scopes', 'scope', 'hypotheses', 'missing_evidence', 'pending_analyses',
                              'handoff_packages', 'stop_reason', 'analyses_used', 'tool_calls_used', 'calls_used'):
                    if field in state:
                        episode[field] = state[field]
                for evidence in state.get('evidence', []):
                    episode['evidence_summary'].append({key: evidence[key] for key in
                        ('evidence_id', 'scope', 'operation', 'status', 'rationale', 'provenance', 'sha256') if key in evidence})
            dossier['episodes'].append(episode)
        target = args.output / (case_id + '.json')
        target.write_text(json.dumps(dossier, ensure_ascii=False, indent=2) + '\n')
        result['ready'].append({'case_id': case_id, 'path': str(target), 'sha256': digest(target),
                                'recorded_episodes': sum('receipt' in row for row in dossier['episodes'])})
    (args.output / 'summary.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'ready_cases': len(result['ready']), 'pending_cases': len(result['not_ready'])}))


if __name__ == '__main__':
    main()
