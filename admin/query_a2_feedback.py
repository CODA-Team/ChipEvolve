"""Verify persisted evaluator facts using the installed Data Interface SDK."""
import argparse
import hashlib
import json
import math
from pathlib import Path

from eda_ai_client import EdaAiClient
from flow_native_baseline import write_json

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-url', required=True)
    parser.add_argument('--kernel-url', required=True)
    parser.add_argument('--binding', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    binding = json.loads(args.binding.read_text())
    client = EdaAiClient(data_url=args.data_url, kernel_url=args.kernel_url)
    response = client.get_metrics(snapshot_id=binding['snapshot_id'])
    rows = {row['name']: row for row in response['data']['metrics']}
    expected = {'TNS': binding['measured']['observations']['tns'],
                'WNS': binding['measured']['observations']['wns'],
                'POWER_TOTAL': binding['measured']['observations']['power']}
    for name, value in expected.items():
        row = rows[name]
        if (row['status'] != 'available' or row['unit'] != value['unit']
                or not math.isclose(row['value'], value['value'], abs_tol=1e-9)
                or not row['evidence']):
            raise RuntimeError('SDK feedback differs from measured evaluator output: ' + name)
    metadata = binding['metadata_copy']
    raw = client.artifact_bytes(binding['producer_run_id'], metadata['artifact_id'])
    if hashlib.sha256(raw).hexdigest() != binding['metadata']['sha256']:
        raise RuntimeError('SDK metadata bytes differ from the actual evaluator artifact')
    source = json.loads(raw)
    if source['evaluation'] != binding['measured']['evaluation'] or source['parasitic_mode'] != 'spef':
        raise RuntimeError('SDK feedback lost its fixed CP0 or real SPEF condition')
    write_json(args.output, {'accepted': True, 'metrics': response,
                            'evaluation': source['evaluation'],
                            'parasitic_mode': source['parasitic_mode'],
                            'source_metadata': metadata})
    print(json.dumps({'accepted': True, 'snapshot_id': binding['snapshot_id']}))
