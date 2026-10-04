"""Native pin-net ranking must be complete, deduplicated and independent of page size."""
import base64

import pytest

from openroad_app_data_foundation import pin_inventory as inventory
from openroad_app_data_foundation.pin_net_ranking import ranked_nets, ranking_script
from openroad_app_data_foundation.repository import DataStore
from tests.test_eda_engineering import sample
from tests.test_eda_pin_types import row


def net(identifier, name, loads, macros, receivers=0, drivers=()):
    header = '\t'.join(['EDA_NET', str(identifier), base64.b64encode(name.encode()).decode(),
                       str(loads), str(macros), str(receivers), str(len(drivers))])
    return '\n'.join([header, *['\t'.join(['EDA_NET_DRIVER', str(identifier),
        base64.b64encode(pin.encode()).decode()]) for pin in drivers]])


def test_net_ranking_uses_complete_candidates_native_bus_names_and_distinct_ids():
    text = 'EDA_NET_TOTAL 4\n' + '\n'.join([
        net(1, 'u/QB\\[1\\]', 2, 0), net(2, 'u/QB\\[10\\]', 2, 1),
        net(3, 'u/QB\\[0\\]', 2, 2), net(4, 'other', 3, 1)])
    first = ranked_nets(text, {'limit': '2'})
    second = ranked_nets(text, {'limit': '2', 'offset': '2'})
    assert [r['name'] for r in first['nets'] + second['nets']] == ['other', 'u/QB[0]', 'u/QB[10]', 'u/QB[1]']
    assert first['count'] == second['count'] == 4
    assert first['next_offset'] == 2 and second['next_offset'] is None
    assert second['nets'][0]['native_name'] == 'u/QB\\[10\\]'
    assert second['nets'][0]['receiving_macro_count'] == 1
    assert [r['rank'] for r in first['nets'] + second['nets']] == [1, 2, 3, 4]
    with pytest.raises(ValueError, match='incomplete'):
        ranked_nets(text.replace('EDA_NET_TOTAL 4', 'EDA_NET_TOTAL 5'), {})
    with pytest.raises(ValueError, match='duplicated'):
        ranked_nets('EDA_NET_TOTAL 2\n' + net(1, 'a', 1, 0) + '\n' + net(1, 'a', 1, 0), {})


def test_pin_inventory_and_net_statistics_use_one_original_native_query(tmp_path, monkeypatch):
    pack = sample(); pack['entities'][0]['attributes']['native_id'] = '17'
    text = 'EDA_PIN_TOTAL 2\n' + row(1, 'Z', 'SIGNAL', 'OUTPUT', 'n', 'SIGNAL') + '\n'
    text += row(2, 'ZZ', 'SIGNAL', 'OUTPUT', 'n', 'SIGNAL') + '\n'
    text += 'EDA_NET_TOTAL 1\n' + net(5, 'n', 4, 2, 3, ('top_input', 'u/Z')) + '\n'
    calls = []
    def native(store, client, sid, payload, root):
        calls.append(payload)
        assert 'dict set selected_nets [$n getId] $n' in payload['script']
        assert '[$m getSigType] ne "SIGNAL"' in payload['script']
        assert '[$m getIoType] ne "OUTPUT"' in payload['script']
        return {'status': 'succeeded', 'run': {'run_id': 'native'},
                'excerpt': {'text': text, 'truncated': False}, 'source': {'artifact_id': 'report'}}
    monkeypatch.setattr(inventory, 'submit_native_query', native)
    store = DataStore(tmp_path / 's.sqlite')
    try:
        store.register(pack)
        result = inventory.pin_inventory(store, None, 's', 'u', {
            'pin_type': 'SIGNAL', 'direction': 'OUTPUT', 'net_sort': 'load_count', 'limit': '1'}, tmp_path)
        assert len(calls) == 1 and not calls[0]['with_timing']
        assert result['count'] == 2 and result['net_ranking']['count'] == 1
        assert result['net_ranking']['nets'][0]['load_count'] == 4
        assert result['net_ranking']['nets'][0]['receiving_macro_count'] == 2
        assert result['net_ranking']['nets'][0]['receiving_instance_count'] == 3
        assert result['net_ranking']['nets'][0]['drivers'] == ['top_input', 'u/Z']
        assert result['evidence'] == [{'artifact_id': 'report'}]
    finally:
        store.close()


def test_net_ranking_rejects_unknown_sort_and_tcl_injection_before_execution():
    for query in [{'net_sort': 'unknown'}, {'net_sort': 'load_count', 'direction': 'OUTPUT"; error bad'},
                  {'net_sort': 'load_count', 'pin_type': 'SIGNAL"; error bad'}]:
        with pytest.raises(ValueError):
            ranking_script(query)


def test_complete_driver_sets_preserve_native_names_and_reject_incomplete_records():
    native = (r'core.bus\[2\]/Q', r'core.bus\[10\]/Q', 'input_port')
    text = 'EDA_NET_TOTAL 1\n' + net(3, 'n', 7, 2, 4, native)
    row = ranked_nets(text, {})['nets'][0]
    assert row['driver_count'] == 3 and row['receiving_instance_count'] == 4
    assert row['drivers'] == ['core.bus[10]/Q', 'core.bus[2]/Q', 'input_port']
    assert row['native_drivers'] == sorted(native)
    with pytest.raises(ValueError, match='drivers are incomplete'):
        ranked_nets('\n'.join(text.splitlines()[:-1]), {})
    with pytest.raises(ValueError, match='drivers are incomplete or duplicated'):
        ranked_nets(text + '\n' + text.splitlines()[-1], {})
    empty = ranked_nets('EDA_NET_TOTAL 1\n' + net(1, 'undriven', 0, 0), {})['nets'][0]
    assert empty['drivers'] == [] and empty['driver_count'] == 0
