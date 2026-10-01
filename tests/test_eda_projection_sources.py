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
        assert paths['record_sources'][0]['record_id'] == 'p'
        for result in (list_timing_points(store, 's', {'fields': 'pin_name,arrival'}),
                       path_points(store, 's', 'p', {'fields': 'pin_name,arrival'})):
            assert len(result['evidence']) == 1
            assert {item['record_id'] for item in result['record_sources']} == {'clock', 'in', 'out'}
            for link in result['record_sources']:
                record_id = unquote(link['evidence_path'].split('/')[-2])
                assert record_id == link['record_id']
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
        full = path_points(store, 's', 'p', {})
        compact = path_points(store, 's', 'p', {'source_detail': 'compact'})
        assert compact['timing_points'] == [{k: v for k, v in row.items() if k != 'evidence'} for row in full['timing_points']]
        assert compact['record_sources']['record_ids'] == ['clock', 'in', 'out']
        assert compact['evidence'][0]['artifact_id'] == 'report'
    finally:
        store.close()
