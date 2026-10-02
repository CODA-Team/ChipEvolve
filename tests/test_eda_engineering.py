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


def query_pair():
    from copy import deepcopy
    parent = sample()
    parent['snapshot']['source_artifacts'] = [{
        'artifact_id': 'odb', 'run_id': 'run', 'logical_path': 'inputs/design.odb',
        'category': 'raw_design_database', 'stage': 'finish', 'sha256': 'a' * 64, 'size_bytes': 1}]
    parent['entities'][2]['attributes'].update(fanout=1, driver_count=1)
    parent['entities'].extend([
        {'object_id': 'pin-a', 'kind': 'pin', 'name': 'u/A', 'attributes': {'direction': 'INPUT'}},
        {'object_id': 'pin-z', 'kind': 'pin', 'name': 'u/Z', 'attributes': {'direction': 'OUTPUT'}},
        {'object_id': 'clock-net', 'kind': 'net', 'name': 'clock',
         'attributes': {'signal_type': 'CLOCK', 'fanout': 99}}])
    parent['relations'] = [
        {'relation_id': 'a-n', 'subject_id': 'pin-a', 'predicate': 'connected_to', 'object_id': 'n'},
        {'relation_id': 'z-n', 'subject_id': 'pin-z', 'predicate': 'connected_to', 'object_id': 'n'},
        {'relation_id': 'n-a', 'subject_id': 'n', 'predicate': 'loads', 'object_id': 'pin-a'},
        {'relation_id': 'n-z', 'subject_id': 'n', 'predicate': 'driven_by', 'object_id': 'pin-z'}]
    child = deepcopy(parent)
    child['snapshot']['snapshot_id'] = 'child'
    child['run_summary'] = {'timing_context': {'parent_snapshot_id': 's'}}
    for kind in ('entities', 'physical_context', 'relations'):
        child[kind] = []
    child['timing_points'].append({
        'point_id': 'clock-net-data', 'path_id': 'p', 'ordinal': 3,
        'pin_name': 'u/CLK', 'instance_id': 'i', 'net_id': 'clock-net',
        'path_section': 'source_path'})
    return parent, child


def test_ranked_and_joined_native_timing_expose_same_explicit_ns_and_ff(tmp_path):
    from openroad_app_data_foundation.queries import list_timing_paths, list_timing_points
    pack = sample()
    pack['timing_paths'][0].update(slack=-2.022e-10, data_arrival_time=8.452e-10,
                                  required_time=6.43e-10, unit='s')
    pack['timing_points'][1].update(slew=4.668e-11, load=7.281e-15, arrival=8.452e-10)
    pack['timing_points'][2].update(slew=1e-11, load=1e-15, arrival=6.43e-10)
    store = DataStore(tmp_path / 'units.sqlite')
    try:
        store.register(pack)
        paths = list_timing_paths(store, 's', {'fields': 'path_id,slack_ns,arrival_ns,required_ns'})['timing_paths']
        assert paths[0]['slack_ns'] == pytest.approx(-0.2022)
        points = list_timing_points(store, 's', {'pin_name': 'u/A', 'fields': 'pin_name,slew_ns,load_ff'})['timing_points']
        assert points[0]['load_ff'] == pytest.approx(7.281)
        result = path_engineering(store, 's', 'p', {'limit': '1'})
        assert result['path']['arrival_ns'] == pytest.approx(0.8452)
        assert result['data_point_extrema']['load']['max_value_ff'] == pytest.approx(7.281)
        assert result['data_point_extrema']['slew']['max_value_ns'] == pytest.approx(0.04668)
        assert result['data_point_extrema']['load']['selected_point']['load_ff'] == pytest.approx(7.281)
        assert store.records('s', 'timing_paths', record_id='p')[0]['slack'] == -2.022e-10
        assert 'slack_ns' not in store.records('s', 'timing_paths', record_id='p')[0]
    finally:
        store.close()


def test_supplemental_path_joins_exact_parent_geometry_and_filters_signal_nets(tmp_path):
    parent, child = query_pair()
    store = DataStore(tmp_path / 'd.sqlite')
    try:
        store.register(parent)
        store.register(child)
        result = path_engineering(store, 'child', 'p', {'signal_type': 'SIGNAL', 'limit': '1'})
        assert result['snapshot']['snapshot_id'] == 'child'
        assert result['object_facts_source']['snapshot']['snapshot_id'] == 's'
        assert result['instance_bbox_union'] == parent['physical_context'][0]['bbox']
        assert result['dbu_per_micron'] == 2000
        assert result['instance_names'] == ['u']
        assert result['instance_bbox_union_um'] == {'x_min': 0, 'y_min': 0, 'x_max': 0.005, 'y_max': 0.01}
        assert result['master_counts'] == {'BUF': 1}
        assert result['net_names'] == ['signal'] and result['net_count'] == 1
        assert result['association_coverage']['status'] == 'complete'
        assert result['association_coverage']['unresolved_net_ids'] == []
        assert result['data_pin_names'] == ['u/A', 'u/Z', 'u/CLK']
    finally:
        store.close()


@pytest.mark.parametrize('mismatch', ['database', 'run', 'stage'])
def test_supplemental_path_never_joins_another_database_or_run(tmp_path, mismatch):
    parent, child = query_pair()
    if mismatch == 'database':
        child['snapshot']['source_artifacts'][0]['sha256'] = 'b' * 64
    else:
        child['snapshot']['run_id' if mismatch == 'run' else 'stage'] = 'other'
    store = DataStore(tmp_path / 'd.sqlite')
    try:
        store.register(parent)
        store.register(child)
        with pytest.raises(ValueError, match='different|same original database'):
            path_engineering(store, 'child', 'p', {})
    finally:
        store.close()


def test_fresh_join_imports_with_writer_and_reads_complete_facts_in_one_operation(tmp_path, monkeypatch):
    from openroad_app_data_foundation import resolved_timing
    from openroad_app_data_foundation.server import Handler
    parent, child = query_pair()
    store = DataStore(tmp_path / 'd.sqlite')
    store.register(parent)
    reader = DataStore(tmp_path / 'd.sqlite', read_only=True)
    calls = []
    def submit(writer, client, sid, query):
        assert writer is store and sid == 's'
        calls.append(query)
        return {'run': {'run_id': 'native-run'}, 'snapshot_id': 'child'}
    def status(writer, client, rid, wait):
        assert writer is store and rid == 'native-run' and wait == 120
        writer.register(child)
        return {'run_id': rid, 'status': 'succeeded', 'snapshot_ids': ['child'], 'terminal_reason': None}
    monkeypatch.setattr(resolved_timing, 'submit_timing_query', submit)
    monkeypatch.setattr(resolved_timing, 'timing_query_status', status)
    handler = Handler.__new__(Handler)
    handler.store, handler.execution_client, handler.auto_import = store, object(), False
    try:
        result = handler._get('/snapshots/s/timing-overview', {
            'resolve': '1', 'check': 'setup', 'startpoint': 'u/A', 'endpoint': 'u/Z', 'limit': '1',
            'signal_type': 'SIGNAL', 'include_physical': '1', 'include_path_details': '1',
            'include_connectivity': '1',
            'fields': 'paths,path_details.data_pin_names,instances,instance_bbox_union,net_names,nets'}, reader)
        assert calls == [{'path_count': 1, 'endpoint_path_count': 1, 'from_pin': 'u/A', 'to_pin': 'u/Z'}]
        assert result['query_execution']['status'] == 'succeeded'
        assert result['snapshot']['snapshot_id'] == 'child'
        assert result['object_facts_source']['snapshot']['snapshot_id'] == 's'
        assert result['path_details'][0]['data_pin_names'] == ['u/A', 'u/Z', 'u/CLK']
        assert result['nets'][0]['connectivity']['load_pins'] == ['u/A']
        assert result['nets'][0]['connectivity']['driver_pins'] == ['u/Z']
        assert result['instance_bbox_union'] == parent['physical_context'][0]['bbox']
        assert '/snapshots/child/timing-overview?' in result['delivery']['full_details']
        assert 'resolve=' not in result['delivery']['full_details']
    finally:
        reader.close()
        store.close()


@pytest.mark.parametrize('state', ['running', 'failed', 'timed_out'])
def test_fresh_join_exposes_pending_or_failed_native_job_without_sample_substitution(tmp_path, monkeypatch, state):
    from openroad_app_data_foundation import resolved_timing
    store = DataStore(tmp_path / 'd.sqlite')
    store.register(sample())
    monkeypatch.setattr(resolved_timing, 'submit_timing_query',
                        lambda *args: {'run': {'run_id': 'native-run'}, 'snapshot_id': 'child'})
    monkeypatch.setattr(resolved_timing, 'timing_query_status', lambda *args: {
        'run_id': 'native-run', 'status': state, 'snapshot_ids': [], 'terminal_reason': 'actual reason'})
    try:
        result = resolved_timing.resolved_timing_overview(store, store, object(), 's', {'wait_seconds': '0'})
        assert result['query_execution']['status'] == state
        assert 'paths' not in result
        assert result['availability']['fresh_path_facts']['reason'] == 'actual reason'
        assert result['availability']['fresh_path_facts']['status_query'].startswith('/timing-queries/native-run')
    finally:
        store.close()


def test_port_delay_counts_are_unique_direction_specific_and_include_undeclared_clock(tmp_path):
    pack = sample()
    pack['entities'] += [{'object_id': 'bterm:' + name, 'kind': 'pin', 'name': name,
                         'attributes': {'direction': direction}}
                        for name, direction in [('a', 'INPUT'), ('clk', 'INPUT'), ('z', 'OUTPUT'), ('io', 'INOUT')]]
    text = ('create_clock -name clk -period 2 [get_ports {clk}]\n'
            'set_input_delay 0.4 -max -clock [get_clocks {clk}] [get_ports {a}]\n'
            'set_input_delay 0.2 -min -clock [get_clocks {clk}] [get_ports {a}]\n'
            'set_output_delay 0.3 -clock [get_clocks {clk}] [get_ports {z}]\n')
    pack['snapshot']['source_artifacts'] = [{
        'artifact_id': 'sdc', 'run_id': 'run', 'logical_path': 'effective.sdc',
        'category': 'raw_constraints', 'stage': 'finish', 'sha256': 'a' * 64, 'size_bytes': len(text)}]
    class SourceClient:
        def artifact_excerpt(self, run_id, artifact_id, *, offset, max_bytes):
            return {'text': text[offset:offset + max_bytes]}
    store = DataStore(tmp_path / 'd.sqlite')
    try:
        store.register(pack)
        result = constraint_context(store, SourceClient(), 's', {})
        assert result['port_delay_coverage']['input_delay'] == {
            'direction': 'INPUT', 'port_count': 2, 'ports_with_explicit_delay_count': 1,
            'ports_without_explicit_delay_count': 1}
        assert result['port_delay_coverage']['output_delay']['port_count'] == 1
        assert result['ports_without_delay'] == {'input_delay': ['clk'], 'output_delay': []}
        assert result['other_port_directions'] == {'INOUT': 1}
        assert result['declaration_counts']['input_delay'] == 2
    finally:
        store.close()


def test_connected_instance_statistics_deduplicate_load_pins_and_preserve_group_types(tmp_path):
    from openroad_app_data_foundation.engineering import object_statistics
    pack, _ = query_pair()
    next(row for row in pack['entities'] if row['object_id'] == 'pin-a')['parent_id'] = 'i'
    pack['entities'] += [
        {'object_id': 'ram', 'kind': 'instance', 'name': 'ram',
         'attributes': {'master': 'SRAM', 'is_macro': 1}},
        {'object_id': 'ram-a', 'kind': 'pin', 'name': 'ram/A', 'parent_id': 'ram'},
        {'object_id': 'ram-b', 'kind': 'pin', 'name': 'ram/B', 'parent_id': 'ram'}]
    pack['relations'] += [{'relation_id': 'n-' + pin, 'subject_id': 'n',
                          'predicate': 'loads', 'object_id': pin} for pin in ('ram-a', 'ram-b')]
    store = DataStore(tmp_path / 'connected.sqlite')
    try:
        store.register(pack)
        query = {'kind': 'instance', 'connected_to': 'signal', 'net_role': 'load'}
        result = object_statistics(store, 's', {**query, 'is_macro': 'true'})
        assert result['object_count'] == 1
        assert result['groups'] == [{'value': 'instance', 'count': 1}]
        result = object_statistics(store, 's', {**query, 'group_by': 'is_macro'})
        assert result['object_count'] == 2
        assert {r['value']: r['count'] for r in result['groups']} == {0: 1, 1: 1}
        result = object_statistics(store, 's', {**query, 'group_by': 'master'})
        assert {r['value']: r['count'] for r in result['groups']} == {'BUF': 1, 'SRAM': 1}
    finally:
        store.close()


def test_instance_and_timing_join_retains_point_witness_and_complete_pin_counts(tmp_path):
    from openroad_app_data_foundation.engineering import instance_engineering
    pack = sample()
    pack['entities'][0]['attributes']['orientation'] = 'MX'
    pack['physical_context'][0].update(x=0, y=0)
    pack['entities'].extend([
        {'object_id': 'a', 'kind': 'pin', 'name': 'u/A', 'parent_id': 'i'},
        {'object_id': 'z', 'kind': 'pin', 'name': 'u/Z', 'parent_id': 'i'},
        {'object_id': 'unconnected', 'kind': 'pin', 'name': 'u/NC', 'parent_id': 'i'}])
    pack['relations'] = [{'relation_id': key, 'subject_id': key, 'object_id': 'n',
                          'predicate': 'connected_to'} for key in ('a', 'z')]
    pack['timing_points'][1].update(load=1, evidence=[{'artifact_id': 'report'}])
    pack['timing_points'][2].update(load=2, evidence=[{'artifact_id': 'report', 'detail': {'point': 2}}])
    store = DataStore(tmp_path / 'd.sqlite')
    try:
        store.register(pack)
        instance = instance_engineering(store, 's', 'u')['instance']
        assert instance['signal_pin_count'] == 2
        assert instance['distinct_signal_net_count'] == 1
        assert instance['distinct_connected_net_count'] == 1
        assert instance['total_pin_count'] == 3 and instance['unclassified_pin_count'] == 1
        from openroad_app_data_foundation.discovery import list_objects
        pins = list_objects(store, 's', {'kind': 'pin', 'parent_instance': 'u', 'signal_type': 'SIGNAL',
                                        'fields': 'name,attributes.net_name'})
        assert [row['name'] for row in pins['objects']] == ['u/A', 'u/Z']
        with pytest.raises(KeyError, match='instance not found'):
            list_objects(store, 's', {'kind': 'pin', 'parent_instance': 'absent-instance'})
        assert instance['orientation_names'] == {'odb': 'MX', 'def': 'FS'}
        result = timing_overview(store, 's', {'check': 'setup', 'limit': '1', 'include_physical': '1',
                                            'fields': 'paths,data_point_extrema'})
        point = result['data_point_extrema']['load']['selected_point']
        assert point['point_id'] == 'out' and point['load'] == 2
        assert point['evidence'][0]['detail']['point'] == 2
        assert point['instance'] == instance
        assert result['association_coverage']['status'] == 'complete'
    finally:
        store.close()


def test_missing_point_net_association_never_claims_full_domain_ranking(tmp_path):
    from openroad_app_data_foundation.envelope import envelope
    pack = sample()
    pack['timing_points'][2].pop('net_id')
    pack['timing_points'][2].update(net_name='missing-native-net', mapping_status='unmapped')
    store = DataStore(tmp_path / 'd.sqlite')
    try:
        store.register(pack)
        result = path_engineering(store, 's', 'p', {'limit': '1'})
        assert result['association_coverage']['status'] == 'partial'
        assert result['association_coverage']['unresolved_point_ids'] == ['out']
        assert result['association_coverage']['ranking_scope'] == 'resolved nets only'
        view = envelope('/snapshots/s/timing-paths/p/engineering', {}, result)
        # Pagination remains visible and coverage never changes to complete.
        assert view['data']['availability']['complete_association_aggregates']['status'] == 'unavailable'
        overview = timing_overview(store, 's', {'limit': '1'})
        assert overview['association_coverage']['incomplete_path_ids'] == ['p']
    finally:
        store.close()


def test_object_provenance_joins_only_its_actual_digest_and_native_locator(tmp_path):
    from openroad_app_data_foundation.evidence import object_provenance
    pack = sample()
    pack['snapshot']['source_artifacts'] = [{'artifact_id': 'odb', 'category': 'raw_design_database',
        'logical_path': 'inputs/design.odb', 'sha256': 'a' * 64, 'run_id': 'extract', 'stage': 'main'}]
    pack['entities'][0].update(locator={'native_id': '1'}, evidence=[{
        'artifact_id': 'odb', 'logical_path': 'inputs/design.odb', 'source_type': 'opendb', 'locator': {'native_id': '1'}}])
    pack['run_summary']['timing_context'] = {'producer': {'native_run_id': 'original-flow',
        'artifacts': {'results/original.odb': {'sha256': 'a' * 64}, 'results/other.odb': {'sha256': 'b' * 64}}}}
    store = DataStore(tmp_path / 'provenance.sqlite')
    try:
        store.register(pack)
        result = object_provenance(store, 's', 'u', 'instance')
        assert result['object']['locator'] == {'native_id': '1'}
        assert result['sources'][0]['original_paths'] == ['results/original.odb']
        assert result['sources'][0]['sha256'] == 'a' * 64
        assert result['producer_identity']['native_run_id'] == 'original-flow'
        assert result['record_sources']['evidence_path'].endswith('/records/entities/i/evidence')
        assert result['extraction_identity'][0]['source_type'] == 'opendb'
        assert result['native_locators'][0]['object_key'] == 'u'
        assert result['native_locators'][0]['artifact_sha256'] == 'a' * 64
    finally:
        store.close()


def test_net_traversal_walks_actual_pages_and_verifies_complete_identity_order(tmp_path):
    from openroad_app_data_foundation.engineering import net_engineering
    pack = sample()
    names = ['u/Z', 'u/A10', 'u/A2', 'u/B', 'u/C']
    pack['entities'][2]['attributes']['fanout'] = len(names)
    pack['entities'].extend({'object_id': str(i), 'name': name, 'kind': 'pin'} for i, name in enumerate(names))
    pack['relations'] = [{'relation_id': str(i), 'subject_id': 'n', 'object_id': str(i), 'predicate': 'loads'}
                         for i in range(len(names))]
    store = DataStore(tmp_path / 'traversal.sqlite')
    try:
        store.register(pack)
        result = net_engineering(store, 's', 'n', {'traverse': '1', 'limit': '2'})
        walk = result['load_traversal']
        assert walk['completed'] and walk['ordering_verified']
        assert walk['returned_count'] == walk['unique_object_count'] == walk['total_count'] == result['load_count']
        assert walk['missing_object_count'] == walk['duplicate_object_count'] == 0
        assert walk['pages_read'] == 3
        assert [page['offset'] for page in walk['pages']] == [0, 2, 4]
        assert walk['pin_names'] == sorted(names)
        assert walk['first_page'] == sorted(names)[:2] and walk['last_page'] == sorted(names)[4:]
        assert result['driver_traversal']['completed'] and result['driver_traversal']['total_count'] == 0
    finally:
        store.close()


def test_named_net_loads_count_distinct_instances_across_pages_and_exclude_ports(tmp_path):
    from openroad_app_data_foundation.discovery import list_objects
    from openroad_app_data_foundation.engineering import net_engineering
    pack = sample()
    pins = [('p1', 'u/A', 'i'), ('p2', 'u/B', 'i'),
            ('p3', 'clock_buf/A', 'c'), ('bterm:out', 'out', None)]
    pack['entities'][2]['attributes']['fanout'] = len(pins)
    pack['entities'].extend({'object_id': key, 'name': name, 'kind': 'pin', 'parent_id': parent}
                           for key, name, parent in pins)
    pack['relations'] = [{'relation_id': key, 'subject_id': 'n', 'object_id': key, 'predicate': 'loads'}
                         for key, _, _ in pins]
    store = DataStore(tmp_path / 'named-loads.sqlite')
    try:
        store.register(pack)
        by_name = list_objects(store, 's', {'kind': 'pin', 'connected_to': 'signal',
                                           'net_role': 'load', 'limit': '100', 'fields': 'name'})
        assert [p['name'] for p in by_name['objects']] == sorted(name for _, name, _ in pins)
        result = net_engineering(store, 's', 'signal', {'traverse': '1', 'limit': '1'})
        assert result['load_traversal']['pages_read'] == len(pins)
        assert result['load_traversal']['internal_instance_count'] == 2
        assert result['load_traversal']['pin_names'] == sorted(name for _, name, _ in pins)
        assert result['driver_traversal']['internal_instance_count'] == 0
        with pytest.raises(KeyError, match='net not found'):
            list_objects(store, 's', {'kind': 'pin', 'connected_to': 'u', 'net_role': 'load'})
    finally:
        store.close()


def test_joined_net_pages_restore_all_named_loads_and_keep_multi_driver_state(tmp_path):
    from openroad_app_data_foundation.engineering import net_engineering
    pack = sample()
    pack['entities'][2]['attributes']['driver_count'] = 2
    pack['entities'].extend({'object_id': name, 'name': name, 'kind': 'pin'}
                            for name in ('d1', 'd2', 'a', 'b', 'c0'))
    pack['relations'] = [{'relation_id': name, 'subject_id': 'n', 'object_id': name,
                          'predicate': 'driven_by' if name.startswith('d') else 'loads'}
                         for name in ('d1', 'd2', 'a', 'b', 'c0')]
    store = DataStore(tmp_path / 'd.sqlite')
    try:
        store.register(pack)
        first = net_engineering(store, 's', 'signal', {'limit': '2'})
        second = net_engineering(store, 's', 'n', {'limit': '2', 'offset': '2'})
        assert first['state'] == second['state'] == 'multi_driver'
        assert first['driver_pins'] == ['d1', 'd2'] and first['driver_count'] == 2
        assert first['load_pins'] + second['load_pins'] == ['a', 'b', 'c0']
        assert first['load_count'] == second['load_count'] == 3
        assert first['load_page']['next_offset'] == 2
        assert not second['load_page']['truncated']
    finally:
        store.close()


def test_inventory_comparison_keeps_native_counts_and_original_substage_values_separate(tmp_path):
    from copy import deepcopy
    from openroad_app_data_foundation.engineering import compare_inventory
    root = tmp_path / 'flow'
    logs = root / 'logs/platform/chip/r'
    logs.mkdir(parents=True)
    (logs / '5_1_grt.json').write_text(json.dumps({'globalroute__design__instance__area': 85}))
    (logs / '5_2_route.json').write_text(json.dumps({'detailedroute__route__drc_errors': 0}))
    (logs / '6_report.json').write_text(json.dumps({'finish__design__instance__area': 86}))
    left = sample();left['snapshot']['snapshot_id'] = 'left';left['snapshot']['stage'] = 'route'
    right = deepcopy(left);right['snapshot']['snapshot_id'] = 'right';right['snapshot']['stage'] = 'finish'
    right['entities'].append({'object_id': 'new', 'kind': 'instance', 'name': 'new'})
    store = DataStore(tmp_path / 'd.sqlite')
    try:
        store.register(left);store.register(right)
        result = compare_inventory(store, 'left', 'right', {'metrics': 'instance__area'}, root)
        assert result['deltas']['instance_count'] == 1
        assert result['deltas']['signal_net_count'] == 0
        assert result['from']['original_metric_reports'][0]['metric_values'][0]['value'] == 85
        assert result['from']['original_metric_reports'][1]['metric_values'] == []
        assert result['to']['original_metric_reports'][0]['metric_values'][0]['value'] == 86
    finally:
        store.close()


def test_native_area_comparison_does_not_relabel_earlier_report_values(tmp_path, monkeypatch):
    from copy import deepcopy
    from openroad_app_data_foundation.engineering import compare_inventory
    left = sample(); left['snapshot']['snapshot_id'] = 'left'
    right = deepcopy(left); right['snapshot']['snapshot_id'] = 'right'
    def actual_area(store, client, sid, root):
        return {'status': 'succeeded', 'value': 85 if sid == 'left' else 99,
                'evidence': [{'artifact_id': 'actual-' + sid}]}
    monkeypatch.setattr('openroad_app_data_foundation.native_inventory.design_area', actual_area)
    store = DataStore(tmp_path / 'area.sqlite')
    try:
        store.register(left); store.register(right)
        result = compare_inventory(store, 'left', 'right', {'include_native_area': '1'}, tmp_path, object())
        assert result['deltas']['native_area_um2'] == 14
        assert result['to']['native_area']['evidence'] == [{'artifact_id': 'actual-right'}]
    finally:
        store.close()


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


def test_pin_timing_filters_do_not_return_an_unrelated_or_wrong_check_point(tmp_path):
    from openroad_app_data_foundation.queries import list_timing_points
    pack = sample()
    pack['timing_paths'].append({'path_id':'h','check':'hold','slack':0,'unit':'s'})
    pack['timing_points'].append({'point_id':'hold-in','path_id':'h','pin_name':'u/A',
                                 'instance_id':'i','net_id':'n','path_section':'source_path','slew':2})
    store = DataStore(tmp_path / 'd.sqlite')
    try:
        store.register(pack)
        setup = list_timing_points(store,'s',{'pin_name':'u/A','check':'setup'})
        assert setup['count'] == 1 and setup['timing_points'][0]['path_id'] == 'p'
        both = list_timing_points(store,'s',{'pin_name':'u/A'})
        assert both['count'] == 2
        assert list_timing_points(store,'s',{'pin_name':'missing'})['count'] == 0
        with pytest.raises(ValueError,match='unknown timing point query fields'):
            list_timing_points(store,'s',{'pin':'u/A'})
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


def test_canonical_metrics_keep_every_literal_corner_and_unqualified_aggregate(tmp_path):
    from openroad_app_data_foundation.queries import list_metrics_for_run
    pack = sample()
    pack['observations'] = [
        {'observation_id': 'metric:finish__timing__setup__ws', 'kind': 'metric', 'value': -0.2},
        {'observation_id': 'metric:finish__timing__setup__ws__corner:slow', 'kind': 'metric', 'value': -0.2},
        {'observation_id': 'metric:finish__timing__setup__ws__corner:fast', 'kind': 'metric', 'value': 0.3}]
    store = DataStore(tmp_path / 'corners.sqlite')
    try:
        store.register(pack)
        all_rows = list_metrics_for_run(store, 'run', {'name': 'WNS'})['metrics']
        assert len(all_rows) == 3
        assert {row['corner']: row['value'] for row in all_rows} == {None: -0.2, 'slow': -0.2, 'fast': 0}
        assert len({row['raw_key'] for row in all_rows}) == 3
        selected = list_metrics_for_run(store, 'run', {'name': 'WS', 'corner': 'fast'})['metrics']
        assert len(selected) == 1 and selected[0]['value'] == 0.3
        assert selected[0]['corner_basis'] == 'literal raw-key component'
    finally:
        store.close()


def test_engineering_counts_unique_data_instances_not_clock_buffers(tmp_path):
    store = DataStore(tmp_path / 'd.sqlite')
    try:
        store.register(sample())
        detail = path_engineering(store, 's', 'p', {'limit': '1'})
        assert detail['instance_count'] == 1
        assert detail['data_path_pin_count'] == 2
        assert detail['data_pin_names'] == ['u/A', 'u/Z']
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
    pack['run_summary']['timing_context'] = {
        'constraints': 'inputs/constraints.sdc', 'producer': {'artifacts': {
            'results/p/chip/r/6_final.sdc': {'sha256': 'b' * 64},
            'results/p/chip/r/4_cts.sdc': {'sha256': 'c' * 64}}}}
    pack['snapshot']['source_artifacts'].append({
        'artifact_id': 'input-sdc', 'logical_path': 'inputs/constraints.sdc', 'sha256': 'b' * 64,
        'run_id': 'run', 'size_bytes': 1, 'category': 'raw_constraints', 'stage': 'finish'})
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
        assert data['original_constraints'][0]['original_paths'] == ['results/p/chip/r/6_final.sdc']
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
        assert routing_summary(store, 's', 'signal') == result
        with pytest.raises(KeyError, match='net not found'):
            routing_summary(store, 's', 'unknown-native-net')
        assert result['via_count'] == 2
        assert result['via_distribution_by_layer'] == {'metal1': 1, 'metal2': 2, 'metal3': 1}
        assert result['segment_layers'] == ['metal2']
        assert result['via_layers'] == ['metal1','metal2','metal3']
        assert result['routing_layers_used'] == ['metal1','metal2','metal3']
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


def test_tool_versions_are_literal_banners_not_source_commit_guesses():
    from openroad_app_data_foundation.source_metadata import reported_versions
    text = ('Yosys 0.68+post (git sha1 UNKNOWN, Release)\n'
            'Launching OpenROAD source commit c487fc7086\n'
            'KLayout 0.30.12\nYosys 0.68+post (git sha1 UNKNOWN, Release)\n')
    rows = reported_versions(text)
    assert rows == [
        {'tool': 'Yosys', 'version_text': '0.68+post (git sha1 UNKNOWN, Release)',
         'original_line': 'Yosys 0.68+post (git sha1 UNKNOWN, Release)', 'line_numbers': [1, 4]},
        {'tool': 'KLayout', 'version_text': '0.30.12', 'original_line': 'KLayout 0.30.12', 'line_numbers': [3]}]


def test_violation_nets_link_to_same_snapshot_and_preserve_unresolved_history(tmp_path):
    from openroad_app_data_foundation.artifacts import violations
    from openroad_app_data_foundation.discovery import list_objects
    root = tmp_path / 'flow'
    reports = root / 'reports/p/chip/r'
    reports.mkdir(parents=True)
    (reports / '5_route_drc.rpt').write_text('')
    (reports / '5_route_drc.rpt-5.rpt').write_text(
        'violation type: Short\n\tsrcs: net:signal net:removed inst:u\n'
        '\tbbox = (1.0, 2.0) - (3.0, 4.0) on Layer metal2\n')
    store = DataStore(tmp_path / 'violations.sqlite')
    try:
        store.register(sample())
        data = violations(store, 's', {'limit': '1'}, root)
        record = data['records']['items'][0]
        assert record['sources'] == ['net:signal', 'net:removed', 'inst:u']
        assert record['nets'] == ['signal', 'removed']
        current, missing = record['net_objects']
        assert current['status'] == 'available'
        object_id = current['matches'][0]['object_id']
        assert list_objects(store, 's', {'ids': object_id})['objects'][0]['name'] == 'signal'
        assert missing == {'name': 'removed', 'status': 'not_present_in_snapshot', 'matches': []}
        assert data['coordinate_unit'] == 'um'
        assert next(f for f in data['files'] if f['is_final_report'])['violation_count'] == 0
        assert data['violation_count'] == 1
    finally:
        store.close()


def test_connected_pin_pages_are_complete_in_native_name_order(tmp_path):
    from openroad_app_data_foundation.discovery import list_objects
    pack = sample()
    pack['relations'] = []
    for index, name in enumerate(['z/A', 'a/A', 'm/A']):
        oid = f'pin-{index}'
        pack['entities'].append({'object_id': oid, 'kind': 'pin', 'name': name,
                                 'attributes': {'direction': 'INPUT'}})
        pack['relations'].append({'relation_id': f'connection-{index}', 'subject_id': oid,
                                  'predicate': 'connected_to', 'object_id': 'n'})
        pack['relations'].append({'relation_id': f'load-{index}', 'subject_id': 'n',
                                  'predicate': 'loads', 'object_id': oid})
    store = DataStore(tmp_path / 'connections.sqlite')
    try:
        store.register(pack)
        first = list_objects(store, 's', {'kind': 'pin', 'connected_to': 'n', 'net_role': 'load', 'limit': '2'})
        last = list_objects(store, 's', {'kind': 'pin', 'connected_to': 'n', 'net_role': 'load', 'offset': '2'})
        assert [p['name'] for p in first['objects'] + last['objects']] == ['a/A', 'm/A', 'z/A']
        assert first['count'] == 3 and first['next_offset'] == 2 and last['next_offset'] is None
        assert first['order'] == 'name'
        assert list_objects(store, 's', {'kind': 'instance'})['order'] == 'stored'
    finally:
        store.close()


def test_original_metric_filter_and_continuation_respect_source_scope(tmp_path):
    from openroad_app_data_foundation.queries import list_metrics_for_run
    pack = sample()
    pack['observations'] = [{'observation_id': f'metric:finish__custom_{i}', 'kind': 'metric',
                             'value': i, 'context': {'scene': 'original'}} for i in range(5)]
    other = sample()
    other['snapshot']['snapshot_id'] = 'other'
    other['snapshot']['stage'] = 'route'
    other['observations'] = [{'observation_id': 'metric:finish__custom_3', 'kind': 'metric',
                              'value': 999, 'context': {'scene': 'other-scene'}}]
    store = DataStore(tmp_path / 'metrics.sqlite')
    try:
        store.register(pack)
        store.register(other)
        one = list_metrics_for_run(store, 'run', {'include_raw': '1', 'snapshot_id': 's',
                                                  'name': 'finish__custom_3', 'scene': 'original'})
        assert [r['value'] for r in one['raw_metrics']] == [3]
        assert one['raw_metric_count'] == 1 and not one['truncated']
        wrong = list_metrics_for_run(store, 'run', {'include_raw': '1', 'snapshot_id': 's',
                                                    'name': 'finish__custom_3', 'scene': 'other-scene'})
        assert wrong['raw_metrics'] == []
        first = list_metrics_for_run(store, 'run', {'include_raw': '1', 'stage': 'finish', 'limit': '2'})
        last = list_metrics_for_run(store, 'run', {'include_raw': '1', 'stage': 'finish', 'limit': '2', 'offset': '4'})
        assert first['raw_metric_count'] == 5 and first['truncated'] and first['next_offset'] == 2
        assert last['raw_metrics_page']['returned'] == 1 and last['next_offset'] is None
        assert last['raw_metrics'][0]['value'] == 4
    finally:
        store.close()


def test_normalized_cell_counts_and_areas_keep_report_basis_and_original_keys(tmp_path):
    pack = sample()
    values = {'design__instance__count__stdcell': 17, 'design__instance__count__macros': 2,
              'design__instance__area': 85, 'design__instance__area__stdcell': 30,
              'design__instance__area__macros': 55, 'flow__platform__distance_units': '1um'}
    pack['observations'] = [{'observation_id': 'metric:finish__' + k, 'kind': 'metric', 'value': v}
                            for k, v in values.items()]
    store = DataStore(tmp_path / 'normalized.sqlite')
    try:
        store.register(pack)
        rows = {r['name']: r for r in project_run(store, [store.snapshot('s')])['metrics']}
        assert rows['STDCELL_COUNT']['value'] == 17 and rows['STDCELL_COUNT']['unit'] == 'count'
        assert rows['MACRO_COUNT']['value'] == 2
        assert rows['AREA']['value'] == 85 and rows['AREA']['unit'] == 'um^2'
        assert rows['STDCELL_AREA']['value'] == 30 and rows['MACRO_AREA']['value'] == 55
        assert 'not die/core' in rows['AREA']['quantity_scope']
        assert rows['STDCELL_COUNT']['raw_key'] == 'finish__design__instance__count__stdcell'
        assert all(r['authoritative_source'] == 'orfs_stage_report' for r in rows.values()
                   if r['status'] == 'available')
    finally:
        store.close()


def test_failed_native_query_exposes_actual_error_without_claiming_success():
    from openroad_app_data_foundation.native_queries import native_query_result
    class Client:
        def run(self, run_id):
            return {'project_id': 'eda-ai-native-query', 'status': 'failed', 'terminal_reason': 'report_error',
                    'stages': [{'attempts': [{'failure': {'category': 'report_error', 'message': 'exit 1'}}]}]}
        def artifacts(self, run_id):
            return [{'artifact_id': 'native-error', 'kind': 'analysis_report', 'metadata': {'report': 'native'}}]
        def artifact_excerpt(self, run_id, artifact_id, **kwargs):
            return {'text': 'invalid command name dbITerm_getBox', 'truncated': False}
    result = native_query_result(Client(), 'failed-run', {})
    assert result['status'] == 'failed' and result['terminal_reason'] == 'report_error'
    assert result['excerpt']['text'] == 'invalid command name dbITerm_getBox'
    assert result['failure_details'][0]['message'] == 'exit 1'


def test_bad_projection_preserves_completed_query_address_and_does_not_require_resubmission(tmp_path, monkeypatch):
    from openroad_app_data_foundation import resolved_timing
    from openroad_app_data_foundation.server import Handler
    parent, child = query_pair()
    store = DataStore(tmp_path / 'd.sqlite')
    store.register(parent)
    store.register(child)
    submitted = []
    def submit(*args):
        submitted.append('native-run')
        return {'run': {'run_id': 'native-run'}, 'snapshot_id': 'child'}
    monkeypatch.setattr(resolved_timing, 'submit_timing_query', submit)
    monkeypatch.setattr(resolved_timing, 'timing_query_status', lambda *args: {
        'run_id': 'native-run', 'status': 'succeeded', 'snapshot_ids': ['child'], 'terminal_reason': None})
    handler = Handler.__new__(Handler)
    handler.store, handler.execution_client, handler.auto_import = store, object(), False
    try:
        with pytest.raises(ValueError, match='unknown metadata field: path_details.master_occurrences') as error:
            handler._get('/snapshots/s/timing-overview', {
                'resolve': '1', 'limit': '1', 'include_path_details': '1',
                'fields': 'path_details.master_occurrences'})
        assert 'native query native-run already succeeded' in str(error.value)
        assert '/snapshots/child/timing-overview?' in str(error.value)
        assert 'resolve=' not in str(error.value)
        result = handler._get('/snapshots/child/timing-overview', {
            'check': 'setup', 'limit': '1', 'include_path_details': '1',
            'fields': 'path_details.master_counts,path_details.instance_names'})
        assert result['path_details'][0]['master_counts'] == {'BUF': 1}
        assert result['path_details'][0]['instance_names'] == ['u']
        assert submitted == ['native-run']
    finally:
        store.close()


def test_path_engineering_and_overview_return_actual_arrival_without_rounded_subtraction(tmp_path):
    pack = sample()
    pack['timing_paths'][0].update(required_time=0.4, data_arrival_time=0.199)
    store = DataStore(tmp_path / 'd.sqlite')
    try:
        store.register(pack)
        detail = path_engineering(store, 's', 'p', {})
        overview = timing_overview(store, 's', {'check': 'setup', 'limit': '1'})
        for path in (detail['path'], overview['paths'][0]):
            assert path['data_arrival_time'] == 0.199
            assert path['data_arrival_time'] != path['required_time'] - path['slack']
    finally:
        store.close()


def test_large_inventory_grouping_uses_narrow_indexes_and_keeps_missing_classifications(tmp_path):
    from openroad_app_data_foundation.engineering import object_statistics
    pack = sample()
    pack['entities'].extend([
        {'object_id': 'macro', 'kind': 'instance', 'name': 'ram', 'attributes': {'is_macro': 1}},
        {'object_id': 'clknet', 'kind': 'net', 'name': 'clk', 'attributes': {'signal_type': 'CLOCK'}},
        {'object_id': 'untyped', 'kind': 'net', 'name': 'unknown', 'attributes': {}}])
    store = DataStore(tmp_path / 'indexed.sqlite')
    try:
        store.register(pack)
        for kind, group, index, expected in [
            ('instance', 'is_macro', 'records_instance_statistics', {None: 1, 0: 1, 1: 1}),
            ('net', 'signal_type', 'records_net_statistics', {None: 1, 'SIGNAL': 1, 'CLOCK': 1})]:
            result = object_statistics(store, 's', {'kind': kind, 'group_by': group})
            assert {row['value']: row['count'] for row in result['groups']} == expected
            assert result['object_count'] == 3
            expression = f"json_extract(payload, '$.attributes.{group}')"
            sql = f"SELECT {expression}, COUNT(*) FROM records WHERE snapshot_id = ? AND record_type = 'entities' AND json_extract(payload, '$.kind') = ? GROUP BY {expression}"
            plan = store.connection.execute('EXPLAIN QUERY PLAN ' + sql, ('s', kind)).fetchall()
            assert any(index in row['detail'] for row in plan)
    finally:
        store.close()
