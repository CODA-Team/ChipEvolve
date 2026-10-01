"""Engineering regressions: positive slack, clock exclusion and original-source access."""
import json
from pathlib import Path

import pytest
from openroad_app_data_foundation.constraints import constraint_context
from openroad_app_data_foundation.engineering import path_engineering, timing_overview
from openroad_app_data_foundation.artifacts import native_excerpt
from openroad_app_data_foundation.metrics import project_run
from openroad_app_data_foundation.repository import DataStore


def sample():
    return {'snapshot': {'snapshot_id': 's', 'design_id': 'chip', 'revision_id': 'r',
                         'run_id': 'run', 'stage': 'finish', 'created_at': '2026-10-01'},
            'run_summary': {'dbu_per_micron': 2000},
            'entities': [{'object_id': 'i', 'kind': 'instance', 'name': 'u',
                          'attributes': {'master': 'BUF', 'is_macro': 0}},
                         {'object_id': 'c', 'kind': 'instance', 'name': 'clock_buf',
                          'attributes': {'master': 'CLKBUF'}},
                         {'object_id': 'n', 'kind': 'net', 'name': 'signal',
                          'attributes': {'fanout': 3, 'signal_type': 'SIGNAL'}}],
            'physical_context': [{'object_id': 'i', 'bbox': {
                'x_min': 0, 'y_min': 0, 'x_max': 10, 'y_max': 20}}],
            'timing_paths': [{'path_id': 'p', 'check': 'setup', 'slack': 0.2,
                              'unit': 's', 'startpoint': 'u/A', 'endpoint': 'u/Z'}],
            'timing_points': [
                {'point_id': 'clock', 'path_id': 'p', 'ordinal': 0,
                 'instance_id': 'c', 'path_section': 'source_clock_path'},
                {'point_id': 'in', 'path_id': 'p', 'ordinal': 1,
                 'pin_name': 'u/A', 'instance_id': 'i', 'net_id': 'n',
                 'path_section': 'source_path'},
                {'point_id': 'out', 'path_id': 'p', 'ordinal': 2,
                 'pin_name': 'u/Z', 'instance_id': 'i', 'net_id': 'n',
                 'path_section': 'source_path'}]}


def test_object_page_joins_chip_geometry_and_reports_missing_geometry(tmp_path):
    from openroad_app_data_foundation.discovery import list_objects
    store = DataStore(tmp_path / 'd.sqlite')
    try:
        store.register(sample())
        page = list_objects(store, 's', {'kind': 'instance', 'sort': 'name',
                            'include_physical': '1', 'fields': 'name,physical', 'limit': '1'})
        assert page['objects'][0]['physical']['status'] == 'not_extracted'
        other = list_objects(store, 's', {'kind': 'instance', 'sort': 'name',
                             'include_physical': '1', 'fields': 'name,physical', 'offset': '1'})
        assert other['objects'][0]['physical']['bbox_um']['x_max'] == 0.005
        assert other['objects'][0]['physical']['bbox_dbu']['y_max'] == 20
    finally:
        store.close()


def test_source_search_pages_original_matches_with_correct_byte_locations(tmp_path):
    from openroad_app_data_foundation.source_search import search_source
    pack = sample()
    source = tmp_path / 'report.txt'
    source.write_text('header\n错误 one\ncontext\nerror two\nend\n')
    from openroad_platform_runtime.digest import sha256
    pack['run_summary']['timing_context'] = {'producer': {'artifacts': {
        'report.txt': {'sha256': sha256(source)}}}}
    store = DataStore(tmp_path / 'd.sqlite')
    try:
        store.register(pack)
        query = {'path': 'report.txt', 'pattern': '错误|error', 'context_lines': '1', 'limit': '1'}
        first = search_source(store, 's', query, tmp_path)
        assert first['count'] == 2 and first['next_offset'] == 1
        second = search_source(store, 's', {**query, 'offset': '1'}, tmp_path)
        assert second['next_offset'] is None
        row = second['matches'][0]
        assert row['match_line'] == 4 and row['line_start'] == 3 and row['line_end'] == 5
        assert source.read_bytes()[row['byte_start']:row['byte_end']].decode() == row['text']
        assert first['source']['sha256'] == sha256(source)
    finally:
        store.close()


def test_clean_design_has_zero_wns_but_positive_worst_slack(tmp_path):
    pack = sample()
    pack['observations'] = [
        {'observation_id': 'metric:finish__timing__setup__ws', 'kind': 'metric', 'value': 0.207},
        {'observation_id': 'metric:finish__timing__hold__ws', 'kind': 'metric', 'value': -0.02}]
    store = DataStore(tmp_path / 'd.sqlite')
    try:
        store.register(pack)
        metrics = {r['name']: r for r in project_run(store, [store.snapshot('s')])['metrics']}
        assert metrics['WNS']['value'] == 0
        assert metrics['WS']['value'] == metrics['WNS']['raw_value'] == 0.207
        assert metrics['HOLD_WNS']['value'] == metrics['HOLD_WS']['value'] == -0.02
    finally:
        store.close()


def test_engineering_counts_unique_data_instances_not_clock_buffers(tmp_path):
    store = DataStore(tmp_path / 'd.sqlite')
    try:
        store.register(sample())
        detail = path_engineering(store, 's', 'p', {'limit': '1'})
        assert detail['instance_count'] == 1
        assert detail['data_path_pin_count'] == 2
        assert detail['master_counts'] == {'BUF': 1}
        assert detail['points_page']['truncated']
        other = path_engineering(store, 's', 'p', {'limit': '1', 'offset': '1'})
        assert [p['pin_name'] for p in detail['points'] + other['points']] == ['u/A', 'u/Z']
        overview = timing_overview(store, 's', {'check': 'setup', 'limit': '5'})
        assert overview['common_instances'] == ['u']
        assert overview['net_names'] == ['signal']
    finally:
        store.close()


def test_constraint_coverage_comes_from_native_check_not_sampled_paths(tmp_path):
    pack = sample()
    sources = {'sdc': 'create_clock -name clk -period 2 [get_ports {clk}]\n'
                      'set_input_delay 0.4 -clock [get_clocks {clk}] -add_delay [get_ports {a}]\n',
               'report': 'Warning: There are 2 unconstrained endpoints.\n  u/D\n  v/D\n'}
    pack['snapshot']['source_artifacts'] = [{'artifact_id': aid, 'run_id': 'run', 'size_bytes': len(text),
                                'category': 'raw_constraints' if aid == 'sdc' else 'analysis_report',
                                'stage': 'finish', 'sha256': 'a' * 64,
                                'logical_path': 'query-data/' + ('effective.sdc' if aid == 'sdc'
                                                                else 'check_setup.rpt')}
                               for aid, text in sources.items()]
    class SourceClient:
        def artifact_excerpt(self, run_id, artifact_id, *, offset, max_bytes):
            return {'text': sources[artifact_id][offset:offset + max_bytes]}
    store = DataStore(tmp_path / 'd.sqlite')
    try:
        store.register(pack)
        data = constraint_context(store, SourceClient(), 's', {})
        assert data['unconstrained_endpoint_count'] == 2
        assert data['unconstrained_endpoints'] == ['u/D', 'v/D']
        assert data['delay_values']['input_delay'] == [0.4]
    finally:
        store.close()


def test_native_excerpt_continues_and_cannot_read_another_run(tmp_path):
    root = tmp_path / 'flow'
    folder = root / 'reports/p/chip/r'
    folder.mkdir(parents=True)
    (folder / 'report.txt').write_text('0123456789')
    store = DataStore(tmp_path / 'd.sqlite')
    try:
        store.register(sample())
        first = native_excerpt(store, 's', {'path': 'reports/p/chip/r/report.txt', 'max_bytes': '4'}, root)
        next_page = native_excerpt(store, 's', {'path': 'reports/p/chip/r/report.txt',
                                               'offset': str(first['next_offset']), 'max_bytes': '6'}, root)
        assert first['text'] + next_page['text'] == '0123456789'
        assert not next_page['truncated']
        with pytest.raises(ValueError):
            native_excerpt(store, 's', {'path': 'reports/p/other/r/report.txt'}, root)
    finally:
        store.close()


def test_discovery_uses_connected_net_type_and_complete_role_pages(tmp_path):
    from openroad_app_data_foundation.discovery import list_objects
    pack = sample()
    pack['entities'] += [
        {'object_id': 'p1', 'kind': 'pin', 'name': r'u/a\[0\]', 'parent_id': 'i'},
        {'object_id': 'p2', 'kind': 'pin', 'name': 'u/b', 'parent_id': 'i'},
        {'object_id': 'p3', 'kind': 'pin', 'name': 'u/c', 'parent_id': 'i'},
        {'object_id': 'clock', 'kind': 'net', 'name': 'clk', 'attributes': {'signal_type': 'CLOCK'}}]
    pack['relations'] = [
        {'relation_id': 'r1', 'subject_id': 'p1', 'predicate': 'connected_to', 'object_id': 'n'},
        {'relation_id': 'r2', 'subject_id': 'p2', 'predicate': 'connected_to', 'object_id': 'n'},
        {'relation_id': 'r3', 'subject_id': 'p3', 'predicate': 'connected_to', 'object_id': 'clock'},
        {'relation_id': 'l1', 'subject_id': 'n', 'predicate': 'loads', 'object_id': 'p1'},
        {'relation_id': 'l2', 'subject_id': 'n', 'predicate': 'loads', 'object_id': 'p2'}]
    store = DataStore(tmp_path / 'd.sqlite')
    try:
        store.register(pack)
        query = {'kind': 'pin', 'parent_id': 'i', 'signal_type': 'SIGNAL', 'sort': 'name', 'limit': '1'}
        first = list_objects(store, 's', query)
        second = list_objects(store, 's', {**query, 'offset': str(first['next_offset'])})
        assert first['count'] == 2
        assert first['objects'][0]['attributes']['signal_type'] == 'SIGNAL'
        assert first['objects'][0]['attributes']['net_name'] == 'signal'
        assert {r['object_id'] for r in first['objects'] + second['objects']} == {'p1', 'p2'}
        roles = list_objects(store, 's', {'kind': 'pin', 'connected_to': 'n', 'net_role': 'load'})
        assert {p['object_id'] for p in roles['objects']} == {'p1', 'p2'}
        assert list_objects(store, 's', {'kind': 'pin', 'name_contains': 'a[0]'})['count'] == 1
        assert list_objects(store, 's', {'kind': 'instance', 'region': '10,0,20,20',
                                        'intersection': 'touching'})['count'] == 1
        assert list_objects(store, 's', {'kind': 'instance', 'region': '10,0,20,20',
                                        'intersection': 'positive_area'})['count'] == 0
        assert list_objects(store, 's', {'kind': 'instance', 'region': '5,0,5,20',
                                        'intersection': 'positive_area'})['count'] == 0
    finally:
        store.close()


def test_routing_totals_uses_geometry_not_reported_metric(tmp_path):
    from openroad_app_data_foundation.engineering import routing_totals
    pack = sample()
    pack['physical_context'].append({'object_id': 'net:1', 'routing': [
        {'routing_type': 'segment', 'centerline_length_dbu': 4000},
        {'routing_type': 'segment', 'centerline_length_dbu': 6000},
        {'routing_type': 'via', 'via': 'V12'}]})
    pack['observations'] = [{'observation_id': 'metric:finish__route__wirelength', 'kind': 'metric', 'value': 900}]
    store = DataStore(tmp_path / 'd.sqlite')
    try:
        store.register(pack)
        result = routing_totals(store, 's')
        assert result['wirelength_um'] == 5
        assert result['segment_count'] == 2 and result['via_count'] == 1
    finally:
        store.close()


def test_parasitics_object_id_resolves_native_name(tmp_path):
    from openroad_app_data_foundation.parasitics import net_parasitics
    pack = sample()
    store = DataStore(tmp_path / 'd.sqlite')
    try:
        store.register(pack)
        result = net_parasitics(store, None, 's', 'n', {})
        assert result['net'] == 'signal' and result['indexed_net']
        assert result['requested_net'] == 'n'
        assert result['reason'] == 'snapshot_has_no_parasitics_artifact'
    finally:
        store.close()


def test_routing_summary_states_via_membership_of_both_layers(tmp_path):
    from openroad_app_data_foundation.discovery import routing_summary
    pack = sample()
    pack['physical_context'].append({'object_id': 'n', 'routing': [
        {'routing_type': 'segment', 'layer': 'metal2', 'x_min': 0, 'y_min': 0,
         'x_max': 4000, 'y_max': 100, 'centerline_length_dbu': 3900},
        {'routing_type': 'via', 'via': 'V12', 'bottom_layer': 'metal1', 'top_layer': 'metal2'},
        {'routing_type': 'via', 'via': 'V23', 'bottom_layer': 'metal2', 'top_layer': 'metal3'}]})
    store = DataStore(tmp_path / 'd.sqlite')
    try:
        store.register(pack)
        result = routing_summary(store, 's', 'n')
        assert result['via_count'] == 2
        assert result['via_distribution_by_layer'] == {'metal1': 1, 'metal2': 2, 'metal3': 1}
        assert result['wirelength_um'] == 1.95
    finally:
        store.close()


def test_point_projection_filters_before_counting_and_keeps_continuation(tmp_path):
    from openroad_app_data_foundation.queries import path_points
    store = DataStore(tmp_path / 'd.sqlite')
    try:
        store.register(sample())
        first = path_points(store, 's', 'p', {'path_section': 'source_path', 'fields': 'pin_name', 'limit': '1'})
        second = path_points(store, 's', 'p', {'path_section': 'source_path', 'fields': 'pin_name', 'limit': '1', 'offset': str(first['next_offset'])})
        assert first['count'] == 2
        assert first['timing_points'] + second['timing_points'] == [{'pin_name': 'u/A'}, {'pin_name': 'u/Z'}]
        assert not second['truncated']
    finally:
        store.close()


def test_native_query_wait_returns_terminal_result_in_one_operation(monkeypatch):
    from openroad_app_data_foundation import timing_queries
    class NativeClient:
        states = iter(['queued', 'running', 'succeeded'])
        def run(self, run_id):
            return {'project_id': 'eda-ai-timing-query', 'status': next(self.states), 'design_id': 'chip', 'terminal_reason': None}
        def artifacts(self, run_id):
            return []
    monkeypatch.setattr(timing_queries.time, 'sleep', lambda seconds: None)
    result = timing_queries.timing_query_status(None, NativeClient(), 'run', 2)
    assert result['status'] == 'succeeded'


def test_generic_native_query_binds_only_its_snapshot_originals(tmp_path):
    from openroad_app_data_foundation.native_queries import submit_native_query, native_query_result
    pack = sample()
    pack['run_summary']['timing_context'] = {'executor': '/tool/openroad'}
    pack['snapshot']['source_artifacts'] = [
        {'artifact_id': 'odb-original', 'category': 'raw_design_database', 'logical_path': 'inputs/design.odb', 'run_id': 'run', 'stage': 'finish', 'sha256': 'a'*64, 'size_bytes': 20}]
    class Client:
        task = None
        def submit(self, task):
            self.task = task
            return {'run': {'run_id': 'native-run'}}
        def run(self, run_id):
            return {'project_id': 'eda-ai-native-query', 'status': 'succeeded', 'terminal_reason': None}
        def artifacts(self, run_id):
            return [{'kind': 'analysis_report', 'artifact_id': 'answer', 'metadata': {'report': 'native'}}]
        def artifact_excerpt(self, run_id, artifact_id, *, offset, max_bytes):
            assert (run_id, artifact_id, offset) == ('native-run', 'answer', 2)
            return {'text': 'actual native output', 'truncated': False}
    store = DataStore(tmp_path / 'd.sqlite')
    try:
        store.register(pack)
        client = Client()
        result = submit_native_query(store, client, 's', {'script': 'puts [[[ord::get_db] getChip] getBlock] getName'})
        assert result['run']['run_id'] == 'native-run'
        assert client.task['staged_inputs'] == [{'destination': 'inputs/design.odb', 'artifact_id': 'odb-original'}]
        assert client.task['inputs']['adapter'] == 'report' and client.task['inputs']['report'] == 'native'
        assert 'spef_path' not in client.task['inputs']
        assert native_query_result(client, 'native-run', {'offset': '2'})['excerpt']['text'] == 'actual native output'
    finally:
        store.close()


def test_compact_pin_projection_keeps_classification_and_batch_identity(tmp_path):
    from openroad_app_data_foundation.discovery import list_objects
    pack = sample()
    pack['entities'].append({'object_id': 'p', 'kind': 'pin', 'name': 'u/A',
                             'attributes': {'direction': 'INPUT', 'geometry': [{'large': 'shape'}]}})
    pack['relations'] = [{'relation_id': 'r', 'subject_id': 'p', 'object_id': 'n', 'predicate': 'connected_to'}]
    store = DataStore(tmp_path / 'compact.sqlite')
    try:
        store.register(pack)
        result = list_objects(store, 's', {'ids': 'p,missing', 'fields': 'name,attributes.direction,attributes.signal_type,attributes.net_name'})
        assert result['found'] == 1 and result['missing_ids'] == ['missing']
        assert result['objects'] == [{'name': 'u/A', 'attributes': {'direction': 'INPUT', 'signal_type': 'SIGNAL', 'net_name': 'signal'}}]
    finally:
        store.close()


def test_path_routing_join_includes_upper_via_layer_and_excludes_unrelated_net(tmp_path):
    pack = sample()
    pack['physical_context'].extend([
        {'object_id': 'n', 'routing': [{'routing_type': 'segment', 'layer': 'metal1'},
          {'routing_type': 'via', 'bottom_layer': 'metal1', 'top_layer': 'metal2'}]},
        {'object_id': 'other', 'routing': [{'routing_type': 'segment', 'layer': 'metal10'}]}])
    store = DataStore(tmp_path / 'routing.sqlite')
    try:
        store.register(pack)
        result = path_engineering(store, 's', 'p', {'include_routing': '1', 'limit': '1'})
        assert result['routing_layers_crossed'] == ['metal1', 'metal2']
        assert timing_overview(store, 's', {'limit': '5'})['instance_names'] == ['u']
    finally:
        store.close()


def test_pin_statistics_share_inventory_filters_and_native_connected_classification(tmp_path):
    from openroad_app_data_foundation.engineering import object_statistics
    pack = sample()
    pack['entities'].extend([
        {'object_id': 'clk', 'kind': 'net', 'name': 'clk', 'attributes': {'signal_type': 'CLOCK'}},
        {'object_id': 'p', 'kind': 'pin', 'name': 'u/D', 'parent_id': 'i'},
        {'object_id': 'ck', 'kind': 'pin', 'name': 'u/CK', 'parent_id': 'i'},
        {'object_id': 'otherp', 'kind': 'pin', 'name': 'v/D', 'parent_id': 'other'}])
    pack['relations'] = [
        {'relation_id': 'r1', 'subject_id': 'p', 'object_id': 'n', 'predicate': 'connected_to'},
        {'relation_id': 'r2', 'subject_id': 'ck', 'object_id': 'clk', 'predicate': 'connected_to'},
        {'relation_id': 'r3', 'subject_id': 'otherp', 'object_id': 'n', 'predicate': 'connected_to'}]
    store = DataStore(tmp_path / 'stats.sqlite')
    try:
        store.register(pack)
        query = {'kind': 'pin', 'parent_id': 'i', 'group_by': 'signal_type'}
        result = object_statistics(store, 's', query)
        assert result['object_count'] == 2
        assert {r['value']: r['count'] for r in result['groups']} == {'CLOCK': 1, 'SIGNAL': 1}
        result = object_statistics(store, 's', {**query, 'signal_type': 'SIGNAL'})
        assert result['groups'] == [{'value': 'SIGNAL', 'count': 1}]
    finally:
        store.close()


def test_exact_name_filter_cannot_silently_return_all_nets(tmp_path):
    from openroad_app_data_foundation.discovery import list_objects
    pack = sample()
    pack['entities'].append({'object_id': 'other', 'kind': 'net', 'name': r'signal\[0\]', 'attributes': {}})
    store = DataStore(tmp_path / 'names.sqlite')
    try:
        store.register(pack)
        result = list_objects(store, 's', {'kind': 'net', 'name': 'signal[0]'})
        assert result['count'] == 1 and result['objects'][0]['object_id'] == 'other'
        with pytest.raises(ValueError, match='unknown object query fields'):
            list_objects(store, 's', {'kind': 'net', 'misspelled_name': 'signal[0]'})
    finally:
        store.close()


def test_point_extrema_keep_all_ties_and_singleton_without_clock_points(tmp_path):
    pack = sample()
    pack['timing_points'][0].update(slew=999, load=999)
    pack['timing_points'][1].update(slew=0.2, load=0.5)
    pack['timing_points'][2].update(slew=0.2, load=0.3)
    store = DataStore(tmp_path / 'maxima.sqlite')
    try:
        store.register(pack)
        result = path_engineering(store, 's', 'p', {'limit': '1'})['data_point_extrema']
        assert result['slew']['max_value'] == 0.2
        assert result['slew']['pin_names'] == ['u/A', 'u/Z']
        assert result['slew']['selected_point']['pin_name'] == 'u/Z'
        assert result['load']['pin_names'] == ['u/A']
        assert result['load']['tie_count'] == 1
        overview = timing_overview(store, 's', {'limit': '5'})
        assert overview['data_point_extrema']['slew']['pin_names'] == ['u/A', 'u/Z']
    finally:
        store.close()


def test_original_stage_inventory_does_not_confuse_missing_index_with_missing_file(tmp_path):
    from openroad_app_data_foundation.artifacts import run_inventory
    root = tmp_path / 'flow';result = root / 'results/p/chip/r';logs = root / 'logs/p/chip/r'
    result.mkdir(parents=True);logs.mkdir(parents=True)
    (result / '1_synth.odb').write_bytes(b'original synth')
    (logs / '1_synth.json').write_text(json.dumps({'synth__timing__setup__ws':0.1,'synth__design__instance__area':3}))
    pack=sample();pack['snapshot']['stage']='finish'
    store=DataStore(tmp_path/'inventory.sqlite')
    try:
        store.register(pack)
        data=run_inventory(store,'s',root)
        synth=data['stages'][0]
        assert synth['availability']=='available' and synth['indexed_snapshots']==[]
        assert synth['original_metrics']['key_count']==2
        assert synth['original_metrics']['has_timing'] and synth['original_metrics']['has_area']
        assert data['original_stage_count']==1
        assert data['stages'][-1]['availability']=='not_produced'
    finally:
        store.close()


def test_source_headers_keep_continued_configuration_actual_nominal_values_and_unique_times():
    from openroad_app_data_foundation.source_metadata import configuration, library_header, flow_timing
    text='export VERILOG_FILES = $(wildcard src/*.sv) \\\n  src/clock.sv\nexport DENSITY = 0.3\n'
    assert configuration(text)['variables']['VERILOG_FILES']=='$(wildcard src/*.sv) src/clock.sv'
    header=library_header('library (L) {\n time_unit : "1ns";\n capacitive_load_unit (1, ff);\n nom_voltage : 1.10;\n nom_temperature : 25.00;\n}')
    assert header['nominal_voltage']==1.1 and header['nominal_temperature']==25
    assert header['capacitive_load_unit']=='1,ff'
    log='1_synth .odb 3 100 abcdef01234567890123\n1_synth .sdc abcdef01234567890123\n1_synth .odb 3 100 abcdef01234567890123\n1_synth .sdc abcdef01234567890123\nTotal 3 100\n'
    times=flow_timing(log)
    assert len(times['stages'])==2 and times['unavailable_timing']==['1_synth.sdc']
    assert times['reported_total']=={'elapsed_s':3,'peak_mb':100}
