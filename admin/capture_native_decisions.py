"""Preserve the incoming batch before native DRP mutates its configurations."""
import argparse
import json
import re
import shutil
import time
from pathlib import Path

from flow_native_baseline import digest, now, write_json


def capture(run):
    flow = run / 'source/flow'
    design = flow / 'designs/nangate45/aes'
    target = run / 'decision-review-evidence'
    if target.exists():
        raise ValueError('Decision capture already exists.')
    while True:
        text = (run / 'campaign.log').read_text()
        marker = re.search(r'ITERATION 2 of 2', text)
        if marker and '>>> Phase 1: Running PLACEMENT stage...' in text[marker.end():]:
            target.mkdir()
            sources = {
                'incoming-lifecycle.json': flow / 'tmp/candidate_lifecycle_iter2.json',
                'incoming-batch.csv': design / 'nangate45_aes.csv',
                'incoming-optimization-state.json': design / 'optimization_state.json',
            }
            for slot in (1, 2, 3):
                sources[f'incoming-config-{slot}.mk'] = design / f'config_{slot}.mk'
                sources[f'incoming-constraint-{slot}.sdc'] = design / f'constraint_{slot}.sdc'
            evidence = {}
            for name, source in sources.items():
                initial = digest(source)
                output = target / name
                shutil.copy2(source, output)
                if digest(source) != initial or digest(output) != initial:
                    raise RuntimeError('Incoming batch changed while captured: ' + str(source))
                evidence[name] = {'path': str(output.relative_to(run)), 'sha256': initial}
            write_json(target / 'capture.json', {'captured_at': now(), 'evidence': evidence,
                       'boundary': 'Round 2 configs generated, before native post-place DRP.'})
            print(json.dumps({'captured_files': len(evidence), 'run': str(run)}), flush=True)
            return
        receipt = json.loads((run / 'receipt.json').read_text())
        if receipt['status'] != 'running':
            raise RuntimeError('Campaign ended before the incoming second batch was captured.')
        time.sleep(2)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-root', type=Path, required=True)
    capture(parser.parse_args().run_root.resolve())
