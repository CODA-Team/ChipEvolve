"""Select complete original flow reports and join their own data-path points."""
import json
from pathlib import Path

from .artifacts import _run_dirs
from .engineering import path_engineering_detail
from .identity import snapshot_identity
from .metadata import timing_values
from .metadata import recovery_path
from .source_json import source_json
from .timing_facts import timing_fact_snapshot, fact_source


def _report_file(snapshot, query, root):
    if query.get('path'):
        return query['path']
    directory = _run_dirs(snapshot, Path(root))['reports']
    if directory['candidate_count'] != 1:
        raise ValueError('original timing report requires one report directory or explicit path')
    path = Path(directory['path']) / (snapshot['stage'] + '.timing_' + query.get('path_type', 'max') + '.json')
    if not path.is_file():
        raise ValueError('no unique stage timing report; select its actual path from artifacts/files')
    return path.relative_to(root).as_posix()


def _header(row, index, source):
    if not isinstance(row.get('source_path'), list):
        raise ValueError('original OpenSTA timing report must declare a source_path array')
    fields = ('startpoint', 'endpoint', 'path_type', 'slack', 'data_arrival_time', 'required_time',
              'crpr', 'source_clock', 'target_clock', 'source_clock_edge', 'target_clock_edge')
    result = {key: row[key] for key in fields if key in row}
    result.update(group=row.get('path_group'), unit='s', report_index=index,
                  report_source_type='original_flow_report',
                  data_pin_names=[point['pin'] for point in row['source_path']])
    result['report_path_id'] = 'report:' + source['sha256'] + ':' + str(index)
    return timing_values(result)


def _points(store, snapshot_id, header, row):
    entities, points = {}, []

    def resolve(kind, name):
        if not name:
            return None
        key = (kind, name)
        if key not in entities:
            matches = store.entities_named(snapshot_id, kind, name)
            if len(matches) > 1:
                raise ValueError('original timing point has an ambiguous ' + kind + ' name: ' + name)
            entities[key] = matches[0]['object_id'] if matches else None
        return entities[key]

    for ordinal, original in enumerate(row['source_path']):
        point = {'point_id': header['report_path_id'] + ':point:' + str(ordinal),
                 'path_id': header['report_path_id'], 'ordinal': ordinal, 'path_section': 'source_path',
                 'pin_name': original['pin'], 'instance_name': original.get('instance'),
                 'net_name': original.get('net'), 'cell_name': original.get('cell'),
                 'arrival': original.get('arrival'), 'slew': original.get('slew'),
                 'load': original.get('capacitance')}
        for kind in ('instance', 'net', 'pin'):
            point[kind + '_id'] = resolve(kind, point[kind + '_name'])
        point['mapping_status'] = ('unmapped' if any(point[kind + '_name'] and not point[kind + '_id']
                                                  for kind in ('instance', 'net', 'pin')) else 'mapped')
        points.append(point)
    return points


def timing_report_paths(store, snapshot_id, query, root):
    allowed = {'path', 'path_type', 'startpoint', 'endpoint', 'group', 'sort', 'order', 'tie_break',
               'limit', 'offset', 'fields', 'detail', 'include_path_details', 'tie_rule',
               'signal_type', 'include_routing', 'detail_limit', 'detail_offset'}
    if set(query) - allowed:
        raise ValueError('unknown original timing-report query fields: ' + ','.join(sorted(set(query) - allowed)))
    if query.get('detail', 'summary') not in ('summary', 'full'):
        raise ValueError('original timing-report detail must be summary|full')
    path_type = query.get('path_type', 'max')
    if path_type not in ('max', 'min'):
        raise ValueError('original report path_type must be max|min')
    if query.get('include_path_details', '0') not in ('0', '1'):
        raise ValueError('include_path_details must be 0|1')
    sort = query.get('sort', 'slack')
    if sort not in ('slack', 'arrival'):
        raise ValueError('original report sort must be slack|arrival')
    order = query.get('order', 'worst')
    if order not in ('worst', 'best'):
        raise ValueError('original report order must be worst|best')
    tie = query.get('tie_break', 'report_order')
    if tie not in ('report_order', 'native_names'):
        raise ValueError('original report tie_break must be report_order|native_names')
    snapshot = store.snapshot(snapshot_id)
    filters = {'path_type': path_type, **{k: query[k] for k in ('startpoint', 'endpoint') if query.get(k)}}
    if query.get('group'):
        filters['path_group'] = query['group']
    ascending = (sort == 'slack') == (order == 'worst')
    original = source_json(store, snapshot_id, {
        'path': _report_file(snapshot, query, Path(root)), 'json_path': '$.checks',
        'filters': json.dumps(filters), 'sort_field': 'slack' if sort == 'slack' else 'data_arrival_time',
        'order': 'asc' if ascending else 'desc',
        'tie_fields': 'startpoint,endpoint' if tie == 'native_names' else '',
        'limit': query.get('limit', '1'), 'offset': query.get('offset', '0')}, root)
    paths = [_header(row, index, original['source']) for row, index in
             zip(original['rows'], original['source_array_indices'])]
    facts = timing_fact_snapshot(store, snapshot)
    result = {'snapshot_id': snapshot_id, 'snapshot': snapshot_identity(snapshot), 'paths': paths,
              'report_source': original['source'], 'source_array_indices': original['source_array_indices'],
              'evidence': [{'source_type': 'original_flow_report', **original['source'],
                            'locator': {'json_path': '$.checks', 'array_indices': original['source_array_indices']}}],
              'object_facts_source': {**fact_source(facts), 'timing_report': original['source'],
                                      'timing_basis': 'original_flow_report'},
              'selection': {'candidate_scope': 'all original report checks, not the indexed native sample',
                            'original_array_count': original['original_array_count'], 'filters': filters,
                            'sort': sort, 'order': order, 'tie_break': tie},
              'units': {'time': 's', 'interface_time_fields': 'ns', 'capacitance': 'F'},
              **{k: original[k] for k in ('count', 'returned', 'truncated', 'next_offset', 'limit', 'offset')}}
    if query.get('include_path_details') == '1':
        details = []
        for header, row in zip(paths, original['rows']):
            detail = {'timing_path': {**header, 'path_id': header['report_path_id']},
                      'timing_points': _points(store, facts['snapshot_id'], header, row)}
            item = path_engineering_detail(store, snapshot_id, detail, {
                **query, 'limit': query.get('detail_limit', '100'),
                'offset': query.get('detail_offset', '0')})
            item['path']['report_path_id'] = item['path'].pop('path_id')
            for point in item['points']:
                point['report_path_id'] = point.pop('path_id')
            for extrema in item['data_point_extrema'].values():
                if extrema['selected_point'] is not None:
                    point = extrema['selected_point']
                    point['report_path_id'] = point.pop('path_id')
            item['object_facts_source']['timing_report'] = original['source']
            item['object_facts_source']['timing_basis'] = 'original_flow_report'
            item['association_coverage']['candidate_domain'] = 'all source_path points of this original flow report row'
            item['report_index'] = header['report_index']
            details.append(item)
        result['path_details'] = details
    if not query.get('fields') and query.get('detail', 'summary') == 'summary':
        omitted = []
        redundant = ('path', 'points', 'instances', 'nets', 'instance_names', 'net_names', 'data_pin_names',
                     'evidence', 'snapshot', 'snapshot_id', 'object_facts_source', 'dbu_per_micron')
        for index, detail in enumerate(result.get('path_details', [])):
            for key in redundant:
                if key in detail:
                    del detail[key]
                    omitted.append('path_details[' + str(index) + '].' + key)
        result['delivery'] = {'detail': 'summary', 'omitted_fields': omitted,
            'full_details': recovery_path('/snapshots/' + snapshot_id + '/timing-reports', query),
            'selection': 'complete original path headers, ordered data pin sequence and joined aggregates; '
                         'associated record pages remain accessible through full_details or explicit fields'}
    return result
