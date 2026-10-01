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
        files = native_files(store, 's', {'kind': 'results'}, root)
        items = {item['relative_path'].rsplit('/', 1)[-1]: item for item in files['files']['items']}
        assert items['6_final.odb']['size_bytes'] == len(b'current bytes')
        assert items['6_final.odb']['producer_manifest_entry'] == declared
        assert items['extra.txt']['producer_manifest_entry'] is None
        assert 'literal original producer declaration' in files['digest_basis']
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
