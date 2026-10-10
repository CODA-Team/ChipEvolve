"""Accept one complete native campaign using its preserved source evidence."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess

from flow_native_baseline import FORMAL, now, write_json


def read(path):
    return json.loads(path.read_text())


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def audit(run):
    receipt = read(run / 'receipt.json')
    flow = run / 'source/flow'
    backup = flow / 'backup_dir/nangate45/aes'
    manifest = read(backup / 'campaign_manifest.json')
    checks = {}
    checks['normal_exit'] = receipt['status'] == 'completed' and receipt.get('exit_code') == 0
    checks['source_unchanged'] = receipt.get('source_changed') == []
    checks['physical_capture_finished'] = receipt.get('capture_exit_code') == 0
    checks['requested_full_campaign'] = manifest['iterations'] == 2 and manifest['runs'] == 3 and manifest['llm_enabled'] is True
    checks['predictor_requested'] = manifest['predictor'] == 'true'
    usage = read(backup / 'llm_usage_summary.json')
    events = [json.loads(line) for line in (backup / 'llm_usage_events.jsonl').read_text().splitlines()]
    responses = [event for event in events if event['event'] == 'response_received']
    checks['real_model_calls'] = len(responses) >= 4 and all(event.get('usage_available') for event in responses)
    checks['inter_iteration_model_calls'] = any(event.get('scope') == 'inter_iteration' and event.get('target_iteration') == 2 for event in responses)
    checks['ledger_complete'] = (usage['status'] == 'completed' and usage.get('pending_calls') == 0
                                 and usage.get('usage_complete') is True and usage.get('completed_iterations') == 2)
    review_path = run / 'model-decision-review.json'
    review = read(review_path) if review_path.is_file() else None
    checks['inter_iteration_decisions_reviewed'] = (isinstance(review, dict)
        and review.get('verified') is True and review.get('campaign_id') == manifest['campaign_id'])
    rounds = []
    reference_clocks = []
    for iteration in (1, 2):
        dump = backup / f'result_dump_{iteration}'
        completed = subprocess.run([str(FORMAL / '.venv/bin/python'), str(flow / 'driver_orchestration.py'),
                                    'validate-backup', '--directory', str(dump),
                                    '--manifest', str(backup / 'campaign_manifest.json'),
                                    '--iteration', str(iteration), '--runs', '3'],
                                   cwd=flow, capture_output=True, text=True)
        checks[f'round_{iteration}_canonical'] = completed.returncode == 0
        metrics = read(dump / f'metrics_final_iter{iteration}.json')
        valid = [row for row in metrics if (
            row.get('tns_source') == 'cp0_eval' and all(
                isinstance(row.get(key), (int, float)) and math.isfinite(row[key])
                for key in ('TNS_EVAL', 'power', 'ecp', 'wl')))]
        # Reuse the native gate: three attempted slots, at least two usable finals.
        checks[f'round_{iteration}_real_final_feedback'] = len(metrics) == 3 and len(valid) >= 2
        captured = read(run / f'iteration-results/iteration-{iteration}/manifest.json')
        artifacts = captured['artifacts']
        expected = {(row['run_id'], suffix) for row in valid for suffix in ('odb', 'def', 'v', 'spef', 'sdc', 'gds')}
        actual = {(entry['candidate_slot'], Path(entry['path']).suffix[1:]) for entry in artifacts}
        checks[f'round_{iteration}_physical_artifacts'] = expected <= actual and all(
            (run / entry['path']).is_file() and (run / entry['path']).stat().st_size == entry['size_bytes']
            and digest(run / entry['path']) == entry['sha256'] for entry in artifacts)
        cp0 = float((dump / 'cp0.txt').read_text())
        reference_clocks.append(cp0)
        stage_decisions = {}
        for stage in ('place', 'cts'):
            decision = read(dump / f'drp_{stage}_iter{iteration}.json')
            checks[f'round_{iteration}_{stage}_real_clone'] = decision['lineage_trusted_count'] >= 1
            checks[f'round_{iteration}_{stage}_llm_parameters'] = any(
                entry.get('origin') == 'llm' for entry in decision['stage_generated_provenance'])
            if iteration == 2:
                checks[f'round_2_{stage}_predictor_used'] = (
                    decision['effective_rank_key'] == 'promising_cost' and decision['scored_count'] == 3
                    and decision['fallback_reason'] is None)
            stage_decisions[stage] = {key: decision.get(key) for key in (
                'source_ids', 'victim_ids', 'stage_generated_params', 'effective_rank_key',
                'scored_count', 'fallback_reason', 'model_sha256', 'lineage_trusted_count')}
        rows = list(csv.DictReader((dump / f'input_batch_iter{iteration}.csv').open()))
        checks[f'round_{iteration}_three_executed_csv_rows'] = len(rows) == 3
        if iteration == 2:
            lifecycle = read(dump / 'candidate_lifecycle_iter2.json')
            csv_events = [event for event in lifecycle['events'] if event.get('stage') == 'csv_written']
            checks['next_csv_bound_to_model_pipeline'] = len(csv_events) == 3 and all(
                event.get('details', {}).get('csv_sha256') == digest(dump / 'input_batch_iter2.csv')
                for event in csv_events)
        rounds.append({'iteration': iteration, 'cp0_ns': cp0, 'metrics': metrics,
                       'valid_final_slots': [row['run_id'] for row in valid],
                       'invalid_final_slots': [row['run_id'] for row in metrics if row not in valid],
                       'drp': stage_decisions, 'canonical_check': completed.stdout + completed.stderr})
    checks['fixed_reference_clock'] = reference_clocks[0] > 0 and reference_clocks[0] == reference_clocks[1]
    baseline = next(row for row in rounds[0]['metrics'] if row['run_id'] == 1)
    power_budget = float(manifest['power_budget'])
    feasible = [dict(iteration=item['iteration'], **row) for item in rounds for row in item['metrics']
                if row['run_id'] in item['valid_final_slots']
                and row['power'] <= baseline['power'] * (1 + power_budget)]
    best = min(feasible, key=lambda row: row['TNS_EVAL']) if feasible else None
    checks['feasible_baseline_preserved'] = best is not None and best['TNS_EVAL'] <= baseline['TNS_EVAL']
    text = (run / 'campaign.log').read_text()
    observations = [line for line in text.splitlines() if re.search(
        r'dummy|fallback|bootstrap|numerical|failed|warning', line, re.I)]
    return {'accepted': all(checks.values()), 'audited_at': now(), 'campaign_id': manifest['campaign_id'],
            'checks': checks, 'receipt': receipt, 'usage': usage, 'rounds': rounds,
            'baseline': baseline, 'best_feasible_observed': best,
            'timing_improvement_observed': best is not None and best['TNS_EVAL'] < baseline['TNS_EVAL'],
            'benefit_proven_by_fair_evaluation': False, 'fallback_and_warning_observations': observations,
            'model_decision_review': review,
            'note': 'Execution acceptance and one-campaign QoR are separate from platform benefit evidence.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-root', type=Path, required=True)
    args = parser.parse_args()
    root = args.run_root.resolve()
    if read(root / 'receipt.json')['status'] == 'running':
        raise SystemExit('Campaign is still running; final acceptance is not available.')
    result = audit(root)
    write_json(root / 'p1-acceptance.json', result)
    print(json.dumps({'accepted': result['accepted'], 'failed_checks': [key for key, value in result['checks'].items() if not value]}))
    raise SystemExit(0 if result['accepted'] else 1)
