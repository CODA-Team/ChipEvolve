"""Save final physical artifacts before native A2 clears the next iteration."""
import hashlib
import argparse
import json
from pathlib import Path
import shutil
import time

RUN = Path(__file__).resolve().parents[1] / 'var/flow-agent/p1-native-20261010'
FLOW = RUN / 'source/flow'


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def main(run=RUN):
    flow = run / 'source/flow'
    captured = set()
    destination = run / 'iteration-results'
    destination.mkdir(exist_ok=True)
    while True:
        for iteration in (1, 2):
            if iteration in captured:
                continue
            backup = flow / f'backup_dir/nangate45/aes/result_dump_{iteration}'
            # Native backup starts only after route, CP0 evaluation and lifecycle finalization.
            if not (backup / f'input_batch_iter{iteration}.csv').is_file():
                continue
            target = destination / f'iteration-{iteration}'
            target.mkdir()
            manifest = []
            for number in (1, 2, 3):
                source = flow / f'results/nangate45/aes/run_{number}'
                for suffix in ('odb', 'def', 'v', 'spef', 'sdc', 'gds'):
                    path = source / f'6_final.{suffix}'
                    if not path.is_file():
                        continue
                    initial = digest(path)
                    output = target / f'run_{number}' / path.name
                    output.parent.mkdir(exist_ok=True)
                    shutil.copy2(path, output)
                    if initial != digest(output) or initial != digest(path):
                        raise RuntimeError('Physical result changed during capture: ' + str(path))
                    manifest.append({'candidate_slot': number, 'path': str(output.relative_to(run)),
                                     'native_source': str(path), 'sha256': initial,
                                     'size_bytes': output.stat().st_size})
            (target / 'manifest.json').write_text(json.dumps({
                'iteration': iteration, 'artifacts': manifest,
                'capture_boundary': str(backup / f'input_batch_iter{iteration}.csv'),
                'note': 'External observation only; algorithm and running source unchanged.',
            }, indent=2) + '\n')
            captured.add(iteration)
            print(json.dumps({'iteration': iteration, 'captured_files': len(manifest)}), flush=True)
        receipt = json.loads((run / 'receipt.json').read_text())
        if receipt['status'] != 'running':
            return
        time.sleep(0.5)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-root', type=Path, default=RUN)
    main(parser.parse_args().run_root.resolve())
