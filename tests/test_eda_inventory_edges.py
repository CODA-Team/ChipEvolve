"""Both ends of complete inventories share one scope without another native invocation."""
import pytest

from openroad_app_data_foundation import pin_inventory as pins
from openroad_app_data_foundation.engineering import object_statistics
from openroad_app_data_foundation.repository import DataStore
from tests.test_eda_geometry_statistics import pack
from tests.test_eda_engineering import sample
from tests.test_eda_pin_types import row


def test_group_tails_are_independent_of_head_offsets_and_group_pagination(tmp_path):
    data = pack()
    data['entities'].extend([{'object_id': name, 'kind': 'instance', 'name': name,
        'attributes': {'is_macro': value} if value is not None else {}}
        for name, value in [('m[10]', 1), (r'm\[2\]', 1), ('z', 1), ('logic[10]', 0), ('logic[2]', 0), ('unknown', None)]])
    store = DataStore(tmp_path / 'groups.sqlite')
    store.register(data)
    try:
        query = {'kind': 'instance', 'group_by': 'is_macro', 'include_names': '1',
                 'names_limit': '2', 'names_tail_limit': '2'}
        full = object_statistics(store, 's', query)
        groups = {g['value']: g['names'] for g in full['groups']}
        assert groups[1]['items'] == ['a', 'b']
        assert groups[1]['tail']['items'] == ['m[2]', 'z']
        assert groups[1]['tail']['offset'] == 3 and groups[1]['tail']['count'] == 5
        assert groups[0]['items'] == groups[0]['tail']['items'] == ['logic[10]', 'logic[2]']
        assert groups[None]['tail']['items'] == ['unknown'] and groups[None]['tail']['count'] == 1
        later = object_statistics(store, 's', {**query, 'names_offset': '4', 'limit': '1'})
        assert later['groups'][0]['names']['items'] == ['z']
        assert later['groups'][0]['names']['tail'] == groups[1]['tail']
        assert later['classification'] == full['classification']
        assert full['object_count'] == later['object_count'] == 8
        stored = object_statistics(store, 's', {**query, 'names_spelling': 'stored'})
        assert stored['groups'][0]['names']['tail']['items'] == [r'm\[2\]', 'z']
        regional = object_statistics(store, 's', {**query, 'region': '0,0,100,100',
            'region_units': 'um', 'intersection': 'positive_area', 'include_physical': '1'})
        assert regional['object_count'] == 1
        assert regional['groups'][0]['names']['items'] == regional['groups'][0]['names']['tail']['items'] == ['a']
        assert regional['geometry']['total_bbox_area_um2'] == 10000
        empty = object_statistics(store, 's', {**query, 'name': 'missing'})
        assert empty['object_count'] == 0 and empty['groups'] == []
    finally:
        store.close()


def test_pin_edges_and_filtered_totals_use_exactly_one_native_report(tmp_path, monkeypatch):
    data = sample()
    data['entities'][0]['attributes']['native_id'] = '17'
    text = 'EDA_PIN_TOTAL 5\n' + '\n'.join([
        row(1, 'CLK', 'CLOCK', 'INPUT', 'clock', 'SIGNAL'),
        row(2, 'A[2]', 'SIGNAL', 'INPUT', 'shared', 'SIGNAL'),
        row(3, 'A[10]', 'SIGNAL', 'INPUT', 'shared', 'SIGNAL'),
        row(4, 'Z', 'SIGNAL', 'INPUT', '', ''),
        row(5, 'Q', 'SIGNAL', 'OUTPUT', 'out', 'SIGNAL')]) + '\n'
    calls = []
    def native(*args):
        calls.append(args)
        return {'status': 'succeeded', 'run': {'run_id': 'one'},
                'excerpt': {'text': text, 'truncated': False}, 'source': {'artifact_id': 'original'}}
    monkeypatch.setattr(pins, 'submit_native_query', native)
    store = DataStore(tmp_path / 'pins.sqlite')
    store.register(data)
    try:
        query = {'pin_type': 'SIGNAL', 'direction': 'INPUT', 'limit': '1', 'tail_limit': '1'}
        actual = pins.pin_inventory(store, None, 's', 'u', query, tmp_path)
        assert len(calls) == 1
        assert actual['pins'][0]['local_name'] == 'A[10]'
        assert actual['pins_tail']['items'][0]['local_name'] == 'Z'
        assert actual['pins_tail']['offset'] == 2 and actual['pins_tail']['count'] == 3
        assert actual['selection']['pin_count'] == 3 and actual['selection']['distinct_net_count'] == 1
        reverse = pins.pin_inventory(store, None, 's', 'u', {**query, 'order': 'desc'}, tmp_path)
        assert len(calls) == 2
        assert reverse['pins'][0]['local_name'] == 'Z' and reverse['pins_tail']['items'][0]['local_name'] == 'A[10]'
        assert reverse['selection'] == actual['selection']
        empty = pins.pin_inventory(store, None, 's', 'u', {**query, 'direction': 'INOUT'}, tmp_path)
        assert empty['pins'] == empty['pins_tail']['items'] == []
        assert empty['pins_tail']['count'] == 0 and empty['selection']['distinct_net_count'] == 0
    finally:
        store.close()


@pytest.mark.parametrize('extra', [{'names_tail_limit': '0'}, {'names_tail_limit': '-1'},
                                  {'names_tail_limit': '10001'}, {'include_names': '0'}])
def test_invalid_group_tails_are_explicit(tmp_path, extra):
    store = DataStore(tmp_path / 'invalid.sqlite')
    store.register(pack())
    try:
        with pytest.raises(ValueError):
            object_statistics(store, 's', {'kind': 'instance', 'include_names': '1', 'names_tail_limit': '1', **extra})
    finally:
        store.close()


@pytest.mark.parametrize('size', ['0', '-1', '10001'])
def test_invalid_pin_tail_does_not_start_a_native_job(tmp_path, monkeypatch, size):
    def unexpected(*args):
        raise AssertionError('Invalid tail launched native work')
    monkeypatch.setattr(pins, 'submit_native_query', unexpected)
    with pytest.raises(ValueError):
        pins.pin_inventory(None, None, 's', 'u', {'tail_limit': size}, tmp_path)
