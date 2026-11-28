"""Retain actual component-use receipts, skill inputs and model identities.

Component calls establish execution of a capability, not answer correctness or
incremental value. Ambiguous scope can legitimately stop before model invocation.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from score_formal import load_state, model_usage


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from strings(child)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--formal', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit('Component-use records are immutable; choose a new output')
    rows = []
    for path in sorted((args.formal / 'receipts').glob('*.json')):
        receipt = json.loads(path.read_text())
        folder = Path(receipt['folder'])
        state = load_state(folder, receipt['arm'])
        row = {'episode_id': receipt['episode_id'], 'receipt': str(path), 'receipt_sha256': digest(path),
               'arm': receipt['arm'], 'model': receipt['model'], 'measurement_status': receipt['status'],
               'state_present': state is not None, 'state_status': state.get('status') if state else None,
               'use_checks': [], 'model_receipts': model_usage(folder)}
        if state is not None and receipt['arm'] in ('A', 'B', 'C'):
            evidence = state.get('evidence', [])
            row['operation_kinds'] = dict(Counter(e['operation']['kind'] for e in evidence))
            row['operation_outcomes'] = dict(Counter(e.get('status') for e in evidence))
            row['operations'] = [{'evidence_id': e['evidence_id'], 'kind': e['operation']['kind'],
                                  'path': e['operation'].get('path'), 'snapshot_id': e['operation'].get('snapshot_id'),
                                  'status': e.get('status'), 'seconds': e.get('seconds')}
                                 for e in evidence]
            allowed = {'file', 'native', 'evidence'} if receipt['arm'] == 'A' else {
                'file', 'sql', 'native', 'evidence'} if receipt['arm'] == 'B' else {
                'read', 'analysis', 'wait', 'execution', 'evidence'}
            row['use_checks'].append({'name': 'only_assigned_operation_family',
                                      'passed': all(e['operation']['kind'] in allowed for e in evidence if e.get('status') == 'succeeded')})
            row['rejected_unavailable_operations'] = [{'evidence_id': e['evidence_id'], 'kind': e['operation']['kind'],
                                                      'status': e.get('status'), 'error': e.get('error')}
                                                     for e in evidence if e['operation']['kind'] not in allowed]
            row['data_interface_successful_reads'] = sum(e['operation']['kind'] == 'read' and e.get('status') == 'succeeded' for e in evidence)
            row['analysis_count'] = state.get('analyses_used')
        elif state is not None:
            inputs = []
            for model_input in [*folder.glob('host-traces/*/prompt.txt'), *folder.glob('model-traces/*/prompt.txt'),
                                *folder.glob('model-traces/*/request.json')]:
                if model_input.suffix == '.json':
                    text = '\n'.join(strings(json.loads(model_input.read_text())))
                else:
                    text = model_input.read_text()
                inputs.append((model_input, text))
            skills = []
            for skill in state.get('skills', []):
                content = skill['content']
                matches = [str(source) for source, text in inputs if content in text]
                skills.append({'name': skill['name'], 'version': skill['version'], 'sha256': skill['sha256'],
                               'content_digest_passed': hashlib.sha256(content.encode()).hexdigest() == skill['sha256'],
                               'runtime_inputs_containing_skill': matches})
            row['skills'] = skills
            row['runtime_input_files'] = [{'path': str(source), 'sha256': digest(source)} for source, _ in inputs]
            row['decisions'] = dict(Counter(item['action'] for item in state.get('decisions', [])))
            row['analysis_tickets'] = state.get('pending_analyses', [])
            row['judgments'] = state.get('judgments', [])
            row['evidence_count'] = len(state.get('evidence', []))
            row['use_checks'].append({'name': 'skill_content_digests', 'passed': all(s['content_digest_passed'] for s in skills)})
            if receipt.get('ablation') == 'no-skills':
                row['use_checks'].append({'name': 'no_skills_ablation', 'passed': not skills})
            elif inputs:
                row['use_checks'].append({'name': 'loaded_skills_entered_runtime',
                                          'passed': bool(skills) and all(s['runtime_inputs_containing_skill'] for s in skills)})
            if receipt.get('ablation') == 'no-supplement':
                row['use_checks'].append({'name': 'no_supplement_ablation', 'passed': not row['analysis_tickets']})
            row['jev_actual_receipt_count'] = sum(not r.get('receipt_missing') and r.get('trace_family') == 'judgment-traces'
                                                for r in row['model_receipts'])
            row['jev_advice_outcomes'] = dict(Counter(item['status'] for item in row['judgments']))
            row['jev_enabled_and_attempted'] = receipt['arm'] == 'E' and bool(row['judgments'])
            row['jev_succeeded_or_fell_back'] = receipt['arm'] == 'E' and any(item['status'] in ('available', 'fallback') for item in row['judgments'])
        rows.append(row)
    summary = {'audited_at': datetime.now(timezone.utc).isoformat(), 'program_sha256': digest(Path(__file__)),
               'episode_count': len(rows),
               'failed_use_checks': [{'episode_id': row['episode_id'], 'check': check['name']}
                                     for row in rows for check in row['use_checks'] if not check['passed']],
               'receipt_model_names': dict(Counter(str(r.get('model')) for row in rows for r in row['model_receipts'] if r.get('model'))),
               'model_identity_basis': {'codex': 'Explicit CLI model argument; receipt repeats the configured model, not an independent provider identity attestation.',
                                        'deepseek-flash': 'Provider response model field retained in actual API receipt.',
                                        'jev': 'Provider/model identity and usage checked in JEV response.'},
               'missing_model_receipts': sum(bool(r.get('receipt_missing')) for row in rows for r in row['model_receipts']),
               'note': 'Scope clarification or early transport failure can stop before model/skill/EDA use. Actual calls do not establish semantic success.'}
    args.output.mkdir(parents=True)
    (args.output / 'records.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n')
    (args.output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({key: summary[key] for key in ('episode_count', 'failed_use_checks', 'receipt_model_names', 'missing_model_receipts')}))


if __name__ == '__main__':
    main()
