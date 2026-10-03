"""Complete signed arrival increments must not use page or clock substitutes."""
import pytest

from openroad_app_data_foundation.repository import DataStore
from openroad_app_data_foundation.server import Handler
from tests.test_eda_engineering import sample


def test_full_path_increment_summary_excludes_clocks_and_preserves_first_tie(tmp_path):
    pack = sample()
    pack['timing_points'] = [
        {'point_id': 'clock', 'path_id': 'p', 'ordinal': 0, 'arrival': 999,
         'pin_name': 'clk', 'path_section': 'source_clock_path'},
        {'point_id': 'port', 'path_id': 'p', 'ordinal': 1, 'arrival': 1e-9,
         'pin_name': 'in', 'instance_name': None, 'path_section': 'source_path'},
        {'point_id': 'a', 'path_id': 'p', 'ordinal': 2, 'arrival': 1.25e-9,
         'pin_name': 'u/A', 'instance_name': 'u', 'instance_id': 'i', 'path_section': 'source_path'},
        {'point_id': 'z', 'path_id': 'p', 'ordinal': 3, 'arrival': 1.5e-9,
         'pin_name': 'u/Z', 'instance_name': 'u', 'instance_id': 'i', 'path_section': 'source_path'},
        {'point_id': 'repeat', 'path_id': 'p', 'ordinal': 4, 'arrival': 1.25e-9,
         'pin_name': 'u/A', 'instance_name': 'u', 'instance_id': 'i', 'path_section': 'source_path'},
        {'point_id': 'capture', 'path_id': 'p', 'ordinal': 5, 'arrival': -999,
         'pin_name': 'capture', 'path_section': 'target_clock_path'}]
    store = DataStore(tmp_path / 'increments.sqlite')
    try:
        store.register(pack)
        handler = Handler.__new__(Handler)
        handler.store, handler.auto_import = store, False
        path = '/snapshots/s/timing-paths/p/engineering'
        tiny = handler._get(path, {'limit': '1', 'fields': 'data_path_increments'})
        full = handler._get(path, {'limit': '100'})
        result = tiny['data_path_increments']
        assert result == full['data_path_increments']
        assert 'points' not in tiny
        assert result['status'] == 'complete' and result['point_count'] == 4
        assert result['cell_pair_count'] == 2 and result['wire_pair_count'] == 1
        assert result['cell_increment_ns'] == pytest.approx(0)
        assert result['wire_increment_ns'] == result['total_increment_ns'] == pytest.approx(0.25)
        assert result['largest_increment']['from_pin'] == 'in'
        assert result['largest_increment']['to_pin'] == 'u/A'
        assert result['largest_increment']['tie_count'] == 2
        overview = handler._get('/snapshots/s/timing-overview', {
            'include_path_details': '1', 'fields': 'path_details.data_path_increments'})
        assert overview['path_details'][0]['data_path_increments'] == result
    finally:
        store.close()


@pytest.mark.parametrize('arrival', [None, True, '0', float('nan'), float('inf')])
def test_missing_or_invalid_arrival_cannot_be_counted_as_zero(arrival):
    from openroad_app_data_foundation.path_increments import data_path_increments
    result = data_path_increments([{'arrival': 1}, {'arrival': arrival}, {'arrival': 2}])
    assert result['status'] == 'partial' and result['missing_arrival_point_indices'] == [1]
    assert result['cell_increment_ns'] is result['wire_increment_ns'] is result['total_increment_ns'] is None
    assert result['largest_increment'] is None


def test_empty_and_single_point_paths_have_different_scope():
    from openroad_app_data_foundation.path_increments import data_path_increments
    empty = data_path_increments([])
    assert empty['status'] == 'not_extracted' and empty['total_increment_ns'] is None
    single = data_path_increments([{'arrival': 0, 'pin_name': 'port'}])
    assert single['status'] == 'complete' and single['total_increment_ns'] == 0
    assert single['adjacent_pair_count'] == 0 and single['largest_increment'] is None
