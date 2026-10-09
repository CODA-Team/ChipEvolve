"""Disclose clean-replay execution intervals overlapping formal model episodes.

Intervals cover registered EF run elapsed time, including queue/native lease wait
and overhead. They do not assert simultaneous native EDA or quantify slowdown.
"""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def collect(value, rows, source):
    if isinstance(value, dict):
        if all(isinstance(value.get(key), str) for key in ('run_id', 'started_at', 'ended_at')):
            start, end = datetime.fromisoformat(value['started_at']), datetime.fromisoformat(value['ended_at'])
            if end >= start:
                rows.setdefault(value['run_id'], {'run_id': value['run_id'], 'status': value.get('status'),
                    'started_at': start.isoformat(), 'ended_at': end.isoformat(), 'seconds': (end - start).total_seconds(),
                    'source': str(source), 'source_sha256': digest(source)})
        for child in value.values():
            collect(child, rows, source)
    elif isinstance(value, list):
        for child in value:
            collect(child, rows, source)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--formal', type=Path, required=True)
    parser.add_argument('--external-run-roots', type=Path, nargs='+', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit('Overlap records are immutable; choose a new output')
    runs = {}
    for root in args.external_run_roots:
        for source in sorted(root.rglob('*.json')):
            collect(json.loads(source.read_text()), runs, source)
    records = []
    for path in sorted((args.formal / 'receipts').glob('*.json')):
        episode = json.loads(path.read_text())
        if not episode.get('started_at') or episode.get('wall_seconds_used') is None:
            continue
        start = datetime.fromisoformat(episode['started_at'])
        end = start + timedelta(seconds=episode['wall_seconds_used'])
        overlap = []
        for row in runs.values():
            left = max(start, datetime.fromisoformat(row['started_at']))
            right = min(end, datetime.fromisoformat(row['ended_at']))
            if right > left:
                overlap.append({'external_run_id': row['run_id'], 'overlap_seconds': (right - left).total_seconds()})
        if overlap:
            records.append({'episode_id': episode['episode_id'], 'started_at': start.isoformat(),
                            'ended_at': end.isoformat(), 'receipt': str(path), 'receipt_sha256': digest(path),
                            'overlaps': overlap})
    result = {'audited_at': datetime.now(timezone.utc).isoformat(), 'program_sha256': digest(Path(__file__)),
              'external_registered_runs': list(runs.values()), 'affected_episode_count': len(records), 'episodes': records,
              'interpretation': 'Replay and measurements shared the host. EDA used one shared lease; waiting remains in each task deadline. Registered run intervals include wait/overhead, so overlap is a disclosure rather than proof of simultaneous native execution or measured slowdown.',
              'matrix_denominator_unchanged': True}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'external_runs': len(runs), 'affected_episodes': len(records)}))


if __name__ == '__main__':
    main()
