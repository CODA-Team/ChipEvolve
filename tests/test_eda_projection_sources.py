"""Selecting facts must not lose their real source or claim a false locator."""
from urllib.parse import unquote

from openroad_app_data_foundation.queries import list_timing_paths, list_timing_points, path_points
from openroad_app_data_foundation.repository import DataStore
from tests.test_eda_engineering import sample


def test_compact_path_and_point_facts_keep_deduplicated_source_and_exact_record_links(tmp_path):
    pack = sample()
    ref = {'artifact_id': 'report', 'sha256': 'a' * 64, 'logical_path': 'original.json'}
    pack['timing_paths'][0]['evidence'] = [{**ref, 'detail': {'path_index': 0}}]
    for point in pack['timing_points']:
        point['evidence'] = [{**ref, 'detail': {'point_id': point['point_id']}}]
    store = DataStore(tmp_path / 'projection.sqlite')
    try:
        store.register(pack)
        paths = list_timing_paths(store, 's', {'fields': 'path_id,slack'})
        assert paths['evidence'][0]['artifact_id'] == 'report'
        assert 'detail' not in paths['evidence'][0]
        assert paths['record_sources']['record_ids'] == ['p']
        for result in (list_timing_points(store, 's', {'fields': 'pin_name,arrival'}),
                       path_points(store, 's', 'p', {'fields': 'pin_name,arrival'})):
            assert len(result['evidence']) == 1
            assert set(result['record_sources']['record_ids']) == {'clock', 'in', 'out'}
            for record_id in result['record_sources']['record_ids']:
                from urllib.parse import quote
                route = result['record_sources']['evidence_template'].replace('{record_id}', quote(record_id, safe=''))
                assert unquote(route.split('/')[-2]) == record_id
                original = store.record_evidence('s', 'timing_points', record_id)[0]['evidence']
                assert original['detail']['point_id'] == record_id
                assert original['sha256'] == result['evidence'][0]['sha256']
    finally:
        store.close()


def test_compact_source_templates_recover_every_original_point_locator(tmp_path):
    from urllib.parse import quote
    pack = sample()
    ref = {'artifact_id': 'report', 'sha256': 'a' * 64, 'logical_path': 'original.json'}
    for point in pack['timing_points']:
        point['evidence'] = [{**ref, 'detail': {'point_id': point['point_id']}}]
    store = DataStore(tmp_path / 'templates.sqlite')
    try:
        store.register(pack)
        result = path_points(store, 's', 'p', {'fields': 'pin_name', 'source_detail': 'compact'})
        sources = result['record_sources']
        assert sources['record_ids'] == ['clock', 'in', 'out']
        assert result['evidence'][0]['sha256'] == ref['sha256']
        for record_id in sources['record_ids']:
            route = sources['evidence_template'].replace('{record_id}', quote(record_id, safe=''))
            assert unquote(route.split('/')[-2]) == record_id
            original = store.record_evidence('s', 'timing_points', record_id)[0]['evidence']
            assert original['detail']['point_id'] == record_id
    finally:
        store.close()


def test_compact_sources_without_field_selection_preserve_full_point_facts(tmp_path):
    pack = sample()
    pack['timing_points'][1].update(arrival=.2, evidence=[{'artifact_id': 'report', 'detail': {'point': 1}}])
    store = DataStore(tmp_path / 'compact-default.sqlite')
    try:
        store.register(pack)
        full = path_points(store, 's', 'p', {'detail': 'full'})
        compact = path_points(store, 's', 'p', {'source_detail': 'compact'})
        assert compact['timing_points'] == [{k: v for k, v in row.items() if k not in ('evidence', 'identity_references')} for row in full['timing_points']]
        assert compact['record_sources']['record_ids'] == ['clock', 'in', 'out']
        assert compact['evidence'][0]['artifact_id'] == 'report'
    finally:
        store.close()


def test_default_timing_summary_retains_every_fact_and_scoped_full_recovery(tmp_path):
    from urllib.parse import urlsplit, parse_qs
    pack = sample()
    pack['timing_paths'][0]['point_ids'] = ['clock', 'in', 'out']
    store = DataStore(tmp_path / 'summary.sqlite')
    try:
        store.register(pack)
        summary = path_points(store, 's', 'p', {'path_section': 'source_path', 'limit': '1', 'offset': '1'})
        full_query = {key: values[0] for key, values in parse_qs(urlsplit(summary['delivery']['full_details']).query).items()}
        full = path_points(store, 's', 'p', full_query)
        assert summary['count'] == full['count'] == 2
        assert summary['timing_points'] == [{k: v for k, v in row.items() if k not in ('evidence', 'identity_references')} for row in full['timing_points']]
        all_points = path_points(store, 's', 'p', {'detail': 'full'})['timing_points']
        assert all_points[1]['identity_references']['instance_id']['canonical']['hierarchical_name'] == 'u'
        paths = list_timing_paths(store, 's', {})
        assert 'point_ids' not in paths['timing_paths'][0]
        assert list_timing_paths(store, 's', {'detail': 'full'})['timing_paths'][0]['point_ids'] == ['clock', 'in', 'out']
    finally:
        store.close()
