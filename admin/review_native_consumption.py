"""Verify actual native stage logs against inherited final candidate configs."""
import argparse
import json
import math
import re
import subprocess
from pathlib import Path

from flow_native_baseline import digest, now, write_json


def stored_adjustments(executable, database, output):
    script = output.with_suffix('.tcl')
    script.write_text(f'read_db {{{database}}}\n' + '''foreach name {metal2 metal3 metal4 metal10} {
    set layer [[[ord::get_db] getTech] findLayer $name]
    puts "PERSISTED_LAYER name=$name adjustment=[$layer getLayerAdjustment]"
}
''')
    with output.open('w') as log:
        result = subprocess.run([str(executable), '-no_init', '-exit', str(script)],
                                stdout=log, stderr=log, check=False)
    if result.returncode != 0:
        raise RuntimeError('Read-only native database inspection failed: ' + str(output))
    return {name: float(value) for name, value in re.findall(
        r'^PERSISTED_LAYER name=(metal\d+) adjustment=([-+\d.eE]+)$',
        output.read_text(), re.MULTILINE)}


def review(run):
    flow = run / 'source/flow'
    backup = flow / 'backup_dir/nangate45/aes'
    manifest = json.loads((backup / 'campaign_manifest.json').read_text())
    evidence = {}
    observations = []
    receipt = json.loads((run / 'receipt.json').read_text())
    baseline = json.loads((Path(receipt['baseline']) / 'baseline/manifest.json').read_text())
    executable = Path(baseline['tools']['openroad']['path'])
    if digest(executable) != baseline['tools']['openroad']['sha256']:
        raise ValueError('OpenROAD executable differs from the frozen native reference.')
    inspection = run / 'parameter-consumption-evidence'
    inspection.mkdir(exist_ok=True)

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
                observation = {'iteration': iteration, 'slot': slot, 'scope': scope,
                                     'expected': expected, 'actual': actual, 'matched': matched,
                                     'log': str(log.relative_to(run)),
                                     'config': str(config_path.relative_to(run))}
                if scope == 'routing':
                    database = run / f'iteration-results/iteration-{iteration}/run_{slot}/6_final.odb'
                    output = inspection / f'final-iteration-{iteration}-slot-{slot}.log'
                    stored = stored_adjustments(executable, database, output)
                    stored_match = set(stored) == {'metal2', 'metal3', 'metal4', 'metal10'} and all(
                        math.isclose(stored[name], expected[index], abs_tol=1e-6)
                        for name, index in (('metal2', 0), ('metal3', 0), ('metal4', 1), ('metal10', 1)))
                    observation.update(stored_adjustments=stored, stored_matched=stored_match,
                                       matched=matched and stored_match)
                    for path in (database, output, output.with_suffix('.tcl')):
                        record(path)
                observations.append(observation)
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
