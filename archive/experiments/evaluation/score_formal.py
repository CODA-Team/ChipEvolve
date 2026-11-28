"""Score frozen fact references and retain diagnosis cases for explicit review.

This scoring program does not run models, alter prompts or change implementation.
Diagnosis success always requires a separate source-grounded reviewer record.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from audit_commands import audit
from scoring import score


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_state(folder, arm):
    paths = list((folder / 'investigations').glob('*/state.json')) if arm in ('D', 'E') else [folder / 'state.json']
    return json.loads(paths[0].read_text()) if len(paths) == 1 and paths[0].is_file() else None


def model_usage(folder):
    paths = set(folder.glob('model-traces/*/receipt.json')) | set(folder.glob('host-traces/*/receipt.json'))
    paths |= set(folder.glob('judgment-traces/*/receipt.json'))
    if (folder / 'model-receipt.json').is_file():
        paths.add(folder / 'model-receipt.json')
    rows = []
    for path in sorted(paths):
        receipt = json.loads(path.read_text())
        rows.append({'path': str(path), 'sha256': digest(path), 'model': receipt.get('model'),
                     'usage': receipt.get('usage', {}), 'actual_usd': receipt.get('actual_usd'),
                     'quoted_usage_usd': receipt.get('quoted_usage_usd'), 'cost_basis': receipt.get('cost_basis'),
                     'trace_family': path.parent.parent.name,
                     'reservation': receipt.get('reservation'), 'seconds': receipt.get('seconds'),
                     'billing': receipt.get('billing'), 'timed_out': receipt.get('timed_out')})
    for family in ('model-traces', 'host-traces', 'judgment-traces'):
        for trace in sorted((folder / family).glob('*')):
            if not trace.is_dir() or (trace / 'receipt.json').is_file():
                continue
            failure_path = trace / 'failure.json'
            failure = json.loads(failure_path.read_text()) if failure_path.is_file() else {}
            rows.append({'path': str(trace), 'trace_family': family, 'receipt_missing': True,
                         'usage': None, 'actual_usd': None, 'reservation': failure.get('reservation'),
                         'failure': failure, 'cost_status': 'unknown; retain ledger reservation where present'})
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sprint', type=Path, required=True)
    parser.add_argument('--formal', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    matrix_path = args.sprint / 'evaluation-v1/public/matrix.json'
    matrix = json.loads(matrix_path.read_text())
    fact_gold = {}
    for design in ('ariane', 'mempool_group', 'nvdla_c'):
        path = args.sprint / ('evaluation-v1/private/' + design + '.gold.json')
        values = json.loads(path.read_text())
        values = values.get('gold', values)
        fact_gold.update({design + ':' + key: value for key, value in values.items()})
    receipts = {row['episode_id']: row for path in (args.formal / 'receipts').glob('*.json')
                for row in [json.loads(path.read_text())]}
    records = []
    for planned in matrix:
        episode_id = planned['episode_id']
        receipt = receipts.get(episode_id)
        record = {**planned, 'measurement_status': receipt['status'] if receipt else 'not_run',
                  'grade': 'not_run' if receipt is None else 'review_required',
                  'correctness_passed': False, 'formal_passed': False}
        if receipt:
            folder = Path(receipt['folder'])
            state = load_state(folder, planned['arm'])
            result_path = folder / 'result.json'
            cli_result = json.loads(result_path.read_text()) if result_path.is_file() else None
            record.update(folder=str(folder), wall_seconds_used=receipt.get('wall_seconds_used'),
                          cleanup_seconds=receipt.get('cleanup_seconds'), exit_code=receipt.get('exit_code'),
                          model_receipts=model_usage(folder), state_status=state.get('status') if state else None,
                          answer=state.get('answer') if state else None,
                          calls_used=(state.get('tool_calls_used', state.get('calls_used')) if state else None),
                          read_bytes_used=(state.get('read_bytes_used') if state else None),
                          analyses_used=(state.get('analyses_used') if state else None))
            record['cli_result'] = cli_result
            if planned['case_id'] in fact_gold:
                if record['answer'] is None:
                    record.update(grade='failed', failure_reason='no committed answer')
                else:
                    correctness = score(record['answer'], fact_gold[planned['case_id']])
                    eligible = (receipt['status'] == 'completed' and not receipt.get('timed_out', False)
                                and receipt.get('wall_seconds_used', float('inf')) <= planned['wall_seconds'])
                    record.update(correctness=correctness, correctness_passed=correctness['passed'],
                                  formal_passed=correctness['passed'] and eligible,
                                  grade='passed' if correctness['passed'] and eligible else 'failed')
            elif cli_result and cli_result.get('status') == 'needs_scope':
                record.update(grade='review_required', clarification_returned=True)
            elif record['answer'] is None and not (state and state.get('handoff_packages')):
                record.update(grade='failed', failure_reason='no committed answer or handoff; needs-scope cases require explicit review')
        records.append(record)
    groups = defaultdict(list)
    for row in records:
        groups[(row['kind'], row['model'], row['arm'], row['repeat'], row['ablation'])].append(row)
    summaries = []
    for (kind, model, arm, repeat, ablation), rows in sorted(groups.items(), key=lambda item: str(item[0])):
        summaries.append({'kind': kind, 'model': model, 'arm': arm, 'repeat': repeat, 'ablation': ablation,
                          'denominator': len(rows), 'grades': dict(Counter(row['grade'] for row in rows)),
                          'measurement_status': dict(Counter(row['measurement_status'] for row in rows)),
                          'wall_seconds_total': sum(row.get('wall_seconds_used') or 0 for row in rows),
                          'formal_passed': sum(row['formal_passed'] for row in rows)})
    command_audit = audit(args.formal / 'episodes')
    (args.output / 'command-audit.json').write_text(json.dumps(command_audit, ensure_ascii=False, indent=2) + '\n')
    result = {'scored_at': datetime.now(timezone.utc).isoformat(), 'denominator': len(matrix),
              'retained_matrix_sha256': digest(matrix_path), 'recorded_receipts': len(receipts),
              'scorer_sha256': digest(Path(__file__)), 'groups': summaries,
              'diagnosis_review': 'Explicit per-condition source-grounded review still required; no answered-equals-pass rule.',
              'scores_provisional_until_source_and_command_review': True,
              'command_review': 'Flagged commands require adjudication; identity/source receipts are checked separately.',
              'engineering_pass_does_not_prove_business_effect': True}
    (args.output / 'records.json').write_text(json.dumps(records, ensure_ascii=False, indent=2) + '\n')
    (args.output / 'summary.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'denominator': len(matrix), 'recorded': len(receipts),
                      'fact_passed': sum(r['formal_passed'] for r in records),
                      'flagged_command_episodes': command_audit['flagged_episodes']}))


if __name__ == '__main__':
    main()
