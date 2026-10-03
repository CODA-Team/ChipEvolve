"""Pair facts retain full intersections, native types and original placed geometry."""
import pytest

from openroad_app_data_foundation.instance_pair import instance_pair
from openroad_app_data_foundation.repository import DataStore
from openroad_app_data_foundation.server import Handler
from tests.test_eda_engineering import sample


@pytest.fixture
def pair_store(tmp_path):
    pack = sample()
    pack['entities'][0]['attributes']['orientation'] = 'R180'
    pack['physical_context'].append({'object_id': 'c', 'bbox': {
        'x_min': 40, 'y_min': 0, 'x_max': 50, 'y_max': 20}})
    pack['entities'].extend([
        {'object_id': key, 'kind': 'net', 'name': name, 'attributes': {'signal_type': net_type}}
        for key, name, net_type in [('s1', r'n\[2\]', 'SIGNAL'), ('s2', 'n[10]', 'SIGNAL'),
                                    ('clk', 'clk', 'CLOCK'), ('left_only', 'alone', 'SIGNAL')]])
    pack['relations'] = []
    for parent, nets in [('i', ['s1', 's1', 's2', 'clk', 'left_only', None]),
                         ('c', ['s1', 's2', 'clk'])]:
        for index, net in enumerate(nets):
            pin = parent + ':' + str(index)
            pack['entities'].append({'object_id': pin, 'kind': 'pin', 'parent_id': parent,
                'name': parent + '/p[' + str(index) + ']',
                'attributes': {'native_pin_signal_type': 'CLOCK' if net == 's1' else 'SIGNAL'}})
            if net:
                pack['relations'].append({'relation_id': pin + '-net', 'subject_id': pin,
                                          'predicate': 'connected_to', 'object_id': net})
    store = DataStore(tmp_path / 'pair.sqlite')
    store.register(pack)
    try:
        yield store
    finally:
        store.close()


def test_complete_net_intersection_counts_shared_ids_once_and_filters_net_own_type(pair_store):
    result = instance_pair(pair_store, 's', 'u', {'with_instance': 'clock_buf', 'signal_type': 'SIGNAL', 'limit': '1'})
    shared = result['shared_nets']
    assert shared['count'] == 2 and shared['returned'] == 1 and shared['next_offset'] == 1
    assert result['truncated']
    assert shared['items'][0]['name'] == 'n[10]'
    next_page = instance_pair(pair_store, 's', 'i', {'with_instance': 'c', 'signal_type': 'SIGNAL', 'offset': '1'})
    assert next_page['shared_nets']['items'][0]['native_name'] == r'n\[2\]'
    assert next_page['shared_nets']['count'] == 2
    end = instance_pair(pair_store, 's', 'i', {'with_instance': 'c', 'signal_type': 'SIGNAL', 'offset': '2'})
    assert end['shared_nets']['count'] == 2 and end['shared_nets']['items'] == []
    clock = instance_pair(pair_store, 's', 'i', {'with_instance': 'c', 'signal_type': 'CLOCK'})
    assert clock['shared_nets']['count'] == 1 and clock['shared_nets']['items'][0]['name'] == 'clk'
    missing = instance_pair(pair_store, 's', 'i', {'with_instance': 'c', 'signal_type': 'ANALOG'})
    assert missing['shared_nets']['count'] == 0 and missing['shared_nets']['next_offset'] is None


def test_reverse_self_and_placed_geometry_are_independent_of_page(pair_store):
    first = instance_pair(pair_store, 's', 'i', {'with_instance': 'c', 'limit': '1'})
    reverse = instance_pair(pair_store, 's', 'c', {'with_instance': 'i', 'order': 'desc'})
    assert first['geometry']['bbox_center_manhattan_um'] == pytest.approx(.02)
    assert reverse['geometry']['bbox_center_manhattan_um'] == first['geometry']['bbox_center_manhattan_um']
    assert reverse['geometry']['bbox_center_delta_um'][0] == pytest.approx(-.02)
    assert first['left']['orientation'] == 'R180'
    assert first['shared_nets']['count'] == reverse['shared_nets']['count'] == 3
    assert [r['name'] for r in reverse['shared_nets']['items']] == ['n[2]', 'n[10]', 'clk']
    self_pair = instance_pair(pair_store, 's', 'i', {'with_instance': 'i'})
    assert self_pair['shared_nets']['count'] == 4
    assert self_pair['geometry']['bbox_center_manhattan_um'] == 0


def test_missing_bbox_does_not_replace_geometry_with_zero_or_hide_connections(pair_store):
    pair_store.connection.execute("DELETE FROM records WHERE snapshot_id='s' AND record_type='physical_context' AND record_id='c'")
    result = instance_pair(pair_store, 's', 'i', {'with_instance': 'c'})
    assert result['geometry']['availability'] == 'missing_bbox'
    assert result['geometry']['bbox_center_manhattan_um'] is None and result['right']['bbox_um'] is None
    assert result['shared_nets']['count'] == 3


def test_public_pair_projection_retains_total_and_native_names(pair_store):
    handler = Handler.__new__(Handler)
    handler.store, handler.auto_import = pair_store, False
    selected = handler._get('/snapshots/s/instances/u/pair', {'with_instance': 'clock_buf',
        'signal_type': 'SIGNAL', 'limit': '1', 'fields': 'geometry,shared_nets'})
    assert selected['shared_nets']['count'] == 2
    assert 'left' not in selected and 'right' not in selected
    assert selected['delivery']['full_details'].endswith('detail=full')


@pytest.mark.parametrize('query', [{}, {'with_instance': 'c', 'order': 'random'},
    {'with_instance': 'c', 'invented': '1'}, {'with_instance': 'c', 'signal_type': ''},
    {'with_instance': 'c', 'offset': '-1'}])
def test_pair_input_errors_are_explicit(pair_store, query):
    with pytest.raises(ValueError):
        instance_pair(pair_store, 's', 'i', query)


def test_pair_rejects_wrong_object_kind_and_missing_peer(pair_store):
    with pytest.raises(ValueError, match='one instance'):
        instance_pair(pair_store, 's', 'n', {'with_instance': 'c'})
    with pytest.raises(KeyError, match='instance not found'):
        instance_pair(pair_store, 's', 'i', {'with_instance': 'absent'})
