"""Original metric families and file declarations must remain complete and literal."""
import json

from openroad_app_data_foundation.artifacts import run_inventory, native_files
from openroad_app_data_foundation.queries import list_metrics_for_run
from openroad_app_data_foundation.repository import DataStore
from tests.test_eda_engineering import sample


def test_metric_namespace_selector_keeps_all_corners_and_source_units(tmp_path):
    root = tmp_path / 'flow'
    logs = root / 'logs/p/chip/r'
    logs.mkdir(parents=True)
    metrics = {'finish__timing__hold__ws__corner:slow': -.1,
               'finish__timing__hold__ws__corner:fast': -.2,
               'finish__timing__hold__tns': -1,
               'finish__timing__setup__ws': 1,
               'finish__custom__placeholder': 4,
               'finish__flow__platform__time_units': '1ns'}
    (logs / '6_report.json').write_text(json.dumps(metrics))
    store = DataStore(tmp_path / 'metric.sqlite')
    try:
        store.register(sample())
        for selector, expected_count in [('hold', 3), ('hold__ws', 2), ('hold__tns', 1),
                                         ('finish__timing__hold__tns', 1), ('place', 0)]:
            result = run_inventory(store, 's', root, stage='finish', metric_names=(selector,))
            report = result['stages'][0]['original_metrics']
            assert len(report['metric_values']) == expected_count
            assert all(row['value'] == metrics[row['raw_key']] for row in report['metric_values'])
            assert report['unit_declarations'] == {'finish__flow__platform__time_units': '1ns'}
        full = run_inventory(store, 's', root, stage='finish')
        assert 'metric_values' not in full['stages'][0]['original_metrics']
    finally:
        store.close()


def test_file_inventory_returns_declared_digest_without_claiming_current_verification(tmp_path):
    root = tmp_path / 'flow'
    results = root / 'results/p/chip/r'
    results.mkdir(parents=True)
    (results / '6_final.odb').write_bytes(b'current bytes')
    (results / 'extra.txt').write_bytes(b'not in manifest')
    pack = sample()
    declared = {'sha256': 'a' * 64, 'size_bytes': 999}
    pack['run_summary']['timing_context'] = {'producer': {'artifacts': {
        'results/p/chip/r/6_final.odb': declared}}}
    store = DataStore(tmp_path / 'file.sqlite')
    try:
        store.register(pack)
        compact = native_files(store, 's', {'kind': 'results'}, root)
        files = native_files(store, 's', {'kind': 'results', 'detail': 'full'}, root)
        assert [i['relative_path'] for i in compact['files']['items']] == [i['relative_path'] for i in files['files']['items']]
        assert compact['files']['count'] == files['files']['count'] == 2
        assert all('producer_manifest_entry' not in i for i in compact['files']['items'])
        assert 'kind=results' in compact['delivery']['full_details'] and 'detail=full' in compact['delivery']['full_details']
        items = {item['relative_path'].rsplit('/', 1)[-1]: item for item in files['files']['items']}
        assert items['6_final.odb']['size_bytes'] == len(b'current bytes')
        assert items['6_final.odb']['producer_manifest_entry'] == declared
        assert items['extra.txt']['producer_manifest_entry'] is None
        assert 'literal original producer declaration' in files['digest_basis']
        projected = native_files(store, 's', {'kind': 'results', 'fields': 'files.items.relative_path,files.items.producer_manifest_entry'}, root)
        assert projected['files']['items'][0]['producer_manifest_entry'] == declared
    finally:
        store.close()


def test_canonical_metric_case_is_flexible_but_raw_key_case_remains_literal(tmp_path):
    pack = sample()
    pack['observations'] = [{'kind': 'metric', 'observation_id': 'metric:finish__timing__setup__ws', 'value': .25},
        {'kind': 'metric', 'observation_id': 'metric:finish__custom__case', 'value': 7}]
    store = DataStore(tmp_path / 'case.sqlite')
    try:
        store.register(pack)
        named = list_metrics_for_run(store, 'run', {'names': 'ws,wns', 'fields': 'name,value'})
        assert named['missing_names'] == [] and {row['name'] for row in named['metrics']} == {'WS', 'WNS'}
        one = list_metrics_for_run(store, 'run', {'name': 'wns'})
        assert len(one['metrics']) == 1 and one['metrics'][0]['value'] == 0
        raw = list_metrics_for_run(store, 'run', {'name': 'finish__custom__CASE', 'include_raw': '1'})
        assert raw['raw_metrics'] == []
    finally:
        store.close()


def test_original_stage_inventory_separates_temporary_query_indexes(tmp_path):
    store = DataStore(tmp_path / 'scopes.sqlite')
    original = sample()
    derived = sample()
    derived['snapshot']['snapshot_id'] = 'query-result'
    derived['run_summary']['timing_context'] = {'parent_snapshot_id': 's'}
    named_query = sample()
    named_query['snapshot']['snapshot_id'] = 's-query-012345abcdef'
    try:
        store.register(original)
        store.register(derived)
        store.register(named_query)
        inventory = run_inventory(store, 's', tmp_path / 'flow', stage='finish')
        assert inventory['stages'][0]['indexed_snapshots'] == ['s']
        assert inventory['additional_query_snapshot_count'] == 2
        assert inventory['additional_query_snapshots_path'] == '/snapshots?run_id=run'
        assert store.snapshot('query-result')['snapshot_id'] == 'query-result'
    finally:
        store.close()


def test_original_metric_substrings_keep_full_names_values_corners_and_substages(tmp_path):
    root = tmp_path / 'flow'
    logs = root / 'logs/p/chip/r'
    logs.mkdir(parents=True)
    original = {'globalroute__global_route__fastroute__overflow_iterations_s': [1, 0],
                'globalroute__custom__overflow__corner:slow': 2,
                'globalroute__route__vias': 7,
                'globalroute__flow__platform__time_units': '1ns'}
    (logs / '5_1_grt.json').write_text(json.dumps(original))
    (logs / '5_2_route.json').write_text(json.dumps({'detailedroute__route__vias': 8}))
    store = DataStore(tmp_path / 'substring.sqlite')
    try:
        store.register(sample())
        result = run_inventory(store, 's', root, stage='route', metric_names=('vias',),
                               metric_contains=('OVERFLOW',))
        reports = result['stages'][0]['metric_reports']
        first = {row['raw_key']: row['value'] for row in reports[0]['metric_values']}
        assert first == {key: value for key, value in original.items() if 'overflow' in key or 'vias' in key}
        assert reports[0]['unit_declarations'] == {'globalroute__flow__platform__time_units': '1ns'}
        assert reports[1]['metric_values'][0]['value'] == 8
        assert reports[1]['metric_values'][0]['source'].endswith('/5_2_route.json')
    finally:
        store.close()


def test_line_range_reads_original_positions_and_exposes_partial_continuation(tmp_path):
    from openroad_app_data_foundation.artifacts import native_excerpt
    import pytest
    root = tmp_path / 'flow'
    logs = root / 'logs/p/chip/r'
    logs.mkdir(parents=True)
    lines = [f'row {i} \n'.encode() for i in range(1, 151)]
    (logs / 'large.log').write_bytes(b''.join(lines))
    store = DataStore(tmp_path / 'lines.sqlite')
    try:
        store.register(sample())
        query = {'path': 'logs/p/chip/r/large.log', 'start_line': '101', 'end_line': '103', 'max_bytes': '100'}
        result = native_excerpt(store, 's', query, root)
        assert result['text'].encode() == b''.join(lines[100:103])
        assert result['offset'] == len(b''.join(lines[:100]))
        assert result['range_complete'] and result['line_end'] == 103
        partial = native_excerpt(store, 's', {**query, 'max_bytes': '4'}, root)
        assert not partial['range_complete'] and not partial['line_end_complete']
        resumed = native_excerpt(store, 's', {'path': query['path'], 'offset': str(partial['next_offset']), 'max_bytes': str(len(b''.join(lines[100:103])) - 4)}, root)
        assert partial['text'] + resumed['text'] == b''.join(lines[100:103]).decode()
        with pytest.raises(KeyError, match='outside the original source'):
            native_excerpt(store, 's', {**query, 'start_line': '151', 'end_line': '153'}, root)
    finally:
        store.close()


def test_boolean_object_queries_accept_both_http_boolean_forms(tmp_path):
    from openroad_app_data_foundation.discovery import list_objects
    import pytest
    store = DataStore(tmp_path / 'boolean.sqlite')
    try:
        pack = sample()
        pack['entities'][0]['attributes']['is_macro'] = 1
        store.register(pack)
        for enabled in ('true', '1'):
            result = list_objects(store, 's', {'kind': 'instance', 'is_macro': enabled, 'include_physical': enabled})
            assert [row['name'] for row in result['objects']] == ['u']
            assert result['objects'][0]['physical']['bbox_um_array'] == [0, 0, .005, .01]
        assert list_objects(store, 's', {'kind': 'instance', 'is_macro': 'false'})['count'] == 0
        with pytest.raises(ValueError, match='must be 0'):
            list_objects(store, 's', {'kind': 'instance', 'is_macro': 'maybe'})
    finally:
        store.close()
