"""Execute a complete ORFS flow in the attempt's isolated output directory."""
import json
import shutil
import subprocess
import zipfile
from pathlib import Path

from ..environment import require_eda_memory
from .adapter import _write_result, now, progress
from .process import run_logged


def run_flow(result_path, started, workspace, inputs):
    require_eda_memory()
    image = Path(inputs['orfs_image']).resolve()
    runtime = shutil.which(inputs.get('container_runtime', 'apptainer'))
    if not runtime or not image.is_file():
        raise ValueError('configured ORFS runtime/image is unavailable')
    config = inputs.get('design_config', 'designs/nangate45/gcd/config.mk')
    if not isinstance(config, str) or Path(config).is_absolute() or '..' in Path(config).parts:
        raise ValueError('design_config must be a relative ORFS configuration path')
    threads = inputs.get('threads', 8)
    if type(threads) is not int or not 1 <= threads <= 8:
        raise ValueError('threads must be 1..8')
    variant = inputs['revision_id']
    if not isinstance(variant, str) or not variant.replace('-', '').replace('_', '').isalnum():
        raise ValueError('revision_id must be an alphanumeric ORFS variant')
    command = [runtime, 'exec', '--cleanenv', '--containall', '--bind', f'{workspace}:/work',
               '--pwd', '/OpenROAD-flow-scripts/flow', str(image), 'make',
               f'DESIGN_CONFIG={config}', 'WORK_HOME=/work/flow', f'FLOW_VARIANT={variant}',
               f'NUM_CORES={threads}']
    # Optional staged design bindings keep the stock flow while making inputs
    # explicit. Defaults retain the original native configuration behavior.
    for field, variable in (('config_path', 'DESIGN_CONFIG'), ('sdc_path', 'SDC_FILE')):
        if inputs.get(field):
            path = (workspace / inputs[field]).resolve()
            path.relative_to(workspace)
            if not path.is_file():
                raise ValueError('missing staged design binding: ' + field)
            command.append(variable + '=/work/' + path.relative_to(workspace).as_posix())
    if inputs.get('liberty_paths'):
        libraries = []
        for value in inputs['liberty_paths']:
            path = (workspace / value).resolve()
            path.relative_to(workspace)
            if not path.is_file():
                raise ValueError('missing staged library')
            libraries.append('/work/' + path.relative_to(workspace).as_posix())
        command.append('LIB_FILES=' + ' '.join(libraries))
    progress('orfs', 'started')
    result = subprocess.CompletedProcess(command, run_logged(command, workspace))
    ended = now()
    (workspace / 'extractor_receipt.json').write_text(json.dumps({
        'command': command, 'started_at': started, 'ended_at': ended,
        'returncode': result.returncode, 'threads': threads,
        'output_root': 'flow', 'design_config': config}, indent=2) + '\n')
    artifacts = [{'kind': 'extractor_log', 'path': 'extractor.log'},
                 {'kind': 'extractor_receipt', 'path': 'extractor_receipt.json'}]
    artifacts.extend(archive_flow(workspace))
    progress('orfs', 'finished', status='succeeded' if result.returncode == 0 else 'failed')
    failure = None if result.returncode == 0 else {
        'category':'orfs_error', 'message':f'ORFS exited with status {result.returncode}', 'retryable':False}
    return _write_result(result_path, started, 'succeeded' if failure is None else 'failed',
                         result.returncode, artifacts, failure)


def archive_flow(workspace):
    with zipfile.ZipFile(workspace / 'flow-artifacts.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        for p in sorted((workspace / 'flow').rglob('*')):
            if p.is_file():
                archive.write(p, p.relative_to(workspace).as_posix())
    artifacts = [{'kind': 'flow_archive', 'path': 'flow-artifacts.zip'}]
    kinds = {'.odb':'raw_design_database', '.sdc':'raw_constraints', '.spef':'raw_parasitics',
             '.v':'raw_netlist', '.def':'raw_layout', '.gds':'raw_layout'}
    for p in sorted((workspace / 'flow').rglob('*')):
        if p.is_file() and (p.suffix in kinds or p.suffix == '.json'):
            artifacts.append({'kind': kinds.get(p.suffix, 'raw_flow_metadata'),
                              'path': p.relative_to(workspace).as_posix()})
    return artifacts
