"""Bind analyses to their fixed original snapshot inputs."""
from collections.abc import Sequence
from pathlib import Path
import threading

from openroad_platform_client import KernelError, LocalFirstKernelClient


def snapshot_inputs(snapshot, with_timing=True):
    context = snapshot.get('run_summary', {}).get('timing_context')
    if not context or not context.get('executor'):
        raise ValueError('snapshot lacks its executable native context')
    inputs = {'openroad_bin': context['executor']}
    roles = {'raw_design_database': 'odb_path'}
    paths = {}
    if with_timing:
        paths = {context['constraints']: 'sdc_path', **{p: 'library' for p in context['libraries']}}
        if context.get('rc_script'): paths[context['rc_script']] = 'rc_script_path'
        if context.get('parasitics'): paths[context['parasitics']] = 'spef_path'
        if context.get('global_routing_segments'): paths[context['global_routing_segments']] = 'global_routing_segments_path'
        inputs['parasitic_mode'] = context['parasitic_mode']
        inputs['ideal_clocks'] = context.get('ideal_clocks', False)
    staged, libraries, provenance = [], [], []
    for ref in snapshot.get('source_artifacts', []):
        key = roles.get(ref.get('category')) or paths.get(ref.get('logical_path'))
        if not key:
            continue
        path = ref['logical_path']
        if any(p['destination'] == path for p in staged):
            raise ValueError('snapshot has ambiguous original native inputs: ' + path)
        staged.append({'destination': path, 'artifact_id': ref['artifact_id']})
        provenance.append(ref)
        if key == 'library': libraries.append(path)
        else: inputs[key] = path
    if 'odb_path' not in inputs or (with_timing and set(libraries) != set(context['libraries'])):
        raise ValueError('snapshot lacks original native inputs')
    if with_timing: inputs['liberty_paths'] = libraries
    inputs['input_provenance'] = provenance
    return inputs, staged


class FileChunks(Sequence):
    """Stream an upload through the existing sequence API without loading a DB."""
    def __init__(self, path, chunk_size=256 * 1024):
        self.path, self.chunk_size = Path(path), chunk_size
        self.size = self.path.stat().st_size

    def __len__(self):
        return max(1, (self.size + self.chunk_size - 1) // self.chunk_size)

    def __getitem__(self, index):
        if not isinstance(index, int) or not 0 <= index < len(self):
            raise IndexError(index)
        with self.path.open('rb') as stream:
            stream.seek(index * self.chunk_size)
            return stream.read(self.chunk_size)


class SnapshotExecutionClient(LocalFirstKernelClient):
    """Submit to one kernel; read and hash-check archive inputs before upload.

    Archive access is limited to public artifact reads. No execution method is
    invoked on the archive. Uploaded inputs are immutable and reusable in the
    new kernel. Confirmed digest mismatches fail before task submission.
    """
    def __init__(self, base_url, *, source_client=None, **kwargs):
        super().__init__(base_url, **kwargs)
        self.source_client = source_client
        self._inputs = {}
        self._input_lock = threading.Lock()

    def submit(self, task, **kwargs):
        staged = []
        refs = {r['artifact_id']: r for r in task.get('inputs', {}).get('input_provenance', [])}
        for item in task.get('staged_inputs', []):
            ref = refs.get(item.get('artifact_id'))
            if ref is None or self.source_client is None:
                staged.append(item)
                continue
            try:
                self.artifact_locator(ref['run_id'], ref['artifact_id'])
            except KernelError as exc:
                if exc.status != 404:
                    raise
                staged.append({k: v for k, v in item.items() if k != 'artifact_id'} |
                              {'input_id': self._upload_original(ref)})
            else:
                staged.append(item)
        return super().submit({**task, 'staged_inputs': staged}, **kwargs)

    def _upload_original(self, ref):
        key = (ref['artifact_id'], ref['sha256'])
        with self._input_lock:
            if key in self._inputs:
                return self._inputs[key]
            locator = self.source_client.artifact_locator(ref['run_id'], ref['artifact_id'])
            if locator['sha256'] != ref['sha256'] or locator['size_bytes'] != ref['size_bytes']:
                raise ValueError('archive artifact identity differs from snapshot provenance')
            uploaded = self.upload_input_chunks(FileChunks(locator['path']))
            if uploaded['sha256'] != ref['sha256'] or uploaded['size_bytes'] != ref['size_bytes']:
                raise ValueError('uploaded analysis input differs from original snapshot bytes')
            self._inputs[key] = uploaded['input_id']
            return uploaded['input_id']
