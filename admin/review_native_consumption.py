"""Verify actual native stage logs against inherited final candidate configs."""
import argparse
import json
import math
import re
from pathlib import Path

from flow_native_baseline import digest, now, write_json


def review(run):
    flow = run / 'source/flow'
    backup = flow / 'backup_dir/nangate45/aes'
    manifest = json.loads((backup / 'campaign_manifest.json').read_text())
    evidence = {}
    observations = []

    def record(path):
        name = str(path.relative_to(run))
        evidence[name] = {'path': name, 'sha256': digest(path)}

    for name in ('designs/nangate45/aes/config.mk',
                 'designs/nangate45/aes/fastroute_floorplan.tcl',
                 'designs/nangate45/aes/fastroute_routing.tcl',
                 'scripts/floorplan.tcl', 'scripts/global_route.tcl', 'scripts/cts.tcl'):
        record(flow / name)
    for iteration in (1, 2):
        dump = backup / f'result_dump_{iteration}'
        metrics_path = dump / f'metrics_final_iter{iteration}.json'
        record(metrics_path)
        metrics = json.loads(metrics_path.read_text())
        for row in metrics:
            if row.get('tns_source') != 'cp0_eval':
                continue
            slot = row['run_id']
            config_path = dump / f'config_{slot}.mk'
            record(config_path)
            parameters = {key: float(value) for key, value in re.findall(
                r'^export\s+(\w+)\s*=\s*([-+\d.eE]+)\s*$',
                config_path.read_text(), re.MULTILINE)}
            for scope, filename, names in (
                ('floorplan', '2_1_floorplan.log',
                 ('FLOORPLAN_PIN_LAYER_ADJUST', 'FLOORPLAN_ABOVE_LAYER_ADJUST')),
                ('routing', '5_1_grt.log', ('PIN_LAYER_ADJUST', 'ABOVE_LAYER_ADJUST')),
                ('cts', '4_1_cts.log', ('CTS_CLUSTER_SIZE', 'CTS_CLUSTER_DIAMETER')),
            ):
                log = dump / f'logs_dump/aes/run_{slot}' / filename
                record(log)
                text = log.read_text()
                if scope == 'cts':
                    command = re.search(r'^clock_tree_synthesis\s+(.+)$', text, re.MULTILINE)
                    found = [re.search(rf'{flag}\s+([-+\d.eE]+)', command[1])
                             if command else None for flag in (
                                 '-sink_clustering_size', '-sink_clustering_max_diameter')]
                    actual = [float(match[1]) for match in found] if all(found) else []
                else:
                    found = re.findall(
                        rf'^A2_LAYER_ADJUST scope={scope} pin=([-+\d.eE]+) above=([-+\d.eE]+)$',
                        text, re.MULTILINE)
                    actual = list(map(float, found[-1])) if len(found) == 1 else []
                expected = [parameters[name] for name in names]
                matched = len(actual) == 2 and all(math.isclose(a, b, abs_tol=1e-9)
                                                   for a, b in zip(actual, expected))
                observations.append({'iteration': iteration, 'slot': slot, 'scope': scope,
                                     'expected': expected, 'actual': actual, 'matched': matched,
                                     'log': str(log.relative_to(run)),
                                     'config': str(config_path.relative_to(run))})
    return {'verified': len(observations) >= 12 and all(row['matched'] for row in observations),
            'campaign_id': manifest['campaign_id'], 'reviewed_at': now(),
            'scope': 'Actual tool logs and config after native checkpoint inheritance, both rounds.',
            'evidence': evidence, 'observations': observations}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-root', type=Path, required=True)
    args = parser.parse_args()
    root = args.run_root.resolve()
    receipt = json.loads((root / 'receipt.json').read_text())
    if receipt['status'] == 'running' or 'capture_exit_code' not in receipt:
        raise SystemExit('Wait for the campaign and artifact capture to finish.')
    result = review(root)
    write_json(root / 'parameter-consumption-review.json', result)
    print(json.dumps({'verified': result['verified'], 'observations': len(result['observations']),
                      'mismatches': [row for row in result['observations'] if not row['matched']]}))
    raise SystemExit(0 if result['verified'] else 1)
