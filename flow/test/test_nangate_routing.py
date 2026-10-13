"""Nangate45 search parameters must reach independent native routing scopes."""
import csv
import os
from pathlib import Path
import shutil
import subprocess


FLOW = Path(__file__).resolve().parents[1]
DESIGN = FLOW / 'designs/nangate45/aes'


def native_commands(tmp_path, script_name, **parameters):
    harness = tmp_path / 'commands.tcl'
    harness.write_text('''proc set_global_routing_layer_adjustment {layers value} {
    puts "adjust $layers $value"
}
proc set_routing_layers {args} { puts "layers $args" }
source [lindex $argv 0]
''')
    environment = dict(os.environ, MAX_ROUTING_LAYER='metal10',
                       MIN_ROUTING_LAYER='metal2', MIN_CLK_ROUTING_LAYER='metal3',
                       **{key: str(value) for key, value in parameters.items()})
    return subprocess.check_output(['tclsh', str(harness), str(DESIGN / script_name)],
                                   env=environment, text=True).splitlines()


def test_floorplan_and_post_cts_hooks_consume_separate_proposals(tmp_path):
    values = dict(FLOORPLAN_PIN_LAYER_ADJUST=.41, FLOORPLAN_ABOVE_LAYER_ADJUST=.27,
                  PIN_LAYER_ADJUST=.63, ABOVE_LAYER_ADJUST=.36)
    floorplan = native_commands(tmp_path, 'fastroute_floorplan.tcl', **values)
    routing = native_commands(tmp_path, 'fastroute_routing.tcl', **values)
    assert floorplan[:2] == ['adjust metal2-metal3 0.41', 'adjust metal4-metal10 0.27']
    assert routing[:2] == ['adjust metal2-metal3 0.63', 'adjust metal4-metal10 0.36']
    assert floorplan[2:4] == routing[2:4] == [
        'layers -clock metal3-metal10', 'layers -signal metal2-metal10']
    assert 'scope=floorplan pin=0.41 above=0.27' in floorplan[-1]
    assert 'scope=routing pin=0.63 above=0.36' in routing[-1]


def test_initial_baseline_preserves_platform_capacities_and_binds_hooks(tmp_path):
    design = tmp_path / 'designs/nangate45/aes'
    design.mkdir(parents=True)
    shutil.copy2(FLOW / 'run_sequential.sh', tmp_path / 'run_sequential.sh')
    for helper in ('initial_constraints.py', 'drp_config.json'):
        shutil.copy2(FLOW / helper, tmp_path / helper)
    for name in ('config.mk', 'constraint.sdc'):
        shutil.copy2(DESIGN / name, design / name)
    subprocess.run(['bash', str(tmp_path / 'run_sequential.sh'), 'nangate45', 'aes', '3', '1'],
                   env=dict(os.environ, DRP_SEED='42'), check=True, capture_output=True)
    rows = list(csv.DictReader((design / 'nangate45_aes.csv').open()))
    assert len(rows) == 3
    assert float(rows[0]['FLOORPLAN_PIN_LAYER_ADJUST']) == .5
    assert float(rows[0]['FLOORPLAN_ABOVE_LAYER_ADJUST']) == .25
    config = (design / 'config_1.mk').read_text()
    assert 'export PIN_LAYER_ADJUST = 0.5' in config
    assert 'export ABOVE_LAYER_ADJUST = 0.25' in config
    base = (design / 'config.mk').read_text()
    assert 'export FASTROUTE_TCL = $(FLOW_HOME)/designs/nangate45/aes/fastroute_floorplan.tcl' in base
    assert 'export PRE_GLOBAL_ROUTE_TCL = $(FLOW_HOME)/designs/nangate45/aes/fastroute_routing.tcl' in base
    commands = native_commands(tmp_path, 'fastroute_floorplan.tcl',
                               FLOORPLAN_PIN_LAYER_ADJUST=.5, FLOORPLAN_ABOVE_LAYER_ADJUST=.25)
    assert commands[:2] == ['adjust metal2-metal3 0.5', 'adjust metal4-metal10 0.25']
