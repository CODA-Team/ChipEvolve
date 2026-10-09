"""Build native tool tasks using the existing public EF task contract."""
import uuid
from typing import Any
from datetime import datetime, timezone
from .inputs import snapshot_inputs


def timing_task(snapshot: dict[str, Any], query: dict[str, Any], *, facts_snapshot_id: str | None = None, analysis_id: str | None = None, created_at: str | None = None) -> dict[str, Any]:
    snapshot_id = snapshot["snapshot_id"]
    facts_snapshot_id = facts_snapshot_id or snapshot_id
    validate_timing_query(query)
    facts = {"snapshot_id": facts_snapshot_id}
    original, staged = snapshot_inputs(snapshot)
    inputs = {**original, 'adapter': 'opensta', 'snapshot_id': facts['snapshot_id'] + '-query-' + (analysis_id or uuid.uuid4().hex[:12]),
              'design_id': snapshot['design_id'], 'revision_id': snapshot['revision_id'],
              'run_id': snapshot['run_id'], 'stage': snapshot['stage'],
              'created_at': created_at or datetime.now(timezone.utc).isoformat(), 'parent_snapshot_id': snapshot_id,
              'output_directory': 'query-data', 'analysis': snapshot['run_summary']['timing_context'].get('analysis'),
              'corner': snapshot['run_summary']['timing_context'].get('corner'), 'unit': 's', **query}
    task = {'schema_version': 3, 'task_id': inputs['snapshot_id'],
            'project_id': 'eda-ai-timing-query', 'design_id': snapshot['design_id'],
            'plugin_id': 'openroad-data', 'inputs': inputs, 'staged_inputs': staged,
            'labels': {'run_type':'analysis', 'analysis_of_run_id':snapshot['run_id'],
                       'parent_snapshot_id':snapshot_id},
            'resources': {'cpu_cores': 2, 'memory_bytes': 6 * 1024**3, 'processes': 128},
            'timeout_seconds': 180, 'max_attempts': 1, 'expected_artifacts': ['data_snapshot']}
    return task


def validate_timing_query(query):
    fields = {'from_pin', 'to_pin', 'path_group', 'path_count', 'endpoint_path_count'}
    if set(query) - fields:
        raise ValueError('unknown timing query field')
    count = query.get('path_count', 5)
    if type(count) is not int or not 1 <= count <= 200:
        raise ValueError('path_count must be between 1 and 200')
    # OpenSTA's -endpoint_path_count: how many paths one endpoint may contribute.
    # The default equals path_count (N variants of one endpoint, the historical
    # behaviour); 1 makes the N reported paths N distinct endpoints, which is
    # what "the N worst paths" means when the reference flow reports one path per
    # endpoint.  Without it the sampler is the only place that distinction could
    # live, and it does not exist there.
    endpoints = query.get('endpoint_path_count')
    if endpoints is not None and (type(endpoints) is not int or not 1 <= endpoints <= 200):
        raise ValueError('endpoint_path_count must be between 1 and 200')
    for key in ('from_pin', 'to_pin', 'path_group'):
        if key in query and (not isinstance(query[key], str) or not query[key] or len(query[key]) > 4096):
            raise ValueError(f'{key} must be a native name')


def native_task(snapshot: dict[str, Any], original: dict[str, Any], staged: list[dict[str, Any]], script: str) -> dict[str, Any]:
    snapshot_id = snapshot["snapshot_id"]
    task_id = snapshot_id + '-native-' + uuid.uuid4().hex[:12]
    task = {'schema_version': 3, 'task_id': task_id, 'project_id': 'eda-ai-native-query',
            'design_id': snapshot['design_id'], 'plugin_id': 'openroad-data',
            'labels': {'parent_snapshot_id': snapshot_id},
            'inputs': {**original, 'adapter': 'report', 'report': 'native',
                       'script': script, 'output_directory': 'reports',
                       'parent_snapshot_id': snapshot_id}, 'staged_inputs': staged,
            'resources': {'cpu_cores': 2, 'memory_bytes': 6 * 1024**3, 'processes': 128},
            'timeout_seconds': 180, 'max_attempts': 1, 'expected_artifacts': ['analysis_report']}
    return task
