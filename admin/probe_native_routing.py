"""Load a preserved real AES database and exercise the native routing setters."""
import argparse
import json
import subprocess
from pathlib import Path

from flow_native_baseline import FORMAL, digest, now, write_json


def probe(reference, output):
    if output.exists():
        raise ValueError('Use a fresh probe directory.')
    receipt = json.loads((reference / 'receipt.json').read_text())
    if receipt['status'] == 'running' or 'capture_exit_code' not in receipt:
        raise ValueError('Wait for the native campaign and capture to finish.')
    artifacts = json.loads((reference / 'iteration-results/iteration-1/manifest.json').read_text())
    entry = next(row for row in artifacts['artifacts']
                 if row['candidate_slot'] == 1 and row['path'].endswith('.odb'))
    database = reference / entry['path']
    if digest(database) != entry['sha256']:
        raise ValueError('Preserved AES database hash differs from capture.')
    baseline = json.loads((Path(receipt['baseline']) / 'baseline/manifest.json').read_text())
    executable = Path(baseline['tools']['openroad']['path'])
    if digest(executable) != baseline['tools']['openroad']['sha256']:
        raise ValueError('OpenROAD executable differs from the native reference.')
    output.mkdir(parents=True)
    script = output / 'probe.tcl'
    hooks = FORMAL / 'flow/designs/nangate45/aes'
    script.write_text(f'read_db {{{database}}}\n' + '''set ::env(MAX_ROUTING_LAYER) metal10
set ::env(MIN_ROUTING_LAYER) metal2
set ::env(MIN_CLK_ROUTING_LAYER) metal3
set ::env(FLOORPLAN_PIN_LAYER_ADJUST) 0.41
set ::env(FLOORPLAN_ABOVE_LAYER_ADJUST) 0.27
set ::env(PIN_LAYER_ADJUST) 0.63
set ::env(ABOVE_LAYER_ADJUST) 0.36
proc observed_setter {command code result operation} {
    puts "NATIVE_SETTER command={$command} code=$code"
}
trace add execution set_global_routing_layer_adjustment leave observed_setter
''' + f'source {{{hooks / "fastroute_floorplan.tcl"}}}\n'
        + f'source {{{hooks / "fastroute_routing.tcl"}}}\n')
    command = [str(executable), '-exit', str(script)]
    with (output / 'openroad.log').open('x') as log:
        result = subprocess.run(command, stdout=log, stderr=log, check=False)
    text = (output / 'openroad.log').read_text()
    expected = [('metal2-metal3', '.41'), ('metal4-metal10', '.27'),
                ('metal2-metal3', '.63'), ('metal4-metal10', '.36')]
    verified = result.returncode == 0 and all(
        f'NATIVE_SETTER command={{set_global_routing_layer_adjustment {layers} 0{value}}} code=0'
        in text for layers, value in expected)
    sources = [database, executable, script, output / 'openroad.log',
               hooks / 'fastroute_floorplan.tcl', hooks / 'fastroute_routing.tcl']
    write_json(output / 'receipt.json', {
        'verified': verified, 'finished_at': now(), 'command': command,
        'exit_code': result.returncode,
        'files': {str(path): digest(path) for path in sources},
        'scope': 'Real AES ODB and real OpenROAD API; full optimization is verified separately.'})
    return verified


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    verified = probe(args.reference.resolve(), args.output.resolve())
    print(json.dumps({'verified': verified, 'output': str(args.output)}))
    raise SystemExit(0 if verified else 1)
