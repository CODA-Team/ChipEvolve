"""Repeated native queries retain complete original object facts and bounded names."""
from copy import deepcopy

import pytest

from openroad_app_data_foundation.engineering import path_engineering
from openroad_app_data_foundation.repository import DataStore
from openroad_app_data_foundation.timing_facts import timing_fact_snapshot
from openroad_app_data_foundation.timing_queries import submit_timing_query
from tests.test_eda_engineering import query_pair


def nested_pack():
    parent, child = query_pair()
    grandchild = deepcopy(child)
    grandchild['snapshot']['snapshot_id'] = 'grandchild'
    grandchild['run_summary']['timing_context']['parent_snapshot_id'] = 'child'
    return parent, child, grandchild


def test_second_supplemental_query_joins_complete_original_geometry_and_nets(tmp_path):
    parent, child, grandchild = nested_pack()
    store = DataStore(tmp_path / 'nested.sqlite')
    try:
        for pack in (parent, child, grandchild):
            store.register(pack)
        result = path_engineering(store, 'grandchild', 'p', {'signal_type': 'SIGNAL', 'limit': '1'})
        assert result['snapshot']['snapshot_id'] == 'grandchild'
        assert result['object_facts_source']['snapshot']['snapshot_id'] == 's'
        assert result['instance_names'] == ['u'] and result['net_names'] == ['signal']
        assert result['association_coverage']['status'] == 'complete'
        assert result['instance_bbox_union_um'] == {'x_min': 0, 'y_min': 0, 'x_max': .005, 'y_max': .01}
    finally:
        store.close()


@pytest.mark.parametrize('mismatch', ['database', 'stage'])
def test_every_parent_hop_checks_original_database_and_state_identity(tmp_path, mismatch):
    parent, child, grandchild = nested_pack()
    if mismatch == 'database':
        parent['snapshot']['source_artifacts'][0]['sha256'] = 'b' * 64
    else:
        parent['snapshot']['stage'] = 'place'
    store = DataStore(tmp_path / 'wrong-parent.sqlite')
    try:
        for pack in (parent, child, grandchild):
            store.register(pack)
        with pytest.raises(ValueError, match='database digest|different stage'):
            timing_fact_snapshot(store, store.snapshot('grandchild'))
    finally:
        store.close()


def test_corrupt_parent_cycle_is_an_explicit_error(tmp_path):
    parent, child, grandchild = nested_pack()
    parent['run_summary']['timing_context'] = {'parent_snapshot_id': 'grandchild'}
    store = DataStore(tmp_path / 'cycle.sqlite')
    try:
        for pack in (parent, child, grandchild):
            store.register(pack)
        with pytest.raises(ValueError, match='parent cycle'):
            timing_fact_snapshot(store, store.snapshot('grandchild'))
    finally:
        store.close()


def test_repeated_query_name_stays_bounded_while_immediate_parent_is_preserved(tmp_path, monkeypatch):
    import openroad_app_data_foundation.timing_queries as module
    parent, child, grandchild = nested_pack()
    store = DataStore(tmp_path / 'query.sqlite')
    class Client:
        def submit(self, task):
            self.task = task
            return {'run': {'run_id': 'native-job', 'status': 'queued'}}
    client = Client()
    from eda_toolkits import jobs
    monkeypatch.setattr(jobs, 'snapshot_inputs', lambda snapshot: ({}, []))
    try:
        for pack in (parent, child, grandchild):
            store.register(pack)
        result = submit_timing_query(store, client, 'grandchild', {'from_pin': 'u/A', 'to_pin': 'u/Z'})
        name = result['snapshot_id']
        assert name.startswith('s-query-') and len(name) == len('s-query-') + 12
        assert result['parent_snapshot_id'] == client.task['inputs']['parent_snapshot_id'] == 'grandchild'
        assert client.task['inputs']['from_pin'] == 'u/A' and client.task['inputs']['to_pin'] == 'u/Z'
    finally:
        store.close()
