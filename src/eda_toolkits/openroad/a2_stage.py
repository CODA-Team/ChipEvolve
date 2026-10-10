"""A deterministic single-candidate seam; A2 retains all search decisions."""
import hashlib
import json
import os
from pathlib import Path

from .a2_checkpoint import clear_downstream, required_checkpoint, restore_checkpoint
from .a2_evaluation import evaluation_plan, parse_evaluation
from .adapter import _write_result, now, progress
from .flow import archive_flow
from .process import run_logged


def input_path(workspace, value):
    path = (workspace / value).resolve()
    path.relative_to(workspace)
    if not path.is_file():
        raise ValueError('staged native input is missing: ' + str(value))
    return path


def fingerprint(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def make_plan(workspace, inputs, profile, flow):
    stage = inputs['stage']
    config = input_path(workspace, inputs['config_path'])
    sdc = input_path(workspace, inputs['sdc_path'])
    flow_dir = Path(profile['flow_dir'])
    if not flow_dir.is_absolute() or not (flow_dir / 'Makefile').is_file():
        raise ValueError('profile.flow_dir must name the frozen native flow')
    if fingerprint(flow_dir / 'Makefile') != profile['makefile_sha256']:
        raise ValueError('native Makefile differs from the tool profile')
    threads = inputs['threads']
    if type(threads) is not int or threads < 1:
        raise ValueError('threads must be a positive integer')
    command = ['make', '-C', str(flow_dir), f'FLOW_HOME={flow_dir}',
               f'DESIGN_CONFIG={config}', f'SDC_FILE={sdc}', f'WORK_HOME={flow}',
               f'NUM_CORES={threads}', f'OPENROAD_EXE={profile["openroad_bin"]}',
               f'YOSYS_EXE={profile["yosys_bin"]}']
    command.extend(f'{key}={flow / name}' for key, name in (
        ('RESULTS_DIR', 'results'), ('LOG_DIR', 'logs'),
        ('OBJECTS_DIR', 'objects'), ('REPORTS_DIR', 'reports')))
    if stage != 'place':
        # Frozen predecessors are inputs, not build targets in this attempt.
        for path in required_checkpoint(flow, stage):
            command.extend(['-o', str(path)])
    command.append({'place': 'place', 'cts': 'cts', 'route_finish': 'finish'}[stage])
    return command


def run_stage(result_path, started, workspace, inputs):
    stage = inputs['stage']
    if stage not in {'place', 'cts', 'route_finish', 'eval_place', 'eval_cts', 'eval_final'}:
        raise ValueError('unknown A2 native stage: ' + str(stage))
    if type(inputs['threads']) is not int or inputs['threads'] < 1:
        raise ValueError('threads must be a positive integer')
    profile_path = input_path(workspace, inputs['profile_path'])
    profile = json.loads(profile_path.read_text())
    flow = workspace / 'flow'
    if stage == 'place':
        if inputs.get('checkpoint_path'):
            raise ValueError('place starts a new candidate and does not consume a checkpoint')
        flow.mkdir()
    else:
        restore_checkpoint(input_path(workspace, inputs['checkpoint_path']), flow)
        required_checkpoint(flow, stage)
        if not stage.startswith('eval_'):
            clear_downstream(flow, stage)
    for name in ('results', 'logs', 'objects', 'reports'):
        (flow / name).mkdir(exist_ok=True)
    environment = dict(os.environ)
    environment.pop('PYTHONPATH', None)
    environment.pop('PYTHONHOME', None)
    environment.update(PATH=os.pathsep.join([str(Path(profile['python_bin']).parent),
                                            str(Path(profile['yosys_bin']).parent),
                                            str(Path(profile['openroad_bin']).parent), '/usr/bin', '/bin']),
                       PYTHONNOUSERSITE='1', OMP_NUM_THREADS=str(inputs['threads']),
                       OPENBLAS_NUM_THREADS=str(inputs['threads']), MKL_NUM_THREADS=str(inputs['threads']))
    if stage.startswith('eval_'):
        script = Path(profile['flow_dir']) / 'eval_tns.tcl'
        if fingerprint(script) != profile['eval_tns_sha256']:
            raise ValueError('native evaluator differs from the tool profile')
        command = evaluation_plan(inputs, profile, flow, environment)
    else:
        command = make_plan(workspace, inputs, profile, flow)
    progress('a2.' + stage, 'started')
    returncode = run_logged(command, workspace, environment=environment)
    failure = None if returncode == 0 else {'category': 'a2_stage_error',
        'message': f'native {stage} exited with status {returncode}', 'retryable': False}
    observations = None
    if returncode == 0:
        if stage.startswith('eval_'):
            try:
                observations = parse_evaluation((workspace / 'extractor.log').read_text())
            except ValueError as error:
                returncode = 1
                failure = {'category': 'a2_evaluation_missing', 'message': str(error), 'retryable': False}
        else:
            stem = {'place': '3_place', 'cts': '4_cts', 'route_finish': '6_final'}[stage]
            for suffix in ('odb', 'sdc'):
                path = flow / 'results' / f'{stem}.{suffix}'
                if not path.is_file() or path.stat().st_size == 0:
                    returncode = 1
                    failure = {'category': 'a2_stage_output_missing',
                        'message': f'native {stage} did not produce {path.name}', 'retryable': False}
                    break
    with (flow / 'combined.log').open('a') as log:
        log.write((workspace / 'extractor.log').read_text())
    receipt = {'stage': stage, 'command': command, 'profile': profile,
               'profile_sha256': fingerprint(profile_path), 'returncode': returncode,
               'started_at': started, 'ended_at': now(), 'observations': observations}
    if stage.startswith('eval_'):
        receipt['evaluation'] = inputs['evaluation']
        stem = {'eval_place': '3_place', 'eval_cts': '4_cts', 'eval_final': '6_final'}[stage]
        receipt['parasitic_mode'] = 'spef' if (flow / 'results' / f'{stem}.spef').is_file() else 'estimate_placement'
    else:
        receipt['config_sha256'] = fingerprint(input_path(workspace, inputs['config_path']))
        receipt['sdc_sha256'] = fingerprint(input_path(workspace, inputs['sdc_path']))
    (workspace / 'extractor_receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    artifacts = [{'kind': 'extractor_log', 'path': 'extractor.log'},
                 {'kind': 'extractor_receipt', 'path': 'extractor_receipt.json'}, *archive_flow(workspace)]
    progress('a2.' + stage, 'finished', status='succeeded' if failure is None else 'failed')
    return _write_result(result_path, started, 'succeeded' if failure is None else 'failed',
                         returncode, artifacts, failure)
