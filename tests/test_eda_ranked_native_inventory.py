"""Full candidate ranking and native classifications cannot use page/pin substitutes."""
import pytest

from openroad_app_data_foundation.discovery import list_objects
from openroad_app_data_foundation.native_inventory import net_inventory
from openroad_app_data_foundation.repository import DataStore


def test_ranked_area_counts_ties_and_missing_geometry_across_all_pages(tmp_path):
    pack = {'snapshot': {'snapshot_id': 's', 'design_id': 'd', 'stage': 'finish',
                         'revision_id': 'r', 'run_id': 'run', 'created_at': '2026-10-02'},
        'run_summary': {'dbu_per_micron': 2000},
        'entities': [{'object_id': name, 'name': name, 'kind': 'instance',
                      'attributes': {'is_macro': 1}} for name in ['a', 'z', 'small', 'missing']],
        'physical_context': [{'object_id': name, 'bbox': {'x_min': 0, 'y_min': 0,
            'x_max': width, 'y_max': 10}} for name, width in [('a', 20), ('z', 20), ('small', 5)]]}
    store = DataStore(tmp_path / 'd.sqlite')
    try:
        store.register(pack)
        query = {'kind': 'instance', 'is_macro': '1', 'sort': 'bbox_area', 'order': 'desc',
                 'limit': '1', 'fields': 'name'}
        first = list_objects(store, 's', query)
        second = list_objects(store, 's', {**query, 'offset': '1'})
        assert first['objects'] == [{'name': 'z'}]
        assert second['objects'] == [{'name': 'a'}]
        assert first['ranking'] == second['ranking']
        assert first['ranking']['candidate_count'] == 4
        assert first['ranking']['leading_value'] == 200
        assert first['ranking']['leading_tie_count'] == 2
        assert first['ranking']['missing_value_count'] == 1
        joined = list_objects(store, 's', {**query, 'include_engineering': '1',
            'fields': 'name,engineering.bbox_um,engineering.distinct_signal_net_count'})
        assert joined['objects'][0]['name'] == 'z'
        assert joined['objects'][0]['engineering']['distinct_signal_net_count'] == 0
        assert joined['objects'][0]['engineering']['bbox_um']['x_max'] == 0.01
        table = list_objects(store, 's', {**query, 'format': 'columns', 'fields': 'name,object_id'})
        assert table['object_columns'] == ['name', 'object_id']
        assert table['object_rows'] == [['z', 'z']]
        assert table['ranking'] == first['ranking']
        assert table['next_offset'] == first['next_offset']
    finally:
        store.close()


def test_native_special_flag_is_not_power_ground_sum(monkeypatch):
    class Store:
        def snapshot(self, identifier):
            return {'snapshot_id': identifier}
    def query(*args):
        return {'run': {'run_id': 'native'}, 'status': 'succeeded', 'source': {'artifact_id': 'real'},
            'excerpt': {'text': 'EDA_NET_TOTAL 4\nEDA_NET_SPECIAL 1\nEDA_NET_TYPE SIGNAL 2\nEDA_NET_TYPE POWER 1\nEDA_NET_TYPE GROUND 1\n'}}
    monkeypatch.setattr('openroad_app_data_foundation.native_inventory.submit_native_query', query)
    result = net_inventory(Store(), None, 's', None)
    assert result['special_net_count'] == 1
    assert result['counts_by_signal_type']['POWER'] + result['counts_by_signal_type']['GROUND'] == 2
    assert result['evidence'] == [{'artifact_id': 'real'}]


@pytest.mark.parametrize('text,truncated', [
    ('EDA_NET_TOTAL 5\nEDA_NET_SPECIAL 2\nEDA_NET_TYPE SIGNAL 3\n', False),
    ('EDA_NET_TOTAL 0\nEDA_NET_SPECIAL 1\n', False),
    ('EDA_NET_TOTAL 1\nEDA_NET_SPECIAL 0\nEDA_NET_TYPE SIGNAL 1\n', True)])
def test_incomplete_native_output_cannot_be_a_complete_inventory(monkeypatch, text, truncated):
    class Store:
        def snapshot(self, identifier): return {'snapshot_id': identifier}
    monkeypatch.setattr('openroad_app_data_foundation.native_inventory.submit_native_query',
        lambda *args: {'run': {'run_id': 'r'}, 'status': 'succeeded',
                       'excerpt': {'text': text, 'truncated': truncated}})
    with pytest.raises(ValueError, match='incomplete or malformed'):
        net_inventory(Store(), None, 's', None)
