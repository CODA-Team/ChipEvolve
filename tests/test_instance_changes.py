"""Paged inventory comparison must retain complete counts and refuse ambiguous matches."""
import pytest

from openroad_app_data_foundation.instance_changes import instance_changes
from openroad_app_data_foundation.repository import DataStore


def register(store,sid,instances,declared=None):
    store.register({'snapshot':{'snapshot_id':sid,'design_id':'chip','revision_id':sid,'run_id':'run-'+sid,'stage':'finish','created_at':'2026-10-09'},
      'run_summary':{'instance_count':len(instances) if declared is None else declared},
      'entities':[{'object_id':sid+'-'+str(i),'name':name,'kind':'instance','attributes':{'master':master}}
              for i,(name,master) in enumerate(instances)]})


@pytest.fixture
def store(tmp_path):
    value=DataStore(tmp_path/"data.sqlite")
    yield value
    value.close()


def test_page_limit_does_not_change_complete_master_change_count(store):
    register(store,'left',[('a','BUF_X1'),('b','BUF_X1'),('same','BUF_X1')])
    register(store,'right',[('a','BUF_X2'),('b','BUF_X4'),('same','BUF_X1')])
    first=instance_changes(store,'left','right',{'limit':'1'})
    second=instance_changes(store,'left','right',{'limit':'1','offset':'1'})
    assert first['status']=='available'
    assert first['count']==second['count']==first['master_changed_count']==2
    assert first['next_offset']==1 and second['next_offset'] is None
    assert [r['name'] for r in first['changes']+second['changes']]==['a','b']
    assert all(c['from']['record_id']!=c['to']['record_id'] for c in first['changes'])


def test_missing_inventory_does_not_claim_proven_removals(store):
    register(store,'left',[('a','BUF_X1')])
    register(store,'right',[],declared=1)
    result=instance_changes(store,'left','right',{})
    assert result['status']=='partial'
    assert not result['coverage'][1]['complete_native_inventory']
    assert result['removed_indexed_count']==1
    assert 'does not prove removal' in result['interpretation']


def test_duplicate_names_are_not_arbitrarily_matched(store):
    register(store,'left',[('a','BUF_X1'),('a','BUF_X2')])
    register(store,'right',[('a','BUF_X4')])
    result=instance_changes(store,'left','right',{})
    assert result['status']=='partial' and result['ambiguous_name_count']==1
    assert result['changes']==[] and result['master_changed_count']==0
