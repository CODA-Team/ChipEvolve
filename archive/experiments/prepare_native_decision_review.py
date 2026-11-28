"""Assemble real model decisions and incoming batch evidence for manual review."""
import argparse
import csv
import json
from pathlib import Path

from flow_native_baseline import digest, now, write_json


def prepare(run, output):
    backup = run / 'source/flow/backup_dir/nangate45/aes'
    campaign = json.loads((backup / 'campaign_manifest.json').read_text())
    events = [json.loads(line) for line in (backup / 'llm_usage_events.jsonl').read_text().splitlines()]
    received = [row for row in events if row['event'] == 'response_received'
                and row.get('scope') == 'inter_iteration' and row.get('target_iteration') == 2]
    audits = {}
    for path in (run / 'model-audit').glob('*.json'):
        value = json.loads(path.read_text())
        audits.setdefault(value['thread_id'], []).append((path, value))
    responses = []
    for event in received:
        matches = audits[event['request_id']]
        if len(matches) != 1:
            raise ValueError('A model response has ambiguous audit evidence.')
        path, value = matches[0]
        responses.append({'operation': event['operation'], 'call_id': event['call_id'],
                          'request_id': event['request_id'], 'path': str(path.relative_to(run)),
                          'sha256': digest(path), 'content': value['content'],
                          'tool_calls': value['tool_calls']})
    evidence_root = run / 'decision-review-evidence'
    files = {path.name: {'path': str(path.relative_to(run)), 'sha256': digest(path)}
             for path in evidence_root.iterdir() if path.is_file()}
    lifecycle = json.loads((evidence_root / 'incoming-lifecycle.json').read_text())
    incoming = evidence_root / 'incoming-batch.csv'
    review = {'verified': False, 'campaign_id': campaign['campaign_id'], 'prepared_at': now(),
              'scope': 'Review actual responses, selection, incoming CSV and generated configs before signing.',
              'manual_findings': [], 'responses': responses, 'evidence_files': files,
              'incoming_csv_sha256': digest(incoming),
              'incoming_rows': list(csv.DictReader(incoming.open())),
              'csv_events': [row for row in lifecycle['events'] if row['stage'] == 'csv_written'],
              'selected_events': [row for row in lifecycle['events'] if row['stage'] == 'agent2_selected']}
    write_json(output, review)
    return {'responses': len(responses), 'evidence_files': len(files), 'output': str(output)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit('Preserve the existing review; choose a fresh output file.')
    print(json.dumps(prepare(args.run_root.resolve(), args.output.resolve())))
