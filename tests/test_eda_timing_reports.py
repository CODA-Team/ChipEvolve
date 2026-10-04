"""Original flow path queries must not substitute reconstructed native samples."""
from copy import deepcopy
import hashlib
import json
from urllib.parse import parse_qs, urlsplit

import pytest

from openroad_app_data_foundation.repository import DataStore
from openroad_app_data_foundation.server import Handler


@pytest.fixture
def report(tmp_path):
    points = [{'pin': 'u/A', 'instance': 'u', 'net': 'a', 'cell': 'BUF', 'arrival': 1e-9},
              {'pin': 'u/Z', 'instance': 'u', 'net': 'b', 'cell': 'BUF', 'arrival': 2e-9},
              {'pin': 'v/A', 'instance': 'v', 'net': 'b', 'cell': 'RAM', 'arrival': 3e-9},
              {'pin': 'v/Z', 'instance': 'v', 'net': 'b', 'cell': 'RAM', 'arrival': 4e-9}]
    row = {'path_type': 'max', 'startpoint': 'u/A', 'endpoint': 'v/Z', 'path_group': 'clk',
           'slack': -0.5e-9, 'data_arrival_time': 4e-9, 'required_time': 3.5e-9,
           'source_path': points, 'source_clock_path': [{'pin': 'clock/Z', 'instance': 'clock'}]}
    rows = [{**row, 'startpoint': 'other' + str(n), 'slack': n * 1e-9} for n in range(55)]
    rows += [{**row, 'slack': -0.1e-9}, row]
    path = tmp_path / 'reports/pdk/chip/r/global_route.timing_max.json'
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({'checks': rows}))
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    relative = path.relative_to(tmp_path).as_posix()
    store = DataStore(tmp_path / 'data.sqlite')
    entities = [{'object_id': name, 'kind': 'instance', 'name': name,
                 'attributes': {'master': master, 'is_macro': macro}}
                for name, master, macro in [('u', 'BUF', 0), ('v', 'RAM', 1), ('clock', 'CLKBUF', 0)]]
    entities += [{'object_id': name, 'kind': 'net', 'name': name,
                  'attributes': {'signal_type': 'SIGNAL', 'fanout': 1}} for name in ('a', 'b')]
    entities += [{'object_id': name, 'kind': 'pin', 'name': name} for name in ('u/A', 'u/Z', 'v/A', 'v/Z')]
    store.register({'snapshot': {'snapshot_id': 's', 'design_id': 'chip', 'revision_id': 'r',
                                 'run_id': 'run', 'stage': 'global_route', 'created_at': '2026-10-04'},
                    'run_summary': {'dbu_per_micron': 1000, 'timing_context': {
                        'producer': {'artifacts': {relative: {'sha256': digest}}}}},
                    'entities': entities, 'physical_context': [
                        {'object_id': 'u', 'bbox': {'x_min': 0, 'y_min': 0, 'x_max': 1000, 'y_max': 1000}},
                        {'object_id': 'v', 'bbox': {'x_min': 2000, 'y_min': 2000, 'x_max': 3000, 'y_max': 3000}}],
                    'timing_paths': [{'path_id': 'p', 'check': 'setup', 'path_type': 'max',
                                      'startpoint': 'u/A', 'endpoint': 'v/Z', 'slack': -0.4e-9, 'unit': 's'}],
                    'timing_points': [{'point_id': 'native', 'path_id': 'p', 'ordinal': 0,
                                       'pin_name': 'u/A', 'instance_id': 'u', 'net_id': 'a',
                                       'path_section': 'source_path'}]})
    handler = Handler.__new__(Handler)
    handler.store, handler.auto_import, handler.native_root = store, False, tmp_path
    yield handler, path, row, digest
    store.close()


def test_original_report_query_recovers_unsampled_path_and_its_complete_associations(report):
    handler, _, original, digest = report
    options = {'startpoint': 'u/A', 'endpoint': 'v/Z', 'include_path_details': '1', 'limit': '1', 'detail_limit': '1',
               'fields': 'paths.slack_ns,paths.data_pin_names,path_details.instance_count,path_details.net_count,'
                         'path_details.macro_count,path_details.standard_cell_count,path_details.master_counts,'
                         'path_details.instance_bbox_union_um,path_details.data_pin_names'}
    path = '/snapshots/s/timing-reports'
    result = handler._get(path, options)
    assert result['paths'] == [{'slack_ns': -0.5, 'data_pin_names': [p['pin'] for p in original['source_path']]}]
    detail = result['path_details'][0]
    assert detail['instance_count'] == 2 and detail['net_count'] == 2
    assert detail['macro_count'] == 1 and detail['standard_cell_count'] == 1
    assert detail['master_counts'] == {'BUF': 1, 'RAM': 1}
    assert detail['instance_bbox_union_um'] == {'x_min': 0, 'y_min': 0, 'x_max': 3, 'y_max': 3}
    assert detail['data_pin_names'] == ['u/A', 'u/Z', 'v/A', 'v/Z']
    assert result['object_facts_source']['timing_report']['sha256'] == digest
    recovery = urlsplit(result['delivery']['full_details'])
    full = handler._get(recovery.path, {k: v[0] for k, v in parse_qs(recovery.query).items()})
    assert full['selection']['original_array_count'] == 57 and full['source_array_indices'] == [56]
    assert full['count'] == 2 and full['path_details'][0]['points_page']['truncated']
    assert full['path_details'][0]['data_path_pin_count'] == 4
    assert full['path_details'][0]['association_coverage']['status'] == 'complete'
    native = handler._get('/snapshots/s/timing-paths/p/engineering', {})
    assert native['data_pin_names'] == ['u/A'] and native['path']['slack_ns'] == pytest.approx(-0.4)
    assert full['paths'][0]['report_source_type'] == 'original_flow_report'
    assert 'path_id' not in full['paths'][0]


def test_original_path_paging_does_not_change_complete_names_or_counts(report):
    handler, _, _, _ = report
    options = {'startpoint': 'u/A', 'endpoint': 'v/Z', 'include_path_details': '1', 'limit': '1'}
    first = handler._get('/snapshots/s/timing-reports', options)
    second = handler._get('/snapshots/s/timing-reports', {**options, 'offset': '1'})
    assert first['count'] == second['count'] == 2
    assert first['paths'][0]['slack_ns'] == -0.5 and second['paths'][0]['slack_ns'] == pytest.approx(-0.1)
    assert first['source_array_indices'] == [56] and second['source_array_indices'] == [55]
    assert second['next_offset'] is None
    assert first['path_details'][0]['instance_count'] == second['path_details'][0]['instance_count'] == 2
    assert len(first['path_details'][0]['points']) == len(second['path_details'][0]['points']) == 4
    later = handler._get('/snapshots/s/timing-reports', {**options, 'detail_limit': '2', 'detail_offset': '2'})
    assert later['source_array_indices'] == [56]
    assert later['path_details'][0]['points_page']['offset'] == 2
    assert [p['pin_name'] for p in later['path_details'][0]['points']] == ['v/A', 'v/Z']
    assert later['path_details'][0]['data_pin_names'] == first['path_details'][0]['data_pin_names']


def test_original_join_cannot_treat_unmapped_points_as_verified_zero_counts(report):
    handler, path, row, _ = report
    bad = deepcopy(row)
    bad['source_path'][2]['instance'] = 'unmapped'
    alternate = path.with_name('alternate.json')
    alternate.write_text(json.dumps({'checks': [bad]}))
    result = handler._get('/snapshots/s/timing-reports', {
        'path': alternate.relative_to(handler.native_root).as_posix(), 'include_path_details': '1'})
    detail = result['path_details'][0]
    assert detail['association_coverage']['status'] == 'partial'
    assert detail['macro_count'] is None and detail['standard_cell_count'] is None
