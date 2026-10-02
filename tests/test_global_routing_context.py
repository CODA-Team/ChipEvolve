"""Global-route queries must reconstruct native routes rather than placement RC."""
import json
import subprocess
import sys
from pathlib import Path


def test_global_route_commands_and_missing_input_rejection(tmp_path):
    plugin = Path(__file__).resolve().parents[1] / 'plugins/openroad-data'
    program = '''import json
from sta_inputs import timing_commands
print(json.dumps(timing_commands(json.loads(input()), lambda value: json.dumps(value))))
'''
    inputs = {'liberty_paths': ['cells.lib', 'memory.lib'], 'sdc_path': 'clock.sdc',
              'rc_script_path': 'rc.tcl', 'global_routing_segments_path': 'route.segments',
              'parasitic_mode': 'global_routing'}
    result = subprocess.run([sys.executable, '-c', program], cwd=plugin,
                            input=json.dumps(inputs), text=True, capture_output=True, check=True)
    commands = json.loads(result.stdout)
    assert commands[-2:] == ['read_global_route_segments "route.segments"',
                             'estimate_parasitics -global_routing']
    assert 'estimate_parasitics -placement' not in commands
    for field in ('global_routing_segments_path', 'rc_script_path'):
        invalid = {key: value for key, value in inputs.items() if key != field}
        result = subprocess.run([sys.executable, '-c', program], cwd=plugin,
                                input=json.dumps(invalid), text=True, capture_output=True)
        assert result.returncode != 0
        assert 'global_routing mode requires' in result.stderr
