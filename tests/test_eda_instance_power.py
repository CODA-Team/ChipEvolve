"""Fresh object power must bind exact native identity and original analysis."""
from copy import deepcopy
import json

import pytest

from openroad_app_data_foundation import instance_power as module
from openroad_app_data_foundation.repository import DataStore
from openroad_app_data_foundation.server import Handler
from tests.test_eda_engineering import query_pair


@pytest.fixture
def store(tmp_path):
    parent,child=query_pair()
    for e in parent['entities']:
        if e['object_id']=='i':
            e['name']='unit\\[2\\]/ram'
            e['attributes']['native_id']='21'
    nested=deepcopy(child)
    nested['snapshot']['snapshot_id']='nested'
    nested['run_summary']['timing_context']['parent_snapshot_id']='child'
    db=DataStore(tmp_path/'power.sqlite')
    for pack in (parent,child,nested):db.register(pack)
    yield db
    db.close()


def outcome(report=None,status='succeeded',truncated=False):
    report=report if report is not None else [{'name':'unit\\[2\\]/ram',
         'internal':.0123,'switching':0.0,'leakage':.0002,'total':.0125}]
    return {'run':{'run_id':'fresh-power'},'status':status,'source':{'artifact_id':'original-report','sha256':'a'*64},
            'excerpt':{'text':'actual library warnings\nEDA_INSTANCE_POWER_BEGIN\n'+json.dumps(report)+'\nEDA_INSTANCE_POWER_END\n',
                       'truncated':truncated},'failure_details':[{'message':'actual native scene error'}] if status=='failed' else []}


@pytest.mark.parametrize('snapshot_id',['s','child','nested'])
def test_fresh_power_uses_exact_original_native_instance_not_report_sample(store,monkeypatch,snapshot_id):
    calls=[]
    def native(db,client,sid,query,root):
        calls.append((sid,query))
        assert sid=='s' and query['with_timing'] is True
        assert 'odb::dbInst_getInst $b 21' in query['script']
        assert 'get_cells -quiet [list $native_name]' in query['script']
        assert 'report_power -instances $cell -format json -digits 9' in query['script']
        return outcome()
    monkeypatch.setattr(module,'submit_native_query',native)
    result=module.instance_power(store,None,snapshot_id,'i',{},None)
    assert len(calls)==1
    assert result['snapshot']['snapshot_id']==snapshot_id
    assert result['object_facts_source']['snapshot']['snapshot_id']=='s'
    assert result['power_w']=={'internal':.0123,'switching':0.0,'leakage':.0002,'total':.0125}
    assert result['unit']=='W' and result['evidence'][0]['artifact_id']=='original-report'


def test_named_scene_and_power_projection_preserve_actual_tool_result(store,monkeypatch):
    scene='slow; corner [test]'
    def native(db,client,sid,query,root):
        import base64
        token=base64.b64encode(scene.encode()).decode()
        assert '-scene [binary decode base64 {'+token+'}]' in query['script']
        assert scene not in query['script']
        return outcome()
    monkeypatch.setattr(module,'submit_native_query',native)
    h=Handler.__new__(Handler);h.store,h.auto_import,h.execution_client=store,False,object()
    r=h._get('/snapshots/nested/instances/i/power',{'scene':scene,'fields':'power_w,unit,native_query'})
    assert r['power_w']['internal']==.0123 and r['unit']=='W'
    assert r['native_query']['run_id']=='fresh-power' and r['native_query']['status']=='succeeded'
    assert r['native_query']['result_path']=='/native-queries/fresh-power?wait_seconds=120'
    assert 'instance' not in r


@pytest.mark.parametrize('status',['failed','running','timed_out'])
def test_failed_or_pending_calculation_keeps_actual_status_without_power_defaults(store,monkeypatch,status):
    monkeypatch.setattr(module,'submit_native_query',lambda *a:outcome(status=status))
    r=module.instance_power(store,None,'s','i',{},None)
    assert r['native_query']['status']==status and 'power_w' not in r
    assert r['native_query']['report']['status']==status
    if status=='failed':assert r['native_query']['report']['failure_details'][0]['message']=='actual native scene error'


@pytest.mark.parametrize('report', [[],[{'name':'other','internal':1,'switching':0,'leakage':0,'total':1}],
    [{'name':'unit[2]/ram','internal':1,'switching':0,'total':1}],
    [{'name':'unit[2]/ram','internal':float('nan'),'switching':0,'leakage':0,'total':1}]])
def test_incomplete_wrong_object_or_nonfinite_native_report_is_not_accepted(store,monkeypatch,report):
    monkeypatch.setattr(module,'submit_native_query',lambda *a:outcome(report=report))
    with pytest.raises(ValueError,match='native instance power report'):
        module.instance_power(store,None,'s','i',{},None)


def test_invalid_original_native_id_never_executes_a_guess(store,monkeypatch):
    store.connection.execute("UPDATE records SET payload=json_set(payload,'$.attributes.native_id','bad') WHERE snapshot_id='s' AND record_type='entities' AND record_id='i'")
    store.connection.commit()
    monkeypatch.setattr(module,'submit_native_query',lambda *a:pytest.fail('invalid ID must not execute'))
    with pytest.raises(ValueError,match='native ID'):module.instance_power(store,None,'s','i',{},None)


def test_large_native_log_is_fully_read_before_extracting_actual_power(store,monkeypatch):
    from openroad_app_data_foundation import native_queries
    original=outcome()
    text='original native warning\n'*4000+original['excerpt']['text']
    first={**original,'excerpt':{'text':text[:1024],'truncated':True,'next_offset':1024}}
    submitted=[];reads=[]
    def submit(*args):submitted.append(args);return first
    def read(client,run_id,query):
        assert run_id=='fresh-power'
        offset=int(query['offset']);maximum=int(query['max_bytes']);end=min(len(text),offset+maximum)
        reads.append(offset)
        return {**original,'excerpt':{'text':text[offset:end],'truncated':end<len(text),'next_offset':end if end<len(text) else None}}
    monkeypatch.setattr(module,'submit_native_query',submit)
    monkeypatch.setattr(native_queries,'native_query_result',read)
    result=module.instance_power(store,None,'s','i',{},None)
    assert len(submitted)==1 and len(reads)>1
    assert result['power_w']['total']==.0125
    assert result['evidence'][0]['artifact_id']=='original-report'
