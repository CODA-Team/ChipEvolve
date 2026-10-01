"""Path endpoint joins must preserve report/native distinctions and port semantics."""
import pytest

from openroad_app_data_foundation.path_endpoints import path_endpoints
from openroad_app_data_foundation.discovery import object_filter
from openroad_app_data_foundation.engineering import object_statistics
from openroad_app_data_foundation.repository import DataStore
from tests.test_eda_engineering import sample


@pytest.mark.parametrize('pin_case', ['instance', 'port', 'absent'])
def test_endpoint_join_retains_source_witness_and_native_placement(tmp_path, monkeypatch, pin_case):
    pack = sample()
    pack['timing_points'][2]['net_name'] = 'reported_net'
    pack['entities'].append({'object_id': 'pA', 'kind': 'pin', 'name': 'u/A', 'parent_id': 'i'})
    if pin_case != 'absent':
        pack['entities'].append({'object_id': 'pZ', 'kind': 'pin', 'name': 'u/Z',
                                **({'parent_id': 'i'} if pin_case == 'instance' else {})})
        pack['relations'] = [{'relation_id': 'rz', 'subject_id': 'pZ', 'object_id': 'n',
                              'predicate': 'connected_to'}]
    def original(store, snapshot_id, record_type, record_id):
        assert record_type == 'timing_points'
        return {'fragments': [{'record_id': record_id, 'source': 'independent original'}]}
    monkeypatch.setattr('openroad_app_data_foundation.path_endpoints.read_evidence', original)
    store = DataStore(tmp_path / 'endpoints.sqlite')
    try:
        store.register(pack)
        result = path_endpoints(store, 's', 'p')
        endpoint = result['endpoints']['endpoint']
        assert endpoint['original_point']['fragments'][0]['record_id'] == 'out'
        assert endpoint['timing_point']['net_name'] == 'reported_net'
        assert endpoint['point_fragments_path'].endswith('/out/fragments')
        if pin_case == 'absent':
            assert endpoint['status'] == 'unavailable'
            assert result['availability']['endpoint']['status'] == 'unavailable'
        else:
            assert endpoint['status'] == 'available'
            assert endpoint['native_connection']['net_name'] == 'signal'
            assert endpoint['timing_point']['net_name'] != endpoint['native_connection']['net_name']
            if pin_case == 'instance':
                assert endpoint['instance']['master'] == 'BUF'
                assert endpoint['instance']['bbox_dbu']['x_max'] == 10
            else:
                assert endpoint['instance'] is None
    finally:
        store.close()


def test_net_type_counts_remain_complete_with_group_pagination_and_unknown_types(tmp_path):
    pack = sample()
    pack['entities'].extend({'object_id': kind, 'kind': 'net', 'name': kind,
                            'attributes': {'signal_type': kind}}
                           for kind in ('CLOCK', 'POWER', 'GROUND'))
    pack['entities'].append({'object_id': 'unknown', 'kind': 'net', 'name': 'unknown'})
    store = DataStore(tmp_path / 'netcounts.sqlite')
    try:
        store.register(pack)
        result = object_statistics(store, 's', {'kind': 'net', 'group_by': 'signal_type', 'limit': '1'})
        assert result['truncated'] and result['object_count'] == 5
        assert result['counts_by_signal_type'] == {'SIGNAL': 1, 'CLOCK': 1, 'POWER': 1, 'GROUND': 1}
        assert result['power_ground_net_count'] == 2 and result['unclassified_net_count'] == 1
        assert 'isSpecial' in result['power_ground_count_basis']
    finally:
        store.close()


@pytest.mark.parametrize('filter_key,index', [('name', 'records_json_name'), ('parent_id', 'records_json_parent')])
def test_selective_pin_lookup_does_not_scan_the_entire_pin_kind(tmp_path, filter_key, index):
    store = DataStore(tmp_path / 'indexed.sqlite')
    try:
        store.register(sample())
        where, values = object_filter(store, 's', {'kind': 'pin', filter_key: 'u'})
        plan = store.connection.execute('EXPLAIN QUERY PLAN SELECT payload FROM records '
            "WHERE snapshot_id=? AND record_type='entities' AND " + where, ['s', *values]).fetchall()
        assert any(index in row['detail'] for row in plan)
        assert all('records_entity_kind' not in row['detail'] for row in plan)
    finally:
        store.close()
