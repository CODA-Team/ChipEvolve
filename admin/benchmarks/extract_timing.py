"""Small real OpenROAD timing experiment. No fake EDA tool or fabricated metrics."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

parser = argparse.ArgumentParser()
parser.add_argument('--openroad', required=True)
parser.add_argument('--period', type=float, required=True)
parser.add_argument('--mode', choices=('ok', 'missing-tech', 'wait'), default='ok')
args = parser.parse_args()
root = Path.cwd()
period = args.period
prefix = '/OpenROAD-flow-scripts/flow/platforms/nangate45'
tech = '' if args.mode == 'missing-tech' else f'read_lef {prefix}/lef/NangateOpenCellLibrary.tech.lef\nread_lef {prefix}/lef/NangateOpenCellLibrary.macro.lef\n'
script = tech + f'''read_liberty {prefix}/lib/NangateOpenCellLibrary_typical.lib
read_verilog design.v
link_design bench
create_clock -name virtual -period {period}
set_input_delay 0.1 -clock virtual [get_ports a]
set_output_delay 0.1 -clock virtual [get_ports y]
set_input_transition 0.02 [get_ports a]
set_load 0.02 [get_ports y]
report_checks -path_delay max -format full_clock_expanded -digits 6
puts "WS_NS=[sta::worst_slack -max]"
puts "TNS_NS=[sta::total_negative_slack -max]"
'''
(root / 'analysis.tcl').write_text(script)
result = subprocess.run([args.openroad, '-exit', 'analysis.tcl'], cwd=root,
                        capture_output=True, text=True, check=False)
output = result.stdout + result.stderr
(root / 'report.rpt').write_text(output)
print(output, flush=True)
# This OpenROAD build exits 0 even for some Tcl errors: values are mandatory.
ws = re.search(r'^WS_NS=([-+0-9.eE]+)$', output, re.M)
tns = re.search(r'^TNS_NS=([-+0-9.eE]+)$', output, re.M)
if result.returncode or '[ERROR ' in output or ws is None or tns is None:
    print('ERROR: OpenROAD did not produce a complete timing experiment', file=sys.stderr)
    raise SystemExit(2)
if args.mode == 'wait':
    # Only the cancel-mechanism task uses this deliberate wait after real STA.
    import time
    print('WAITING_FOR_CANCELLATION', flush=True)
    time.sleep(120)
run_id = os.environ.get('EXECUTION_RUN_ID', 'direct-' + str(period))
snapshot_id = 'timing-' + run_id
source = {'role': 'analysis_report', 'logical_path': 'report.rpt',
          'sha256': hashlib.sha256((root / 'report.rpt').read_bytes()).hexdigest(),
          'source_type': 'line', 'line_start': 1, 'line_end': len(output.splitlines())}
folder = root / 'query-data'
folder.mkdir(exist_ok=True)
snapshot = {'schema_version': 3, 'snapshot_id': snapshot_id, 'design_id': 'buffer-chain',
            'revision_id': 'same-netlist', 'run_id': run_id, 'stage': 'timing',
            'created_at': datetime.now(timezone.utc).isoformat()}
(folder / 'manifest.json').write_text(json.dumps(snapshot))
(folder / 'summary.json').write_text(json.dumps({'tool': 'OpenROAD', 'constraints': {'clock_period_ns': period},
                                              'timing_context': {'corner': 'typical', 'coverage_scope': 'single IO path'}}))
observations = [
    {'observation_id': 'metric:time-unit', 'name': 'timing__flow__platform__time_units',
     'kind': 'metric', 'value': '1ns'},
    {'observation_id': 'metric:ws', 'name': 'timing__timing__setup__ws', 'kind': 'metric',
     'value': float(ws.group(1)), 'context': {'corner': 'typical'}, 'evidence': [source]},
    {'observation_id': 'metric:tns', 'name': 'timing__timing__setup__tns', 'kind': 'metric',
     'value': float(tns.group(1)), 'context': {'corner': 'typical'}, 'evidence': [source]},
]
(folder / 'observations.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in observations))
entities = [{'object_id': f'instance:u{i}', 'kind': 'instance', 'name': f'u{i}', 'cell_type': 'BUF_X1'} for i in range(1, 4)]
(folder / 'objects.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in entities))
paths = [{'path_id': 'io:a-y', 'startpoint': 'a', 'endpoint': 'y', 'slack': float(ws.group(1)),
          'unit': 'ns', 'corner': 'typical', 'check': 'setup', 'analysis': 'max', 'evidence': [source]}]
(folder / 'timing_paths.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in paths))
(folder / 'coverage.json').write_text(json.dumps({'timing': {'scope': 'IO path with ideal nets; no parasitics'},
                                               'physical': {'status': 'unavailable'}}))
