"""Complete clock trees and delays from the exact original OpenSTA path report."""
from urllib.parse import quote

from .identity import snapshot_identity
from .queries import original_timing_path


def clock_paths(store, snapshot_id, path_id):
    rows = store.records(snapshot_id, 'timing_paths', record_id=path_id, limit=1)
    if not rows:
        raise KeyError('timing path not found: ' + path_id)
    path = rows[0]
    report = original_timing_path(store, snapshot_id, path)
    result = {'snapshot_id': snapshot_id, 'snapshot': snapshot_identity(store.snapshot(snapshot_id)),
              'path_id': path_id, 'evidence': path.get('evidence', []),
              'original_record': '/snapshots/' + snapshot_id + '/records/timing_paths/' + quote(path_id, safe='') + '/fragments',
              'basis': 'literal original OpenSTA report; all clock points in report order; native mapping is not substituted',
              'units': {'time': 's', 'capacitance': 'F', 'distance': 'm'}}
    if report is None:
        result['availability'] = {'clock_report': {'status': 'unavailable',
            'reason': 'original report entry is not attached to this stored path; recover its original_record or run a fresh timing query'}}
        return result
    result['report_header'] = {key: value for key, value in report.items()
                               if key not in ('source_path', 'source_clock_path', 'target_clock_path')}
    for section in ('source_clock_path', 'target_clock_path'):
        if section not in report:
            raise ValueError('original timing report does not declare ' + section)
        result[section] = report[section]
    result['clock_point_counts'] = {section: len(result[section]) for section in ('source_clock_path', 'target_clock_path')}
    return result
