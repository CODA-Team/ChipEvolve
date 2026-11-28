"""Preserve terminal EF records and compare them after an owned service restart."""
import argparse
import hashlib
import json
from pathlib import Path

from openroad_platform_client import KernelClient


def capture(client, run_id):
    return {'run': client.run(run_id), 'artifacts': client.artifacts(run_id),
            'resources': client.resources(run_id),
            'logs': client.logs(run_id, max_bytes=65536)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=('before', 'after'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--lifecycle', type=Path, required=True)
    parser.add_argument('--kernel-url', default='http://127.0.0.1:18700')
    args = parser.parse_args()
    client = KernelClient(args.kernel_url)
    args.output.mkdir(parents=True, exist_ok=True)
    ids = [row['run_id'] for row in json.loads(args.lifecycle.read_text())['results']]
    ids += ['run-000b59ba68144a33bd2c4a3ea3d0da1b',
            'run-bff2197543cc4192aa559ce48c829fcf',
            'run-e0374d328e0a40bd937c1e3e25ab48a2']
    records = {run_id: capture(client, run_id) for run_id in ids}
    payload = json.dumps(records, indent=2, sort_keys=True) + '\n'
    target = args.output / (args.mode + '.json')
    if target.exists():
        raise SystemExit('Acceptance records are immutable; choose a new output folder')
    target.write_text(payload)
    if args.mode == 'after':
        before = json.loads((args.output / 'before.json').read_text())
        rows = {run_id: {key: records[run_id][key] == before[run_id][key]
                        for key in records[run_id]} for run_id in ids}
        passed = all(all(row.values()) for row in rows.values())
        result = {'passed': passed, 'checks': rows,
                  'before_sha256': hashlib.sha256((args.output/'before.json').read_bytes()).hexdigest(),
                  'after_sha256': hashlib.sha256(target.read_bytes()).hexdigest()}
        (args.output / 'summary.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result))
        return 0 if passed else 1
    print(json.dumps({'captured': len(records), 'health': client.health()}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
