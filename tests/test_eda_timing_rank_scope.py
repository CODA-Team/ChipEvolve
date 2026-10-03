"""Rank actual native arrival facts before paging, retaining scope and nulls."""
import pytest

from openroad_app_data_foundation.queries import list_timing_paths, list_timing_points
from openroad_app_data_foundation.repository import DataStore
from tests.test_eda_engineering import sample


@pytest.fixture
def rank_store(tmp_path):
    pack = sample()
    pack['timing_paths'] = [{'path_id': key, 'path_type': 'max', 'check': 'setup',
        'startpoint': start, 'endpoint': 'u/D', 'group': group, 'data_arrival_time': value,
        'slack': slack, 'unit': 's'} for key, start, group, value, slack in [
        ('early', 'a', 'clk', 0., -2.), ('late', 'z', 'clk', 2e-9, 1.),
        ('tie', 'b', 'clk', 2e-9, .5), ('outside', 'c', 'other', 7e-9, -3.),
        ('unknown', 'd', 'clk', None, 0.)]]
    pack['timing_points'] = [{'point_id': key, 'path_id': 'early', 'arrival': value}
                             for key, value in [('pa', 0.), ('pb', 2e-9), ('pc', None)]]
    store = DataStore(tmp_path / 'ranks.sqlite')
    store.register(pack)
    try:
        yield store
    finally:
        store.close()


def test_arrival_ranking_is_native_not_slack_or_report_order_and_nulls_stay_last(rank_store):
    query = {'sort': 'arrival', 'order': 'worst', 'tie_break': 'native_names',
             'group': 'clk', 'limit': '1', 'fields': 'path_id,arrival_ns'}
    first = list_timing_paths(rank_store, 's', query)
    assert first['timing_paths'] == [{'path_id': 'tie', 'arrival_ns': 2.}]
    assert first['count'] == first['selection']['matching_count'] == 4
    assert first['selection']['ranking_before_paging'] and first['selection']['filters_before_paging']
    assert first['selection']['first_returned_rank'] == first['selection']['last_returned_rank'] == 1
    assert first['truncated'] and first['next_offset'] == 1
    page = list_timing_paths(rank_store, 's', {**query, 'offset': '1', 'limit': '3'})
    assert [r['path_id'] for r in page['timing_paths']] == ['late', 'early', 'unknown']
    assert page['timing_paths'][-1]['arrival_ns'] is None
    assert page['selection']['first_returned_rank'] == 2 and page['selection']['last_returned_rank'] == 4
    assert not page['truncated'] and page['count'] == 4
    best = list_timing_paths(rank_store, 's', {**query, 'order': 'best', 'limit': '10'})
    assert [r['path_id'] for r in best['timing_paths']] == ['early', 'tie', 'late', 'unknown']
    slack = list_timing_paths(rank_store, 's', {**query, 'sort': 'slack'})
    assert slack['timing_paths'][0]['path_id'] == 'early'
    points = list_timing_points(rank_store, 's', {'sort': 'arrival', 'order': 'worst'})
    assert [r['point_id'] for r in points['timing_points']] == ['pb', 'pa', 'pc']


def test_empty_and_unranked_page_does_not_claim_a_worst_rank(rank_store):
    empty = list_timing_paths(rank_store, 's', {'sort': 'arrival', 'group': 'absent'})
    assert empty['count'] == 0 and empty['selection']['first_returned_rank'] is None
    beyond = list_timing_paths(rank_store, 's', {'sort': 'arrival', 'offset': '20'})
    assert beyond['count'] == 5 and beyond['timing_paths'] == []
    assert beyond['selection']['last_returned_rank'] is None
    unranked = list_timing_paths(rank_store, 's', {'limit': '1'})
    assert not unranked['selection']['ranking_before_paging']
    assert unranked['selection']['first_returned_rank'] is None
