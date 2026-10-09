"""Nangate45 buffer sizing with fixed evaluation inputs and native receipts."""
import hashlib
import json
import re
from typing import Any

from .inputs import snapshot_inputs
from .jobs import native_task


def buffer_eco_task(snapshot: dict[str, Any], package: dict[str, Any], proposal: dict[str, Any]) -> dict[str, Any]:
    """Only the proposal is model-authored; package permissions are caller-owned."""
    if package['role'] != 'eco' or package['consumer_status'] != 'ready':
        raise ValueError('this receiver connects only the ECO role')
    scope = package['scope']
    for field in ('snapshot_id', 'design_id', 'run_id', 'revision_id', 'stage'):
        if snapshot[field] != scope[field]:
            raise ValueError('ECO input changed fixed ' + field)
    original, staged = snapshot_inputs(snapshot)
    loaded = {ref['logical_path']: ref for ref in original['input_provenance']}
    declared = {ref['logical_path']: ref for ref in package['fixed_inputs']}
    for path, ref in loaded.items():
        expected = declared.get(path)
        if expected is None or any(ref[key] != expected[key] for key in ('artifact_id','run_id','sha256','size_bytes')):
            raise ValueError('ECO source identity is missing or changed: ' + path)
    if set(proposal) != {'changes', 'reason'} or not isinstance(proposal['reason'], str) or not proposal['reason']:
        raise ValueError('ECO proposal needs only changes and an explicit reason')
    changes = proposal['changes']
    if not isinstance(changes, list) or not changes:
        raise ValueError('ECO needs at least one explicit buffer size change')
    permissions = {p['instance']: p for p in package['buffer_permissions']}
    if len(permissions) != len(package['buffer_permissions']):
        raise ValueError('ECO permissions have duplicate instances')
    seen = set()
    script = 'file mkdir outputs\n'
    for change in changes:
        if set(change) != {'instance', 'target_master'}:
            raise ValueError('buffer change has unknown fields')
        instance, target = change['instance'], change['target_master']
        permission = permissions.get(instance)
        if permission is None or instance in seen or target not in permission['allowed_masters']:
            raise ValueError('buffer resize is outside the handed-off permissions')
        seen.add(instance)
        before = permission['original_master']
        if not all(isinstance(name, str) and re.fullmatch(r'BUF_X[1-9][0-9]*', name) for name in (before,target)):
            raise ValueError('current ECO toolkit supports verified Nangate45 BUF_X family only')
        if not isinstance(instance, str) or not re.fullmatch(r'[A-Za-z0-9_./$\\\[\]-]+',instance):
            raise ValueError('unsupported native buffer name for this adapter')
        script += f'set inst [[ord::get_db_block] findInst {{{instance}}}]\n'
        script += 'if {$inst == "NULL"} {error "allowed buffer instance is missing"}\n'
        script += f'if {{[[$inst getMaster] getName] ne "{before}"}} {{error "original buffer master changed"}}\n'
        script += f'puts "BEFORE {instance} [[$inst getMaster] getName]"\n'
        script += f'set master [[ord::get_db] findMaster {{{target}}}]\n'
        script += 'if {$master == "NULL"} {error "requested buffer master is missing"}\n'
        script += '$inst swapMaster $master\n'
        script += f'puts "AFTER {instance} [[$inst getMaster] getName]"\n'
    script += 'write_db outputs/candidate.odb\nwrite_verilog outputs/candidate.v\n'
    script += '''sta::redirect_file_begin {outputs/area.rpt}
report_design_area
set block [ord::get_db_block]
set dbu [$block getDbUnitsPerMicron]
set area 0.0
foreach inst [$block getInsts] {
  set master [$inst getMaster]
  set area [expr {$area + double([$master getWidth])*[$master getHeight]/$dbu/$dbu}]
}
puts [format "EDA_EXACT_ALL_INSTANCE_AREA_UM2 %.12g" $area]
puts "EDA_AREA_BASIS OpenDB master geometry, all instances including physical-only cells"
sta::redirect_file_end
'''
    for check, delay in (('setup','max'),('hold','min')):
        script += 'sta::redirect_file_begin {outputs/' + check + '.json}\n'
        script += f'report_checks -path_delay {delay} -group_path_count 200 -endpoint_path_count 1 -fields {{slew cap input_pins net fanout}} -format json -digits 10\n'
        script += 'sta::redirect_file_end\n'
        script += 'sta::redirect_file_begin {outputs/' + check + '.rpt}\n'
        script += f'report_worst_slack -{delay}\nreport_tns -{delay}\nsta::redirect_file_end\n'
    task = native_task(snapshot, original, staged, script)
    identity = hashlib.sha256(json.dumps(proposal,sort_keys=True).encode()).hexdigest()[:12]
    task.update(task_id=package['handoff_id']+'-'+identity, project_id='codex-eco-handoff')
    task['inputs']['native_extra_paths'] = ['outputs/candidate.odb','outputs/candidate.v',
        'outputs/setup.json','outputs/hold.json','outputs/setup.rpt','outputs/hold.rpt','outputs/area.rpt']
    budget = package['budget']
    if budget['max_experiments'] != 1:
        raise ValueError('current ECO receiver accepts one experiment per package')
    task['timeout_seconds'] = min(180,budget['max_seconds'])
    task['resources'] = {'cpu_cores':budget['cpu_cores'], 'memory_bytes':budget['memory_bytes'],'processes':128}
    if not 1 <= budget['cpu_cores'] <= 8 or not 1 <= budget['memory_bytes'] <= 24*1024**3:
        raise ValueError('ECO resource budget exceeds the release policy')
    task['inputs']['threads'] = budget['cpu_cores']
    task['labels'].update(handoff_id=package['handoff_id'],investigation_id=package['investigation_id'])
    return task


def eco_export_task(snapshot: dict[str, Any], package: dict[str, Any], physical_run: dict[str, Any], artifacts: list[dict[str, Any]]) -> dict[str, Any]:
    """Fresh process reloads the candidate and evaluates both checks for DF."""
    original, staged = snapshot_inputs(snapshot)
    odb = next(a for a in artifacts if a['store_key'] == 'outputs/candidate.odb')
    netlist = next(a for a in artifacts if a['store_key'] == 'outputs/candidate.v')
    area = next(a for a in artifacts if a['store_key'] == 'outputs/area.rpt')
    before_odb = original['odb_path']
    staged = [item for item in staged if item['destination'] != before_odb]
    staged += [
        {'artifact_id':odb['artifact_id'], 'destination':'outputs/candidate.odb'},
        {'artifact_id':netlist['artifact_id'], 'destination':'outputs/candidate.v'},
        {'artifact_id':area['artifact_id'], 'destination':'outputs/area.rpt'},
    ]
    original['input_provenance'] = [ref for ref in original['input_provenance'] if ref['logical_path'] != before_odb]
    sid = package['handoff_id'] + '-candidate'
    task = {
        'schema_version':3,'task_id':sid,'project_id':'eco-result-export',
        'design_id':snapshot['design_id'],'plugin_id':'openroad-data',
        'inputs':{**original,'odb_path':'outputs/candidate.odb','adapter':'openroad',
            'snapshot_id':sid,'design_id':snapshot['design_id'],
            'revision_id':package['handoff_id'],'run_id':physical_run['run_id'],
            'stage':snapshot['stage'],'unit':'s','corner':snapshot['run_summary']['timing_context'].get('corner'),
            'analysis':snapshot['run_summary']['timing_context'].get('analysis'),
            'path_count':200,'endpoint_path_count':1,'output_directory':'query-data',
            'created_at':physical_run['created_at'],
            'native_extra_paths':['outputs/candidate.v','outputs/area.rpt']},
        'staged_inputs':staged,'timeout_seconds':120,'max_attempts':1,
        'labels':{'run_type':'analysis','analysis_of_run_id':physical_run['run_id'],
                  'handoff_id':package['handoff_id'],
                  'experiment_parent_snapshot_id':snapshot['snapshot_id']},
        'resources':{'cpu_cores':2,'memory_bytes':6*1024**3,'processes':128},
        'expected_artifacts':['data_snapshot'],
    }
    return task
