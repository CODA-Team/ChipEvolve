"""Accept one complete native campaign using its preserved source evidence."""
import argparse
import csv
import hashlib
import json
import math
import re
import subprocess
from pathlib import Path

from flow_native_baseline import FORMAL, now, write_json


def read(path):
    return json.loads(path.read_text())


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def audit_model_ledger(flow, manifest, usage):
    """Recompute the native ledger without equating failed-call cost with lost events."""
    script = ('import json,sys; from pathlib import Path; '
              'from llm_usage import build_summary,load_events; '
              'm=json.loads(Path(sys.argv[1]).read_text()); '
              'u=json.loads(Path(sys.argv[2]).read_text()); '
              'print(json.dumps(build_summary(load_events(Path(sys.argv[3])), '
              'campaign_id=m["campaign_id"],llm_enabled=m["llm_enabled"], '
              'status=u["status"],exit_code=u["exit_code"], '
              'completed_iterations=u["completed_iterations"])))')
    backup = flow / 'backup_dir/nangate45/aes'
    result = subprocess.run([str(FORMAL / '.venv/bin/python'), '-c', script,
                             str(backup / 'campaign_manifest.json'),
                             str(backup / 'llm_usage_summary.json'),
                             str(backup / 'llm_usage_events.jsonl')],
                            cwd=flow, capture_output=True, text=True, check=False)
    if result.returncode:
        return {'complete': False, 'cost_complete': False, 'error': result.stderr}
    recomputed = json.loads(result.stdout)
    matching = all(usage.get(key) == value for key, value in recomputed.items()
                   if key != 'generated_utc')
    complete = (matching and usage.get('campaign_id') == manifest['campaign_id']
                and usage['status'] == 'completed' and usage.get('exit_code') == 0
                and usage.get('completed_iterations') == 2
                and usage.get('pending_calls') == 0
                and usage.get('successful_missing_usage') == 0
                and usage.get('successful_inconsistent_usage') == 0)
    return {'complete': complete, 'summary_matches_events': matching,
            'cost_complete': recomputed['usage_complete'],
            'known_total_tokens': recomputed['known_total_tokens'],
            'total_tokens': recomputed['total_tokens'],
            'failed_unknown_usage': recomputed['failed_unknown_usage'],
            'note': 'Terminal failures remain recorded. Unknown cost precludes exact cost comparisons.'}


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
    consumption_path = run / 'parameter-consumption-review.json'
    consumption = read(consumption_path) if consumption_path.is_file() else None
    checks['physical_parameter_consumption'] = (isinstance(consumption, dict)
        and consumption.get('verified') is True
        and consumption.get('campaign_id') == manifest['campaign_id'])
    checks['parameter_consumption_evidence_intact'] = (
        checks['physical_parameter_consumption']
        and bool(consumption.get('evidence'))
        and all((run / entry['path']).is_file()
                and digest(run / entry['path']) == entry['sha256']
                for entry in consumption['evidence'].values()))
    usage = read(backup / 'llm_usage_summary.json')
    events = [json.loads(line) for line in (backup / 'llm_usage_events.jsonl').read_text().splitlines()]
    responses = [event for event in events if event['event'] == 'response_received']
    checks['real_model_calls'] = len(responses) >= 4 and all(event.get('usage_available') for event in responses)
    checks['inter_iteration_model_calls'] = any(event.get('scope') == 'inter_iteration' and event.get('target_iteration') == 2 for event in responses)
    ledger = audit_model_ledger(flow, manifest, usage)
    checks['ledger_complete'] = ledger['complete']
    review_path = run / 'model-decision-review.json'
    review = read(review_path) if review_path.is_file() else None
    checks['inter_iteration_decisions_reviewed'] = (isinstance(review, dict)
        and review.get('verified') is True and review.get('campaign_id') == manifest['campaign_id'])
    checks['review_evidence_intact'] = (checks['inter_iteration_decisions_reviewed']
        and bool(review.get('evidence_files')) and bool(review.get('responses'))
        and all((run / entry['path']).is_file()
                and digest(run / entry['path']) == entry['sha256']
                for entry in (*review['evidence_files'].values(), *review['responses'])))
    rounds = []
    reference_clocks = []
    for iteration in (1, 2):
        dump = backup / f'result_dump_{iteration}'
        completed = subprocess.run([str(FORMAL / '.venv/bin/python'), str(flow / 'driver_orchestration.py'),
                                    'validate-backup', '--directory', str(dump),
                                    '--manifest', str(backup / 'campaign_manifest.json'),
                                    '--iteration', str(iteration), '--runs', '3'],
                                   cwd=flow, capture_output=True, text=True, check=False)
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
            direct_llm = any(entry.get('origin') == 'llm'
                             for entry in decision['stage_generated_provenance'])
            reviewed_selection = (checks['review_evidence_intact'] and any(
                entry.get('verified') is True and entry.get('iteration') == iteration
                and entry.get('stage') == stage
                and entry.get('decision_sha256') == digest(dump / f'drp_{stage}_iter{iteration}.json')
                and entry.get('selected_parameters') == decision['stage_generated_params']
                for entry in review.get('stage_model_decisions', [])))
            checks[f'round_{iteration}_{stage}_model_decision_effective'] = (
                direct_llm or reviewed_selection)
            if iteration == 2:
                checks[f'round_2_{stage}_predictor_used'] = (
                    decision['effective_rank_key'] == 'promising_cost' and decision['scored_count'] == 3
                    and decision['fallback_reason'] is None)
            stage_decisions[stage] = {key: decision.get(key) for key in (
                'source_ids', 'victim_ids', 'stage_generated_params', 'effective_rank_key',
                'scored_count', 'fallback_reason', 'model_sha256', 'lineage_trusted_count')}
            stage_decisions[stage]['direct_llm_parameters_selected'] = direct_llm
            stage_decisions[stage]['model_selection_reviewed'] = reviewed_selection
        rows = list(csv.DictReader((dump / f'input_batch_iter{iteration}.csv').open()))
        checks[f'round_{iteration}_three_executed_csv_rows'] = len(rows) == 3
        if iteration == 2:
            lifecycle = read(dump / 'candidate_lifecycle_iter2.json')
            csv_events = [event for event in lifecycle['events'] if event.get('stage') == 'csv_written']
            checks['next_csv_bound_to_model_pipeline'] = len(csv_events) == 3 and all(
                event.get('details', {}).get('csv_sha256') == digest(dump / 'input_batch_iter2.csv')
                for event in csv_events)
            checks['review_matches_executed_next_csv'] = (review is not None
                and review.get('incoming_csv_sha256') == digest(dump / 'input_batch_iter2.csv'))
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
        r'dummy|fallback|bootstrap|numerical|failed|warning', line, re.IGNORECASE)]
    return {'accepted': all(checks.values()), 'audited_at': now(), 'campaign_id': manifest['campaign_id'],
            'checks': checks, 'receipt': receipt, 'usage': usage, 'model_ledger_audit': ledger,
            'model_cost_complete': ledger['cost_complete'], 'rounds': rounds,
            'baseline': baseline, 'best_feasible_observed': best,
            'timing_improvement_observed': best is not None and best['TNS_EVAL'] < baseline['TNS_EVAL'],
            'benefit_proven_by_fair_evaluation': False, 'fallback_and_warning_observations': observations,
            'model_decision_review': review,
            'parameter_consumption_review': consumption,
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
