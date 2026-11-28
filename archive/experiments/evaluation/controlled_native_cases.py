"""Controlled physical/constraint experiments and separate native OpenSTA oracles.

No DF parser generates the reference answers. Oracle runs/files stay out of the
public case bindings and every model prompt. Public experiments expose actual
inputs and provenance, so investigating a changed constraint is possible.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import time
import urllib.request

from eda_toolkits.inputs import FileChunks, SnapshotExecutionClient, snapshot_inputs
from eda_toolkits.jobs import native_task


DEVELOPMENT = {
    'e00': {},
    'e01': {'period_ns': 0.20},
    'e02': {'period_ns': 0.30},
    'e03': {'resize': ['output53', 'BUF_X1']},
    'e04': {'resize': ['place178', 'BUF_X4']},
    'e05': {'rc_scale': 1.3},
    'e06': {},
    'e07': {'relax_endpoint': 'resp_msg[12]'},
    'e10': {'resize': ['output53', 'BUF_X1'], 'rc_scale': 1.3},
    'e11': {'resize': ['place178', 'BUF_X4'], 'period_ns': 0.24},
}


def write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2) + '\n'
    if path.exists() and path.read_text() != text:
        history = path.parent/'history'
        history.mkdir(exist_ok=True)
        old = path.read_bytes()
        (history/(hashlib.sha256(old).hexdigest()[:16]+'-'+path.name)).write_bytes(old)
    path.write_text(text)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def wait(client, run_id):
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        run = client.run(run_id)
        if run['status'] in ('succeeded', 'failed', 'cancelled', 'timed_out', 'lost'):
            return run
        time.sleep(0.2)
    raise TimeoutError('native case wait expired')


def source(client, artifacts, key):
    found = [a for a in artifacts if a.get('store_key', a.get('logical_path')) == key]
    if len(found) != 1:
        raise ValueError('expected exactly one original artifact: ' + key)
    ref = found[0]
    location = client.artifact_locator(ref['run_id'], ref['artifact_id'])
    if digest(location['path']) != ref['sha256']:
        raise ValueError('native input changed after registration')
    return ref, Path(location['path'])


def redirected(path, command):
    return f'sta::redirect_file_begin {{{path}}}\n{command}\nsta::redirect_file_end'


def build(args):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(args.data_url+'/snapshots/'+args.snapshot+'/summary?detail=full') as response:
        snapshot = json.load(response)['data']['snapshot']
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    private = output/'private'
    private.mkdir(exist_ok=True)
    os.chmod(private, 0o700)
    client = SnapshotExecutionClient(args.kernel_url)
    original, staged = snapshot_inputs(snapshot)
    original_refs = snapshot['source_artifacts']
    _, constraints = source(client, original_refs, original['sdc_path'])
    _, parasitics = source(client, original_refs, original['spef_path'])
    specs = json.loads(args.specs.read_text()) if args.specs else DEVELOPMENT
    selected = args.cases or list(specs)
    bindings = {}
    for name in selected:
        changes = specs[name]
        folder = output/'public'/name
        if (folder/'binding.json').exists():
            bindings[name] = json.loads((folder/'binding.json').read_text())
            print(name, 'resume passed case', flush=True)
            continue
        folder.mkdir(parents=True, exist_ok=True)
        inputs = dict(original)
        fixed = [dict(item) for item in staged]
        edits = {}
        if set(changes) & {'period_ns', 'relax_endpoint', 'waveform_ns', 'hold_uncertainty_ns'}:
            text = constraints.read_text()
            if 'period_ns' in changes:
                text, count = re.subn(r'(-period\s+)0\.250*\b',
                                     lambda m: m[1]+str(changes['period_ns']), text)
                if count != 2:
                    raise ValueError('controlled period change needs exactly two known clocks')
            if 'relax_endpoint' in changes:
                # An explicit endpoint override after the original SDC, both min/max.
                text += '\nset_output_delay -clock [get_clocks vclk_core_clock] 0.0 '
                text += '[get_ports {resp_msg[12]}]\n'
            if 'waveform_ns' in changes:
                a, b = changes['waveform_ns']
                text = re.sub(r'-waveform\s+\{[^}]+\}', '', text)
                text, count = re.subn(r'^(\s*create_clock\b)',
                    lambda match: match[1] + ' -waveform {' + str(a) + ' ' + str(b) + '}',
                    text, flags=re.M)
                if count != 2: raise ValueError('expected two original clock declarations')
            if 'hold_uncertainty_ns' in changes:
                text += '\nset_clock_uncertainty -hold ' + str(changes['hold_uncertainty_ns']) + ' [all_clocks]\n'
            edits['sdc_path'] = ('constraints.sdc', text)
        if 'rc_scale' in changes:
            scale = changes['rc_scale']
            text = parasitics.read_text()
            for token in ('C', 'R'):
                text, count = re.subn(r'(^\*'+token+r'_UNIT\s+)([0-9.eE+-]+)',
                                     lambda m: m[1]+str(float(m[2])*scale), text, flags=re.M)
                if count != 1:
                    raise ValueError('SPEF must declare exactly one resistance/capacitance unit')
            edits['spef_path'] = ('parasitics.spef', text)
        for field, (filename, text) in edits.items():
            path = folder/filename
            path.write_text(text)
            uploaded = client.upload_input_chunks(FileChunks(path))
            old_path = inputs[field]
            fixed = [item for item in fixed if item['destination'] != old_path]
            fixed.append({'input_id':uploaded['input_id'], 'destination':old_path})
            inputs['input_provenance'] = [ref for ref in inputs['input_provenance']
                                          if ref['logical_path'] != old_path]
        if changes.get('slow_library'):
            if args.slow_library is None: raise ValueError('slow corner needs an explicit native liberty file')
            path = folder/'slow.lib'
            path.write_bytes(args.slow_library.read_bytes())
            uploaded=client.upload_input_chunks(FileChunks(path))
            if len(inputs['liberty_paths']) != 1: raise ValueError('controlled library change needs one source')
            old_path=inputs['liberty_paths'][0]
            fixed=[item for item in fixed if item['destination'] != old_path]
            fixed.append({'input_id':uploaded['input_id'],'destination':old_path})
            inputs['input_provenance']=[ref for ref in inputs['input_provenance'] if ref['logical_path'] != old_path]
        script = 'file mkdir outputs\n'
        if 'resize' in changes:
            instance, master = changes['resize']
            script += f'set inst [[ord::get_db_block] findInst {{{instance}}}]\n'
            script += 'if {$inst == "NULL"} {error "controlled resize instance missing"}\n'
            script += f'puts "BEFORE {instance} [[$inst getMaster] getName]"\n'
            script += f'set master [[ord::get_db] findMaster {{{master}}}]\n'
            script += 'if {$master == "NULL"} {error "requested master unavailable"}\n'
            script += '$inst swapMaster $master\n'
            script += f'puts "AFTER {instance} [[$inst getMaster] getName]"\n'
        script += 'write_db outputs/candidate.odb\nwrite_verilog outputs/candidate.v\n'
        script += 'report_design_area\n'
        script += 'set block [ord::get_db_block]\nset dbu [$block getDbUnitsPerMicron]\nset area 0.0\n'
        script += 'foreach inst [$block getInsts] {set m [$inst getMaster]; set area [expr {$area + double([$m getWidth])*[$m getHeight]/$dbu/$dbu}]}\n'
        script += 'puts [format "EDA_EXACT_ALL_INSTANCE_AREA_UM2 %.12g" $area]\n'
        task = native_task(snapshot, inputs, fixed, script)
        variant = hashlib.sha256((script+json.dumps(changes,sort_keys=True)).encode()).hexdigest()[:12]
        task.update(task_id='controlled-'+name+'-'+variant, project_id='controlled-'+args.split)
        task['inputs']['native_extra_paths'] = ['outputs/candidate.odb', 'outputs/candidate.v']
        write(folder/'physical-task.json', task)
        physical = client.submit(task, idempotency_key='controlled-'+args.split+'-'+name+'-'+variant)
        physical_id = physical['run']['run_id']
        run = wait(client, physical_id)
        artifacts = client.artifacts(physical_id)
        write(folder/'physical-result.json', {'run':run, 'logs':client.logs(physical_id,max_bytes=65536),
                                             'artifacts':artifacts, 'resources':client.resources(physical_id)})
        if run['status'] != 'succeeded':
            raise RuntimeError('native physical case failed: ' + name)
        database, _ = source(client, artifacts, 'outputs/candidate.odb')
        # Evaluate the actual output database, with the exact edited SDC/SPEF inputs.
        evaluate_inputs = dict(inputs)
        evaluate_inputs['odb_path'] = 'outputs/candidate.odb'
        evaluate_staged = [item for item in fixed if item['destination'] != original['odb_path']]
        evaluate_staged.append({'artifact_id':database['artifact_id'], 'destination':'outputs/candidate.odb'})
        oracle_script = 'file mkdir oracle\n'
        for check, delay in (('setup','max'),('hold','min')):
            oracle_script += redirected('oracle/'+check+'.json',
                f'report_checks -path_delay {delay} -group_path_count 200 -endpoint_path_count 1 '
                '-fields {slew cap input_pins net fanout} -format json -digits 10')+'\n'
            oracle_script += redirected('oracle/'+check+'.rpt',
                f'report_worst_slack -{delay}\nreport_tns -{delay}')+'\n'
        oracle_script += redirected('oracle/area.rpt','report_design_area')+'\n'
        oracle = native_task(snapshot, evaluate_inputs, evaluate_staged, oracle_script)
        oracle.update(task_id='oracle-'+name+'-'+variant, project_id='private-native-oracles')
        oracle['inputs']['native_extra_paths'] = ['oracle/setup.json','oracle/hold.json',
                                                 'oracle/setup.rpt','oracle/hold.rpt','oracle/area.rpt']
        write(private/name/'oracle-task.json', oracle)
        submitted = client.submit(oracle, idempotency_key='controlled-native-oracle-'+name+'-'+variant)
        oracle_id = submitted['run']['run_id']
        reference_run = wait(client, oracle_id)
        references = client.artifacts(oracle_id)
        write(private/name/'oracle-result.json', {'run':reference_run,'artifacts':references,
                                                'logs':client.logs(oracle_id,max_bytes=65536)})
        if reference_run['status'] != 'succeeded':
            raise RuntimeError('independent native oracle failed: ' + name)
        gold = {'inputs':{}, 'files':{}}
        for ref in artifacts:
            if ref['store_key'] in ('outputs/candidate.odb','outputs/candidate.v') or ref['kind'] in ('raw_constraints','raw_library','raw_parasitics'):
                gold['inputs'][ref['store_key']] = ref['sha256']
        for key in ['oracle/setup.json','oracle/hold.json','oracle/setup.rpt','oracle/hold.rpt','oracle/area.rpt']:
            ref, path = source(client, references, key)
            target = private/name/Path(key).name
            target.write_bytes(path.read_bytes())
            gold['files'][key] = {'sha256':ref['sha256'], 'bytes':ref['size_bytes']}
        write(private/name/'gold.json', gold)
        snapshot_id = args.prefix+'-'+name+'-finish'
        product_inputs = {**evaluate_inputs, 'adapter':'openroad', 'snapshot_id':snapshot_id,
                          'design_id':snapshot['design_id'], 'revision_id':'controlled-'+name,
                          'run_id':physical_id, 'stage':'finish', 'unit':'s', 'corner':changes.get('corner','typical'),
                          'analysis':changes.get('analysis','default'), 'path_count':changes.get('path_count',20), 'endpoint_path_count':1,
                          'output_directory':'query-data',
                          'created_at':run['created_at']}
        product = {'schema_version':3,'task_id':snapshot_id,'project_id':'controlled-case-export',
                   'design_id':snapshot['design_id'],'plugin_id':'openroad-data',
                   'inputs':product_inputs,'staged_inputs':evaluate_staged,
                   'labels':{'run_type':'analysis','analysis_of_run_id':physical_id,
                             'experiment_parent_snapshot_id':args.snapshot},
                   'resources':{'cpu_cores':2,'memory_bytes':6*1024**3,'processes':128},
                   'timeout_seconds':120,'max_attempts':1,'expected_artifacts':['data_snapshot']}
        for original_path, destination in [('reports/native.rpt','inputs/physical.rpt'),
                                           ('outputs/candidate.v','outputs/candidate.v')]:
            ref = next(a for a in artifacts if a['store_key'] == original_path)
            product['staged_inputs'].append({'artifact_id':ref['artifact_id'],'destination':destination})
        product['inputs']['native_extra_paths'] = ['inputs/physical.rpt','outputs/candidate.v']
        for field in ('from_pin','to_pin','path_group'):
            if field in changes: product['inputs'][field] = changes[field]
        write(folder/'export-task.json', product)
        exported = client.submit(product,idempotency_key='controlled-export-'+name)
        export_id = exported['run']['run_id']
        export_run = wait(client,export_id)
        export_artifacts = client.artifacts(export_id)
        write(folder/'export-result.json',{'run':export_run,'artifacts':export_artifacts,
                                          'logs':client.logs(export_id,max_bytes=65536)})
        if export_run['status'] != 'succeeded':
            raise RuntimeError('product export failed: '+name)
        bundle = next(a for a in export_artifacts if a['kind']=='data_snapshot')
        request = urllib.request.Request(args.data_url+'/snapshots/from-run',
            data=json.dumps({'run_id':export_id,'artifact_id':bundle['artifact_id']}).encode(),
            headers={'Content-Type':'application/json'})
        with opener.open(request,timeout=30) as response:
            write(folder/'import.json',json.load(response))
        binding = {'case_experiment':name,'snapshot_id':snapshot_id,'physical_run_id':physical_id,
                   'export_run_id':export_id,'native_inputs':gold['inputs'],
                   'oracle_available_to_models':False}
        write(folder/'binding.json',binding)
        bindings[name]=binding
        print(name,snapshot_id,'native oracle and public snapshot ready',flush=True)
    write(output/'public/bindings.json',bindings)
    return 0


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--kernel-url',default='http://127.0.0.1:18700')
    parser.add_argument('--data-url',default='http://127.0.0.1:18924')
    parser.add_argument('--snapshot',default='gcd-shared-toolchain-01-finish')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--cases',nargs='+')
    parser.add_argument('--specs',type=Path)
    parser.add_argument('--prefix',default='controlled')
    parser.add_argument('--split',choices=['development','sealed'],default='development')
    parser.add_argument('--slow-library',type=Path)
    raise SystemExit(build(parser.parse_args()))
