"""Report-order and native-name timing ranking choices are explicit and stable."""
from openroad_app_data_foundation.repository import DataStore
from openroad_app_data_foundation.queries import list_timing_paths
from tests.test_eda_engineering import sample
import pytest


def test_equal_path_slack_can_use_full_native_names(tmp_path):
    pack=sample()
    first=pack['timing_paths'][0]
    first.update(startpoint='z/Q',endpoint='z/D',slack=-1)
    pack['timing_paths'].append({**first,'path_id':'second','startpoint':'a/Q','endpoint':'a/D'})
    store=DataStore(tmp_path/'d.sqlite')
    try:
        store.register(pack)
        query={'sort':'slack','order':'worst','limit':'1'}
        report=list_timing_paths(store,'s',query)
        names=list_timing_paths(store,'s',{**query,'tie_break':'native_names'})
        assert report['timing_paths'][0]['path_id']=='p'
        assert names['timing_paths'][0]['path_id']=='second'
        assert names['tie_break']=='native_names'
    finally:
        store.close()


def test_native_path_type_filter_keeps_asynchronous_max_and_excludes_min(tmp_path):
    pack = sample()
    first = pack['timing_paths'][0]
    first.update(path_type='max', check='setup', group='clock', slack=-.1)
    pack['timing_paths'].extend([
        {**first, 'path_id': 'async', 'group': 'asynchronous', 'slack': -.3},
        {**first, 'path_id': 'hold', 'path_type': 'min', 'check': 'hold', 'slack': -.5}])
    store = DataStore(tmp_path / 'native-types.sqlite')
    try:
        store.register(pack)
        query = {'path_type': 'max', 'sort': 'slack', 'limit': '1', 'fields': 'path_id,path_type,group,slack_ns'}
        result = list_timing_paths(store, 's', query)
        assert result['count'] == 2 and result['timing_paths'][0]['path_id'] == 'async'
        assert result['filters']['path_type'] == 'max'
        assert list_timing_paths(store, 's', {**query, 'path_type': 'min'})['timing_paths'][0]['path_id'] == 'hold'
        with pytest.raises(ValueError, match='path_type must be max|min'):
            list_timing_paths(store, 's', {**query, 'path_type': 'maximum'})
    finally:
        store.close()
