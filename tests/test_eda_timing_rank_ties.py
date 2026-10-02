"""Report-order and native-name timing ranking choices are explicit and stable."""
from openroad_app_data_foundation.repository import DataStore
from openroad_app_data_foundation.queries import list_timing_paths
from tests.test_eda_engineering import sample


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
