"""Filtered native pin counts stay complete and preserve exact connection identity."""
import pytest

from openroad_app_data_foundation import pin_inventory as module
from openroad_app_data_foundation.repository import DataStore
from tests.test_eda_engineering import sample
from tests.test_eda_pin_types import row


def test_filtered_direction_counts_and_both_name_orders_before_paging(tmp_path, monkeypatch):
    pack = sample()
    pack['entities'][0]['attributes']['native_id'] = '17'
    exact = r'root.bus\[0\]'
    text = 'EDA_PIN_TOTAL 5\n' + '\n'.join([
        row(1, 'CLK', 'CLOCK', 'INPUT', exact, 'SIGNAL'),
        row(2, 'A[2]', 'SIGNAL', 'INPUT', exact, 'SIGNAL'),
        row(3, 'A[10]', 'SIGNAL', 'INPUT', exact, 'SIGNAL'),
        row(4, 'Z', 'SIGNAL', 'INPUT', '', ''),
        row(5, 'Q', 'SIGNAL', 'OUTPUT', 'root.bus[0]', 'SIGNAL')]) + '\n'
    monkeypatch.setattr(module, 'submit_native_query', lambda *args: {
        'status': 'succeeded', 'run': {'run_id': 'native'},
        'excerpt': {'text': text, 'truncated': False}, 'source': {'artifact_id': 'native-pins'}})
    store = DataStore(tmp_path / 'pins.sqlite')
    store.register(pack)
    try:
        query = {'pin_type': 'SIGNAL', 'direction': 'INPUT', 'sort': 'name', 'limit': '1'}
        first = module.pin_inventory(store, None, 's', 'u', query, tmp_path)
        last = module.pin_inventory(store, None, 's', 'u', {**query, 'order': 'desc'}, tmp_path)
        middle = module.pin_inventory(store, None, 's', 'u', {**query, 'offset': '1'}, tmp_path)
        lower = module.pin_inventory(store, None, 's', 'u', {**query, 'pin_type': 'signal', 'direction': 'input'}, tmp_path)
        assert lower['pins'] == first['pins'] and lower['selection'] == first['selection']
        assert first['selection'] == last['selection'] == middle['selection']
        assert first['selection']['pin_count'] == 3
        assert first['selection']['connected_pin_count'] == 2
        assert first['selection']['distinct_net_count'] == 1
        assert first['pin_counts_by_native_type'] == {'CLOCK': 1, 'SIGNAL': 4}
        assert first['distinct_net_counts_by_native_pin_type'] == {'CLOCK': 1, 'SIGNAL': 2}
        assert first['pins'][0]['local_name'] == 'A[10]'
        assert middle['pins'][0]['local_name'] == 'A[2]'
        assert last['pins'][0]['local_name'] == 'Z'
        assert first['pins'][0]['net_name'] == 'root.bus[0]'
        assert first['pins'][0]['net_native_name'] == exact
        assert last['pins'][0]['net_name'] is None and last['pins'][0]['net_native_name'] is None
        assert all(r['count'] == 3 and r['returned'] == 1 and r['truncated'] for r in [first, last, middle])
        assert first['evidence'] == [{'artifact_id': 'native-pins'}]
    finally:
        store.close()


@pytest.mark.parametrize('query', [
    {'pin_type': 'SIGNLA'}, {'direction': 'INPUTS'}, {'sort': 'fanout'},
    {'order': 'worst'}, {'limit': '-1'}, {'offset': '-1'}])
def test_invalid_inventory_scope_does_not_start_a_native_run(tmp_path, monkeypatch, query):
    def unexpected(*args):
        raise AssertionError('Invalid query started a native operation')
    monkeypatch.setattr(module, 'submit_native_query', unexpected)
    with pytest.raises(ValueError):
        module.pin_inventory(None, None, 's', 'u', query, tmp_path)
